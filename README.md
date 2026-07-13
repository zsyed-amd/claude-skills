# AMD DCGPU TME — Claude Skills

Shared Claude Code skills for the AMD DCGPU TME team.

## Installation

```bash
git clone https://github.com/zsyed-amd/claude-skills ~/.claude/skills-repo
ln -s ~/.claude/skills-repo/weekly-tracker ~/.claude/skills/weekly-tracker
```

Then open Claude Code and run `/weekly-tracker` — the one-time setup will walk you through the rest.

## Skills

### `/weekly-tracker`

Automated weekly work tracker. Collects GitHub activity, Claude chat tasks, content created, and meeting transcripts every Friday at 6pm, then posts your summary to the shared Confluence page and SharePoint list. On Monday, Automation runs `/weekly-tracker send` to email the full team summary to manager.

**Prerequisites before first run:**

| Prereq | Command |
|--------|---------|
| `atlassian` CLI + `confluence` profile | `atlassian auth login --confluence-only --profile confluence` |
| Microsoft Graph token (SharePoint access) | See [Graph Auth Setup](#graph-auth-setup) below |
| `gh` CLI authed | `gh auth login` |
| Internal GitHub (optional) | `gh auth login --hostname github.amd.com` |

#### Graph Auth Setup

Run this once to get a token with SharePoint write access:

```bash
python3 - <<'EOF'
import json, ssl, sys, time, urllib.request, urllib.parse
from pathlib import Path

CLIENT_ID = "1fec8e78-bce4-4aaf-ab1b-5451cc387264"
TENANT_ID = "3dd8961f-e488-4e60-8e11-a82d994e183d"
SCOPES = "Sites.ReadWrite.All offline_access"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

# Device code request
payload = urllib.parse.urlencode({"client_id": CLIENT_ID, "scope": SCOPES}).encode()
req = urllib.request.Request(
    f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/devicecode",
    data=payload
)
dc = json.loads(opener.open(req, timeout=15).read())
print(dc["message"])

# Poll for token
poll_payload = urllib.parse.urlencode({
    "client_id": CLIENT_ID, "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    "device_code": dc["device_code"]
}).encode()
while True:
    time.sleep(dc.get("interval", 5))
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data=poll_payload
    )
    try:
        result = json.loads(opener.open(req, timeout=15).read())
        if "access_token" in result:
            out = {**result, "client_id": CLIENT_ID, "tenant_id": TENANT_ID,
                   "scopes": SCOPES, "expires_at": time.time() + result.get("expires_in", 3600)}
            p = Path.home() / ".config" / "microsoft-graph" / "token.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(out, indent=2))
            print(f"Token saved to {p}")
            break
    except Exception:
        pass
EOF
```
