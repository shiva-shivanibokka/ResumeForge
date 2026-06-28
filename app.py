"""
ResumeForge — app.py

3-step flow:
  Step 1 — Analyse     : JD URL (small) + resume upload (small) on same row,
                         JD text paste full-width below, then Analyse button
  Step 2 — Configure   : GitHub, LinkedIn, page length, fonts
  Step 3 — Generate    : resume + scores + preview + download + edit + cover letter

UI: pill/bubble section headings, soft corners, no hard-coded colours.
Run: python app.py
"""

import os, base64, re, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

import gradio as gr
import anthropic

from jd_parser import fetch_jd_text, extract_jd_structured
from resume_parser import parse_resume
from github_parser import parse_github_profile
from project_matcher import match_and_tailor
from resume_builder import build_resume, FontConfig, AVAILABLE_FONTS
from scorer import (
    score_resume,
    extract_resume_text,
    score_card_markdown,
    quick_gap_analysis,
    gap_analysis_markdown,
)
from cover_letter import (
    generate_cover_letter_text,
    build_cover_letter_docx,
    revise_cover_letter,
)
from project_matcher import rank_projects_for_jd

EMPTY_STATE = {
    "jd_structured": None,
    "jd_raw": "",
    "resume_data": None,
    "resume_raw_text": "",
    "all_projects": [],
    "matched_payload": None,
    "linkedin_url": "",
    "github_url": "",
    "last_docx_path": None,
    "last_pdf_path": None,
    "log_lines": [],
    "gap_data": None,
    "selected_keywords": [],
}



def _get_client(api_key=""):
    key = (api_key or "").strip() or os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError(
            "Anthropic API key not found. Add ANTHROPIC_API_KEY to .env or paste in Settings."
        )
    return anthropic.Anthropic(api_key=key)


def _https(url):
    url = (url or "").strip()
    return ("https://" + url) if url and not url.startswith("http") else url


def _log(state, *msgs):
    for m in msgs:
        state["log_lines"].append(str(m))


def _pdf_iframe(pdf_path):
    """
    Embed the PDF for inline preview.
    Gradio 6 serves files from allowed_paths via /gradio_api/file= endpoint.
    We encode as base64 as fallback but primarily use the file URL.
    """
    if not pdf_path or not Path(pdf_path).exists():
        return ""
    try:
        # Use Gradio's file serving endpoint — works when allowed_paths includes tempdir
        # Encode path for URL safety
        import urllib.parse

        encoded = urllib.parse.quote(str(Path(pdf_path).as_posix()), safe="/:")
        file_url = f"/gradio_api/file={encoded}"
        return (
            f'<iframe src="{file_url}" '
            f'width="100%" height="1050px" '
            f'style="border:1px solid #555;border-radius:8px;margin-top:0.5rem">'
            f"</iframe>"
        )
    except Exception as e:
        return f"Preview error: {e}"


def _safe_float(v):
    """Convert font size input to float or None — avoids Gradio's 0-value issue."""
    try:
        f = float(v)
        return f if f > 0 else None
    except Exception:
        return None




