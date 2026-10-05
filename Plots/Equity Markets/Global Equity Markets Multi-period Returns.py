from __future__ import annotations

import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from matplotlib import font_manager

# =====================================================================
# IMPORT MSCI-DATA
# =====================================================================

try:
    from mscidata import msci
except ImportError as error:
    raise ImportError(
        "\nCould not import 'msci' from the 'mscidata' package.\n\n"
        "Install or upgrade the required packages using:\n\n"
        "    pip install --upgrade msci-data pandas\n\n"
        f"Original import error: {error}"
    ) from error

# =====================================================================
# USER SETTINGS
# =====================================================================

# Manual chart positioning controls
TITLE_Y = 0.955
SUBTITLE_Y = 0.915
SUBTITLE_LINE_SPACING = 0.020
HEAT_MAP_Y = 0.12
SOURCE_Y = 0.082
NOTE_Y = 0.060
NOTE_LINE_SPACING = 0.016

# Horizons shown in the heatmap (label -> look-back offset).
# 1D is handled separately: last observation vs the one before it.
HORIZONS = {
    "1D": None,
    "1W": pd.DateOffset(weeks=1),
    "1M": pd.DateOffset(months=1),
    "3M": pd.DateOffset(months=3),
    "6M": pd.DateOffset(months=6),
    "1Y": pd.DateOffset(years=1),
    "3Y": pd.DateOffset(years=3),
    "5Y": pd.DateOffset(years=5),
    "10Y": pd.DateOffset(years=10),
}

# Number of years behind each multi-year horizon (used to annualise)
HORIZON_YEARS = {
    "3Y": 3,
    "5Y": 5,
    "10Y": 10,
}

# Horizons of this many years or more are shown annualised (p.a.).
# Set to None to show cumulative returns for every horizon.
ANNUALISE_FROM_YEARS = 3

# Column used to sort the rows
SORT_BY = "1Y"

# Volatility column: annualised SD of daily returns over this look-back
SD_LOOKBACK = pd.DateOffset(years=1)
SD_LABEL = "1Y SD"
MIN_SD_OBSERVATIONS = 20

FONT_FAMILY = "Helvetica"

MSCI_RETURN_VARIANT = "NETR"

# Extra calendar days requested before the longest look-back, so the
# observation on or before the 10Y target date is always captured.
DOWNLOAD_LOOKBACK_DAYS = 15

# =====================================================================
# OUTPUT LOCATION
# =====================================================================

OUTPUT_DIR = Path(__file__).resolve().parent

PNG_FILE = (
    OUTPUT_DIR
    / "Global_Market_Returns_Heatmap.png"
)

# =====================================================================
# GLOBAL STYLE
# =====================================================================

plt.rcParams["font.family"] = "sans-serif"

plt.rcParams["font.sans-serif"] = [
    FONT_FAMILY,
    "Arial",
    "Helvetica",
    "DejaVu Sans",
]

# =====================================================================
# MAJOR GLOBAL EQUITY MARKETS
# MSCI NET TOTAL RETURN INDICES IN USD
# =====================================================================

SECTORS = {
    "United States": "984000",
    "Canada": "912400",
    "United Kingdom": "982600",
    "Eurozone": "106400",
    "Germany": "928000",
    "France": "925000",
    "Italy": "938000",
    "Spain": "972400",
    "Switzerland": "975600",
    "Japan": "939200",
    "China": "302400",
    "India": "935600",
    "South Korea": "941000",
    "Taiwan": "915800",
    "Hong Kong": "934400",
    "Australia": "903600",
    "Brazil": "907600",
    "Mexico": "848400",
    "South Africa": "971000",
    "UAE": "133717",
    "Singapore": "998100",
}

# =====================================================================
# GLOBAL EQUITY BENCHMARKS
# =====================================================================

BENCHMARKS = {
    "MSCI World": "990100",
    "MSCI Emerging Markets": "891800",
    "MSCI All Country": "892400",
    "MSCI Ex-AMER": "991000",
    "MSCI World Momentum": "703755",
}

