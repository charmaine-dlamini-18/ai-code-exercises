"""Tests for the task priority workflow (calculate_task_score, sort_tasks_by_importance, get_top_priority_tasks).

Run from the TaskManager directory:
    python -m unittest discover -s tests -v

The tests build tasks with deterministic time offsets (relative to datetime.now())
instead of freezing the clock, so they never depend on the time of day they run.
"""
import unittest
from datetime import datetime, timedelta

from models import Task, TaskPriority, TaskStatus
from task_priority import (
    calculate_task_score,
    get_top_priority_tasks,
    sort_tasks_by_importance,
)

# Must match the CURRENT_USER_ID introduced in task_priority.py by the feature.
CURRENT_USER = "current-user"


def base_task(**overrides):
    """Create a task with all score modifiers neutralised.

    - TODO status (no penalty)
    - no due date (no due bonus)
    - no tags (no tag boost)
    - updated 2 days ago (no recent-update boost)

    `assigned_to` is applied as an attribute (not a constructor kwarg) so the
    tests keep working before/after the assignee feature lands (TDD).
    """
    defaults = {
        "title": "test task",
        "priority": TaskPriority.MEDIUM,
        "due_date": None,
        "tags": None,
    }
    defaults.update(overrides)
    assigned_to = defaults.pop("assigned_to", None)
    task = Task(**defaults)
    task.status = TaskStatus.TODO
    task.updated_at = datetime.now() - timedelta(days=2)
    if assigned_to is not None:
        task.assigned_to = assigned_to
    return task


class TestCalculateTaskScoreBase(unittest.TestCase):
    def test_low_priority_scores_10(self):
        self.assertEqual(calculate_task_score(base_task(priority=TaskPriority.LOW)), 10)

    def test_medium_priority_scores_20(self):
        self.assertEqual(calculate_task_score(base_task(priority=TaskPriority.MEDIUM)), 20)

    def test_high_priority_scores_40(self):
        self.assertEqual(calculate_task_score(base_task(priority=TaskPriority.HIGH)), 40)

    def test_urgent_priority_scores_60(self):
        self.assertEqual(calculate_task_score(base_task(priority=TaskPriority.URGENT)), 60)

    def test_unknown_priority_scores_zero(self):
        task = base_task()
        task.priority = "bogus"
        self.assertEqual(calculate_task_score(task), 0)


class TestCalculateTaskScoreDueDate(unittest.TestCase):
    """Exercise 2.2: due date buckets are tested with offsets relative to now."""

    def test_no_due_date_adds_nothing(self):
        self.assertEqual(calculate_task_score(base_task(due_date=None)), 20)

    def test_overdue_task_adds_35(self):
        task = base_task(due_date=datetime.now() - timedelta(days=1))
        self.assertEqual(calculate_task_score(task), 20 + 35)

    def test_due_today_adds_20(self):
        task = base_task(due_date=datetime.now() + timedelta(hours=5))
        self.assertEqual(calculate_task_score(task), 20 + 20)

    def test_due_within_two_days_adds_15(self):
        # 42h away -> (due - now).days == 1, which is <= 2
        task = base_task(due_date=datetime.now() + timedelta(days=1, hours=18))
        self.assertEqual(calculate_task_score(task), 20 + 15)

    def test_due_within_a_week_adds_10(self):
        # 84h away -> (due - now).days == 3, which is <= 7
        task = base_task(due_date=datetime.now() + timedelta(days=3, hours=12))
        self.assertEqual(calculate_task_score(task), 20 + 10)

    def test_due_beyond_a_week_adds_nothing(self):
        # 9 days away -> (due - now).days == 8, which is > 7
        task = base_task(due_date=datetime.now() + timedelta(days=9))
        self.assertEqual(calculate_task_score(task), 20)


