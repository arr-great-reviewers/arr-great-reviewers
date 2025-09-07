"""Utilities for institution identification and data processing."""

import json
import re
from pathlib import Path
from typing import Dict


def institution_name_to_url_safe_id(institution_name: str) -> str:
    """
    Convert institution name to URL-safe identifier.

    Args:
        institution_name: The institution's full name

    Returns:
        URL-safe identifier for the institution
    """
    # Convert to lowercase and replace spaces/special characters with hyphens
    url_safe = re.sub(r"[^a-zA-Z0-9]+", "-", institution_name.lower())
    # Remove leading/trailing hyphens and multiple consecutive hyphens
    url_safe = re.sub(r"-+", "-", url_safe).strip("-")
    return url_safe


def load_institution_mappings() -> Dict[str, str]:
    """
    Create and return institution name to URL-safe ID mappings.

    Returns:
        Dictionary mapping institution names to URL-safe IDs
    """
    # We'll build this dynamically from the data
    mappings = {}

    # Load institution data from metrics
    metrics_dir = Path("data/metrics")
    inst_file = metrics_dir / "top_institutions_absolute.json"

    if inst_file.exists():
        with open(inst_file, "r", encoding="utf-8") as f:
            institutions = json.load(f)

        for inst in institutions:
            inst_name = inst["institution"]
            url_safe_id = institution_name_to_url_safe_id(inst_name)
            mappings[inst_name] = url_safe_id

    return mappings


def build_institution_database() -> Dict[str, Dict]:
    """
    Build a comprehensive institution database.

    Returns:
        Dictionary mapping URL-safe institution IDs to their data
    """
    institution_db = {}

    # Load metrics data
    metrics_dir = Path("data/metrics")
    inst_file = metrics_dir / "top_institutions_absolute.json"

    if not inst_file.exists():
        return institution_db

    with open(inst_file, "r", encoding="utf-8") as f:
        institutions_data = json.load(f)

    # Load reviewer database to get individual reviewer data per institution
    reviewer_db_file = Path("data/reviewers_database.json")
    reviewer_db = {}
    if reviewer_db_file.exists():
        with open(reviewer_db_file, "r", encoding="utf-8") as f:
            reviewer_db = json.load(f)

    # Load cycle data for institution-specific cycle performance
    raw_data_dir = Path("data/raw")
    cycle_data = {}
    for cycle_file in raw_data_dir.glob("*.json"):
        cycle_name = cycle_file.stem
        with open(cycle_file, "r", encoding="utf-8") as f:
            cycle_data[cycle_name] = json.load(f)

    # Build institution database
    # First, group institutions by URL-safe ID to handle name variations
    institution_groups = {}
    for inst_data in institutions_data:
        inst_name = inst_data["institution"]
        url_safe_id = institution_name_to_url_safe_id(inst_name)

        if url_safe_id not in institution_groups:
            institution_groups[url_safe_id] = []
        institution_groups[url_safe_id].append(inst_data)

    # Now process each group, merging institutions with the same URL-safe ID
    for url_safe_id, inst_group in institution_groups.items():
        # Merge data from all institutions in this group
        total_recognized = sum(inst["recognized"] for inst in inst_group)
        total_reviewed = sum(inst["reviewed"] for inst in inst_group)
        total_reviewer_count = sum(inst["reviewer_count"] for inst in inst_group)

        # Use the name from the institution with the most recognized reviews
        primary_inst = max(inst_group, key=lambda x: x["recognized"])
        merged_name = primary_inst["institution"]

        # Get all institution names for reviewer matching
        all_inst_names = [inst["institution"] for inst in inst_group]

        # Get reviewers from all institution name variations
        institution_reviewers = []
        for reviewer_id, reviewer in reviewer_db.items():
            if reviewer["institution"] in all_inst_names:
                institution_reviewers.append(reviewer)

        # Calculate cycle-specific data for this institution group
        cycles = {}
        for cycle_name, cycle_reviewers in cycle_data.items():
            cycle_inst_data = {
                "recognized": 0,
                "reviewed": 0,
                "reviewer_count": 0,
                "reviewers": [],
            }

            for reviewer in cycle_reviewers:
                if reviewer["institution"] in all_inst_names:
                    cycle_inst_data["recognized"] += int(reviewer.get("recognized", 0))
                    cycle_inst_data["reviewed"] += int(reviewer.get("reviewed", 0))
                    cycle_inst_data["reviewer_count"] += 1
                    cycle_inst_data["reviewers"].append(
                        {
                            "name": reviewer["name"],
                            "recognized": int(reviewer.get("recognized", 0)),
                            "reviewed": int(reviewer.get("reviewed", 0)),
                            "percentage": float(reviewer.get("percentage", 0.0)),
                        }
                    )

            # Calculate recognition rate for this cycle
            cycle_inst_data["recognition_rate"] = (
                cycle_inst_data["recognized"] / cycle_inst_data["reviewed"]
                if cycle_inst_data["reviewed"] > 0
                else 0.0
            )

            # Sort reviewers by recognized count
            cycle_inst_data["reviewers"].sort(
                key=lambda x: (x["recognized"], x["percentage"]), reverse=True
            )

            cycles[cycle_name] = cycle_inst_data

        # Top reviewers from this institution (across all cycles)
        top_reviewers = sorted(
            institution_reviewers,
            key=lambda x: (x["total_recognized"], x["recognition_rate"]),
            reverse=True,
        )  # All reviewers, sorted by performance

        # Calculate overall recognition rate
        overall_recognition_rate = (
            total_recognized / total_reviewed if total_reviewed > 0 else 0.0
        )

        institution_db[url_safe_id] = {
            "name": merged_name,
            "url_safe_id": url_safe_id,
            "total_recognized": total_recognized,
            "total_reviewed": total_reviewed,
            "total_reviewers": total_reviewer_count,
            "recognition_rate": overall_recognition_rate,
            "top_reviewers": top_reviewers,
            "cycles": cycles,
            "achievements": [],
            "name_variations": sorted(
                list(set(all_inst_names))
            ),  # All institution name variations
        }

    return institution_db


