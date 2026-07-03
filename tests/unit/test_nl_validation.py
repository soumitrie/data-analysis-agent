"""Unit tests for the NL chart-spec validator (no LLM key required)."""
import json

import pytest

from graph.nodes import _parse_llm_json, _validate_nl_spec, build_nl_messages


FULL = {"date": "txn_date", "amount": "amount", "category": "category", "counterparty": "counterparty"}
NO_DATE = {"date": None, "amount": "amount", "category": "category", "counterparty": None}


# --------------------------------------------------------------------------- #
#  Lenient JSON parsing — the Gemini thinking model intermittently appends a
#  stray trailing brace / fences a JSON-mode reply. A VALID chart object must
#  still be recovered (so a chartable request is never wrongly declined), while
#  genuinely non-JSON garbage raises (→ graceful decline).
# --------------------------------------------------------------------------- #

def test_parse_clean_json_object():
    assert _parse_llm_json('{"chart": {"type": "distribution"}}') == {"chart": {"type": "distribution"}}


def test_parse_tolerates_trailing_extra_brace():
    """The exact artifact observed live: a complete object followed by a stray '}'."""
    text = '{\n  "chart": {\n    "type": "time_series",\n    "top_k": 8\n  }\n}\n}'
    assert _parse_llm_json(text) == {"chart": {"type": "time_series", "top_k": 8}}


def test_parse_strips_markdown_fence():
    assert _parse_llm_json('```json\n{"declined": true}\n```') == {"declined": True}


def test_parse_declined_object():
    assert _parse_llm_json('{"declined": true, "reason": "cannot map"}')["declined"] is True


def test_parse_non_json_prose_raises():
    with pytest.raises(ValueError):
        _parse_llm_json("I'm sorry, I can't help with that request.")


def test_parse_empty_raises():
    with pytest.raises(ValueError):
        _parse_llm_json("")


def test_valid_time_series_grouped_is_cleaned():
    spec = _validate_nl_spec(
        {"type": "time_series", "bucket": "month", "group_role": "category", "top_k": 8,
         "title": "T", "junk": "ignored"},
        FULL,
    )
    assert spec["type"] == "time_series"
    assert spec["bucket"] == "month"
    assert spec["group_role"] == "category"
    assert spec["top_k"] == 8
    assert "junk" not in spec


def test_unknown_type_rejected():
    assert _validate_nl_spec({"type": "pie"}, FULL) is None


def test_time_series_without_date_rejected():
    assert _validate_nl_spec({"type": "time_series"}, NO_DATE) is None


def test_group_role_absent_from_mapping_is_dropped_not_guessed():
    # counterparty not detected -> group_role dropped, chart stays ungrouped (valid)
    spec = _validate_nl_spec({"type": "time_series", "group_role": "counterparty"}, NO_DATE)
    assert spec is None  # no date anyway
    spec2 = _validate_nl_spec(
        {"type": "time_series", "group_role": "counterparty"},
        {"date": "txn_date", "amount": "amount", "category": "category", "counterparty": None},
    )
    assert spec2 is not None
    assert "group_role" not in spec2  # dropped, never guessed


def test_top_n_defaults_and_invalid_metric_coerced():
    spec = _validate_nl_spec({"type": "top_n_breakdown", "metric": "median"}, FULL)
    assert spec["metric"] == "sum"
    assert spec["top_n"] == 10
    assert spec["group_role"] in ("counterparty", "category")


def test_invalid_sign_coerced_to_all():
    spec = _validate_nl_spec({"type": "distribution", "sign": "sideways"}, FULL)
    assert spec["sign"] == "all"


def test_nl_messages_include_history_no_raw_rows():
    profile = {"row_count": 3, "columns": [], "date_range": {"start": None, "end": None},
               "amount_summary": None, "top_categories": []}
    history = [{"request_text": "monthly total", "chart_title": "Monthly Total", "declined": False}]
    system, user = build_nl_messages(profile, FULL, "and by category", history)
    parsed = json.loads(user)
    assert parsed["request"] == "and by category"
    assert parsed["history"][0]["request"] == "monthly total"
    assert parsed["history"][0]["resulted_in"] == "Monthly Total"
