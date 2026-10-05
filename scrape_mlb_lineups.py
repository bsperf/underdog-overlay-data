
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

TEAM_NAMES = {
    "Arizona": "AZ",
    "Athletics": "ATH",
    "Atlanta": "ATL",
    "Baltimore": "BAL",
    "Boston": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati": "CIN",
    "Cleveland": "CLE",
    "Colorado": "COL",
    "Detroit": "DET",
    "Houston": "HOU",
    "Kansas City": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami": "MIA",
    "Milwaukee": "MIL",
    "Minnesota": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Philadelphia": "PHI",
    "Pittsburgh": "PIT",
    "San Diego": "SD",
    "San Francisco": "SF",
    "Seattle": "SEA",
    "St. Louis": "STL",
    "Tampa Bay": "TB",
    "Texas": "TEX",
    "Toronto": "TOR",
    "Washington": "WSH"
}


def normalize(value):
    code = re.sub(
        r"[^A-Z]", "",
        str(value).upper()
    )
    return TEAM_ALIASES.get(code, code)


def find_team_in_text(text):
    text = str(text or "")

    # Prefer explicit full names.
    for name, code in sorted(
        TEAM_NAMES.items(),
        key=lambda item: -len(item[0])
    ):
        if re.search(
            r"\b" + re.escape(name) + r"\b",
            text,
            re.I
        ):
            return code

    # Then try standalone abbreviations.
    for token in re.findall(
        r"\b[A-Z]{2,3}\b",
        text.upper()
    ):
        code = normalize(token)
        if code in VALID_TEAMS:
            return code

    return None


def identify_team(card):
    # Check explicit attributes and nearby
    # team/header elements first.
    elements = [card] + list(
        card.select(
            '[class*="header"], '
            '[class*="team"], '
            '[data-team], '
            '[title], img[alt]'
        )
    )

    for el in elements:
        for attr in (
            "data-team",
            "data-team-abbr",
            "data-abbr",
            "title",
            "alt"
        ):
            value = el.get(attr)

            if value:
                team = find_team_in_text(value)
                if team:
                    return team

    # Search nearby headings outside the card.
    parent = card.parent

    if parent:
        for el in parent.find_all(
            ["h2", "h3", "h4"],
            recursive=False
        ):
            team = find_team_in_text(
                el.get_text(" ", strip=True)
            )
            if team:
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

    for index, card in enumerate(cards):
        body = card.select_one(
            ".lineup-card-body"
        )

        if not body:
            continue

        team = identify_team(card)

        # Show the actual surrounding HTML
        # to locate reliable team identifiers.
        if index == 0:
            print(
                "DIAGNOSTICS: first card HTML:",
                str(card)[:3500]
            )
            print(
                "DIAGNOSTICS: first card parent HTML:",
                str(card.parent)[:5000]
            )

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

            index_number = int(slot) - 1

            if 0 <= index_number < 9:
                lineup[index_number] = (
                    name_el.get_text(
                        " ", strip=True
                    )
                )

        if not team:
            print(
                "DIAGNOSTICS: unidentified card:",
                index,
                "first player:",
                lineup[0]
            )
            continue

        if any(not name for name in lineup):
            print(
                "DIAGNOSTICS: incomplete lineup:",
                team,
                lineup
            )
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
                f"Duplicate team detected: {team}"
            )

        results[team] = {
            "confirmed": not unconfirmed,
            "lineup": lineup
        }

    print(
        "DIAGNOSTICS: parsed teams:",
        list(results)
    )

    if not results:
        raise ValueError(
            "No complete team lineups parsed"
        )

    return results


def main():
    response = requests.get(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0"
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
