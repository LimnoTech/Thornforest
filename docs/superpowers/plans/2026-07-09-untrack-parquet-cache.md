# Untrack Parquet Files (Local Cache Only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop committing `.parquet` files to git while keeping them on disk as `load_dataframe`'s
local backup cache; CSV stays the committed transparency copy.

**Architecture:** Add a `.gitignore` pattern for `data/**/*.parquet`, untrack the 16 currently
committed parquet files with `git rm --cached` (working-tree copies untouched), and correct the
`CLAUDE.md` "Storage & data" section that currently documents parquet as committed.

**Tech Stack:** git, no code changes (Python/notebooks unaffected).

## Global Constraints

- Do not delete any parquet file from disk — only remove it from git's index.
- Do not touch CSV files, zarr outputs, or any notebook `.py`/`.ipynb` code.
- Per `CLAUDE.md`: this is a single task-group round — branch directly off `main` (no integration
  branch needed), agent does not commit, leave everything staged for the user.

---

### Task 1: Untrack parquet files, update `.gitignore` and `CLAUDE.md`

**Files:**
- Modify: `.gitignore` (add pattern under the `## Project-specific ##` section, ~line 221-236)
- Modify: `CLAUDE.md` (Storage & data section, lines 177-190; helper-inventory line 161)
- Untrack (via `git rm --cached`, not deleted from disk):
  - `data/climate/conus404_trends_by_huc8.parquet`
  - `data/climate/conus404_wateryear_by_huc8.parquet`
  - `data/hydrography/huc8_watersheds.parquet`
  - `data/tceq_waterquality/tceq_monitoring_locations.parquet`
  - `data/tceq_waterquality/tceq_results.parquet`
  - `data/tceq_waterquality/tceq_trends.parquet`
  - `data/twdb_groundwater/twdb_trends.parquet`
  - `data/twdb_groundwater/twdb_water_levels.parquet`
  - `data/twdb_groundwater/twdb_water_quality.parquet`
  - `data/twdb_groundwater/twdb_wells.parquet`
  - `data/usgs_waterdata/usgs_daily_values.parquet`
  - `data/usgs_waterdata/usgs_field_measurements.parquet`
  - `data/usgs_waterdata/usgs_monitoring_locations.parquet`
  - `data/usgs_waterdata/usgs_monitoring_locations_parameters.parquet`
  - `data/usgs_waterdata/usgs_samples.parquet`
  - `data/usgs_waterdata/usgs_trends.parquet`

**Interfaces:** None — no code changes, this task is self-contained.

- [ ] **Step 1: Create a branch off `main`**

```bash
git checkout main
git pull origin main
git checkout -b untrack-parquet-cache
```

Expected: new branch created, working tree clean, matches `origin/main`.

- [ ] **Step 2: Verify the exact set of tracked parquet files matches this plan's list**

```bash
git ls-files 'data/*.parquet' 'data/**/*.parquet' | sort
```

Expected: exactly the 16 paths listed above (one per line, alphabetically sorted). If the list
differs (e.g. a new notebook has added more since this plan was written), untrack whatever the
command actually returns instead of the hardcoded list above — this command is the source of truth.

- [ ] **Step 3: Untrack the files without deleting them from disk**

```bash
git ls-files 'data/*.parquet' 'data/**/*.parquet' | xargs git rm --cached
```

