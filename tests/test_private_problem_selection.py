import os
import sys
from datetime import datetime
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kouhai_bot import private_judge, problem_preparation
from kouhai_bot.problems import picker
from kouhai_bot.problems.date_filter import TZ


def test_private_random_problem_obeys_global_contest_date_range(
    tmp_path,
    monkeypatch,
):
    problems = [
        {"contestId": 1, "index": "A", "rating": 2200, "tags": []},
        {"contestId": 2, "index": "B", "rating": 2200, "tags": []},
    ]
    start_times = {
        1: int(datetime(2019, 1, 1, tzinfo=TZ).timestamp()),
        2: int(datetime(2024, 1, 1, tzinfo=TZ).timestamp()),
    }
    monkeypatch.setattr(
        private_judge,
        "get_config",
        lambda: SimpleNamespace(data_dir=str(tmp_path)),
    )
    monkeypatch.setattr(private_judge, "_fetch_problemset", lambda: problems)
    monkeypatch.setattr(private_judge, "_ensure_statement", lambda _problem: {"description": "ok"})
    monkeypatch.setattr(private_judge.random, "shuffle", lambda _items: None)
    monkeypatch.setattr(
        problem_preparation,
        "effective_rating_range",
        lambda _group_id: (2000, 2400),
    )
    monkeypatch.setattr(
        problem_preparation,
        "effective_contest_date_range",
        lambda _group_id: ("2023-01-01", "2025-12-31"),
    )
    monkeypatch.setattr(
        picker,
        "_get_cached_contest_start_times",
        lambda: start_times,
    )

    selected = private_judge.resolve_random_problem(123)

    assert selected["today"] == "2B"
