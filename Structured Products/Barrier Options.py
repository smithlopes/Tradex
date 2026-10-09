import QuantLib as ql
import numpy as np
import pandas as pd
from mscidata import msci


# ================================================================
# USER SETTINGS
# ================================================================

INDEX_CODE = "990100"
INDEX_NAME = "MSCI World"
RETURN_TYPE = "NETR"
CURRENCY = "USD"

# Historical volatility lookback
VOL_LOOKBACK_YEARS = 3

# ------------------------------------------------
# IMPLIED VOLATILITY
# ------------------------------------------------
# None = use historical volatility
#
# Example:
# IMPLIED_VOLATILITY = 0.15
# means 15.00% implied volatility
# ------------------------------------------------
IMPLIED_VOLATILITY = None

# Option settings
OPTION_TYPE = ql.Option.Call
MATURITY_YEARS = 1

# Strike as a multiple of spot
STRIKE_FACTOR = 1.00

# Double barrier levels as multiples of spot
LOWER_BARRIER_FACTOR = 0.80
UPPER_BARRIER_FACTOR = 1.20

# Rebate paid if barrier is hit
REBATE = 0.0

# Market assumptions
RISK_FREE_RATE = 0.04
DIVIDEND_YIELD = 0.00

# Trading days used for annualisation
TRADING_DAYS = 252

# Numerical Greek bumps
SPOT_BUMP = 0.01       # 1% spot bump
VOL_BUMP = 0.01        # 1 percentage-point volatility bump


# ================================================================
# GET MSCI DATA
# ================================================================

today = pd.Timestamp.today().normalize()

start_date = (
    today - pd.DateOffset(years=VOL_LOOKBACK_YEARS)
)

data = msci.get_levels(
    INDEX_CODE,
    start_date.strftime("%Y-%m-%d"),
    today.strftime("%Y-%m-%d"),
    RETURN_TYPE
)

# ------------------------------------------------
# Validate returned data
# ------------------------------------------------

if data is None or len(data) == 0:
    raise ValueError(
        "MSCI returned no data. Check the index code and date range."
    )

if not isinstance(data, pd.DataFrame):
    data = pd.DataFrame(data)

required_columns = {
    "INDEX_CODE",
    "DATE",
    "LEVEL"
}

missing_columns = required_columns - set(data.columns)

if missing_columns:
    raise ValueError(
        f"MSCI data is missing expected columns: "
        f"{sorted(missing_columns)}\n"
        f"Returned columns: {list(data.columns)}"
    )

# ------------------------------------------------
# Extract the actual index levels
# ------------------------------------------------

data["DATE"] = pd.to_datetime(data["DATE"])

data["LEVEL"] = pd.to_numeric(
    data["LEVEL"],
    errors="coerce"
)

data = data.dropna(
    subset=["DATE", "LEVEL"]
)

data = data.sort_values("DATE")

levels = data["LEVEL"].astype(float)

# Make sure we actually have usable data
if len(levels) < 30:
    raise ValueError(
        f"Only {len(levels)} valid MSCI observations were returned."
    )

if levels.iloc[-1] <= 0:
    raise ValueError(
        f"Invalid latest MSCI level: {levels.iloc[-1]}"
    )

# Latest MSCI index level = spot
spot = float(levels.iloc[-1])


# ================================================================
# HISTORICAL VOLATILITY
# ================================================================

log_returns = np.log(
    levels / levels.shift(1)
).dropna()

historical_volatility = (
    log_returns.std(ddof=1)
    * np.sqrt(TRADING_DAYS)
)

# ------------------------------------------------
# Select volatility
# ------------------------------------------------

if IMPLIED_VOLATILITY is None:

    volatility = historical_volatility
    volatility_source = "Historical"

else:

    if IMPLIED_VOLATILITY <= 0:
        raise ValueError(
            "IMPLIED_VOLATILITY must be greater than zero."
        )

    volatility = IMPLIED_VOLATILITY
    volatility_source = "Implied"


# ================================================================
# QUANTLIB SETUP
# ================================================================

calendar = ql.TARGET()

day_counter = ql.Actual365Fixed()

evaluation_date = ql.Date(
    today.day,
    today.month,
    today.year
)

ql.Settings.instance().evaluationDate = evaluation_date

maturity_date = (
    evaluation_date
    + ql.Period(MATURITY_YEARS, ql.Years)
)


# ================================================================
# OPTION LEVELS
# ================================================================

strike = spot * STRIKE_FACTOR

lower_barrier = (
    spot * LOWER_BARRIER_FACTOR
)

upper_barrier = (
    spot * UPPER_BARRIER_FACTOR
)


# ================================================================
# PROCESS CREATION
# ================================================================