Expected output: one `rm 'data/...'` line per file (git's untrack message), and all 16 `.parquet`
files still physically present in `data/` afterward:

```bash
find data -name '*.parquet' | wc -l   # still 16 — confirms nothing was deleted from disk
```

- [ ] **Step 4: Add the `.gitignore` pattern**

In `.gitignore`, under the `## Project-specific ##` section, add a new entry after the existing
`# Raw CONUS404 monthly gridded datacube...` block (which currently documents parquet as
committed — that comment needs correcting too):

Replace:
```gitignore
# Raw CONUS404 monthly gridded datacube (~57 MB) — regenerated from OSN by NB2.
# Small DERIVED products (climatology/trend zarrs, per-HUC-8 parquet/CSV) ARE committed.
/data/climate/conus404_monthly_grid.zarr/
```

With:
```gitignore
# Raw CONUS404 monthly gridded datacube (~57 MB) — regenerated from OSN by NB2.
# Small DERIVED products (climatology/trend zarrs) ARE committed; their per-HUC-8 CSV is too —
# the parquet copy is local-cache-only (see the rule below).
/data/climate/conus404_monthly_grid.zarr/

# Parquet is a local backup cache for load_dataframe (see CLAUDE.md § Storage & data) — not
# committed. The CSV written alongside each parquet by save_dataframe IS committed.
/data/**/*.parquet
```

- [ ] **Step 5: Verify `git status` shows untracking, not deletion, and the new ignore rule works**

```bash
git status
```

Expected: the 16 files appear staged as deletions from the index (`deleted:` under "Changes to be
committed"), `.gitignore` and `CLAUDE.md` appear as modified, and **no** parquet file appears under
"Untracked files" (proving the new `.gitignore` pattern successfully suppresses them — if any
parquet file *does* show up as untracked instead of being silently ignored, the glob pattern is
wrong and needs fixing before continuing).

- [ ] **Step 6: Update `CLAUDE.md` — Storage & data section**

Replace (lines 179-187):
```markdown
- **Tabular** (Geo)DataFrames → **GeoParquet + a CSV copy** via `save_dataframe` (parquet is compact and
  typed — what notebooks read; the CSV, geometry as WKT, is for transparency).
- **Datacubes** (anything read natively with xarray) → **zarr v3 with an explicit `ZstdCodec`**
  (Icechunk-ready) via `save_datacube`, **never parquet** (parquet flattens away dims/coords/CRS/chunking).
- **Two cache layers, kept separate:** `cache/` (git-ignored) is the persistent **HTTP request
  cache** (sqlite; HyRiver + `async_retriever`) that makes re-runs fast; `data/` (committed) holds the
  curated **outputs** other notebooks read (written every run, not freshness-gated).
- **Git-ignored:** `cache/`, `data_temp/` (scratch/raw downloads), `.pixi/`, `_site/`, `.quarto/`.
  **Committed:** `data/` outputs, `pixi.lock`, and `_freeze/` (the render cache).
```

With:
```markdown
- **Tabular** (Geo)DataFrames → **GeoParquet + a CSV copy** via `save_dataframe` (parquet is compact,
  typed, and what notebooks read back via `load_dataframe`; the CSV, geometry as WKT, is the
  committed transparency copy).
- **Datacubes** (anything read natively with xarray) → **zarr v3 with an explicit `ZstdCodec`**
  (Icechunk-ready) via `save_datacube`, **never parquet** (parquet flattens away dims/coords/CRS/chunking).
- **Two cache layers, kept separate:** `cache/` (git-ignored) is the persistent **HTTP request
  cache** (sqlite; HyRiver + `async_retriever`) that makes re-runs fast; `data/*.parquet` (also
  git-ignored, but committed CSVs sit right next to it) is a second, **backup** cache — read by
  `load_dataframe` when a source library bypasses `cache/` entirely (see below). Neither layer is
  committed; only the CSV output derived from them is.
- **Git-ignored:** `cache/`, `data_temp/` (scratch/raw downloads), `.pixi/`, `_site/`, `.quarto/`,
  and (as of this round) all `data/` parquet files (pattern `` data/**/*.parquet `` in
  `.gitignore`) — parquet is a local cache, not a deliverable.
  **Committed:** `data/*.csv` outputs, the derived climate zarr grids, `pixi.lock`, and `_freeze/`
  (the render cache). A fresh clone has no parquet until a notebook runs once to (re)populate the
  cache — CSVs are already there as the committed record.
```

- [ ] **Step 7: Update `CLAUDE.md` — helper inventory line (parenthetical was accurate but now worth
  reinforcing that parquet is local-only)**

Replace (line 161):
```markdown
  - `io` — `save_dataframe`, `load_dataframe` (parquet-as-backup-cache read side), `save_datacube`.
```

With:
```markdown
  - `io` — `save_dataframe`, `load_dataframe` (parquet-as-backup-cache read side — parquet itself is
    git-ignored, only its CSV sibling is committed), `save_datacube`.
```

- [ ] **Step 8: Sanity-check no notebook code needs to change**

```bash
grep -rn "FileNotFoundError" notebooks/*.py
```

Expected: each of notebooks 2-5 has one `FileNotFoundError` guard on
`S.data_dir / "hydrography" / "huc8_watersheds.parquet"` pointing the user at notebook 1 — confirms
the existing missing-file handling is already correct and this task needs no code changes. (This is
a read-only check, not a step that modifies anything.)

- [ ] **Step 9: Confirm the test suite is unaffected**

```bash
pixi run test
```

Expected: all tests pass, unchanged — `notebooks/tests/test_save_dataframe.py` operates entirely on
`tmp_path`, never touching the committed `data/` files, so untracking them doesn't affect it.

- [ ] **Step 10: Confirm local caching still works end-to-end with the now-untracked files**

Run one fetch notebook headlessly (its parquet files are still present on disk, just untracked) and
confirm it logs a cache hit instead of refetching:

```bash
pixi run jupyter nbconvert --to notebook --execute --inplace notebooks/3_usgs_waterdata.ipynb
grep -o "using cached [^\"]*" notebooks/3_usgs_waterdata.ipynb | head -20
```

Expected: at least one "using cached ..." line in the output, confirming `load_dataframe` found the
untracked-but-still-on-disk parquet file and skipped the network call — proving untracking doesn't
affect local cache behavior for anyone with an existing checkout.

- [ ] **Step 11: Leave everything staged for the user to review and commit**

```bash
git add .gitignore CLAUDE.md
git status
```

Expected: `.gitignore`, `CLAUDE.md`, and the 16 `git rm --cached` deletions all show under "Changes
to be committed"; do **not** run `git commit` — stop here and hand off to the user.
