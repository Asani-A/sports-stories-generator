# story_parser.py
# Responsibility: validate Claude's raw text response, parse it into a Python
# dictionary, validate the structure, and write it to a JSON output file.
# This module is the quality gate between the AI layer and the output layer.

import json
import re
import os
from datetime import datetime


def parse_and_save(raw_response: str, team_key: str) -> dict:
    """
    Parses Claude's raw text response into a validated Story dictionary
    and saves it as a JSON file in the output/ directory.

    Args:
        raw_response: The raw string returned by claude_client.generate_story()
        team_key:     "lakers" or "manutd" — used to name the output file

    Returns:
        The validated Story dictionary.

    Raises:
        ValueError: If the response can't be parsed or fails validation.
        IOError:    If the output file can't be written.
    """

    # Step 1: Clean the raw response.
    # This handles the edge cases described above — markdown fences,
    # preamble text, and whitespace — before we try to parse.
    cleaned = _clean_response(raw_response)

    # Step 2: Parse the cleaned string into a Python dictionary.
    story = _parse_json(cleaned)

    # Step 3: Validate the dictionary has the structure we expect.
    # This catches schema drift — e.g. missing fields or wrong slide count.
    _validate_schema(story)

    # Step 4: Write the validated dictionary to a JSON file.
    output_path = _write_json(story, team_key)

    print(f"💾 Story saved to: {output_path}")
    return story


def _clean_response(raw: str) -> str:
    """
    Removes common Claude response artifacts that would break JSON parsing.

    This function is defensive — it assumes the response *might* have issues
    and strips them safely. If the response is already clean, nothing changes.
    """

    # Strip leading and trailing whitespace first.
    cleaned = raw.strip()

    # Remove markdown code fences if present.
    # re.sub() is Python's regex substitution function.
    # The pattern r'```(?:json)?\s*' matches either:
    #   ```json    (with the word json)
    #   ```        (without it)
    # followed by optional whitespace. The re.DOTALL flag makes . match
    # newlines too. We replace both the opening and closing fences with "".
    cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'```\s*$', '', cleaned, flags=re.MULTILINE)

    # If there's any text before the first {, strip it.
    # This handles preamble like "Here is the JSON: { ... }"
    # str.find() returns the index of the first occurrence, or -1 if not found.
    brace_start = cleaned.find('{')
    brace_end = cleaned.rfind('}')  # rfind finds the LAST occurrence

    if brace_start == -1 or brace_end == -1:
        raise ValueError(
            "No JSON object found in Claude's response. "
            f"Raw response was:\n{raw[:200]}..."
        )

    # Slice out just the JSON object, discarding anything before { or after }
    cleaned = cleaned[brace_start:brace_end + 1]

    return cleaned.strip()


def _parse_json(cleaned: str) -> dict:
    """
    Parses a cleaned JSON string into a Python dictionary.
    Provides a clear error message if parsing still fails after cleaning.
    """
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse Claude's response as JSON.\n"
            f"Parse error: {e}\n"
            f"Cleaned response was:\n{cleaned[:300]}..."
        )


def _validate_schema(story: dict) -> None:
    """
    Validates that the parsed Story dictionary has the expected structure.

    We check for:
    - Required top-level fields
    - Presence and type of the slides list
    - Correct number of slides (exactly 4)
    - Required fields within each slide type

    This function raises ValueError on the first problem it finds,
    with a message specific enough to diagnose the issue.
    """

    # Check required top-level fields.
    # These are the fields our HTML renderer will reference by name.
    required_top_level = ["team", "match", "date", "result", "slides"]
    for field in required_top_level:
        if field not in story:
            raise ValueError(
                f"Story is missing required top-level field: '{field}'. "
                f"Keys present: {list(story.keys())}"
            )

    # Check slides is a list.
    if not isinstance(story["slides"], list):
        raise ValueError(
            f"'slides' should be a list, got {type(story['slides']).__name__}"
        )

    # Check slide count.
    # We expect exactly 4: headline, stat, stat, cta.
    # We warn rather than raise for count issues — 3 or 5 slides isn't
    # catastrophic, just not ideal. A missing required field IS catastrophic.
    slide_count = len(story["slides"])
    if slide_count != 4:
        print(f"⚠️  Warning: expected 4 slides, got {slide_count}. Continuing.")

    # Define required fields per slide type.
    # Each slide type has a different shape, so we validate each separately.
    required_fields = {
        "headline": ["type", "text", "subtext"],
        "stat":     ["type", "stat_label", "stat_value", "narrative"],
        "cta":      ["type", "text", "subtext"]
    }

    for i, slide in enumerate(story["slides"]):
        slide_type = slide.get("type")

        if slide_type not in required_fields:
            raise ValueError(
                f"Slide {i+1} has unknown type: '{slide_type}'. "
                f"Expected one of: {list(required_fields.keys())}"
            )

        for field in required_fields[slide_type]:
            if field not in slide:
                raise ValueError(
                    f"Slide {i+1} (type: '{slide_type}') is missing "
                    f"required field: '{field}'. "
                    f"Fields present: {list(slide.keys())}"
                )

    # If we reach here, the schema is valid.
    print(f"✅ Schema validated: {slide_count} slides, "
          f"types: {[s['type'] for s in story['slides']]}")


def _write_json(story: dict, team_key: str) -> str:
    """
    Writes the validated Story dictionary to a JSON file in output/.

    The filename includes a timestamp so repeated runs don't overwrite
    each other — useful when you want to compare outputs across sessions.

    Returns the full path of the written file.
    """

    # Build the output directory path relative to this file's location.
    # os.path.dirname(__file__) gives us the directory this script lives in.
    # os.path.join() builds a path safely regardless of OS (handles / vs \).
    output_dir = os.path.join(os.path.dirname(__file__), "output")

    # Create the directory if it doesn't exist.
    # exist_ok=True means don't raise an error if it already exists —
    # the opposite of the default behaviour.
    os.makedirs(output_dir, exist_ok=True)

    # Build a timestamped filename.
    # strftime formats a datetime object as a string.
    # "%Y%m%d_%H%M%S" produces something like "20260213_143022".
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{team_key}_story_{timestamp}.json"
    output_path = os.path.join(output_dir, filename)

    # Write the dictionary as formatted JSON.
    # indent=2 makes the file human-readable (pretty-printed).
    # ensure_ascii=False preserves emoji and non-ASCII characters —
    # important since our CTA slides often contain emoji.
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(story, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise IOError(f"Failed to write output file: {e}")

    return output_path


if __name__ == "__main__":
    from sports_fetcher import fetch_last_match
    from prompt_builder import build_prompt
    from claude_client import generate_story

    for team_key in ["lakers", "manutd"]:
        print(f"\n{'='*60}")
        print(f"PARSING STORY FOR: {team_key.upper()}")
        print('='*60)

        match = fetch_last_match(team_key)
        prompt = build_prompt(match)
        raw_response = generate_story(prompt)
        story = parse_and_save(raw_response, team_key)

        # Print a summary of what was saved rather than the whole thing —
        # we've already seen the full JSON in Stage 4.
        print(f"\n📋 Story summary:")
        print(f"   Team:   {story['team']}")
        print(f"   Match:  {story['match']}")
        print(f"   Result: {story['result']}")
        print(f"   Slides: {[s['type'] for s in story['slides']]}")