def step1_analyse(jd_url, jd_text_paste, resume_file, api_key, state):
    state = dict(state)
    state["log_lines"] = []
    log = lambda *m: _log(state, *m)

    try:
        client = _get_client(api_key)
    except ValueError as e:
        return (
            str(e),
            "",
            gr.CheckboxGroup(choices=[], value=[]),
            gr.CheckboxGroup(choices=[], value=[]),
            "\n".join(state["log_lines"]),
            state,
            gr.update(visible=False),
        )

    # JD
    jd_raw = ""
    if (jd_url or "").strip():
        log(f"Fetching JD: {jd_url.strip()}")
        r = fetch_jd_text(jd_url.strip())
        if r["success"]:
            jd_raw = r["text"]
            log(f"  Extracted {len(jd_raw):,} chars.")
        else:
            log(f"  URL failed: {r['error']}")
    if not jd_raw and (jd_text_paste or "").strip():
        jd_raw = jd_text_paste.strip()
        log(f"Using pasted JD ({len(jd_raw):,} chars).")
    if not jd_raw:
        return (
            "❌ Provide a job URL or paste the JD text.",
            "",
            gr.CheckboxGroup(choices=[], value=[]),
            gr.CheckboxGroup(choices=[], value=[]),
            "\n".join(state["log_lines"]),
            state,
            gr.update(visible=False),
        )

    log("Parsing JD with Claude...")
    jd_structured = extract_jd_structured(jd_raw, client)
    state["jd_structured"] = jd_structured
    state["jd_raw"] = jd_raw
    log(
        f"  {jd_structured.get('job_title', '?')} @ {jd_structured.get('company', '?')}"
    )

    # Resume
    if not resume_file:
        return (
            "❌ Upload your resume (PDF or .docx).",
            "",
            gr.CheckboxGroup(choices=[], value=[]),
            gr.CheckboxGroup(choices=[], value=[]),
            "\n".join(state["log_lines"]),
            state,
            gr.update(visible=False),
        )

    log(f"Parsing resume: {Path(resume_file).name}")
    resume_data = parse_resume(resume_file, client)
    if resume_data.get("error"):
        log(f"  Warning: {resume_data['error']}")
    state["resume_data"] = resume_data
    state["resume_raw_text"] = resume_data.get("raw_text", "")
    log(
        f"  {resume_data.get('name', '?')} — {len(resume_data.get('experience', []))} exp, {len(resume_data.get('education', []))} edu"
    )

    # Gap analysis
    log("Running keyword gap analysis...")
    gap = quick_gap_analysis(jd_raw, state["resume_raw_text"], client)
    state["gap_data"] = gap
    if gap.get("error"):
        log(f"  Warning: {gap['error']}")
    else:
        log(
            f"  Missing required: {len(gap.get('required_missing', []))}  Missing preferred: {len(gap.get('preferred_missing', []))}"
        )

    gap_md = gap_analysis_markdown(gap)

    req_choices = [
        f"{i['keyword']} — {i.get('explanation', '')[:80]}"
        for i in gap.get("required_missing", [])
    ]
    pref_choices = [
        f"{i['keyword']} — {i.get('explanation', '')[:80]}"
        for i in gap.get("preferred_missing", [])
    ]

    job = f"{jd_structured.get('job_title', '?')} @ {jd_structured.get('company', '?')}"
    status = f"✅ Analysed: **{job}** — review gaps below and select keywords to add, then complete Step 2"

    return (
        status,
        gap_md,
        gr.CheckboxGroup(
            choices=req_choices,
            value=req_choices,
            label="Required / Critical Keywords",
            info="Pre-selected. Uncheck any you don't want added to your resume.",
        ),
        gr.CheckboxGroup(
            choices=pref_choices,
            value=pref_choices,
            label="Preferred / Nice-to-Have Keywords",
            info="Pre-selected. Uncheck any you don't want added.",
        ),
        "\n".join(state["log_lines"]),
        state,
        gr.update(visible=True),
    )




def step2b_fetch_projects(github_url, linkedin_url, gh_token, api_key, state):
    """
    Fetch GitHub repos, rank top 10 by JD relevance.
    Returns a CheckboxGroup for user selection.
    Outputs: status_md, project_checkboxes, log_display, app_state
    """
    state = dict(state)
    state["log_lines"] = list(state.get("log_lines", []))
    log = lambda *m: _log(state, *m)

    jd_structured = state.get("jd_structured")
    resume_data = state.get("resume_data")

    def _err(msg):
        return (
            msg,
            gr.CheckboxGroup(choices=[], value=[]),
            "\n".join(state["log_lines"]),
            state,
        )

    if not jd_structured or not resume_data:
        return _err("Complete Step 1 (Analyse) first.")

    try:
        client = _get_client(api_key)
    except ValueError as e:
        return _err(str(e))

    # Store URLs
    li = (
        _https(linkedin_url)
        if (linkedin_url or "").strip()
        else _https(resume_data.get("linkedin", ""))
    )
    gh = _https(github_url) if (github_url or "").strip() else ""
    state["linkedin_url"] = li
    state["github_url"] = gh
    resume_data = dict(resume_data)
    if li:
        resume_data["linkedin_url"] = li
        resume_data["linkedin"] = "LinkedIn"
    if gh:
        resume_data["github_url"] = gh
        resume_data["github"] = "GitHub"
    state["resume_data"] = resume_data

    if not gh:
        return _err("Enter your GitHub profile URL.")

    log(f"Analysing GitHub: {gh}")
    token = (gh_token or "").strip() or None
    gh_result = parse_github_profile(
        gh, client, token=token, max_repos=100, progress_callback=log
    )
    if not gh_result["success"]:
        return _err(f"GitHub parsing failed: {gh_result['error']}")

    all_projects = gh_result["projects"]
    state["all_projects"] = all_projects
    log(f"Found {len(all_projects)} repos. Ranking top 10 for this JD...")

    ranked = rank_projects_for_jd(jd_structured, all_projects, client, top_n=10)
    state["ranked_projects"] = ranked
    log(f"Top 10 ranked. Select at least 3 to include in your resume.")

    choices = [
        f"{p['name']} — {p.get('relevance_reason', p.get('one_line', ''))[:90]}"
        for p in ranked
    ]
    # Pre-select top 4 by default
    default_selected = choices[:4]

    return (
        f"Found **{len(all_projects)} repos** — ranked top 10 by JD relevance below. Select at least 3.",
        gr.CheckboxGroup(
            choices=choices,
            value=default_selected,
            label="Select projects to include (min 3)",
            info="Top 10 most relevant to this JD. Pre-selected: top 4. Check/uncheck freely.",
        ),
        "\n".join(state["log_lines"]),
        state,
    )




