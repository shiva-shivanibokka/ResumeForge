"""
github_parser.py
Reads a GitHub profile and extracts project summaries from repositories.

Strategy per repo (in order of priority):
  1. README.md  → primary source
  2. requirements.txt / pyproject.toml / package.json / Pipfile / go.mod  → tech stack
  3. Top-level file/folder names  → infer project type
  4. Repo metadata (description, topics, language)  → supplement

Claude then synthesizes all signals into a structured project summary.
"""

import os
import re
import base64
import requests
from typing import Optional


# GITHUB API CLIENT


def _github_headers(token: Optional[str] = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # Always fall back to env var if no token passed
    tok = (token or "").strip() or os.getenv("GITHUB_TOKEN", "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


def _get(url: str, token: Optional[str] = None) -> Optional[dict]:
    """Make a GET request to GitHub API, return JSON or None on error."""
    try:
        resp = requests.get(url, headers=_github_headers(token), timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _get_file_content(
    owner: str, repo: str, path: str, token: Optional[str] = None
) -> Optional[str]:
    """Fetch a file from a GitHub repo and return its decoded text content."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    data = _get(url, token)
    if not data or "content" not in data:
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except Exception:
        return None


def _get_readme(owner: str, repo: str, token: Optional[str] = None) -> str:
    """Try common README filenames."""
    for name in ("README.md", "readme.md", "README.rst", "README.txt", "README"):
        content = _get_file_content(owner, repo, name, token)
        if content and len(content.strip()) > 50:
            return content[:6000]  # cap at 6K chars
    return ""


def _get_dep_file(owner: str, repo: str, token: Optional[str] = None) -> str:
    """Try to find a dependency file to infer tech stack."""
    candidates = [
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "package.json",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
        "Gemfile",
        "environment.yml",
    ]
    for name in candidates:
        content = _get_file_content(owner, repo, name, token)
        if content:
            return f"[{name}]\n{content[:2000]}"
    return ""


def _get_top_files(owner: str, repo: str, token: Optional[str] = None) -> list:
    """List top-level files/folders in the repo."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents"
    data = _get(url, token)
    if not data or not isinstance(data, list):
        return []
    return [item["name"] for item in data[:30]]


# PROFILE + REPO LISTING


def parse_github_url(github_url: str) -> Optional[str]:
    """Extract username from a GitHub profile URL."""
    github_url = github_url.strip().rstrip("/")
    # Handle: https://github.com/username or github.com/username
    match = re.search(r"github\.com/([a-zA-Z0-9\-_]+)/?$", github_url)
    if match:
        return match.group(1)
    # If they just typed a username
    if re.match(r"^[a-zA-Z0-9\-_]+$", github_url):
        return github_url
    return None


def get_user_repos(
    username: str, token: Optional[str] = None, max_repos: int = 30
) -> list:
    """
    Fetch all public repos for a user, sorted by last updated.
    Returns list of repo metadata dicts.
    """
    url = (
        f"https://api.github.com/users/{username}/repos"
        f"?sort=updated&direction=desc&per_page={max_repos}&type=owner"
    )
    data = _get(url, token)
    if not data or not isinstance(data, list):
        return []

    repos = []
    for r in data:
        # Skip forks and empty repos
        if r.get("fork") or r.get("size", 0) == 0:
            continue
        repos.append(
            {
                "name": r["name"],
                "full_name": r["full_name"],
                "description": r.get("description") or "",
                "language": r.get("language") or "",
                "topics": r.get("topics", []),
                "stars": r.get("stargazers_count", 0),
                "updated_at": r.get("updated_at", ""),
                "html_url": r.get("html_url", ""),
            }
        )
    return repos


# PER-REPO CONTENT GATHERING


def gather_repo_context(
    owner: str, repo_meta: dict, token: Optional[str] = None
) -> dict:
    """
    Collect all available context for a single repo.
    Returns a dict with everything Claude needs to write a project summary.
    """
    repo_name = repo_meta["name"]
    context = {**repo_meta}  # copy metadata

    # 1. README
    readme = _get_readme(owner, repo_name, token)
    context["readme"] = readme

    # 2. Dependency file (only if README is sparse)
    dep_file = ""
    if len(readme) < 300:
        dep_file = _get_dep_file(owner, repo_name, token)
    context["dep_file"] = dep_file

    # 3. Top-level file listing (always useful as a supplement)
    top_files = _get_top_files(owner, repo_name, token)
    context["top_files"] = top_files

    return context


# CLAUDE-POWERED PROJECT SUMMARIZATION


def summarize_repo_with_claude(repo_context: dict, client) -> dict:
    """
    Ask Claude to produce a structured project summary from all gathered context.
    Returns a dict suitable for use in resume generation.
    """
    import json

    readme_section = (
        f"README:\n{repo_context['readme']}"
        if repo_context["readme"]
        else "No README found."
    )
    dep_section = (
        f"\nDependency file:\n{repo_context['dep_file']}"
        if repo_context["dep_file"]
        else ""
    )
    files_section = (
        f"\nTop-level files/folders: {', '.join(repo_context['top_files'])}"
        if repo_context["top_files"]
        else ""
    )
    topics_section = (
        f"\nGitHub topics: {', '.join(repo_context['topics'])}"
        if repo_context["topics"]
        else ""
    )

    prompt = f"""You are a professional resume writer analyzing a GitHub repository.

Repo: {repo_context["name"]}
Primary language: {repo_context["language"]}
GitHub description: {repo_context["description"]}
Stars: {repo_context["stars"]}
{topics_section}
{files_section}
{dep_section}

{readme_section}

Based on all the above, produce a structured JSON summary of this project for a resume:
{{
  "name": "Clean project name (human-readable, not the repo slug)",
  "one_line": "One sentence describing what this project does",
  "tech_stack": ["list of specific technologies, libraries, frameworks used"],
  "category": "one of: ML/AI, LLM/Agentic AI, Data Science, Data Analysis, Web/Full-Stack, Backend, DevOps/MLOps, Computer Vision, NLP, Other",
  "keywords": ["10-15 resume keywords this project demonstrates"],
  "bullets": [
    "Strong resume bullet 1 — quantified if possible, action verb first",
    "Strong resume bullet 2",
    "Strong resume bullet 3"
  ],
  "is_relevant_for_tech": true or false
}}

Rules for bullets:
- Start with strong action verbs (Built, Engineered, Developed, Designed, Implemented, Trained, Deployed)
- Include numbers/metrics wherever the README mentions them
- Focus on what was built and why it matters, not just what technologies were used
- Keep each bullet under 200 characters

If this is a toy project, tutorial copy, or has no meaningful content, set is_relevant_for_tech to false.

Return only the JSON object. No markdown fences. No explanation."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = next((b.text for b in response.content if hasattr(b, "text")), "").strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
    except Exception:
        # Minimal fallback
        return {
            "name": repo_context["name"].replace("-", " ").replace("_", " ").title(),
            "one_line": repo_context["description"] or "No description available.",
            "tech_stack": [repo_context["language"]]
            if repo_context["language"]
            else [],
            "category": "Other",
            "keywords": repo_context["topics"],
            "bullets": [
                f"Developed {repo_context['name']} using {repo_context['language']}."
            ],
            "is_relevant_for_tech": bool(repo_context["language"]),
        }


# MAIN ENTRY POINT


def parse_github_profile(
    github_url: str,
    client,
    token: Optional[str] = None,
    max_repos: int = 100,
    progress_callback=None,
) -> dict:
    """
    Full pipeline: GitHub URL → list of structured project summaries.

    Args:
        github_url: GitHub profile URL or username
        client: Anthropic client instance
        token: GitHub personal access token (optional but recommended)
        max_repos: max repos to process
        progress_callback: optional function(message: str) for UI progress updates

    Returns:
        {
            "success": bool,
            "username": str,
            "profile_url": str,
            "projects": [list of summarized project dicts],
            "error": str | None,
        }
    """

    def log(msg):
        if progress_callback:
            progress_callback(msg)

    result = {
        "success": False,
        "username": "",
        "profile_url": "",
        "projects": [],
        "error": None,
    }

    # 1. Parse username
    username = parse_github_url(github_url)
    if not username:
        result["error"] = f"Could not extract a GitHub username from: {github_url}"
        return result

    result["username"] = username
    result["profile_url"] = f"https://github.com/{username}"
    log(f"Fetching repositories for @{username}...")

    # 2. Get repo list
    repos = get_user_repos(username, token, max_repos=max_repos)
    if not repos:
        result["error"] = (
            f"No public repositories found for @{username}, or the GitHub API rate limit was hit. "
            "Add a GITHUB_TOKEN to increase the rate limit."
        )
        return result

    log(f"Found {len(repos)} repositories. Analysing in parallel...")

    # 3. Gather context + summarize all repos concurrently
    # Parallelise with ThreadPoolExecutor — cuts ~3 min sequential → ~20 sec
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    # Thread-safe log
    log_lock = threading.Lock()
    counter = {"n": 0}

    def process_repo(repo_meta):
        context = gather_repo_context(username, repo_meta, token)
        summary = summarize_repo_with_claude(context, client)
        summary["github_url"] = repo_meta["html_url"]
        summary["repo_name"] = repo_meta["name"]
        with log_lock:
            counter["n"] += 1
            log(f"  [{counter['n']}/{len(repos)}] Done: {repo_meta['name']}")
        return summary

    projects = []
    # Cap concurrency at 8 to stay within Anthropic rate limits
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(process_repo, r): r for r in repos}
        for future in as_completed(futures):
            try:
                summary = future.result()
                if summary.get("is_relevant_for_tech", True):
                    projects.append(summary)
            except Exception as e:
                repo_name = futures[future].get("name", "?")
                log(f"  Warning: failed to process {repo_name}: {e}")

    result["success"] = True
    result["projects"] = projects
    log(f"Done. {len(projects)} relevant tech projects found.")
    return result
