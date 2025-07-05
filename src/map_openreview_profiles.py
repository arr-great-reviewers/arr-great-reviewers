#!/usr/bin/env python3

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

import requests
import typer
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import track
from rich.table import Table

app = typer.Typer(help="Map reviewer names to OpenReview profiles")
console = Console()


def normalize_name(name: str) -> str:
    """Convert name to OpenReview profile format: ~First_Last$n"""
    # Remove special characters and normalize spaces
    name = re.sub(r"[^\w\s-]", "", name)
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    return name


def fetch_openreview_profile(profile_id: str) -> Optional[Dict]:
    """Fetch OpenReview profile data"""
    url = f"https://openreview.net/profile?id={profile_id}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            content = response.text
            actual_profile_id = profile_id
            redirected = False

            # Check for shouldRedirect and preferredId in the page content
            redirect_match = re.search(
                r'\\"shouldRedirect\\":\s*true.*?\\"preferredId\\":\s*\\"([^"]+)\\"',
                content,
            )
            if redirect_match:
                actual_profile_id = redirect_match.group(1)
                redirected = True

            return {
                "profile_id": actual_profile_id,
                "original_id": profile_id,
                "exists": True,
                "content": content,
                "redirected": redirected,
            }
        return None
    except requests.RequestException:
        return None


def extract_institution_from_profile(profile_content: str) -> List[str]:
    """Extract text content from history section of OpenReview profile HTML"""
    # Parse the HTML content
    soup = BeautifulSoup(profile_content, "html.parser")

    # Find all sections with class="history"
    history_sections = soup.find_all("section", class_="history")

    # Extract text from each history section
    history_texts = []
    for section in history_sections:
        # Get all text from the history section, preserving some structure
        section_text = section.get_text(separator=" ", strip=True)
        if section_text:
            history_texts.append(section_text)

    return history_texts


def institution_matches(
    target_institution: str, profile_institutions: List[str]
) -> bool:
    """Check if target institution matches any profile institution"""
    target_lower = target_institution.lower()

    for profile_inst in profile_institutions:
        profile_lower = profile_inst.lower()

        # Exact match
        if target_lower == profile_lower:
            return True

        # Partial match (either direction)
        if target_lower in profile_lower or profile_lower in target_lower:
            return True

        # Common abbreviations and variations
        # Add more as needed based on your data
        abbreviations = {
            "university": "univ",
            "institute": "inst",
            "technology": "tech",
            "college": "coll",
        }

        target_abbrev = target_lower
        profile_abbrev = profile_lower

        for full, abbrev in abbreviations.items():
            target_abbrev = target_abbrev.replace(full, abbrev)
            profile_abbrev = profile_abbrev.replace(full, abbrev)

        if target_abbrev == profile_abbrev:
            return True

    return False


def find_matching_profiles(
    name: str, institution: str, max_profiles: int = 30
) -> List[str]:
    """Find matching OpenReview profiles for a given name and institution.

    Returns a list of matching profile IDs (deduplicated).
    """
    # Generate profile candidates
    normalized_name = normalize_name(name)
    profile_candidates = [f"~{normalized_name}{i}" for i in range(1, max_profiles + 1)]

    matching_profiles = set()  # Use set to avoid duplicates

    # Check each profile candidate
    for profile_id in profile_candidates:
        profile_data = fetch_openreview_profile(profile_id)

        if profile_data:
            profile_institutions = extract_institution_from_profile(
                profile_data["content"]
            )

            if institution_matches(institution, profile_institutions):
                # Use the actual profile ID (in case of redirect)
                actual_id = profile_data["profile_id"]

                # Only add if not already found (deduplication)
                if actual_id not in matching_profiles:
                    matching_profiles.add(actual_id)

                    if profile_data.get("redirected"):
                        console.print(
                            f"[green]✓[/green] Found match: {profile_id} → {actual_id} for {name}"
                        )
                    else:
                        console.print(
                            f"[green]✓[/green] Found match: {actual_id} for {name}"
                        )
                else:
                    # Profile already found through different redirect
                    if profile_data.get("redirected"):
                        console.print(
                            f"[blue]i[/blue] Duplicate: {profile_id} → {actual_id} for {name} (already found)"
                        )

    # Convert back to list and return
    return list(matching_profiles)


