# prompt_builder.py
# Responsibility: transform clean match data into a structured prompt for Claude.
# This module knows about sports data and prompt engineering.
# It knows nothing about HTTP calls or file I/O.

def build_prompt(match: dict) -> str:
    """
    Constructs a detailed prompt for Claude based on cleaned match data.

    Args:
        match: The cleaned dictionary returned by sports_fetcher.fetch_last_match()

    Returns:
        A complete prompt string ready to be sent to the Claude API.
    """

    # We build the prompt in sections, then join them at the end.
    # This is easier to read and modify than one giant f-string.

    # --- Section 1: Persona ---
    # We give Claude a specific professional identity. "Sports content writer
    # specialising in social media Stories" is more precise than just
    # "sports writer" — it primes the model for punchy, visual-first language
    # rather than long-form journalism.
    persona = (
        "You are an expert sports content writer specialising in Instagram and "
        "Snapchat Stories for a B2B sports media platform. Your writing is bold, "
        "punchy, and visual-first. You write for fans who are scrolling fast — "
        "every word must earn its place. You never use clichés like 'at the end "
        "of the day' or 'gave 110 percent'."
    )

    # --- Section 2: Match Context ---
    # We inject the actual match data here. Notice we're selective — we give
    # Claude exactly what it needs to write good copy and nothing more.
    # Giving it the entire raw API response would add noise and cost tokens.
    sport = match["sport"]
    team = match["team_name"]
    opponent = match["opponent"]
    result = match["result"]
    our_score = match["our_score"]
    opp_score = match["opp_score"]
    date = match["date"]
    venue = match["venue"]
    league = match["league"]
    location_context = "at home" if match["is_home"] else "on the road"

    # Build a sport-specific detail line.
    # For football we have goal scorer details if available.
    # For basketball we have the point margin, which is more meaningful.
    if sport == "football" and match.get("goal_details_home"):
        home_goals = match["goal_details_home"] or "none"
        away_goals = match["goal_details_away"] or "none"
        extra_detail = (
            f"Home goal details: {home_goals}. "
            f"Away goal details: {away_goals}."
        )
    elif sport == "basketball":
        margin = abs(our_score - opp_score)
        extra_detail = f"Margin of victory/defeat: {margin} points."
    else:
        extra_detail = ""

    match_context = f"""
Here is the match data you will write about:

- Team: {team}
- Sport: {sport}
- League: {league}
- Opponent: {opponent}
- Result: {result}
- Score: {team} {our_score} — {opp_score} {opponent}
- Date: {date}
- Venue: {venue}
- Location: {location_context}
{extra_detail}
"""

    # --- Section 3: Task Instructions ---
    # This is the "what to do" section. We specify slide count, tone guidance
    # per result type, and constraints. The tone guidance is a product decision:
    # a WIN Story should feel celebratory, a LOSS Story should feel honest but
    # forward-looking, a DRAW somewhere in between. This makes the content feel
    # emotionally intelligent rather than robotically neutral.
    if result == "WIN":
        tone_guidance = (
            "Tone: Celebratory and bold. This is a moment to hype the fanbase. "
            "Use strong, active language. Make the reader feel the win."
        )
    elif result == "LOSS":
        tone_guidance = (
            "Tone: Honest and forward-looking. Acknowledge the result directly — "
            "don't sugarcoat it — but end on a note of resilience or next-game "
            "motivation. Fans respect honesty."
        )
    else:  # DRAW
        tone_guidance = (
            "Tone: Measured but engaging. A draw has drama in it — find it. "
            "Focus on a standout moment or stat that makes the story worth telling."
        )

    task = f"""
Your task is to generate a 4-slide Instagram/Snapchat Story about this match.

{tone_guidance}

The 4 slides must be:
1. HEADLINE slide — A short punchy headline (max 5 words, ALL CAPS) and a 
   one-sentence subtext (max 15 words) that expands on it.
2. STAT slide — Focus on the final score. Include a stat_label, stat_value, 
   and one narrative sentence (max 20 words) giving context.
3. STAT slide — Pick the most compelling secondary stat or moment from the 
   data (margin, a scorer, a comeback, a shutout, etc). Same structure.
4. CTA slide — A call-to-action for the team's fanbase. The text field should 
   be an account handle style label (e.g. "More from Lakeshow Nation"), and 
   subtext should be a one-line follow/engage prompt with a relevant emoji.

Important constraints:
- Headlines must feel like a back-page newspaper splash, not a press release.
- Stat values should be formatted for visual impact (e.g. "124 - 104", "2 - 0").
- Never start two slides with the same word.
- Write specifically about THIS match. Do not use generic filler content.
"""

    # --- Section 4: Output Format ---
    # This is the most technically critical section of the prompt.
    # We tell Claude to return ONLY a JSON object — no preamble, no explanation,
    # no markdown code fences. Just the raw JSON.
    #
    # Why so explicit? Because language models are trained on human conversation,
    # where it's natural to say "Sure! Here's the JSON: ...". That's charming
    # in a chatbot but breaks a JSON parser. We explicitly suppress that behavior.
    #
    # We also show the exact schema with every field name and type. This acts
    # like a typed contract — Claude knows exactly what shape to produce.
    output_format = f"""
Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
Start your response with {{ and end with }}.

The JSON must follow this exact schema:

{{
  "team": "{team}",
  "match": "<event name>",
  "date": "{date}",
  "result": "{result}",
  "slides": [
    {{
      "type": "headline",
      "text": "<MAX 5 WORDS ALL CAPS>",
      "subtext": "<max 15 words>"
    }},
    {{
      "type": "stat",
      "stat_label": "<short label e.g. FINAL SCORE>",
      "stat_value": "<the value e.g. 124 - 104>",
      "narrative": "<max 20 words of context>"
    }},
    {{
      "type": "stat",
      "stat_label": "<short label>",
      "stat_value": "<the value>",
      "narrative": "<max 20 words of context>"
    }},
    {{
      "type": "cta",
      "text": "<fanbase label>",
      "subtext": "<one-line engage prompt with emoji>"
    }}
  ]
}}
"""

    # Join all sections into one complete prompt string.
    # We use double newlines between sections for readability —
    # whitespace in prompts doesn't cost significant tokens but
    # helps the model parse the structure of your instructions.
    return f"{persona}\n\n{match_context}\n\n{task}\n\n{output_format}"

if __name__ == "__main__":
    # We import sports_fetcher here just for testing purposes.
    # In production, main.py orchestrates this — prompt_builder
    # never imports sports_fetcher directly.
    from sports_fetcher import fetch_last_match

    for team_key in ["lakers", "manutd"]:
        print(f"\n{'='*60}")
        print(f"PROMPT FOR: {team_key.upper()}")
        print('='*60)
        match = fetch_last_match(team_key)
        prompt = build_prompt(match)
        print(prompt)
        print(f"\n📏 Prompt length: {len(prompt)} characters / ~{len(prompt)//4} tokens")