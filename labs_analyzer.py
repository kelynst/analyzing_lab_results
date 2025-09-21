#!/usr/bin/env python3
"""
labs_analyzer.py  — with sex-specific reference ranges

What it does:
- Loads a CSV of lab results
- Cleans obvious issues (blank-only rows/cols, whitespace, duplicates)
- Infers common column names (PatientID vs patient_id, Test vs test_name, etc.)
- Normalizes date-like columns to ISO (YYYY-MM-DD)
- Applies reference ranges (sex-specific where provided) to flag out-of-range values
- Produces summary stats (overall + grouped) and saves them to CSV
- Generates a simple histogram chart per test (saved under ./outputs)

Usage (examples):
    python labs_analyzer.py sample_labs.csv
    python labs_analyzer.py sample_labs.csv --by test_name sex
    python labs_analyzer.py sample_labs.csv --no-charts
    python labs_analyzer.py sample_labs.csv --out-clean cleaned_demo.csv --out-flags flags_demo.csv --out-summary summary_demo.csv

Notes:
- This is a portfolio/learning tool. Reference ranges are demo-only (not clinical guidance).
"""

from __future__ import annotations

import argparse
import sys
import re
from pathlib import Path
from typing import Iterable, Optional, Tuple, Dict, List, Union

import pandas as pd
import matplotlib.pyplot as plt


# ----------------------------
# Basic configuration
# ----------------------------
DEFAULT_OUT_DIR = Path("outputs")
DEFAULT_SUMMARY_PREFIX = "summary_"
DEFAULT_CLEAN_PREFIX = "cleaned_"
DEFAULT_FLAGS_PREFIX = "flags_"

# Column name candidates for flexible matching
CANDIDATES = {
    "patient_id": ["patient_id", "patientid", "patient", "mrn", "member_id"],
    "sex": ["sex", "gender", "biological_sex"],
    "test_name": ["test", "test_name", "analyte", "labtest"],
    "value": ["value", "result", "result_value", "lab_value"],
    "units": ["units", "unit", "uom"],
    "date": ["date", "collection_date", "draw_date", "result_date"],
}

# Detect date-like columns by name pattern (heuristic)
DATE_PATTERNS = re.compile(
    r"\b(date|collection_date|draw_date|result_date|reported_date)\b",
    re.IGNORECASE,
)

# ------------------------------------------------------------------
# Demo reference ranges (very simplified; NOT for clinical use)
# Each test entry may be:
#   - a tuple (low, high, units)  -> unisex fallback
#   - a dict with sex keys {'M': (low, high, units), 'F': (...)} and
#     optionally a 'default' fallback tuple.
# ------------------------------------------------------------------
DEMO_RANGES: Dict[str, Union[
    Tuple[float, float, str],
    Dict[str, Tuple[float, float, str]]
]] = {
    # Hemoglobin: sex-specific
    "HGB": {
        "M": (13.5, 17.5, "g/dL"),
        "F": (12.0, 15.5, "g/dL"),
        "default": (12.0, 16.0, "g/dL"),  # fallback if sex missing/unknown
    },
    # White Blood Cell: unisex fallback
    "WBC": (4.0, 11.0, "10^9/L"),
    # Glucose (fasting): unisex fallback
    "GLU": (70, 99, "mg/dL"),
}


# ----------------------------
# Utility helpers
# ----------------------------
def _print_header(title: str) -> None:
    bar = "=" * 64
    print(f"\n{bar}\n{title}\n{bar}")


def _infer_col(df: pd.DataFrame, options: Iterable[str]) -> Optional[str]:
    """Return the first matching column (case-insensitive), or None if not found."""
    lowered = {c.lower(): c for c in df.columns}
    for opt in options:
        if opt.lower() in lowered:
            return lowered[opt.lower()]
    return None


def _find_date_columns(df: pd.DataFrame) -> List[str]:
    """Heuristically find date-like columns via name patterns."""
    date_cols = []
    for c in df.columns:
        if DATE_PATTERNS.search(c):
            date_cols.append(c)
    # de-dup preserving order
    seen = set()
    kept = []
    for c in date_cols:
        if c not in seen:
            seen.add(c)
            kept.append(c)
    return kept