def step3_generate(
    req_selected,
    pref_selected,
    project_selection,
    page_option,
    api_key,
    body_font,
    state,
):
    state = dict(state)
    state["log_lines"] = list(state.get("log_lines", []))
    log = lambda *m: _log(state, *m)

    jd_structured = state.get("jd_structured")
    resume_data = state.get("resume_data")
    jd_raw = state.get("jd_raw", "")
    ranked_projects = state.get("ranked_projects", [])

    def _err(msg):
        return (msg, None, None, "", "", "\n".join(state["log_lines"]), state)

    if not jd_structured:
        return _err("Complete Step 1 first.")
    if not resume_data:
        return _err("Upload your resume in Step 1.")
    if not ranked_projects:
        return _err("Fetch GitHub projects first (click 'Fetch & Rank Projects').")

    # Validate project selection
    selected_projects = []
    for label in project_selection or []:
        proj_name = label.split("—")[0].strip()
        for p in ranked_projects:
            if p.get("name", "").strip() == proj_name:
                selected_projects.append(p)
                break
    if len(selected_projects) < 3:
        return _err(
            f"Select at least 3 projects (you selected {len(selected_projects)})."
        )

    try:
        client = _get_client(api_key)
    except ValueError as e:
        return _err(str(e))

    # Keywords
    selected_keywords = []
    for label in (req_selected or []) + (pref_selected or []):
        kw = label.split("—")[0].strip() if "—" in label else label.strip()
        if kw:
            selected_keywords.append(kw)
    state["selected_keywords"] = selected_keywords
    if selected_keywords:
        jd_structured = dict(jd_structured)
        jd_structured["required_skills"] = list(
            dict.fromkeys(selected_keywords + jd_structured.get("required_skills", []))
        )

    log(f"Matching {len(selected_projects)} selected projects to JD...")
    matched = match_and_tailor(
        jd_structured,
        resume_data,
        selected_projects,
        client,
        num_projects=min(4, len(selected_projects)),
        bullets_per_project=3,
    )
    state["matched_payload"] = matched
    if matched.get("_error"):
        log(f"Warning: {matched['_error']}")
    log(
        f"Projects selected: {[p['name'] for p in matched.get('selected_projects', [])]}"
    )

    # Build with auto-fill font sizing
    one_page = page_option != "2-Page Resume"
    fc = FontConfig(
        body_font=body_font or "Calibri",
        name_font=body_font or "Calibri",
        heading_font=body_font or "Calibri",
    )
    log(
        f"Building {'1-page' if one_page else '2-page'} A4 with auto-fill font sizing..."
    )

    result = build_resume(
        personal=resume_data,
        education=resume_data.get("education", []),
        matched_payload=matched,
        output_dir=None,
        to_pdf=True,
        one_page=one_page,
        font_config=fc,
        auto_fill=one_page,  # auto-fill only for 1-page
    )
    if result.get("font_config_used"):
        fc_used = result["font_config_used"]
        log(
            f"  Auto-fit: body={fc_used.get('body_size')}pt  heading={fc_used.get('heading_size')}pt  name={fc_used.get('name_size')}pt"
        )
    if result.get("error"):
        log(f"Note: {result['error']}")

    docx_path = result.get("docx_path")
    pdf_path = result.get("pdf_path")
    state["last_docx_path"] = docx_path
    state["last_pdf_path"] = pdf_path

    if not docx_path:
        return _err("Build failed — see Logs tab.")

    log("Scoring...")
    scores = score_resume(extract_resume_text(docx_path), jd_raw, client)
    scores_md = score_card_markdown(scores)
    log(
        f"  ATS: {scores.get('ats_score', 0)}/10  Match: {scores.get('match_score', 0)}/10"
    )
    log("Done!")

    job_label = f"{matched.get('job_title', '')} @ {matched.get('company', '')}"
    status = f"Resume ready: **{job_label}**"
    preview = _pdf_iframe(pdf_path)

    return (
        status,
        docx_path,
        pdf_path,
        preview,
        scores_md,
        "\n".join(state["log_lines"]),
        state,
    )




