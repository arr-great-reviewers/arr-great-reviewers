"""
ARR Great Reviewers Site Builder

Builds the static site with support for selective generation:
- Default: Generate all pages including all ~2000+ reviewer pages and institution pages
- --skip-reviewers: Generate all pages except individual reviewer pages (fast)
- --skip-institutions: Generate all pages except individual institution pages (fast)
- --single-reviewer ID: Generate core pages + only the specified reviewer page (automatically skips all other reviewers and all institutions)
- --single-institution ID: Generate core pages + only the specified institution page (automatically skips all other institutions and all reviewers)

Usage:
    python -m src.build_site                           # Full build
    python -m src.build_site --skip-reviewers          # Fast build (no reviewers)
    python -m src.build_site --skip-institutions       # Fast build (no institutions)
    python -m src.build_site --single-reviewer "~ID"   # Single reviewer build (auto-skips other reviewers + institutions)
    python -m src.build_site --single-institution "google"  # Single institution build (auto-skips other institutions + reviewers)

Makefile integration:
    make site                       # Full build
    make site-fast                 # Fast build (skip reviewers)
    make site-single-reviewer      # Single reviewer build (Marek Suppa)
    make site-single-institution   # Single institution build (Google)
"""

from __future__ import annotations

import json
import multiprocessing as mp
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path("templates")
SITE = Path("site")
SITE.mkdir(parents=True, exist_ok=True)


def render(template: str, context: dict, out: Path) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tmpl = env.get_template(template)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tmpl.render(**context), encoding="utf-8")


def render_template_parallel(task_data: Tuple[str, Dict[str, Any], Path]) -> bool:
    """Worker function for parallel template rendering"""
    template_name, context, output_path = task_data

    try:
        # Each process gets its own Jinja2 environment
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES)),
            autoescape=select_autoescape(["html", "xml"]),
            cache_size=500,
        )

        template = env.get_template(template_name)
        content = template.render(**context)

        # Ensure directory exists (thread-safe with exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file atomically to prevent corruption
        temp_path = output_path.with_suffix(".tmp")
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(output_path)

        return True

    except Exception as e:
        print(f"Error rendering {output_path}: {e}")
        return False


def generate_pages_parallel(
    tasks: list[Tuple[str, Dict[str, Any], Path]],
    page_type: str,
    num_workers: int | None = None,
) -> int:
    """Generate pages in parallel using multiprocessing"""
    if not tasks:
        return 0

    if num_workers is None:
        num_workers = min(mp.cpu_count(), 8)  # Cap at 8 to avoid memory issues

    print(f"Generating {len(tasks)} {page_type} pages using {num_workers} workers...")

    # Pre-create directories to avoid race conditions
    unique_dirs = set(task[2].parent for task in tasks)
    if len(unique_dirs) > 100:  # Only parallelize directory creation for large sets
        with ThreadPoolExecutor(max_workers=4) as executor:
            dir_futures = [
                executor.submit(
                    lambda d: d.mkdir(parents=True, exist_ok=True), dir_path
                )
                for dir_path in unique_dirs
            ]
            for future in as_completed(dir_futures):
                future.result()
    else:
        for dir_path in unique_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    # Render templates in parallel
    start_time = time.time()
    successful = 0

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all rendering tasks
        futures = [executor.submit(render_template_parallel, task) for task in tasks]

        # Process completed tasks with progress reporting
        completed = 0
        for future in as_completed(futures):
            if future.result():
                successful += 1
            completed += 1

            # Progress reporting for large sets
            if len(tasks) > 100 and completed % 200 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (len(tasks) - completed) / rate if rate > 0 else 0
                print(
                    f"  Progress: {completed}/{len(tasks)} ({completed / len(tasks) * 100:.1f}%) "
                    f"Rate: {rate:.1f}/s ETA: {eta:.0f}s"
                )

    elapsed = time.time() - start_time
    rate = successful / elapsed if elapsed > 0 else 0
    print(
        f"Generated {successful}/{len(tasks)} {page_type} pages in {elapsed:.1f}s ({rate:.1f} pages/sec)"
    )

    return successful


