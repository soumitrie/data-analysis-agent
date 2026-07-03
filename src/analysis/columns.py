"""Deterministic column-role detection.

Best-guess heuristics assign each column a role — date / amount / category /
counterparty — and build a human-readable assumption note. The engine never
interrogates the user; it states its interpretation and proceeds.
"""
from __future__ import annotations

import pandas as pd
from pandas.api import types as pdt

_DATE_NAME_HINTS = ("date", "time", "day", "timestamp", "posted", "settle")
_AMOUNT_NAME_HINTS = ("amount", "value", "total", "sum", "price", "debit", "credit", "balance", "usd")
_CATEGORY_NAME_HINTS = ("category", "type", "class", "kind", "status", "segment", "channel")
_COUNTERPARTY_NAME_HINTS = (
    "counterparty", "payee", "merchant", "vendor", "customer", "client",
    "account", "party", "name", "beneficiary", "entity",
)
_ID_NAME_HINTS = ("id", "ref", "number", "no", "code", "txn_id", "uuid")


def _name_matches(name: str, hints: tuple[str, ...]) -> bool:
    low = name.lower()
    return any(h in low for h in hints)


def is_date_like(series: pd.Series, name: str = "") -> bool:
    if pdt.is_datetime64_any_dtype(series):
        return True
    non_null = series.dropna()
    if non_null.empty:
        return False
    sample = non_null.head(2000)
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    frac = float(parsed.notna().mean())
    threshold = 0.6 if _name_matches(name, _DATE_NAME_HINTS) else 0.8
    return frac >= threshold


def pick_date_column(df: pd.DataFrame) -> str | None:
    named = [c for c in df.columns if _name_matches(str(c), _DATE_NAME_HINTS) and is_date_like(df[c], str(c))]
    if named:
        return str(named[0])
    for c in df.columns:
        if is_date_like(df[c], str(c)):
            return str(c)
    return None


def _is_id_like(df: pd.DataFrame, col: str) -> bool:
    """A near-unique column (e.g. txn_id) — an identifier, not an amount/category."""
    n = len(df)
    if n == 0:
        return False
    return df[col].nunique(dropna=True) >= 0.95 * n


def _is_int_id(df: pd.DataFrame, col: str) -> bool:
    """A near-unique INTEGER column looks like a sequential identifier. Float
    columns (e.g. signed amounts) are never treated as ids."""
    return pdt.is_integer_dtype(df[col]) and _is_id_like(df, col)


def pick_amount_column(df: pd.DataFrame, exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    numeric = [
        str(c) for c in df.columns
        if c not in exclude and pdt.is_numeric_dtype(df[c]) and not _is_int_id(df, c)
    ]
    if not numeric:
        return None
    named = [c for c in numeric if _name_matches(c, _AMOUNT_NAME_HINTS)]
    candidates = named or numeric

    def score(col: str) -> tuple[int, float]:
        series = df[col].dropna()
        has_negative = 1 if (series < 0).any() else 0
        spread = float(series.std()) if len(series) > 1 else 0.0
        return (has_negative, spread)

    return max(candidates, key=score)


def _string_columns(df: pd.DataFrame, exclude: set[str]) -> list[str]:
    out = []
    for c in df.columns:
        if c in exclude:
            continue
        if pdt.is_numeric_dtype(df[c]) or pdt.is_datetime64_any_dtype(df[c]):
            continue
        if is_date_like(df[c], str(c)):
            continue
        out.append(str(c))
    return out


def pick_category_column(df: pd.DataFrame, exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    n = len(df)
    cap = max(20, int(0.05 * n)) if n else 20
    candidates = []
    for c in _string_columns(df, exclude):
        card = df[c].nunique(dropna=True)
        if 2 <= card <= cap:
            candidates.append((c, card))
    if not candidates:
        return None
    named = [(c, card) for c, card in candidates if _name_matches(c, _CATEGORY_NAME_HINTS)]
    pool = named or candidates
    # lowest cardinality among the pool is the most "category-like"
    return min(pool, key=lambda t: t[1])[0]


def pick_counterparty_column(df: pd.DataFrame, exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    candidates = []
    for c in _string_columns(df, exclude):
        if _is_id_like(df, c):
            continue
        card = df[c].nunique(dropna=True)
        if card >= 2:
            candidates.append((c, card))
    if not candidates:
        return None
    named = [(c, card) for c, card in candidates if _name_matches(c, _COUNTERPARTY_NAME_HINTS)]
    pool = named or candidates
    # highest cardinality among the pool is the most "counterparty-like"
    return max(pool, key=lambda t: t[1])[0]


def _quote(name: str | None) -> str:
    return f"'{name}'" if name else "none"


def build_assumption_note(mapping: dict) -> str:
    parts = []
    if mapping.get("date"):
        parts.append(f"{_quote(mapping['date'])} as the transaction date")
    if mapping.get("amount"):
        parts.append(f"{_quote(mapping['amount'])} as the signed transaction amount")
    if mapping.get("category"):
        parts.append(f"{_quote(mapping['category'])} as the transaction category")
    if mapping.get("counterparty"):
        parts.append(f"{_quote(mapping['counterparty'])} as the counterparty")
    if not parts:
        return "No standard transaction columns were confidently detected; charts use best-guess roles."
    body = "; ".join(parts)
    return (
        f"Interpreted {body}. These roles were auto-detected from the column names and "
        f"values — no configuration was required. Charts assume these roles."
    )


def detect_roles(df: pd.DataFrame, profile: dict | None = None) -> dict:
    """Assign the four roles + assumption note. `profile` is accepted for
    interface symmetry (spec/agent.md) but detection reads the DataFrame."""
    date_col = pick_date_column(df)
    used: set[str] = {date_col} if date_col else set()

    amount_col = pick_amount_column(df, exclude=used)
    if amount_col:
        used.add(amount_col)

    category_col = pick_category_column(df, exclude=used)
    if category_col:
        used.add(category_col)

    counterparty_col = pick_counterparty_column(df, exclude=used)

    mapping = {
        "date": date_col,
        "amount": amount_col,
        "category": category_col,
        "counterparty": counterparty_col,
    }
    mapping["assumption_note"] = build_assumption_note(mapping)
    return mapping