ALL_INDICES = {
    **SECTORS,
    **BENCHMARKS,
}

BENCHMARK_NAMES = list(
    BENCHMARKS
)

# =====================================================================
# MSCI INDEX-CODE VALIDATION
# =====================================================================


def clean_index_code(
    index_code: object,
) -> str:
    """Convert an MSCI index code to a clean string."""

    if index_code is None:
        return ""

    return str(index_code).strip()


def is_placeholder_code(
    index_code: object,
) -> bool:
    """Return True when an MSCI index code is a placeholder."""

    cleaned_code = clean_index_code(
        index_code
    )

    if not cleaned_code:
        return True

    upper_code = cleaned_code.upper()

    exact_placeholders = {
        "NONE",
        "N/A",
        "NA",
        "TBC",
        "TBD",
        "PLACEHOLDER",
    }

    placeholder_prefixes = (
        "REPLACE",
        "REPLACE WITH",
        "REPLACE-WITH",
        "ADD",
        "INSERT",
        "ENTER",
        "PUT",
    )

    if upper_code in exact_placeholders:
        return True

    return upper_code.startswith(
        placeholder_prefixes
    )


def validate_numeric_index_code(
    index_name: str,
    index_code: object,
) -> str:
    """Validate and return an MSCI numeric index code."""

    cleaned_code = clean_index_code(
        index_code
    )

    if not cleaned_code.isdecimal():
        raise ValueError(
            f"MSCI index code for '{index_name}' must contain "
            f"digits only. Received: {cleaned_code!r}"
        )

    return cleaned_code


# =====================================================================
# DATE RANGE
# =====================================================================

today = pd.Timestamp.today().normalize()

longest_offset = max(
    (
        offset
        for offset in HORIZONS.values()
        if offset is not None
    ),
    key=lambda offset: today - offset,
    default=pd.DateOffset(years=1),
)

# max() above picks the offset giving the *latest* date, so pick the
# offset giving the earliest date instead.
longest_offset = min(
    (
        offset
        for offset in HORIZONS.values()
        if offset is not None
    ),
    key=lambda offset: today - offset,
)

download_start_date = (
    today
    - longest_offset
    - pd.Timedelta(
        days=DOWNLOAD_LOOKBACK_DAYS
    )
)

download_end_date = today

chart_title = (
    "Global Equity Market Returns Across Time Horizons"
)

# =====================================================================
# PREPARE VALID MSCI INDEX CODES
# =====================================================================

valid_indices: dict[str, str] = {}

for index_name, index_code in ALL_INDICES.items():

    if is_placeholder_code(index_code):

        print(
            f"Skipping {index_name}: a confirmed numeric "
            f"MSCI index code has not been supplied."
        )

        continue

    cleaned_index_code = validate_numeric_index_code(
        index_name=index_name,
        index_code=index_code,
    )

    valid_indices[
        index_name
    ] = cleaned_index_code

if not valid_indices:
    raise ValueError(
        "No valid numeric MSCI index codes were supplied."
    )

# Request each code only once.
unique_index_codes = list(
    dict.fromkeys(
        valid_indices.values()
    )
)

index_code_to_names: dict[str, list[str]] = {}

for index_name, index_code in valid_indices.items():

    index_code_to_names.setdefault(
        index_code,
        [],
    ).append(
        index_name
    )

# =====================================================================
# DOWNLOAD MSCI NET TOTAL RETURN DATA
# =====================================================================

print()

print(
    "Downloading MSCI Net Total Return index data..."
)

print(
    f"Requested period: "
    f"{download_start_date:%Y-%m-%d} to "
    f"{download_end_date:%Y-%m-%d}"
)

print(
    f"Requesting {len(unique_index_codes)} unique "
    f"MSCI index code(s) in one batched request."
)

download_started = time.perf_counter()

