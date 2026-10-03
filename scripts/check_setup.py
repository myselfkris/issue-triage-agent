"""Smoke test: fetch one page of closed issues and print what came back.

Run from the repo root:  python scripts/check_setup.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx

from triage.config import GITHUB_API, GITHUB_TOKEN, SOURCE_REPO, github_headers


def main() -> None:
    url = f"{GITHUB_API}/repos/{SOURCE_REPO}/issues"
    params = {"state": "closed", "per_page": 100, "page": 1}
    resp = httpx.get(url, headers=github_headers(), params=params, timeout=20)
    resp.raise_for_status()

    items = resp.json()
    issues = [i for i in items if "pull_request" not in i]
    labeled = [i for i in issues if i["labels"]]

    print(f"Token set:        {'yes' if GITHUB_TOKEN else 'no (60 requests/hour limit)'}")
    print(f"Rate limit left:  {resp.headers.get('x-ratelimit-remaining')} / {resp.headers.get('x-ratelimit-limit')}")
    print(f"Items on page 1:  {len(items)} ({len(issues)} issues, {len(items) - len(issues)} PRs)")
    print(f"Issues w/ labels: {len(labeled)}")
    if labeled:
        sample = labeled[0]
        print("\nSample issue:")
        print(json.dumps({
            "number": sample["number"],
            "title": sample["title"],
            "labels": [l["name"] for l in sample["labels"]],
            "state_reason": sample.get("state_reason"),
            "html_url": sample["html_url"],
        }, indent=2))


if __name__ == "__main__":
    main()
