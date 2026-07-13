Automated weekly work tracker for the AMD DCGPU TME team. Each team member runs
`/weekly-tracker` on their own machine — it collects GitHub commits/PRs/merges,
Claude chat session tasks, content created (decks, Confluence pages, SharePoint docs,
drop folder), and meeting transcripts (private). Every Friday it auto-posts each
person's summary to a shared Confluence page and a SharePoint list row. On Monday,
Zohair runs `/weekly-tracker send` to email the full team summary to Evan Groenke.
First run triggers a one-time setup questionnaire that saves a personal config and
registers the Friday cron automatically.