try:

    downloaded_data = msci.get_levels(
        unique_index_codes,
        download_start_date.strftime(
            "%Y-%m-%d"
        ),
        download_end_date.strftime(
            "%Y-%m-%d"
        ),
        variant=MSCI_RETURN_VARIANT,
    )

except Exception as error:

    raise RuntimeError(
        f"The batched MSCI data request failed.\n"
        f"Original error: {error}"
    ) from error

download_seconds = (
    time.perf_counter()
    - download_started
)

if downloaded_data is None:
    raise ValueError(
        "No data returned from MSCI."
    )

hist = pd.DataFrame(
    downloaded_data
)

if hist.empty:
    raise ValueError(
        "MSCI returned an empty dataset."
    )

print(
    f"MSCI download completed in "
    f"{download_seconds:.2f} seconds."
)

print(
    f"Raw observations returned: "
    f"{len(hist):,}"
)

# =====================================================================
# NORMALISE MSCI DATA
# =====================================================================

hist.columns = [
    str(column).strip().upper()
    for column in hist.columns
]

required_columns = {
    "INDEX_CODE",
    "DATE",
    "LEVEL",
}

missing_columns = (
    required_columns.difference(
        hist.columns
    )
)

if missing_columns:
    raise ValueError(
        "MSCI response is missing required column(s): "
        + ", ".join(
            sorted(
                missing_columns
            )
        )
    )

hist["INDEX_CODE"] = (
    hist["INDEX_CODE"]
    .astype(str)
    .str.strip()
)

# Protect against numeric codes being returned as 990100.0
hist["INDEX_CODE"] = (
    hist["INDEX_CODE"]
    .str.replace(
        r"\.0$",
        "",
        regex=True,
    )
)

hist["DATE"] = pd.to_datetime(
    hist["DATE"],
    errors="coerce",
    utc=True,
).dt.tz_convert(None)

hist["LEVEL"] = pd.to_numeric(
    hist["LEVEL"],
    errors="coerce",
)

invalid_rows = (
    hist["DATE"].isna()
    | hist["LEVEL"].isna()
)

if invalid_rows.any():

    print(
        f"Removing {int(invalid_rows.sum())} row(s) "
        f"with invalid dates or index levels."
    )

    hist = hist.loc[
        ~invalid_rows
    ].copy()

if hist.empty:
    raise ValueError(
        "No valid MSCI observations remained after "
        "normalising the downloaded data."
    )

requested_code_set = set(
    unique_index_codes
)

unmatched_code_rows = (
    ~hist["INDEX_CODE"].isin(
        requested_code_set
    )
)

if unmatched_code_rows.any():

    unmatched_codes = sorted(
        hist.loc[
            unmatched_code_rows,
            "INDEX_CODE",
        ]
        .dropna()
        .unique()
        .tolist()
    )

    print(
        "Removing observations for unrecognised MSCI "
        "index code(s): "
        + ", ".join(
            unmatched_codes
        )
    )

hist = hist.loc[
    ~unmatched_code_rows
].copy()

if hist.empty:
    raise ValueError(
        "No observations matched the requested MSCI "
        "index codes."
    )

hist = (
    hist.sort_values(
        [
            "INDEX_CODE",
            "DATE",
        ]
    )
    .drop_duplicates(
        subset=[
            "INDEX_CODE",
            "DATE",
        ],
        keep="last",
    )
    .reset_index(drop=True)
)

hist["price"] = hist["LEVEL"]

returned_codes = set(
    hist["INDEX_CODE"]
    .unique()
    .tolist()
)

for missing_code in unique_index_codes:

    if missing_code not in returned_codes:

        print(
            f"No MSCI history returned for code {missing_code}: "
            + ", ".join(
                index_code_to_names.get(
                    missing_code,
                    [],
                )
            )
        )

# =====================================================================
# CALCULATE MULTI-PERIOD RETURNS
# =====================================================================

# Common reference date: the latest observation in the dataset
as_of_date = hist["DATE"].max()