def create_process(
    spot_value,
    volatility_value
):

    spot_handle = ql.QuoteHandle(
        ql.SimpleQuote(spot_value)
    )

    risk_free_curve = ql.YieldTermStructureHandle(
        ql.FlatForward(
            evaluation_date,
            RISK_FREE_RATE,
            day_counter
        )
    )

    dividend_curve = ql.YieldTermStructureHandle(
        ql.FlatForward(
            evaluation_date,
            DIVIDEND_YIELD,
            day_counter
        )
    )

    volatility_curve = ql.BlackVolTermStructureHandle(
        ql.BlackConstantVol(
            evaluation_date,
            calendar,
            volatility_value,
            day_counter
        )
    )

    process = ql.BlackScholesMertonProcess(
        spot_handle,
        dividend_curve,
        risk_free_curve,
        volatility_curve
    )

    return process


# ================================================================
# VANILLA OPTION PRICER
# ================================================================

def price_vanilla(
    spot_value,
    volatility_value
):

    process = create_process(
        spot_value,
        volatility_value
    )

    payoff = ql.PlainVanillaPayoff(
        OPTION_TYPE,
        strike
    )

    exercise = ql.EuropeanExercise(
        maturity_date
    )

    option = ql.VanillaOption(
        payoff,
        exercise
    )

    engine = ql.AnalyticEuropeanEngine(
        process
    )

    option.setPricingEngine(engine)

    return option.NPV()


# ================================================================
# DOUBLE BARRIER OPTION PRICER
# ================================================================

def price_double_barrier(
    spot_value,
    volatility_value
):

    process = create_process(
        spot_value,
        volatility_value
    )

    payoff = ql.PlainVanillaPayoff(
        OPTION_TYPE,
        strike
    )

    exercise = ql.EuropeanExercise(
        maturity_date
    )

    option = ql.DoubleBarrierOption(
        ql.DoubleBarrier.KnockOut,
        lower_barrier,
        upper_barrier,
        REBATE,
        payoff,
        exercise
    )

    engine = ql.AnalyticDoubleBarrierEngine(
        process
    )

    option.setPricingEngine(engine)

    return option.NPV()


# ================================================================
# BASE OPTION VALUES
# ================================================================

vanilla_value = price_vanilla(
    spot,
    volatility
)

barrier_value = price_double_barrier(
    spot,
    volatility
)


# ================================================================
# VANILLA GREEKS
# ================================================================

# ------------------------------------------------
# DELTA
# ------------------------------------------------

vanilla_spot_up = spot * (1 + SPOT_BUMP)

vanilla_spot_down = spot * (1 - SPOT_BUMP)

vanilla_price_up = price_vanilla(
    vanilla_spot_up,
    volatility
)

vanilla_price_down = price_vanilla(
    vanilla_spot_down,
    volatility
)

vanilla_delta = (
    vanilla_price_up
    - vanilla_price_down
) / (
    vanilla_spot_up
    - vanilla_spot_down
)


# ------------------------------------------------
# GAMMA
# ------------------------------------------------

vanilla_gamma = (
    vanilla_price_up
    - 2 * vanilla_value
    + vanilla_price_down
) / (
    (spot * SPOT_BUMP) ** 2
)


# ------------------------------------------------
# VEGA
# ------------------------------------------------

vanilla_vol_up = (
    volatility + VOL_BUMP
)

vanilla_vol_down = max(
    volatility - VOL_BUMP,
    0.0001
)

vanilla_price_vol_up = price_vanilla(
    spot,
    vanilla_vol_up
)

vanilla_price_vol_down = price_vanilla(
    spot,
    vanilla_vol_down
)

# Vega per 1 percentage-point move in volatility
vanilla_vega = (
    vanilla_price_vol_up
    - vanilla_price_vol_down
) / (
    vanilla_vol_up
    - vanilla_vol_down
) * 0.01


# ------------------------------------------------
# THETA
# ------------------------------------------------

ql.Settings.instance().evaluationDate = (
    evaluation_date + ql.Period(1, ql.Days)
)

vanilla_value_next_day = price_vanilla(
    spot,
    volatility
)

ql.Settings.instance().evaluationDate = evaluation_date

vanilla_theta = (
    vanilla_value_next_day
    - vanilla_value
)


# ================================================================
# DOUBLE BARRIER GREEKS
# ================================================================

# ------------------------------------------------
# DELTA
# ------------------------------------------------

barrier_spot_up = (
    spot * (1 + SPOT_BUMP)
)

barrier_spot_down = (
    spot * (1 - SPOT_BUMP)
)

barrier_price_up = price_double_barrier(
    barrier_spot_up,
    volatility
)

barrier_price_down = price_double_barrier(
    barrier_spot_down,
    volatility
)

