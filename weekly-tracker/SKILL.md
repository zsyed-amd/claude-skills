---
name: weekly-tracker
description: >
  Automated weekly work tracker for AMD DCGPU TME team. Collects GitHub activity,
  Claude chat tasks, content created, and meeting transcripts, then posts a personal
  summary to a shared Confluence page and SharePoint list every Friday. Monday send
  command emails the full team summary to the manager.
version: "1.0.0"
metadata:
  author: zsyed@amd.com
  category: productivity
  tags: [weekly, tracker, github, confluence, sharepoint, email]
inputs:
  - name: command
    type: string
    required: false
    description: "'send' to email manager summary, 'setup' to re-run onboarding. Empty = weekly collection."
security:
  data_access: [local-readonly, local-readwrite]
  network_access: true
  network_hosts: [github.com, github.amd.com, graph.microsoft.com, api.atlassian.com]
  permissions: [file_read, file_write, bash]
  sandboxed: false
compatibility:
  universal: true
---

# Weekly Tracker Skill

## Skill directory
SKILL_DIR is the directory containing this file. All scripts live at `$SKILL_DIR/scripts/`.

---

## Step 1 — Parse arguments

Read `$ARGUMENTS` (the text after `/weekly-tracker`):
- Empty or no args → **COLLECTION MODE** (standard weekly run)
- `send` → **SEND MODE** (compile and email manager summary)
- `setup` → **SETUP MODE** (re-run onboarding, overwrite config)

---

## Step 2 — Load or create config

Config file: `~/.claude/weekly-tracker.json`

If the file does NOT exist (or arg is `setup`) → run **ONBOARDING FLOW** below.
If the file exists and arg is empty → skip to **COLLECTION MODE**.
If the file exists and arg is `send` → skip to **SEND MODE**.

---

## ONBOARDING FLOW (first run or /weekly-tracker setup)

Tell the user: "Welcome to weekly-tracker! I'll ask you 5 quick questions to set up your personal profile. This only runs once."

Ask these questions one at a time and wait for answers:

**Q1: Full name?**
Store as `name`.

**Q2: Do you use GitHub for your work?**
- If YES → ask: "What is your AMD internal GitHub username on github.amd.com?" (required)
  - Then ask: "Do you also have a public GitHub account on github.com? If so, what's your username? (optional, press enter to skip)"
- If NO → skip GitHub tracking entirely.

**Q3: Where do meeting transcripts land on your machine?**
Options: folder path (e.g. ~/Downloads/transcripts), "I paste them into Claude", or "skip"
Store as `transcript_folder` (path or "claude_sessions" or null).

**Q4: Describe the non-GitHub work you produce this week — decks, blogs, whitepapers, Confluence pages, SharePoint docs, event collateral, etc.**
Free-text answer. Based on response, propose a personalized content tracking plan:

- Mentions PowerPoint/decks/PPTX → add: `{"type": "folder_scan", "path": "~/Downloads", "extensions": [".pptx", ".pdf"]}`
- Mentions Confluence pages → add: `{"type": "confluence_api"}`
- Mentions SharePoint/SP docs → add: `{"type": "sharepoint_api"}`
- Mentions a specific folder → ask for the path, add: `{"type": "folder_scan", "path": "<their path>", "extensions": ["*"]}`
- Always add: `{"type": "drop_folder", "path": "~/weekly-work/"}` (default catch-all)
- Always add: `{"type": "claude_sessions"}` (always scan Claude chat history)

Show the proposed tracking plan and ask: "Does this tracking plan look right? (yes / tweak / skip extra tracking)"
If they want to tweak, adjust accordingly.

**Q5: Auto-confirmed (baked in defaults):**
- Confluence space ID: `1670049694`
- Confluence folder ID: `1793961891`
- SP Site ID: `amdcloud-my.sharepoint.com,fc60e54f-ec1b-469b-93c2-d79471b2a67c,cd704538-2cf6-49ae-a1a4-4343ec2e3b38`
- SP List ID: `977e2de1-9663-40ea-bbd8-d4fc80a63a11`
- Manager email: `evan.groenke@amd.com`
- ATLASSIAN_PROFILE: `confluence`

Tell the user these are pre-filled for the team.

