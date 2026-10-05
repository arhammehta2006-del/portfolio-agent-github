"""
risk.py - turns the user's answers into (1) a validated financial snapshot, (2) a list of goals,
and (3) a risk profile (appetite / capacity, blended into one score — see allocation.py for the
third angle, "required risk", which needs the funding engine and lives there to avoid a circular import).
Plain Python, no AI. Every rule here can be explained in the viva.
"""
from statistics import mean
import config as C

STATED_SCORE = {"Low": 3, "Moderate": 6, "High": 9}

# Three scenario questions: (question, [(answer text, score 2/6/10)])
QUIZ = [
    {
        "q": "Your investments fall 20% in one month because markets are nervous. What would you do?",
        "options": [
            ("Sell everything to stop further loss", 2),
            ("Do nothing and wait for recovery", 6),
            ("Invest more, prices are lower now", 10),
        ],
    },
    {
        "q": "Which 5-year outcome would you prefer?",
        "options": [
            ("Steady ~7% a year, almost no chance of loss", 2),
            ("~10% a year on average, with dips of up to 15%", 6),
            ("~13% a year on average, with dips of up to 30%", 10),
        ],
    },
    {
        "q": "Markets fall just before you need the money for a goal. How much does hitting the exact date matter?",
        "options": [
            ("Very important, I cannot delay", 2),
            ("I could delay by a year or so", 6),
            ("I am flexible, the date can move", 10),
        ],
    },
]


def bucket_for(years):
    """Label a goal by how far away it is."""
    if years <= C.SHORT_MAX_YEARS:
        return "Short"      # up to 3 years
    if years <= C.MEDIUM_MAX_YEARS:
        return "Medium"     # more than 3, up to 7 years
    return "Long"           # more than 7 years


# ------------------------------------------------------------------ financial snapshot (new)
def emergency_fund_target(inp):
    """
    Months of essential expenses recommended, then the rupee target.
    Base months come from employment stability; dependents add buffer; capped at a sensible max.
    This is a stated planning heuristic (see config.py), not a regulatory requirement.
    """
    base_months = C.EMERGENCY_MONTHS_BASE.get(inp.get("employment", "Salaried"), 6)
    months = base_months + C.EMERGENCY_MONTHS_PER_DEPENDENT * inp.get("dependents", 0)
    months = min(months, C.EMERGENCY_MONTHS_CAP)
    expenses = inp.get("monthly_expenses") or 0
    return months, months * expenses


def financial_snapshot(inp):
    """
    Pure derived numbers about the client's day-to-day finances. No risk scoring here —
    just the arithmetic that risk scoring and the financial-health scorecard both read from.
    Every field defaults to 0/False so a user who skips the financial-life step still gets a plan
    (just without affordability/emergency-fund checks, which are then shown as 'not assessed').
    """
    income = inp.get("monthly_income") or 0
    expenses = inp.get("monthly_expenses") or 0
    emi = inp.get("emi_total") or 0
    disposable = max(0.0, income - expenses - emi)
    savings_rate = (disposable / income) if income > 0 else None

    months, target = emergency_fund_target(inp)
    current = inp.get("emergency_savings") or 0
    shortfall = max(0.0, target - current)

    emi_ratio = (emi / income) if income > 0 else None
    high_emi_burden = emi_ratio is not None and emi_ratio > C.HIGH_EMI_BURDEN_RATIO
    high_interest_debt = bool(inp.get("emi_high_interest"))

    existing_equity = inp.get("existing_equity") or 0
    existing_other = inp.get("existing_other") or 0
    existing_total = existing_equity + existing_other
    existing_equity_share = (existing_equity / existing_total) if existing_total > 0 else None

    return {
        "income_known": income > 0,
        "monthly_income": income, "monthly_expenses": expenses, "emi_total": emi,
        "disposable_income": disposable, "savings_rate": savings_rate,
        "emergency_months_target": months, "emergency_target": target,
        "emergency_current": current, "emergency_shortfall": shortfall,
        "emi_ratio": emi_ratio, "high_emi_burden": high_emi_burden, "high_interest_debt": high_interest_debt,
        "existing_equity": existing_equity, "existing_other": existing_other,
        "existing_total": existing_total, "existing_equity_share": existing_equity_share,
        "has_health_insurance": bool(inp.get("has_health_insurance", True)),
        "has_life_insurance": bool(inp.get("has_life_insurance", True)),
        "sole_earner": bool(inp.get("sole_earner", False)),
        "liquidity_need": inp.get("liquidity_need", "Some"),
    }


