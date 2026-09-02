# Sage X3 Discovery Monitor

A free, GitHub-hosted research dashboard for finding public evidence of recent Sage X3 implementations/users.

## What it does

- Searches Google News RSS for configurable Sage X3 queries.
- Searches DuckDuckGo HTML results as a second discovery route.
- Extracts likely company names and evidence URLs.
- Avoids duplicate evidence URLs.
- Scores freshness and evidence confidence heuristically.
- Stores results in `data/candidates.json`.
- Publishes a searchable dashboard through GitHub Pages.
- Runs automatically on a schedule using GitHub Actions.
- Keeps the data in Git, so the history is persistent and downloadable.

## Important limitation

This is deliberately a **free** build. It does not use a paid search API. Search-engine HTML/RSS formats can change, and job-board sites may block automated access. Treat the output as leads and verify each evidence page manually before submission.

## Setup

1. Create a public GitHub repository, e.g. `sage-x3-discovery`.
2. Upload all files from this folder, preserving `.github/workflows/`.
3. In GitHub, go to Settings -> Pages.
4. Under Build and deployment, choose **GitHub Actions**.
5. The included `pages.yml` workflow publishes `index.html`.
6. The included `discover.yml` workflow runs the search every Monday at 07:15 UTC and can also be run manually.
7. Open the Pages URL shown in Settings -> Pages.

## Changing search frequency

Edit `.github/workflows/discover.yml`.

The default is weekly. For example:
- weekly: `15 7 * * 1`
- twice weekly: `15 7 * * 1,4`

GitHub scheduled workflows use UTC unless a timezone is specified.

## Adding known/excluded companies

Edit `scripts/config.json` and add names to `known_companies`.

These are excluded from new candidate creation. This is optional because the competition team will filter duplicates; use it only for companies you know you don't want to see again.

## Adding search queries

Edit `scripts/config.json`. The default list concentrates on:
- new ERP
- implementation
- migration
- go-live
- job/recruitment evidence
- 2025/2026

Add country/language-specific queries as required.

## Downloading the records

The easiest route is:
- open the repository
- open `data/candidates.json`
- download the file

You can also use the GitHub web interface to download the repository as ZIP.

## Suggested future upgrades

- Add a dedicated job-board search API if a free quota becomes available.
- Add AI evidence verification.
- Add CSV/XLSX generation automatically.
- Add "Known", "Submitted", and "Rejected" states.
- Add email/notification when a new high-confidence candidate is found.
