"""
llm_client.py — Sends the repository context to an LLM and returns a summary.

WHY THIS FILE EXISTS
--------------------
This file handles all communication with the LLM (Large Language Model).
It is separate from main.py so that:
  - It's easy to swap out one LLM provider for another
  - The prompting logic lives in one place

WHICH LLM?
----------
Nebius Token Factory provides an OpenAI-compatible API endpoint,
so we use the `openai` Python library pointed at Nebius's base URL.
This same code works with OpenAI, or any OpenAI-compatible provider —
just change LLM_BASE_URL and LLM_API_KEY in your .env file.

PROMPT DESIGN
-------------
We use a two-part prompt:
  - System prompt: tells the LLM what role it's playing and what format to use
  - User prompt: contains the actual repo content and asks for the summary

We ask the LLM to produce a structured answer with clear sections so the
output is readable and useful.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# Load variables from .env file (if it exists)
load_dotenv()

# ---------------------------------------------------------------------------
# Configuration — read from environment variables
# ---------------------------------------------------------------------------

LLM_API_KEY  = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.studio.nebius.ai/v1/")
LLM_MODEL    = os.getenv("LLM_MODEL",    "meta-llama/Meta-Llama-3.1-70B-Instruct")

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a senior software engineer who specializes in quickly 
understanding unfamiliar codebases. You will be given the contents of a GitHub 
repository (directory structure + key file contents) and your job is to write 
a clear, concise summary for a developer who has never seen this project before.

Your summary must include these sections:

## What This Project Does
A 2-3 sentence plain-English explanation of the project's purpose and main functionality.

## Technologies & Stack
A bullet list of the main languages, frameworks, libraries, and tools used.

## Project Structure
A short description of how the code is organized (main directories, key files, 
and their roles).

## How to Get Started
Based on what you can see (README, package files, etc.), briefly describe how 
someone would install and run this project.

## Notable Details
Any interesting design decisions, patterns, or things worth knowing about.

Keep the tone professional but approachable. Be specific — avoid vague statements 
like "this is a well-structured project". Aim for 300-500 words total.
If you cannot determine something from the provided files, say so rather than guessing.
"""


def _build_user_prompt(repo_context: str) -> str:
    """Wrap the repo context in a clear instruction."""
    return f"""Please summarize the following GitHub repository.

{repo_context}

---
Write your summary now, following the format described in your instructions."""


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def summarize_with_llm(repo_context: str) -> str:
    """
    Send the repository context to the LLM and return the summary text.

    Args:
        repo_context: The string produced by github_client.fetch_repo_contents()

    Returns:
        A human-readable markdown summary of the repository.

    Raises:
        ValueError: If LLM_API_KEY is not set.
        Exception: If the API call fails.
    """
    if not LLM_API_KEY:
        raise ValueError(
            "LLM_API_KEY environment variable is not set. "
            "Please add it to your .env file. "
            "Get a key from https://api.studio.nebius.ai/ (Nebius) "
            "or https://platform.openai.com/api-keys (OpenAI)."
        )

    # Create the OpenAI client pointed at our chosen provider
    client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )

    # Make the API call
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_user_prompt(repo_context)},
        ],
        temperature=0.3,   # Lower = more focused/deterministic
        max_tokens=1024,   # Enough for a good summary, not too expensive
    )

    # Extract the text from the response
    summary = response.choices[0].message.content.strip()

    return summary
