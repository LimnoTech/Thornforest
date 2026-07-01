# `_helpers` refactor — package split, notebook promotion, pytest, pyproject — Design

**Date:** 2026-07-01
**Status:** Design (awaiting user review before planning)

## Goal

Refactor the single 312-line `notebooks/_helpers.py` into a focused, teaching-oriented package;
promote reusable logic out of the notebooks; adopt pytest as the real test framework; and
consolidate the environment manifest into `pyproject.toml`. Structure everything so the generic
pieces can later be lifted into the sibling **`watershed-analysis-planning`** (WAP) package with
near-zero edits.

## Context

- `notebooks/_helpers.py` today mixes ~7 concerns (path utils, I/O, display, session/config, data
  colors, a GeoViews hook, and a large CONUS404 climate block). It is imported as `from _helpers
  import …`; the leading underscore is deliberate — **Quarto ignores `_`-prefixed files/dirs**, so the
  module never renders as a site page.
- WAP is already a proper installable library (`src/watershed_analysis_planning/`, `pyproject.toml`
  with hatchling + editable self-install + `pytest`/`pytest-cov`/`ruff`), and its CLAUDE.md states
  `src/…` is "for all shared functions, organized into logical modules." Its dependency stack is
  nearly identical to Thornforest's. It is the eventual destination for the generic helpers.
- The notebooks target readers **new to reproducible geospatial Python workflows**. Teaching is a
  first-class objective of this refactor: readable code, and notebooks that show intermediate results.

## Non-goals (this round)

- **No cross-repo dependency yet.** Thornforest does not import WAP; the seam is *prepared*, not crossed.
- **No `[project]`/`[build-system]` in `pyproject.toml`.** Thornforest is an analysis workspace, not a
  distributable package; helpers are notebook-local and underscore-named. (Decided with user.)
- **No new data sources / analyses.** Continuous data, TCEQ/NCEI, trend/pre-post analysis remain out.

---

## Design

### 1. Package structure

Convert `notebooks/_helpers.py` → a `notebooks/_helpers/` **package**. The underscore keeps Quarto
ignoring it; `__init__.py` re-exports the full public API so **every existing `from _helpers import …`
keeps working unchanged** (no import churn in the notebooks).

```
notebooks/_helpers/
  __init__.py    # re-exports the public API (back-compat shim)
  config.py      # Thornforest-only constants (see §2)
  session.py     # find_repo_root, Session, init_session
  io.py          # save_outputs, save_datacube
  viz.py         # show, set_plot_defaults, CATEGORICAL, categorical_colors, make_legend_clickable
  analysis.py    # water_year, mk_sen_trend, coverage
  usgs.py        # classify_parameter, parameter-name lookup, station_parameters, fetch_*/tidy_*
  climate.py     # CONUS404 constants + conus404_monthly_grid, zonal_by_huc8, pixel_trend
```

Each module is small enough to hold in context and has one clear purpose. `__init__.py` is the only
public surface notebooks depend on.

### 2. Generic / project seam

Project-specific constants move to `config.py`; functions accept them as **arguments defaulting to the
config value**. This is what makes later extraction to WAP mechanical (`git mv` the generic module,
swap the default import).

- `config.py` holds: `PRIORITY_GROUPS` (the 11 priority parameters), `PLOT_WIDTH` (600, tuned to the
  Quarto cosmo column), `WATERSHEDS` (the three HUC-8 codes/names), and `CONUS404_VARIABLES` (the
  source-term mapping, see §4).
- Example: `classify_parameter(parameter_code=None, characteristic=None, groups=PRIORITY_GROUPS)`.
  With `groups` injected, `usgs.py` is fully generic.
- All of `session.py`, `io.py`, `viz.py` (except the `PLOT_WIDTH` value), `analysis.py`, `usgs.py`,
  `climate.py` are generic and WAP-bound. `config.py` stays behind in Thornforest.

### 3. Teaching-first principles

- **Readable code as reference material:** small functions, plain-language docstrings that explain
  *why*, public APIs over private attributes.
- **Fetch stays visible; only mechanical transforms are factored out.** `usgs.py` splits each USGS
  data type into two layers:
  - `fetch_daily` / `fetch_samples` / `fetch_field` — thin wrappers over `waterdata.get_*` that guard
    empty ID lists and silence the known upstream warning, **returning the raw response**.
  - `tidy_daily` / `tidy_samples` / `tidy_field` — **pure** transforms (rename → tag
    `priority_group`/`huc8`/`parameter_name` → select/sort). No network → unit-testable.
