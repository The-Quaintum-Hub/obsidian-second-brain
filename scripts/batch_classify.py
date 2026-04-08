"""Classify all historical sessions. Usage: python3 batch_classify.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from utils.config import get_claude_projects_dir
from utils.jsonl_parser import parse_session

def main():
    projects_dir = get_claude_projects_dir()
    results = {"substantial": [], "minor": [], "trivial": [], "subagent": []}
    errors = []
    for f in sorted(projects_dir.rglob("*.jsonl")):
        try:
            s = parse_session(f)
            results[s.classification].append({
                "session_id": s.session_id, "project": s.project,
                "date": s.start_time.isoformat() if s.start_time else None,
                "duration_min": s.duration_min, "messages": s.user_message_count,
                "files_edited": len(s.files_edited), "file": str(f),
                "size_bytes": f.stat().st_size})
        except Exception as e:
            errors.append({"file": str(f), "error": str(e)})

    output = {**results, "stats": {k: len(v) for k, v in results.items()},
              "errors": errors}
    output["stats"]["total"] = sum(output["stats"][k] for k in results)
    output["stats"]["errors"] = len(errors)

    out_path = Path("batch-manifest.json")
    out_path.write_text(json.dumps(output, indent=2, default=str) + "\n")
    for k in results:
        print(f"  {k:12s}: {len(results[k])}")
    print(f"  {'errors':12s}: {len(errors)}")
    print(f"Saved to: {out_path}")

if __name__ == "__main__":
    main()
