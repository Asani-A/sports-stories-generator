# claude_client.py
# Responsibility: send a prompt to the Claude API and return the raw response text.
# This module knows nothing about sports, HTML, or files.
# It has one job: talk to Claude.

import os
from dotenv import load_dotenv
import anthropic  # the official Anthropic Python SDK

# Load environment variables from .env so ANTHROPIC_API_KEY is accessible.
# It's safe to call load_dotenv() multiple times across modules —
# it's idempotent (calling it again has no effect if already loaded).
load_dotenv()


def generate_story(prompt: str) -> str:
    """
    Sends a prompt to Claude and returns the generated text response.

    Args:
        prompt: The complete prompt string from prompt_builder.build_prompt()

    Returns:
        Claude's raw response as a string (should be a JSON object).

    Raises:
        ValueError: If the API key is missing.
        anthropic.APIError: If the API call fails.
    """

    # Step 1: Retrieve the API key from the environment.
    # We validate it here rather than letting the SDK throw a cryptic error.
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found. "
            "Check your .env file is present and correctly formatted."
        )

    # Step 2: Instantiate the Anthropic client.
    # The SDK reads the api_key and handles authentication for every
    # subsequent request. We create it fresh per call here for simplicity.
    # In a production web server you'd create it once at startup and reuse it.
    client = anthropic.Anthropic(api_key=api_key)

    # Step 3: Split our prompt into system and user parts.
    # Our prompt from prompt_builder is one big string. We're going to
    # send the first paragraph (the persona) as the system prompt, and
    # the rest (match data + task + format) as the user message.
    #
    # We do this by splitting on the first double-newline after the persona.
    # The persona is always the first block, ending before "\n\nHere is the match".
    # This gives Claude a cleaner instruction hierarchy.
    parts = prompt.split("\n\nHere is the match data", 1)

    if len(parts) == 2:
        # Successfully split — persona goes to system, rest to user
        system_content = parts[0].strip()
        user_content = "Here is the match data" + parts[1].strip()
    else:
        # Fallback: if splitting fails for any reason, send everything
        # as the user message. The output quality will be nearly identical.
        system_content = (
            "You are an expert sports content writer for social media Stories. "
            "Follow the user's instructions exactly."
        )
        user_content = prompt

    print("🤖 Sending prompt to Claude...")

    # Step 4: Make the API call.
    # This is the core of this entire module — one method call.
    # Let's break down every parameter:
    #
    #   model: which Claude model to use. claude-sonnet-4-5-20250929 is
    #          the current Sonnet model — fast, capable, great at
    #          following structured output instructions.
    #
    #   max_tokens: the maximum number of tokens Claude can generate in
    #               its response. 1024 is generous for a 4-slide JSON object
    #               (which will be ~200-300 tokens). This is a safety cap,
    #               not a target — Claude will stop when it's done.
    #
    #   system: the standing brief. Sets Claude's persona and behaviour
    #           for the entire interaction.
    #
    #   messages: the conversation. We send one user message containing
    #             the match data, task instructions, and format spec.
    #             The list structure supports multi-turn conversations,
    #             but we only need one turn here.
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        system=system_content,
        messages=[
            {
                "role": "user",
                "content": user_content
            }
        ]
    )

    # Step 5: Extract the text from the response object.
    # The SDK returns a Message object, not a plain string.
    # response.content is a list of content blocks (Claude can return
    # multiple blocks in advanced use cases like tool use).
    # For a standard text response, we always want content[0].text.
    #
    # response.usage gives you the token counts for this call —
    # we log them so you can see exactly what each call costs.
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    print(f"✅ Response received.")
    print(f"📊 Tokens used — Input: {input_tokens} | Output: {output_tokens} | "
          f"Total: {input_tokens + output_tokens}")

    # Return just the text string — everything else in the response
    # object (model name, stop reason, usage) is logged above but
    # not passed forward. The next module only needs the text.
    return response.content[0].text


if __name__ == "__main__":
    from sports_fetcher import fetch_last_match
    from prompt_builder import build_prompt

    # Test with the Lakers first — it has the richer data (point margin)
    match = fetch_last_match("lakers")
    prompt = build_prompt(match)

    # Make the actual API call
    raw_response = generate_story(prompt)

    print("\n" + "="*60)
    print("RAW RESPONSE FROM CLAUDE:")
    print("="*60)
    print(raw_response)