class TestCalculateTaskScoreStatus(unittest.TestCase):
    def test_done_status_subtracts_50(self):
        task = base_task()
        task.status = TaskStatus.DONE
        self.assertEqual(calculate_task_score(task), 20 - 50)

    def test_review_status_subtracts_15(self):
        task = base_task()
        task.status = TaskStatus.REVIEW
        self.assertEqual(calculate_task_score(task), 20 - 15)

    def test_in_progress_has_no_penalty(self):
        task = base_task()
        task.status = TaskStatus.IN_PROGRESS
        self.assertEqual(calculate_task_score(task), 20)


class TestCalculateTaskScoreTags(unittest.TestCase):
    def test_blocker_tag_adds_8(self):
        self.assertEqual(calculate_task_score(base_task(tags=["blocker"])), 20 + 8)

    def test_critical_tag_adds_8(self):
        self.assertEqual(calculate_task_score(base_task(tags=["critical"])), 20 + 8)

    def test_urgent_tag_adds_8(self):
        self.assertEqual(calculate_task_score(base_task(tags=["urgent"])), 28)

    def test_unrelated_tags_add_nothing(self):
        self.assertEqual(calculate_task_score(base_task(tags=["feature", "work"])), 20)

    def test_empty_tags_add_nothing(self):
        self.assertEqual(calculate_task_score(base_task(tags=[])), 20)


class TestCalculateTaskScoreRecency(unittest.TestCase):
    """Exercise 3.2 regression pin: 'days since update' uses timedelta.days.

    A millisecond-division port (like the JS/Java bug described in Exercise 3.2)
    would give .days() == 0 for ANY update younger than ~24h wall time, but here we
    pin the exact floored-day behaviour:
    - updated 23h ago -> 0 days -> +5 boost
    - updated 25h ago -> 1 day  -> no boost
    """

    def test_updated_23_hours_ago_gets_boost(self):
        task = base_task()
        task.updated_at = datetime.now() - timedelta(hours=23)
        self.assertEqual(calculate_task_score(task), 25)

    def test_updated_25_hours_ago_gets_no_boost(self):
        task = base_task()
        task.updated_at = datetime.now() - timedelta(hours=25)
        self.assertEqual(calculate_task_score(task), 20)

    def test_brand_new_task_gets_boost(self):
        self.assertEqual(calculate_task_score(Task("fresh")), 25)


class TestAssigneeBoost(unittest.TestCase):
    """Exercise 3.1 (TDD): tasks assigned to the current user get +12."""

    def test_task_assigned_to_current_user_gets_plus_12(self):
        mine = base_task(assigned_to=CURRENT_USER)
        theirs = base_task(assigned_to="someone-else")
        self.assertEqual(calculate_task_score(mine), calculate_task_score(theirs) + 12)
        self.assertEqual(calculate_task_score(mine), 32)

    def test_task_assigned_to_someone_else_gets_no_boost(self):
        self.assertEqual(calculate_task_score(base_task(assigned_to="someone-else")), 20)

    def test_unassigned_task_gets_no_boost(self):
        self.assertEqual(calculate_task_score(base_task(assigned_to=None)), 20)


class TestCombinedFactors(unittest.TestCase):
    def test_all_positive_factors_accumulate(self):
        task = base_task(
            title="critical urgent overdue",
            priority=TaskPriority.URGENT,
            due_date=datetime.now() - timedelta(days=1),
            tags=["critical"],
            assigned_to=CURRENT_USER,
        )
        task.updated_at = datetime.now() - timedelta(hours=2)
        self.assertEqual(calculate_task_score(task), 60 + 35 + 8 + 12 + 5)

    def test_done_overdue_task_is_heavily_penalised(self):
        task = base_task(
            title="finished late",
            priority=TaskPriority.URGENT,
            due_date=datetime.now() - timedelta(days=3),
        )
        task.status = TaskStatus.DONE
        self.assertEqual(calculate_task_score(task), 60 + 35 - 50)


