"""
jd_parser.py
Fetches a job description from any URL and returns clean plain text.

Strategy:
  1. Try a simple requests + BeautifulSoup scrape (works for most public pages)
  2. Strip nav/header/footer boilerplate using heuristics
  3. Return the cleaned text for Claude to process

Works with: LinkedIn, Indeed, Greenhouse, Lever, Workday, Jobright,
            company career pages, and any other public job posting URL.
"""

import re

import requests
from bs4 import BeautifulSoup

from app.llm import LLMError

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# Sites that block server-side scraping and require login / JS rendering
_BLOCKED_DOMAINS = {
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "monster.com",
}


def _is_blocked_domain(url: str) -> bool:
    """Return True if the URL belongs to a site known to block scraping."""
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower().removeprefix("www.")
    return any(host == d or host.endswith("." + d) for d in _BLOCKED_DOMAINS)


# Tags whose content we always discard
NOISE_TAGS = {
    "script",
    "style",
    "noscript",
    "header",
    "footer",
    "nav",
    "aside",
    "form",
    "svg",
    "img",
    "button",
    "iframe",
}

# CSS classes / IDs that usually contain boilerplate (substring match)
NOISE_PATTERNS = [
    "nav",
    "menu",
    "header",
    "footer",
    "sidebar",
    "cookie",
    "banner",
    "advertisement",
    "social",
    "share",
    "related",
    "recommended",
    "signup",
    "login",
    "modal",
]


def _is_noisy(tag) -> bool:
    """Return True if a tag looks like navigation/boilerplate."""
    if not hasattr(tag, "attrs") or tag.attrs is None:
        return False
    for attr in ("class", "id"):
        val = tag.get(attr, "")
        if isinstance(val, list):
            val = " ".join(val)
        val = val.lower()
        if any(p in val for p in NOISE_PATTERNS):
            return True
    return False


def fetch_jd_text(url: str) -> dict:
    """
    Fetch a job description from a URL.

    Returns:
        {
            "success": bool,
            "url": str,
            "text": str,          # cleaned JD text (may be empty on failure)
            "error": str | None,  # error message if success=False
        }
    """
    result = {"success": False, "url": url, "text": "", "error": None}

    if _is_blocked_domain(url):
        result["error"] = (
            "This job board blocks automated access and requires login or JavaScript. "
            "Please copy and paste the job description text directly into the text box instead."
        )
        return result

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code in (401, 403, 999):
            result["error"] = (
                f"Access denied (HTTP {resp.status_code}). "
                "The job board requires login or blocks automated access. "
                "Please paste the job description text directly into the text box instead."
            )
            return result
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        result["error"] = "Request timed out. The page took too long to respond."
        return result
    except requests.exceptions.HTTPError as e:
        result["error"] = (
            f"HTTP error: {e}. "
            "Try pasting the job description text directly into the text box instead."
        )
        return result
    except requests.exceptions.RequestException as e:
        result["error"] = f"Could not reach URL: {e}"
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove obviously noisy tags entirely
    for tag in soup.find_all(NOISE_TAGS):
        tag.decompose()

    # Remove noisy elements by class/id
    for tag in soup.find_all(True):
        if _is_noisy(tag):
            tag.decompose()

    # Try known content containers first (platform-specific)
    content_selectors = [
        # Greenhouse
        {"id": "content"},
        # Lever
        {"class_": "content"},
        # LinkedIn
        {"class_": "description__text"},
        # Indeed
        {"id": "jobDescriptionText"},
        # Workday (handled separately below)
        # {"data-automation-id": "job-description"},
        # Jobright / generic
        {"class_": "job-description"},
        {"class_": "jobDescription"},
        {"class_": "job_description"},
        {"class_": "posting-description"},
    ]

    text = ""
    for sel in content_selectors:
        el = soup.find(**sel)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 200:
                break

    # Fallback: grab the largest <article> or <main> or <section>
    if len(text) < 200:
        for tag_name in ("article", "main", "section", "div"):
            candidates = soup.find_all(tag_name)
            if candidates:
                best = max(candidates, key=lambda t: len(t.get_text()))
                candidate_text = best.get_text(separator="\n", strip=True)
                if len(candidate_text) > len(text):
                    text = candidate_text
            if len(text) > 200:
                break

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip lines that are pure whitespace
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    # Collapse very long runs of repeated characters (e.g. "----...")
    text = re.sub(r"(.)\1{10,}", r"\1\1\1", text)

    if len(text) < 100:
        result["error"] = (
            "Could not extract meaningful text from this URL. "
            "The page may require login or JavaScript rendering. "
            "Try pasting the job description text directly instead."
        )
        return result

    result["success"] = True
    result["text"] = text[:15_000]  # cap at 15K chars — more than enough for any JD
    return result


def extract_jd_structured(jd_text: str, llm) -> dict:
    """
    Use Claude to extract structured data from raw JD text.

    Returns a dict with keys:
        job_title, company, location, job_type, required_skills,
        preferred_skills, responsibilities, qualifications, keywords
    """
    prompt = f"""You are a resume optimization assistant. Extract structured information from this job description.

Return a JSON object with exactly these keys:
{{
  "job_title": "string — the role title",
  "company": "string — company name",
  "location": "string — location or Remote",
  "job_type": "string — Full-time / Part-time / Contract / Internship",
  "required_skills": ["list of must-have technical skills mentioned"],
  "preferred_skills": ["list of nice-to-have skills mentioned"],
  "responsibilities": ["top 5-6 key responsibilities as short phrases"],
  "qualifications": ["top 4-5 qualifications/requirements"],
  "keywords": ["20-30 ATS keywords from the JD — tech terms, tools, methodologies"]
}}

Only return the JSON object, no markdown fences, no explanation.

JOB DESCRIPTION:
{jd_text}"""

    try:
        raw = llm.complete(prompt=prompt, max_tokens=2000).text
    except LLMError as e:
        raise RuntimeError(f"JD structured extraction failed: {e}") from e

    import json

    # Strip markdown fences if Claude added them despite instructions
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: return minimal structure with raw text
        return {
            "job_title": "Tech Role",
            "company": "Unknown",
            "location": "",
            "job_type": "",
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "qualifications": [],
            "keywords": [],
            "_raw_text": jd_text[:3000],
        }


if __name__ == "__main__":
    # Quick test
    test_url = "https://boards.greenhouse.io/anthropic/jobs/4020305008"
    print(f"Testing JD parser with: {test_url}\n")
    result = fetch_jd_text(test_url)
    if result["success"]:
        print(f"SUCCESS — extracted {len(result['text'])} characters")
        print("\n--- First 500 chars ---")
        print(result["text"][:500])
    else:
        print(f"FAILED: {result['error']}")
