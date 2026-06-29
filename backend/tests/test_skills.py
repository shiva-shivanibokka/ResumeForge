from app.routers.generate import _augment_skills, _flatten_skills, _resume_font, merge_skills


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


def _flat_lower(skills: dict) -> list[str]:
    return [s.lower() for v in skills.values() for s in _flatten_skills(v)]


def test_merge_dedupes_across_categories():
    out = merge_skills({"Lang": "Python, SQL", "More": "python, Go"})
    flat = _flat_lower(out)
    assert flat.count("python") == 1
    assert "go" in flat and "sql" in flat


def test_merge_appends_extra_to_last_category_no_catchall():
    out = merge_skills({"Languages": "Python", "Cloud": "AWS"}, ["Kubernetes"])
    assert "Additional Skills" not in out and "Other" not in out
    assert "kubernetes" in out["Cloud"].lower()  # folded into the last category


def test_merge_skips_already_present_extra():
    out = merge_skills({"Languages": "Python"}, ["python"])
    assert _flat_lower(out).count("python") == 1


def test_merge_empty_creates_single_skills_category():
    out = merge_skills({}, ["Go", "Rust"])
    assert list(out.keys()) == ["Skills"]
    assert {"go", "rust"} <= set(_flat_lower(out))


def test_augment_adds_selected_keywords_and_dedupes():
    matched = {"tailored_skills": {"Languages": "Python, python", "Cloud": "AWS"}}
    _augment_skills(matched, {"skills": ["Python", "SQL"]}, selected_keywords=["Kubernetes"])
    flat = _flat_lower(matched["tailored_skills"])
    assert flat.count("python") == 1  # deduped
    assert "kubernetes" in flat  # selected keyword added
    assert "Additional Skills" not in matched["tailored_skills"]
