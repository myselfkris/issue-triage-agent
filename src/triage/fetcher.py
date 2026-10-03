"""Async downloader for closed, labeled GitHub issues."""
import asyncio
import json
import random
from pathlib import Path

import httpx

from triage.config import GITHUB_API, github_headers

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 6
MAX_SLEEP = 120.0


def parse_issue(raw: dict) -> dict | None:
    """Keep the fields we need; return None for pull requests and unlabeled issues."""
    if "pull_request" in raw or not raw.get("labels"):
        return None
    return {
        "number": raw["number"],
        "title": raw["title"],
        "body": raw.get("body") or "",
        "labels": [label["name"] for label in raw["labels"]],
        "state_reason": raw.get("state_reason"),
        "created_at": raw["created_at"],
        "closed_at": raw.get("closed_at"),
        "comments": raw.get("comments", 0),
        "html_url": raw["html_url"],
    }


def retry_delay(resp: httpx.Response, attempt: int) -> float:
    """Seconds to wait before retrying: Retry-After, rate-limit reset, or exponential backoff."""
    retry_after = resp.headers.get("retry-after")
    if retry_after and retry_after.isdigit():
        return min(float(retry_after), MAX_SLEEP)
    if resp.headers.get("x-ratelimit-remaining") == "0":
        reset = resp.headers.get("x-ratelimit-reset")
        if reset and reset.isdigit():
            import time

            return min(max(int(reset) - time.time(), 1.0), MAX_SLEEP)
    return min(2.0**attempt + random.random(), MAX_SLEEP)


def is_rate_limited(resp: httpx.Response) -> bool:
    if resp.status_code in RETRY_STATUSES:
        return True
    # GitHub signals rate limiting with 403 as well.
    return resp.status_code == 403 and (
        resp.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in resp.headers
    )


async def get_with_retry(client: httpx.AsyncClient, url: str, params: dict) -> httpx.Response:
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = await client.get(url, params=params)
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt == MAX_RETRIES:
                raise
            await asyncio.sleep(min(2.0**attempt + random.random(), MAX_SLEEP))
            continue
        if not is_rate_limited(resp):
            resp.raise_for_status()
            return resp
        if attempt == MAX_RETRIES:
            resp.raise_for_status()
        await asyncio.sleep(retry_delay(resp, attempt))
    raise RuntimeError("unreachable")


async def fetch_page(client: httpx.AsyncClient, repo: str, page: int) -> list[dict]:
    resp = await get_with_retry(
        client,
        f"{GITHUB_API}/repos/{repo}/issues",
        {"state": "closed", "per_page": 100, "page": page},
    )
    return resp.json()


def load_progress(out_path: Path) -> tuple[set[int], set[int]]:
    """Return (issue numbers already saved, pages already completed)."""
    numbers: set[int] = set()
    if out_path.exists():
        with out_path.open() as f:
            for line in f:
                numbers.add(json.loads(line)["number"])
    pages_path = out_path.with_suffix(".pages.json")
    pages = set(json.loads(pages_path.read_text())) if pages_path.exists() else set()
    return numbers, pages


async def download(
    repo: str,
    out_path: Path,
    target: int = 5000,
    concurrency: int = 5,
    wave: int = 10,
    max_pages: int = 500,
    client: httpx.AsyncClient | None = None,
) -> int:
    """Download issues until `target` labeled issues are saved. Returns the total saved."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    numbers, done_pages = load_progress(out_path)
    pages_path = out_path.with_suffix(".pages.json")
    sem = asyncio.Semaphore(concurrency)
    own_client = client is None
    client = client or httpx.AsyncClient(headers=github_headers(), timeout=20)

    async def worker(page: int) -> tuple[int, list[dict]]:
        async with sem:
            return page, await fetch_page(client, repo, page)

    try:
        next_page = 1
        exhausted = False
        while len(numbers) < target and not exhausted and next_page <= max_pages:
            pages = [p for p in range(next_page, next_page + wave) if p not in done_pages]
            next_page += wave
            results = await asyncio.gather(*(worker(p) for p in pages))
            with out_path.open("a") as f:
                for page, raw_items in sorted(results):
                    if not raw_items:
                        exhausted = True
                    kept = 0
                    for raw in raw_items:
                        issue = parse_issue(raw)
                        if issue and issue["number"] not in numbers:
                            f.write(json.dumps(issue) + "\n")
                            numbers.add(issue["number"])
                            kept += 1
                    done_pages.add(page)
                    print(f"page {page}: {len(raw_items)} items, kept {kept}, total {len(numbers)}")
            pages_path.write_text(json.dumps(sorted(done_pages)))
    finally:
        if own_client:
            await client.aclose()
    return len(numbers)