# ------------------------------------------------------------------ validation
def validate(inp):
    """Return (errors, warnings). Errors block the plan; warnings are shown to the user."""
    errors, warnings = [], []
    age = inp.get("age", 0)
    if not (18 <= age <= 70):
        errors.append("Age should be between 18 and 70.")
    if inp.get("amount", 0) <= 0:
        errors.append("Please enter an investable amount greater than zero.")
    if inp.get("has_retirement"):
        ra = inp.get("retirement_age", 0)
        if ra <= age:
            errors.append("Retirement age must be greater than your current age.")
        elif ra - age > 45:
            warnings.append("Retirement is more than 45 years away, projections that far out are very uncertain.")
    for i, g in enumerate(inp.get("goals", []), start=1):
        name = str(g.get("name") or "").strip()
        years = g.get("years") or 0
        cost = g.get("cost") or 0
        if not name and (years or cost):
            errors.append(f"Goal {i}: please give it a name.")
        if name and years <= 0:
            errors.append(f"Goal '{name}': years to go must be more than 0.")
        if name and years > 50:
            errors.append(f"Goal '{name}': years to go looks too large (max 50).")
        if name and cost < 0:
            errors.append(f"Goal '{name}': cost cannot be negative.")
    if inp.get("mode", "").startswith("SIP") and 0 < inp.get("amount", 0) < 500:
        warnings.append("Most funds need at least Rs 500 per month for a SIP.")
    if not clean_goals(inp) and not inp.get("has_retirement"):
        warnings.append("No goals entered, we will treat your money as general long-term wealth building.")

    snap = financial_snapshot(inp)
    if snap["emergency_shortfall"] > 0 and snap["emergency_current"] == 0:
        warnings.append(f"You do not yet have an emergency fund. Based on your situation, aim for about "
                         f"{snap['emergency_months_target']:g} months of expenses in a liquid fund before taking market risk.")
    elif snap["emergency_shortfall"] > 0:
        warnings.append(f"Your emergency fund is short by about Rs {snap['emergency_shortfall']:,.0f} of its "
                         f"{snap['emergency_months_target']:g}-month target. We'll top this up before investing the rest.")

    if snap["income_known"]:
        sip_amount = inp.get("amount", 0) if inp.get("mode", "").startswith("SIP") else 0
        if sip_amount > snap["disposable_income"] * 1.0001:
            warnings.append(f"Your monthly SIP (Rs {sip_amount:,.0f}) is more than your disposable income "
                             f"(income minus expenses and EMIs, about Rs {snap['disposable_income']:,.0f}/month). "
                             "Consider a smaller SIP, or review your expenses/EMIs.")
        if snap["high_emi_burden"]:
            warnings.append(f"Your EMIs are about {snap['emi_ratio'] * 100:.0f}% of your income, "
                             "a high debt burden. If any of this debt carries a high interest rate, "
                             "consider repaying it before increasing investments.")
    if not snap["has_health_insurance"]:
        warnings.append("You reported no health insurance. Consider addressing this protection gap "
                         "alongside your investment plan, especially with dependents to support.")
    if inp.get("dependents", 0) > 0 and snap["sole_earner"] and not snap["has_life_insurance"]:
        warnings.append("You are the primary income earner with dependents but reported no life insurance. "
                         "Consider addressing this protection gap as part of your overall financial plan.")
    return errors, warnings


def clean_goals(inp):
    """Keep only filled-in goal rows."""
    out = []
    for g in inp.get("goals", []):
        name = str(g.get("name") or "").strip()
        years = float(g.get("years") or 0)
        cost = float(g.get("cost") or 0)
        if name and years > 0:
            out.append({
                "name": name, "years": years, "cost": cost,
                "priority": g.get("priority") or "Important",
                "inflation_category": g.get("inflation_category") or C.DEFAULT_GOAL_INFLATION_CATEGORY,
            })
    return out