def run_edit(edit_instructions, page_option, api_key, body_font, state):
    state = dict(state)
    state["log_lines"] = list(state.get("log_lines", []))
    log = lambda *m: _log(state, *m)

    matched_payload = state.get("matched_payload")
    resume_data = state.get("resume_data")
    jd_raw = state.get("jd_raw", "")

    def _err(msg):
        return (msg, None, None, "", "", "\n".join(state["log_lines"]), state)

    if not matched_payload:
        return _err("Generate the resume first.")
    if not (edit_instructions or "").strip():
        return _err("Enter edit instructions.")

    try:
        client = _get_client(api_key)
    except ValueError as e:
        return _err(str(e))

    log(f"Applying edits: {edit_instructions[:200]}")
    prompt = f"""You are a professional resume editor.
Apply ONLY the requested edits. Do not change anything not mentioned.

CURRENT PAYLOAD:
{json.dumps(matched_payload, indent=2)[:6000]}

EDIT INSTRUCTIONS:
{edit_instructions}

Return the complete updated JSON payload. Same structure. No markdown fences. No explanation."""

    try:
        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        updated = json.loads(raw)
        state["matched_payload"] = updated
        log("Edits applied.")
    except Exception as e:
        log(f"Edit parse failed: {e}")
        updated = matched_payload

    one_page = page_option != "2-Page Resume"
    fc = FontConfig(
        body_font=body_font or "Calibri",
        name_font=body_font or "Calibri",
        heading_font=body_font or "Calibri",
    )
    result = build_resume(
        personal=resume_data,
        education=resume_data.get("education", []),
        matched_payload=updated,
        output_dir=None,
        to_pdf=True,
        one_page=one_page,
        font_config=fc,
        auto_fill=one_page,
    )
    if result.get("error"):
        log(f"Note: {result['error']}")

    docx_path = result.get("docx_path")
    pdf_path = result.get("pdf_path")
    state["last_docx_path"] = docx_path
    state["last_pdf_path"] = pdf_path

    scores_md = ""
    if docx_path and jd_raw:
        scores = score_resume(extract_resume_text(docx_path), jd_raw, client)
        scores_md = score_card_markdown(scores)
        log(
            f"Re-scored — ATS:{scores.get('ats_score', 0)}/10 Match:{scores.get('match_score', 0)}/10"
        )

    log("Rebuild complete.")
    return (
        "Resume updated.",
        docx_path,
        pdf_path,
        _pdf_iframe(pdf_path) if pdf_path else "",
        scores_md,
        "\n".join(state["log_lines"]),
        state,
    )




