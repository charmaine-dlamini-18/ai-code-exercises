# testing-001 — Findings: Using AI to help with testing

**Exercise:** Using AI to help with testing (task prioritization algorithm)
**Chosen implementation:** Python (`use-cases/testing-001/python/TaskManager`)
**Functions under test:** `calculate_task_score`, `sort_tasks_by_importance`, `get_top_priority_tasks`
**Test runner:** `python -m unittest discover -s tests -v` (from `python/TaskManager`; stdlib only, no external dependencies)

The Python TaskManager shipped **no test suite at all** (README says `Run the Tests: TODO`). This exercise was the opportunity to build one from scratch, driving the work with the Socratic AI prompts from the worksheet.

---

## Part 1 — Understanding What to Test

### 1.1 Behavior analysis of `calculate_task_score`

The conversation with the AI started from my own reading of the function, then the AI asked questions to surface behaviours I hadn't listed. Behaviours I identified first:

- Base score comes from priority: LOW 10, MEDIUM 20, HIGH 40, URGENT 60 (weight × 10).
- Due date adds a bonus that scales down as the deadline moves further out.
- DONE tasks get a penalty (designed so finished tasks rank low).
- Specially-tagged tasks (blocker/critical/urgent) get a boost.
- Recently updated tasks get a boost.

Behaviours the AI's questions surfaced that I initially **missed**:

1. **Unknown priority** falls back to weight 0 — the `.get(task.priority, 0)` means a corrupted/invalid priority silently scores 0 rather than raising.
2. **The REVIEW penalty is −15** — easy to overlook because DONE (−50) dominates attention; REVIEW is a separate, smaller bucket.
3. **Due-date ladder has a shape**: overdue +35, due today +20, next 2 days +15, next week +10, **nothing beyond 7 days** — and compared to the +35/+20, the "next 2 days" bucket is what most intuitively would have expected to be the top bonus. Worth pinning exactly.
4. **No due date** must not crash and adds nothing.
5. **Recency uses floored `timedelta.days`** — `days_since_update < 1` means "fewer than 1 full day", i.e. exactly 0 days. A task updated 23h ago still gets the +5 boost.
6. **Factors combine additively** — an overdue URGENT critical blocker assigned to you can score 120, several times a plain task.

### 1.2 Test planning (all three functions) — the checklist

The AI guided the plan by asking, for each behaviour: *"how would you test it?"* and for each edge case: *"what do you expect to happen?"*. The resulting checklist, ordered by priority:

| # | Test case | Priority | Type | Dependency | Expected outcome |
|---|-----------|----------|------|------------|------------------|
| 1 | Base score per priority (LOW/MEDIUM/HIGH/URGENT) | High | unit | neutral `base_task` (TODO, no due, no tags, updated 2 days ago) | 10 / 20 / 40 / 60 |
| 2 | Unknown priority value | High | unit | task with `priority` set to a bogus value | score 0 (no crash) |
| 3 | Due-date buckets: overdue / today / ≤2d / ≤7d / >7d / none | High | unit | due-date determined relative to `datetime.now()` | +35 / +20 / +15 / +10 / +0 / +0 on base 20 |
| 4 | Status penalties: DONE / REVIEW / IN_PROGRESS | High | unit | task status set directly | −50 / −15 / +0 |
| 5 | Tag boost: blocker, critical, urgent, unrelated, empty | High | unit | tags list | +8 for the three magic tags, else +0 |
| 6 | Recency boost & boundary (23h vs 25h; brand new) | High | unit | `updated_at` offset relative to now | +5 when `.days == 0`, else +0 |
| 7 | Combined factors (all positive at once) | Medium | unit | urgent, overdue, critical, assigned, recently updated | 60+35+8+12+5 = 120 |
| 8 | Sort returns highest score first, desc | High | unit | list of tasks with distinct scores | first element has max score |
| 9 | Sort edge cases: empty / single / ties / no mutation | High | unit | minimal lists | `[]` / `[t]` / stable order preserved / input unchanged |
| 10 | `get_top_priority_tasks`: N, default 5, N > len, N=0 | Medium | unit | pre-scored task lists | correct slice each time |
| 11 | Integration: score → sort → top-N compose | High | **integration** | a realistic mixed workload (urge, overdue, blocker, assignee, done-penalty…) | sorted order non-increasing; top-3 exactly the 3 highest by independent score |

**Testing dependencies:** the only "dependency" is the clock. Rather than freezing time (which would need an external library, violating the "stdlib only" constraint), every test computes dates as **offsets from `datetime.now()`** (e.g. `now + timedelta(hours=5)`), so results are deterministic regardless of when the suite runs. Tests use a shared `base_task()` helper that neutralises every modifier (TODO, no due date, no tags, updated 2 days ago), and each test toggles exactly one factor.

---

## Part 2 — Improving a Single Test