- **Notebooks teach by showing intermediate results:** call `fetch_*`, `show(raw.head())` to reveal the
  real API response shape, explain the columns in markdown (with links to the API docs), call `tidy_*`,
  `show()` the tidy result, then `show(coverage(...))`. Nothing is hidden — the reader sees the raw
  dataframe *and* a documented transform they can open in `usgs.py`.
- **Link liberally to primary sources** in docstrings and markdown (USGS parameter-code tables,
  dataretrieval WaterData docs, CONUS404 documentation, HyRiver docs).

### 4. Source-term fidelity (data), paraphrase-with-links (prose)

Principle: **carry source terminology — parameter/variable names, descriptions, units — verbatim in
the data (datasets and saved outputs); introduce new names only for explicitly derived or blended
quantities, and label them as such. In prose (docstrings/markdown), paraphrasing is fine as long as it
links to the primary documentation.**

- **USGS — already compliant, preserve it:** `parameter_code` + `parameter_name` come verbatim from
  `get_reference_table("parameter-codes")`; `characteristic` verbatim from the samples service. These
  stay unedited in every output, **alongside** (never replacing) our explicitly-new `priority_group`.
- **CONUS404 — currently paraphrased; fix:** we rename `PREC_ACC_NC → precip_mm`, `ACETLSM → et_mm`,
  etc., which erases the source term. Instead:
  - Keep the **original variable names + their `long_name`/description/units attributes** in the
    datacube. Verify `save_datacube` preserves variable `attrs` (it clears `encoding`, which is
    correct, but must not drop `attrs`); add a regression test.
  - Treat friendly labels (`precip_mm`, `et_mm`, …) as **derived presentation names**, documented in
    `config.CONUS404_VARIABLES`: `original_name → {source_description, source_units, derived_label,
    derivation}`. `balance_mm` (P − ET − Q) and `water_year` are genuinely new — labeled as derived.
  - Where the notebook presents friendly names, a markdown cell shows the mapping so newcomers see the
    agency's actual vocabulary, with a link to the CONUS404 documentation.

### 5. pytest adoption

`pytest` is already a dependency. This round makes it real:

- Add a `test` pixi task (`pytest`) and `[tool.pytest.ini_options]` with `testpaths = ["notebooks/tests"]`.
- **TDD the pure functions** (no network):
  - `analysis.py`: `water_year` (Oct-1 boundary → WY label), `mk_sen_trend` (`<4 → "insufficient"`; a
    known monotonic series → expected slope sign/value), `coverage` (counts + first/last per group).
  - `usgs.py`: `classify_parameter` (code match, characteristic match, the pH exact-match guard,
    unknown → `None`); `tidy_daily`/`tidy_samples`/`tidy_field` on tiny in-memory fixtures — asserting
    `huc8`/`priority_group`/`parameter_name` tagging, the fragmentation-safe assignment, column
    selection/order, and the empty-input guard.
  - `io.py`: improve `test_save_outputs` per the PR review — geometry-**first** fixture so the reorder
    assertion actually exercises the move; read the CSV back and assert geometry serializes as WKT.
  - `climate.py`: `save_datacube` preserves variable `attrs` (source-term fidelity regression).
- Network-dependent functions (`fetch_*`, `conus404_monthly_grid`, `zonal_by_huc8`) are verified by
  notebook execution + render, per the existing philosophy — not mocked in unit tests.

### 6. `pixi.toml` → `pyproject.toml`

Consolidate into a single `pyproject.toml` mirroring WAP's `[tool.pixi.*]` layout, **without**
`[project]`/`[build-system]`:

- `[tool.pixi.workspace]` — channels, platforms, name, version.
- `[tool.pixi.dependencies]` — the current conda deps (python under it), plus `ruff` (for uniformity
  with WAP).
- `[tool.pixi.tasks]` — `render`, `preview`, and new `test`.
- `[tool.pixi.pypi-dependencies]` — empty placeholder (as today).
- `[tool.pytest.ini_options]` — `testpaths`.
- `[tool.ruff]` — baseline lint config matching WAP.
- Delete `pixi.toml`. Confirm `pixi install` / `pixi run render` / `pixi run test` work from the new
  manifest and that `pixi.lock` regenerates cleanly.

### 7. Folded-in PR-review fixes

Code fixes (into the new modules as they are written):

- `save_outputs`: use public `isinstance(df, gpd.GeoDataFrame)` instead of the private
  `_geometry_column_name` attribute.
