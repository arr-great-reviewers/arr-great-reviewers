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

import hashlib
import json
import multiprocessing as mp
import re
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple
from xml.etree.ElementTree import Element, SubElement, tostring

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.reviewer_utils import (
    HIDDEN_AFFILIATION,
    format_cycle,
    get_reviewer_openreview_id,
    load_excluded_reviewers,
    load_hidden_affiliations,
)

TEMPLATES = Path("templates")
SITE = Path("site")
SITE.mkdir(parents=True, exist_ok=True)
BASE_URL = "https://arrgreatreviewers.org"


def _asset_version() -> str:
    """Short content hash of the CSS/JS, appended as ?v= so browsers drop stale copies."""
    digest = hashlib.sha256()
    for path in sorted(Path("static").glob("*/*.[cj]s")):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


ASSET_VERSION = _asset_version()


def _cycle_stats_pages() -> Dict[str, str]:
    """ARR's public stats page for each cycle, from the JSON URLs we download."""
    import tomllib

    with open("config/data_sources.toml", "rb") as f:
        sources = tomllib.load(f).get("sources", {})
    return {cycle: url.rsplit("/", 1)[0] + "/" for cycle, url in sources.items()}


CYCLE_STATS_PAGES = _cycle_stats_pages()
# Shown in the footer so readers can tell how fresh the numbers are
BUILD_DATE = datetime.now(timezone.utc).strftime("%B %-d, %Y")


def _configure(env: Environment) -> Environment:
    env.filters["cycle_label"] = format_cycle
    env.filters["cycle_stats_url"] = lambda cycle: CYCLE_STATS_PAGES.get(cycle)
    # " (Institution)" for page metadata; empty when the affiliation is hidden
    env.filters["affiliation_suffix"] = lambda inst: (
        f" ({inst})" if inst and inst != HIDDEN_AFFILIATION else ""
    )
    env.globals["asset_version"] = ASSET_VERSION
    env.globals["build_date"] = BUILD_DATE
    env.globals["latest_cycle"] = (
        format_cycle(max(CYCLE_STATS_PAGES)) if CYCLE_STATS_PAGES else ""
    )
    return env


def render(template: str, context: dict, out: Path) -> None:
    env = _configure(
        Environment(
            loader=FileSystemLoader(str(TEMPLATES)),
            autoescape=select_autoescape(["html", "xml"]),
        )
    )
    tmpl = env.get_template(template)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tmpl.render(**context), encoding="utf-8")


def render_template_parallel(task_data: Tuple[str, Dict[str, Any], Path]) -> bool:
    """Worker function for parallel template rendering"""
    template_name, context, output_path = task_data

    try:
        # Each process gets its own Jinja2 environment
        env = _configure(
            Environment(
                loader=FileSystemLoader(str(TEMPLATES)),
                autoescape=select_autoescape(["html", "xml"]),
                cache_size=500,
            )
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


def write_institution_redirects(institution_db: dict) -> int:
    """Keep old institution URLs working after spellings were merged.

    Every spelling in ARR's data used to get its own page at the slug of that exact
    spelling (or of its de-duplicated "X, X" form). When it now belongs to a merged
    institution, its old URL forwards to the merged page.
    """
    from src.institution_utils import (
        institution_name_to_url_safe_id,
        slugify_institution,
    )

    targets: Dict[str, str] = {}
    for cycle_file in Path("data/raw").glob("*.json"):
        for row in json.loads(cycle_file.read_text(encoding="utf-8")):
            raw = row.get("institution", "")
            new_id = institution_name_to_url_safe_id(raw)
            if new_id not in institution_db:
                continue
            doubled = re.match(r"^\s*(.+?)\s*,\s*\1\s*$", raw)
            for old_id in {
                slugify_institution(raw),
                slugify_institution(doubled.group(1) if doubled else raw),
            }:
                if old_id and old_id != new_id and old_id not in institution_db:
                    targets.setdefault(old_id, new_id)
    for old_id, new_id in targets.items():
        url = f"/institution/{new_id}/"
        out = SITE / "institution" / old_id / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={url}">'
            f'<link rel="canonical" href="{BASE_URL}{url}">'
            f'<meta name="robots" content="noindex"><title>Moved</title></head>'
            f'<body><p>This page moved to <a href="{url}">{url}</a>.</p></body></html>',
            encoding="utf-8",
        )
    return len(targets)


