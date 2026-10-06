from __future__ import annotations

# =============================================================================
# Imports
# =============================================================================

import time
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
from matplotlib.dates import DateFormatter, MonthLocator
from matplotlib.ticker import FormatStrFormatter

try:
    from mscidata import msci
except ImportError as error:
    raise ImportError(
        "\nCould not import 'msci' from the 'mscidata' package.\n\n"
        "Install or upgrade the required packages using:\n\n"
        "    pip install --upgrade msci-data pandas\n\n"
        f"Original import error: {error}"
    ) from error


# =============================================================================
# Configuration
# =============================================================================

SCRIPT_VERSION = "MSCI_RATIO_SLIDE_V1.3"
print(f"SCRIPT_VERSION = {SCRIPT_VERSION}")

YEAR: int | None = None
INCLUDE_CURRENT_MONTH = True
SAVE_SV = False
DOWNLOAD_LOOKBACK_DAYS = 10
MSCI_RETURN_VARIANT = "NETR"

SERIES_DEFINITIONS = [
    ("990100", "129857", "MSCI World", "#6b8fd1"),
    ("891800", "129856", "MSCI Emerging Markets", "#e8856a"),
]

SLIDE_WIDTH_PX = 1920
SLIDE_HEIGHT_PX = 1080

LEFT_MARGIN_PX = 90
RIGHT_MARGIN_PX = 1920 - 90

BANNER_RADIUS_PX = 7
BANNER_TEXT_BASELINE_PX = 226.7

NEUTRAL_BAND_PCT = 1.0

INK = "#000000"
SUBTITLE_INK = "#2d2a2a"
AXIS = "#7f7f7f"
GRID = "#b9b9b9"
FOOT = "#8c8c8c"
BANNER_TEXT = "#ffffff"

TITLE_SIZE = 26
SUBTITLE_SIZE = 14
FOOT_SIZE = 11
TICK_SIZE = 13
BANNER_SIZE = 18

PANEL_GEOMETRY = [
    {
        "axes": (225.0, 941.3, 261.2, 853.7),
        "banner": (225.0, 945.0, 192.0, 240.0),
    },
    {
        "axes": (1083.6, 1798.0, 265.0, 858.5),
        "banner": (1081.0, 1800.0, 192.0, 240.0),
    },
]

NOTE_TEXT = (
    "Note: Ratio = daily MSCI Net Total Return index level (USD, dividends "
    "reinvested net of withholding tax), market-cap weighted index / "
    "equal-weighted index: MSCI World (990100 / 129857), "
    "MSCI Emerging Markets (891800 / 129856). Past performance is not a "
    "reliable indicator of future results. Indices are unmanaged, exclude "
    "fees and costs, and cannot be invested in directly. Panels use separate "
    "scales."
)


# =============================================================================
# Matplotlib typography
# =============================================================================

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = [
    "Helvetica",
    "Arial",
    "Liberation Sans",
    "DejaVu Sans",
]


# =============================================================================
# Slide coordinate helpers
# =============================================================================

def rx_x(value_px: float) -> float:
    """Convert slide x-coordinate in pixels to figure-relative x."""
    return value_px / SLIDE_WIDTH_PX


def px_y(value_px: float) -> float:
    """Convert slide y-coordinate from top-left pixels to figure y."""
    return 1.0 - value_px / SLIDE_HEIGHT_PX


# =============================================================================
# Date range
# =============================================================================

today = pd.Timestamp.today().normalize()

if YEAR is not None:
    start = pd.Timestamp(
        year=YEAR,
        month=1,
        day=1,
    )
    end = pd.Timestamp(
        year=YEAR,
        month=12,
        day=31,
    )
else:
    if INCLUDE_CURRENT_MONTH:
        end = today
        start = (
            today.replace(day=1)
            - pd.DateOffset(months=12)
        )
    else:
        end = (
            today.replace(day=1)
            - pd.Timedelta(days=1)
        )
        start = (
            end.replace(day=1)
            - pd.DateOffset(months=12)
        )

download_start = (
    start
    - pd.Timedelta(days=DOWNLOAD_LOOKBACK_DAYS)
)

download_end = min(end, today)

if start >= end:
    raise ValueError(
        "Start date must be earlier than end date."
    )


# =============================================================================
# MSCI data download
# =============================================================================

codes = sorted(
    {
        code
        for cap_code, equal_code, _, _ in SERIES_DEFINITIONS
        for code in (cap_code, equal_code)
    }
)