- `find_repo_root`: print a warning when the marker is not found (currently silently returns CWD).
- `tidy_*`: assert-or-warn when the `huc8` join produces NaN (id mismatch → silent data loss);
  guard empty station-id lists in `fetch_*`; report how many samples-summary requests returned empty
  (throttled/504 vs genuinely no-samples); audit parameter codes that fell through to the raw-code
  fallback; report rows dropped by the `priority_group` NaN filter on the code-keyed services.

Doc/cosmetic fixes:

- Notebook H1 titles: `1_usgs_hydrography` "USGS Hydrofabric" → "USGS Hydrography"; `2_usgs_climate`
  `3 ·` → `2 ·`; `3_usgs_waterdata` `2 ·` → `3 ·`.
- `.gitignore` comment "regenerated from OSN by NB3" → "by NB2".
- NB3 markdown step numbers → sequential (currently 1, 5, 6, 7, 8, 10).
- Reconcile the raw CONUS404 cube size (`~80 MB` in NB2/README vs `~57 MB` in CLAUDE.md) against the
  actual on-disk size; make all references agree.
- Drop the "see Task 3 verification" clause from the `PLOT_WIDTH` comment.

### 8. NB3 runtime warnings

- **`DtypeWarning` (mixed types in the samples CSV):** raised inside `dataretrieval`'s own
  `pd.read_csv`, so we cannot pass `dtype`. `fetch_samples` wraps the call in
  `warnings.catch_warnings()` and suppresses that specific warning, with a comment noting it is a known
  upstream quirk and that the columns we consume are not the mixed ones.
- **`PerformanceWarning` (highly fragmented frame):** caused by our one-column-at-a-time assignment on
  the wide samples frame. `tidy_samples` computes the derived columns and assigns them in a single
  `.assign(...)` on a narrowed copy, eliminating the repeated `frame.insert`.

### 9. CLAUDE.md changes

CLAUDE.md is the durable home for the standing directives this refactor introduces. Each edit is
applied **at the point its underlying change lands**, so CLAUDE.md never describes a state that does
not yet exist (e.g. the `pyproject.toml` reference is switched in the same task-group that deletes
`pixi.toml`).

- **Source-term fidelity — added now** (standing data-handling rule, true independent of this refactor)
  as a **general critical guardrail**: carry each source's parameter/variable names, descriptions, and
  units verbatim in datasets and saved outputs; introduce new names only for explicitly derived/blended
  quantities and label them as such; in prose, paraphrasing is fine but link to primary docs liberally.
- **Testing** — flip the **"No formal test suite"** guardrail → tests run via `pixi run test` (pytest);
  verification is pytest **plus** executing notebooks + render. Update the Workflow verification bullet.
- **Environment** — switch the manifest references from `pixi.toml` to `pyproject.toml` (Commands +
  environment note), and add `pixi run test` to the Commands block.
- **Helpers** — update the reference from `_helpers.py` to the `_helpers/` package + module map; note
  the generic/project seam (project constants in `config.py`, functions take them as arguments) and the
  fetch/tidy split as the teaching-vs-reuse pattern.
- **Teaching** — add a short directive (Notebooks & helpers) that notebooks show intermediate results
  (raw API responses via `show(...)`) and link to primary sources, for the new-contributor audience.

### 10. Notebook changes

- **NB3 (`3_usgs_waterdata`):** move `PRIORITY_GROUPS`→`config`, `classify_parameter`/param-name
  lookup/`station_parameters`→`usgs`, `coverage`→`analysis`; replace the three inline fetch+tag cells
  with `fetch_*`/`tidy_*` calls that display raw + tidy intermediate results; renumber steps; fix the
  H1 title; add primary-source links.
- **NB2 (`2_usgs_climate`):** adopt the `CONUS404_VARIABLES` source-term mapping; keep original
  variable names in the cube and present the derived-label mapping in markdown; fix the H1 title.
- **NB1 (`1_usgs_hydrography`):** fix the H1 title. Imports unchanged (re-export shim).

---

## Testing strategy

- **Unit (pytest):** the pure functions listed in §5, run with `pixi run test`.
- **Integration:** execute each notebook headlessly (`nbconvert --execute --inplace`) and `pixi run
  render`; confirm no tracebacks, embeds present, and the two NB3 warnings are gone.
- **Regression:** `save_datacube` attribute-preservation test guards the source-term-fidelity fix.

## Rollout / dependencies

This refactor builds on the round-3 branch's fetch code, so it should branch off
`round3-usgs-timeseries` (or off `main` after round-3 merges). Per repo convention, the agent creates
the branch and does not commit; the user reviews the working-tree diff and commits at each task-group
gate.

## Open items

None outstanding — the two prior open decisions (lean `pyproject`; paraphrase-with-links) are settled.
