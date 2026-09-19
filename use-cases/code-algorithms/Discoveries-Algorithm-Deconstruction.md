# Exercise: Algorithm Deconstruction Challenge — Findings

Language: **Python**
Algorithm chosen: **Algorithm 1 — Task Priority Sorting and Filtering**
Starter file: `code-algorithms/python/TaskManager/task_priority.py`
Prompt approach: "Prompt 1: Understand an Algorithm Through Step-by-Step Analysis" (+ elements of Prompt 3 for control flow)

---

## 1. The Algorithm at a Glance

**What it does:** Ranks tasks by a calculated numeric "importance score" so the most urgent work surfaces first.

- `calculate_task_score(task)` -> int — a weighted scoring function combining priority, due-date proximity, status, tags, and recency of update.
- `sort_tasks_by_importance(tasks)` -> list — sorts tasks highest score first.
- `get_top_priority_tasks(tasks, limit=5)` -> list — returns the top N.

**Pattern used:** *Decorate–Sort–Undecorate* (DSUS): build `(score, task)` pairs, sort by the score, then strip the scores off.

---

## 2. Step-by-Step Deconstruction (as explained via the AI prompt)

### 2.1 `calculate_task_score` — five weighted factors

| Section | Code | Effect on score |
|---|---|---|
| Base priority weight | `priority_weights.get(priority, 0) * 10` | LOW=10, MEDIUM=20, HIGH=40, URGENT=60 |
| Due-date proximity | buckets on `days_until_due` | overdue +35, today +20, ≤2 days +15, ≤7 days +10, no due date +0 |
| Status penalty | `DONE` / `REVIEW` | DONE −50, REVIEW −15 |
| Tag keyword hit | any of `blocker`, `critical`, `urgent` | +8 |
| Recency | updated `< 1` day ago | +5 |

**Key design idea:** this is a *weighted scoring heuristic* — not a rule engine. Every factor nudges the score, and the weights encode **business priority**: an overdue low-priority task (10 + 35 = 45) deliberately outranks a medium-priority task with no deadline (20).

### 2.2 Worked example with concrete values

```
Task A: URGENT, due today, tag "critical", updated 5h ago, IN_PROGRESS
   60 (priority) + 20 (today) + 8 (tag) + 5 (recent)            = 93
Task D: HIGH, due in 5 days, tag "blocker", REVIEW
   40 (priority) + 10 (≤7 days) + 8 (tag) − 15 (review)         = 43
Task B: LOW, no due date, no tags, updated 3 days ago, TODO
   10 (priority)                                               = 10
Task C: MEDIUM, overdue 3 days, DONE
   20 (priority) + 35 (overdue) − 50 (done)                    =  5
```

Result order: **A (93) → D (43) → B (10) → C (5)**.

```
score(task) =
    weight(priority) × 10        base
  + bucket(due)                  urgency (overdue > today > 2d > 7d > none)
  − statusPenalty                done/review sink the task
  + 8 if tag in {blocker, critical, urgent}
  + 5 if updated < 24h           recency boost
```

### 2.3 `sort_tasks_by_importance` — the sorting core

```python
task_scores = [(calculate_task_score(task), task) for task in tasks]   # decorate
sorted_tasks = [task for _, task in sorted(task_scores, key=lambda x: x[0], reverse=True)]  # sort + undecorate
```

