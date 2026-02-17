# sports_fetcher.py
# Responsibility: fetch and clean recent match data from TheSportsDB API.
# This module knows nothing about AI or HTML — it only knows about sports data.

import requests  # third-party library for making HTTP requests
import json

# --- Team Configuration ---
# These are TheSportsDB's permanent numeric IDs for our two target teams.
# If you wanted to add a new team, you'd look up their ID on thesportsdb.com
# and add a new entry here. This is a simple form of configuration management.
TEAM_CONFIG = {
    "manutd": {
        "id": "133612",
        "name": "Manchester United",
        "api_name": "Manchester United",
        "sport": "football",
        "league": "Premier League"
    },
    "lakers": {
        "id": "134867",
        "name": "Los Angeles Lakers",
        "api_name": "Los Angeles Lakers",
        "sport": "basketball",
        "league": "NBA"
    }
}

# The base URL for TheSportsDB's free API tier.
# v1/json/123/ is their free endpoint — "123" is the free API key they provide
# publicly. A paid key would replace this with your personal key.
BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"


def fetch_last_match(team_key: str) -> dict:
    """
    Fetches and returns cleaned data for a team's most recent match.

    Args:
        team_key: Either "manutd" or "lakers" (matches keys in TEAM_CONFIG)

    Returns:
        A dictionary containing only the fields we need for Story generation.

    Raises:
        ValueError: If team_key isn't recognised.
        ConnectionError: If the API call fails.
    """

    # Step 1: Validate the input early.
    # "Fail fast" is a good engineering principle — catch bad input at the
    # boundary of your function, not deep inside it where it's harder to debug.
    if team_key not in TEAM_CONFIG:
        raise ValueError(
            f"Unknown team '{team_key}'. Choose from: {list(TEAM_CONFIG.keys())}"
        )

    team = TEAM_CONFIG[team_key]

    # Step 2: Build the API URL.
    # f-strings let us inject variables into strings cleanly.
    # This produces something like:
    # "https://www.thesportsdb.com/api/v1/json/3/eventslast.php?id=66"
    url = f"{BASE_URL}/eventslast.php?id={team['id']}"

    print(f"📡 Fetching last match for {team['name']}...")

    # Step 3: Make the HTTP GET request.
    # requests.get() sends a GET request to the URL and waits for a response.
    # timeout=10 means: if the server doesn't respond within 10 seconds,
    # stop waiting and raise an error. Without this, your script could hang
    # forever if the API is down.
    try:
        response = requests.get(url, timeout=10)

        # raise_for_status() checks the HTTP status code.
        # A 200 code means success. 404 means not found. 500 means server error.
        # This line will raise an exception for any non-200 response,
        # so we don't silently process empty or error data.
        response.raise_for_status()

    except requests.exceptions.Timeout:
        raise ConnectionError(f"Request to TheSportsDB timed out after 10 seconds.")
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Failed to fetch data from TheSportsDB: {e}")

    # Step 4: Parse the JSON response.
    # response.content gives us the raw bytes from the server.
# Decoding with 'utf-8-sig' strips the BOM character if present,
# then falls back to normal UTF-8 if there's no BOM — so this is
# safe regardless of what the server sends.
    data = json.loads(response.content.decode("utf-8-sig"))

    # Step 5: Validate the response structure.
    # APIs can return empty results (e.g. if a team has no recent matches logged).
    # We check before trying to access data, which would throw a KeyError.
    if not data.get("results"):
        raise ValueError(
            f"No recent match data found for {team['name']}. "
            "TheSportsDB may not have updated results yet."
        )

    # Step 6: Extract only the most recent match.
    # results[0] is the most recent event in the list.
    # We store the raw dict in a variable so we can reference it cleanly below.
    raw_match = data["results"][0]

    # Step 7: Clean and reshape the data.
    # This is a critical step called "data normalisation."
    # The raw API response has ~40 fields, many of which are null or irrelevant.
    # We extract only what our prompt builder needs, rename fields to be
    # self-explanatory, and handle inconsistent types (like scores as strings).
    # The result is a clean contract between this module and the next one.
    cleaned = _extract_match_data(raw_match, team)

    print(f"✅ Match data fetched: {cleaned['event_name']} ({cleaned['date']})")
    return cleaned


def _extract_match_data(raw: dict, team: dict) -> dict:
    """
    Extracts and normalises fields from a raw TheSportsDB event object.

    The underscore prefix on _extract_match_data is a Python convention meaning
    "this is a private helper function — it's for internal use within this
    module only, not intended to be called from outside."

    Args:
        raw: The raw event dictionary from TheSportsDB
        team: The team config dictionary from TEAM_CONFIG

    Returns:
        A clean, normalised dictionary with only the fields we need.
    """

    # Safe integer conversion helper.
    # The API sometimes returns "2", sometimes 2, sometimes None.
    # This function handles all three cases consistently.
    def safe_int(value):
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0

    # Determine if our team was playing at home or away.
    # This affects how we frame the narrative ("at Old Trafford" vs "on the road").
    home_team = raw.get("strHomeTeam", "")
    away_team = raw.get("strAwayTeam", "")
    is_home = team["api_name"].lower() == home_team.lower()

    home_score = safe_int(raw.get("intHomeScore"))
    away_score = safe_int(raw.get("intAwayScore"))

    # Determine the result from our team's perspective.
    if is_home:
        our_score = home_score
        opp_score = away_score
        opponent = away_team
    else:
        our_score = away_score
        opp_score = home_score
        opponent = home_team

    if our_score > opp_score:
        result = "WIN"
    elif our_score < opp_score:
        result = "LOSS"
    else:
        result = "DRAW"

    # Build the clean dictionary.
    # Every key here is something the prompt builder will reference by name.
    # Think of this as the "API contract" between your two modules.
    return {
        "team_name": team["name"],
        "sport": team["sport"],
        "league": team["league"],
        "event_name": raw.get("strEvent", "Unknown Match"),
        "date": raw.get("dateEvent", "Unknown Date"),
        "venue": raw.get("strVenue", "Unknown Venue"),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score,
        "away_score": away_score,
        "our_score": our_score,
        "opp_score": opp_score,
        "opponent": opponent,
        "result": result,
        "is_home": is_home,
        # Goal details are football-specific. For basketball these will be None.
        # The prompt builder will handle this gracefully.
        "goal_details_home": raw.get("strHomeGoalDetails") or None,
        "goal_details_away": raw.get("strAwayGoalDetails") or None,
        "status": raw.get("strStatus", "Unknown"),
    }


# This block only runs when executing: python sports_fetcher.py
# It does NOT run when sports_fetcher is imported by main.py.
# This lets every module be both a reusable library AND a standalone test script.
if __name__ == "__main__":
    import json  # standard library for pretty-printing JSON

    for team_key in ["manutd", "lakers"]:
        print(f"\n{'='*50}")
        match = fetch_last_match(team_key)
        # json.dumps with indent=2 pretty-prints the dictionary so it's
        # readable in the terminal rather than one long line.
        print(json.dumps(match, indent=2))