def calculate_institution_achievements(
    institution_db: Dict[str, Dict],
) -> Dict[str, Dict]:
    """
    Calculate achievements (badges) for all institutions.

    Args:
        institution_db: The institution database

    Returns:
        Updated institution database with achievements
    """
    # Calculate overall rankings by recognition count
    overall_ranking = sorted(
        institution_db.values(),
        key=lambda x: (
            x["total_recognized"],
            x["recognition_rate"],
            x["total_reviewed"],
        ),
        reverse=True,
    )

    # Assign overall achievement badges
    for i, institution in enumerate(overall_ranking):
        url_safe_id = institution["url_safe_id"]
        rank = i + 1

        if rank == 1:
            institution_db[url_safe_id]["achievements"].append(
                {
                    "type": "overall_top_1",
                    "title": "Top 1 Institution",
                    "description": f"Ranked #{rank} among all institutions",
                    "rank": rank,
                }
            )
        elif rank == 2:
            institution_db[url_safe_id]["achievements"].append(
                {
                    "type": "overall_top_2",
                    "title": "Top 2 Institution",
                    "description": f"Ranked #{rank} among all institutions",
                    "rank": rank,
                }
            )
        elif rank == 3:
            institution_db[url_safe_id]["achievements"].append(
                {
                    "type": "overall_top_3",
                    "title": "Top 3 Institution",
                    "description": f"Ranked #{rank} among all institutions",
                    "rank": rank,
                }
            )
        elif rank <= 5:
            institution_db[url_safe_id]["achievements"].append(
                {
                    "type": "overall_top_5",
                    "title": "Top 5 Institution",
                    "description": f"Ranked #{rank} among all institutions",
                    "rank": rank,
                }
            )
        elif rank <= 10:
            institution_db[url_safe_id]["achievements"].append(
                {
                    "type": "overall_top_10",
                    "title": "Top 10 Institution",
                    "description": f"Ranked #{rank} among all institutions",
                    "rank": rank,
                }
            )
        elif rank <= 20:
            institution_db[url_safe_id]["achievements"].append(
                {
                    "type": "overall_top_20",
                    "title": "Top 20 Institution",
                    "description": f"Ranked #{rank} among all institutions",
                    "rank": rank,
                }
            )
        elif rank <= 50:
            institution_db[url_safe_id]["achievements"].append(
                {
                    "type": "overall_top_50",
                    "title": "Top 50 Institution",
                    "description": f"Ranked #{rank} among all institutions",
                    "rank": rank,
                }
            )
        elif rank <= 100:
            institution_db[url_safe_id]["achievements"].append(
                {
                    "type": "overall_top_100",
                    "title": "Top 100 Institution",
                    "description": f"Ranked #{rank} among all institutions",
                    "rank": rank,
                }
            )

    # Calculate cycle-specific rankings
    all_cycles = set()
    for institution in institution_db.values():
        all_cycles.update(institution["cycles"].keys())

    for cycle in all_cycles:
        # Get institutions active in this cycle
        cycle_institutions = []
        for institution in institution_db.values():
            if cycle in institution["cycles"]:
                cycle_institutions.append((institution, institution["cycles"][cycle]))

        # Sort by recognized reviews in this cycle
        cycle_ranking = sorted(
            cycle_institutions,
            key=lambda x: (
                x[1]["recognized"],
                x[1]["recognition_rate"],
                x[1]["reviewed"],
            ),
            reverse=True,
        )

        # Assign cycle-specific badges
        for i, (institution, cycle_data) in enumerate(cycle_ranking):
            url_safe_id = institution["url_safe_id"]
            rank = i + 1

            if rank == 1:
                institution_db[url_safe_id]["achievements"].append(
                    {
                        "type": f"cycle_top_1_{cycle}",
                        "title": f"Top 1 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank == 2:
                institution_db[url_safe_id]["achievements"].append(
                    {
                        "type": f"cycle_top_2_{cycle}",
                        "title": f"Top 2 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank == 3:
                institution_db[url_safe_id]["achievements"].append(
                    {
                        "type": f"cycle_top_3_{cycle}",
                        "title": f"Top 3 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank <= 5:
                institution_db[url_safe_id]["achievements"].append(
                    {
                        "type": f"cycle_top_5_{cycle}",
                        "title": f"Top 5 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank <= 10:
                institution_db[url_safe_id]["achievements"].append(
                    {
                        "type": f"cycle_top_10_{cycle}",
                        "title": f"Top 10 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank <= 20:
                institution_db[url_safe_id]["achievements"].append(
                    {
                        "type": f"cycle_top_20_{cycle}",
                        "title": f"Top 20 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank <= 50:
                institution_db[url_safe_id]["achievements"].append(
                    {
                        "type": f"cycle_top_50_{cycle}",
                        "title": f"Top 50 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )
            elif rank <= 100:
                institution_db[url_safe_id]["achievements"].append(
                    {
                        "type": f"cycle_top_100_{cycle}",
                        "title": f"Top 100 in {cycle}",
                        "description": f"Ranked #{rank} in {cycle} cycle",
                        "rank": rank,
                        "cycle": cycle,
                    }
                )

    return institution_db


def generate_cycle_institution_files(institution_db: Dict[str, Dict]) -> None:
    """
    Generate pre-ranked institution data files for each cycle.
    This eliminates the need for JavaScript to aggregate raw data.
    """
    print("Generating cycle-specific institution ranking files...")

    # Get all cycles
    all_cycles = set()
    for institution in institution_db.values():
        all_cycles.update(institution["cycles"].keys())

    metrics_dir = Path("data/metrics")
    metrics_dir.mkdir(parents=True, exist_ok=True)

    for cycle in sorted(all_cycles):
        # Get institutions active in this cycle
        cycle_institutions = []
        for institution in institution_db.values():
            if cycle in institution["cycles"]:
                cycle_data = institution["cycles"][cycle]
                cycle_institutions.append(
                    {
                        "institution": institution["name"],
                        "reviewer_count": cycle_data["reviewer_count"],
                        "reviewed": cycle_data["reviewed"],
                        "recognized": cycle_data["recognized"],
                        "recognition_rate": cycle_data["recognition_rate"],
                        "percentage": cycle_data["recognition_rate"] * 100,
                    }
                )

        # Sort by same criteria as Python ranking logic
        cycle_institutions.sort(
            key=lambda x: (x["recognized"], x["recognition_rate"], x["reviewed"]),
            reverse=True,
        )

        # Save to cycle-specific file
        output_file = metrics_dir / f"institutions_{cycle}.json"
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(cycle_institutions, f, ensure_ascii=False, indent=2)

        print(f"  Generated {output_file} with {len(cycle_institutions)} institutions")


def generate_institution_data() -> None:
    """
    Generate the complete institution database with unique IDs and achievements.
    Saves the data to a JSON file for use in site generation.
    """
    print("Building institution database...")
    institution_db = build_institution_database()

    print("Calculating achievements...")
    institution_db = calculate_institution_achievements(institution_db)

    # Generate cycle-specific ranking files
    generate_cycle_institution_files(institution_db)

    # Save to file
    output_file = Path("data/institutions_database.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(institution_db, f, indent=2, ensure_ascii=False)

    print(f"Generated institution database with {len(institution_db)} institutions")
    print(f"Saved to: {output_file}")

    # Generate summary statistics
    total_achievements = sum(
        len(inst["achievements"]) for inst in institution_db.values()
    )

    print(f"- Total achievements: {total_achievements}")

    # Save institution mappings for reference
    mappings = load_institution_mappings()
    mappings_file = Path("data/institution_mappings.json")
    with open(mappings_file, "w", encoding="utf-8") as f:
        json.dump(mappings, f, indent=2, ensure_ascii=False)
    print(f"- Institution mappings saved to: {mappings_file}")


if __name__ == "__main__":
    generate_institution_data()
