<#
.SYNOPSIS
  Delete the BOAT 2026 computer-use EC2 stack and all resources it created.
.EXAMPLE
  ./teardown.ps1
#>
[CmdletBinding()]
param(
  [string]$StackName = "boat-computer-use",
  [string]$Region    = "eu-west-1",
  [string]$Profile   = ""
)

$ErrorActionPreference = "Stop"
$base = @("--region", $Region)
if ($Profile) { $base += @("--profile", $Profile) }

Write-Host "Deleting stack '$StackName' in $Region ..." -ForegroundColor Cyan
& aws cloudformation delete-stack --stack-name $StackName @base
if ($LASTEXITCODE -ne 0) { throw "delete-stack failed" }

Write-Host "Waiting for deletion to complete..."
& aws cloudformation wait stack-delete-complete --stack-name $StackName @base
Write-Host "Stack '$StackName' deleted. All instance/SG/IAM resources are gone." -ForegroundColor Green
Write-Host "Note: the EC2 key pair is NOT deleted. Remove it manually if you want:"
Write-Host "  aws ec2 delete-key-pair --key-name boat-computer-use-key --region $Region"
