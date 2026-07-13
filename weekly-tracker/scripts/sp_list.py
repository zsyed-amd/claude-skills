#!/usr/bin/env python3
"""Upsert a row in the Weekly Summary SharePoint list.

Usage:
    python3 sp_list.py --week "07/07/2026 - 07/11/2026" --person "Zohair Syed" --summary "..."
"""
import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_FILE = Path.home() / ".config" / "microsoft-graph" / "token.json"
SITE_ID = "amdcloud-my.sharepoint.com,fc60e54f-ec1b-469b-93c2-d79471b2a67c,cd704538-2cf6-49ae-a1a4-4343ec2e3b38"
LIST_ID = "977e2de1-9663-40ea-bbd8-d4fc80a63a11"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def get_token() -> str:
    data = json.loads(TOKEN_FILE.read_text())
    token = data.get("access_token", "")
    # Refresh if needed
    import time
    if data.get("expires_at", 0) - time.time() < 300 and data.get("refresh_token"):
        token = _refresh(data)
    return token


def _refresh(data: dict) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    payload = urllib.parse.urlencode({
        "client_id": data["client_id"],
        "grant_type": "refresh_token",
        "refresh_token": data["refresh_token"],
        "scope": data.get("scopes", "Files.ReadWrite.All Sites.ReadWrite.All Mail.Send offline_access"),
    }).encode()

    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{data['tenant_id']}/oauth2/v2.0/token",
        data=payload,
    )
    result = json.loads(opener.open(req, timeout=15).read())
    import time
    data["access_token"] = result["access_token"]
    data["expires_at"] = time.time() + result.get("expires_in", 3600)
    TOKEN_FILE.write_text(json.dumps(data, indent=2))
    return result["access_token"]


def make_opener(token: str):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))

    class TokenHandler(urllib.request.BaseHandler):
        def http_request(self, req):
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Content-Type", "application/json")
            return req
        https_request = http_request

    opener.add_handler(TokenHandler())
    return opener


def _request(token: str, url: str, method: str = "GET", data: bytes | None = None):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    return json.loads(opener.open(req, timeout=15).read())


def find_existing_row(token: str, week: str, person: str) -> str | None:
    """Return item ID if a row for this week+person exists, filtering in Python."""
    url = f"{GRAPH_BASE}/sites/{SITE_ID}/lists/{LIST_ID}/items?$expand=fields&$select=id,fields"
    try:
        result = _request(token, url)
        for item in result.get("value", []):
            fields = item.get("fields", {})
            if fields.get("Week") == week and fields.get("Name") == person:
                return item["id"]
        return None
    except Exception:
        return None


def upsert_row(week: str, person: str, summary: str) -> bool:
    token = get_token()
    fields = {"Title": f"{person} — {week}", "Week": week, "Name": person, "Summary": summary}
    existing_id = find_existing_row(token, week, person)

    try:
        if existing_id:
            _request(token,
                f"{GRAPH_BASE}/sites/{SITE_ID}/lists/{LIST_ID}/items/{existing_id}/fields",
                method="PATCH", data=json.dumps(fields).encode())
            print(f"Updated SP list row: {person} | {week}")
        else:
            _request(token,
                f"{GRAPH_BASE}/sites/{SITE_ID}/lists/{LIST_ID}/items",
                method="POST", data=json.dumps({"fields": fields}).encode())
            print(f"Created SP list row: {person} | {week}")
        return True
    except urllib.error.HTTPError as e:
        print(f"SP list error: {e.read().decode()}", file=sys.stderr)
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", required=True, help="e.g. '07/07/2026 - 07/11/2026'")
    parser.add_argument("--person", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()

    success = upsert_row(args.week, args.person, args.summary)
    sys.exit(0 if success else 1)
