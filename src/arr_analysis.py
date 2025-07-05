from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from rich import print

from src.reviewer_utils import get_reviewer_openreview_id, load_reviewer_mappings

RAW_DIR = Path("data/raw")
METRIC_DIR = Path("data/metrics")
METRIC_DIR.mkdir(parents=True, exist_ok=True)
SCHEMA_PATH = Path("static/schema.json")


def load_data() -> pd.DataFrame:
    frames = []
    mappings = load_reviewer_mappings()

    for file in RAW_DIR.glob("*.json"):
        df = pd.read_json(file)
        df["iteration"] = file.stem

        # Add OpenReview ID for each reviewer
        df["openreview_id"] = df.apply(
            lambda row: get_reviewer_openreview_id(
                row["name"], row["institution"], mappings
            ),
            axis=1,
        )

        frames.append(df)
    if not frames:
        return pd.DataFrame(
            columns=[
                "name",
                "institution",
                "reviewed",
                "recognized",
                "percentage",
                "iteration",
                "openreview_id",
            ]
        )  # type: ignore[arg-type]
    df = pd.concat(frames, ignore_index=True)
    for col in ["reviewed", "recognized", "percentage"]:
        df[col] = df[col].astype(int)
    return df


def gini(array: np.ndarray) -> float:
    if array.size == 0:
        return float("nan")
    array = array.flatten().astype(float)
    if np.amin(array) < 0:
        array -= np.amin(array)
    array += 1e-6
    array = np.sort(array)
    index = np.arange(1, array.shape[0] + 1)
    n = array.shape[0]
    return np.sum((2 * index - n - 1) * array) / (n * np.sum(array))


def build_metrics(df: pd.DataFrame) -> None:
    # Filter to only include reviewers with OpenReview IDs and consolidate by OpenReview ID
    df_with_openreview = df[df["openreview_id"].notna()].copy()

    # For reviewers with OpenReview IDs, consolidate by OpenReview ID and use the most recent name/institution
    if not df_with_openreview.empty:
        # Group by OpenReview ID and get the most recent name/institution for each reviewer
        consolidated_reviewers = (
            df_with_openreview.sort_values("iteration")
            .groupby("openreview_id")
            .agg(
                {
                    "name": "last",  # Use most recent name
                    "institution": "last",  # Use most recent institution
                    "recognized": "sum",
                    "reviewed": "sum",
                    "percentage": "mean",
                }
            )
            .reset_index()
        )
    else:
        consolidated_reviewers = pd.DataFrame(
            columns=[
                "openreview_id",
                "name",
                "institution",
                "recognized",
                "reviewed",
                "percentage",
            ]
        )

    # People by absolute count - tie-breaking by recognition rate, then by total reviews
    people_abs = (
        consolidated_reviewers.assign(
            recognition_rate=lambda x: x["recognized"] / x["reviewed"].clip(lower=1)
        )
        .sort_values(
            by=["recognized", "recognition_rate", "reviewed"],
            ascending=[False, False, False],
        )  # type: ignore[call-arg]
        .drop(
            columns=["openreview_id"]
        )  # Remove openreview_id for output compatibility
    )
    people_abs.to_json(
        METRIC_DIR / "top_people_absolute.json", orient="records", indent=2
    )

    # People by percentage - tie-breaking by recognized count, then by total reviews
    people_pct = (
        consolidated_reviewers.assign(
            recognition_rate=lambda x: x["recognized"] / x["reviewed"].clip(lower=1)
        )
        .sort_values(
            by=["percentage", "recognized", "reviewed"], ascending=[False, False, False]
        )  # type: ignore[call-arg]
        .drop(
            columns=["openreview_id"]
        )  # Remove openreview_id for output compatibility
    )
    people_pct.to_json(
        METRIC_DIR / "top_people_percentage.json", orient="records", indent=2
    )

    # Institutions by absolute count - tie-breaking by recognition rate, then by total reviews
    inst_abs = (
        df.groupby("institution", as_index=False)
        .agg({"recognized": "sum", "reviewed": "sum", "name": "nunique"})
        .rename(columns={"name": "reviewer_count"})
        .assign(
            recognition_rate=lambda x: x["recognized"] / x["reviewed"].clip(lower=1)
        )
        .sort_values(
            by=["recognized", "recognition_rate", "reviewed"],
            ascending=[False, False, False],
        )  # type: ignore[call-arg]
    )
    inst_abs.to_json(
        METRIC_DIR / "top_institutions_absolute.json", orient="records", indent=2
    )

    # Institutions by percentage - tie-breaking by recognized count, then by total reviews
    inst_pct = (
        df.assign(weight=df["reviewed"])
        .groupby("institution")
        .apply(
            lambda g: pd.Series(
                {
                    "percentage": float(
                        np.average(g["percentage"], weights=g["weight"])
                    ),
                    "recognized": g["recognized"].sum(),
                    "reviewed": g["reviewed"].sum(),
                }
            ),
            include_groups=False,
        )
        .reset_index()  # type: ignore[call-arg]
        .sort_values(
            by=["percentage", "recognized", "reviewed"], ascending=[False, False, False]
        )  # type: ignore[call-arg]
    )
    inst_pct.to_json(
        METRIC_DIR / "top_institutions_percentage.json", orient="records", indent=2
    )

    snap = (
        df.groupby("iteration")
        .agg({"reviewed": "sum", "recognized": "sum"})
        .reset_index()
    )
    snap.to_json(METRIC_DIR / "monthly_snapshots.json", orient="records", indent=2)

    misc = {
        "gini_recognized": gini(df["recognized"].to_numpy()),
        "herfindahl_institutions": float(
            np.square(df.groupby("institution")["recognized"].sum()).sum()
            / float(df["recognized"].sum() ** 2)
        ),
    }
    with (METRIC_DIR / "misc_insights.json").open("w") as f:
        json.dump(misc, f, indent=2)

    schema = {
        "top_people_absolute": list(people_abs.columns),
        "top_people_percentage": list(people_pct.columns),
        "top_institutions_absolute": list(inst_abs.columns),
        "top_institutions_percentage": list(inst_pct.columns),
        "monthly_snapshots": list(snap.columns),
        "misc_insights": list(misc.keys()),
    }
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SCHEMA_PATH.open("w") as f:
        json.dump(schema, f, indent=2)


if __name__ == "__main__":
    df = load_data()
    if df.empty:
        print("No data available. Run arr_dl.py first.")
    else:
        build_metrics(df)
        print("Metrics built")
