# ARR Great Reviewers

Most reviews get written, submitted, and forgotten. But across all ARR cycles, thousands of reviews were so exceptional that Area Chairs flagged them as "Great Reviews." These aren't participation trophies -- they're the reviews that saved papers from rejection, caught fatal flaws others missed, or suggested the key experiment that made everything click. Yet these recognitions end up buried at the bottom of stats pages while the reviewers who wrote them remain invisible.

**ARR Great Reviewers** brings together all the "Great Review" recognitions from across ARR's cycle pages into one place. It allows reviewers to see their cumulative impact -- how many authors they've helped, how their reviewing has evolved, and where they stand among peers. It's a small way to acknowledge those who pour effort into making others' research better.

The entire analysis is transparent and open-source, with code available in this repository, covering all ARR cycles where "Great Review" data is available.

## Quick start

```bash
make build
```

This command creates a `uv` virtual environment, installs dependencies, runs
the analytics pipeline, and builds the static site into `site/`.

## Build targets

The following Makefile targets are available for different build scenarios:

- **`make build`** - Full build: data download, metrics calculation, and complete site generation (default)
- **`make build-mapped`** - Full build that fails if any reviewers remain unmapped
- **`make build-fast`** - Fast build: data download, metrics calculation, and site generation excluding individual reviewer pages
- **`make build-single-reviewer`** - Single reviewer build: data download, metrics calculation, and site generation with only Marek Suppa's reviewer page

You can also run individual components:

- **`make data`** - Download and process ARR data only
- **`make metrics`** - Calculate metrics only (requires data)
- **`make site`** - Generate complete site only (requires data and metrics)
- **`make site-fast`** - Generate site excluding reviewer pages (requires data and metrics)
- **`make site-single-reviewer`** - Generate site with only Marek Suppa's reviewer page (requires data and metrics)

### OpenReview profile mapping

- **`make map-openreview`** - Build a full OpenReview mapping from scratch (writes `data/openreview_profile_mapping.json`)
- **`make map-openreview-incremental`** - Only process reviewers not yet present in the mapping file
- **`uv run python -m src.map_openreview_profiles incremental --reprocess-no-matches`** - Reprocess previously unmatched reviewers before scanning for new ones
- **`make map-openreview-check`** - Fail if any reviewers in `data/raw` are still unmapped
- **`make map-openreview-check-top`** - Fail if any top 100 reviewers per cycle are still unmapped
- **`make map-openreview-reprocess-top`** - Reprocess no-matches only for the top 100 reviewers per cycle

To check a specific set of cycles or a different cutoff:

```bash
uv run python -m src.map_openreview_profiles check --top-n-per-cycle 100 --cycles 2025_07,2025_10 --fail-on-missing
```

To reprocess only those top reviewers:

```bash
uv run python -m src.map_openreview_profiles reprocess-top --top-n-per-cycle 100 --cycles 2025_07,2025_10
```

Note: `map-openreview-reprocess-top` uses existing `data/metrics/reviewers_*.json` files. If those files are stale or missing, run `make metrics` first.

Profile lookup uses the OpenReview `profiles/search` API, which requires login. Provide
authenticated OpenReview cookies via environment variables:

```bash
export OPENREVIEW_ACCESS_TOKEN="..."
export OPENREVIEW_REFRESH_TOKEN="..."
make map-openreview-reprocess-top
```

Alternatively, provide a cookie JSON dump from a browser session (or drop it at
`./openreview_cookies.json`):

```bash
export OPENREVIEW_COOKIES_FILE="/path/to/openreview_cookies.json"
make map-openreview-reprocess-top
```

Each reviewer costs one search request (all profiles with that full name, including
their institution history); a profile matches when its history matches the reviewer's
institution. OpenReview rate-limits this endpoint (roughly 100–130 requests/hour), so
the mapper backs off on HTTP 429 and honours `Retry-After`; large batches take hours.
Lookups that still fail are skipped rather than recorded as "no match", so a later
`incremental` run picks them up.

If automatic lookup finds multiple candidate profiles, the candidates remain in
`multiple_matches` as evidence but no profile ID is used until a manual mapping resolves
the ambiguity.

### Reviewer contact details

- **`make contacts`** - Collect contact candidates for the top 100 reviewers overall (`--top-n` changes the cutoff)