print(
    f"Latest observation date: {as_of_date:%Y-%m-%d}"
)

horizon_cols = list(
    HORIZONS.keys()
)

rows: list[dict[str, object]] = []

for index_name, index_code in valid_indices.items():

    try:

        levels = (
            hist.loc[
                hist["INDEX_CODE"] == index_code,
                [
                    "DATE",
                    "price",
                ],
            ]
            .drop_duplicates(
                subset=[
                    "DATE",
                ],
                keep="last",
            )
            .set_index(
                "DATE"
            )["price"]
            .sort_index()
        )

        if levels.empty:

            print(
                f"No MSCI history returned for "
                f"{index_name}: {index_code}"
            )

            continue

        end_level = float(
            levels.asof(
                as_of_date
            )
        )

        row: dict[str, object] = {
            "Sector": index_name,
        }

        for label, offset in HORIZONS.items():

            if label == "1D":

                # Latest observation vs the previous trading day
                if len(levels) >= 2:

                    period_return = (
                        float(levels.iloc[-1])
                        / float(levels.iloc[-2])
                        - 1
                    )

                else:

                    period_return = np.nan

            else:

                target_date = as_of_date - offset

                # No history that far back for this index
                if target_date < levels.index[0]:

                    period_return = np.nan

                else:

                    start_level = levels.asof(
                        target_date
                    )

                    if pd.isna(start_level) or start_level == 0:

                        period_return = np.nan

                    else:

                        period_return = (
                            end_level
                            / float(start_level)
                            - 1
                        )

            # Annualise the multi-year horizons
            years = HORIZON_YEARS.get(
                label
            )

            if (
                ANNUALISE_FROM_YEARS is not None
                and years is not None
                and years >= ANNUALISE_FROM_YEARS
                and pd.notna(period_return)
            ):

                period_return = (
                    (1 + period_return)
                    ** (1 / years)
                    - 1
                )

            row[label] = (
                period_return * 100
                if pd.notna(period_return)
                else np.nan
            )

        # Annualised SD of daily returns over the trailing window
        sd_window = levels.loc[
            as_of_date - SD_LOOKBACK:
            as_of_date
        ]

        sd_daily_returns = (
            sd_window
            .pct_change(
                fill_method=None
            )
            .dropna()
        )

        if len(sd_daily_returns) >= MIN_SD_OBSERVATIONS:

            row["Annualized SD"] = (
                float(
                    sd_daily_returns.std(
                        ddof=1
                    )
                )
                * np.sqrt(252)
                * 100
            )

        else:

            row["Annualized SD"] = np.nan

        rows.append(
            row
        )

    except Exception as exc:

        print(
            f"Failed for {index_name}: {exc}"
        )

# =====================================================================
# BUILD DATAFRAME
# =====================================================================

combined_df = pd.DataFrame(
    rows
)

if combined_df.empty:
    raise ValueError(
        "No valid sector data found."
    )

combined_df = combined_df.set_index(
    "Sector"
)

combined_df = combined_df[
    horizon_cols
    + [
        "Annualized SD",
    ]
]

combined_df = combined_df.sort_values(
    SORT_BY,
    ascending=False,
    na_position="last",
)

# =====================================================================
# DYNAMIC INSIGHT-LED SUBTITLE
# =====================================================================

subtitle = (
    "Equity-market returns across major economies over horizons "
    "from one day to ten years, with trailing one-year volatility"
)

sort_series = (
    combined_df[SORT_BY]
    .replace([np.inf, -np.inf], np.nan)
    .dropna()
    .sort_values(ascending=False)
)

month_series = (
    combined_df["1M"]
    .replace([np.inf, -np.inf], np.nan)
    .dropna()
    .sort_values(ascending=False)
)

vol_series = (
    combined_df["Annualized SD"]
    .replace([np.inf, -np.inf], np.nan)
    .dropna()
    .sort_values(ascending=False)
)