download_start_str = download_start.strftime("%Y-%m-%d")
download_end_str = download_end.strftime("%Y-%m-%d")

print(
    f"Downloading MSCI levels: "
    f"{download_start_str} -> {download_end_str}"
)
print(
    f"Return variant: {MSCI_RETURN_VARIANT}"
)
print(
    f"Codes: {', '.join(codes)}"
)

download_t0 = time.perf_counter()

try:
    raw_data = msci.get_levels(
        codes,
        download_start_str,
        download_end_str,
        MSCI_RETURN_VARIANT,
    )
except Exception as error:
    raise RuntimeError(
        "\nMSCI data download failed.\n\n"
        f"Codes: {codes}\n"
        f"Start: {download_start_str}\n"
        f"End: {download_end_str}\n"
        f"Variant: {MSCI_RETURN_VARIANT}\n\n"
        f"Original error: {error}"
    ) from error

download_seconds = time.perf_counter() - download_t0

print(
    f"MSCI download completed in "
    f"{download_seconds:.2f}s"
)


# =============================================================================
# Data preparation
# =============================================================================

if isinstance(raw_data, pd.DataFrame):
    data = raw_data.copy()
else:
    data = pd.DataFrame(raw_data)

data.columns = [
    str(column).strip().upper()
    for column in data.columns
]

required_columns = {
    "INDEX_CODE",
    "DATE",
    "LEVEL",
}

missing_columns = (
    required_columns
    - set(data.columns)
)

if missing_columns:
    raise ValueError(
        "MSCI data is missing required columns: "
        + ", ".join(sorted(missing_columns))
    )

data["INDEX_CODE"] = (
    data["INDEX_CODE"]
    .astype(str)
    .str.strip()
    .str.replace("O", "", regex=False)
)

data["DATE"] = (
    pd.to_datetime(
        data["DATE"],
        utc=True,
        errors="coerce",
    )
    .dt.tz_localize(None)
)

data["LEVEL"] = pd.to_numeric(
    data["LEVEL"],
    errors="coerce",
)

data = (
    data
    .dropna(
        subset=[
            "INDEX_CODE",
            "DATE",
            "LEVEL",
        ]
    )
    .sort_values(
        [
            "INDEX_CODE",
            "DATE",
        ]
    )
    .drop_duplicates(
        [
            "INDEX_CODE",
            "DATE",
        ],
        keep="last",
    )
    .reset_index(drop=True)
)

missing_codes = sorted(
    set(codes)
    - set(data["INDEX_CODE"])
)

if missing_codes:
    print(
        "Missing codes: "
        + ", ".join(missing_codes)
    )
else:
    print("Missing codes: none")


# =============================================================================
# Ratio construction
# =============================================================================

ratio_series: list[dict[str, Any]] = []

for (
    cap_code,
    equal_code,
    label,
    colour,
) in SERIES_DEFINITIONS:

    cap = (
        data.loc[
            data["INDEX_CODE"] == cap_code,
            [
                "DATE",
                "LEVEL",
            ],
        ]
        .rename(
            columns={
                "LEVEL": "CAP",
            }
        )
        .set_index("DATE")
    )

    equal = (
        data.loc[
            data["INDEX_CODE"] == equal_code,
            [
                "DATE",
                "LEVEL",
            ],
        ]
        .rename(
            columns={
                "LEVEL": "EQUAL",
            }
        )
        .set_index("DATE")
    )

    combined = (
        pd.concat(
            [
                cap,
                equal,
            ],
            axis=1,
        )
        .sort_index()
        .ffill()
        .dropna()
    )

    combined = combined.loc[
        (combined.index >= start)
        & (combined.index <= end)
    ]

    if combined.empty:
        print(
            f"Skipping {label}: "
            "no ratio data in selected period."
        )
        continue

    ratio = (
        combined["CAP"]
        / combined["EQUAL"]
    )

    ratio = (
        ratio
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            np.nan,
        )
        .dropna()
    )

    if ratio.empty:
        print(
            f"Skipping {label}: "
            "no valid ratio data."
        )
        continue

    if len(ratio) >= 2:
        days_elapsed = (
            ratio.index
            - ratio.index[0]
        ).total_seconds() / 86400.0

        slope = np.polyfit(
            days_elapsed,
            ratio.to_numpy(dtype=float),
            1,
        )[0]

        trend_pct = (
            slope
            * days_elapsed[-1]
            / ratio.mean()
            * 100.0
        )
    else:
        trend_pct = 0.0

    ratio_series.append(
        {
            "cap_code": cap_code,
            "equal_code": equal_code,
            "label": label,
            "colour": colour,
            "ratio": ratio,
            "start_value": float(
                ratio.iloc[0]
            ),
            "end_value": float(
                ratio.iloc[-1]
            ),
            "trend_pct": float(
                trend_pct
            ),
        }
    )

