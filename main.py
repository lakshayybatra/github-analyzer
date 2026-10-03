"""
main.py — GitHub Repo Analyzer Backend
FastAPI server that fetches and processes GitHub user data via the public GitHub API.
Exposes clean REST endpoints consumed by the frontend.
Includes a Gemini-powered chatbot that knows the user's GitHub data.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from collections import Counter
import httpx
import os

app = FastAPI(title="GitHub Repo Analyzer")
app.mount("/static", StaticFiles(directory="static"), name="static")

GITHUB_API   = "https://api.github.com"
GEMINI_API   = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_KEY   = os.getenv("GEMINI_API_KEY", "")

HEADERS = {"Accept": "application/vnd.github+json"}
TOKEN   = os.getenv("GITHUB_TOKEN")
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


# ── Models ─────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    username: str
    github_context: dict  # full profile + repo data passed from frontend


# ── Helpers ────────────────────────────────────────────────────────────────────

async def gh_get(client: httpx.AsyncClient, url: str):
    r = await client.get(url, headers=HEADERS)
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="GitHub user not found.")
    if r.status_code == 403:
        raise HTTPException(status_code=429, detail="GitHub API rate limit hit. Try again in a minute.")
    r.raise_for_status()
    return r.json()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/api/user/{username}")
async def get_user_profile(username: str):
    async with httpx.AsyncClient() as client:
        data = await gh_get(client, f"{GITHUB_API}/users/{username}")
    return {
        "login":        data.get("login"),
        "name":         data.get("name") or data.get("login"),
        "avatar_url":   data.get("avatar_url"),
        "bio":          data.get("bio") or "No bio provided.",
        "location":     data.get("location") or "—",
        "public_repos": data.get("public_repos", 0),
        "followers":    data.get("followers", 0),
        "following":    data.get("following", 0),
        "created_at":   data.get("created_at", "")[:10],
        "html_url":     data.get("html_url"),
    }


@app.get("/api/repos/{username}")
async def get_repo_stats(username: str):
    async with httpx.AsyncClient() as client:
        repos = await gh_get(
            client,
            f"{GITHUB_API}/users/{username}/repos?per_page=100&sort=updated"
        )

    if not repos:
        return {
            "top_repos": [], "language_breakdown": [],
            "totals": {"stars": 0, "forks": 0, "repos": 0},
            "recent_repos": []
        }

    sorted_by_stars = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)
    top_repos = [
        {
            "name":        r["name"],
            "description": r.get("description") or "No description.",
            "stars":       r.get("stargazers_count", 0),
            "forks":       r.get("forks_count", 0),
            "language":    r.get("language") or "—",
            "url":         r.get("html_url"),
            "updated_at":  r.get("updated_at", "")[:10],
        }
        for r in sorted_by_stars[:5]
    ]

    lang_counter = Counter(r["language"] for r in repos if r.get("language"))
    total_lang   = sum(lang_counter.values()) or 1
    language_breakdown = [
        {"language": lang, "count": count, "pct": round(count / total_lang * 100, 1)}
        for lang, count in lang_counter.most_common(8)
    ]

    totals = {
        "stars": sum(r.get("stargazers_count", 0) for r in repos),
        "forks": sum(r.get("forks_count", 0) for r in repos),
        "repos": len(repos),
    }

    recent_repos = [
        {
            "name":       r["name"],
            "language":   r.get("language") or "—",
            "updated_at": r.get("updated_at", "")[:10],
            "url":        r.get("html_url"),
        }
        for r in repos[:5]
    ]

    return {
        "top_repos":          top_repos,
        "language_breakdown": language_breakdown,
        "totals":             totals,
        "recent_repos":       recent_repos,
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not GEMINI_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set on server.")
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Build context string from GitHub data
    ctx  = req.github_context
    profile = ctx.get("profile", {})
    repos   = ctx.get("repos", {})

    top_repos_text = "\n".join(
        f"  - {r['name']} ({r['language']}) — {r['stars']} stars, {r['forks']} forks. {r['description']}"
        for r in repos.get("top_repos", [])
    )
    lang_text = ", ".join(
        f"{l['language']} ({l['pct']}%)"
        for l in repos.get("language_breakdown", [])
    )
    recent_text = ", ".join(r["name"] for r in repos.get("recent_repos", []))

    system_prompt = f"""You are a helpful GitHub profile analyst assistant. 
You have been given data about the GitHub user @{req.username} and your job is to answer questions about them in a friendly, conversational, and insightful way.

Here is everything you know about this user:

NAME: {profile.get("name")}
BIO: {profile.get("bio")}
LOCATION: {profile.get("location")}
FOLLOWERS: {profile.get("followers")} | FOLLOWING: {profile.get("following")}
PUBLIC REPOS: {profile.get("public_repos")}
JOINED GITHUB: {profile.get("created_at")}
TOTAL STARS: {repos.get("totals", {}).get("stars")}
TOTAL FORKS: {repos.get("totals", {}).get("forks")}

TOP REPOS BY STARS:
{top_repos_text}

LANGUAGE BREAKDOWN: {lang_text}
RECENTLY UPDATED REPOS: {recent_text}

Answer questions about this user based only on the data above. Be concise, friendly and insightful.
If asked something you don't have data for, say so honestly.
Do not make up information."""

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": req.message}]}],
        "generationConfig": {"maxOutputTokens": 400, "temperature": 0.7}
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.post(
                f"{GEMINI_API}?key={GEMINI_KEY}",
                json=payload
            )
            r.raise_for_status()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Gemini API timed out. Try again.")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"Gemini API error: {e.response.status_code}")

    data = r.json()
    try:
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise HTTPException(status_code=502, detail="Unexpected response from Gemini.")

    return {"reply": reply}