if (
    len(sort_series) >= 2
    and len(month_series) >= 2
    and len(vol_series) >= 2
):

    subtitle = (
        f"Over {SORT_BY}, {sort_series.index[0]} led at "
        f"{sort_series.iloc[0]:+.1f}% while "
        f"{sort_series.index[-1]} lagged at "
        f"{sort_series.iloc[-1]:+.1f}%. Over the past month, "
        f"{month_series.index[0]} led at "
        f"{month_series.iloc[0]:+.1f}% and "
        f"{month_series.index[-1]} trailed at "
        f"{month_series.iloc[-1]:+.1f}%. "
        f"{vol_series.index[-1]} was the least volatile at "
        f"{vol_series.iloc[-1]:.1f}%, compared with "
        f"{vol_series.index[0]} at {vol_series.iloc[0]:.1f}%."
    )

# =====================================================================
# PREPARE HEATMAP DATA
# =====================================================================

heatmap_df = combined_df[
    horizon_cols
].copy()

annualized_sd_series = (
    combined_df["Annualized SD"]
    .copy()
)

annot_df = pd.DataFrame(
    "",
    index=heatmap_df.index,
    columns=heatmap_df.columns,
)

for column in horizon_cols:

    decimals = 2 if column == "1D" else 1

    annot_df[column] = heatmap_df[column].map(
        lambda value, d=decimals: (
            f"{value:+.{d}f}%"
            if pd.notna(value)
            else ""
        )
    )

# Header labels (flag the annualised columns)
display_labels: list[str] = []

for column in horizon_cols:

    years = HORIZON_YEARS.get(
        column
    )

    if (
        ANNUALISE_FROM_YEARS is not None
        and years is not None
        and years >= ANNUALISE_FROM_YEARS
    ):

        display_labels.append(
            f"{column} p.a."
        )

    else:

        display_labels.append(
            column
        )

# =====================================================================
# PLOT
# =====================================================================

number_of_rows = len(
    heatmap_df
)

sd_column_index = len(
    horizon_cols
)

total_number_of_columns = (
    sd_column_index + 1
)

figure_width = 23

figure_height = max(
    10,
    0.42 * number_of_rows + 4.2,
)

fig = plt.figure(
    figsize=(
        figure_width,
        figure_height,
    ),
    facecolor="white",
)

renderer = fig.canvas.get_renderer()

common_left_position = 0.03

common_right_position = 0.97

# ---------------------------------------------------------------------
# Measure the widest y-axis label so the first column fits its content
# ---------------------------------------------------------------------

maximum_label_width_pixels = 0.0

for label in [
    "Economies",
    *heatmap_df.index,
]:

    probe = fig.text(
        0,
        0,
        label,
        fontsize=16,
        fontweight="bold",
    )

    maximum_label_width_pixels = max(
        maximum_label_width_pixels,
        probe.get_window_extent(
            renderer=renderer
        ).width,
    )

    probe.remove()

label_padding_left_pixels = 0.12 * fig.dpi

label_padding_right_pixels = 0.20 * fig.dpi

label_column_pixels = (
    maximum_label_width_pixels
    + label_padding_left_pixels
    + label_padding_right_pixels
)

table_width_pixels = (
    (
        common_right_position
        - common_left_position
    )
    * fig.bbox.width
)

pixels_per_heatmap_column = (
    (
        table_width_pixels
        - label_column_pixels
    )
    / total_number_of_columns
)

y_axis_label_column_width = (
    label_column_pixels
    / pixels_per_heatmap_column
)

label_text_offset = (
    label_padding_left_pixels
    / pixels_per_heatmap_column
)

ax = fig.add_axes(
    [
        common_left_position,
        HEAT_MAP_Y,
        common_right_position
        - common_left_position,
        0.74,
    ]
)

# ---------------------------------------------------------------------
# Heatmap: one independent colour scale per horizon column
# ---------------------------------------------------------------------

