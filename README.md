# Issue-Triage Agent

An AI agent that reads new GitHub issues, labels them, and finds likely duplicates. Project 1 of the 12-week plan.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then paste your GitHub token into .env
python scripts/check_setup.py      # should print a sample issue
```

## Layout

| Path | Purpose |
| --- | --- |
| `src/triage/config.py` | Settings from `.env` and GitHub headers |
| `scripts/check_setup.py` | Fetches one page to prove setup works |
| `src/triage/fetcher.py` | Async downloader with retry/backoff |
| `scripts/fetch_issues.py` | Day 1: run the download to `data/issues.jsonl` |
| `scripts/stats.py` | Counts issues, duplicates and top labels |
| `data/` | Downloaded issues (git-ignored) |
| `notes/` | Design notes, duplicate conventions, findings |
| `tests/` | Tests, including the mocked 429 test |

## Data notes

- Source repo: `microsoft/vscode`
- How duplicates are marked: _fill in on Day 1_

## Day 1 commands

```bash
python scripts/check_setup.py     # one page, proves token + network work
pytest                            # includes the mocked 429 retry test
python scripts/fetch_issues.py    # downloads 5,000+ labeled closed issues
python scripts/stats.py           # totals, duplicates, top labels
```
