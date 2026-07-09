# Stop committing parquet files — local cache only

**Date:** 2026-07-09

**Status:** Draft for review

**Scope:** Remove all `.parquet` files from git tracking; keep them on disk as `load_dataframe`'s
local backup cache. CSV outputs remain committed unchanged. No zarr/climate outputs are affected.

## Context & goal

Every fetch notebook now writes `save_dataframe` output as a parquet + CSV pair, and reads it back
via `load_dataframe(path, max_age_days=7)` as a backup cache when the underlying HTTP client bypasses
`cache/aiohttp_cache.sqlite`. Since CSV is already committed as the transparency copy of every table,
committing parquet too is redundant storage of the same data — and, as a corollary, is actively
adding a bug: **git resets file mtimes to checkout time on every clone/checkout**, so a freshly
checked-out committed parquet always looks "brand new" to `load_dataframe`'s mtime-based freshness
check, regardless of the data's true age. A CI re-execution (freeze-miss) could therefore silently
skip a live fetch it should have made. Untracking parquet removes this failure mode entirely — CI
never has a stale-but-fresh-looking file to misread.

## Decision

- **Untrack, don't delete.** `git rm -r --cached` on the 16 currently-tracked `.parquet` files
  (verified list, one per subfolder):
  - `data/climate/` — 2
  - `data/hydrography/` — 1
  - `data/tceq_waterquality/` — 3
  - `data/twdb_groundwater/` — 4
  - `data/usgs_waterdata/` — 6
  Working-tree copies are untouched, so `load_dataframe`'s local caching keeps working exactly as
  today for anyone with an existing checkout.
- **`.gitignore`:** add `data/**/*.parquet` under the existing `## Project-specific ##` section.
- **Out of scope, unaffected:** CSV files (still committed, unchanged), the committed zarr
  climatology/trend grids in `data/climate/` (different format, different helper —
  `save_datacube`/zarr, not `save_dataframe`/parquet), and the (unrelated, in-flight)
  Excel-workbook-export feature.
- **No notebook code changes.** Every notebook already handles a missing parquet correctly:
  `load_dataframe` returns `None` on a miss (triggering a fresh fetch), and the one hard dependency
  each notebook has — `huc8_watersheds.parquet`, read directly rather than through `load_dataframe`
  — already raises a clear `FileNotFoundError` pointing at notebook 1 if it's missing. This doesn't
  introduce a new failure mode: `pixi run render` (local and CI) executes notebooks 1→5 in one
  continuous pass, so notebook 1 always produces that file before notebook 2 reads it.
- **Documentation:** update `CLAUDE.md`'s "Storage & data" section — the "Git-ignored / Committed"
  bullets currently say parquet is committed; correct them to state parquet is local-cache-only
  (git-ignored) and CSV is the committed record/transparency copy. Also touch the sentence in
  "Notebooks & helpers" that currently frames `load_dataframe`/`save_dataframe` output as committed.

## Testing / verification

- `git status` after untracking shows the 16 parquet files as newly-ignored (not as pending
  deletions) and no working-tree files are actually removed from disk.
- `pixi run test` still passes unchanged (the `test_save_dataframe.py` suite operates on `tmp_path`,
  not the committed `data/` files, so it's unaffected).
- Run any one fetch notebook (e.g. `3_usgs_waterdata`) headlessly with the existing on-disk parquet
  present and confirm it still logs a cache hit (`load_dataframe` finds the file, skips the network
  call) — proving local caching is unaffected by the untracking.
- `pixi run render` still succeeds end-to-end (notebooks 1→5 in one pass).

## Out of scope

- Deleting the parquet files from disk (they stay, as the cache).
- Any change to CSV commit behavior, zarr/climate outputs, or the Excel workbook export feature.
- Adding a commit-time or CI cache-warming step for parquet — CI simply refetches live data each run
  now (the correct behavior this change restores).
