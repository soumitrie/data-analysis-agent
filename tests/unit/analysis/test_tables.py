"""Aggregated-table serializer — JSON-safe cells, no raw rows. No LLM key."""
import math

import numpy as np

from analysis.tables import make_table


def test_make_table_coerces_numpy_and_floats():
    table = make_table(
        ["Period", "Total amount"],
        [["2024-01-31", np.float64(1234.5)], ["2024-02-29", np.int64(7)]],
    )
    assert table["columns"] == ["Period", "Total amount"]
    assert table["rows"] == [["2024-01-31", 1234.5], ["2024-02-29", 7]]
    # every cell is a native JSON-safe scalar
    for row in table["rows"]:
        for cell in row:
            assert isinstance(cell, (str, int, float))


def test_make_table_sanitizes_nan_inf():
    table = make_table(["k", "v"], [["a", float("nan")], ["b", math.inf]])
    assert table["rows"] == [["a", 0.0], ["b", 0.0]]


def test_make_table_headers_are_strings():
    table = make_table([1, 2], [[10, 20]])
    assert table["columns"] == ["1", "2"]