- **One-pass scoring:** scores are computed exactly once per task (not recomputed inside the sort comparator — that would be O(n log n) scoring calls).
- **`key=lambda x: x[0]` is important:** it sorts only on the score, and `sorted()` is *stable*, so equal scores keep input order. (Without the `key`, Python would compare the `Task` objects on ties and raise `TypeError` — the reference snippet in the exercise page omits `key`; the repo's Python version correctly includes it.)

### 2.4 Complexity

| Function | Time | Space |
|---|---|---|
| `calculate_task_score` | O(1) per task | O(1) |
| `sort_tasks_by_importance` | O(n) score + O(n log n) sort = **O(n log n)** | O(n) |
| `get_top_priority_tasks(limit=k)` | O(n log n) — full sort even for top k | O(n) |

### 2.5 Edge cases discovered while testing with the AI

- **Done urgent vs open low:** URGENT DONE = 60 − 50 = 10 ties LOW open = 10 — a *finished* urgent task can still tie an *open* trivial task.
- **Scores can go negative:** a DONE LOW task no due date = −40. Sorting still works, but a minus sign is unexpected.
- **Overdue is not graded:** any task overdue by 1 day or 100 days gets the same +35.
- **Default priority weights:** `get` falls back to 0 for a task without a known priority (base score 0).

---

## 3. Insights & Learning Points

1. **Heuristic scoring, not ranking rules.** The algorithm encodes "what should bubble to the top" as additive weights; tweaking one constant changes global behaviour — so the weights are the specification.
2. **Decorate–sort–undecorate** avoids recomputing the score during comparison and keeps the sort key simple.
3. **Stability matters:** using `key=` keeps ties deterministic (input order); comparing full tuples would crash on equal scores.
4. **Padding weight gaps:** Python's weights (HIGH=4, URGENT=6) differ from the JS/Java versions (HIGH=3, URGENT=4) — the same "specification" produces different rankings across languages. Worth flagging for consistency.
5. **`datetime.now()` is called up to 3 times per task** inside `calculate_task_score`; cheap, but slightly wasteful and non-atomic across calls.

---

## 4. Reflection Questions

**How did the AI's explanation change your understanding?**
The step-by-step breakdown reframed the function from "five if-statements adding numbers" into a deliberate *weighted heuristic*: each section maps to a business factor (priority, deadline urgency, status, tags, recency), and the weights reveal intent — e.g., overdue (+35) deliberately beats a whole priority tier (20-point gap between MEDIUM and HIGH).

**What aspects were still difficult after the AI explanation?**
Cross-language behaviour: the *same* algorithm produces different scores in Python vs JS/Java because the priority weights differ. Also the tie-breaking behaviour (`key=` vs tuple comparison) was subtle — I confirmed the repo's Python version handles it, while the exercise-page reference fragment would crash.

**How would you explain this to another junior developer?**
"Give every task points: base points for its priority, bonus points the closer its deadline is, penalty points if it's done or in review, small bonuses for critical tags and recent edits. Then sort by points, highest first. `get_top_priority_tasks` just slices the sorted list."

**Did you test this understanding against AI?** Yes — answered prompt-posed questions:
- *Which dominates: overdue or priority?* Overdue (+35) outweighs one priority tier: LOW overdue (45) beats MEDIUM without a deadline (20).
- *Stable ties?* Yes — with `key=`, equal scores keep input order; without it, `TypeError`.
- *Is full sort needed for top-5?* No — a heap-based partial sort is faster (see next section).

**How might you improve the algorithm?**
1. Use `heapq.nlargest(limit, tasks, key=calculate_task_score)` so top-N is **O(n log k)** not O(n log n).
2. Bucket overdue severity (e.g., +35, +45, +55 by how overdue) instead of a flat +35.
3. Snapshot `now = datetime.now()` once per call and reuse.
4. Expose the scoring weights as named module constants for maintainers; document the table.
5. Use set intersection for the tag check (`set(tags) & KEYWORD_TAGS`) to avoid a linear scan.
6. Guard/pin negative scores (e.g., floor at 0) if consumers assume non-negative.
7. Unify weight tables across Python/JS/Java so rankings are language-independent.
8. Add a `score_details` breakdown (or debug mode) returning the factor contributions for auditing how a task was ranked.

---

## 5. AI Prompt Used (filled in, for the personal prompt library)

> I'm trying to understand this algorithm/function in our codebase:
> [`task_priority.py` — `calculate_task_score`, `sort_tasks_by_importance`, `get_top_priority_tasks`]
>
> Based on my current understanding:
> 1. I think this function is trying to rank tasks by importance using a weighted scoring heuristic
> 2. The inputs seem to be a Task object with priority/due_date/status/tags/updated_at, and it returns an integer score
> 3. I'm particularly confused about why equal-score ties are handled via `key=lambda x: x[0]` rather than just sorting the tuples
>
> Could you help me understand this by:
> 1. Breaking down the algorithm into key sections with their purposes
> 2. Walking through a simple example execution with concrete values
> 3. Explaining the core technique/pattern being used here
> 4. Highlighting any non-obvious optimizations or tricks
>
> After your explanation, could you ask me 2-3 targeted questions that would test my understanding of this algorithm's:
> - Underlying principles
> - Edge cases
> - Performance characteristics