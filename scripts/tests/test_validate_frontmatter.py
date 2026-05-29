from validate_frontmatter import validate_note

def test_valid_note_has_no_errors():
    fm = {"type": "pattern", "title": "X", "project": "openclaw",
          "status": "active", "updated": "2026-05-28"}
    assert validate_note("patterns/x.md", fm) == []

def test_missing_fields_reported():
    fm = {"type": "pattern", "title": "X"}
    errs = validate_note("patterns/x.md", fm)
    assert len(errs) == 1
    assert "project" in errs[0] and "status" in errs[0] and "updated" in errs[0]

def test_invalid_type_reported():
    fm = {"type": "banana", "title": "X", "project": "p",
          "status": "active", "updated": "2026-05-28"}
    errs = validate_note("patterns/x.md", fm)
    assert any("invalid type" in e for e in errs)
