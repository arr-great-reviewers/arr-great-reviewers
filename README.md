# ARR Great Reviewers

Most reviews get written, submitted, and forgotten. But across all ARR cycles where Area Chairs have awarded "Great Review" recognitions, thousands of reviews were so helpful that they received this distinction. Yet these recognitions get buried at the bottom of stats pages, and the amazing reviewers behind them remain invisible.

**ARR Great Reviewers** finally gives credit where it's due. This open-source project recognizes outstanding peer reviewers in ACL Rolling Review by collecting public statistics, computing comprehensive metrics, and publishing an interactive website that celebrates excellence in academic peer review.

Great reviews transform papers - they clarify murky ideas, identify crucial gaps, and push our field forward. Yet reviewers rarely get thanked for this essential work. This project is a way of saying what authors often think but rarely say: **thank you** to the reviewers who make our research better.

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

## Contributor guide

All code is formatted with `ruff` and type-checked with `pyright`. Please ensure
`make build` completes successfully before opening a pull request.

See the [About page](https://arrgreatreviewers.org/about/) for details on our motivation and methodology.
