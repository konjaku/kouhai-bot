import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kouhai_bot.problems.date_filter import (
    TZ,
    contest_timestamp_in_range,
    normalize_contest_date_range,
)


def test_year_range_expands_to_inclusive_full_years():
    assert normalize_contest_date_range("2016", "2018") == (
        "2016-01-01",
        "2018-12-31",
    )


def test_exact_date_range_is_preserved():
    assert normalize_contest_date_range("2023-04-05", "2024-06-07") == (
        "2023-04-05",
        "2024-06-07",
    )


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [
        ("2024-02-30", "2025"),
        ("2024-1-01", "2025"),
        ("2025", "2024"),
    ],
)
def test_invalid_or_reversed_date_ranges_are_rejected(minimum, maximum):
    with pytest.raises(ValueError):
        normalize_contest_date_range(minimum, maximum)


def test_contest_timestamp_range_uses_asia_shanghai_calendar_date():
    timestamp = int(datetime(2020, 1, 1, 0, 30, tzinfo=TZ).timestamp())

    assert contest_timestamp_in_range(
        timestamp,
        "2020-01-01",
        "2020-01-01",
    )
    assert not contest_timestamp_in_range(
        timestamp,
        "2019-12-31",
        "2019-12-31",
    )
