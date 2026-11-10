import json
import os
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from kouhai_bot.problems import picker


@pytest.fixture(autouse=True)
def _restore_picker_state():
    original_state_dir = picker.STATE_DIR
    original_group = picker.CURRENT_GROUP
    original_rating = (picker.RATING_MIN, picker.RATING_MAX)
    original_dates = (picker.CONTEST_DATE_MIN, picker.CONTEST_DATE_MAX)
    yield
    picker.STATE_DIR = original_state_dir
    picker.CACHE_DIR = os.path.join(original_state_dir, "statements")
    picker.GROUPS_DIR = os.path.join(original_state_dir, "groups")
    picker._set_group(original_group)
    picker._set_rating_range(*original_rating)
    picker._set_contest_date_range(*original_dates)


def _problem(contest_id: int, index: str) -> dict:
    return {"contestId": contest_id, "index": index, "rating": 2200}


def _configure_picker_tmp(tmp_path):
    data_dir = tmp_path / "data"
    picker._set_state_dir(str(data_dir))
    picker._set_group("g1")
    group_dir = data_dir / "groups" / "g1"
    group_dir.mkdir(parents=True)
    return data_dir, group_dir



def test_set_state_dir_updates_all_picker_storage_paths(tmp_path):
    data_dir, group_dir = _configure_picker_tmp(tmp_path)

    assert picker.STATE_DIR == str(data_dir)
    assert picker.CACHE_DIR == str(data_dir / "statements")
    assert picker.GROUPS_DIR == str(data_dir / "groups")
    assert picker._state_file() == str(group_dir / "state.json")
    assert picker._used_file() == str(group_dir / "used.json")
    assert picker._scoreboard_file() == str(group_dir / "scoreboard.json")
    assert picker._cache_path("123A") == str(data_dir / "statements" / "123A.json")
    assert picker._cache_all_path() == str(
        data_dir
        / f"cf_all_{picker.RATING_MIN}_{picker.RATING_MAX}_any_any.json"
    )


def test_target_cache_path_is_bound_to_date_range(tmp_path):
    data_dir, _group_dir = _configure_picker_tmp(tmp_path)
    picker._set_contest_date_range("2016", "2018")

    assert picker._cache_all_path() == str(
        data_dir
        / f"cf_all_{picker.RATING_MIN}_{picker.RATING_MAX}_2016-01-01_2018-12-31.json"
    )


def test_fetch_targets_filters_by_real_contest_start_date(monkeypatch, tmp_path):
    _configure_picker_tmp(tmp_path)
    picker._set_rating_range(2000, 2400)
    picker._set_contest_date_range("2020", "2021")
    problems = [
        _problem(1, "A"),
        _problem(2, "B"),
        _problem(3, "C"),
        _problem(999, "D"),
    ]
    start_times = {
        1: int(datetime(2019, 12, 31, tzinfo=picker.TZ).timestamp()),
        2: int(datetime(2020, 6, 1, tzinfo=picker.TZ).timestamp()),
        3: int(datetime(2022, 1, 1, tzinfo=picker.TZ).timestamp()),
    }
    monkeypatch.setattr(
        picker,
        "_fetch_cf_api",
        lambda _url: {"problems": problems},
    )
    monkeypatch.setattr(
        picker,
        "_get_cached_contest_start_times",
        lambda: start_times,
    )

    targets = picker._fetch_and_cache_targets()

    assert [picker._problem_id(problem) for problem in targets] == ["2B"]
    assert targets[0]["contestDate"] == "2020-06-01"


def test_fetch_targets_without_date_filter_does_not_load_contest_list(
    monkeypatch,
    tmp_path,
):
    _configure_picker_tmp(tmp_path)
    picker._set_rating_range(2000, 2400)
    picker._set_contest_date_range("", "")
    monkeypatch.setattr(
        picker,
        "_fetch_cf_api",
        lambda _url: {"problems": [_problem(1, "A")]},
    )
    contest_loader = pytest.fail
    monkeypatch.setattr(
        picker,
        "_get_cached_contest_start_times",
        lambda: contest_loader("contest list must not be loaded"),
    )

    targets = picker._fetch_and_cache_targets()

    assert [picker._problem_id(problem) for problem in targets] == ["1A"]