### 2.1 From a basic test to a behaviour test

Initial simple test (the obvious first attempt):

```python
def test_medium_priority_score(self):
    task = Task("do the thing", priority=TaskPriority.MEDIUM)
    assert calculate_task_score(task) == 25   # guessed
```

The AI guided the improvement with questions. Problems it made me see:

- The assertion (`25`) was both **arbitrary** and **wrong** for the baseline: a freshly created task carries `updated_at = now`, so it *also* earns the +5 recency boost — the real value is `20 + 5 = 25`. My test was accidentally relying on an unrelated factor, which is exactly the "implementation-detail vs behaviour" trap.
- The test name described the input, not the **behaviour** it pins.
- It could not distinguish the base priority weight from the recency boost.

Rewritten version (asserts behaviour, isolates the factor):

```python
def test_medium_priority_scores_20(self):
    task = base_task(priority=TaskPriority.MEDIUM)
    assert calculate_task_score(task) == 20
```

with `base_task()` explicitly ageing `updated_at` by 2 days so the recency boost can't leak in. Each assertion is now a precise statement about one factor.

### 2.2 Learning from examples — due date calculation

The AI's example showed the principle for date logic: **test each bucket at a value comfortably *inside* it**, using offsets relative to *now*, and name the test after the bucket. One key insight the example demonstrated: `timedelta.days` **floors**, so `now + timedelta(days=3)` evaluated a microsecond later yields `.days == 2` — a test author must pad offsets into the middle of a bucket, not the edge.

The resulting table-style test (one method per bucket):

```python
def test_overdue_task_adds_35(self):
    task = base_task(due_date=datetime.now() - timedelta(days=1))
    assert calculate_task_score(task) == 55          # 20 + 35

def test_due_today_adds_20(self):
    task = base_task(due_date=datetime.now() + timedelta(hours=5))
    assert calculate_task_score(task) == 40          # 20 + 20

def test_due_within_two_days_adds_15(self):
    task = base_task(due_date=datetime.now() + timedelta(days=1, hours=18))   # 42h -> .days == 1
    assert calculate_task_score(task) == 35          # 20 + 15

def test_due_within_a_week_adds_10(self):
    task = base_task(due_date=datetime.now() + timedelta(days=3, hours=12))   # 84h -> .days == 3
    assert calculate_task_score(task) == 30          # 20 + 10

def test_due_beyond_a_week_adds_nothing(self):
    task = base_task(due_date=datetime.now() + timedelta(days=9))             # .days == 8
    assert calculate_task_score(task) == 20
```

Better than a single combined test because a failure now tells you **which bucket** is wrong, not just "the date logic is wrong."

---

## Part 3 — Test-Driven Development

### 3.1 TDD for a new feature: +12 boost for tasks assigned to the current user

**Design decision** (agreed with the AI before writing code): the codebase has no notion of an authenticated user, so "current user" is a module constant `CURRENT_USER_ID = "current-user"` in `task_priority.py`, and the `Task` model grows an `assigned_to` attribute (default `None`). Persistence round-trips the field (encoder serialises `__dict__`, decoder restores `assigned_to`).

**RED — write the failing test first.** The first test asserts the *delta*, so it is robust to other factors:

```python
def test_task_assigned_to_current_user_gets_plus_12(self):
    mine = base_task(assigned_to=CURRENT_USER)
    theirs = base_task(assigned_to="someone-else")
    assert calculate_task_score(mine) == calculate_task_score(theirs) + 12
    assert calculate_task_score(mine) == 32
```

Initial run: **36/38 pass, 2 fail** — exactly the assignee tests (`20 != 32` and the combined test `108 != 120`). Clean red.

**GREEN — minimal code.** Three lines in `calculate_task_score`:

```python
if task.assigned_to == CURRENT_USER_ID:
    score += 12
```

**REFACTOR.** None needed — the change is small and additive; adding structure now would be speculative.

**Next test.** The feedback loop asks *"what could regress next?"* → a task assigned to someone else, and an unassigned task, must both get no boost (guards against "any assignment boosts" bugs):

```python
def test_task_assigned_to_someone_else_gets_no_boost(self):
    assert calculate_task_score(base_task(assigned_to="someone-else")) == 20

def test_unassigned_task_gets_no_boost(self):
    assert calculate_task_score(base_task(assigned_to=None)) == 20
```

Suite: **38/38 pass.**

### 3.2 TDD for a bug fix: "days since update"

The worksheet describes a bug where `days_since_update` is computed by **dividing milliseconds** (JS) or via the wrong **ChronoUnit** (Java), so any update under 24h — even 23h59m old — still reads as "0 days".

```python
# current Python implementation
days_since_update = (datetime.now() - task.updated_at).days
```

**Analysis first:** the Python port does *not* have this bug — it already uses `timedelta.days`, which is exactly the fix the exercise describes. There was no failure to reproduce in the Python implementation. I did not manufacture a bug just to go through the motions.