class TestSortTasksByImportance(unittest.TestCase):
    def test_sorts_highest_score_first(self):
        low = base_task(title="low", priority=TaskPriority.LOW)
        urgent = base_task(title="urgent", priority=TaskPriority.URGENT)
        medium = base_task(title="medium", priority=TaskPriority.MEDIUM)
        result = sort_tasks_by_importance([medium, low, urgent])
        self.assertEqual([t.title for t in result], ["urgent", "medium", "low"])

    def test_empty_list_returns_empty(self):
        self.assertEqual(sort_tasks_by_importance([]), [])

    def test_single_task_is_returned(self):
        task = base_task()
        self.assertEqual(sort_tasks_by_importance([task]), [task])

    def test_stable_for_equal_scores(self):
        first = base_task(title="first")
        second = base_task(title="second")
        result = sort_tasks_by_importance([first, second, first])
        self.assertEqual([t.title for t in result], ["first", "second", "first"])

    def test_does_not_mutate_input(self):
        tasks = [base_task(title="a"), base_task(title="b")]
        before = list(tasks)
        sort_tasks_by_importance(tasks)
        self.assertEqual(tasks, before)


class TestGetTopPriorityTasks(unittest.TestCase):
    def test_returns_top_n(self):
        urgent = base_task(title="u", priority=TaskPriority.URGENT)
        high = base_task(title="h", priority=TaskPriority.HIGH)
        low = base_task(title="l", priority=TaskPriority.LOW)
        result = get_top_priority_tasks([low, high, urgent], limit=2)
        self.assertEqual([t.title for t in result], ["u", "h"])

    def test_default_limit_is_five(self):
        tasks = [base_task(title=f"t{i}") for i in range(7)]
        self.assertEqual(len(get_top_priority_tasks(tasks)), 5)

    def test_limit_larger_than_list_returns_all(self):
        tasks = [base_task(title="a"), base_task(title="b")]
        self.assertEqual(len(get_top_priority_tasks(tasks, limit=10)), 2)

    def test_limit_zero_returns_empty(self):
        self.assertEqual(get_top_priority_tasks([base_task()], limit=0), [])


class TestTaskPriorityWorkflowIntegration(unittest.TestCase):
    """Exercise 4.1: calculate + sort + top-N compose into one workflow.

    Mix realistic tasks with overlapping factors so we can not only check order but also
    verify the exact top slice by re-deriving scores independently.
    """

    def test_full_workflow_ranks_expected_tasks(self):
        tasks = [
            base_task(title="deadline on fire",
                      priority=TaskPriority.URGENT,
                      due_date=datetime.now() - timedelta(days=1),
                      tags=["critical"],
                      assigned_to=CURRENT_USER),      # 120: 60+35+8+12+5
            base_task(title="due today",
                      priority=TaskPriority.HIGH,
                      due_date=datetime.now() + timedelta(hours=5)),   # 40+20=60
            base_task(title="due soon",
                      priority=TaskPriority.MEDIUM,
                      due_date=datetime.now() + timedelta(days=3, hours=12)),   # 20+10=30
            base_task(title="finished old", priority=TaskPriority.HIGH),  # 40-50=-10
            base_task(title="quiet low", priority=TaskPriority.LOW),      # 10
            base_task(title="plain medium"),                              # 20
            base_task(title="big urgency", priority=TaskPriority.URGENT), # 60
        ]
        tasks[0].updated_at = datetime.now() - timedelta(hours=2)  # 2h ago == 0 days, still+5

        sorted_tasks = sort_tasks_by_importance(tasks)
        scores = [calculate_task_score(t) for t in sorted_tasks]
        self.assertEqual(scores, sorted(scores, reverse=True),
                         "sort_tasks_by_importance must return non-increasing scores")

        top = get_top_priority_tasks(tasks, limit=3)
        self.assertEqual([t.title for t in top], [t.title for t in sorted_tasks[:3]])

        top_scores = {t.title: calculate_task_score(t) for t in top}
        self.assertEqual(set(top_scores.values()), set(sorted(scores, reverse=True)[:3]))
        self.assertEqual(top_scores["deadline on fire"], scores[0])

    def test_workflow_handles_empty_input(self):
        self.assertEqual(get_top_priority_tasks([]), [])
        self.assertEqual(sort_tasks_by_importance([]), [])


if __name__ == "__main__":
    unittest.main()