if not ratio_series:
    raise ValueError(
        "There is no ratio data available "
        "for the selected period."
    )


# =============================================================================
# Optional CSV output
# =============================================================================

if SAVE_SV:
    csv_parts = []

    for item in ratio_series:
        part = (
            item["ratio"]
            .rename("RATIO")
            .to_frame()
            .reset_index()
        )

        part.insert(
            0,
            "INDEX",
            item["label"],
        )

        csv_parts.append(part)

    csv_output = pd.concat(
        csv_parts,
        ignore_index=True,
    )

    csv_output.to_csv(
        "msci_cap_equal_ratios.csv",
        index=False,
    )

    print(
        "Saved: msci_cap_equal_ratios.csv"
    )


# =============================================================================
# Narrative helpers
# =============================================================================

def classify(
    trend_pct: float,
) -> str:
    if trend_pct > NEUTRAL_BAND_PCT:
        return "concentrated"

    if trend_pct < -NEUTRAL_BAND_PCT:
        return "broad-based"

    return "balanced"


def format_ratio(
    value: float,
) -> str:
    if abs(value) < 0.5:
        return f"{value:.3f}x"

    return f"{value:.2f}x"


def join_with_and(
    items: list[str],
) -> str:
    if len(items) == 1:
        return items[0]

    if len(items) == 2:
        return (
            f"{items[0]} and {items[1]}"
        )

    return (
        f"{', '.join(items[:-1])}, "
        f"and {items[-1]}"
    )


def trend_word(
    status: str,
) -> str:
    if status == "concentrated":
        return "trended upward"

    if status == "broad-based":
        return "trended downward"

    return "was broadly flat"


# =============================================================================
# Narrative construction
# =============================================================================

period_phrase = (
    f"in {YEAR}"
    if YEAR is not None
    else "over the last 12 months"
)

for item in ratio_series:
    item["status"] = classify(
        item["trend_pct"]
    )
    item["trend_word"] = trend_word(
        item["status"]
    )

statuses = [
    item["status"]
    for item in ratio_series
]

if len(set(statuses)) == 1:
    common_status = statuses[0]

    movements = [
        (
            f"from "
            f"{format_ratio(item['start_value'])} "
            f"to "
            f"{format_ratio(item['end_value'])} "
            f"in {item['label']}"
        )
        for item in ratio_series
    ]

    if len(ratio_series) > 1:
        observation = (
            "the cap-weighted to equal-weighted ratio "
            f"{trend_word(common_status)} in both markets, "
            f"going {join_with_and(movements)}"
        )
    else:
        item = ratio_series[0]

        observation = (
            "the cap-weighted to equal-weighted ratio "
            f"{trend_word(common_status)}, going from "
            f"{format_ratio(item['start_value'])} "
            f"to {format_ratio(item['end_value'])} "
            f"in {item['label']}"
        )

    if common_status == "concentrated":
        conclusion = (
            "growth has been concentrated in the largest "
            f"companies ({period_phrase}), with the largest "
            "outpacing the average company"
        )

    elif common_status == "broad-based":
        conclusion = (
            "growth has been broad-based across companies "
            f"({period_phrase}), with the average company "
            "outpacing the largest"
        )

    else:
        conclusion = (
            "growth has not been clearly concentrated or "
            f"broad-based ({period_phrase}), with large and "
            "average companies broadly in line"
        )

else:
    observation_parts = [
        (
            f"{item['trend_word']} in {item['label']} "
            f"(from "
            f"{format_ratio(item['start_value'])} "
            f"to "
            f"{format_ratio(item['end_value'])})"
        )
        for item in ratio_series
    ]

    observation = (
        "the cap-weighted to equal-weighted ratio "
        + join_with_and(observation_parts)
    )

    status_order = [
        "concentrated",
        "broad-based",
        "balanced",
    ]

    status_phrases = []

    for status in status_order:
        status_labels = [
            item["label"]
            for item in ratio_series
            if item["status"] == status
        ]

        if status_labels:
            status_phrases.append(
                f"{status} in "
                f"{join_with_and(status_labels)}"
            )

    conclusion = (
        f"growth has been mixed ({period_phrase}): "
        + " but ".join(status_phrases)
    )

