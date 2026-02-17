# html_renderer.py
# Responsibility: take a validated Story dictionary and write a styled HTML
# preview file to the output/ directory.
# This module knows about HTML and CSS. It knows nothing about APIs or JSON parsing.

import os
from datetime import datetime


def render_html(story: dict, team_key: str) -> str:
    """
    Generates a styled HTML preview of the Story slides.

    Args:
        story:    The validated dictionary returned by story_parser.parse_and_save()
        team_key: "lakers" or "manutd" — used for theming and filename

    Returns:
        The full path of the written HTML file.
    """

    # Step 1: Choose a colour theme based on team and result.
    # Real sports media products use official team colours.
    # We define a palette per team and adjust brightness based on result.
    theme = _get_theme(team_key, story["result"])

    # Step 2: Generate the HTML string for each slide.
    # We build each slide as a separate HTML block, then join them.
    slides_html = "\n".join(
    _render_slide(slide, theme, story["result"]) for slide in story["slides"]
)

    # Step 3: Wrap the slides in a full HTML document.
    html = _build_document(story, slides_html, theme)

    # Step 4: Write the file.
    output_path = _write_html(html, team_key)

    print(f"🎨 HTML preview saved to: {output_path}")
    return output_path


def _get_theme(team_key: str, result: str) -> dict:
    """
    Returns a colour theme dictionary for the given team and result.

    Each theme has:
    - bg:         main background colour (dark, as is standard for Stories)
    - accent:     primary brand colour used for labels and highlights
    - accent2:    secondary brand colour for gradients and borders
    - text:       primary text colour (almost always white for Stories)
    - subtext:    secondary text colour (slightly muted)
    - card_bg:    slide card background (slightly lighter than page bg)
    - result_tag: colour of the WIN/LOSS/DRAW badge
    """

    # Base palettes using each team's official brand colours.
    # Lakers: purple (#552583) and gold (#FDB927)
    # Man Utd: red (#DA291C) and gold/yellow (#FBE122)
    palettes = {
        "lakers": {
            "bg": "#1a0533",
            "accent": "#FDB927",
            "accent2": "#552583",
            "text": "#FFFFFF",
            "subtext": "#E0D0F0",
            "card_bg": "#2d0f52",
        },
        "manutd": {
            "bg": "#1a0505",
            "accent": "#DA291C",
            "accent2": "#FBE122",
            "text": "#FFFFFF",
            "subtext": "#F0D0D0",
            "card_bg": "#2d0a0a",
        }
    }

    # Fallback palette for any team not in the dict — clean dark theme.
    base = palettes.get(team_key, {
        "bg": "#0f0f0f",
        "accent": "#00ff88",
        "accent2": "#005533",
        "text": "#FFFFFF",
        "subtext": "#CCCCCC",
        "card_bg": "#1a1a1a",
    })

    # Result colour for the badge shown on the headline slide.
    result_colours = {
        "WIN":  "#00C851",  # green
        "LOSS": "#ff4444",  # red
        "DRAW": "#ffbb33",  # amber
    }
    base["result_tag"] = result_colours.get(result, "#888888")

    return base


def _render_slide(slide: dict, theme: dict, result: str = "") -> str:

    slide_type = slide.get("type")

    if slide_type == "headline":
        return _render_headline(slide, theme, result)  # pass result through
    elif slide_type == "stat":
        return _render_stat(slide, theme)
    elif slide_type == "cta":
        return _render_cta(slide, theme)
    else:
        return f'<div class="slide"><p>Unknown slide type: {slide_type}</p></div>'


def _render_headline(slide: dict, theme: dict, result: str = "") -> str:
    return f"""
    <div class="slide headline-slide" style="
        background: linear-gradient(160deg, {theme['card_bg']} 0%, {theme['accent2']} 100%);
        border-top: 4px solid {theme['accent']};
    ">
        <div class="result-badge" style="background: {theme['result_tag']}">
            {result}
        </div>
        <h1 class="headline-text" style="color: {theme['accent']}">
            {slide['text']}
        </h1>
        <p class="subtext" style="color: {theme['subtext']}">
            {slide['subtext']}
        </p>
        <div class="slide-type-label">STORY</div>
    </div>"""


def _render_stat(slide: dict, theme: dict) -> str:
    """Renders a stat slide — label, large value, narrative sentence."""
    return f"""
    <div class="slide stat-slide" style="
        background: {theme['card_bg']};
        border-left: 4px solid {theme['accent']};
    ">
        <p class="stat-label" style="color: {theme['accent']}">
            {slide['stat_label']}
        </p>
        <h2 class="stat-value" style="color: {theme['text']}">
            {slide['stat_value']}
        </h2>
        <p class="narrative" style="color: {theme['subtext']}">
            {slide['narrative']}
        </p>
    </div>"""


