"""
project_matcher.py
Uses Claude to:
  1. Select the 3-4 best PRODUCTION/DEPLOYED projects from GitHub for a given JD
     (prefers real systems over educational notebooks)
  2. Rewrite exactly 3 bullet points per project — highly quantified, JD-keyword-matched
  3. Generate a tailored skills section
  4. Light-touch rewrite of experience bullets
"""

import re
import json


def rank_projects_for_jd(
    jd_structured: dict,
    all_projects: list,
    client,
    top_n: int = 10,
) -> list:
    """
    Ask Claude to rank the top `top_n` most relevant projects for this JD.
    Returns a list of project dicts in ranked order (most relevant first),
    each with an added 'relevance_reason' field explaining why it was picked.
    """
    if not all_projects:
        return []

    # Pre-sort by production score to give Claude a good starting set
    sorted_projects = sorted(all_projects, key=_score_project, reverse=True)
    candidates = sorted_projects[: min(25, len(sorted_projects))]

    proj_summaries = json.dumps(
        [
            {
                "index": i,
                "name": p.get("name", ""),
                "one_line": p.get("one_line", ""),
                "category": p.get("category", ""),
                "tech_stack": p.get("tech_stack", [])[:8],
                "keywords": p.get("keywords", [])[:8],
            }
            for i, p in enumerate(candidates)
        ],
        indent=2,
    )

    jd_summary = json.dumps(
        {
            "job_title": jd_structured.get("job_title", ""),
            "company": jd_structured.get("company", ""),
            "required_skills": jd_structured.get("required_skills", []),
            "preferred_skills": jd_structured.get("preferred_skills", []),
            "keywords": jd_structured.get("keywords", [])[:20],
            "responsibilities": jd_structured.get("responsibilities", [])[:5],
        },
        indent=2,
    )

    prompt = f"""You are a resume expert ranking GitHub projects by relevance to a job description.

JOB DESCRIPTION:
{jd_summary}

CANDIDATE PROJECTS (indexed 0 to {len(candidates) - 1}):
{proj_summaries}

Rank the top {top_n} most relevant projects for this specific JD. Prefer:
- Production/deployed systems over notebooks or tutorials
- Projects whose tech stack overlaps with required/preferred skills
- Projects that demonstrate responsibilities mentioned in the JD
- Real working systems with clear impact

Return ONLY a JSON array of exactly {top_n} objects (no markdown, no explanation):
[
  {{"index": <original_index>, "relevance_reason": "1-sentence why this project fits this JD"}},
  ...
]
Ordered from most to least relevant."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = next((b.text for b in response.content if hasattr(b, "text")), "")
        raw = raw.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        ranked_refs = json.loads(raw)

        result = []
        for ref in ranked_refs[:top_n]:
            idx = ref.get("index", 0)
            if 0 <= idx < len(candidates):
                proj = dict(candidates[idx])
                proj["relevance_reason"] = ref.get("relevance_reason", "")
                result.append(proj)
        return result
    except Exception:
        # Fallback: return top-scored projects unchanged
        return candidates[:top_n]


# Projects that are clearly educational/tutorial — deprioritised
EDUCATIONAL_SIGNALS = [
    "basics",
    "fundamentals",
    "tutorial",
    "intro",
    "introduction",
    "learning",
    "course",
    "homework",
    "exercise",
    "notebook",
    "all-about",
    "dive-deeper",
    "core-algorithms",
    "leetcode",
    "data-preprocessing",
]


def _score_project(project: dict) -> int:
    """
    Heuristic score: higher = more production-worthy.
    Used to pre-sort before sending to Claude.
    """
    score = 0
    name_lower = project.get("name", "").lower()
    repo_lower = project.get("repo_name", "").lower()
    combined = name_lower + " " + repo_lower

    # Penalise educational signals
    if any(sig in combined for sig in EDUCATIONAL_SIGNALS):
        score -= 30

    # Reward deployment signals
    deployment_signals = [
        "deployed",
        "hugging face",
        "gradio",
        "fastapi",
        "flask",
        "docker",
        "mlflow",
        "production",
        "api",
        "dashboard",
        "agent",
        "mcp",
        "rag",
        "llm",
        "transformer",
    ]
    cat = project.get("category", "").lower()
    one_line = project.get("one_line", "").lower()
    bullets_text = " ".join(project.get("bullets", [])).lower()
    full_text = combined + " " + cat + " " + one_line + " " + bullets_text

    for sig in deployment_signals:
        if sig in full_text:
            score += 5

    # Reward categories
    if cat in ("llm/agentic ai", "mlops"):
        score += 20
    elif cat in ("ml/ai", "computer vision", "nlp"):
        score += 10
    elif cat == "web/full-stack":
        score += 5
    elif cat == "other":
        score -= 10

    # Reward stars
    score += project.get("stars", 0) * 2

    return score


def match_and_tailor(
    jd_structured: dict,
    resume_data: dict,
    confirmed_projects: list,
    client,
    num_projects: int = 4,
    bullets_per_project: int = 3,
) -> dict:
    """
    Core AI matching step.

    Args:
        jd_structured:      output from jd_parser.extract_jd_structured()
        resume_data:        output from resume_parser.parse_resume()
        confirmed_projects: list of project dicts the user confirmed (from github_parser)
        client:             Anthropic client
        num_projects:       how many projects to select (default 4)
        bullets_per_project: exactly how many bullets per project (default 3)

    Returns dict with keys:
        selected_projects, tailored_skills, tailored_experience,
        resume_title, ats_keywords_used, company, job_title
    """

    # Pre-sort: production projects first
    sorted_projects = sorted(confirmed_projects, key=_score_project, reverse=True)

    # Pass top 12 to Claude (enough signal, not overwhelming)
    projects_for_claude = sorted_projects[:12]

    projects_json = json.dumps(projects_for_claude, indent=2)
    jd_json = json.dumps(jd_structured, indent=2)
    resume_json = json.dumps(
        {
            "experience": resume_data.get("experience", []),
            "skills": resume_data.get("skills", []),
        },
        indent=2,
    )

    prompt = f"""You are an elite resume writer and ATS optimization specialist.

