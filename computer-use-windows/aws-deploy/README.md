# AWS EC2 deployment — BOAT 2026 computer-use Windows host

Stands up a **Windows Server 2022 (GUI)** EC2 instance that runs the three demo
components. You RDP into it and present that desktop as the one the AI agent
drives. Everything is one CloudFormation stack, so teardown is a single command.

```
deploy.ps1  ─► CloudFormation stack ─► Windows EC2 instance
                                        ├── Python + git installed (bootstrap)
                                        ├── repo cloned, deps installed
                                        ├── firewall opened for 8081 / 5050
                                        └── "Start BOAT Demo" desktop shortcut
```

## What gets created

| Resource | Purpose |
|----------|---------|
| EC2 instance (`t3.large`, Win Server 2022) | The Windows desktop the agent drives |
| Security group | RDP 3389, server 8081, portal 5050 — **only from your IP** |
| IAM role + instance profile | SSM management (Session Manager) |
| EC2 key pair (auto-created) | Decrypts the Windows Administrator password |
| Security group ingress 6080 | (Optional) noVNC web gateway — for embedding the desktop in a Mendix iframe |

## Prerequisites

- AWS CLI v2 configured for an account that can create EC2/IAM/CloudFormation.
- If you use SSO: **`aws sso login`** first (the token expires).
- Run from this folder in PowerShell.

## Deploy

```powershell
aws sso login                 # if you use SSO
./deploy.ps1                  # auto-detects your IP, default VPC, a public subnet
```

Useful overrides:

```powershell
./deploy.ps1 -Region eu-west-1 -InstanceType t3.xlarge -Profile myprofile
./deploy.ps1 -AllowedCidr 203.0.113.7/32 -VpcId vpc-xxx -SubnetId subnet-xxx
```

The script prints the **PublicIp** and the **ServerEndpoint**
(`http://<ip>:8081/computer_tool`).

## After deploy

1. Wait ~5–8 min for the bootstrap. It's done when `C:\bootstrap-complete.txt`
   exists (or watch `C:\bootstrap.log`).
2. Get the Administrator password:
   ```powershell
   aws ec2 get-password-data --instance-id <id> --priv-launch-key boat-computer-use-key.pem --region eu-west-1
   ```
3. **RDP** to the PublicIp as `Administrator`. **Set the RDP window to ~1280×800**
   so the model's coordinates match the desktop 1:1 (see the resolution note in
   the parent README — this is the single most important reliability setting).
4. Run the **"Start BOAT Demo"** desktop shortcut (= `start_demo_env.bat`, a clean
   restart each time).
5. In Mendix, set the `ComputerUse` constant `LocalhostIPAddress` to the EC2
   **PublicIp** so it calls the instance.

## Optional: noVNC web viewer (iframe in Mendix)

To show the live Windows desktop inside the Mendix app (mirroring the Linux
noVNC pattern), run `install_vnc.ps1` once on the instance via SSM after the
bootstrap finishes:

```powershell
# from your laptop (after aws sso login):
$cmd = aws ssm send-command `
  --instance-ids <i-...> `
  --document-name AWS-RunPowerShellScript `
  --parameters file://ssm_install_vnc.json `
  --region eu-west-1 --timeout-seconds 600 `
  --query "Command.CommandId" --output text
aws ssm wait command-executed --command-id $cmd --instance-id <i-...> --region eu-west-1
```

What it installs (persistent, restart-survives):

- **TightVNC server**, bound to `127.0.0.1:5900`, no VNC auth (the security
  group is the access control).
- **websockify + noVNC** on `0.0.0.0:6080`.
- A **scheduled task** that starts websockify at every boot.

Iframe URL for the Mendix widget (same parameter pattern as the Linux setup):

```
http://<public-ip>:6080/vnc.html?autoconnect=1&resize=scale&view_only=1&reconnect=1&reconnect_delay=2000
```

Caveat: TightVNC mirrors the active session. If nobody is RDP'd in, you'll see
the Windows login screen. Either RDP in to create that session, or run the
AutoLogon step below so the desktop is always live.

## Optional: AutoLogon + autostart (recommended for the demo)

The login screen blocks computer-use — pyautogui needs an active interactive
session, and a disconnected RDP locks the session. `enable_autologon.ps1`
configures Windows to auto-login as Administrator on every boot and adds the
demo's start script to the Startup folder, so the noVNC iframe always shows a
live, demo-ready desktop with no RDP needed.

**Tradeoff:** stores the Administrator password in plaintext in the registry
(`HKLM\...\Winlogon\DefaultPassword`). Acceptable for a throwaway demo instance
behind an IP-restricted security group; not for long-lived/shared hosts.

```powershell
# Get the admin password (decrypted via the .pem from deploy.ps1):
$pw = aws ec2 get-password-data --instance-id <i-...> `
        --priv-launch-key boat-computer-use-key.pem `
        --region eu-west-1 --query PasswordData --output text

# Build the SSM payload: set the env var, then run the sanitized script.
$script = Get-Content -Raw enable_autologon.ps1
$payload = "`$env:AUTOLOGON_PASSWORD = '$pw'`n$script"
@{ commands = @($payload) } | ConvertTo-Json -Depth 5 | Out-File ssm_autologon.json -Encoding utf8

$cmd = aws ssm send-command --instance-ids <i-...> `
        --document-name AWS-RunPowerShellScript `
        --parameters file://ssm_autologon.json `
        --region eu-west-1 --query "Command.CommandId" --output text
aws ssm wait command-executed --command-id $cmd --instance-id <i-...> --region eu-west-1
```

The instance reboots ~15 s after the script reports success; SSM comes back
online ~60-90 s later with Administrator already logged in.

## Teardown (stop billing)

```powershell
./teardown.ps1
```

Deletes the instance, security group, and IAM role. The key pair is left in
place (delete manually if you want).

## Important caveats

- **Keep the RDP session connected during the demo.** `pyautogui` needs an
  active interactive desktop session to move the mouse and capture the screen.
  If you disconnect RDP the session locks and the agent's actions/screenshots
  fail. For a hands-off setup, NICE DCV (which keeps a console session live) is
  better than plain RDP, but adds setup — not included here.
- **Cost.** A `t3.large` Windows instance bills per hour while running. Stop or
  tear down when not demoing.
- **Security.** The security group is locked to the IP `deploy.ps1` detected. If
  your IP changes (or Mendix calls from elsewhere), re-run `deploy.ps1` or widen
  `-AllowedCidr`. Never open these ports to `0.0.0.0/0`.
- **Where does Mendix run?** If Mendix runs on your laptop, it reaches the
  instance over the internet via the PublicIp on 8081 (allowed by the SG). If you
  run Mendix on the instance too, `127.0.0.1` works but mind the 8081 port
  conflict noted in the parent README.
