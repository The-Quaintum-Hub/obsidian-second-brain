from utils.frontmatter import parse_frontmatter

def test_parses_simple_keys_and_lists():
    text = (
        "---\n"
        "type: pattern\n"
        'title: "OpenClaw cron gotchas"\n'
        "project: openclaw\n"
        "status: active\n"
        "tags: [openclaw, cron, hooks]\n"
        "updated: 2026-05-28\n"
        "---\n"
        "# Body\nstuff\n"
    )
    fm = parse_frontmatter(text)
    assert fm["type"] == "pattern"
    assert fm["title"] == "OpenClaw cron gotchas"
    assert fm["project"] == "openclaw"
    assert fm["status"] == "active"
    assert fm["tags"] == ["openclaw", "cron", "hooks"]
    assert fm["updated"] == "2026-05-28"

def test_returns_empty_when_no_frontmatter():
    assert parse_frontmatter("# Just a heading\nno fm") == {}
