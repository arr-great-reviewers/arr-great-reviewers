# ARR Great Reviewers

This project collects and visualises data from the ACL Rolling Review
"Great Reviewers" program. It downloads per-iteration statistics, computes
aggregate metrics, and publishes a static website with interactive charts.

## Quick start

```bash
make build
```

This command creates a `uv` virtual environment, installs dependencies, runs
the analytics pipeline, and builds the static site into `site/`.

## Contributor guide

All code is formatted with `ruff` and type-checked with `pyright`. Please ensure
`make build` completes successfully before opening a pull request.

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for details on data processing.