## JOB DESCRIPTION:
{jd_json}

## CANDIDATE PROJECTS (ranked by production-readiness — prefer ones higher in this list):
{projects_json}

## CANDIDATE EXPERIENCE & SKILLS:
{resume_json}

## YOUR STRICT RULES:

### PROJECT SELECTION
- Select exactly {num_projects} projects that best match the JD
- STRONGLY prefer projects that are deployed, have APIs, use production tools (Docker, MLflow, FastAPI, Gradio, HuggingFace Spaces), or are agentic AI systems
- AVOID selecting educational notebooks, tutorial repos, or "basics of X" projects unless there is genuinely no better option
- Prioritise projects whose tech stack overlaps with the JD's required_skills and keywords

### BULLET POINTS (CRITICAL)
- Write EXACTLY {bullets_per_project} bullet points per project — no more, no fewer
- Every bullet MUST start with a strong past-tense action verb (Built, Engineered, Developed, Designed, Implemented, Trained, Deployed, Achieved, Reduced, Improved)
- Every bullet MUST include at least one specific number, metric, or quantified result
  - If the README/summary has numbers, USE them (e.g., "47,515+ records", "66.1% accuracy", "50 tools", "657,035 training windows")
  - If no numbers exist, use meaningful proxies: "reduced inference latency by ~40%", "processed 10K+ data points", "cut manual review time by 3x"
- Weave in the JD's EXACT keywords and terminology naturally (not forced)
- Keep each bullet under 230 characters
- No bullet should be generic — every bullet must be specific to THIS project

### SKILLS SECTION
- Create 4-5 skill categories
- Include only skills the candidate demonstrably has (from projects + experience)
- Prioritise skills the JD explicitly mentions
- Do NOT invent skills not evidenced in their background

### EXPERIENCE BULLETS
- Light touch only — rewrite 1-2 bullets per role to mirror JD language
- Never fabricate accomplishments

### RESUME TITLE
- Use the JD's exact job title or the closest professional equivalent

Return a JSON object with EXACTLY this structure:
{{
  "job_title": "exact job title from JD",
  "company": "company name from JD",
  "resume_title": "title to show on resume header",
  "selected_projects": [
    {{
      "name": "project name",
      "tech_stack": ["tech1", "tech2", "tech3"],
      "bullets": ["bullet 1", "bullet 2", "bullet 3"],
      "github_url": "url if available"
    }}
  ],
  "tailored_skills": {{
    "Category Name": "Skill1, Skill2, Skill3",
    "Category Name 2": "Skill4, Skill5"
  }},
  "tailored_experience": [
    {{
      "company": "...",
      "title": "...",
      "dates": "...",
      "location": "...",
      "bullets": ["bullet 1", "bullet 2", "bullet 3"]
    }}
  ],
  "ats_keywords_used": ["keyword1", "keyword2"]
}}

Return ONLY the JSON. No markdown fences. No explanation."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = next((b.text for b in response.content if hasattr(b, "text")), "")
        raw = raw.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)

        # Enforce bullet count
        for proj in result.get("selected_projects", []):
            bullets = proj.get("bullets", [])
            if len(bullets) > bullets_per_project:
                proj["bullets"] = bullets[:bullets_per_project]
            elif len(bullets) < bullets_per_project:
                while len(proj["bullets"]) < bullets_per_project:
                    proj["bullets"].append(
                        bullets[-1] if bullets else "Developed core functionality."
                    )

        return result

    except Exception as e:
        return {
            "job_title": jd_structured.get("job_title", "Software Engineer"),
            "company": jd_structured.get("company", ""),
            "resume_title": jd_structured.get("job_title", "Software Engineer"),
            "selected_projects": confirmed_projects[:num_projects],
            "tailored_skills": {},
            "tailored_experience": resume_data.get("experience", []),
            "ats_keywords_used": [],
            "_error": str(e),
        }
