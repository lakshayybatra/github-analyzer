# GitHub Repo Analyzer

A full-stack web app that lets you explore any GitHub user's profile — their top repos, language breakdown, activity, and more. There's also an AI chatbot powered by Gemini that knows the user's GitHub data and can answer questions about them.

---

## What it does

- Search any GitHub username and instantly see their profile stats
- Top repositories ranked by stars
- Language breakdown as an interactive doughnut chart
- Recently updated repos
- An AI chatbot on the side that you can ask things like:
  - *"What's their strongest language?"*
  - *"Would they be a good Python hire?"*
  - *"Summarize this profile in 2 sentences"*

---

## Tech stack

- **Backend** — Python, FastAPI, httpx
- **Frontend** — HTML, CSS, JavaScript, Chart.js
- **AI** — Google Gemini 2.5 Flash API
- **External API** — GitHub REST API

---

## Running it locally

**1. Clone the repo**
```bash
git clone https://github.com/lakshayybatra/github-analyzer
cd github-analyzer
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Set your Gemini API key**

Get a free key at [aistudio.google.com](https://aistudio.google.com)

```bash
# Mac/Linux
export GEMINI_API_KEY="your_key_here"

# Windows (PowerShell)
$env:GEMINI_API_KEY="your_key_here"
```

**4. Optionally set a GitHub token** (bumps rate limit from 60 to 5000 requests/hour)

Get a free token at github.com/settings/tokens

```bash
export GITHUB_TOKEN="your_token_here"
```

**5. Start the server**
```bash
uvicorn main:app --reload
```

**6. Open your browser**
```
http://localhost:8000
```

---

## Project structure

```
github_analyzer/
├── main.py           # FastAPI backend — all API endpoints and GitHub/Gemini logic
├── requirements.txt  # Python dependencies
├── Procfile          # For Render deployment
└── static/
    └── index.html    # Frontend — HTML, CSS, and JS all in one file
```

---

## How it works

When you search a username, the frontend calls two backend endpoints — `/api/user/{username}` and `/api/repos/{username}`. The backend fetches data from GitHub's public API, processes it (sorts by stars, counts languages, calculates percentages), and returns clean JSON. The frontend renders it with Chart.js for the doughnut chart.

The chatbot works by passing the full GitHub data as context to the Gemini API along with your question. Gemini only answers based on what's actually in the data — it won't make things up.
