"""
config.py - all the tunable numbers in ONE place.
Change a number here and the whole app follows, so every choice is easy to explain in the viva.
"""
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- The five asset classes the portfolios are built from ----
ASSETS = ["Liquid Fund", "Debt Fund", "Gold", "Large-cap Equity", "Mid-cap Equity"]

# ---- Return / risk assumptions -------------------------------------------------
# Loaded from data/assumptions.csv. Replace the placeholder values with figures you
# compute from real historical data (see build_assumptions.py).
_DEFAULTS = {
    "Liquid Fund": (0.060, 0.010),
    "Debt Fund": (0.070, 0.030),
    "Gold": (0.080, 0.140),
    "Large-cap Equity": (0.120, 0.170),
    "Mid-cap Equity": (0.140, 0.220),
}


def load_assumptions():
    """Return (dict asset -> (expected_return, volatility), source_note)."""
    path = os.path.join(BASE_DIR, "data", "assumptions.csv")
    try:
        df = pd.read_csv(path)
        out = {r["asset"]: (float(r["expected_return"]), float(r["volatility"])) for _, r in df.iterrows()}
        for a in ASSETS:
            if a not in out:
                raise ValueError(f"{a} missing in assumptions.csv")
        note = "Loaded from data/assumptions.csv"
        if df["source"].astype(str).str.contains("PLACEHOLDER").any():
            note += " (contains PLACEHOLDER values - replace with your own historical data)"
        return out, note
    except Exception as e:  # never crash the demo because of a data file
        return dict(_DEFAULTS), f"Using built-in placeholder assumptions ({e})"


ASSUMPTIONS, ASSUMPTIONS_NOTE = load_assumptions()

# Rough correlations between asset classes (placeholder - replace with data-based values if you can).
#            Liquid Debt  Gold  LC    MC
CORR = [
    [1.00, 0.50, 0.00, 0.00, 0.00],  # Liquid
    [0.50, 1.00, 0.10, 0.10, 0.05],  # Debt
    [0.00, 0.10, 1.00, 0.05, 0.05],  # Gold
    [0.00, 0.10, 0.05, 1.00, 0.85],  # Large-cap
    [0.00, 0.05, 0.05, 0.85, 1.00],  # Mid-cap
]

# ---- Planning assumptions ------------------------------------------------------
INFLATION = 0.06            # yearly rise in costs (goal costs are entered in today's rupees)
PLANNING_MARGIN = 0.01      # we plan with returns 1 percentage point lower than expected (prudence)
RETIREMENT_MULTIPLE = 25    # retirement corpus = 25 x yearly expenses (the "4% rule")
DEFAULT_WEALTH_YEARS = 15   # horizon used for surplus money with no goal attached
N_SIMS = 2000               # number of simulated futures for the probability estimates
SEED = 42                   # fixed seed -> same inputs always give the same numbers (good for demos)

# ---- Horizon buckets (years) ----------------------------------------------------
CAPITAL_PROTECTION_YEARS = 1   # goals this close are held 100% in liquid funds
SHORT_MAX_YEARS = 3            # up to 3 years = short term
MEDIUM_MAX_YEARS = 7           # more than 3 up to 7 years = medium term, above 7 = long term

# ---- Risk-score labels -----------------------------------------------------------
CONSERVATIVE_BELOW = 4.0
AGGRESSIVE_FROM = 7.0
PROFILES = ["Conservative", "Moderate", "Aggressive"]

# =========================================================================
# ADDITIONS BELOW THIS LINE support the expanded financial-profile,
# emergency-fund, debt, goal-priority, step-up-SIP and risk-metric features.
# Every number here is a stated, documented assumption — see the
# "Assumptions & Methodology" panel the app renders from this file.
# =========================================================================

# ---- Goal priority tiers (used to decide funding order under a budget constraint) ----
PRIORITIES = ["Essential", "Important", "Aspirational"]
PRIORITY_ORDER = {p: i for i, p in enumerate(PRIORITIES)}   # Essential funded first

# ---- Goal-type-specific inflation (item 23: different expenses inflate differently) ----
# PLACEHOLDER figures — replace with RBI/CPI sub-index data if available for your submission.
GOAL_INFLATION = {
    "General": 0.06,
    "Education": 0.08,
    "Healthcare": 0.09,
    "Travel": 0.06,
    "Housing": 0.07,
}
DEFAULT_GOAL_INFLATION_CATEGORY = "General"

# ---- Employment types and how they affect risk CAPACITY and emergency-fund months ----
EMPLOYMENT_TYPES = ["Salaried", "Self-employed / business owner", "Freelancer / professional", "Student", "Retired", "Other"]

# Months of essential expenses recommended in the emergency fund, by employment stability.
# These are PLACEHOLDER planning norms (commonly cited retail financial-planning heuristics),
# not a regulatory requirement — stated explicitly so the assumption is visible, not silent.
EMERGENCY_MONTHS_BASE = {
    "Salaried": 4,
    "Self-employed / business owner": 8,
    "Freelancer / professional": 8,
    "Student": 3,
    "Retired": 6,
    "Other": 6,
}
EMERGENCY_MONTHS_PER_DEPENDENT = 1     # +1 month of buffer per financial dependent
EMERGENCY_MONTHS_CAP = 12              # don't ask for more than a year's buffer

# Employment-type effect on risk CAPACITY points (1-10 scale, same scale as age/dependents/etc in risk.py).
# Stable, predictable income supports more capacity for market risk; irregular or no income reduces it.
EMPLOYMENT_CAPACITY_PTS = {
    "Salaried": 7,
    "Self-employed / business owner": 5,
    "Freelancer / professional": 4,
    "Student": 5,
    "Retired": 3,
    "Other": 5,
}

# ---- Debt / affordability checks ----
HIGH_EMI_BURDEN_RATIO = 0.40     # EMIs above this share of monthly income are flagged as a high debt burden
HIGH_INTEREST_DEBT_RATE = 0.12   # loans costlier than this are flagged as "consider repaying before investing more"

# ---- Existing-portfolio awareness (item 19) ----
# How much new-money allocation is pulled toward asset classes the client is currently underweight in,
# when they report an already-concentrated existing portfolio. 0 = ignore existing holdings, 1 = fully offset them.
EXISTING_PORTFOLIO_OFFSET = 0.5

# ---- Risk metrics (item 14) ----
RISK_FREE_RATE = 0.065   # PLACEHOLDER — approx short-term G-Sec/liquid-fund yield, for the Sharpe ratio calc only

# ---- Step-up SIP default ----
DEFAULT_SIP_STEP_UP = 0.0   # 0% unless the user says otherwise