**Save config** to `~/.claude/weekly-tracker.json`:
```json
{
  "name": "<Q1>",
  "github": {
    "amd": {"username": "<amd_username>", "host": "github.amd.com"},
    "public": {"username": "<public_username_or_null>", "host": "github.com"}
  },
  "transcript_folder": "<Q3_value>",
  "content_sources": [<proposed_sources>],
  "confluence_space_id": "1670049694",
  "confluence_folder_id": "1793961891",
  "sp_site_id": "amdcloud-my.sharepoint.com,fc60e54f-ec1b-469b-93c2-d79471b2a67c,cd704538-2cf6-49ae-a1a4-4343ec2e3b38",
  "sp_list_id": "977e2de1-9663-40ea-bbd8-d4fc80a63a11",
  "manager_email": "evan.groenke@amd.com",
  "atlassian_profile": "confluence"
}
```

**Create drop folder:** Run `mkdir -p ~/weekly-work/`

**Register Friday cron** using CronCreate:
- cron: `0 18 * * 5`
- recurring: true
- durable: true
- prompt: `Run /weekly-tracker to collect and post this week's work summary.`

Tell the user: "Setup complete! The skill will auto-run every Friday at 6pm. You can also run `/weekly-tracker` anytime for a manual update."

---

## COLLECTION MODE (standard weekly run)

This runs automatically every Friday via cron, or manually anytime.

### 1. Calculate date range
- Check today's day of week.
- **If today is Monday**: use LAST week's range — week start = 7 days ago Monday, week end = last Friday.
- **Otherwise**: use the current week — week start = most recent Monday, week end = this coming Friday.
- Week label for Confluence: e.g. `Week of Jul 6–10, 2026` (use actual Mon–Fri dates, not Mon–11)
- Week label for SP list: e.g. `07/06/2026 - 07/10/2026` (MM/DD/YYYY - MM/DD/YYYY, always Mon to Fri)
- `since_date` = the Monday of the target week in ISO format (not always 7 days ago)

### 2. Collect GitHub activity (if github configured)
For each configured GitHub host, run:
```bash
python3 $SKILL_DIR/scripts/github_activity.py \
  --host <host> --username <username> --days 7
```
Capture output as `github_summary`.

Also check: does `gh` CLI have auth for this host? Run `gh auth status --hostname <host>`.
If not authenticated, note it in the output and skip that host gracefully.

### 3. Collect Claude chat session summaries
Scan `~/.claude/projects/` for all `.jsonl` files modified in the past 7 days (excluding subagent files).
For each file, extract user messages (type=user, content is text, not system-reminder or task-notification).
Identify: what tasks were worked on, what was completed, any blockers or next-week items mentioned.
Compile as `chat_summary` (tasks, blockers, next_week sections).

### 4. Collect meeting transcripts (PRIVATE — never post)
Only if `transcript_folder` is configured:
- If it's a folder path → scan for `.docx`, `.txt`, `.pdf` files modified in past 7 days. Read/summarize each.
- If it's `claude_sessions` → look for transcript-like content in session JSONL files (long user messages that look like meeting transcripts with names and timestamps).
Compile as `meeting_summary` — this stays in Claude chat ONLY, never posted anywhere.

### 5. Collect content from configured sources
For each source in `content_sources`:

- **drop_folder**: Run `find ~/weekly-work/ -newer <7_days_ago> -type f 2>/dev/null`. List filenames.
- **folder_scan**: Run `find <path> -newer <7_days_ago> -name "*.pptx" -o -name "*.pdf" ... 2>/dev/null`. List filenames.
- **confluence_api**: Run:
  ```bash
  export ATLASSIAN_PROFILE=confluence
  atlassian confluence search \
    --cql "creator = currentUser() AND created >= \"<since_date_cql>\" AND type = page" \
    --json
  ```
  Extract page titles and dates.
- **claude_sessions**: Already covered in step 3.

Compile as `content_summary`.

### 6. Self-report prompt
Ask the user: **"Anything else you shipped or worked on this week that wasn't captured above? (one line, or press enter to skip)"**

Add their response to `content_summary` if not empty.

### 7. Generate private meeting summary
If `meeting_summary` has content, show it in the Claude chat now:
```
──────────────────────────────────────
MEETING SUMMARY (private — not posted)
──────────────────────────────────────
<meeting_summary content>
──────────────────────────────────────
```