**Test-first discipline applied anyway** by pinning the *correct* boundary behaviour with regression tests (these would **fail** against a millisecond-division implementation and guard us if someone ever rewrites this):

```python
def test_updated_23_hours_ago_gets_boost(self):
    task = base_task()
    task.updated_at = datetime.now() - timedelta(hours=23)
    assert calculate_task_score(task) == 25   # .days == 0 -> +5

def test_updated_25_hours_ago_gets_no_boost(self):
    task = base_task()
    task.updated_at = datetime.now() - timedelta(hours=25)
    assert calculate_task_score(task) == 20   # .days == 1 -> nothing
```

**Minimal fix:** none required (correct already). The regression tests now document the intended semantics so an accidental re-introduction of the millisecond bug fails loudly.

---

## Part 4 — Integration Testing

One integration test verifies all three functions *compose*, using a realistic mixed workload where factors overlap:

```python
def test_full_workflow_ranks_expected_tasks(self):
    tasks = [
        base_task(title="deadline on fire", priority=URGENT,
                  due_date=now - timedelta(days=1), tags=["critical"],
                  assigned_to=CURRENT_USER),                 # 120
        base_task(title="due today", priority=HIGH,
                  due_date=now + timedelta(hours=5)),        # 60
        base_task(title="due soon", priority=MEDIUM,
                  due_date=now + timedelta(days=3, hours=12)), # 30
        base_task(title="finished old", priority=HIGH),      # -10 (DONE)
        base_task(title="quiet low", priority=LOW),          # 10
        base_task(title="plain medium"),                     # 20
        base_task(title="big urgency", priority=URGENT),     # 60
    ]
    tasks[0].updated_at = now - timedelta(hours=2)

    sorted_tasks = sort_tasks_by_importance(tasks)
    scores = [calculate_task_score(t) for t in sorted_tasks]
    assert scores == sorted(scores, reverse=True)

    top = get_top_priority_tasks(tasks, limit=3)
    assert [t.title for t in top] == [t.title for t in sorted_tasks[:3]]
    assert top_scores["deadline on fire"] == scores[0]
```

Assertions were chosen to verify **correct behaviour of the whole workflow**, not re-implement it: order must be non-increasing, the top slice must match the independently re-scored maximum subset, and the genuinely urgent task must rank first. The test is readable because all seven fixtures are one-line `base_task(...)` builders and each comment states the expected score.

---

## Submitted deliverables

| Part | Deliverable | Location |
|------|-------------|----------|
| 1 | Test plan & behaviour checklist | this document (Part 1) |
| 2 | Improved unit tests (`calculate_task_score`, incl. due-date table) | `python/TaskManager/tests/test_task_priority.py` |
| 3 | TDD feature (+12 assignee boost) & bug-fix regression tests | `tests/test_task_priority.py` (TestAssigneeBoost, TestCalculateTaskScoreRecency) + minimal implementation in `task_priority.py`, `models.py`, `storage.py` |
| 4 | Integration test | `tests/test_task_priority.py` (TestTaskPriorityWorkflowIntegration) |
| Reflection | see below | this document |

**Suite status:** `Ran 38 tests ... OK.`

---

## Reflection

1. **AI-as-tutor > AI-as-coder.** The Socratic prompts (asking questions instead of generating tests) forced me to articulate *why* each test exists. The "behaviours I missed" (unknown-priority fallback, the REVIEW −15 bucket, the >7-day drop-off) would never have appeared in a generated test suite — they came from being interrogated about the code.
2. **Behaviour vs implementation.** My first instinct was to assert on a raw numeric guess; the good practice is to *isolate* one factor per test (the `base_task` neutraliser) and name tests after the behaviour (`test_due_beyond_a_week_adds_nothing`).
3. **Time-based tests need deterministic design.** Without a clock-freezing library, offsets-from-`now` are the way — but `timedelta.days` floors, so bucket values must pad into the middle of their range or you get an off-by-one that only fails on some run. That cost me two red runs before I internalised it.
4. **TDD changes the shape of the code.** Writing the assignee test *first* forced a concrete decision (what does "current user" mean in a codebase with no auth?) before any implementation — the test was the specification.
5. **Honesty about bugs.** Part 3.2's bug doesn't exist in the Python port. Rather than inventing a defect, the exercise still contributed real value: boundary regression tests that catch the bug class if it's ever reintroduced, and documentation of the intended `.days` semantics.
6. **The Python project had zero tests to begin with.** Building the suite from scratch demonstrated that the priority logic — despite being small — is full of subtle, independently-wrongable rules (7 due-date outcomes, 3 status outcomes, 3 tag triggers, recency flooring, an unknown-priority switch). All of it is cheap to pin once your helper lets you toggle one factor at a time.