def _render_cta(slide: dict, theme: dict) -> str:
    """Renders the CTA slide — fanbase label, follow prompt, branded button."""
    return f"""
    <div class="slide cta-slide" style="
        background: linear-gradient(160deg, {theme['accent2']} 0%, {theme['card_bg']} 100%);
        border-top: 4px solid {theme['accent']};
    ">
        <h2 class="cta-text" style="color: {theme['text']}">
            {slide['text']}
        </h2>
        <p class="cta-subtext" style="color: {theme['subtext']}">
            {slide['subtext']}
        </p>
        <div class="cta-button" style="
            background: {theme['accent']};
            color: {theme['bg']};
        ">
            Follow Now
        </div>
    </div>"""


def _build_document(story: dict, slides_html: str, theme: dict) -> str:
    """
    Wraps the slide HTML in a complete, self-contained HTML document.

    All CSS is inlined in a <style> block — no external files needed.
    The CSS uses a mobile-first approach with a max-width that mirrors
    the aspect ratio of a real Stories feed (~390px wide).
    """

    # We use Python's triple-quoted f-string to write the full HTML document.
    # Every {variable} here is a Python variable being injected.
    # The double braces {{ and }} are escaped braces — they render as
    # literal { and } in the HTML output, not Python substitutions.
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{story['team']} — Match Story</title>
    <style>
        /* Page reset and base */
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            background: {theme['bg']};
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                         'Helvetica Neue', Arial, sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
        }}

        /* Header bar above the cards */
        .story-header {{
            width: 100%;
            max-width: 390px;
            margin-bottom: 24px;
            text-align: center;
        }}

        .story-header .team-name {{
            color: {theme['accent']};
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 3px;
            text-transform: uppercase;
        }}

        .story-header .match-info {{
            color: {theme['subtext']};
            font-size: 12px;
            margin-top: 4px;
        }}

        /* Each slide card — Story aspect ratio is roughly 9:16.
           390px wide × 693px tall mirrors a real phone Stories screen. */
        .slide {{
            width: 390px;
            min-height: 240px;
            border-radius: 16px;
            padding: 36px 32px;
            margin-bottom: 16px;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            overflow: hidden;
        }}

        /* Headline slide */
        .headline-text {{
            font-size: 42px;
            font-weight: 900;
            line-height: 1.05;
            letter-spacing: -1px;
            margin-bottom: 16px;
            text-transform: uppercase;
        }}

        .subtext {{
            font-size: 16px;
            line-height: 1.5;
            font-weight: 400;
        }}

        .result-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: #000;
            margin-bottom: 20px;
            align-self: flex-start;
        }}

        .slide-type-label {{
            position: absolute;
            top: 16px;
            right: 20px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 3px;
            color: rgba(255,255,255,0.25);
        }}

        /* Stat slide */
        .stat-label {{
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-bottom: 12px;
        }}

        .stat-value {{
            font-size: 56px;
            font-weight: 900;
            letter-spacing: -2px;
            line-height: 1;
            margin-bottom: 20px;
        }}

        .narrative {{
            font-size: 15px;
            line-height: 1.6;
            font-weight: 400;
        }}

        /* CTA slide */
        .cta-text {{
            font-size: 28px;
            font-weight: 900;
            line-height: 1.2;
            margin-bottom: 12px;
            color: {theme['text']};
        }}

        .cta-subtext {{
            font-size: 15px;
            line-height: 1.5;
            margin-bottom: 28px;
        }}

        .cta-button {{
            display: inline-block;
            padding: 12px 28px;
            border-radius: 30px;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 1px;
            text-transform: uppercase;
            align-self: flex-start;
            cursor: pointer;
        }}

        /* Footer */
        .story-footer {{
            width: 100%;
            max-width: 390px;
            text-align: center;
            margin-top: 16px;
            color: rgba(255,255,255,0.2);
            font-size: 11px;
            letter-spacing: 1px;
        }}
    </style>
</head>
<body>

    <div class="story-header">
        <div class="team-name">{story['team']}</div>
        <div class="match-info">{story['match']} &nbsp;·&nbsp; {story['date']}</div>
    </div>

    {slides_html}

    <div class="story-footer">
        Generated by Sports Stories Generator &nbsp;·&nbsp;
        {datetime.now().strftime("%d %b %Y")}
    </div>

</body>
</html>"""


def _write_html(html: str, team_key: str) -> str:
    """Writes the HTML string to a timestamped file in output/."""

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{team_key}_story_{timestamp}.html"
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


if __name__ == "__main__":
    import json
    import glob

    # Find the most recent JSON files for each team in output/
    for team_key in ["lakers", "manutd"]:
        # glob finds files matching a pattern — * is a wildcard
        pattern = os.path.join("output", f"{team_key}_story_*.json")
        matches = sorted(glob.glob(pattern))

        if not matches:
            print(f"⚠️  No JSON file found for {team_key}. Run story_parser.py first.")
            continue

        # Take the most recent file (last in sorted order)
        latest_json = matches[-1]
        print(f"\n📂 Loading: {latest_json}")

        with open(latest_json, "r", encoding="utf-8") as f:
            story = json.load(f)

        html_path = render_html(story, team_key)
        print(f"✅ Open this in your browser: {html_path}")