for column in horizon_cols:

    column_df = pd.DataFrame(
        np.nan,
        index=heatmap_df.index,
        columns=heatmap_df.columns,
    )

    column_df[column] = heatmap_df[column]

    column_annot = pd.DataFrame(
        "",
        index=heatmap_df.index,
        columns=heatmap_df.columns,
    )

    column_annot[column] = annot_df[column]

    if column_df[column].notna().sum() == 0:
        continue

    column_limit = float(
        column_df[column]
        .abs()
        .max()
    )

    if not np.isfinite(column_limit) or column_limit <= 0:

        column_limit = 1.0

    sns.heatmap(
        column_df,
        ax=ax,
        cmap="RdYlGn",
        vmin=-column_limit,
        vmax=column_limit,
        center=0,
        annot=column_annot.values,
        fmt="",
        annot_kws={
            "fontsize": 15,
            "fontweight": "bold",
        },
        mask=column_df.isna(),
        cbar=False,
        linewidths=1,
        linecolor="white",
        xticklabels=False,
        yticklabels=False,
    )

ax.set_xlabel("")

ax.set_ylabel("")

ax.set_xticks([])

for spine in ax.spines.values():
    spine.set_visible(False)

# =====================================================================
# ANNUALIZED SD DATA BARS (LEFT TO RIGHT GRADIENT)
# =====================================================================

finite_sd_values = (
    annualized_sd_series
    .replace(
        [
            np.inf,
            -np.inf,
        ],
        np.nan,
    )
    .dropna()
)

if finite_sd_values.empty:

    maximum_sd = 1.0

else:

    maximum_sd = float(
        finite_sd_values.max()
    )

if maximum_sd <= 0:

    maximum_sd = 1.0

sd_gradient_cmap = (
    LinearSegmentedColormap.from_list(
        "AnnualizedSDGradient",
        [
            "#F2F2F2",
            "#FFE8E8",
            "#FFCACA",
            "#FF9D9D",
            "#FF7070",
            "#FF4D4D",
        ],
    )
)

sd_gradient_array = np.linspace(
    0,
    1,
    256,
).reshape(
    1,
    -1,
)

for row_position, sd_value in enumerate(
    annualized_sd_series
):

    cell_x = sd_column_index

    cell_y = row_position

    ax.add_patch(
        Rectangle(
            (
                cell_x,
                cell_y,
            ),
            1,
            1,
            facecolor="white",
            edgecolor="none",
            linewidth=0,
            zorder=5,
        )
    )

    if pd.notna(sd_value) and np.isfinite(sd_value):

        bar_fraction = float(
            np.clip(
                sd_value / maximum_sd,
                0.03,
                1.0,
            )
        )

        ax.imshow(
            sd_gradient_array,
            cmap=sd_gradient_cmap,
            extent=[
                cell_x,
                cell_x + bar_fraction,
                cell_y + 1,
                cell_y,
            ],
            aspect="auto",
            interpolation="bilinear",
            zorder=6,
        )

        ax.text(
            cell_x + 0.5,
            cell_y + 0.5,
            f"{sd_value:.1f}%",
            ha="center",
            va="center",
            fontsize=15,
            fontweight="bold",
            color="black",
            zorder=11,
        )

# imshow resets the axis limits, so apply the table limits afterwards
ax.set_xlim(
    -y_axis_label_column_width,
    total_number_of_columns,
)

ax.set_ylim(
    number_of_rows,
    -1,
)

# =====================================================================
# X-AXIS LABEL CELLS
# =====================================================================

x_axis_labels = (
    display_labels
    + [
        SD_LABEL,
    ]
)

for column_position, column_label in enumerate(
    x_axis_labels
):

    ax.add_patch(
        Rectangle(
            (
                column_position,
                -1,
            ),
            1,
            1,
            facecolor="#F2F2F2",
            edgecolor="none",
            linewidth=0,
            zorder=9,
            clip_on=False,
        )
    )

    ax.text(
        column_position + 0.5,
        -0.5,
        column_label,
        ha="center",
        va="center",
        fontsize=16,
        fontweight="bold",
        color="black",
        zorder=11,
        clip_on=False,
    )

