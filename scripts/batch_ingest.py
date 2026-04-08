"""Batch ingest historical sessions. Usage: python3 batch_ingest.py --manifest FILE"""
import argparse, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from utils.config import get_vault_path
from capture_session import run_capture

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--skip-enrichment", action="store_true")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--only", choices=["substantial", "minor", "both"], default="both")
    ap.add_argument("--delay", type=float, default=5.0)
    args = ap.parse_args()

    data = json.loads(args.manifest.read_text())
    vault = get_vault_path()
    sessions = []
    if args.only in ("minor", "both"):
        sessions += [(s, True) for s in data.get("minor", [])]
    if args.only in ("substantial", "both"):
        sessions += [(s, args.skip_enrichment) for s in data.get("substantial", [])]

    total, created, skipped, errors = len(sessions), 0, 0, 0
    print(f"Processing {total} sessions into {vault}")

    for i, (info, skip) in enumerate(sessions):
        p = Path(info["file"])
        if not p.exists():
            errors += 1; continue
        try:
            if run_capture(p, vault, skip_enrichment=skip):
                created += 1
                print(f"  [{i+1}/{total}] OK: {info['session_id'][:8]} ({info['project']})")
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{total}] ERROR: {e}")

        if (i + 1) % args.batch_size == 0 and i + 1 < total:
            print(f"  --- Batch pause --- {created} created, {skipped} skipped, {errors} errors")
            time.sleep(args.delay)

    print(f"\nDone! Created: {created}, Skipped: {skipped}, Errors: {errors}")

if __name__ == "__main__":
    main()
