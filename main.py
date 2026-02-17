# main.py
# Responsibility: entry point and orchestrator for the Sports Stories Generator.
# This module coordinates all other modules but contains no business logic itself.
# If a module is a specialist, main.py is the project manager.

import os
import sys
import webbrowser  # standard library — opens URLs/files in the default browser

# Import our five pipeline modules.
# Each import gives us access to that module's public functions.
from sports_fetcher import fetch_last_match
from prompt_builder import build_prompt
from claude_client import generate_story
from story_parser import parse_and_save
from html_renderer import render_html


# --- Team menu configuration ---
# This dictionary drives both the display menu and the routing logic.
# Adding a new team means adding one entry here — nothing else changes.
TEAMS = {
    "1": {
        "key": "manutd",
        "display": "Manchester United",
        "sport": "⚽ Football (Premier League)",
    },
    "2": {
        "key": "lakers",
        "display": "LA Lakers",
        "sport": "🏀 Basketball (NBA)",
    },
    "3": {
        "key": "both",
        "display": "Both teams",
        "sport": "Run full pipeline for both",
    }
}


def print_banner():
    """Prints a welcome banner when the tool starts."""
    print("\n" + "="*55)
    print("  🏆  SPORTS STORIES GENERATOR")
    print("  Powered by TheSportsDB + Claude AI")
    print("="*55)


def print_menu():
    """Prints the team selection menu."""
    print("\nSelect a team to generate a Story for:\n")
    for number, team in TEAMS.items():
        print(f"  [{number}]  {team['display']}")
        print(f"       {team['sport']}\n")


def get_user_choice() -> str:
    """
    Prompts the user for input and validates it.

    Loops until the user enters a valid choice — rather than crashing
    on bad input, we explain what's valid and ask again.
    This is called a 'validation loop' and it's the correct pattern
    for any CLI input handling.

    Returns:
        A valid key string from TEAMS ("1", "2", or "3").
    """
    valid_choices = list(TEAMS.keys())

    while True:
        # input() pauses the program and waits for the user to type something.
        # The string argument is the prompt shown to them.
        choice = input(f"Enter your choice ({'/'.join(valid_choices)}): ").strip()

        if choice in valid_choices:
            return choice

        # Invalid input — tell them exactly what's wrong and loop again.
        print(f"  ❌ '{choice}' isn't a valid option. "
              f"Please enter {', '.join(valid_choices[:-1])} or {valid_choices[-1]}.\n")


def run_pipeline(team_key: str) -> dict:
    """
    Runs the full Story generation pipeline for a single team.

    This function calls each module in sequence, passing the output
    of each stage as the input to the next. If any stage fails,
    the exception propagates up to main() where it's caught and
    displayed cleanly.

    Args:
        team_key: "manutd" or "lakers"

    Returns:
        A dictionary with the paths of the generated files:
        { "json_path": "...", "html_path": "..." }
    """

    team_display = next(
        t["display"] for t in TEAMS.values() if t["key"] == team_key
    )

    print(f"\n{'─'*55}")
    print(f"  Generating Story for: {team_display}")
    print(f"{'─'*55}")

    # Stage 1: Fetch match data
    # If the API is down or returns no data, fetch_last_match raises
    # a ConnectionError or ValueError — both caught in main().
    match = fetch_last_match(team_key)

    # Stage 2: Build the prompt
    # Pure Python transformation — shouldn't fail unless match dict
    # is malformed, which story_parser would have caught already.
    prompt = build_prompt(match)

    # Stage 3: Call Claude
    # May raise anthropic.APIError for network/auth issues.
    raw_response = generate_story(prompt)

    # Stage 4: Parse and save JSON
    # Validates the response and writes output/{team}_story_{timestamp}.json
    story = parse_and_save(raw_response, team_key)

    # Stage 5: Render HTML
    # Reads the story dict and writes output/{team}_story_{timestamp}.html
    # We pass story["result"] explicitly so the headline badge renders correctly.
    # (We noted this edge case at the end of Stage 6.)
    html_path = render_html(story, team_key)

    # Build a result summary to return to main()
    return {
        "team": team_display,
        "match": story["match"],
        "result": story["result"],
        "html_path": html_path,
    }


def print_summary(results: list):
    """
    Prints a clean summary of everything generated once the pipeline finishes.

    Args:
        results: List of result dicts returned by run_pipeline()
    """
    print(f"\n{'='*55}")
    print("  ✅  GENERATION COMPLETE")
    print(f"{'='*55}\n")

    for r in results:
        print(f"  🏆  {r['team']}")
        print(f"      Match:  {r['match']}")
        print(f"      Result: {r['result']}")
        print(f"      HTML:   {r['html_path']}\n")

    print("  Open the HTML files above in any browser to preview")
    print("  your Story cards.\n")
    print(f"{'='*55}\n")


def main():
    """
    Main entry point. Orchestrates the full user interaction and pipeline run.
    """

    print_banner()
    print_menu()

    # Get a validated choice from the user
    choice = get_user_choice()
    selected = TEAMS[choice]

    # Determine which teams to run
    if selected["key"] == "both":
        team_keys = ["manutd", "lakers"]
    else:
        team_keys = [selected["key"]]

    # Run the pipeline for each selected team, collecting results.
    # We wrap each run in a try/except so one team failing doesn't
    # prevent the other from running — important for the "both" option.
    results = []

    for team_key in team_keys:
        try:
            result = run_pipeline(team_key)
            results.append(result)

        except ConnectionError as e:
            # Sports API failure — network or data issue
            print(f"\n  ❌ Could not fetch match data: {e}")
            print("     Check your internet connection and try again.\n")

        except ValueError as e:
            # Bad data or failed parsing — likely a prompt/response issue
            print(f"\n  ❌ Data error: {e}\n")

        except Exception as e:
            # Catch-all for unexpected errors — log the type so it's diagnosable
            print(f"\n  ❌ Unexpected error for {team_key}: {type(e).__name__}: {e}\n")

    # If nothing succeeded, exit with a non-zero status code.
    # Exit code 1 is the Unix convention for "something went wrong."
    # This matters if you ever run this tool from a shell script or CI pipeline.
    if not results:
        print("  No Stories were generated. Exiting.")
        sys.exit(1)

    # Print the summary table
    print_summary(results)

    # Automatically open all generated HTML files in the default browser.
    # webbrowser.open() is non-blocking — it fires and returns immediately.
    # We ask the user first because auto-opening files can be surprising.
    open_preview = input("  Open HTML preview(s) in browser now? (y/n): ").strip().lower()

    if open_preview == "y":
        for result in results:
            # We prefix the path with 'file://' to tell the browser
            # this is a local file, not a web URL.
            webbrowser.open(f"file://{os.path.abspath(result['html_path'])}")
            print(f"  🌐 Opened: {result['html_path']}")


# The __main__ guard — this block only runs when you execute main.py directly.
# If another script were to import main.py (unusual but possible), the
# pipeline wouldn't auto-execute on import.
if __name__ == "__main__":
    main()