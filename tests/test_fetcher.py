import asyncio
import json

import httpx
import pytest

from triage import fetcher


def make_issue(n, labels=("bug",), pr=False):
    item = {
        "number": n,
        "title": f"issue {n}",
        "body": "text",
        "labels": [{"name": l} for l in labels],
        "state_reason": "completed",
        "created_at": "2026-01-01T00:00:00Z",
        "closed_at": "2026-01-02T00:00:00Z",
        "comments": 0,
        "html_url": f"https://github.com/o/r/issues/{n}",
    }
    if pr:
        item["pull_request"] = {}
    return item


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def fake_sleep(_):
        return None

    monkeypatch.setattr(fetcher.asyncio, "sleep", fake_sleep)


def test_parse_issue_drops_prs_and_unlabeled():
    assert fetcher.parse_issue(make_issue(1, pr=True)) is None
    assert fetcher.parse_issue(make_issue(2, labels=())) is None
    assert fetcher.parse_issue(make_issue(3))["labels"] == ["bug"]


def test_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(429, headers={"retry-after": "1"})
        return httpx.Response(200, json=[make_issue(1)])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetcher.fetch_page(client, "o/r", 1)

    items = asyncio.run(run())
    assert calls["n"] == 3
    assert items[0]["number"] == 1


def test_403_with_exhausted_rate_limit_is_retried():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(403, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": "0"})
        return httpx.Response(200, json=[])

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetcher.fetch_page(client, "o/r", 1)

    assert asyncio.run(run()) == []
    assert calls["n"] == 2


def test_gives_up_after_max_retries():
    def handler(request):
        return httpx.Response(429)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await fetcher.fetch_page(client, "o/r", 1)

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(run())


def test_download_saves_labeled_issues_and_resumes(tmp_path):
    def handler(request):
        page = int(request.url.params["page"])
        if page == 1:
            return httpx.Response(200, json=[make_issue(1), make_issue(2, pr=True), make_issue(3, labels=())])
        if page == 2:
            return httpx.Response(200, json=[make_issue(4)])
        return httpx.Response(200, json=[])

    out = tmp_path / "issues.jsonl"

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetcher.download("o/r", out, target=100, wave=3, client=client)

    assert asyncio.run(run()) == 2
    saved = [json.loads(l)["number"] for l in out.read_text().splitlines()]
    assert saved == [1, 4]

    # Re-running adds nothing and does not duplicate lines.
    assert asyncio.run(run()) == 2
    assert len(out.read_text().splitlines()) == 2