def load_reviewer_data(data_dir: Path) -> List[Dict]:
    """Load reviewer data from JSON files"""
    reviewers = []

    for json_file in data_dir.glob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    reviewers.extend(data)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            console.print(f"[red]Error loading {json_file}: {e}[/red]")

    return reviewers


def map_profiles(
    reviewers: List[Dict], max_profiles: int = 30, output_file: Optional[Path] = None
) -> Dict:
    """Map reviewer names to OpenReview profiles"""

    results = {
        "metadata": {
            "total_processed": 0,
            "single_matches": 0,
            "multiple_matches": 0,
            "no_matches": 0,
        },
        "single_matches": {},
        "multiple_matches": {},
        "no_matches": {},
    }

    # Process each reviewer
    for reviewer in track(reviewers, description="Mapping profiles..."):
        name = reviewer.get("name", "")
        institution = reviewer.get("institution", "")

        if not name or not institution:
            continue

        results["metadata"]["total_processed"] += 1

        # Use the abstracted function to find matches
        matching_profiles = find_matching_profiles(name, institution, max_profiles)

        # Categorize results
        key = f"{name}|{institution}"

        if len(matching_profiles) == 1:
            results["single_matches"][key] = {
                "name": name,
                "institution": institution,
                "openreview_profiles": matching_profiles,
                "match_count": len(matching_profiles),
            }
            results["metadata"]["single_matches"] += 1
            console.print(
                f"[bright_green]✓ MATCH FOUND[/bright_green] for {name} @ {institution}"
            )
        elif len(matching_profiles) > 1:
            results["multiple_matches"][key] = {
                "name": name,
                "institution": institution,
                "openreview_profiles": matching_profiles,
                "match_count": len(matching_profiles),
            }
            results["metadata"]["multiple_matches"] += 1
            console.print(
                f"[yellow]⚠ MULTIPLE MATCHES[/yellow] for {name} @ {institution}: {matching_profiles}"
            )
        else:
            results["no_matches"][key] = {
                "name": name,
                "institution": institution,
                "openreview_profiles": [],
                "match_count": 0,
            }
            results["metadata"]["no_matches"] += 1
            console.print(
                f"[bright_red]✗ NO MATCH[/bright_red] for {name} @ {institution}"
            )

    # Save results
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        console.print(f"[green]Results saved to {output_file}[/green]")

    return results


def load_existing_results(results_file: Path) -> Optional[Dict]:
    """Load existing results from JSON file"""
    try:
        with open(results_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        console.print(f"[red]Error loading results file {results_file}: {e}[/red]")
        return None


def reprocess_no_matches(results: Dict, max_profiles: int = 30) -> Dict:
    """Reprocess entries from no_matches and move found matches to appropriate sections"""
    if not results.get("no_matches"):
        console.print("[blue]No unmatched entries to reprocess[/blue]")
        return results

    # Make a copy of no_matches to iterate over
    no_matches_copy = dict(results["no_matches"])
    newly_found = []

    console.print(
        f"[blue]Reprocessing {len(no_matches_copy)} unmatched entries...[/blue]"
    )

    for key, entry in track(no_matches_copy.items(), description="Reprocessing..."):
        name = entry["name"]
        institution = entry["institution"]

        # Use the abstracted function to find matches
        matching_profiles = find_matching_profiles(name, institution, max_profiles)

        # If matches found, move from no_matches to appropriate section
        if matching_profiles:
            # Remove from no_matches
            del results["no_matches"][key]
            results["metadata"]["no_matches"] -= 1

            # Update entry with found profiles
            entry["openreview_profiles"] = matching_profiles
            entry["match_count"] = len(matching_profiles)

            # Add to appropriate section
            if len(matching_profiles) == 1:
                results["single_matches"][key] = entry
                results["metadata"]["single_matches"] += 1
                console.print(
                    f"[bright_green]✓ NEW MATCH FOUND[/bright_green] for {name} @ {institution}"
                )
            else:
                results["multiple_matches"][key] = entry
                results["metadata"]["multiple_matches"] += 1
                console.print(
                    f"[yellow]⚠ NEW MULTIPLE MATCHES[/yellow] for {name} @ {institution}: {matching_profiles}"
                )

            newly_found.append(entry)
        else:
            console.print(
                f"[bright_red]✗ STILL NO MATCH[/bright_red] for {name} @ {institution}"
            )

    console.print("\n" + "=" * 60 + "\n")
    if newly_found:
        console.print(
            f"[bright_green]🎉 Found {len(newly_found)} new matches during reprocessing![/bright_green]"
        )
        console.print("\n[bright_green]Newly matched reviewers:[/bright_green]")
        for entry in newly_found:
            console.print(f"  • {entry['name']} @ {entry['institution']}")
    else:
        console.print(
            "[bright_blue]No new matches found during reprocessing[/bright_blue]"
        )

    return results


def display_summary(results: Dict):
    """Display summary table of results"""
    table = Table(title="OpenReview Profile Mapping Summary")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="magenta")

    metadata = results["metadata"]
    table.add_row("Total Processed", str(metadata["total_processed"]))
    table.add_row("Single Matches", str(metadata["single_matches"]))
    table.add_row("Multiple Matches", str(metadata["multiple_matches"]))
    table.add_row("No Matches", str(metadata["no_matches"]))

    console.print(table)


