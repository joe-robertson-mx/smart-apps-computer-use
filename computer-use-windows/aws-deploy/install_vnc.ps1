# Installs TightVNC (loopback-only, no auth) + websockify + noVNC, exposes a
# browser-viewable Windows desktop at http://<public-ip>:6080/vnc.html.
# Run on the EC2 host via SSM. Security relies on the security group (only
# the presenter's IP can reach 6080) and TightVNC bound to 127.0.0.1.
$ErrorActionPreference = "Continue"
$log = "C:\vnc-install.log"
function Log($m) { "$(Get-Date -Format o)  $m" | Tee-Object -FilePath $log -Append }
Log "vnc install starting"

$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine")
$choco = "C:\ProgramData\chocolatey\bin\choco.exe"

# 1. TightVNC server (silent, registered as service, firewall opened).
& $choco install -y tightvnc --no-progress `
  --params "/SERVER_REGISTER_AS_SERVICE=1 /SERVER_ADD_FIREWALL_EXCEPTION=1 /SET_USEVNCAUTHENTICATION=0 /VALUE_OF_USEVNCAUTHENTICATION=0 /SET_USECONTROLAUTHENTICATION=0 /VALUE_OF_USECONTROLAUTHENTICATION=0" 2>&1 | Tee-Object -FilePath $log -Append
Log "tightvnc installed"

# 2. Tighten config: loopback-only + no auth (SG + loopback are the controls).
$srv = "HKLM:\SOFTWARE\TightVNC\Server"
New-Item -Path $srv -Force | Out-Null
Set-ItemProperty -Path $srv -Name "UseVncAuthentication" -Value 0 -Type DWord
Set-ItemProperty -Path $srv -Name "UseControlAuthentication" -Value 0 -Type DWord
Set-ItemProperty -Path $srv -Name "LoopbackOnly" -Value 1 -Type DWord
Set-ItemProperty -Path $srv -Name "AllowLoopback" -Value 1 -Type DWord
Set-ItemProperty -Path $srv -Name "RfbPort" -Value 5900 -Type DWord
Restart-Service tvnserver -Force -ErrorAction SilentlyContinue
Log "tightvnc configured (loopback only, no auth)"

# 3. websockify (pip) + noVNC (git clone).
$py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = "C:\Python311\python.exe" }
& $py -m pip install --quiet websockify 2>&1 | Tee-Object -FilePath $log -Append
Log "websockify installed"

if (-not (Test-Path "C:\noVNC")) {
  $git = (Get-Command git.exe -ErrorAction SilentlyContinue).Source
  if (-not $git) { $git = "C:\Program Files\Git\bin\git.exe" }
  & $git clone --depth=1 https://github.com/novnc/noVNC.git C:\noVNC 2>&1 | Tee-Object -FilePath $log -Append
  Log "noVNC cloned"
}

# Convenience: vnc.html landing page that auto-connects without prompting.
Copy-Item -Path "C:\noVNC\vnc.html" -Destination "C:\noVNC\index.html" -Force -ErrorAction SilentlyContinue

# 4. Firewall (already added by bootstrap, ensure 6080 is open).
New-NetFirewallRule -DisplayName "noVNC 6080" -Direction Inbound -LocalPort 6080 -Protocol TCP -Action Allow -ErrorAction SilentlyContinue | Out-Null
Log "firewall ok"

# 5. Scheduled task to run websockify at boot (so it survives restarts).
$taskName = "noVNC-websockify"
$argLine  = "-m websockify --web=C:\noVNC 0.0.0.0:6080 127.0.0.1:5900"
$action   = New-ScheduledTaskAction -Execute $py -Argument $argLine
$trigger  = New-ScheduledTaskTrigger -AtStartup
$principal= New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Log "scheduled task registered + started"

Start-Sleep -Seconds 4
$listening = (Get-NetTCPConnection -State Listen -LocalPort 6080 -ErrorAction SilentlyContinue) -ne $null
$vncListen  = (Get-NetTCPConnection -State Listen -LocalPort 5900 -ErrorAction SilentlyContinue) -ne $null
Log ("6080 listening: " + $listening + "   5900 listening: " + $vncListen)

if ($listening -and $vncListen) {
  "VNC_INSTALL_OK" | Out-File C:\vnc-install-complete.txt -Encoding utf8
  Write-Output "VNC_INSTALL_OK"
} else {
  Write-Output "VNC_INSTALL_INCOMPLETE: 6080=$listening 5900=$vncListen"
}