### 8. Generate work summary (to be posted)
Compile into this structure:

```
## <name>

### GitHub
<github_summary or "No GitHub activity this week.">

### Tasks Completed
<chat_summary.tasks or "No Claude chat sessions found.">

### Content Created
<content_summary or "None captured.">

### Blockers / Open Items
<chat_summary.blockers or "None.">

### Next Week
<chat_summary.next_week or "TBD.">
```

### 9. Post to Confluence
Find or create this week's page under the team folder.

**Check if page exists:**
```bash
export ATLASSIAN_PROFILE=confluence
atlassian confluence search \
  --cql "parent = 1793961891 AND title = \"<week_label>\"" \
  --json
```

**If page doesn't exist — create it:**
```bash
atlassian --profile confluence confluence page create \
  --space "~7120203ddb5b24b4804d7eb14ba090431d0ef2" \
  --title "<week_label>" \
  --parent-id 1793961891 \
  --body "<h1><week_label></h1>"
```
Capture the new page ID.

**Upsert user section on the page:**
- Get current page body: `atlassian --profile confluence confluence page get <page_id> --body-format storage`
- If user's section already exists (search for `<h2><name></h2>`) → replace it
- If not → append the new section
- Update the page: `atlassian --profile confluence confluence page update <page_id> --body "<updated_body>"`

Use XHTML storage format. Wrap each section in `<h2>`, `<h3>`, `<p>`, `<ul>`/`<li>` tags appropriately.

### 10. Update SharePoint list
```bash
python3 $SKILL_DIR/scripts/sp_list.py \
  --week "<sp_week_label>" \
  --person "<name>" \
  --summary "<3-sentence plain text summary of the week>"
```

The 3-sentence summary should cover: (1) main GitHub/code work, (2) key tasks or content created, (3) blockers or next week focus.

### 11. Re-register cron (auto-renew)
Call CronCreate again with the same settings to reset the 7-day expiry:
- cron: `0 18 * * 5`, recurring: true, durable: true
- prompt: `Run /weekly-tracker to collect and post this week's work summary.`

### 12. Confirm to user
Show a brief confirmation:
```
✓ Confluence page updated: <week_label>
✓ SharePoint list updated
✓ Cron renewed for next Friday
<meeting_summary shown above if applicable>
```

---

## SEND MODE (/weekly-tracker send)

Only Zohair should run this. Run on Monday morning to email last week's summary to Evan.

### 1. Calculate last week's date range
- Last Monday to last Friday
- Confluence page title: e.g. `Week of Jul 7–11, 2026`
- Subject: `Team Weekly Summary — Jul 7–11`

### 2. Find last week's Confluence page
```bash
export ATLASSIAN_PROFILE=confluence
atlassian confluence search \
  --cql "parent = 1793961891 AND title = \"<last_week_label>\"" \
  --json
```
Get the page ID. If not found → tell user "No page found for last week. Has the team run /weekly-tracker yet?"

### 3. Read the page
```bash
atlassian --profile confluence confluence page get <page_id> --body-format storage
```
Parse out each team member's section (each `<h2>` block = one person).

### 4. Compile email body
Format as markdown then convert to HTML using the send_email.py script:

```
Hi Evan,

Here's what the team shipped last week (Jul 7–11):

──────────────────────────────
ZOHAIR SYED
• GitHub: <1-line github summary>
• Tasks: <1-line tasks summary>
• Content: <1-line content summary>
• Next week: <next week item>

[TEAM MEMBER 2]
• ...
──────────────────────────────

Full details → https://amd.atlassian.net/wiki/spaces/~7120203ddb5b24b4804d7eb14ba090431d0ef2/pages/<page_id>
```

Keep each person's section to 4 bullet points max — this email should be scannable in 60 seconds.

### 5. Send email
```bash
python3 $SKILL_DIR/scripts/send_email.py \
  --to evan.groenke@amd.com \
  --subject "Team Weekly Summary — <date_range>" \
  --body "<compiled_email_markdown>"
```

### 6. Confirm
Tell the user: "Email sent to evan.groenke@amd.com. Subject: Team Weekly Summary — <date_range>"