def build_site(
    skip_reviewers: bool = False,
    skip_institutions: bool = False,
    single_reviewer: str | None = None,
    single_institution: str | None = None,
) -> None:
    # Copy static assets to site directory
    static_source = Path("static")
    static_dest = SITE / "assets"

    if static_source.exists():
        # Remove existing assets directory to ensure clean copy
        if static_dest.exists():
            shutil.rmtree(static_dest)

        # Copy entire static directory recursively
        shutil.copytree(static_source, static_dest)

    # Copy metrics data to site directory for JavaScript access
    metrics_source = Path("data/metrics")
    metrics_dest = SITE / "data" / "metrics"

    if metrics_source.exists():
        # Create destination directory
        metrics_dest.mkdir(parents=True, exist_ok=True)

        # Copy all JSON files
        for json_file in metrics_source.glob("*.json"):
            shutil.copy2(json_file, metrics_dest / json_file.name)

    # Copy raw data for cycle-specific pages
    raw_source = Path("data/raw")
    raw_dest = SITE / "data" / "raw"

    if raw_source.exists():
        # Create destination directory
        raw_dest.mkdir(parents=True, exist_ok=True)

        # Copy all JSON files
        for json_file in raw_source.glob("*.json"):
            shutil.copy2(json_file, raw_dest / json_file.name)

    # Copy reviewer database
    reviewer_db_source = Path("data/reviewers_database.json")
    if reviewer_db_source.exists():
        shutil.copy2(reviewer_db_source, SITE / "data" / "reviewers_database.json")

    # Copy institution database
    institution_db_source = Path("data/institutions_database.json")
    if institution_db_source.exists():
        shutil.copy2(
            institution_db_source, SITE / "data" / "institutions_database.json"
        )

    # Copy institution mappings for JavaScript lookup
    institution_mappings_source = Path("data/institution_mappings.json")
    if institution_mappings_source.exists():
        shutil.copy2(
            institution_mappings_source, SITE / "data" / "institution_mappings.json"
        )

    # Copy OpenReview profile mapping for JavaScript lookup
    openreview_mapping_source = Path("data/openreview_profile_mapping.json")
    if openreview_mapping_source.exists():
        shutil.copy2(
            openreview_mapping_source, SITE / "data" / "openreview_profile_mapping.json"
        )

    # Load metrics for template rendering
    metrics = {}
    for file in Path("data/metrics").glob("*.json"):
        with file.open() as f:
            metrics[file.stem] = json.load(f)

    # Load cycle data
    cycles = []
    for file in Path("data/raw").glob("*.json"):
        cycles.append(file.stem)
    cycles.sort()

    # Load reviewer database
    reviewer_db = {}
    if Path("data/reviewers_database.json").exists():
        with open("data/reviewers_database.json", "r", encoding="utf-8") as f:
            reviewer_db = json.load(f)

    # Load institution database
    institution_db = {}
    if Path("data/institutions_database.json").exists():
        with open("data/institutions_database.json", "r", encoding="utf-8") as f:
            institution_db = json.load(f)

    # Load institution mappings for reviewer pages
    institution_mappings = {}
    if Path("data/institution_mappings.json").exists():
        with open("data/institution_mappings.json", "r", encoding="utf-8") as f:
            institution_mappings = json.load(f)

    common = {
        "site_title": "ARR Great Reviewers",
        "description": "Visualisations of ARR Great Reviewers data.",
        "cycles": cycles,
    }
    render("index.html", {**common, "metrics": metrics}, SITE / "index.html")
    render(
        "reviewers.html",
        {**common, "metrics": metrics},
        SITE / "reviewers" / "index.html",
    )
    render(
        "institutions.html",
        {**common, "metrics": metrics},
        SITE / "institutions" / "index.html",
    )

    # Generate cycle-specific pages
    for cycle in cycles:
        cycle_name = cycle.replace("_", "-")
        cycle_context = {
            **common,
            "cycle_id": cycle,
            "cycle_name": cycle_name,
            "cycles": cycles,
        }
        render(
            "reviewers_cycle.html",
            cycle_context,
            SITE / "reviewers" / cycle / "index.html",
        )
        render(
            "institutions_cycle.html",
            cycle_context,
            SITE / "institutions" / cycle / "index.html",
        )

    # Generate individual reviewer pages (only for reviewers with OpenReview IDs)
    # When building a single reviewer, automatically skip building all reviewers
    # When building a single institution, also skip building all reviewers for performance
    if not skip_reviewers and not single_reviewer and not single_institution:
        # Prepare all reviewer page tasks for parallel generation
        reviewer_tasks = []
        for openreview_id, reviewer_data in reviewer_db.items():
            # URL-encode the OpenReview ID for file system compatibility
            # OpenReview IDs are in format ~First_LastN, we need to make them URL-safe
            url_safe_id = (
                openreview_id.replace("~", "").replace("/", "-").replace("\\", "-")
            )

            # Add institution URL-safe ID to reviewer data
            reviewer_data_with_url = reviewer_data.copy()
            reviewer_data_with_url["institution_url_safe_id"] = (
                institution_mappings.get(reviewer_data["institution"])
            )

            reviewer_context = {
                **common,
                "reviewer": reviewer_data_with_url,
            }

            output_path = SITE / "reviewer" / url_safe_id / "index.html"
            reviewer_tasks.append(
                ("reviewer_profile.html", reviewer_context, output_path)
            )

        # Generate all reviewer pages in parallel
        generate_pages_parallel(reviewer_tasks, "reviewer")
    elif single_reviewer:
        # Generate only the specified reviewer page
        if single_reviewer in reviewer_db:
            print(f"Generating single reviewer page for {single_reviewer}...")
            url_safe_id = (
                single_reviewer.replace("~", "").replace("/", "-").replace("\\", "-")
            )
            # Add institution URL-safe ID to reviewer data
            reviewer_data = reviewer_db[single_reviewer].copy()
            reviewer_data["institution_url_safe_id"] = institution_mappings.get(
                reviewer_data["institution"]
            )

            reviewer_context = {
                **common,
                "reviewer": reviewer_data,
            }
            render(
                "reviewer_profile.html",
                reviewer_context,
                SITE / "reviewer" / url_safe_id / "index.html",
            )
        else:
            print(f"Warning: Reviewer {single_reviewer} not found in database")
    else:
        print("Skipping reviewer pages generation...")

    # Generate individual institution pages
    # When building a single institution, automatically skip building all institutions
    # When building a single reviewer, also skip building all institutions for performance
    if not skip_institutions and not single_institution and not single_reviewer:
        # Prepare all institution page tasks for parallel generation
        institution_tasks = []
        for url_safe_id, institution_data in institution_db.items():
            institution_context = {
                **common,
                "institution": institution_data,
            }
            output_path = SITE / "institution" / url_safe_id / "index.html"
            institution_tasks.append(
                ("institution_profile.html", institution_context, output_path)
            )

        # Generate all institution pages in parallel
        generate_pages_parallel(institution_tasks, "institution")
    elif single_institution:
        # Generate only the specified institution page
        if single_institution in institution_db:
            print(f"Generating single institution page for {single_institution}...")
            institution_context = {
                **common,
                "institution": institution_db[single_institution],
            }
            render(
                "institution_profile.html",
                institution_context,
                SITE / "institution" / single_institution / "index.html",
            )
        else:
            print(f"Warning: Institution {single_institution} not found in database")
    else:
        print("Skipping institution pages generation...")

    render(
        "about.html",
        {**common},
        SITE / "about" / "index.html",
    )

    (SITE / "404.html").write_text("Page not found", encoding="utf-8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the ARR Great Reviewers site")
    parser.add_argument(
        "--skip-reviewers",
        action="store_true",
        help="Skip generating individual reviewer pages",
    )
    parser.add_argument(
        "--skip-institutions",
        action="store_true",
        help="Skip generating individual institution pages",
    )
    parser.add_argument(
        "--single-reviewer",
        type=str,
        help="Generate only the specified reviewer page (OpenReview ID)",
    )
    parser.add_argument(
        "--single-institution",
        type=str,
        help="Generate only the specified institution page (URL-safe ID)",
    )

    args = parser.parse_args()
    build_site(
        skip_reviewers=args.skip_reviewers,
        skip_institutions=args.skip_institutions,
        single_reviewer=args.single_reviewer,
        single_institution=args.single_institution,
    )
