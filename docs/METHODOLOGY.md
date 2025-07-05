# Methodology

This document explains the data collection and processing for ARR great reviewers.

## Data Collection

The dataset comes from the ACL Rolling Review public statistics endpoints. We
fetch JSON files for each iteration listed in `config/data_sources.toml`. Each
entry includes reviewer name, institution, counts of reviews and recognized
reviews, and the percentage of recognized reviews.

Downloaded files are validated against a reference schema and stored under
`data/raw/`. We then concatenate these files and clean numeric fields to build a
unified DataFrame. Aggregations produce metrics for top reviewers and
institutions which are exported as JSON under `data/metrics/`. These metrics
feed the static site visualisations.

## Ranking and Tie-Breaking

When ranking reviewers and institutions, ties are resolved using the following hierarchy:

### For Recognition Count Rankings:
1. **Primary**: Total number of recognized reviews (descending)
2. **Tie-breaker 1**: Recognition rate (recognized/total reviews) (descending)
3. **Tie-breaker 2**: Total number of reviews (descending)

### For Recognition Rate Rankings:
1. **Primary**: Recognition percentage (descending)
2. **Tie-breaker 1**: Total number of recognized reviews (descending)
3. **Tie-breaker 2**: Total number of reviews (descending)

This ensures consistent and fair rankings where reviewers with identical primary metrics are ordered by meaningful secondary criteria that reflect their overall contribution and review volume.

## Limitations

Limitations include potential inconsistencies in institution names and the fact
that recognition percentages can be influenced by small sample sizes. More
details can be found in the project README.
