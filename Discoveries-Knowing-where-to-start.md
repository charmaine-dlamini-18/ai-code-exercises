# Exercise: Knowing Where to Start — Submission

Language chosen: **Python** implementation of the Task Manager (`task-manager/python/`).

## 1. Initial vs. Final Understanding

**Initial understanding:**
- I guessed the app was a command-line task manager built entirely on the Python standard library (no frameworks, no database), organized in a layered way: CLI -> business logic -> models -> storage.
- I expected configuration files (a `requirements.txt`) and possibly third-party dependencies; none exist.
- I assumed persistence would be something more robust; it is a single JSON file.

**Final understanding:**
- The app is a pure standard-library CLI tool. Layers: `cli.py` (argparse UI) -> `app.py` (`TaskManager` service) -> `storage.py` (JSON persistence with custom encoder/decoder) -> `models.py` (domain: `Task`, `TaskStatus`, `TaskPriority`).
- Entry point is `cli.py:main()`; every command flows `cli -> TaskManager -> TaskStorage -> tasks.json`.
- Key semantics learned: "overdue" is a strict boolean (`due_date < now` and status != DONE); `completed_at` is set only by `mark_as_done()` and never cleared; priority is a passive attribute no business rule uses yet; the status lifecycle is a convention, not enforced.

## 2. Most Valuable Insights from Each Prompt

- **Part 1 (Project Structure):** Confirmed the layered architecture and revealed the absence of any dependencies. Established the entry-point and data-flow map that every later part relied on.
- **Part 2 (Finding Feature Implementation):** Taught me to search for *patterns* (serialization, file I/O, command wiring) rather than feature keywords when a feature doesn't exist yet, and to trace one existing feature end-to-end as a template for new ones (the `stats` command became my template for CSV export).
- **Part 3 (Domain Model):** The most valuable. It exposed the business semantics behind the code (strict overdue check, passive priority, stale `completed_at`, unenforced status lifecycle) — exactly the knowledge needed to design new business rules and to spot real edge cases and bugs.
- The "test your understanding" questions in Part 3 were the highlight: answering them surfaced inconsistencies (e.g., reopening a DONE task leaves `completed_at` set, skewing stats) that a casual read would miss.

## 3. Approach to Implementing the Business Rule

Rule: *Tasks overdue more than 7 days are automatically marked abandoned unless they are high priority.*

Plan:
1. `models.py` — add `ABANDONED` to `TaskStatus`; add a `days_overdue()` method (the code only has a boolean `is_overdue()`).
2. `app.py` — add `TaskManager.mark_abandoned_overdue()` holding the rule: skip DONE/ABANDONED, require `days_overdue() > 7`, skip `HIGH` priority, set status, save.
3. `storage.py` — add a query helper mirroring the existing `get_tasks_by_*` methods; reuse existing `save()`.
4. `cli.py` — add an `ABANDONED` display symbol and a subcommand (or startup sweep), mirroring the `stats` wiring.

Open questions for the team before coding: where "automatic" runs (no scheduler exists — cron, CLI hook, or explicit command); whether "high priority" includes `URGENT`; whether abandoned tasks stay visible in `list`/`stats`; whether abandoned is a final state; and whether 7 days should be configurable.

## 4. Strategies for Approaching Unfamiliar Code

- Start with structure, not details: skim the directory tree and config files, then form a hypothesis before asking for help.
- Find the entry point and trace one complete feature end-to-end; reuse that flow as a template for anything new.
- When searching, combine feature keywords with *pattern* searches (file I/O, serialization, command wiring).
- Articulate my current understanding explicitly before prompting — the quality of context determines the quality of the answer.
- Answer any questions an AI poses rather than skipping them; they reveal gaps and hidden edge cases.
- Keep a running document of findings, glossary terms, misconceptions, and "questions for the team" as I explore.