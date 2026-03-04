"""
main.py — Entry point for the GitHub Repository Summarizer API.

This is a FastAPI application. FastAPI is a modern Python web framework
that makes it easy to build APIs. It automatically generates documentation
and validates request/response data.

The app exposes one endpoint:
  POST /summarize  →  accepts a GitHub URL, returns a project summary
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import uvicorn

from github_client import fetch_repo_contents
from llm_client import summarize_with_llm

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GitHub Repository Summarizer",
    description="Give me a GitHub URL and I'll tell you what the project does.",
    version="1.0.0",
)

# Allow all origins so the API can be called from a browser or any tool
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SummarizeRequest(BaseModel):
    """What the caller must send in the request body (JSON)."""
    github_url: str  # e.g. "https://github.com/owner/repo"

class SummarizeResponse(BaseModel):
    """What we send back."""
    summary: str
    repo_url: str

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    """Health-check endpoint — just confirms the server is running."""
    return {"status": "ok", "message": "GitHub Summarizer is running. POST to /summarize"}


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    """
    Main endpoint.

    Steps:
      1. Validate and parse the GitHub URL
      2. Use the GitHub API to fetch important files from the repo
      3. Send those files to an LLM and ask for a summary
      4. Return the summary
    """
    url = request.github_url.strip()

    # Basic sanity check
    if "github.com" not in url:
        raise HTTPException(status_code=400, detail="URL must be a GitHub repository URL.")

    # --- Step 1: Fetch repo contents via GitHub API ---
    try:
        repo_context = fetch_repo_contents(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch repository: {e}")

    # --- Step 2: Ask the LLM to summarize ---
    try:
        summary = summarize_with_llm(repo_context)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")

    return SummarizeResponse(summary=summary, repo_url=url)


# ---------------------------------------------------------------------------
# Run directly with:  python main.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