def test_select_problem_excludes_scoreboard_solves_when_used_is_missing(monkeypatch, tmp_path):
    _data_dir, group_dir = _configure_picker_tmp(tmp_path)
    (group_dir / "scoreboard.json").write_text(json.dumps({
        "solves": [{"problem": "1A"}],
        "user_submissions": {},
    }))
    monkeypatch.setattr(picker, "_get_cached_targets", lambda: [_problem(1, "A"), _problem(2, "B")])
    monkeypatch.setattr(picker.random, "choice", lambda seq: seq[0])

    selected = picker.select_problem()

    assert picker._problem_id(selected) == "2B"


def test_select_problem_resets_used_but_keeps_solved_excluded(monkeypatch, tmp_path):
    _data_dir, group_dir = _configure_picker_tmp(tmp_path)
    (group_dir / "scoreboard.json").write_text(json.dumps({
        "solves": [{"problem": "1A"}],
        "user_submissions": {},
    }))
    (group_dir / "used.json").write_text(json.dumps(["2B"]))
    monkeypatch.setattr(picker, "_get_cached_targets", lambda: [_problem(1, "A"), _problem(2, "B")])
    monkeypatch.setattr(picker.random, "choice", lambda seq: seq[0])

    selected = picker.select_problem()

    assert picker._problem_id(selected) == "2B"
    assert json.loads((group_dir / "used.json").read_text()) == []


def test_select_problem_excludes_current_when_used_is_missing(monkeypatch, tmp_path):
    _data_dir, group_dir = _configure_picker_tmp(tmp_path)
    (group_dir / "state.json").write_text(json.dumps({"today": "1A"}))
    monkeypatch.setattr(
        picker,
        "_get_cached_targets",
        lambda: [_problem(1, "A"), _problem(2, "B")],
    )
    monkeypatch.setattr(picker.random, "choice", lambda seq: seq[0])

    selected = picker.select_problem()

    assert picker._problem_id(selected) == "2B"


def test_select_problem_reset_keeps_current_excluded(monkeypatch, tmp_path):
    _data_dir, group_dir = _configure_picker_tmp(tmp_path)
    (group_dir / "state.json").write_text(json.dumps({"today": "1A"}))
    (group_dir / "used.json").write_text(json.dumps(["2B"]))
    monkeypatch.setattr(
        picker,
        "_get_cached_targets",
        lambda: [_problem(1, "A"), _problem(2, "B")],
    )
    monkeypatch.setattr(picker.random, "choice", lambda seq: seq[0])

    selected = picker.select_problem()

    assert picker._problem_id(selected) == "2B"
    assert json.loads((group_dir / "used.json").read_text()) == []


def test_select_problem_raises_when_every_candidate_is_solved(monkeypatch, tmp_path):
    _data_dir, group_dir = _configure_picker_tmp(tmp_path)
    (group_dir / "scoreboard.json").write_text(json.dumps({
        "solves": [{"problem": "1A"}, {"problem": "2B"}],
        "user_submissions": {},
    }))
    monkeypatch.setattr(picker, "_get_cached_targets", lambda: [_problem(1, "A"), _problem(2, "B")])

    with pytest.raises(RuntimeError, match="No unsolved problems"):
        picker.select_problem()


