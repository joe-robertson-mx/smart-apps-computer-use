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