barrier_delta = (
    barrier_price_up
    - barrier_price_down
) / (
    barrier_spot_up
    - barrier_spot_down
)


# ------------------------------------------------
# GAMMA
# ------------------------------------------------

barrier_gamma = (
    barrier_price_up
    - 2 * barrier_value
    + barrier_price_down
) / (
    (spot * SPOT_BUMP) ** 2
)


# ------------------------------------------------
# VEGA
# ------------------------------------------------

barrier_vol_up = (
    volatility + VOL_BUMP
)

barrier_vol_down = max(
    volatility - VOL_BUMP,
    0.0001
)

barrier_price_vol_up = price_double_barrier(
    spot,
    barrier_vol_up
)

barrier_price_vol_down = price_double_barrier(
    spot,
    barrier_vol_down
)

# Vega per 1 percentage-point move in volatility
barrier_vega = (
    barrier_price_vol_up
    - barrier_price_vol_down
) / (
    barrier_vol_up
    - barrier_vol_down
) * 0.01


# ------------------------------------------------
# THETA
# ------------------------------------------------

ql.Settings.instance().evaluationDate = (
    evaluation_date + ql.Period(1, ql.Days)
)

barrier_value_next_day = price_double_barrier(
    spot,
    volatility
)

ql.Settings.instance().evaluationDate = evaluation_date

barrier_theta = (
    barrier_value_next_day
    - barrier_value
)


# ================================================================
# OUTPUT
# ================================================================

print("=" * 65)
print("MSCI WORLD OPTION PRICING")
print("=" * 65)

print(f"Index               : {INDEX_NAME}")
print(f"Index code          : {INDEX_CODE}")
print(f"Return type         : {RETURN_TYPE}")
print(f"Currency            : {CURRENCY}")

print("-" * 65)

print(f"Spot                : {spot:.2f}")
print(f"Historical vol      : {historical_volatility:.2%}")

print(
    f"Volatility used     : "
    f"{volatility:.2%} ({volatility_source})"
)

print(f"Risk-free rate      : {RISK_FREE_RATE:.2%}")
print(f"Dividend yield      : {DIVIDEND_YIELD:.2%}")

print("-" * 65)

print(
    f"Option type         : "
    f"{'Call' if OPTION_TYPE == ql.Option.Call else 'Put'}"
)

print(
    f"Maturity            : "
    f"{MATURITY_YEARS} year(s)"
)

print("-" * 65)

print(
    f"Strike factor       : "
    f"{STRIKE_FACTOR:.2f}x"
)

print(f"Strike              : {strike:.2f}")

print("-" * 65)

print("VANILLA EUROPEAN OPTION")
print("-" * 65)

print(
    f"OPTION VALUE        : "
    f"{vanilla_value:.4f}"
)

print(
    f"Delta               : "
    f"{vanilla_delta:.6f}"
)

print(
    f"Gamma               : "
    f"{vanilla_gamma:.8f}"
)

print(
    f"Vega (1% vol)       : "
    f"{vanilla_vega:.6f}"
)

print(
    f"Theta (per day)     : "
    f"{vanilla_theta:.6f}"
)

print("-" * 65)

print("DOUBLE BARRIER OPTION")
print("-" * 65)

print(
    "Barrier type        : "
    "Double Knock-Out"
)

print(
    f"Lower barrier factor: "
    f"{LOWER_BARRIER_FACTOR:.2f}x"
)

print(
    f"Lower barrier       : "
    f"{lower_barrier:.2f}"
)

print(
    f"Upper barrier factor: "
    f"{UPPER_BARRIER_FACTOR:.2f}x"
)

print(
    f"Upper barrier       : "
    f"{upper_barrier:.2f}"
)

print(
    f"Rebate              : "
    f"{REBATE:.2f}"
)

print("-" * 65)

print(
    f"OPTION VALUE        : "
    f"{barrier_value:.4f}"
)

print(
    f"Delta               : "
    f"{barrier_delta:.6f}"
)

print(
    f"Gamma               : "
    f"{barrier_gamma:.8f}"
)

print(
    f"Vega (1% vol)       : "
    f"{barrier_vega:.6f}"
)

print(
    f"Theta (per day)     : "
    f"{barrier_theta:.6f}"
)

print("-" * 65)

print("BARRIER EFFECT")
print("-" * 65)

if vanilla_value != 0:

    print(
        f"Barrier / Vanilla   : "
        f"{barrier_value / vanilla_value:.2%}"
    )

    print(
        f"Value lost to bars  : "
        f"{vanilla_value - barrier_value:.4f}"
    )

else:

    print("Barrier / Vanilla   : N/A")
    print("Value lost to bars  : N/A")

print("=" * 65)