def run_cover_letter(tone, extra_instructions, api_key, state):
    """Generate cover letter → docx + pdf + preview."""
    state = dict(state)
    state["log_lines"] = list(state.get("log_lines", []))
    log = lambda *m: _log(state, *m)

    jd_structured = state.get("jd_structured")
    resume_data = state.get("resume_data")
    matched_payload = state.get("matched_payload")
    selected_kws = state.get("selected_keywords", [])

    # Returns: status, docx, pdf, preview_html, log, state
    def _err(msg):
        return (msg, None, None, "", "\n".join(state["log_lines"]), state)

    if not jd_structured or not resume_data:
        return _err("Complete Step 1 first.")
    if not matched_payload:
        return _err("Generate the resume first (Step 3).")

    try:
        client = _get_client(api_key)
    except ValueError as e:
        return _err(str(e))

    log(f"Generating {tone} cover letter...")
    try:
        letter_text = generate_cover_letter_text(
            jd_structured=jd_structured,
            resume_data=resume_data,
            matched_payload=matched_payload,
            selected_keywords=selected_kws,
            tone=tone,
            client=client,
            extra_instructions=(extra_instructions or "").strip(),
        )
        log("Cover letter generated.")
    except Exception as e:
        return _err(f"Failed: {e}")

    state["cover_letter_text"] = letter_text
    cl_result = build_cover_letter_docx(letter_text, resume_data, jd_structured)
    if cl_result.get("error"):
        log(f"Note: {cl_result['error']}")
    if cl_result.get("pdf_error"):
        log(f"PDF note: {cl_result['pdf_error']}")

    state["cl_docx_path"] = cl_result.get("docx_path")
    state["cl_pdf_path"] = cl_result.get("pdf_path")

    log("Done.")
    preview = (
        _pdf_iframe(cl_result.get("pdf_path")) if cl_result.get("pdf_path") else ""
    )
    return (
        "Cover letter ready — download below.",
        cl_result.get("docx_path"),
        cl_result.get("pdf_path"),
        preview,
        "\n".join(state["log_lines"]),
        state,
    )


def run_cover_letter_edit(cl_edit_instructions, api_key, state):
    """Apply edits to existing cover letter."""
    state = dict(state)
    state["log_lines"] = list(state.get("log_lines", []))
    log = lambda *m: _log(state, *m)

    letter_text = state.get("cover_letter_text", "")
    jd_structured = state.get("jd_structured", {})
    resume_data = state.get("resume_data", {})

    def _err(msg):
        return (msg, None, None, "", "\n".join(state["log_lines"]), state)

    if not letter_text:
        return _err("Generate a cover letter first.")
    if not (cl_edit_instructions or "").strip():
        return _err("Enter edit instructions.")

    try:
        client = _get_client(api_key)
    except ValueError as e:
        return _err(str(e))

    log(f"Applying cover letter edits: {cl_edit_instructions[:150]}")
    try:
        updated_text = revise_cover_letter(
            letter_text, cl_edit_instructions, jd_structured, resume_data, client
        )
        state["cover_letter_text"] = updated_text
        log("Edits applied.")
    except Exception as e:
        log(f"Edit failed: {e}")
        updated_text = letter_text

    cl_result = build_cover_letter_docx(updated_text, resume_data, jd_structured)
    if cl_result.get("error"):
        log(f"Note: {cl_result['error']}")

    state["cl_docx_path"] = cl_result.get("docx_path")
    state["cl_pdf_path"] = cl_result.get("pdf_path")

    log("Done.")
    preview = (
        _pdf_iframe(cl_result.get("pdf_path")) if cl_result.get("pdf_path") else ""
    )
    return (
        "Cover letter updated.",
        cl_result.get("docx_path"),
        cl_result.get("pdf_path"),
        preview,
        "\n".join(state["log_lines"]),
        state,
    )

    log("Done.")
    return (
        "Cover letter ready — download above, preview below.",
        cl_result.get("docx_path"),  # gr.File accepts plain path
        letter_text,
        "\n".join(state["log_lines"]),
        state,
    )


# Pill/bubble step headings, soft card borders, better spacing.
# No hardcoded background colours — uses Gradio's CSS variables for dark-mode safety.

