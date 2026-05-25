<#
.SYNOPSIS
  Deploy the BOAT 2026 computer-use Windows EC2 host to AWS (CloudFormation).

.DESCRIPTION
  One-command deploy. Auto-detects your public IP (for the security group),
  the default VPC and a public subnet, and creates an EC2 key pair if needed.
  Re-runnable: updates the stack in place. Tear down with teardown.ps1.

.EXAMPLE
  # Re-auth first if you use SSO:
  aws sso login
  ./deploy.ps1

.EXAMPLE
  ./deploy.ps1 -InstanceType t3.xlarge -Region eu-west-1
#>
[CmdletBinding()]
param(
  [string]$StackName  = "boat-computer-use",
  [string]$Region     = "eu-west-1",
  [string]$Profile    = "",
  [string]$KeyPairName= "boat-computer-use-key",
  [string]$AllowedCidr= "",            # default: your public IP /32
  [string]$InstanceType = "t3.large",
  [string]$VpcId      = "",            # default: the account's default VPC
  [string]$SubnetId   = ""             # default: a public subnet in that VPC
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$template = Join-Path $here "cloudformation.yaml"

# Thin wrapper so every call carries --region (+ --profile if set).
function Invoke-Aws {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CliArgs)
  $base = @("--region", $Region)
  if ($Profile) { $base += @("--profile", $Profile) }
  & aws @CliArgs @base
  if ($LASTEXITCODE -ne 0) { throw "aws $($CliArgs -join ' ') failed (exit $LASTEXITCODE)" }
}

Write-Host "=== Checking AWS credentials ===" -ForegroundColor Cyan
try {
  $id = Invoke-Aws sts get-caller-identity --output json | ConvertFrom-Json
  Write-Host "  Account $($id.Account) as $($id.Arn)"
} catch {
  Write-Host "  No valid credentials. Run 'aws sso login' (or set AWS keys) and retry." -ForegroundColor Red
  exit 1
}

if (-not $AllowedCidr) {
  $ip = (Invoke-RestMethod -Uri "https://checkip.amazonaws.com").Trim()
  $AllowedCidr = "$ip/32"
  Write-Host "  Detected your public IP -> AllowedCidr = $AllowedCidr"
}

if (-not $VpcId) {
  $VpcId = Invoke-Aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text
  if (-not $VpcId -or $VpcId -eq "None") { throw "No default VPC found. Pass -VpcId and -SubnetId explicitly." }
  Write-Host "  Using default VPC $VpcId"
}

if (-not $SubnetId) {
  $SubnetId = Invoke-Aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VpcId" "Name=map-public-ip-on-launch,Values=true" --query "Subnets[0].SubnetId" --output text
  if (-not $SubnetId -or $SubnetId -eq "None") {
    $SubnetId = Invoke-Aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VpcId" --query "Subnets[0].SubnetId" --output text
  }
  if (-not $SubnetId -or $SubnetId -eq "None") { throw "No subnet found in $VpcId. Pass -SubnetId explicitly." }
  Write-Host "  Using subnet $SubnetId"
}

# Ensure the key pair exists; create + save the .pem if not.
$pemPath = Join-Path $here "$KeyPairName.pem"
$keyExists = $true
try { Invoke-Aws ec2 describe-key-pairs --key-names $KeyPairName --output json | Out-Null }
catch { $keyExists = $false }
if (-not $keyExists) {
  Write-Host "  Key pair '$KeyPairName' not found - creating and saving $pemPath" -ForegroundColor Yellow
  $material = Invoke-Aws ec2 create-key-pair --key-name $KeyPairName --query "KeyMaterial" --output text
  $material | Out-File -FilePath $pemPath -Encoding ascii
  Write-Host "  Saved private key to $pemPath  (keep it safe; needed for the RDP password)"
} else {
  Write-Host "  Using existing key pair '$KeyPairName'"
  if (-not (Test-Path $pemPath)) {
    Write-Host "  NOTE: $pemPath not present locally. You'll need the matching .pem to decrypt the RDP password." -ForegroundColor Yellow
  }
}

Write-Host "=== Deploying stack '$StackName' ($Region) ===" -ForegroundColor Cyan
Invoke-Aws cloudformation deploy `
  --template-file $template `
  --stack-name $StackName `
  --capabilities CAPABILITY_IAM `
  --parameter-overrides `
    KeyPairName=$KeyPairName `
    AllowedCidr=$AllowedCidr `
    VpcId=$VpcId `
    SubnetId=$SubnetId `
    InstanceType=$InstanceType

Write-Host "=== Stack outputs ===" -ForegroundColor Cyan
$outs = Invoke-Aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
foreach ($o in $outs) { Write-Host ("  {0,-16} {1}" -f ($o.OutputKey + ":"), $o.OutputValue) }

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Wait ~5-8 min for the bootstrap (python/git/deps) to finish on the instance."
Write-Host "     Check by RDP: C:\bootstrap-complete.txt appears when done."
Write-Host "  2. Get the Administrator password:"
Write-Host "       aws ec2 get-password-data --instance-id <id> --priv-launch-key $pemPath --region $Region"
Write-Host "  3. RDP to the PublicIp (set the RDP window to ~1280x800), run 'Start BOAT Demo' on the desktop."
Write-Host "  4. Point the Mendix ComputerUse constant LocalhostIPAddress at the PublicIp."
Write-Host "  5. When finished, tear it down:  ./teardown.ps1 -StackName $StackName -Region $Region"