subtitle = (
    f"We can see {observation}, "
    f"and hence {conclusion}."
)


# =============================================================================
# Figure
# =============================================================================

fig = plt.figure(
    figsize=(16, 9),
    dpi=150,
    facecolor="white",
)

fig.patch.set_facecolor("white")


# =============================================================================
# Full-canvas overlay
#
# IMPORTANT:
# The overlay deliberately uses slide pixels as its data coordinates.
# x = 0..1920 from left to right
# y = 0..1080 from top to bottom
# =============================================================================

overlay = fig.add_axes(
    [0, 0, 1, 1],
    zorder=10,
    facecolor="none",
)

overlay.set_xlim(
    0,
    SLIDE_WIDTH_PX,
)

overlay.set_ylim(
    0,
    SLIDE_HEIGHT_PX,
)

overlay.invert_yaxis()
overlay.axis("off")


# =============================================================================
# Rendered text measurement / wrapping
# =============================================================================

def rendered_text_width_px(
    text: str,
    fontsize: float,
    italic: bool = False,
) -> float:

    probe = fig.text(
        0,
        0,
        text,
        fontsize=fontsize,
        fontweight="normal",
        fontstyle=(
            "italic"
            if italic
            else "normal"
        ),
        alpha=0,
    )

    fig.canvas.draw()

    renderer = fig.canvas.get_renderer()

    extent = probe.get_window_extent(
        renderer=renderer
    )

    probe.remove()

    return (
        extent.width
        * SLIDE_WIDTH_PX
        / fig.bbox.width
    )


def wrap_text(
    text: str,
    fontsize: float,
    max_width_px: float,
    italic: bool = False,
) -> list[str]:

    words = text.split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = (
            word
            if not current
            else f"{current} {word}"
        )

        if (
            rendered_text_width_px(
                candidate,
                fontsize,
                italic=italic,
            )
            <= max_width_px
        ):
            current = candidate
        else:
            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


def fit_wrapped_text(
    text: str,
    initial_size: float,
    minimum_size: float,
    max_width_px: float,
    max_lines: int,
    italic: bool = False,
) -> tuple[float, list[str]]:

    fontsize = initial_size

    while fontsize >= minimum_size:
        lines = wrap_text(
            text,
            fontsize,
            max_width_px,
            italic=italic,
        )

        if len(lines) <= max_lines:
            return fontsize, lines

        fontsize -= 0.5

    return (
        minimum_size,
        wrap_text(
            text,
            minimum_size,
            max_width_px,
            italic=italic,
        ),
    )


# =============================================================================
# Title
# =============================================================================

overlay.text(
    LEFT_MARGIN_PX,
    83,
    "Is Equity Growth Concentrated or Broad-Based?",
    transform=overlay.transData,
    fontsize=TITLE_SIZE,
    fontweight="bold",
    color=INK,
    ha="left",
    va="baseline",
)


# =============================================================================
# Subtitle
# =============================================================================

max_text_width = (
    RIGHT_MARGIN_PX
    - LEFT_MARGIN_PX
)

subtitle_size, subtitle_lines = (
    fit_wrapped_text(
        subtitle,
        initial_size=SUBTITLE_SIZE,
        minimum_size=11,
        max_width_px=max_text_width,
        max_lines=2,
        italic=False,
    )
)

subtitle_baselines = [
    124,
    155,
]

for line, baseline in zip(
    subtitle_lines,
    subtitle_baselines,
):
    overlay.text(
        LEFT_MARGIN_PX,
        baseline,
        line,
        transform=overlay.transData,
        fontsize=subtitle_size,
        color=SUBTITLE_INK,
        ha="left",
        va="baseline",
    )


# =============================================================================
# Source
# =============================================================================

overlay.text(
    LEFT_MARGIN_PX,
    981,
    "Source: MSCI",
    transform=overlay.transData,
    fontsize=FOOT_SIZE,
    fontstyle="italic",
    color=FOOT,
    ha="left",
    va="baseline",
)


# =============================================================================
# Note
# =============================================================================

note_size, note_lines = fit_wrapped_text(
    NOTE_TEXT,
    initial_size=FOOT_SIZE,
    minimum_size=8,
    max_width_px=max_text_width,
    max_lines=2,
    italic=True,
)

note_baselines = [
    1013,
    1037,
]

