# Code Understanding Journal
---
# Exercise: Codebase Exploration Challenge
## 7. Part 1 — Understanding a Specific Feature: Task Creation & Status Updates

**Prompt used:** "Prompt 1: Understand how a specific feature works"

**Files identified as related:**
- `cli.py:39-44,86-96` (create command), `cli.py:53-55,107-111` (status command)
- `task_manager.py:12-25` (`create_task`), `task_manager.py:41-50` (`update_task_status`)
- `models.py:18-30` (`Task.__init__`), `models.py:32-36` (`Task.update`), `models.py:38-41` (`mark_as_done`)
- `storage.py:67-70` (`add_task`), `storage.py:72-81` (`get_task` / `update_task`), `storage.py:60-65` (`save`), `storage.py:49-58` (`load`)

**Main components involved:**
1. `cli.py` — parses arguments, dispatches to `TaskManager`, prints the result.
2. `task_manager.py` — service layer: converts user input to domain objects and enums, orchestrates storage.
3. `models.py` — creates/holds state: `Task`, `TaskStatus` (enum), `TaskPriority` (enum).
4. `storage.py` — in-memory dict of tasks + JSON file persistence.

**Execution flow — creating a task (`python cli.py create "Buy milk" -d "..." -p 2 -t "a,b"`):**
```
cli.py main() → args.command == "create"
  ├─ parse/clean tags (cli.py:87)
  └─ task_manager.create_task(title, description, priority, due, tags)   [task_manager.py:12]
       ├─ TaskPriority(value) → enum
       ├─ parse "YYYY-MM-DD" → datetime (invalid prints "Invalid date format...", returns None)
       ├─ Task(...)                     [models.py:18] → id=uuid4, status=TODO,
       │                                             created_at=updated_at=now, tags=[]
       └─ storage.add_task(task)        [storage.py:67]
            ├─ self.tasks[task.id] = task   (in-memory)
            ├─ save()  → json.dump(TaskEncoder, indent=2) → tasks.json   [storage.py:60]
            └─ return task.id
  └─ CLI prints "Created task with ID: <uuid>"
```

**Execution flow — updating a status (`python cli.py status <id> done`):**
```
cli.py main() → args.command == "status"   [cli.py:107]
  └─ task_manager.update_task_status(id, "done")   [task_manager.py:41]
       ├─ new_status = TaskStatus("done") → TaskStatus.DONE
       ├─ if new_status == DONE:
       │    ├─ storage.get_task(id)  → in-memory dict lookup   [storage.py:72]
       │    ├─ if task: task.mark_as_done()           [models.py:38]
       │    │     status = DONE; completed_at = now; updated_at = completed_at
       │    ├─ storage.save()   → full-file rewrite     [storage.py:60]
       │    └─ return True
       └─ else: storage.update_task(id, status=new_status) → Task.update(**kwargs)
            → updated_at = now → save()   [storage.py:75]
  └─ CLI prints "Updated task status to done" / failure message
```

**How data is stored and retrieved:**
- At startup `TaskStorage.__init__` builds an in-memory `{task_id: Task}` dict via `load()`.
- `load()` reads `tasks.json` using a custom `TaskDecoder` (`object_hook`) that rebuilds `Task` objects — rotating enum values back to enums and ISO strings back to `datetime`.
- `save()` writes the whole list of tasks with a custom `TaskEncoder` — converting `priority`/`status` to `.value` and datetimes to ISO strings.
- Every mutation trigger a **full-file rewrite** (no diffing/appending).

**Interesting design patterns discovered:**
- **Layered architecture**: CLI (presentation) → service → storage → model.
- **Repository pattern**: `TaskStorage` hides the persistence mechanism behind CRUD-like methods (`get_task`, `update_task`, `delete_task`...).
- **Custom serialization via `JSONEncoder`/`JSONDecoder` subclasses** to bridge enums/datetimes to JSON.
- **Enum-typed state/priority** ensures valid values, but validation is duplicated at the argparse layer too (`choices=[1,2,3,4]`).
- **Tests rely on dependency injection**: many tests swap `task_manager.storage` for a `Mock()`.

---

## 8. Part 2 — Deepen Understanding: Task Prioritization System

**Prompt used:** "Prompt 2: Deepen understanding of a codebase" (guided-questioning / pair-programming style).

**My initial understanding (shared with the AI):**
- Priority is a `TaskPriority` enum: LOW=1, MEDIUM=2, HIGH=3, URGENT=4 (default MEDIUM).
- It's set at creation (`-p`), changeable via the `priority` command, usable as a `list --priority` filter, shown as `!`/`!!`/`!!!`/`!!!!` symbols, and grouped in stats by `priority.name`.
- The enum itself raises `ValueError` for invalid integers (e.g. 5).
- I believed priority was a passive attribute with no behavioural consequences and that it was stored under its display name.

