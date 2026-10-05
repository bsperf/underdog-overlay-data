
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://rotogrinders.com/lineups/mlb"
OUTPUT = Path("mlb_batting_orders.json")

TEAMS = {
    "Arizona Diamondbacks": "AZ",
    "Arizona": "AZ",
    "Athletics": "ATH",
    "Oakland Athletics": "ATH",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "LA Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "LA Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "NY Mets": "NYM",
    "New York Yankees": "NYY",
    "NY Yankees": "NYY",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH"
}

ALIASES = {
    "ARI": "AZ", "ARZ": "AZ",
    "OAK": "ATH", "KCR": "KC",
    "SDP": "SD", "SFG": "SF",
    "TBR": "TB", "WAS": "WSH"
}

VALID = set(TEAMS.values())

def identify(text):
    text = str(text or "").strip()

    for name, code in sorted(
        TEAMS.items(),
        key=lambda item: -len(item[0])
    ):
        if re.search(
            r"(?<!\w)" + re.escape(name) + r"(?!\w)",
            text, re.I
        ):
            return code

    code = re.sub(r"[^A-Z]", "", text.upper())
    code = ALIASES.get(code, code)

    return code if code in VALID else None


def header_teams(game, lineups):
    # Look only before the lineup section,
    # avoiding player names and stats.
    candidates = []

    for child in game.children:
        if child is lineups:
            break

        if not getattr(child, "name", None):
            continue

        for el in [child] + list(child.descendants):
            if not getattr(el, "name", None):
                continue

            for attr in (
                "alt", "title", "data-team",
                "data-abbr", "data-team-abbr"
            ):
                value = el.get(attr)
                if isinstance(value, str):
                    candidates.append(value)

            # Only short text-bearing elements.
            if el.name in (
                "span", "a", "h2", "h3",
                "h4", "strong"
            ):
                value = el.get_text(" ", strip=True)
                if len(value) <= 45:
                    candidates.append(value)

    found = []

    for candidate in candidates:
        code = identify(candidate)
        if code and code not in found:
            found.append(code)

    return found


def parse_card(card):
    body = card.select_one(".lineup-card-body")

    if body is None:
        return None

    lineup = [None] * 9

    for player in body.select(".lineup-card-player"):
        name_el = player.select_one(
            ".player-nameplate-name"
        )
        number_el = player.select_one(
            ".player-nameplate > .small"
        )

        if not name_el or not number_el:
            continue

        number = number_el.get_text(strip=True)

        if not number.isdigit():
            continue

        index = int(number) - 1

        if 0 <= index < 9:
            lineup[index] = name_el.get_text(
                " ", strip=True
            )

    if any(name is None for name in lineup):
        return None

    unconfirmed = (
        "unconfirmed" in body.get("class", [])
        or body.select_one(
            ".lineup-card-unconfirmed"
        ) is not None
    )

    return {
        "confirmed": not unconfirmed,
        "lineup": lineup
    }


def parse(html):
    soup = BeautifulSoup(html, "html.parser")

    sections = soup.select(".game-card-lineups")
    results = {}

    print(
        "DIAGNOSTICS: game sections:",
        len(sections)
    )

    if not sections:
        raise ValueError("No game lineup sections")

    for index, section in enumerate(sections):
        cards = section.select(
            ":scope > .lineup-card"
        )

        game = section.parent

        if game is None:
            raise ValueError("Missing game container")

        teams = header_teams(game, section)

        print(
            "DIAGNOSTICS: game", index,
            "teams:", teams,
            "cards:", len(cards)
        )

        if len(teams) != 2 or len(cards) != 2:
            # Print header markup, not entire lineups.
            header = []
            for child in game.children:
                if child is section:
                    break
                if getattr(child, "name", None):
                    header.append(str(child))

            print(
                "DIAGNOSTICS: game header HTML:",
                "".join(header)[:6000]
            )

            raise ValueError(
                f"Cannot safely identify game {index}"
            )

        for team, card in zip(teams, cards):
            parsed = parse_card(card)

            if parsed is None:
                raise ValueError(
                    f"Incomplete lineup for {team}"
                )

            if team in results:
                raise ValueError(
                    f"Duplicate team: {team}"
                )

            results[team] = parsed

    if len(results) != len(sections) * 2:
        raise ValueError(
            "Team count does not match games"
        )

    return results


def main():
    response = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30
    )

    response.raise_for_status()

    results = parse(response.text)

    data = {
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "teams": results
    }

    OUTPUT.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

    print(
        "SUCCESS: saved",
        len(results),
        "team lineups"
    )
    print("Teams:", list(results))


if __name__ == "__main__":
    main()