@app.command()
def reprocess(
    results_file: Path = typer.Option(
        Path("data/openreview_profile_mapping.json"),
        "--results-file",
        "-r",
        help="Path to existing results JSON file",
    ),
    max_profiles: int = typer.Option(
        30,
        "--max-profiles",
        "-m",
        help="Maximum number of profile variants to try (1 to N)",
    ),
):
    """Reprocess no-matches from existing results file and update with any new matches found."""

    if not results_file.exists():
        console.print(f"[red]Error: Results file {results_file} does not exist[/red]")
        console.print(
            "[blue]Hint: Run the main command first to generate initial results[/blue]"
        )
        raise typer.Exit(1)

    # Load existing results
    console.print(f"[blue]Loading existing results from {results_file}...[/blue]")
    results = load_existing_results(results_file)

    if not results:
        raise typer.Exit(1)

    # Display current summary
    console.print("[blue]Current state:[/blue]")
    display_summary(results)

    # Reprocess no matches
    console.print("[blue]Reprocessing unmatched entries...[/blue]")
    updated_results = reprocess_no_matches(results, max_profiles)

    # Save updated results back to file
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(updated_results, f, indent=2, ensure_ascii=False)

    console.print(f"[green]Updated results saved to {results_file}[/green]")

    # Display updated summary
    console.print("[blue]Updated state:[/blue]")
    display_summary(updated_results)


@app.command()
def main(
    data_dir: Path = typer.Option(
        Path("data/raw"),
        "--data-dir",
        "-d",
        help="Directory containing reviewer JSON files",
    ),
    max_profiles: int = typer.Option(
        30,
        "--max-profiles",
        "-m",
        help="Maximum number of profile variants to try (1 to N)",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (defaults to data/openreview_profile_mapping.json)",
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l", help="Limit number of reviewers to process (for testing)"
    ),
):
    """Map reviewer names to OpenReview profiles by matching institution information."""

    if not data_dir.exists():
        console.print(f"[red]Error: Data directory {data_dir} does not exist[/red]")
        raise typer.Exit(1)

    # Set default output file if not specified
    if output_file is None:
        output_file = Path("data/openreview_profile_mapping.json")

    # Load reviewer data
    console.print(f"[blue]Loading reviewer data from {data_dir}...[/blue]")
    reviewers = load_reviewer_data(data_dir)

    if not reviewers:
        console.print("[red]No reviewer data found![/red]")
        raise typer.Exit(1)

    # Apply limit if specified
    if limit:
        reviewers = reviewers[:limit]
        console.print(f"[yellow]Processing limited to {limit} reviewers[/yellow]")

    console.print(f"[blue]Found {len(reviewers)} reviewers to process[/blue]")

    # Map profiles
    results = map_profiles(reviewers, max_profiles, output_file)

    # Display summary
    display_summary(results)


if __name__ == "__main__":
    app()
