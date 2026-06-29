from app.routers.generate import _augment_skills, _flatten_skills, _resume_font


def test_resume_font_auto_enables_autofit():
    fc, auto = _resume_font("Calibri", "auto", one_page=True)
    assert auto is True and fc.body_font == "Calibri"


def test_resume_font_fixed_size_disables_autofit_with_ratios():
    fc, auto = _resume_font("Arial", "10", one_page=True)
    assert auto is False
    assert fc.body_size == 10.0
    assert fc.heading_size == 11.0  # 10 * 1.1
    assert fc.name_size == 22.0  # 10 * 2.2


def test_resume_font_bad_value_falls_back_to_auto():
    fc, auto = _resume_font("Calibri", "huge", one_page=True)
    assert auto is True


def test_flatten_handles_list_dict_and_string():
    assert _flatten_skills(["a", "b"]) == ["a", "b"]
    assert _flatten_skills("a, b , c") == ["a", "b", "c"]
    assert _flatten_skills({"Lang": "python, go", "Cloud": ["aws"]}) == ["python", "go", "aws"]


def test_augment_keeps_all_existing_skills_and_selected_keywords():
    # LLM dropped most skills; safety net must restore them + add selected keywords.
    matched = {"tailored_skills": {"Languages": "Python"}}
    resume = {"skills": ["Python", "SQL", "Docker", "React"]}
    _augment_skills(matched, resume, selected_keywords=["Kubernetes"])
    present = {s.lower() for v in matched["tailored_skills"].values() for s in _flatten_skills(v)}
    for expected in ("python", "sql", "docker", "react", "kubernetes"):
        assert expected in present


def test_augment_is_case_insensitive_no_duplicates():
    matched = {"tailored_skills": {"Languages": "python"}}
    resume = {"skills": ["Python"]}  # already present (different case)
    _augment_skills(matched, resume, selected_keywords=[])
    # "python" should not be duplicated into Additional Skills
    assert "Additional Skills" not in matched["tailored_skills"]


def test_augment_with_empty_tailored_uses_all_originals():
    matched = {"tailored_skills": {}}
    resume = {"skills": ["Go", "Rust"]}
    _augment_skills(matched, resume, selected_keywords=[])
    present = {s.lower() for v in matched["tailored_skills"].values() for s in _flatten_skills(v)}
    assert {"go", "rust"} <= present