def test_fetch_statement_retries_after_parse_failure(monkeypatch, tmp_path):
    """A first attempt that yields an unusable page (challenge/redirect
    variant) must be retried once before giving up."""
    _configure_picker_tmp(tmp_path)
    fetch_calls = []
    process_calls = []

    raw_html = (
        '<div class="problem-statement">'
        '<div class="title">A. Retry</div>'
        '<div class="time-limit">1 second</div>'
        '<div class="memory-limit">256 megabytes</div>'
        '<div class="section-title">Input</div>n'
        '<div class="sample-test">'
        '<div class="input"><pre>1</pre></div>'
        '<div class="output"><pre>1</pre></div>'
        '</div>'
        "</div><script"
    )

    def fake_fetch(url):
        fetch_calls.append(url)
        return raw_html

    def fake_process(contest_id, index, vl_backend="none", *, html=None):
        process_calls.append((contest_id, index, html))
        if len(process_calls) == 1:
            return {"error": "Could not find problem-statement div", "pid": f"{contest_id}{index}"}
        return {
            "pid": f"{contest_id}{index}",
            "text": "Statement",
            "formulas_found": 0,
            "graphics_found": 0,
            "images": [],
        }

    monkeypatch.setattr(picker.cf_fetcher, "fetch_html", fake_fetch)
    monkeypatch.setattr(picker.cf_statement, "process_problem", fake_process)

    stmt = picker.fetch_statement(_problem(1, "A"))

    assert stmt is not None
    assert len(fetch_calls) == 2
    assert len(process_calls) == 2
    assert stmt["samples"] == [{"input": "1", "output": "1"}]


def test_fetch_statement_gives_up_after_second_parse_failure(monkeypatch, tmp_path):
    _configure_picker_tmp(tmp_path)
    fetch_calls = []

    def fake_fetch(url):
        fetch_calls.append(url)
        return "<html>homepage</html>"

    def fake_process(contest_id, index, vl_backend="none", *, html=None):
        return {"error": "Could not find problem-statement div", "pid": f"{contest_id}{index}"}

    monkeypatch.setattr(picker.cf_fetcher, "fetch_html", fake_fetch)
    monkeypatch.setattr(picker.cf_statement, "process_problem", fake_process)

    stmt = picker.fetch_statement(_problem(1, "A"))

    assert stmt is None
    assert len(fetch_calls) == 2


def test_fetch_statement_caches_image_metadata(monkeypatch, tmp_path):
    _configure_picker_tmp(tmp_path)

    raw_html = (
        '<div class="problem-statement">'
        '<div class="title">A. Image</div>'
        '<div class="time-limit">1 second</div>'
        '<div class="memory-limit">256 megabytes</div>'
        '<div class="section-title">Input</div>n'
        '<pre>1</pre><pre>1</pre>'
        "</div><script"
    )
    fetch_calls = []
    process_calls = []

    def fake_fetch(url):
        fetch_calls.append(url)
        return raw_html

    def fake_process(contest_id, index, vl_backend="none", *, html=None):
        process_calls.append((contest_id, index, vl_backend, html))
        return {
            "pid": f"{contest_id}{index}",
            "text": "Statement [DIAGRAM]",
            "formulas_found": 0,
            "graphics_found": 1,
            "images": [{"src": "https://codeforces.com/image.png", "kind": "graphic"}],
        }

    monkeypatch.setattr(picker.cf_fetcher, "fetch_html", fake_fetch)
    monkeypatch.setattr(picker.cf_statement, "process_problem", fake_process)

    stmt = picker.fetch_statement(_problem(1, "A"))

    assert fetch_calls == ["https://codeforces.com/problemset/problem/1/A"]
    assert process_calls == [(1, "A", "none", raw_html)]
    assert stmt["images"] == [{"src": "https://codeforces.com/image.png", "kind": "graphic"}]
    assert stmt["has_images"] is True
    assert stmt["_images_collected"] is True


def test_picker_cli_reveal_reads_configured_data_dir(tmp_path):
    data_dir = tmp_path / "custom-data"
    group_dir = data_dir / "groups" / "g1"
    group_dir.mkdir(parents=True)
    (group_dir / "state.json").write_text(json.dumps({
        "today": "123A",
        "name": "Custom State",
        "rating": 2400,
    }))
    env = {**os.environ, "HOME": str(tmp_path / "home")}
    script = os.path.join(
        os.path.dirname(__file__), "..", "src", "kouhai_bot", "problems", "picker.py"
    )

    result = subprocess.run(
        [
            sys.executable,
            script,
            "reveal",
            "--group",
            "g1",
            "--data-dir",
            str(data_dir),
        ],
        check=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert "CF123A Custom State 2400" in result.stdout
