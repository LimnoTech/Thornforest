# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repo. This file covers **how to work
here**; for *what the project is* — scope, data sources, per-notebook narrative, environment setup,
and API-key setup — see [README.md](README.md) and its sections, referenced inline below. When the
two disagree, this file wins on process, README wins on scope.

> **Using this file as a template.** Within each section, directives that transfer to other repos
> come first; repo-specific ones follow under a **This repo:** marker. To reuse, keep the general
> bullets and swap the repo-specific ones.

## ⚠️ Critical guardrails — read before any work

- **Only the user commits and merges — never the agent.** Do **not** run `git commit`, `git merge`,
  or `git push`. Make and verify changes, leave them **staged / on-disk**, and let the user review
  and commit in GitHub Desktop. Creating a branch (`git checkout -b`) **or a git worktree** is fine —
  for a multi-task-group round of work, that's the round's own **integration branch** (e.g.
  `round4-<topic>`, see [Workflow](#workflow)), never `main` directly. *A git-ignored `.claude/`
  hook also blocks these, but this written rule is the durable, cross-machine contract.*
- **Multi-step work pauses at each task-group gate** — branch off the round's integration branch
  (off `main` only for a single-task-group round), agent does not commit, user reviews the
  working-tree diff and commits before the next group. See [Workflow](#workflow).
- **Edit the notebook `.py`, never the `.ipynb`.** Notebooks are jupytext-paired; the `.py` is the
  source of truth and what you review. After editing: `pixi run jupytext --sync <name>.py`.
- **Tests run via `pixi run test` (pytest).** Verification is the pytest suite **plus** executing
  notebooks headlessly + `pixi run render`. See [Commands](#commands) and [Workflow](#workflow).
- **Storage formats are fixed** — tabular → GeoParquet **+ CSV** (`save_dataframe`); raster/xarray
  datacubes → **zarr v3** (`save_datacube`), never parquet. See [Storage & data](#storage--data).
- **Preserve original source terminology in the data.** Carry each source's own parameter/variable
  names, descriptions, and units **verbatim** in datasets and saved outputs; introduce new names only
  for explicitly derived or blended quantities, and label them as such (so newcomers see the raw
  vocabulary the agencies actually use). In prose (docstrings/markdown) paraphrasing is fine — but
  **link to the primary documentation, liberally.**

**This repo:**

- **USGS data comes from the new WaterData APIs — NOT legacy NWIS / Water Quality Portal.** See
  [README § migration note](README.md#task-2-hydrological-and-water-quality-data-compilation-and-analysis)
  and [USGS WaterData](#usgs-waterdata-apis--discovery) below.
- **Federal hydrography & monitoring data is US-only** — it stops at the Rio Grande border; the
  Mexican side needs other sources and the stream network is deferred. See
  [README § binational caveat](README.md#approach) and [the Mexico gap](#the-mexico-gap).
- **A USGS API key in `.env`** (`API_USGS_PAT`) raises rate limits; without it, repeated calls **hit
  HTTP 429**. Setup in [README § USGS API key](README.md#usgs-api-key-optional).

## Commands

Environment is managed by **pixi** ([pyproject.toml](pyproject.toml)); **never** use bare `pip`/`conda`.
Install and interactive use are in [README § Environment](README.md#environment). Working commands:

```bash
pixi run jupytext --sync notebooks/<name>.py                    # regenerate the paired .ipynb after editing .py
pixi run jupyter nbconvert --to notebook --execute --inplace <nb>.ipynb   # refresh committed .ipynb outputs
pixi run render      # build _site/ (executes notebooks, refreshes _freeze/)
pixi run preview     # live-reload preview server
pixi run test        # run the pytest unit suite (notebooks/tests/)
```

Define any new reusable task under `[tool.pixi.tasks]` in `pyproject.toml` so it's discoverable.

## Workflow

- **Branch per coupled task-group, off the round's integration branch.** For any plan with **more
  than one task-group**, first create one local **integration branch** off `main` (e.g.
  `round4-<topic>`) — every group in that round branches off, and merges back into, *that* branch,
  never `main` directly. Group tightly-coupled tasks onto one branch (not one per micro-step). The
  user reviews, commits, and merges each group into the integration branch before the next branches
  off its updated tip. Task-groups are dependent, so **pause after each group** for that gate. Only
  once the **entire round** is complete does the integration branch itself get merged into `main`
  (and pushed) — a single-plan round should produce exactly **one** merge-to-`main` event, not one
  per task-group. (A single-task-group round can skip the integration branch and branch directly
  off `main`, since there's nothing to isolate it from.)
- **Independent task-groups may run in parallel git worktrees.** Check the plan's own stated
  dependencies first: if two or more groups don't depend on each other's output, implement each in
  its own isolated worktree/branch off the round's integration branch (see above), concurrently,
  instead of serializing them. This does **not** relax the no-agent-commit rule — subagents in a
  worktree still only stage changes. The user reviews and commits **from that worktree's own
  directory** (open it in GitHub Desktop as its own local repo, or `cd` into it) and merges its
  branch into the integration branch from the primary checkout before any *dependent* group's
  worktree branches off the updated tip. Remove a worktree (`git worktree remove`, or
  `ExitWorktree`) once its branch is merged.
  - **`worktree.baseRef` must be `"head"` for this to work**, set in `.claude/settings.json`
    (`{"worktree": {"baseRef": "head"}}`). The default (`"fresh"`) branches every new worktree from
    **`origin/<default-branch>`**, not local `main` — so if the integration branch (or any
    task-group merge into it) hasn't been *pushed*, new worktrees silently branch from a stale ref
    and miss it. `"head"` branches from whatever the primary checkout currently has checked out
    (the integration branch, kept up to date locally as groups merge in), so no push is needed
    until the round's single final merge-to-`main`.
  - Before creating the round's first worktree, **check out the integration branch** in the primary
    checkout (`git checkout -b round4-<topic>`) so it — not `main` — is the local HEAD every
    worktree branches from.
- **Multi-step plans run via subagent-driven development** — a fresh implementer subagent per
  task-group, then a task review (spec + code quality) before handing to the user. Since the agent
  doesn't commit, per-group review runs on the **working-tree diff** (`git add -N` untracked, then
  `git diff`) within that group's branch or worktree, not commit ranges.
- **Typical cadence — pause at each task-group gate.** The agent implements a task-group, reviews it
  (and applies fixes), then **stops and leaves the work staged** — in the primary checkout for a
  plain branch, or in that group's own worktree directory when run in parallel — **for the user to
  commit** before the next (or next batch of parallel) group(s) start; the user's commit(s) become
  the clean baseline. The agent runs *within* a group autonomously (no check-ins between steps) — the
  gates are only *between* groups. To maximize autonomy, **group more tasks per gate** (fewer, larger
  task-groups → fewer pauses); to keep tighter checkpoints, split them. When handing off a
  worktree-based group, the agent states the **worktree path, branch name, and a short guidance list
  of what to check** in that diff.
- **Verification:** run `pixi run test` (pytest, `notebooks/tests/`) for the `_helpers` package,
  **plus** the deliverable is executed notebooks + the rendered site — execute notebooks headlessly
  and `pixi run render` + grep.
  - **A dispatched subagent told to run `nbconvert --execute` in the foreground reliably backgrounds
    it anyway** (or otherwise ends its turn before the process finishes) once a run takes more than
    a few minutes — seen repeatedly across rounds. Don't re-dispatch hoping it waits this time:
    check the orphaned process directly (`ps aux | grep nbconvert`), and poll completion via the
    notebook's own `execution_count`/cell outputs (nbconvert's stdout isn't streamed live — it only
    lands in the `.ipynb` at the end). **Never pipe the command through `tail`** when checking
    success — `cmd | tail -N`'s exit code reflects `tail`, not `nbconvert`, so a real crash can look
    clean; redirect to a file and `echo "EXIT=$?"` on the next line into that same file instead.
- **Explore new data sources in a `sandbox/` notebook first**, then port the proven approach into the
  numbered notebooks. (`sandbox/` is excluded from the site render.)
- **Writing PR/issue descriptions:** GitHub renders a single newline inside a PR/issue-body
  paragraph as a literal line break (unlike CommonMark, which is what this repo's own `README.md`
  follows when rendered by GitHub's file browser). Write each paragraph and bullet as one
  continuous line in the source, however long — don't manually soft-wrap prose for local
  readability, or it will render broken mid-sentence once posted.

## Notebooks & helpers

- **`.py` is the source of truth** (jupytext-paired) — edit it, then `--sync`. Notebooks are written
  for readers **new to Python/Jupyter**: explain each step in markdown, keep code cells small.
- **Reusable helpers live in the [`notebooks/_helpers/`](notebooks/_helpers/) package** — `import`
  them, don't redefine. The leading underscore makes Quarto ignore the package when rendering. Keep
  heavy imports **lazy** (inside the functions that need them) so light notebooks don't pay the cost.
  Modules are split by concern and kept **generic** (`session`, `io`, `viz`, `analysis`, `usgs`,
  `climate`), with project-specific constants isolated in `config.py` and **injected as arguments**
  (e.g. `groups`) rather than hardcoded — that seam is what would let the package be lifted into
  another project. `usgs` splits fetching into `fetch_*` (network calls) vs. `tidy_*` (pure
  transforms), so the pure half is unit-testable without a live API. `__init__.py` re-exports the
  public API, so `from _helpers import save_dataframe, show, ...` is unchanged regardless of which
  module a helper actually lives in.
- **Type-hint functions in the `_helpers` package**; keep notebook cells hint-free — the audience is
  new to Python/Jupyter, and inline type syntax adds noise without teaching value there.
- **Set up each notebook with `S = init_session()`** once near the top — it loads `.env`, configures
  the HTTP cache, and returns paths/headers (`S.data_dir`, `S.cache_file`, `S.api_headers`, …). Don't
  scatter that config across cells.
- **`save_dataframe` returns nothing on purpose** (a save is often a cell's last line; a returned frame
  would auto-render as a stray, non-scrollable table). Display tables with **`show(df)`** — a
  fixed-height, sticky-header scrollable box that emits every row.
- **`load_dataframe` is the read-side companion — use it as a "backup cache" for fetch calls that
  bypass `cache/`.** Libraries like `dataretrieval` (USGS/WQP) and plain `requests`-based ArcGIS
  queries make their own HTTP requests outside HyRiver's `async_retriever`, so they never hit the
  on-disk request cache. Instead, treat the already-saved product **parquet file itself** as the
  cache: `load_dataframe(path, max_age_days=7)` returns the saved (Geo)DataFrame if it's still
  fresh, or `None` if missing/stale — guard the fetch with `if load_dataframe(...) is None:` and
  only `save_dataframe` inside that branch, so a fresh run within the window skips the network call
  entirely. When a stage's cache-hit means a downstream diagnostic can't run (e.g. an audit that
  needs the *raw*, untidied response), gate that diagnostic on the same fetch-vs-cache flag rather
  than making it error or silently produce nothing — see `3_usgs_waterdata`/`4_tceq_waterquality`/
  `5_twdb_groundwater` for the pattern with multiple interdependent cached stages.
- **Prefer pyarrow explicitly for tabular I/O** — both for performance and because it infers dtypes
  better than pandas' legacy NumPy-based engine. `save_dataframe`/`load_dataframe` pass
  `engine="pyarrow"` (write) and `engine="pyarrow", dtype_backend="pyarrow"` (read, plain
  DataFrames) explicitly rather than relying on pandas' `engine="auto"` default. GeoDataFrames read
  via `geopandas.read_parquet` are already pyarrow-based internally, so no extra option is needed
  there. Code that consumes a `load_dataframe`-returned frame should expect pyarrow-backed dtypes
  (e.g. `string[pyarrow]`, `double[pyarrow]`), not classic NumPy `object`/`float64`.
- **Color data with colorcet, never the brand palette** — `categorical_colors(keys)` (colorcet
  `b_glasbey_category10`) for figure data; the brand palette + Roboto (`_brand.yml`) are site chrome.
- **Show intermediate results, don't just chain silently** — e.g. `show(raw.head())` right after an
  API call, before tidying it — and **link to primary documentation** liberally, so a newcomer can
  see the raw response shape and trace it back to the source API's own docs.

**This repo:**

- Helper inventory (`notebooks/_helpers/`, re-exported from the package root):
  - `session` — `find_repo_root`, `init_session`/`Session`.
  - `io` — `save_dataframe`, `load_dataframe` (parquet-as-backup-cache read side — parquet itself is
    git-ignored, only its CSV sibling is committed), `save_datacube`.
  - `viz` — `show`, `categorical_colors`/`CATEGORICAL`, `make_legend_clickable`.
  - `analysis` — `water_year`, `mk_sen_trend`, `coverage`, `trend_by_group`.
  - `usgs` — `classify_parameter`, `build_parameter_name_lookup`, `station_parameters`,
    `fetch_daily`/`fetch_samples`/`fetch_field`, `tidy_daily`/`tidy_samples`/`tidy_field`.
  - `tceq` — `fetch_wqp_results`/`tidy_wqp_results` (EPA Water Quality Portal, organization
    `TCEQMAIN` — TCEQ has no API of its own).
  - `twdb` — `fetch_gwdb_wells` (ArcGIS FeatureServer inventory), `fetch_gwdb_zip`/
    `fetch_gwdb_members` (nightly bulk file — the FeatureServer has no time-series endpoint),
    `tidy_gwdb_water_levels`/`tidy_gwdb_water_quality`.
  - `climate` — `conus404_monthly_grid`, `zonal_by_huc8`, `pixel_trend`, plus the `CONUS404_VARIABLES`
    constant from `config`.
  - `excel` — `save_workbook` (compiles a notebook's saved tables into one downloadable .xlsx,
    one sheet each, frozen panes + autofilter).
  - Candidate to grow into a shareable cross-project package (`config.py` is the only
    Thornforest-specific module).
- Per-notebook responsibilities and methods are described in [README § Approach](README.md#approach).

## Storage & data

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
- **`data_temp/gwdb_download.zip`** (git-ignored scratch) caches TWDB's nightly full-state bulk
  file for a week — much larger than the HTTP request cache, so it's kept separate rather than
  routed through `cache/`.

**This repo:**

- `data/hydrography/` — HyRiver/`pygeohydro` geometries (e.g. `huc8_watersheds`).
- `data/usgs_waterdata/` — `dataretrieval.waterdata` products (station inventory + time-series).
- `data/tceq_waterquality/` — TCEQ Surface Water Quality Monitoring results via the EPA Water
  Quality Portal (`dataretrieval.wqp`, organization `TCEQMAIN`).
- `data/twdb_groundwater/` — TWDB GWDB well inventory (ArcGIS FeatureServer) + water levels/quality
  (TWDB's nightly bulk file, filtered to the study wells).
- `data/climate/` — CONUS404: the raw `conus404_monthly_grid.zarr` cube is **git-ignored** (~57 MB,
  regenerated from the cloud); the derived climatology/trend grids and water-year/trend tables are committed.
- `data/<source>/` — one folder per new source (TCEQ, NCEI, …).
- Plain `dataretrieval.waterdata` discovery calls use their own client and are **not** in `cache/`.

## Website (Quarto → GitHub Pages)

- **Config:** [`_quarto.yml`](_quarto.yml) (`cosmo` theme, `code-fold`, `execute-dir: file`,
  `freeze: auto`) + [`index.qmd`](index.qmd) landing page.
- **Freeze:** `pixi run render` **executes** the notebooks — that bakes the interactive
  HoloViews/GeoViews Bokeh embeds (`holoviews_exec`) into the static HTML — then freezes to
  **`_freeze/` (committed)**. **Re-render and leave `_freeze/` staged after editing a notebook.**
- **Render resolves paired notebooks via their `.py`** (the `render:` list targets `.py`;
  underscore-prefixed files **and directories**, like `_helpers/`, are ignored); **navbar `href`s
  point at the output `.html`**. `sandbox/` is excluded.
- **Refreshing committed `.ipynb` outputs:** neither `jupytext --sync` nor `pixi run render` updates
  the `.ipynb`'s stored outputs (what you see in the IDE / on GitHub). After changing code that
  affects displayed output, run the `nbconvert` command in [Commands](#commands), then render.

**This repo:** [`.github/workflows/publish.yml`](.github/workflows/publish.yml) renders and deploys on
every push to `main`; the render step gets the **`API_USGS_PAT`** repo secret so a freeze-miss CI
re-execution stays authenticated. Live at <https://limnotech.github.io/Thornforest/>. **This is why
multi-task-group rounds use a local integration branch** (see [Workflow](#workflow)) rather than
merging each group straight into `main` — pushing `main` mid-round would deploy an incomplete round
to the live site once per group instead of once per round.

## USGS WaterData APIs & discovery

Background and the migration rationale are in
[README § migration note](README.md#task-2-hydrological-and-water-quality-data-compilation-and-analysis).
Working notes for this repo:

- **Use `dataretrieval.waterdata`**, not `dataretrieval.nwis` (legacy) or WQP endpoints.
  Reference: [WaterData demo](https://doi-usgs.github.io/dataretrieval-python/examples/WaterData_demo.html).
- **Discovery:** `get_monitoring_locations()`, `get_time_series_metadata()`,
  `get_field_measurements_metadata()`, lookups `get_reference_table()`/`get_codes()`.
  **Fetch:** `get_daily()`, `get_continuous()`, `get_samples()`, `get_field_measurements()`.
- Each returns a `(dataframe, metadata)` tuple — a GeoDataFrame when geopandas is installed
  (`skip_geometry=True` drops coordinates). Query by `monitoring_location_id`, geography, USGS
  `parameter_code` (e.g. discharge `00060`), and date range. Specify **just enough** inputs —
  redundant geographic/parameter filters slow queries and can error.
- **The availability pattern (NB3):**
  - **Stations:** `get_monitoring_locations(bbox=[minlon,minlat,maxlon,maxlat])`, then `.set_crs(4326)`
    (it returns without one) and `geopandas.sjoin(predicate="within")` to the polygons. Use bbox +
    spatial filter, **not** `hydrologic_unit_code` (matches only the exact HUC, missing HUC12-tagged sites).
  - **daily / continuous** — both from `get_time_series_metadata(bbox=…)`, split on
    `computation_period_identifier` (`"Daily"` vs `"Points"`). **field** — `get_field_measurements_metadata(bbox=…)`.
  - **samples** — ⚠️ the area-wide samples *results* service **504-times-out** in dense regions and
    `get_samples(service="locations")` just mirrors the registry. The reliable signal is per-station
    `get_samples_summary(monitoringLocationIdentifier=<id>)` (non-empty = has samples) — one request per
    site, so it's the slow step (cache it).
  - Join availability back to stations on `monitoring_location_id`.

### The Mexico gap

The watersheds straddle the Rio Grande, but **every NHD product is US-only** and stops at the border
(~25.84°N at the river mouth) — verified for the HyRiver `nhdflowline_network` service, `pynhd.NHDPlusHR`,
and the EPA NHDPlus V2.1 VPU 13 download (`sandbox/explore_nhdplus_vpu13`). A **binational** stream
network needs a Mexico-capable source — **HydroRIVERS**, Mexico's **INEGI** Red Hidrográfica, or **OSM**
waterways. Until decided, the stream network is omitted. (CONUS404 climate in NB2 *does* cover the whole
area, since it's gridded model output rather than US-only gauges.)

## Gotchas (learned)

- **Tile maps:** set `frame_width` + `data_aspect=1` (don't also fix height) so basemap tiles aren't
  stretched — let height follow the data's true aspect.
- **Don't force a tile `min_zoom`** above the initial view to shrink labels — it breaks pan/zoom (tiles
  don't exist below the forced level). Choose the basemap/extent instead.
- **Toggle layers:** overlay one labeled layer per category, then a Bokeh hook
  `plot.state.legend.click_policy = "hide"` — static-HTML-safe, no Panel `embed` needed.

**This repo:**

- Basemap is `geoviews.tile_sources.EsriWorldTopo`.
- **EPA NHDPlus file-geodatabases** (sandbox): read via `s3fs(anon=True)` from
  `dmap-data-commons-ow/NHDPlusV21/…` → extract `.7z` with **`libarchive`** → `pyogrio.read_arrow`.
  `FType` is a numeric code (460 = StreamRiver); `StreamOrde` lives in `PlusFlowlineVAA` joined by
  **COMID**; geometries are 3D → `.geometry.force_2d()` before GeoViews can draw them.