**Guided questions asked by the AI (and where I found the answers):**
1. What happens if `update_task_priority` is given an invalid value like 5? — `TaskPriority(5)` raises `ValueError`, confirmed by `tests/test_task_manager.py:test_update_task_priority_invalid_priority`.
2. Where is priority validated on the CLI vs. in the service layer? — argparse restricts `choices=[1,2,3,4]` (cli.py:59) *and* the enum construction at `task_manager.py:52-53` guards the service layer; `list_tasks(priority_filter=N)` constructs `TaskPriority(N)` (task_manager.py:36) so invalid filters raise too.
3. How does priority round-trip through JSON? — Stored as its integer `.value` (`storage.py:11` `task_dict['priority'] = obj.priority.value`) and restored via `TaskPriority(obj['priority'])` (storage.py:28).
4. Does priority influence overdue status, statistics, or any other rule? — **No.** It's used only for filtering, display symbols, and the stats grouping.
5. Why store `.value` (int) instead of `.name` in JSON? — Stable, compact, and matches the CLI's integer arguments (1–4); names are uppercase and tied to code, values are the contract.

**Initial understanding vs. what I discovered:**
- **Confirmed:** priority is passive — no business rule depends on it. The "abandoned unless high priority" rule in the other exercise would be the *first*.
- **Corrected:** priority is NOT stored under its name — it's stored as integer `.value`.
- **New inconsistency found:** in `get_statistics`, `status_counts` keys use `status.value` ("todo", "done"...), but `priority_counts` keys use `priority.name` ("LOW", "MEDIUM"...). So stats show priorities in a different format than storage/CLI use.
- **Design note:** priority gets triple validation (argparse choices, enum construction, tests) — the enum is doing the real enforcement.

**Misconceptions clarified:**
- URGENT is not a special state — it's just the top ordinal; the `!!!!` symbol is the only thing that sets it apart.
- Validation isn't a single layer; it's layered (CLI + enum + tests), and the enum is the hard guarantee.

---

## 9. Part 3 — Mapping Data Flow: Marking a Task as Complete

**Prompt used:** "Prompt 3: Mapping Data Flow and State Management"

**Entry point & components:** `cli.py:107` (`status` command) → `task_manager.py:41-50` (`update_task_status`) → `models.py:38-41` (`mark_as_done`) → `storage.py:72` (`get_task`) + `storage.py:60` (`save`) → `tasks.json`.

**Data flow diagram:**
```
User: python cli.py status <id> done
  │
  ▼
cli.py main()  [args.command == "status"]
  │  task_id, "done"
  ▼
TaskManager.update_task_status(id, "done")   [task_manager.py:41]
  │  new_status = TaskStatus("done")  ==  TaskStatus.DONE
  │
  ├──► TaskStorage.get_task(id) [storage.py:72]  → in-memory dict lookup
  │        │
  │        ▼
  │     Task (or None)
  │        │  found
  │        ▼
  │     Task.mark_as_done()   [models.py:38]
  │        ├─ status    : TODO/... → DONE
  │        ├─ completed_at : None   → datetime.now()
  │        └─ updated_at   : = completed_at
  │        │
  │        ▼
  │     TaskStorage.save()   [storage.py:60]
  │        └─ TaskEncoder → json.dump(indent=2) → tasks.json  (full rewrite)
  │
  ▼
True  →  cli prints "Updated task status to done"
```

**State changes that occur:**
- `task.status`: any → `TaskStatus.DONE`
- `task.completed_at`: `None` → `datetime.now()`
- `task.updated_at`: → same as `completed_at`

**Potential points of failure:**
- **Task not found** → no state change; `update_task_status` returns `False` and the CLI reports the failure (safe path).
- **Stale `completed_at`:** only `mark_as_done()` sets `completed_at`. Changing a DONE task to another status via the non-DONE branch (`update_task` → `Task.update`) does **not** clear it — stats keep counting it as "completed last week". Confirmed by reading `task_manager.py:41-50` + `models.py:32-41`.
- **Full-file rewrite:** `save()` serializes the *entire* list each time; there is no locking — two CLI processes could overwrite each other's changes.
- **Swallowed exceptions:** `load()`/`save()` print errors but don't raise — a failed save leaves disk stale while memory holds the "truth", risking silent data loss.
- **No transactions:** in-memory mutations + single `save()` are not atomic as a unit.

**How the application persists this change:**
- The DONE task is in the in-memory dict; `save()` re-serializes all tasks via `TaskEncoder`, which now includes a populated `completed_at` as an ISO-format string. `load()` on the next run restores it with `datetime.fromisoformat` via `TaskDecoder`.

---