ax.add_patch(
    Rectangle(
        (
            0,
            -1,
        ),
        total_number_of_columns,
        1,
        facecolor="none",
        edgecolor="#1b263b",
        linewidth=2.5,
        zorder=15,
        clip_on=False,
    )
)

# =====================================================================
# Y-AXIS LABEL CELLS
# =====================================================================

ax.set_yticks([])

ax.tick_params(
    axis="y",
    which="both",
    length=0,
)

for row_position, row_label in enumerate(
    heatmap_df.index
):

    if row_label in BENCHMARK_NAMES:

        y_axis_label_fill = "#a9d6e5"

    else:

        y_axis_label_fill = "#F2F2F2"

    ax.add_patch(
        Rectangle(
            (
                -y_axis_label_column_width,
                row_position,
            ),
            y_axis_label_column_width,
            1,
            facecolor=y_axis_label_fill,
            edgecolor="none",
            linewidth=0,
            zorder=10,
            clip_on=False,
        )
    )

    ax.text(
        -y_axis_label_column_width
        + label_text_offset,
        row_position + 0.5,
        row_label,
        ha="left",
        va="center",
        fontsize=16,
        fontweight="bold",
        color="black",
        zorder=11,
        clip_on=False,
    )

# =====================================================================
# TOP-LEFT CORNER CELL
# =====================================================================

ax.add_patch(
    Rectangle(
        (
            -y_axis_label_column_width,
            -1,
        ),
        y_axis_label_column_width,
        1,
        facecolor="#F2F2F2",
        edgecolor="#1b263b",
        linewidth=2.5,
        zorder=17,
        clip_on=False,
    )
)

ax.text(
    -y_axis_label_column_width
    + label_text_offset,
    -0.5,
    "Economies",
    ha="left",
    va="center",
    fontsize=16,
    fontweight="bold",
    color="black",
    zorder=18,
    clip_on=False,
)

# =====================================================================
# BORDERS AND ROW GUIDES
# =====================================================================

# Bottom border of the header row
ax.plot(
    [
        -y_axis_label_column_width,
        total_number_of_columns,
    ],
    [
        0,
        0,
    ],
    color="#1b263b",
    linewidth=2.5,
    zorder=24,
    clip_on=False,
)

# Vertical border between the label column and the data columns
ax.plot(
    [
        0,
        0,
    ],
    [
        -1,
        number_of_rows,
    ],
    color="#1b263b",
    linewidth=2.5,
    zorder=14,
    clip_on=False,
)

# Vertical border before the SD column
ax.plot(
    [
        sd_column_index,
        sd_column_index,
    ],
    [
        -1,
        number_of_rows,
    ],
    color="#1b263b",
    linewidth=2.5,
    zorder=16,
    clip_on=False,
)

# Row guides
for row_boundary in range(
    1,
    number_of_rows,
):

    ax.plot(
        [
            -y_axis_label_column_width,
            total_number_of_columns,
        ],
        [
            row_boundary,
            row_boundary,
        ],
        color="#1b263b",
        linewidth=1,
        linestyle=(
            0,
            (
                1,
                2.5,
            ),
        ),
        alpha=1,
        zorder=23,
        clip_on=False,
    )

# Outside border of the entire table
ax.add_patch(
    Rectangle(
        (
            -y_axis_label_column_width,
            -1,
        ),
        total_number_of_columns
        + y_axis_label_column_width,
        number_of_rows + 1,
        facecolor="none",
        edgecolor="#1b263b",
        linewidth=2.5,
        zorder=25,
        clip_on=False,
    )
)

# =====================================================================
# TITLE
# =====================================================================

fig.text(
    common_left_position,
    TITLE_Y,
    chart_title,
    ha="left",
    va="top",
    fontsize=36,
    fontweight="bold",
)

