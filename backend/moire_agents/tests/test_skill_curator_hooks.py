import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mcp_server_handoff as h  # noqa: E402


def _write_skill(root, app, name, frontmatter_extra="", body="Body text.\n"):
    skill_dir = os.path.join(root, app, name)
    os.makedirs(skill_dir, exist_ok=True)
    path = os.path.join(skill_dir, "SKILL.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "---\n"
            f"name: {name}\n"
            "description: a searchable test skill\n"
            f"{frontmatter_extra}"
            "---\n\n"
            f"{body}"
        )
    return path


def test_skill_search_bumps_attempts_and_last_searched(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SKILL_LIB_ROOT", str(tmp_path))
    path = _write_skill(tmp_path, "testapp", "searchable-skill", frontmatter_extra="attempts: 0\n")

    result = h._skill_search("searchable")

    assert result["success"] is True
    assert len(result["results"]) == 1
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    assert "attempts: 1" in text
    assert "last_searched:" in text


def test_skill_search_no_match_does_not_touch_file(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SKILL_LIB_ROOT", str(tmp_path))
    path = _write_skill(tmp_path, "testapp", "unrelated-skill", frontmatter_extra="attempts: 0\n")

    result = h._skill_search("nonexistent-query-xyz")

    assert result["results"] == []
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    assert "attempts: 0" in text
    assert "last_searched" not in text


def test_skill_save_and_index_new_skill_gets_curator_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SKILL_LIB_ROOT", str(tmp_path))

    result = h._skill_save_and_index(
        "testapp", "new-skill", {"name": "new-skill", "description": "d"}, "Body\n"
    )

    assert result["success"] is True
    with open(result["path"], "r", encoding="utf-8") as f:
        text = f.read()
    assert "agent_created: true" in text
    assert "attempts: 0" in text
    assert "curator_status: active" in text
    assert "pinned: false" in text


def test_skill_save_and_index_existing_file_not_flipped_to_agent_created(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SKILL_LIB_ROOT", str(tmp_path))
    _write_skill(tmp_path, "testapp", "human-skill", frontmatter_extra="agent_created: false\n")

    result = h._skill_save_and_index(
        "testapp", "human-skill", {"name": "human-skill", "description": "edited"}, "New body\n"
    )

    assert result["success"] is True
    with open(result["path"], "r", encoding="utf-8") as f:
        text = f.read()
    # Pass-through behavior for edits to an existing file is unchanged:
    # only whatever the caller supplied is written, no defaults injected.
    assert "agent_created" not in text


def test_skill_save_and_index_new_skill_agent_created_cannot_be_overridden_false(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SKILL_LIB_ROOT", str(tmp_path))

    result = h._skill_save_and_index(
        "testapp",
        "spoofed-skill",
        {"name": "spoofed-skill", "description": "d", "agent_created": False},
        "Body\n",
    )

    assert result["success"] is True
    with open(result["path"], "r", encoding="utf-8") as f:
        text = f.read()
    # Server-side invariant wins over caller-supplied input for brand-new skills.
    assert "agent_created: true" in text


def test_bump_skill_usage_no_blank_line_for_bare_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SKILL_LIB_ROOT", str(tmp_path))
    # Realistic shape of every pre-existing skill: only name/description,
    # no attempts:/last_searched: lines at all.
    path = _write_skill(tmp_path, "testapp", "bare-skill")

    assert h._bump_skill_usage(path) is True
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    assert not text.startswith("---\n\n")
    assert "attempts: 1" in text
    assert "last_searched:" in text


def test_bump_skill_usage_twice_does_not_compound_blank_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(h, "_SKILL_LIB_ROOT", str(tmp_path))
    path = _write_skill(tmp_path, "testapp", "bare-skill-2")

    assert h._bump_skill_usage(path) is True
    assert h._bump_skill_usage(path) is True

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    assert not text.startswith("---\n\n")
    assert "attempts: 2" in text
    # Frontmatter block must still open with a single "---" line, not one
    # followed by a run of blank lines from repeated joins.
    fm_start = text.split("\n", 1)[1]
    assert not fm_start.startswith("\n")
