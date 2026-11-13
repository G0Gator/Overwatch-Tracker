# Overwatch Team Weekly Tracker

This project polls the OverFast API for your team members and writes a weekly snapshot into a Google Sheet.

It is designed to run as a Jenkins job every Monday or on any schedule you choose.

## What it tracks

For each player and week, the job records:

- snapshot date
- player id / username
- platform
- gamemode
- games played
- games won
- games lost
- win rate
- KDA
- total minutes/hours played
- last updated timestamp from OverFast

This is the cleanest way to answer: are they actually putting in games, and is their win rate trending up or down?

Important: OverFast exposes player summaries and historical stat snapshots, but not a direct "current win streak" field. That means this tracker records weekly snapshots and trends rather than a precise ongoing streak number. If you need exact live streak tracking, you would need a different data source or match-history API.

## Setup

### 1. Create a Google service account

1. Go to Google Cloud Console.
2. Create a project.
3. Enable Google Sheets API.
4. Create a service account.
5. Download the JSON key file.
6. Share the target spreadsheet with the service account email address as an Editor.

### 2. Prepare your players

Use the OverFast player ids, for example:

- `TeKrop-2217`
- `SomePlayer-1234`

The API accepts BattleTag names with `#` replaced by `-`.

### 3. Create a secret file for Jenkins

In Jenkins, add a secret file credential named something like `overwatch-gsheets-creds` and upload the service-account JSON.

### 4. Jenkins environment variables

Set these in the pipeline or Jenkins job configuration:

- `PLAYER_IDS` = comma-separated list of OverFast player ids
- `PLATFORM` = `pc` or `console`
- `GAMEMODE` = `competitive` or `quickplay`
- `SPREADSHEET_ID` = Google Sheet id from the URL
- `SHEET_NAME` = worksheet name such as `Weekly_Stats`
- `OVERFAST_API_BASE_URL` = defaults to `https://overfast-api.tekrop.fr`

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python scripts/overwatch_weekly_tracker.py \
  --players "TeKrop-2217,AnotherPlayer-1234" \
  --platform pc \
  --gamemode competitive \
  --spreadsheet-id "YOUR_SHEET_ID" \
  --sheet-name "Weekly_Stats" \
  --service-account-file "./secrets/google-service-account.json"
```

## Jenkins

The included `Jenkinsfile` runs weekly on Monday at 08:00 UTC and writes each snapshot to the spreadsheet.

You can also trigger it manually from Jenkins.

## Files

- `scripts/overwatch_weekly_tracker.py` — fetches stats and writes rows
- `Jenkinsfile` — weekly Jenkins pipeline
- `requirements.txt` — Python dependencies

## Notes

- OverFast is rate limited, so keep the job sparse and avoid running it too frequently.
- One run per week is reasonable.
- If a row already exists for the same date and player, the script updates it instead of creating a duplicate.
