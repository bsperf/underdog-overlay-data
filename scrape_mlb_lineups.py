
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://rotogrinders.com/lineups/mlb"
OUTPUT = Path("mlb_batting_orders.json")

TEAM_ALIASES = {
    "ARI": "AZ", "ARZ": "AZ",
    "OAK": "ATH", "KCR": "KC",
    "SDP": "SD", "SFG": "SF",
    "TBR": "TB", "WAS": "WSH"
}

VALID_TEAMS = {
    "AZ", "ATH", "ATL", "BAL", "BOS",
    "CHC", "CWS", "CIN", "CLE", "COL",
    "DET", "HOU", "KC", "LAA", "LAD",
    "MIA", "MIL", "MIN", "NYM", "NYY",
    "PHI", "PIT", "SD", "SF", "SEA",
    "STL", "TB", "TEX", "TOR", "WSH"
}

def normalize(value):
    code = re.sub(
        r"[^A-Z]", "", str(value).upper()
    )
    return TEAM_ALIASES.get(code, code)

def identify_team(card):
    # Inspect the card header and its attributes.
    candidates = []

    for el in [card] + list(
        card.select(
            '[class*="header"], [class*="team"], '
            '[data-team], [title], img[alt]'
        )
    ):
        for attr in (
            "data-team", "data-team-abbr",
            "title", "alt"
        ):
            if el.has_attr(attr):
                candidates.append(el.get(attr, ""))

        if el.name != "img":
            candidates.append(
                el.get_text(" ", strip=True)
            )

    for text in candidates:
        for token in re.findall(
            r"\b[A-Z]{2,3}\b", text.upper()
        ):
            team = normalize(token)
            if team in VALID_TEAMS:
                return team

    return None

def parse_lineups(html):
    soup = BeautifulSoup(
        html, "html.parser"
    )

    results = {}
    cards = soup.select(".lineup-card")

    print(
        "DIAGNOSTICS: lineup cards:",
        len(cards)
    )

    for card in cards:
        body = card.select_one(
            ".lineup-card-body"
        )

        if not body:
            continue

        team = identify_team(card)

        if not team:
            print(
                "DIAGNOSTICS: unidentified card:",
                card.get_text(
                    " ", strip=True
                )[:160]
            )
            continue

        lineup = [None] * 9

        for player in body.select(
            ".lineup-card-player"
        ):
            name_el = player.select_one(
                ".player-nameplate-name"
            )

            slot_el = player.select_one(
                ".player-nameplate > .small"
            )

            if not name_el or not slot_el:
                continue

            slot = slot_el.get_text(
                " ", strip=True
            )

            if not slot.isdigit():
                continue

            index = int(slot) - 1

            if 0 <= index < 9:
                lineup[index] = (
                    name_el.get_text(
                        " ", strip=True
                    )
                )

        # Do not publish partial lineups.
        if any(not name for name in lineup):
            continue

        unconfirmed = (
            "unconfirmed" in body.get(
                "class", []
            )
            or body.select_one(
                ".lineup-card-unconfirmed"
            ) is not None
        )

        if team in results:
            raise ValueError(
                f"Duplicate lineup for {team}"
            )

        results[team] = {
            "confirmed": not unconfirmed,
            "lineup": lineup
        }

    if not results:
        raise ValueError(
            "No complete team lineups parsed"
        )

    print(
        "DIAGNOSTICS: parsed teams:",
        list(results)
    )

    return results

def main():
    response = requests.get(
        URL,
        headers={
            "User-Agent":
                "Mozilla/5.0"
        },
        timeout=30
    )
    response.raise_for_status()

    teams = parse_lineups(
        response.text
    )

    data = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "teams": teams
    }

    OUTPUT.write_text(
        json.dumps(
            data,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"Saved {len(teams)} teams "
        f"to {OUTPUT}"
    )

if __name__ == "__main__":
    main()