def _coerce_dates(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    """Coerce listed columns to ISO date strings where possible."""
    for c in cols:
        try:
            ser = pd.to_datetime(df[c], errors="coerce", infer_datetime_format=True)
            df[c] = ser.dt.date.astype("string")
        except Exception:
            # Leave column as-is if conversion fails
            pass
    return df


def _safe_float(series: pd.Series) -> pd.Series:
    """Try to coerce to float; if it fails, return original (with NaN for bad rows)."""
    try:
        return pd.to_numeric(series, errors="coerce")
    except Exception:
        return series


# ----------------------------
# Core processing
# ----------------------------
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError("This script expects a CSV file (e.g., sample_labs.csv).")

    df = pd.read_csv(path)

    # Drop completely empty rows/columns
    df = df.dropna(how="all").dropna(axis=1, how="all")

    # Trim whitespace in string columns
    for c in df.columns:
        if pd.api.types.is_object_dtype(df[c]):
            df[c] = df[c].astype("string").str.strip()

    # Drop duplicates
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    if removed:
        print(f"• Removed {removed} duplicate row(s).")

    return df


def normalize_schema(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Optional[str]], List[str]]:
    """
    Map flexible column names into a normalized schema mapping.
    Returns: (df, mapping, date_columns)
      mapping: canonical_name -> actual_column_name (or None)
    """
    mapping = {
        "patient_id": _infer_col(df, CANDIDATES["patient_id"]),
        "sex": _infer_col(df, CANDIDATES["sex"]),
        "test_name": _infer_col(df, CANDIDATES["test_name"]),
        "value": _infer_col(df, CANDIDATES["value"]),
        "units": _infer_col(df, CANDIDATES["units"]),
        "date": _infer_col(df, CANDIDATES["date"]),
    }

    # Date coercion
    date_cols = _find_date_columns(df)
    if mapping["date"] and mapping["date"] not in date_cols:
        date_cols.append(mapping["date"])
    df = _coerce_dates(df, date_cols)

    # Values to float where possible
    if mapping["value"]:
        df[mapping["value"]] = _safe_float(df[mapping["value"]])

    return df, mapping, date_cols


