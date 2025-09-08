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
- **`make build-fast`** - Fast build: data download, metrics calculation, and site generation excluding individual reviewer pages
- **`make build-single-reviewer`** - Single reviewer build: data download, metrics calculation, and site generation with only Marek Suppa's reviewer page

You can also run individual components:

- **`make data`** - Download and process ARR data only
- **`make metrics`** - Calculate metrics only (requires data)
- **`make site`** - Generate complete site only (requires data and metrics)
- **`make site-fast`** - Generate site excluding reviewer pages (requires data and metrics)
- **`make site-single-reviewer`** - Generate site with only Marek Suppa's reviewer page (requires data and metrics)

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