For each reviewer the collector fetches the OpenReview profile in one batched,
authenticated request (same cookies as above) and crawls the listed homepage —
including same-site JS bundles and a few contact-like pages, and decoding Cloudflare and
shifted-`mailto:` obfuscation. Reviewers still without a domain-confirmed address then
get the first pages of up to 25 recent papers from their ACL Anthology author page read,
and finally up to 15 recent arXiv papers found by author name (throttled to one request
every 3 seconds).

Paper headers list every co-author, so a paper address is kept only if it clearly
resembles one of the reviewer's OpenReview names (`ido.dagan`, `nbalepur`), or if it is
an initials-style username (`th656`, `nv2006`, `cli`) on an institutional domain from
their OpenReview profile. arXiv name searches return namesakes, so arXiv addresses must
be domain-confirmed.

Each candidate is scored against the masked email domains OpenReview shows
(`****@cmu.edu`): `high` means an institutional domain from the profile matches, or a
gmail-style domain from the profile plus a name match; `medium` means only the name
matches. Addresses that only the layout of a paper can attribute go in
`data/contacts/manual_contacts.toml` (keyed by OpenReview id, with `email`, `source`,
`note`); they override automatic results and are marked `manual`.

The result is written to `data/contacts/top100_contacts.{csv,json}`. Everything under
`data/contacts/` is gitignored and contains personal data: check every row by hand
before sending anything, and delete the files when you are done.

### Removing a reviewer

Reviewers who ask to be removed are listed by OpenReview ID in the
`EXCLUDED_REVIEWERS` environment variable (separated by commas, spaces or newlines).
`src/arr_dl.py` drops their rows from the downloaded ARR data, so they disappear from
every page, ranking and institution total, and from the data files copied to the site.

In CI the variable comes from the `EXCLUDED_REVIEWERS` GitHub Actions secret, so the
repository never lists who opted out. To remove someone, add their ID to the secret
(Settings → Secrets and variables → Actions) and re-run the deploy workflow. For a
local build:

```bash
EXCLUDED_REVIEWERS="~Jane_Doe1" make build
```

Rows only match when the reviewer's name and institution map to their OpenReview ID,
so check that the mapping exists (`make map-openreview-check`) before relying on it.

### Hiding a reviewer's affiliation

Reviewers who want to stay listed but without their affiliation go in the
`HIDDEN_AFFILIATIONS` environment variable (OpenReview IDs, same format as above; in
CI the `HIDDEN_AFFILIATIONS` GitHub Actions secret). `src/arr_dl.py` replaces their
affiliation with "Affiliation not shown" at download, after the OpenReview lookup, so
their profile, ranking rows and the data files on the site never contain it. Their
Great Reviews no longer count toward the old institution, and the placeholder is kept
out of institution rankings. ARR's own statistics pages still show the original.

```bash
HIDDEN_AFFILIATIONS="~Jane_Doe1" make build
```

### Performance comparison

- **Full build** (`make build`): Generates all pages including ~2000+ individual reviewer pages
- **Fast build** (`make build-fast`): Skips individual reviewer pages, significantly faster for development
- **Single reviewer build** (`make build-single-reviewer`): Generates only one reviewer page for testing reviewer-specific functionality

## Configuration

The project uses configuration files in the `config/` directory to control data sources and reviewer mappings:

### `config/data_sources.toml`

Maps ARR cycle names to their JSON data source URLs from the ACL Rolling Review statistics endpoints.

**Format:**

```toml
[sources]
2024_04 = "https://stats.aclrollingreview.org/iterations/2024/april/great_reviewers_data.json"
2024_06 = "https://stats.aclrollingreview.org/iterations/2024/june/great_reviewers_data.json"
```

**Usage:** The `src/arr_dl.py` module reads this file to download data for each configured ARR cycle. Add new cycles by adding entries with the cycle name as key and the corresponding stats URL as value.

### `config/manual_openreview_mappings.toml`

Manual mappings of reviewer names to OpenReview profile IDs for cases where automatic matching fails or needs override.

**Format:**

```toml
[mappings]
"Full Name|Institution" = "openreview_profile_id"
```

**Example:**

```toml
[mappings]
"John Doe|Yale University" = "~John_Doe123"
```

**Usage:** The `src/reviewer_utils.py` module loads these mappings to supplement automatic OpenReview profile matching. Add entries when reviewers need manual profile linking or to fix mismatched profiles.

## Contributor guide

All code is formatted with `ruff` and type-checked with `pyright`. Please ensure
`make build` completes successfully before opening a pull request.

See the [About page](https://arrgreatreviewers.org/about/) for details on our motivation and methodology.