def _normalize_sex_value(raw: object) -> Optional[str]:
    """
    Normalize a sex value to 'M' or 'F' when possible; return None if unknown/missing.
    Accepts common strings like 'M', 'F', 'Male', 'Female', case-insensitive.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip().lower()
    if s in {"m", "male", "man"}:
        return "M"
    if s in {"f", "female", "woman"}:
        return "F"
    return None


def _lookup_range_for_test_and_sex(test: str, sex: Optional[str]):
    """
    Return (low, high, units) for a given test and sex using DEMO_RANGES.
    Order:
      - if test has sex-specific dict and sex 'M'/'F' present → use that
      - elif test has dict with 'default' → use default
      - elif test has tuple → use it
      - else → None
    """
    if test not in DEMO_RANGES:
        return None

    entry = DEMO_RANGES[test]
    if isinstance(entry, tuple):
        return entry

    # dict case
    if sex and sex in entry:
        return entry[sex]
    if "default" in entry:
        return entry["default"]
    return None


def apply_reference_ranges(
    df: pd.DataFrame, mapping: Dict[str, Optional[str]]
) -> pd.DataFrame:
    """
    Add columns:
      - ref_low, ref_high, ref_units
      - flag (LOW/HIGH/NORMAL/UNKNOWN)
    Based on DEMO_RANGES and test_name; if sex is present, use sex-specific thresholds.
    """
    test_col = mapping.get("test_name")
    val_col = mapping.get("value")
    sex_col = mapping.get("sex")

    df = df.copy()
    df["ref_low"] = pd.NA
    df["ref_high"] = pd.NA
    df["ref_units"] = pd.NA
    df["flag"] = "UNKNOWN"

    if not test_col or not val_col:
        return df  # cannot apply

    for i, row in df.iterrows():
        test = str(row.get(test_col, "")).strip().upper()
        val = row.get(val_col, None)
        if pd.isna(val):
            continue

        sex_norm = _normalize_sex_value(row.get(sex_col)) if sex_col else None
        rng = _lookup_range_for_test_and_sex(test, sex_norm)

        if rng is None:
            continue

        low, high, units = rng
        df.at[i, "ref_low"] = low
        df.at[i, "ref_high"] = high
        df.at[i, "ref_units"] = units

        try:
            v = float(val)
            if v < low:
                df.at[i, "flag"] = "LOW"
            elif v > high:
                df.at[i, "flag"] = "HIGH"
            else:
                df.at[i, "flag"] = "NORMAL"
        except Exception:
            # leave as UNKNOWN if not numeric
            pass

    return df


def summarize(
    df: pd.DataFrame,
    mapping: Dict[str, Optional[str]],
    group_by: Iterable[str],
) -> pd.DataFrame:
    """
    Build a tidy summary table with overall + grouped stats for values.
    - overall: count, mean, min, max
    - grouped: same aggregated by provided columns (canonical or actual)
    """
    rows = []
    val_col = mapping.get("value")

    # Overall
    overall = {
        "group_type": "overall",
        "group_value": "ALL",
        "count": len(df),
    }
    if val_col and val_col in df.columns:
        series = pd.to_numeric(df[val_col], errors="coerce")
        overall.update(
            {
                "mean": float(series.mean()) if series.notna().any() else None,
                "min": float(series.min()) if series.notna().any() else None,
                "max": float(series.max()) if series.notna().any() else None,
            }
        )
    else:
        overall.update({"mean": None, "min": None, "max": None})
    rows.append(overall)

    # Map canonical group keys to actual columns if present
    canon_to_actual = {k: v for k, v in mapping.items() if v}
    actual_group_cols = []
    for g in group_by:
        # allow passing either canonical or actual name
        actual = canon_to_actual.get(g, g if g in df.columns else None)
        if actual and actual not in actual_group_cols:
            actual_group_cols.append(actual)

    # Grouped
    for col in actual_group_cols:
        if val_col and val_col in df.columns:
            tmp = (
                df.groupby(col)[val_col]
                .agg(count="count", mean="mean", min="min", max="max")
                .reset_index()
            )
        else:
            tmp = df.groupby(col).size().reset_index(name="count")
            tmp["mean"] = None
            tmp["min"] = None
            tmp["max"] = None

        for _, r in tmp.iterrows():
            rows.append(
                {
                    "group_type": col,
                    "group_value": r[col] if pd.notna(r[col]) else "(missing)",
                    "count": int(r["count"]),
                    "mean": float(r["mean"]) if pd.notna(r["mean"]) else None,
                    "min": float(r["min"]) if pd.notna(r["min"]) else None,
                    "max": float(r["max"]) if pd.notna(r["max"]) else None,
                }
            )

    return pd.DataFrame(rows)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_outputs(
    *,
    df_clean: pd.DataFrame,
    df_flags: pd.DataFrame,
    df_summary: pd.DataFrame,
    inp_path: Path,
    out_clean: Optional[Path],
    out_flags: Optional[Path],
    out_summary: Optional[Path],
) -> Tuple[Path, Path, Path]:
    """Resolve filenames and write CSVs. Return written paths."""
    if out_clean is None:
        out_clean = inp_path.with_name(f"{DEFAULT_CLEAN_PREFIX}{inp_path.stem}.csv")
    if out_flags is None:
        out_flags = inp_path.with_name(f"{DEFAULT_FLAGS_PREFIX}{inp_path.stem}.csv")
    if out_summary is None:
        out_summary = inp_path.with_name(f"{DEFAULT_SUMMARY_PREFIX}{inp_path.stem}.csv")

    df_clean.to_csv(out_clean, index=False)
    df_flags.to_csv(out_flags, index=False)
    df_summary.to_csv(out_summary, index=False)
    return out_clean, out_flags, out_summary


def plot_histograms_per_test(
    df: pd.DataFrame, mapping: Dict[str, Optional[str]], out_dir: Path
) -> Optional[List[Path]]:
    test_col = mapping.get("test_name")
    val_col = mapping.get("value")
    if not test_col or not val_col or test_col not in df.columns or val_col not in df.columns:
        return None

    ensure_dir(out_dir)
    paths: List[Path] = []

    # For each test, draw a histogram of values (if numeric)
    for test, sub in df.groupby(test_col):
        vals = pd.to_numeric(sub[val_col], errors="coerce").dropna()
        if vals.empty:
            continue

        plt.figure(figsize=(7, 4))
        plt.hist(vals, bins=15)
        plt.title(f"{test} - Value Distribution")
        plt.xlabel("Value")
        plt.ylabel("Frequency")
        plt.tight_layout()

        out_path = out_dir / f"{str(test).replace('/', '_')}_hist.png"
        plt.savefig(out_path, dpi=140)
        plt.close()
        paths.append(out_path)

    return paths or None


# ----------------------------
# CLI
# ----------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Analyze (clean + flag + summarize + chart) lab results from a CSV."
    )
    p.add_argument("input", help="Path to CSV (e.g., sample_labs.csv)")
    p.add_argument(
        "--by",
        nargs="*",
        default=["test_name", "sex"],
        help="Group-by fields (canonical or actual column names). Default: test_name sex",
    )
    p.add_argument(
        "--out-clean",
        default="",
        help="Output CSV for cleaned data. Default: cleaned_<input>.csv",
    )
    p.add_argument(
        "--out-flags",
        default="",
        help="Output CSV for flagged (abnormal) rows. Default: flags_<input>.csv",
    )
    p.add_argument(
        "--out-summary",
        default="",
        help="Output CSV for summary table. Default: summary_<input>.csv",
    )
    p.add_argument(
        "--no-charts",
        action="store_true",
        help="Disable chart generation.",
    )
    p.add_argument(
        "--outputs-dir",
        default=str(DEFAULT_OUT_DIR),
        help=f"Directory to save charts. Default: {DEFAULT_OUT_DIR}",
    )
    return p


def main() -> int:
    ap = build_parser()
    args = ap.parse_args()

    inp = Path(args.input)
    out_clean = Path(args.out_clean) if args.out_clean else None
    out_flags = Path(args.out_flags) if args.out_flags else None
    out_summary = Path(args.out_summary) if args.out_summary else None
    out_dir = Path(args.outputs_dir)

    # Load
    _print_header("Loading data")
    try:
        df = load_csv(inp)
    except Exception as e:
        print(f"✗ Failed to load input: {e}")
        return 2

    print(f"• Rows: {len(df):,}  Cols: {len(df.columns)}")
    print(f"• Columns: {list(df.columns)}")

    # Normalize schema
    _print_header("Normalizing schema")
    df, mapping, date_cols = normalize_schema(df)
    print("• Column mapping (canonical → actual):")
    for k, v in mapping.items():
        print(f"   - {k:10s} → {v!r}")
    if date_cols:
        print(f"• Date columns normalized: {', '.join(date_cols)}")
    else:
        print("• Date columns normalized: (none detected)")

    # Apply reference ranges (sex-aware)
    _print_header("Flagging out-of-range values")
    df_flagged = apply_reference_ranges(df, mapping)
    test_col = mapping.get("test_name")
    if test_col:
        present = set(str(t).upper() for t in df_flagged[test_col].dropna().unique())
        covered = sorted(present & set(DEMO_RANGES.keys()))
        if covered:
            print(f"• Reference ranges applied for: {', '.join(covered)}")
        else:
            print("• No tests matched demo reference ranges.")

    # Build summary
    _print_header("Summarizing")
    summary = summarize(df_flagged, mapping, args.by)
    print(f"• Summary rows: {len(summary):,}")

    # Write outputs
    _print_header("Saving CSVs")
    try:
        flags_only = df_flagged[df_flagged["flag"].isin(["LOW", "HIGH"])].copy()
        clean_path, flags_path, summary_path = write_outputs(
            df_clean=df_flagged,
            df_flags=flags_only,
            df_summary=summary,
            inp_path=inp,
            out_clean=out_clean,
            out_flags=out_flags,
            out_summary=out_summary,
        )
        print(f"• Cleaned CSV : {clean_path}")
        print(f"• Flags CSV   : {flags_path}")
        print(f"• Summary CSV : {summary_path}")
    except Exception as e:
        print(f"✗ Failed to write outputs: {e}")
        return 3

    # Charts
    chart_paths = None
    if not args.no_charts:
        _print_header("Plotting")
        try:
            chart_paths = plot_histograms_per_test(df_flagged, mapping, out_dir)
            if chart_paths:
                print(f"• Charts saved in: {out_dir}")
            else:
                print("• Chart generation skipped (no numeric values or no test column).")
        except Exception as e:
            print(f"! Chart step failed (continuing): {e}")

    # Done
    _print_header("Done")
    print("✅ Lab Analysis Complete")
    print(f"• Input         : {inp.name}")
    print(f"• Cleaned CSV   : {clean_path.name}")
    print(f"• Flags CSV     : {flags_path.name}")
    print(f"• Summary CSV   : {summary_path.name}")
    print(f"• Rows (clean)  : {len(df_flagged):,}")
    if chart_paths:
        print(f"• Charts dir    : {out_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())