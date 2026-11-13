#!/usr/bin/env python3
import argparse
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import gspread
import requests
from google.oauth2 import service_account


DEFAULT_API_BASE_URL = "https://overfast-api.tekrop.fr"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch OverFast weekly team stats and write to Google Sheets.")
    parser.add_argument("--players", required=True, help="Comma-separated list of player ids, such as TeKrop-2217,AnotherPlayer-1234")
    parser.add_argument("--platform", default="pc", choices=["pc", "console"], help="Platform filter")
    parser.add_argument("--gamemode", default="competitive", choices=["competitive", "quickplay"], help="Gamemode filter")
    parser.add_argument("--spreadsheet-id", required=True, help="Google Sheet ID")
    parser.add_argument("--sheet-name", default="Weekly_Stats", help="Worksheet name in the spreadsheet")
    parser.add_argument("--service-account-file", help="Path to the GCP service account JSON file")
    parser.add_argument("--api-base-url", default=os.getenv("OVERFAST_API_BASE_URL", DEFAULT_API_BASE_URL), help="OverFast API base URL")
    parser.add_argument("--snapshot-date", help="Optional date override in YYYY-MM-DD format")
    return parser.parse_args()


def get_player_ids(raw_players: str) -> List[str]:
    return [p.strip() for p in raw_players.split(",") if p and p.strip()]


def fetch_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def safe_get(mapping: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def normalize_rank_label(rank_data: Dict[str, Any]) -> str:
    if not isinstance(rank_data, dict):
        return "unknown"
    division = rank_data.get("division") or rank_data.get("tier")
    rank = rank_data.get("rank") or rank_data.get("level")
    if division and rank:
        return f"{division} {rank}"
    if division:
        return str(division)
    if rank:
        return str(rank)
    return "unknown"


def get_row_for_player(summary: Dict[str, Any], platform: str, gamemode: str) -> Dict[str, Any]:
    general = safe_get(summary, "general", default={})
    return {
        "games_played": general.get("games_played"),
        "games_won": general.get("games_won"),
        "games_lost": general.get("games_lost"),
        "winrate": general.get("winrate"),
        "kda": general.get("kda"),
        "time_played": general.get("time_played"),
        "platform": platform,
        "gamemode": gamemode,
    }


def get_google_sheet(service_account_file: str, spreadsheet_id: str, sheet_name: str):
    creds = service_account.Credentials.from_service_account_file(
        service_account_file,
        scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"],
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
    return worksheet


def ensure_headers(worksheet):
    headers = [
        "snapshot_date",
        "player_id",
        "username",
        "platform",
        "gamemode",
        "games_played",
        "games_won",
        "games_lost",
        "winrate",
        "kda",
        "time_played_seconds",
        "competitive_rank",
        "last_updated_at",
    ]
    existing = worksheet.row_values(1)
    if not existing:
        worksheet.append_row(headers)


def row_exists(worksheet, snapshot_date: str, player_id: str, platform: str, gamemode: str) -> Optional[int]:
    rows = worksheet.get_all_values()
    if len(rows) < 2:
        return None
    for index, row in enumerate(rows[1:], start=2):
        if len(row) < 13:
            continue
        if row[0] == snapshot_date and row[1] == player_id and row[3] == platform and row[4] == gamemode:
            return index
    return None


def build_row(snapshot_date: str, player_id: str, username: str, values: Dict[str, Any]) -> List[Any]:
    return [
        snapshot_date,
        player_id,
        username,
        values["platform"],
        values["gamemode"],
        values.get("games_played"),
        values.get("games_won"),
        values.get("games_lost"),
        values.get("winrate"),
        values.get("kda"),
        values.get("time_played"),
        values.get("competitive_rank"),
        values.get("last_updated"),
    ]


def format_snapshot_date(value: Optional[str]) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_player_data(player_id: str, platform: str, gamemode: str, api_base_url: str) -> Optional[Dict[str, Any]]:
    summary_url = f"{api_base_url.rstrip('/')}/players/{player_id}/summary"
    stats_url = f"{api_base_url.rstrip('/')}/players/{player_id}/stats/summary"
    try:
        summary_payload = fetch_json(summary_url)
        stats_payload = fetch_json(stats_url, params={"platform": platform, "gamemode": gamemode})
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            print(f"Skipping {player_id}: OverFast returned 404 (player not found or BattleTag is wrong).")
            return None
        raise

    username = summary_payload.get("username") or player_id
    rank_data = safe_get(summary_payload, "competitive", platform, default={})
    rank_label = normalize_rank_label(rank_data)

    row_values = get_row_for_player(stats_payload, platform, gamemode)
    row_values["competitive_rank"] = rank_label
    row_values["last_updated"] = summary_payload.get("last_updated_at")
    return {"player_id": player_id, "username": username, **row_values}


def main() -> None:
    args = parse_args()
    player_ids = get_player_ids(args.players)
    if not player_ids:
        raise ValueError("No player ids were provided. Use --players with a comma-separated list.")

    service_account_file = args.service_account_file or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not service_account_file:
        raise ValueError("Set --service-account-file or GOOGLE_SERVICE_ACCOUNT_FILE to point to the Google service account JSON file.")

    worksheet = get_google_sheet(service_account_file, args.spreadsheet_id, args.sheet_name)
    ensure_headers(worksheet)

    snapshot_date = format_snapshot_date(args.snapshot_date)

    for player_id in player_ids:
        print(f"Fetching {player_id} ...")
        data = fetch_player_data(player_id, args.platform, args.gamemode, args.api_base_url)
        if data is None:
            continue
        row = build_row(snapshot_date, data["player_id"], data["username"], data)
        existing_row_number = row_exists(worksheet, snapshot_date, data["player_id"], args.platform, args.gamemode)
        if existing_row_number:
            worksheet.update(f"A{existing_row_number}:M{existing_row_number}", [row])
            print(f"Updated row for {data['player_id']} on {snapshot_date}")
        else:
            worksheet.append_row(row)
            print(f"Appended row for {data['player_id']} on {snapshot_date}")

    print("Done.")


if __name__ == "__main__":
    main()