for line, baseline in zip(
    note_lines,
    note_baselines,
):
    overlay.text(
        LEFT_MARGIN_PX,
        baseline,
        line,
        transform=overlay.transData,
        fontsize=note_size,
        fontstyle="italic",
        color=FOOT,
        ha="left",
        va="baseline",
    )


# =============================================================================
# Plot panels
# =============================================================================

for item, geometry in zip(
    ratio_series,
    PANEL_GEOMETRY,
):

    axes_left, axes_right, axes_top, axes_bottom = (
        geometry["axes"]
    )

    axes = fig.add_axes(
        [
            rx_x(axes_left),
            px_y(axes_bottom),
            rx_x(
                axes_right
                - axes_left
            ),
            (
                axes_bottom
                - axes_top
            )
            / SLIDE_HEIGHT_PX,
        ],
        zorder=2,
        facecolor="none",
    )

    ratio = item["ratio"]

    # -------------------------------------------------------------------------
    # Ratio line
    # -------------------------------------------------------------------------

    axes.plot(
        ratio.index,
        ratio.values,
        color=item["colour"],
        linewidth=2.6,
        solid_capstyle="round",
        solid_joinstyle="round",
        zorder=4,
    )

    # -------------------------------------------------------------------------
    # Grid
    # -------------------------------------------------------------------------

    axes.set_axisbelow(True)

    axes.grid(
        True,
        which="major",
        axis="both",
        linestyle="--",
        linewidth=1,
        color=GRID,
        zorder=0,
    )

    # -------------------------------------------------------------------------
    # Spines
    # -------------------------------------------------------------------------

    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)

    axes.spines["left"].set_color(AXIS)
    axes.spines["bottom"].set_color(AXIS)

    axes.spines["left"].set_linewidth(1.5)
    axes.spines["bottom"].set_linewidth(1.5)

    # -------------------------------------------------------------------------
    # X axis
    # -------------------------------------------------------------------------

    axes.xaxis.set_major_locator(
        MonthLocator(interval=1)
    )

    axes.xaxis.set_major_formatter(
        DateFormatter("%b %y")
    )

    axes.tick_params(
        axis="x",
        which="major",
        labelsize=TICK_SIZE,
        length=5,
        width=1.2,
        pad=8,
        colors=INK,
    )

    for tick in axes.get_xticklabels():
        tick.set_rotation(30)
        tick.set_ha("right")

    # -------------------------------------------------------------------------
    # Y axis
    # -------------------------------------------------------------------------

    axes.yaxis.set_major_formatter(
        FormatStrFormatter("%.2fx")
    )

    axes.tick_params(
        axis="y",
        which="major",
        length=0,
        pad=10,
        labelsize=TICK_SIZE,
        colors=INK,
    )

    # -------------------------------------------------------------------------
    # Y label — first panel only
    # -------------------------------------------------------------------------

    if item is ratio_series[0]:
        axes.set_ylabel(
            "Ratio (Cap Weighted / Equal Weighted)",
            fontsize=TICK_SIZE,
            color=INK,
            labelpad=16,
        )

    # -------------------------------------------------------------------------
    # X limits
    # -------------------------------------------------------------------------

    axes.set_xlim(
        ratio.index[0],
        ratio.index[-1]
        + pd.Timedelta(days=10),
    )

    # -------------------------------------------------------------------------
    # Banner
    # -------------------------------------------------------------------------

    banner_left, banner_right, banner_top, banner_bottom = (
        geometry["banner"]
    )

    banner = patches.FancyBboxPatch(
        (
            banner_left,
            banner_top,
        ),
        banner_right - banner_left,
        banner_bottom - banner_top,
        boxstyle=(
            f"round,pad=0,"
            f"rounding_size={BANNER_RADIUS_PX}"
        ),
        mutation_aspect=1,
        linewidth=0,
        edgecolor="none",
        facecolor=item["colour"],
        transform=overlay.transData,
        zorder=11,
    )

    overlay.add_patch(banner)

    # Banner text uses the pixel coordinate directly.
    # Do not apply px_y() here because the overlay itself already has
    # top-left pixel coordinates through its inverted y-axis.
    overlay.text(
        (
            banner_left
            + banner_right
        )
        / 2,
        BANNER_TEXT_BASELINE_PX,
        item["label"],
        transform=overlay.transData,
        fontsize=BANNER_SIZE,
        fontweight="bold",
        color=BANNER_TEXT,
        ha="center",
        va="baseline",
        zorder=12,
    )


# =============================================================================
# Display
# =============================================================================

plt.show()