CSS = """
body, .gradio-container { font-size: 15px !important; font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important; }

#rf-title {
    font-size: 2.6rem !important; font-weight: 900 !important;
    text-align: center; letter-spacing: -1px; margin-bottom: 0.2rem !important;
}
#rf-sub { text-align: center; font-size: 1.05rem; margin-bottom: 1.4rem; }

.step-pill p, .step-pill {
    display: inline-block !important;
    padding: 0.4rem 1.3rem !important;
    border-radius: 999px !important;
    border: 2px solid var(--color-accent, #6366f1) !important;
    background: var(--color-accent-soft, rgba(99,102,241,0.08)) !important;
    font-size: 1.05rem !important; font-weight: 800 !important;
    margin: 1.2rem 0 0.6rem !important; letter-spacing: 0.01em;
}

input, textarea, select,
.block, .gr-box, .gr-form,
.svelte-1p9xokt, [data-testid="textbox"] > label > div {
    border-radius: 10px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
    transition: box-shadow 0.2s ease, border-color 0.2s ease !important;
}
input:focus, textarea:focus, select:focus {
    box-shadow: 0 4px 16px rgba(99,102,241,0.18) !important;
    outline: none !important;
}

select, .gr-dropdown select,
ul.options { border-radius: 10px !important; }

button.primary { border-radius: 10px !important; font-weight: 700 !important; font-size: 1rem !important; letter-spacing: 0.02em; box-shadow: 0 3px 10px rgba(99,102,241,0.25) !important; }
button.secondary { border-radius: 10px !important; font-weight: 600 !important; }
button:hover { transform: translateY(-1px); box-shadow: 0 5px 16px rgba(99,102,241,0.3) !important; }

.accordion { border-radius: 12px !important; }

.gr-group, .gradio-group { border-radius: 14px !important; box-shadow: 0 2px 12px rgba(0,0,0,0.06) !important; }

label > span:first-child { font-size: 0.93rem !important; font-weight: 700 !important; }
.gr-info { font-size: 0.8rem !important; }

.gr-checkbox-group .gr-checkbox { border-radius: 6px !important; }

.gr-radio label { border-radius: 8px !important; padding: 0.35rem 0.7rem !important; }
.gr-radio label:has(input:checked) { background: var(--color-accent-soft, rgba(99,102,241,0.12)) !important; }

.tab-nav button { font-size: 1rem !important; font-weight: 700 !important; border-radius: 8px 8px 0 0 !important; }

#log-box textarea { font-family: 'Courier New', monospace !important; font-size: 0.8rem !important; border-radius: 10px !important; }

.file-preview { border-radius: 10px !important; }

h1, h2, h3 { letter-spacing: -0.3px; }

hr { margin: 1rem 0 !important; }
"""



THEME = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="purple",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace"],
)