def build_goals(inp):
    """
    Convert inputs into a list of goal dicts:
      name, years, kind ('goal' | 'open' | 'retirement'), today_value, target (future rupees or None),
      bucket, priority, inflation_category, inflation_rate.
    Costs are entered in today's rupees and inflated to the goal date using a goal-type-specific
    inflation assumption (education/healthcare/travel/housing inflate faster than general CPI — see config.py).
    """
    goals = []
    for g in clean_goals(inp):
        infl = C.GOAL_INFLATION.get(g["inflation_category"], C.GOAL_INFLATION[C.DEFAULT_GOAL_INFLATION_CATEGORY])
        if g["cost"] > 0:
            goals.append({
                "name": g["name"], "years": g["years"], "kind": "goal",
                "today_value": g["cost"],
                "target": g["cost"] * (1 + infl) ** g["years"],
                "priority": g["priority"], "inflation_category": g["inflation_category"], "inflation_rate": infl,
            })
        else:
            goals.append({"name": g["name"], "years": g["years"], "kind": "open",
                          "today_value": None, "target": None,
                          "priority": g["priority"], "inflation_category": g["inflation_category"], "inflation_rate": infl})
    if inp.get("has_retirement") and inp.get("retirement_age", 0) > inp.get("age", 0):
        yrs = inp["retirement_age"] - inp["age"]
        exp = inp.get("monthly_expenses") or 0
        infl = C.GOAL_INFLATION["General"]
        if exp > 0:
            today_val = exp * 12 * C.RETIREMENT_MULTIPLE
            target = today_val * (1 + infl) ** yrs
        else:
            today_val, target = None, None
        goals.append({"name": "Retirement", "years": float(yrs), "kind": "retirement",
                      "today_value": today_val, "target": target,
                      "priority": "Essential", "inflation_category": "General", "inflation_rate": infl})
    for g in goals:
        g["bucket"] = bucket_for(g["years"])
    return goals


def _weighted_horizon(goals):
    """Average years to goals, weighted by rupee size (goals with no size get the average weight)."""
    if not goals:
        return 10.0
    sized = [g["today_value"] for g in goals if g["today_value"]]
    fallback = mean(sized) if sized else 1.0
    weights = [g["today_value"] or fallback for g in goals]
    return sum(w * g["years"] for w, g in zip(weights, goals)) / sum(weights)


def risk_profile(inp, goals):
    """
    Risk score 1-10 = the LOWER of WILLINGNESS (how they feel) and CAPACITY (what they can afford).
    Standard practice: never take more risk than the person is comfortable with OR can afford.
      willingness = 40% stated appetite + 60% scenario-question answers (behaviour beats labels)
      capacity    = average of age, dependents, money-weighted horizon, emergency-fund coverage, employment stability

    This is the APPETITE/CAPACITY half of the picture (item 18 in the spec). The third angle,
    REQUIRED risk (how much return the goals actually need), depends on the funding engine and is
    computed in allocation.py's build_plan() to avoid a circular import — it is merged into the
    final notes/explanation there, not into this score, so the already-validated appetite/capacity
    logic below is never silently overridden by it.
    """
    stated = STATED_SCORE[inp["stated_risk"]]
    quiz = mean(inp["quiz"])
    willingness = 0.4 * stated + 0.6 * quiz

    age = inp["age"]
    age_pts = 9 if age <= 30 else 7 if age <= 40 else 5 if age <= 50 else 3 if age <= 60 else 2
    dep = inp.get("dependents", 0)
    dep_pts = 9 if dep == 0 else 7 if dep == 1 else 5 if dep == 2 else 3
    horizon = _weighted_horizon(goals)
    horizon_pts = max(1.0, min(10.0, 1 + 0.6 * horizon))

    snap = financial_snapshot(inp)
    coverage = min(1.0, snap["emergency_current"] / snap["emergency_target"]) if snap["emergency_target"] > 0 else 1.0
    emergency_pts = 2 + 7 * coverage   # 2 (no buffer) .. 9 (fully funded)

    employment_pts = C.EMPLOYMENT_CAPACITY_PTS.get(inp.get("employment", "Salaried"), 5)
    if snap["high_emi_burden"]:
        employment_pts = max(1, employment_pts - 2)   # heavy EMI load reduces how much risk you can really afford

    capacity = mean([age_pts, dep_pts, horizon_pts, emergency_pts, employment_pts])

    score = round(max(1.0, min(10.0, min(willingness, capacity))), 1)
    label = ("Conservative" if score < C.CONSERVATIVE_BELOW
             else "Aggressive" if score >= C.AGGRESSIVE_FROM else "Moderate")
    return {
        "score": score, "label": label,
        "willingness": round(willingness, 1), "capacity": round(capacity, 1),
        "stated": stated, "quiz": round(quiz, 1),
        "components": {"age": age_pts, "dependents": dep_pts, "horizon": round(horizon_pts, 1),
                       "emergency_fund": round(emergency_pts, 1), "employment": employment_pts},
        "weighted_horizon_years": round(horizon, 1),
    }
