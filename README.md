# Thornforest project for American Forests

## Task 2: Hydrological and Water Quality Data Compilation and Analysis

Gather, compile, organize, and analyze 25 years (2000–2025) of publicly and
digitally available precipitation, streamflow, and water quality data for the
three HUC-8 watersheds of interest:
- South Laguna Madre (12110208)
- Los Olmos (13090001)
- Lower Rio Grande (13090002)

Water quality data will include conductivity, temperature, dissolved oxygen,
dissolved solids, total algae/chlorophyll, pH, nutrient concentrations (nitrogen and
phosphorus species), and turbidity measurements, where available.

Retrieve data from multiple federal and state sources, including USGS streamflow gauge records and water
quality sampling data; EPA water quality monitoring; Texas Commission on Environmental Quality (TCEQ)
Surface Water Quality Monitoring program; Texas Water Development Board groundwater and surface water
databases; the International Boundary and Water Commission for Rio Grande flow and allocation data; NOAA
National Centers for Environmental Information (NCEI) for precipitation records; and local irrigation
district records where accessible.

> **USGS / EPA data-system migration.** USGS and EPA are retiring the legacy data systems — the National
> Water Information System (**NWIS**) and the EPA STORET / **Water Quality Portal** — and consolidating
> federal water data behind the new **USGS Water Data APIs** at <https://api.waterdata.usgs.gov>. This
> project targets the new APIs via the **`waterdata` module of the [`dataretrieval`](https://doi-usgs.github.io/dataretrieval-python/)**
> Python package (which supersedes that package's legacy `nwis` module), rather than the deprecated
> NWIS/WQP endpoints. See the [WaterData demo](https://doi-usgs.github.io/dataretrieval-python/examples/WaterData_demo.html).
> Data is also fetched from the USGS Water Services host <https://api.water.usgs.gov>, used alongside
> the WaterData APIs at <https://api.waterdata.usgs.gov>.

Compile all retrieved into a structured database format (such as Excel or other format preferred by
American Forests) that American Forests can use for ongoing analysis. We will document each data source with
complete source information (including hyperlinks) and any relevant metadata. We will map monitoring station
locations relative to existing thornscrub area and American Forests restoration sites to assess spatial relevance. We
will use the collected and organized data to assess whether measurable changes in water quantity or quality
correlate with the timing and location of 25 years of restoration activity in the region.

Apply scientific statistical methods to identify correlations, which may include trend analyses of the raw data
(how does the water quantity or quality data change over time), trend analysis of normalized data (e.g.: adjust flow
and/or water quality data based on observed rainfall or temperature to minimize external factors that may skew the
trend analysis), box and whisker plots of data collected pre- and post-restoration efforts, and similar.

## Approach

The work is organized as a series of Jupyter notebooks following a **hybrid** structure:

- **Fetch notebooks (one per source)** — discover what data exists within the three HUC-8 watersheds,
  fetch the 2000–2025 record, and save it to `data/`. The first notebook, `1_usgs_hydrography_waterdata`,
  also establishes the spatial foundation: HUC-8 watershed boundaries and the stream network (via HyRiver
  `pynhd`), then begins data discovery with the new USGS `dataretrieval.waterdata` module.
- **Display / analyze notebooks (shared)** — read the saved data and work across sources by data type or
  watershed (maps, trend analyses, pre/post-restoration comparisons). A structured deliverable (Excel or
  the format American Forests prefers) is exported from the harmonized data at the end.

The notebooks will be published as a static, **fully interactive** website (HoloViews/GeoViews visuals)
on **GitHub Pages**, built with **[Quarto](https://quarto.org)**.

Saved data lives in `data/`: tabular timeseries as **Parquet** under a per-source subdirectory
(`data/<source>/`), and station locations / watershed & stream geometries as **GeoParquet** under
`data/spatial/`.

## Environment

We recommend using [pixi](https://pixi.prefix.dev/latest/), the next-generation reproducible package management tool built on [conda](https://docs.conda.io/projects/conda/en/stable/) tooling.

If you are new to pixi but familiar with conda, this [Switching from Conda](https://pixi.prefix.dev/latest/switching_from/conda/) documentation succinctly compares similarities and differences.

For required dependencies see [pixi.toml](pixi.toml).

### 1. Install Pixi

Follow [Pixi Installation](https://pixi.prefix.dev/latest/installation/) instructions for your platform.

### 2. Clone or Download this Repository

From these Github sites, click on the green "Code" dropdown button near the upper right. Select to either "Open in GitHub Desktop" (i.e. git clone) or "Download ZIP". 

We recommend using GitHub Desktop, to most easily manage git workflows by providing excellent visuals for stagging commits, exploring commit histories, comparing branches, and resolving merge conflicts in tight integration with Visual Studio Code.

Place your copy of these repos in any convenient location on your computer.

### 3. Create a Workspace and Python Environment

Create a project-specific Pixi workspace and Python enviornment(s) from the `pixi.toml` manifest file.

```bash
pixi install              # create/refresh the env from pixi.lock
pixi run jupyter lab      # work on notebooks interactively
```

## USGS API key (optional)

Accessing the USGS Water Data APIs works **without credentials**; a free
[API key](https://api.waterdata.usgs.gov/signup/) only raises rate limits. To add one safely:

```bash
cp .env.example .env          # then paste your key into .env (API_USGS_PAT=...)
```

`.env` is git-ignored — your key never gets committed. Notebooks load it with
[`python-dotenv`](https://pypi.org/project/python-dotenv/):

```python
from dotenv import load_dotenv
load_dotenv()                 # reads API_USGS_PAT from .env into the environment, if present
```

The `dataretrieval.waterdata` calls then pick up the key automatically. With no `.env`, everything
still runs (at lower rate limits).
