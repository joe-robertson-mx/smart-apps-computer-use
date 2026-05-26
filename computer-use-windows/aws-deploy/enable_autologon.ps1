# Enables Windows AutoAdminLogon as Administrator and auto-starts the BOAT
# demo on logon, then triggers a delayed reboot so SSM reports success first.
# Tradeoff: stores the Administrator password in plaintext in HKLM\Winlogon.
# Acceptable for a throwaway demo instance behind an IP-restricted SG.
$ErrorActionPreference = "Continue"
$log = "C:\autologon-setup.log"
function Log($m) { "$(Get-Date -Format o)  $m" | Tee-Object -FilePath $log -Append }
Log "autologon setup starting"

$winlogon = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
# Password is supplied at runtime via $env:AUTOLOGON_PASSWORD (set by the
# wrapper that builds the SSM JSON). We never commit the password to git.
$pw = $env:AUTOLOGON_PASSWORD
if (-not $pw) { throw "AUTOLOGON_PASSWORD env var is not set on the target host" }

Set-ItemProperty -Path $winlogon -Name "AutoAdminLogon"   -Value "1"             -Type String
Set-ItemProperty -Path $winlogon -Name "DefaultUserName"  -Value "Administrator" -Type String
Set-ItemProperty -Path $winlogon -Name "DefaultPassword"  -Value $pw             -Type String
# AutoLogonCount absent/0 == unlimited autologon attempts. Remove if present.
Remove-ItemProperty -Path $winlogon -Name "AutoLogonCount" -ErrorAction SilentlyContinue
Log "registry keys written"

# Drop start_demo_env.bat into the All-Users Startup folder so the demo starts
# automatically when Administrator's autologon session begins.
$startup = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp"
New-Item -ItemType Directory -Force -Path $startup | Out-Null
$ws = New-Object -ComObject WScript.Shell
$lnkPath = Join-Path $startup "Start BOAT Demo.lnk"
$sc = $ws.CreateShortcut($lnkPath)
$sc.TargetPath       = "C:\repos\smart-apps-computer-use\computer-use-windows\start_demo_env.bat"
$sc.WorkingDirectory = "C:\repos\smart-apps-computer-use\computer-use-windows"
$sc.WindowStyle      = 7   # minimized
$sc.Save()
Log "startup shortcut added"

"AUTOLOGON_OK" | Out-File C:\autologon-complete.txt -Encoding utf8
Write-Output "AUTOLOGON_OK_REBOOTING"
Log "scheduling reboot in 15 seconds"
# Delayed reboot so SSM gets a chance to report success before the agent dies.
& shutdown.exe /r /t 15 /c "AutoLogon configured - rebooting"
