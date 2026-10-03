"""Download closed, labeled issues to data/issues.jsonl.

Run from the repo root:  python scripts/fetch_issues.py [--repo owner/name] [--target 5000]
Safe to re-run: pages already saved are skipped.
"""
import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from triage.config import GITHUB_TOKEN, SOURCE_REPO
from triage.fetcher import download


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=SOURCE_REPO)
    parser.add_argument("--target", type=int, default=5000)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "issues.jsonl")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        sys.exit("GITHUB_TOKEN is not set. Copy .env.example to .env and add your token.")

    total = asyncio.run(download(args.repo, args.out, target=args.target))
    print(f"Done: {total} labeled issues in {args.out}")


if __name__ == "__main__":
    main()