with gr.Blocks(title="ResumeForge") as demo:
    app_state = gr.State(EMPTY_STATE)

    gr.Markdown("# ResumeForge", elem_id="rf-title")
    gr.Markdown("AI-powered tailored resumes for any tech role", elem_id="rf-sub")

    with gr.Tabs(elem_classes=["tab-nav"]):
        # TAB 1 — BUILD & PREVIEW
        with gr.Tab("Build & Preview"):
            # Settings
            with gr.Accordion("⚙ API Keys & Settings", open=False):
                with gr.Row():
                    api_key_input = gr.Textbox(
                        label="Anthropic API Key",
                        placeholder="sk-ant-... (or set in .env)",
                        type="password",
                    )
                    gh_token_input = gr.Textbox(
                        label="GitHub Personal Access Token",
                        placeholder="ghp_... (or set GITHUB_TOKEN in .env)",
                        type="password",
                        info="Read-only public repos. Raises API rate limit to 5,000/hr.",
                    )

            gr.Markdown(
                "### Step 1 — Analyse Job Description & Resume",
                elem_classes=["step-pill"],
            )

            # Row: JD URL (left, compact) + Resume upload (right, compact)
            with gr.Row(equal_height=True):
                jd_url_input = gr.Textbox(
                    label="Job Posting URL",
                    placeholder="Paste any job link — Jobright, LinkedIn, Greenhouse, Indeed…",
                    scale=3,
                )
                resume_upload = gr.File(
                    label="Upload Resume (PDF or .docx)",
                    file_types=[".pdf", ".docx", ".doc"],
                    scale=2,
                )

            # JD text — full width below
            jd_text_input = gr.Textbox(
                label="Or paste JD text directly (fallback if URL fails)",
                placeholder="Paste the full job description here…",
                lines=4,
            )

            analyse_btn = gr.Button("Analyse JD + Resume", variant="primary", size="lg")
            analyse_status = gr.Markdown("")

            gr.Markdown("---")
            gr.Markdown("#### Keyword Gap Analysis")
            gr.Markdown(
                "*Results appear here after clicking Analyse. Select keywords you want woven into your resume.*",
                elem_classes=["section-label"],
            )
            gap_display = gr.Markdown("")

            with gr.Row():
                with gr.Column():
                    req_checkboxes = gr.CheckboxGroup(
                        choices=[],
                        value=[],
                        label="Required / Critical Keywords",
                        info="Pre-selected. Uncheck any you don't want added.",
                    )
                with gr.Column():
                    pref_checkboxes = gr.CheckboxGroup(
                        choices=[],
                        value=[],
                        label="Preferred / Nice-to-Have Keywords",
                        info="Pre-selected. Uncheck any you don't want added.",
                    )

            gr.Markdown("---")

            # IMPORTANT: gr.Column(visible=False) is used — NOT gr.Group.
            # gr.Group with visible=False breaks button event registration in Gradio 6.
            with gr.Column(visible=False) as step2_group:
                gr.Markdown(
                    "### Step 2 — Profile Links & Settings", elem_classes=["step-pill"]
                )
                with gr.Row():
                    linkedin_input = gr.Textbox(
                        label="LinkedIn URL",
                        placeholder="https://linkedin.com/in/your-profile",
                        info="Clickable link in resume header",
                        scale=2,
                    )
                    github_url_input = gr.Textbox(
                        label="GitHub Profile URL",
                        placeholder="https://github.com/your-username",
                        info="Agent reads your public repos",
                        scale=2,
                    )
                    page_option = gr.Radio(
                        choices=["1-Page Resume", "2-Page Resume"],
                        value="1-Page Resume",
                        label="Resume Length",
                        scale=1,
                    )

                with gr.Accordion(
                    "Font (optional — default: Calibri, auto-sized)", open=False
                ):
                    gr.Markdown(
                        "Font sizes are **automatically calculated** to fill the page. You only choose the font family."
                    )
                    body_font_dd = gr.Dropdown(
                        choices=AVAILABLE_FONTS,
                        value="Calibri",
                        label="Resume Font",
                        info="Applied to name, headings, and body with proportional scaling",
                    )

                gr.Markdown("---")

                gr.Markdown(
                    "### Step 2b — Fetch & Rank Projects", elem_classes=["step-pill"]
                )
                gr.Markdown(
                    "Agent reads your GitHub repos and ranks the **top 10 most relevant** to this JD. Select at least 3."
                )
                fetch_projects_btn = gr.Button(
                    "Fetch & Rank Projects from GitHub", variant="primary"
                )
                fetch_projects_status = gr.Markdown("")

                project_checkboxes = gr.CheckboxGroup(
                    choices=[],
                    value=[],
                    label="Top 10 Relevant Projects (select at least 3)",
                    info="Ranked by relevance to the JD. Pre-selected: top 4. Change freely.",
                )

                gr.Markdown("---")

                gr.Markdown("### Step 3 — Generate Resume", elem_classes=["step-pill"])
                generate_btn = gr.Button(
                    "Generate Tailored Resume", variant="primary", size="lg"
                )
                generate_status = gr.Markdown("")

                gr.Markdown("---")
                gr.Markdown("#### Resume Scores")
                scores_display = gr.Markdown("")

                gr.Markdown("---")
                gr.Markdown("#### Preview")
                preview_html = gr.HTML("")

                gr.Markdown("---")
                gr.Markdown("#### Download")
                with gr.Row():
                    docx_out = gr.File(label="Word Document (.docx)", interactive=False)
                    pdf_out = gr.File(label="PDF (.pdf)", interactive=False)

                gr.Markdown("---")

                with gr.Accordion("Request Edits to Resume", open=False):
                    gr.Markdown(
                        "Describe changes in plain English. Claude revises and rebuilds."
                    )
                    edit_input = gr.Textbox(
                        label="Edit Instructions",
                        placeholder="'Swap project 1 for Sepsis ML'  |  'Make bullets more concise'  |  'Emphasise RAG more'",
                        lines=3,
                    )
                    edit_btn = gr.Button("Apply Edits & Rebuild", variant="secondary")
                    edit_status = gr.Markdown("")

                gr.Markdown("---")

                with gr.Accordion("Generate Cover Letter", open=False):
                    gr.Markdown(
                        "Personalised cover letter from your resume, JD, and selected keywords. Generate the resume first."
                    )
                    with gr.Row():
                        cl_tone = gr.Radio(
                            choices=["Professional", "Conversational", "Concise"],
                            value="Professional",
                            label="Tone",
                            scale=1,
                        )
                        cl_extra = gr.Textbox(
                            label="Additional instructions (optional)",
                            placeholder="e.g. 'Mention my interest in AI for construction', 'Keep under 250 words'",
                            lines=2,
                            scale=3,
                        )
                    cl_btn = gr.Button("Generate Cover Letter", variant="secondary")
                    cl_status = gr.Markdown("")

                    gr.Markdown("---")
                    gr.Markdown("#### Cover Letter Preview")
                    cl_preview_html = gr.HTML("")

                    gr.Markdown("#### Download Cover Letter")
                    with gr.Row():
                        cl_docx_out = gr.File(label="Word (.docx)", interactive=False)
                        cl_pdf_out = gr.File(label="PDF (.pdf)", interactive=False)

                    gr.Markdown("---")
                    with gr.Accordion("Edit Cover Letter", open=False):
                        gr.Markdown(
                            "Describe changes and Claude will rewrite the cover letter."
                        )
                        cl_edit_input = gr.Textbox(
                            label="Cover Letter Edit Instructions",
                            placeholder="'Make it more concise'  |  'Add enthusiasm about the AI product work'  |  'Remove the last paragraph'",
                            lines=3,
                        )
                        cl_edit_btn = gr.Button("Apply Edits", variant="secondary")
                        cl_edit_status = gr.Markdown("")

        # TAB 2 — LOGS
        with gr.Tab("Logs"):
            gr.Markdown("Full pipeline activity log from the last run.")
            log_display = gr.Textbox(
                label="Activity Log", lines=35, interactive=False, elem_id="log-box"
            )
            clear_btn = gr.Button("Clear", size="sm")


    analyse_btn.click(
        fn=step1_analyse,
        inputs=[jd_url_input, jd_text_input, resume_upload, api_key_input, app_state],
        outputs=[
            analyse_status,
            gap_display,
            req_checkboxes,
            pref_checkboxes,
            log_display,
            app_state,
            step2_group,
        ],
    )

    fetch_projects_btn.click(
        fn=step2b_fetch_projects,
        inputs=[
            github_url_input,
            linkedin_input,
            gh_token_input,
            api_key_input,
            app_state,
        ],
        outputs=[fetch_projects_status, project_checkboxes, log_display, app_state],
    )

    generate_btn.click(
        fn=step3_generate,
        inputs=[
            req_checkboxes,
            pref_checkboxes,
            project_checkboxes,
            page_option,
            api_key_input,
            body_font_dd,
            app_state,
        ],
        outputs=[
            generate_status,
            docx_out,
            pdf_out,
            preview_html,
            scores_display,
            log_display,
            app_state,
        ],
    )

    edit_btn.click(
        fn=run_edit,
        inputs=[edit_input, page_option, api_key_input, body_font_dd, app_state],
        outputs=[
            edit_status,
            docx_out,
            pdf_out,
            preview_html,
            scores_display,
            log_display,
            app_state,
        ],
    )

    cl_btn.click(
        fn=run_cover_letter,
        inputs=[cl_tone, cl_extra, api_key_input, app_state],
        outputs=[
            cl_status,
            cl_docx_out,
            cl_pdf_out,
            cl_preview_html,
            log_display,
            app_state,
        ],
    )

    cl_edit_btn.click(
        fn=run_cover_letter_edit,
        inputs=[cl_edit_input, api_key_input, app_state],
        outputs=[
            cl_edit_status,
            cl_docx_out,
            cl_pdf_out,
            cl_preview_html,
            log_display,
            app_state,
        ],
    )

    clear_btn.click(fn=lambda: "", outputs=[log_display])


if __name__ == "__main__":
    import tempfile

    demo.launch(
        server_name="127.0.0.1",
        server_port=7862,
        share=False,
        inbrowser=True,
        css=CSS,
        theme=THEME,
        allowed_paths=[tempfile.gettempdir()],
    )