# =====================================================================
# WORD-WRAPPED SUBTITLE AND NOTES
# =====================================================================


def wrap_text_to_figure_width(
    text: str,
    left: float,
    right: float,
    **text_kwargs,
) -> list[str]:
    """Wrap text on word boundaries so each line fits left..right."""

    wrapped_lines: list[str] = []

    current_line = ""

    for word in text.split():

        candidate = (
            word
            if not current_line
            else f"{current_line} {word}"
        )

        probe = fig.text(
            left,
            0.5,
            candidate,
            **text_kwargs,
        )

        candidate_width = (
            probe.get_window_extent(
                renderer=renderer
            ).width
            / fig.bbox.width
        )

        probe.remove()

        if (
            left + candidate_width <= right
            or not current_line
        ):

            current_line = candidate

        else:

            wrapped_lines.append(
                current_line
            )

            current_line = word

    if current_line:

        wrapped_lines.append(
            current_line
        )

    return wrapped_lines


subtitle_right_limit = 0.97

subtitle_font_size = 18.0

subtitle_color = "#696969"

subtitle_lines = wrap_text_to_figure_width(
    subtitle,
    common_left_position,
    subtitle_right_limit,
    fontsize=subtitle_font_size,
)

if subtitle_lines:

    fig.text(
        common_left_position,
        SUBTITLE_Y,
        subtitle_lines[0],
        ha="left",
        va="top",
        fontsize=subtitle_font_size,
        color=subtitle_color,
    )

    if len(subtitle_lines) >= 2:

        fig.text(
            common_left_position,
            SUBTITLE_Y - SUBTITLE_LINE_SPACING,
            " ".join(
                subtitle_lines[1:]
            ),
            ha="left",
            va="top",
            fontsize=subtitle_font_size,
            color=subtitle_color,
        )

# =====================================================================
# SOURCE
# =====================================================================

fig.text(
    common_left_position,
    SOURCE_Y,
    "Source: MSCI",
    ha="left",
    va="bottom",
    fontsize=16,
    style="italic",
    color="#7d8597",
    alpha=1,
)

# =====================================================================
# DATA NOTE
# =====================================================================

data_note = (
    "Notes: Returns are MSCI Net Total Return indices in USD, "
    f"measured to {as_of_date:%d %b %Y}. "
)

if ANNUALISE_FROM_YEARS is not None:

    data_note += (
        f"Horizons of {ANNUALISE_FROM_YEARS} years or more are "
        "annualised (p.a.); shorter horizons are cumulative. "
    )

else:

    data_note += (
        "All horizons are cumulative returns. "
    )

data_note += (
    f"{SD_LABEL} is the standard deviation of daily returns over "
    "the last year, annualized using the 252 trading day "
    "convention. Blank cells indicate insufficient index history."
)

data_note_font_size = 16

data_note_color = "#7d8597"

data_note_alpha = 1

data_note_lines = wrap_text_to_figure_width(
    data_note,
    common_left_position,
    common_right_position,
    fontsize=data_note_font_size,
    style="italic",
)

if data_note_lines:

    fig.text(
        common_left_position,
        NOTE_Y,
        data_note_lines[0],
        ha="left",
        va="bottom",
        fontsize=data_note_font_size,
        style="italic",
        color=data_note_color,
        alpha=data_note_alpha,
    )

    if len(data_note_lines) >= 2:

        fig.text(
            common_left_position,
            NOTE_Y - NOTE_LINE_SPACING,
            " ".join(
                data_note_lines[1:]
            ),
            ha="left",
            va="bottom",
            fontsize=data_note_font_size,
            style="italic",
            color=data_note_color,
            alpha=data_note_alpha,
        )

# =====================================================================
# Confirm Font Used
# =====================================================================

resolved = font_manager.findfont(
    font_manager.FontProperties(family="sans-serif", weight="bold")
)
print("Font used:", resolved)

# =====================================================================
# DISPLAY
# =====================================================================

plt.show()