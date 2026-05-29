# Computer-Use Prompt Lab

Iterate on the system/user prompts for the BOAT 2026 computer-use demo, score the
agent against the two legacy apps, and export the winners for Mendix.

## How it works
This package plays the role Mendix plays: it runs the Bedrock agent loop and sends every
tool action over the existing `POST /computer_tool` contract to `windows_server.py`. See
the design spec: `docs/superpowers/specs/2026-05-29-computer-use-prompt-lab-design.md`.

## Prerequisites
- AWS creds for Bedrock (`aws sso login`, profile `default`, region `eu-west-1`).
- The demo host running `start_demo_env.bat` (windows_server.py on :8081 + the two apps).
- Network: laptop must reach `host:8081` (`/computer_tool` + `/control/*`).
- `pip install -r prompt_lab/requirements.txt`

## Run
```bash
python -m prompt_lab.runner --host http://<HOST_IP>:8081 \
  --models sonnet-4-5,opus-4-7 --repeats 2
```
Reports land in `prompt_lab/reports/`.

## Authoring
- Prompt variants: `prompt_lab/prompts/*.md` (`## system` / `## user` sections).
- Scenarios: `prompt_lab/scenarios/*.yaml` (case data + expected_record + mode).
- Export a winner for Mendix: use `prompt_lab.mendix_export.export_variant`.

## Tests
```bash
python -m pytest
```
