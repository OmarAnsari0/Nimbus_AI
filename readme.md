# GitHub Repository Summarizer

A simple API service that takes a GitHub repository URL and returns a human-readable
summary of what the project does, what technologies it uses, and how it's structured.

Built with **Python**, **FastAPI**, and an **LLM** (Nebius / OpenAI-compatible).

---

## How It Works

```
You → POST /summarize { "github_url": "..." }
       ↓
  1. Parse the GitHub URL (extract owner/repo)
  2. Call GitHub API to get the file tree
  3. Fetch the most important files (README, manifests, source files)
       — skipping binaries, lock files, node_modules, etc.
       — staying within a ~12,000-word budget
  4. Send file contents to an LLM with a prompt asking for a summary
  5. Return the summary as JSON
       ↓
You ← { "summary": "...", "repo_url": "..." }
```

---

## Prerequisites

- **Python 3.11+** — check with `python --version`  
- **pip** — usually included with Python  
- An **LLM API key** from [Nebius Token Factory](https://api.studio.nebius.ai/) *(recommended — $1 free credit)* or [OpenAI](https://platform.openai.com/api-keys)

---

## Installation & Setup

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/github-summarizer.git
cd github-summarizer
```

### Step 2 — Create a virtual environment

A virtual environment keeps this project's dependencies isolated from your
system Python. This is good practice and avoids version conflicts.

```bash
# Create the virtual environment (only need to do this once)
python -m venv venv

# Activate it:
# On macOS / Linux:
source venv/bin/activate

# On Windows (Command Prompt):
venv\Scripts\activate.bat

# On Windows (PowerShell):
venv\Scripts\Activate.ps1
```

You'll know it's active when you see `(venv)` at the start of your terminal prompt.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs FastAPI, Uvicorn (the server), the OpenAI SDK, and a few other packages.

### Step 4 — Configure your API key

Copy the example environment file:

```bash
# macOS / Linux:
cp .env.example .env

# Windows:
copy .env.example .env
```

Now open `.env` in any text editor and fill in your API key:

```
LLM_API_KEY=your_actual_api_key_here
```

**Getting a Nebius API key (free $1 credit):**
1. Go to [https://api.studio.nebius.ai/](https://api.studio.nebius.ai/)
2. Sign up / log in
3. Go to **API Keys** and create a new key
4. Paste it into your `.env` file

> ⚠️ Never commit your `.env` file to GitHub. It's already in `.gitignore` to prevent this.

---

## Running the Server

```bash
python main.py
```

Or alternatively:

```bash
uvicorn main:app --reload --port 8000
```

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

The server is now running at **http://localhost:8000**

---

## Using the API

### Option A — Interactive docs (easiest way to test)

Open your browser and go to:
```
http://localhost:8000/docs
```

FastAPI automatically generates a nice UI where you can try the endpoint directly.

### Option B — curl (command line)

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/tiangolo/fastapi"}'
```

### Option C — Python requests

```python
import requests

response = requests.post(
    "http://localhost:8000/summarize",
    json={"github_url": "https://github.com/tiangolo/fastapi"}
)
print(response.json()["summary"])
```

### Option D — httpie (if installed)

```bash
http POST localhost:8000/summarize github_url="https://github.com/tiangolo/fastapi"
```

### Example Response

```json
{
  "summary": "## What This Project Does\nFastAPI is a modern, high-performance web framework for building APIs with Python...\n\n## Technologies & Stack\n- Python 3.7+\n- Starlette (ASGI framework)\n- Pydantic (data validation)\n...",
  "repo_url": "https://github.com/tiangolo/fastapi"
}
```

---

## Running the Tests

```bash
pip install pytest
pytest test_app.py -v
```

Tests mock the GitHub API and LLM calls so they run quickly without needing
real API keys or network access.

---

## Project Structure

```
github-summarizer/
├── main.py            # FastAPI app — defines the /summarize endpoint
├── github_client.py   # Fetches and filters repository files via GitHub API
├── llm_client.py      # Sends content to the LLM and returns the summary
├── test_app.py        # Automated tests
├── requirements.txt   # Python dependencies
├── .env.example       # Template for environment variables (copy to .env)
├── .gitignore         # Tells Git which files to ignore
└── README.md          # This file
```

---

## Design Decisions

### How we handle large repositories

Repositories can have thousands of files. We can't send everything to the LLM because:
- LLMs have a **context window limit** (max text they can process at once)
- Sending more tokens costs more money and takes longer

Our approach:
1. Use the GitHub Trees API to get a full file list in one request
2. **Skip** files that add no signal: `node_modules/`, `*.lock`, binaries, images, etc.
3. **Prioritize** high-signal files: `README.md`, `package.json`, `requirements.txt`, etc.
4. Then add **source files** starting with top-level ones (usually most important)
5. Stop once we hit ~12,000 words — comfortably within the LLM's context window

### Why FastAPI?

FastAPI is modern, fast, and has excellent documentation. It auto-validates
request/response data using Pydantic and generates interactive API docs for free.

### Why the OpenAI SDK for Nebius?

Nebius's API is OpenAI-compatible (same request/response format), so we can
use the standard `openai` Python library — just changing the `base_url`.
This makes it trivial to switch to OpenAI or another provider.

---

## Troubleshooting

**"LLM_API_KEY environment variable is not set"**
→ Make sure you created `.env` (not just `.env.example`) and added your key.

**GitHub API rate limit errors**
→ Add a `GITHUB_TOKEN` to your `.env` file. Public repos only need read access.
   Create one at https://github.com/settings/tokens

**Port 8000 already in use**
→ Run on a different port: `uvicorn main:app --reload --port 8001`

**`ModuleNotFoundError`**
→ Make sure your virtual environment is activated (`source venv/bin/activate`)
   and you ran `pip install -r requirements.txt`