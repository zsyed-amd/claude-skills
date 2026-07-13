#!/usr/bin/env python3
"""Scan GitHub for user activity in the past 7 days across all repos.

Usage:
    python3 github_activity.py --host github.com --username zsyed-amd
    python3 github_activity.py --host github.amd.com --username zsyed
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone


def get_activity(host: str, username: str, days: int = 7) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    commits, prs, merges = [], [], []

    # Set gh host env
    env_host = f"GH_HOST={host}" if host != "github.com" else ""

    def gh(*args):
        cmd = ["gh"] + list(args)
        if host != "github.com":
            import os
            env = {**__import__("os").environ, "GH_HOST": host}
        else:
            env = None
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            return []
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

    # Get user events
    events = gh("api", f"/users/{username}/events?per_page=100")
    if not events:
        # Try authenticated user endpoint
        events = gh("api", "/users/events?per_page=100")

    seen_repos = set()
    for event in events:
        created = event.get("created_at", "")
        if created < since:
            continue

        etype = event.get("type", "")
        repo = event.get("repo", {}).get("name", "unknown")
        payload = event.get("payload", {})

        if etype == "PushEvent":
            for commit in payload.get("commits", []):
                msg = commit.get("message", "").split("\n")[0]
                commits.append({"repo": repo, "message": msg, "date": created[:10]})

        elif etype == "PullRequestEvent":
            pr = payload.get("pull_request", {})
            action = payload.get("action", "")
            title = pr.get("title", "")
            merged = pr.get("merged", False)
            if merged or action == "closed" and pr.get("merged"):
                merges.append({"repo": repo, "title": title, "date": created[:10]})
            elif action == "opened":
                prs.append({"repo": repo, "title": title, "date": created[:10]})

        elif etype == "CreateEvent":
            ref_type = payload.get("ref_type", "")
            ref = payload.get("ref", "")
            if ref_type == "branch" and repo not in seen_repos:
                seen_repos.add(repo)

    return {"commits": commits, "prs": prs, "merges": merges, "host": host}


def format_summary(activity: dict) -> str:
    lines = []
    host = activity.get("host", "github.com")

    if activity["commits"]:
        lines.append(f"**Commits ({host}):**")
        seen = set()
        for c in activity["commits"]:
            key = f"{c['repo']}: {c['message']}"
            if key not in seen:
                seen.add(key)
                lines.append(f"  - [{c['date']}] {c['repo']}: {c['message']}")

    if activity["prs"]:
        lines.append(f"**PRs opened ({host}):**")
        for p in activity["prs"]:
            lines.append(f"  - [{p['date']}] {p['repo']}: {p['title']}")

    if activity["merges"]:
        lines.append(f"**Merged ({host}):**")
        for m in activity["merges"]:
            lines.append(f"  - [{m['date']}] {m['repo']}: {m['title']}")

    return "\n".join(lines) if lines else ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="github.com")
    parser.add_argument("--username", required=True)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    activity = get_activity(args.host, args.username, args.days)

    if args.json:
        print(json.dumps(activity, indent=2))
    else:
        summary = format_summary(activity)
        print(summary if summary else "No GitHub activity found.")