def generate_sitemap(
    cycles: list[str],
    reviewer_db: dict,
    institution_db: dict,
) -> None:
    """Generate sitemap.xml with all site pages."""
    lastmod = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    urlset = Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    def add_url(path: str, priority: str = "0.5", changefreq: str = "weekly") -> None:
        url_el = SubElement(urlset, "url")
        SubElement(url_el, "loc").text = f"{BASE_URL}{path}"
        SubElement(url_el, "lastmod").text = lastmod
        SubElement(url_el, "changefreq").text = changefreq
        SubElement(url_el, "priority").text = priority

    # Core pages
    add_url("/", priority="1.0", changefreq="weekly")
    add_url("/reviewers/", priority="0.9", changefreq="weekly")
    add_url("/institutions/", priority="0.9", changefreq="weekly")
    add_url("/about/", priority="0.7", changefreq="monthly")

    # Cycle pages
    for cycle in cycles:
        add_url(f"/reviewers/{cycle}/", priority="0.7", changefreq="monthly")
        add_url(f"/institutions/{cycle}/", priority="0.7", changefreq="monthly")

    # Reviewer profiles
    for openreview_id in reviewer_db:
        url_safe_id = (
            openreview_id.replace("~", "").replace("/", "-").replace("\\", "-")
        )
        add_url(f"/reviewer/{url_safe_id}/", priority="0.6", changefreq="monthly")

    # Institution profiles
    for url_safe_id in institution_db:
        add_url(f"/institution/{url_safe_id}/", priority="0.6", changefreq="monthly")

    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_body = tostring(urlset, encoding="unicode")
    (SITE / "sitemap.xml").write_text(xml_declaration + xml_body, encoding="utf-8")
    print(f"Generated sitemap.xml with {len(urlset)} URLs")


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

    # Old URLs of institution spellings that are now merged
    if institution_db_source.exists():
        moved = write_institution_redirects(
            json.loads(institution_db_source.read_text(encoding="utf-8"))
        )
        print(f"Wrote {moved} institution redirects")

    # Copy OpenReview profile mapping for JavaScript lookup, minus opted-out reviewers
    # and without the real affiliation of anyone who asked to hide it
    openreview_mapping_source = Path("data/openreview_profile_mapping.json")
    if openreview_mapping_source.exists():
        mapping = json.loads(openreview_mapping_source.read_text(encoding="utf-8"))
        excluded = load_excluded_reviewers()
        if excluded:
            for category in ("single_matches", "multiple_matches", "no_matches"):
                entries = mapping.get(category, {})
                for key in [
                    k
                    for k, v in entries.items()
                    if excluded & set(v.get("openreview_profiles", []))
                    or get_reviewer_openreview_id(*k.split("|", 1), mapping) in excluded
                ]:
                    del entries[key]
        hidden = load_hidden_affiliations()
        if hidden:
            for category in ("single_matches", "multiple_matches", "no_matches"):
                entries = mapping.get(category, {})
                for key in [
                    k
                    for k, v in entries.items()
                    if hidden & set(v.get("openreview_profiles", []))
                ]:
                    entry = entries.pop(key)
                    entry["institution"] = HIDDEN_AFFILIATION
                    entries[
                        f"{entry.get('name', key.split('|', 1)[0])}|{HIDDEN_AFFILIATION}"
                    ] = entry
        (SITE / "data" / "openreview_profile_mapping.json").write_text(
            json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
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
    render(
        "index.html",
        {**common, "metrics": metrics, "recognized_reviewer_count": len(reviewer_db)},
        SITE / "index.html",
    )
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
        cycle_name = format_cycle(cycle)
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

    # Copy robots.txt to site root
    robots_source = Path("static/robots.txt")
    if robots_source.exists():
        shutil.copy2(robots_source, SITE / "robots.txt")

    # Generate sitemap.xml
    generate_sitemap(cycles, reviewer_db, institution_db)


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
