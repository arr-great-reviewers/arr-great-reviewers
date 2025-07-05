"""Utilities for reviewer identification and data processing."""

import json
import tomllib
from pathlib import Path
from typing import Dict, Optional


def get_reviewer_unique_id(
    name: str, institution: str, openreview_id: Optional[str] = None
) -> Optional[str]:
    """
    Get the unique identifier for a reviewer (only if they have an OpenReview ID).

    Args:
        name: The reviewer's full name
        institution: The reviewer's institution
        openreview_id: Optional OpenReview profile ID

    Returns:
        The OpenReview profile ID if available, None otherwise
    """
    # Only return actual OpenReview IDs, don't generate fake ones
    return openreview_id if openreview_id else None


def load_manual_mappings() -> Dict[str, str]:
    """
    Load the manual OpenReview profile mappings from TOML file.

    Returns:
        Dictionary mapping "name|institution" to OpenReview profile ID
    """
    manual_file = Path("config/manual_openreview_mappings.toml")

    if not manual_file.exists():
        return {}

    with open(manual_file, "rb") as f:
        data = tomllib.load(f)

    return data.get("mappings", {})


def load_reviewer_mappings() -> Dict[str, Dict]:
    """
    Load the OpenReview profile mappings.

    Returns:
        Dictionary containing mapping data
    """
    mapping_file = Path("data/openreview_profile_mapping.json")

    if not mapping_file.exists():
        return {}

    with open(mapping_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_reviewer_openreview_id(
    name: str, institution: str, mappings: Dict[str, Dict]
) -> Optional[str]:
    """
    Get the OpenReview profile ID for a reviewer.

    Args:
        name: The reviewer's full name
        institution: The reviewer's institution
        mappings: The OpenReview mappings data

    Returns:
        The OpenReview profile ID if found, None otherwise
    """
    key = f"{name}|{institution}"

    # Check manual mappings first (highest priority)
    manual_mappings = load_manual_mappings()
    if key in manual_mappings:
        return manual_mappings[key]

    # Check single matches from automatic mapping
    if key in mappings.get("single_matches", {}):
        profiles = mappings["single_matches"][key]["openreview_profiles"]
        return profiles[0] if profiles else None

    # For multiple matches, return the first one (could be improved with disambiguation)
    if key in mappings.get("multiple_matches", {}):
        profiles = mappings["multiple_matches"][key]["openreview_profiles"]
        return profiles[0] if profiles else None

    return None


def build_reviewer_database() -> Dict[str, Dict]:
    """
    Build a comprehensive reviewer database with only reviewers who have OpenReview IDs.

    Returns:
        Dictionary mapping OpenReview profile IDs to their data
    """
    reviewer_db = {}
    mappings = load_reviewer_mappings()

    # Load all reviewer data from different sources
    raw_data_dir = Path("data/raw")
    metrics_dir = Path("data/metrics")

    # Get all reviewers from top_people_absolute.json
    top_people_file = metrics_dir / "top_people_absolute.json"
    if top_people_file.exists():
        with open(top_people_file, "r", encoding="utf-8") as f:
            top_people = json.load(f)

        for reviewer in top_people:
            name = reviewer["name"]
            institution = reviewer["institution"]
            openreview_id = get_reviewer_openreview_id(name, institution, mappings)

            # Only include reviewers with actual OpenReview IDs
            if not openreview_id:
                continue

            reviewer_db[openreview_id] = {
                "name": name,
                "institution": institution,
                "openreview_id": openreview_id,
                "unique_id": openreview_id,
                "total_recognized": reviewer.get("recognized", 0),
                "total_reviewed": reviewer.get("reviewed", 0),
                "recognition_rate": reviewer.get("recognition_rate", 0.0),
                "cycles": {},
                "achievements": [],
            }

    # Add cycle-specific data
    for cycle_file in raw_data_dir.glob("*.json"):
        cycle_name = cycle_file.stem

        with open(cycle_file, "r", encoding="utf-8") as f:
            cycle_data = json.load(f)

        for reviewer in cycle_data:
            name = reviewer["name"]
            institution = reviewer["institution"]
            openreview_id = get_reviewer_openreview_id(name, institution, mappings)

            # Only include reviewers with actual OpenReview IDs
            if not openreview_id:
                continue

            # Add to database if not already there
            if openreview_id not in reviewer_db:
                reviewer_db[openreview_id] = {
                    "name": name,
                    "institution": institution,
                    "openreview_id": openreview_id,
                    "unique_id": openreview_id,
                    "total_recognized": 0,
                    "total_reviewed": 0,
                    "recognition_rate": 0.0,
                    "cycles": {},
                    "achievements": [],
                }

            # Add cycle-specific data
            reviewer_db[openreview_id]["cycles"][cycle_name] = {
                "recognized": int(reviewer.get("recognized", 0)),
                "reviewed": int(reviewer.get("reviewed", 0)),
                "percentage": float(reviewer.get("percentage", 0.0)),
            }

    # Recalculate overall totals from cycle data for all reviewers
    for openreview_id, reviewer_data in reviewer_db.items():
        total_recognized = 0
        total_reviewed = 0
        
        for cycle_data in reviewer_data["cycles"].values():
            total_recognized += cycle_data["recognized"]
            total_reviewed += cycle_data["reviewed"]
        
        # Update totals (this will override values from top_people_absolute.json)
        reviewer_data["total_recognized"] = total_recognized
        reviewer_data["total_reviewed"] = total_reviewed
        reviewer_data["recognition_rate"] = (
            total_recognized / total_reviewed if total_reviewed > 0 else 0.0
        )

    return reviewer_db


def calculate_achievements(reviewer_db: Dict[str, Dict]) -> Dict[str, Dict]:
    """
    Calculate achievements (badges) for all reviewers.

    Args:
        reviewer_db: The reviewer database

    Returns:
        Updated reviewer database with achievements
    """
    # Calculate overall rankings - Recognition Count Rankings tie-breaking
    overall_ranking = sorted(
        reviewer_db.values(),
        key=lambda x: (
            x["total_recognized"],
            x["recognition_rate"],
            x["total_reviewed"],
        ),
        reverse=True,
    )

    # Assign overall achievement badges
    for i, reviewer in enumerate(overall_ranking):
        unique_id = reviewer["unique_id"]
        rank = i + 1

        if rank == 1:
            reviewer_db[unique_id]["achievements"].append(
                {
                    "type": "overall_top_1",
                    "title": "Top 1 Overall",
                    "description": f"Ranked #{rank} among all reviewers",
                    "rank": rank,
                }
            )
        elif rank == 2:
            reviewer_db[unique_id]["achievements"].append(
                {
                    "type": "overall_top_2",
                    "title": "Top 2 Overall",
                    "description": f"Ranked #{rank} among all reviewers",
                    "rank": rank,
                }
            )
        elif rank == 3:
            reviewer_db[unique_id]["achievements"].append(
                {
                    "type": "overall_top_3",
                    "title": "Top 3 Overall",
                    "description": f"Ranked #{rank} among all reviewers",
                    "rank": rank,
                }
            )
        elif rank <= 5:
            reviewer_db[unique_id]["achievements"].append(
                {
                    "type": "overall_top_5",
                    "title": "Top 5 Overall",
                    "description": f"Ranked #{rank} among all reviewers",
                    "rank": rank,
                }
            )
        elif rank <= 10:
            reviewer_db[unique_id]["achievements"].append(
                {
                    "type": "overall_top_10",
                    "title": "Top 10 Overall",
                    "description": f"Ranked #{rank} among all reviewers",
                    "rank": rank,
                }
            )
        elif rank <= 20:
            reviewer_db[unique_id]["achievements"].append(
                {
                    "type": "overall_top_20",
                    "title": "Top 20 Overall",
                    "description": f"Ranked #{rank} among all reviewers",
                    "rank": rank,
                }
            )
        elif rank <= 50:
            reviewer_db[unique_id]["achievements"].append(
                {
                    "type": "overall_top_50",
                    "title": "Top 50 Overall",
                    "description": f"Ranked #{rank} among all reviewers",
                    "rank": rank,
                }
            )

    # Calculate cycle-specific rankings
    all_cycles = set()
    for reviewer in reviewer_db.values():
        all_cycles.update(reviewer["cycles"].keys())

    for cycle in all_cycles:
        # Get reviewers active in this cycle
        cycle_reviewers = []
        for reviewer in reviewer_db.values():
            if cycle in reviewer["cycles"]:
                cycle_reviewers.append((reviewer, reviewer["cycles"][cycle]))

        # Sort by recognized reviews in this cycle - Recognition Count Rankings tie-breaking
        cycle_ranking = sorted(
            cycle_reviewers,
            key=lambda x: (
                x[1]["recognized"],
                x[1]["percentage"] / 100,
                x[1]["reviewed"],
            ),
            reverse=True,
        )

        # Assign cycle-specific badges
        for i, (reviewer, cycle_data) in enumerate(cycle_ranking):
            unique_id = reviewer["unique_id"]
            rank = i + 1

            if rank == 1:
                reviewer_db[unique_id]["achievements"].append(
                    {
                        "type": f"cycle_top_1_{cycle}",
                        "title": f"Top 1 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank == 2:
                reviewer_db[unique_id]["achievements"].append(
                    {
                        "type": f"cycle_top_2_{cycle}",
                        "title": f"Top 2 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank == 3:
                reviewer_db[unique_id]["achievements"].append(
                    {
                        "type": f"cycle_top_3_{cycle}",
                        "title": f"Top 3 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank <= 5:
                reviewer_db[unique_id]["achievements"].append(
                    {
                        "type": f"cycle_top_5_{cycle}",
                        "title": f"Top 5 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank <= 10:
                reviewer_db[unique_id]["achievements"].append(
                    {
                        "type": f"cycle_top_10_{cycle}",
                        "title": f"Top 10 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank <= 20:
                reviewer_db[unique_id]["achievements"].append(
                    {
                        "type": f"cycle_top_20_{cycle}",
                        "title": f"Top 20 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank <= 50:
                reviewer_db[unique_id]["achievements"].append(
                    {
                        "type": f"cycle_top_50_{cycle}",
                        "title": f"Top 50 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )

    return reviewer_db


def generate_reviewer_data() -> None:
    """
    Generate the complete reviewer database with unique IDs and achievements.
    Saves the data to a JSON file for use in site generation.
    """
    print("Building reviewer database...")
    reviewer_db = build_reviewer_database()

    print("Calculating achievements...")
    reviewer_db = calculate_achievements(reviewer_db)

    # Save to file
    output_file = Path("data/reviewers_database.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(reviewer_db, f, indent=2, ensure_ascii=False)

    print(f"Generated reviewer database with {len(reviewer_db)} reviewers")
    print(f"Saved to: {output_file}")

    # Generate summary statistics
    total_with_openreview = sum(1 for r in reviewer_db.values() if r["openreview_id"])
    total_achievements = sum(len(r["achievements"]) for r in reviewer_db.values())

    print(f"- Reviewers with OpenReview IDs: {total_with_openreview}")
    print(f"- Total achievements: {total_achievements}")


if __name__ == "__main__":
    generate_reviewer_data()
