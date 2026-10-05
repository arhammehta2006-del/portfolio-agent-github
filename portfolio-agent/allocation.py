"""
allocation.py - the calculation engine (plain Python + numpy, NO AI).
Steps:  goals -> emergency-fund top-up -> per-goal allocation -> funding split (by priority) ->
        3 portfolio options (existing-portfolio-aware) -> simulated outcomes -> financial health.
The AI layer only ever explains numbers produced here.
"""
import numpy as np
import config as C
import risk as R

# ---- Allocation rules: horizon bucket x risk profile -> % in [Liquid, Debt, Gold, Large-cap, Mid-cap] ----
ALLOC = {
    "Short": {   # up to 3 years: protect the money
        "Conservative": [70, 30, 0, 0, 0],
        "Moderate":     [55, 35, 5, 5, 0],
        "Aggressive":   [40, 40, 5, 15, 0],
    },
    "Medium": {  # more than 3, up to 7 years: mix of safety and growth
        "Conservative": [10, 55, 10, 25, 0],
        "Moderate":     [5, 35, 10, 40, 10],
        "Aggressive":   [0, 20, 10, 45, 25],
    },
    "Long": {    # more than 7 years: time to ride out market ups and downs
        "Conservative": [0, 40, 10, 40, 10],
        "Moderate":     [0, 20, 10, 45, 25],
        "Aggressive":   [0, 5, 5, 50, 40],
    },
}


def goal_allocation(years, profile):
    """Weights (fractions, same order as C.ASSETS) for a goal `years` away under a risk profile."""
    if years <= C.CAPITAL_PROTECTION_YEARS:
        return [1.0, 0.0, 0.0, 0.0, 0.0]        # goal is very close: 100% liquid
    row = ALLOC[R.bucket_for(years)][profile]
    return [x / 100 for x in row]


def alloc_dict(weights):
    return {a: float(round(float(w) * 100, 1)) for a, w in zip(C.ASSETS, weights)}


def equity_share(weights):
    return (weights[3] + weights[4]) * 100


def tilt_for_existing(weights, existing_equity_share):
    """
    Item 19: don't blindly add more equity if the client's EXISTING holdings are already
    equity-heavy (or the reverse). Shifts new-money equity weight toward/away from debt+liquid,
    proportionally to how far the existing portfolio sits from this mix's own equity target.
    Applied only to the blended overall view (not each goal's own protective allocation), so a
    near-term goal's capital-protection rule is never weakened by this adjustment.
    """
    if existing_equity_share is None:
        return weights
    w = list(weights)
    target_equity = w[3] + w[4]
    diff = existing_equity_share - target_equity   # positive = already overweight equity vs. this target
    if abs(diff) < 1e-6 or target_equity <= 0:
        return w
    shift = C.EXISTING_PORTFOLIO_OFFSET * diff * target_equity
    shift = max(-target_equity, min(target_equity, shift))
    w[3] -= shift * (w[3] / target_equity)
    w[4] -= shift * (w[4] / target_equity)
    w[1] += shift          # absorb into debt first
    if w[1] < 0:
        w[0] += w[1]        # spill any remainder into liquid
        w[1] = 0.0
    w = [max(0.0, x) for x in w]
    s = sum(w)
    return [x / s for x in w] if s > 0 else w


# ---- Portfolio maths ---------------------------------------------------------
_MU = np.array([C.ASSUMPTIONS[a][0] for a in C.ASSETS])
_SD = np.array([C.ASSUMPTIONS[a][1] for a in C.ASSETS])
_COV = np.outer(_SD, _SD) * np.array(C.CORR)


def portfolio_stats(w):
    """Expected yearly return and volatility (typical ups and downs) of a mix."""
    w = np.array(w, dtype=float)
    return float(w @ _MU), float(np.sqrt(w @ _COV @ w))


def sharpe_ratio(mu, sd):
    """Return per unit of risk, relative to a risk-free rate (config.RISK_FREE_RATE). Item 14."""
    return float((mu - C.RISK_FREE_RATE) / sd) if sd > 1e-9 else 0.0


def planning_return(w):
    """Prudent return used to size the required saving: expected - volatility drag - safety margin."""
    mu, sd = portfolio_stats(w)
    return max(0.0, mu - 0.5 * sd ** 2 - C.PLANNING_MARGIN)


def _sip_future_value(c0, months, rm, step_up):
    """Explicit month-by-month future value of a SIP whose contribution grows `step_up` each year."""
    v = 0.0
    for t in range(months):
        year_idx = t // 12
        v += c0 * (1 + step_up) ** year_idx
        v *= (1 + rm)
    return v


def required_funding(target, years, g, sip, step_up=0.0):
    """Monthly SIP (first month's amount, if step_up>0) or lumpsum today needed to reach `target`."""
    if sip:
        months = max(1, round(years * 12))
        rm = (1 + g) ** (1 / 12) - 1
        if step_up <= 1e-9:
            return target / months if rm < 1e-9 else target * rm / ((1 + rm) ** months - 1)
        lo, hi = 0.0, max(target, 1.0)
        for _ in range(60):      # binary search: ~60 iterations is far more precision than needed
            mid = (lo + hi) / 2
            fv = _sip_future_value(mid, months, rm, step_up)
            if fv < target:
                lo = mid
            else:
                hi = mid
        return hi
    return target / (1 + g) ** years


def required_return(amount, target, years, sip, step_up=0.0):
    """
    Inverse of required_funding: given a fixed amount/SIP, what annual return would be needed to
    reach `target` in `years`? Used for the 'Required Risk' angle (item 18) — a single, documented
    simplification using the client's money-weighted horizon rather than solving goal-by-goal,
    so it never needs the funding split (which itself depends on a chosen profile).
    """
    if amount <= 0 or target <= 0 or years <= 0:
        return 0.0
    lo, hi = -0.5, 0.5
    for _ in range(60):
        mid = (lo + hi) / 2
        rm = (1 + mid) ** (1 / 12) - 1 if sip else None
        fv = _sip_future_value(amount, max(1, round(years * 12)), rm, step_up) if sip else amount * (1 + mid) ** years
        if fv < target:
            lo = mid
        else:
            hi = mid
    return hi


def simulate(z, mu, sd, funding, sip, target, step_up=0.0):
    """
    Monte Carlo: run many possible futures. z is a (months x sims) array of standard normal shocks,
    re-used across options so the three portfolios are compared on the SAME simulated markets.
    """
    n, sims = z.shape
    if funding <= 0:
        return {"median": 0.0, "p10": 0.0, "p90": 0.0, "prob": 0.0 if target else None,
                "median_pct": 0.0 if target else None}
    v = np.zeros(sims) if sip else np.full(sims, float(funding))
    mm, sm = mu / 12, sd / np.sqrt(12)
    for t in range(n):
        if sip:
            year_idx = t // 12
            v = v + funding * (1 + step_up) ** year_idx
        v = v * (1 + np.maximum(mm + sm * z[t], -0.95))
    return {
        "median": float(np.median(v)), "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90)),
        "prob": float((v >= target).mean()) if target else None,
        "median_pct": float(np.median(v) / target) if target else None,   # typical outcome as share of the target
    }


# ---- Financial health scorecard (item 39) ----------------------------------------
def financial_health(inp, snap, goals):
    """Labelled scorecard. Any input the user skipped comes back as 'Not assessed', never guessed."""
    card = {}

    if snap["emergency_target"] <= 0:
        card["Emergency Fund"] = "Not assessed"
    elif snap["emergency_shortfall"] <= 0:
        card["Emergency Fund"] = "Good"
    elif snap["emergency_current"] / snap["emergency_target"] >= 0.5:
        card["Emergency Fund"] = "Needs Attention"
    else:
        card["Emergency Fund"] = "At Risk"

    if snap["emi_ratio"] is None:
        card["Debt Level"] = "Not assessed"
    elif snap["high_emi_burden"]:
        card["Debt Level"] = "Needs Attention"
    else:
        card["Debt Level"] = "Healthy"

    if snap["savings_rate"] is None:
        card["Savings Rate"] = "Not assessed"
    elif snap["savings_rate"] >= 0.3:
        card["Savings Rate"] = "Strong"
    elif snap["savings_rate"] >= 0.15:
        card["Savings Rate"] = "Good"
    else:
        card["Savings Rate"] = "Needs Attention"

    ret = next((g for g in goals if g["kind"] == "retirement"), None)
    if ret is None:
        card["Retirement Planning"] = "Not assessed"
    elif ret.get("funded_ratio") is None:
        card["Retirement Planning"] = "On Track"
    elif ret["funded_ratio"] >= 0.95:
        card["Retirement Planning"] = "On Track"
    elif ret["funded_ratio"] >= 0.7:
        card["Retirement Planning"] = "Behind Target"
    else:
        card["Retirement Planning"] = "Significantly Behind"

    needs_life_cover = inp.get("dependents", 0) > 0 and snap["sole_earner"] and not snap["has_life_insurance"]
    if not snap["has_health_insurance"] or needs_life_cover:
        card["Insurance Protection"] = "Needs Review"
    else:
        card["Insurance Protection"] = "Good"

    return card


# ---- The full plan ---------------------------------------------------------------
def build_plan(inp, override=None, amount_mult=1.0):
    """
    inp: validated inputs dict. override: force a risk profile (what-if). amount_mult: scale the money (what-if).
    Returns one big dict that both the UI and the AI layer read from.
    """
    sip = inp["mode"].startswith("SIP")
    step_up = float(inp.get("sip_step_up") or 0.0) if sip else 0.0
    goals = R.build_goals(inp)
    prof = R.risk_profile(inp, goals)
    rec = override or prof["label"]
    amount = inp["amount"] * amount_mult
    snap = R.financial_snapshot(inp)

    # 1) plan returns from the RECOMMENDED profile's allocation for each goal
    for g in goals:
        w = goal_allocation(g["years"], rec)
        g["plan_return"] = planning_return(w)

    # 2) emergency-fund top-up comes out of the investable amount FIRST (item 3) — it is tracked
    #    separately from the goals list so the existing per-goal simulation loop below is untouched.
    avail = amount
    topup_needed = snap["emergency_shortfall"]
    topup = min(topup_needed, avail) if topup_needed > 0 else 0.0
    avail -= topup
    emergency_topup = {
        "required": topup_needed, "funding": topup,
        "funded_ratio": (topup / topup_needed) if topup_needed > 0 else 1.0,
    }

    # 3) split the remaining money: fund goals by PRIORITY first, then nearest goal within a tier (item 11)
    avail_after_emergency = avail
    targeted = [x for x in goals if x["target"] is not None]
    targeted.sort(key=lambda x: (C.PRIORITY_ORDER.get(x.get("priority", "Important"), 1), x["years"]))
    for g in targeted:
        g["required"] = required_funding(g["target"], g["years"], g["plan_return"], sip, step_up)
        g["funding"] = min(g["required"], avail)
        g["funded_ratio"] = g["funding"] / g["required"] if g["required"] > 0 else 1.0
        avail -= g["funding"]
    for g in goals:
        if g["target"] is None:
            g.update(required=None, funding=0.0, funded_ratio=None)

    # 4) anything left over goes to open-ended goals, or to an automatic wealth-building bucket
    surplus = max(avail, 0.0)
    if surplus > 0.5:
        open_goals = [g for g in goals if g["target"] is None]
        if open_goals:
            for g in open_goals:
                g["funding"] += surplus / len(open_goals)
        else:
            longest = max([g["years"] for g in goals], default=0)
            yrs = longest if longest >= C.MEDIUM_MAX_YEARS else float(C.DEFAULT_WEALTH_YEARS)
            goals.append({"name": "Long-term wealth building (surplus)", "years": yrs, "kind": "wealth",
                          "today_value": None, "target": None, "bucket": R.bucket_for(yrs),
                          "priority": "Aspirational", "inflation_category": "General", "inflation_rate": C.GOAL_INFLATION["General"],
                          "required": None, "funding": surplus, "funded_ratio": None, "plan_return": 0.0})

    # 5) build the three portfolio options and simulate every goal under each
    z_list = []
    for i, g in enumerate(goals):
        rng = np.random.default_rng(C.SEED + i)
        z_list.append(rng.standard_normal((max(1, round(g["years"] * 12)), C.N_SIMS)))

    options = {}
    for name in C.PROFILES:
        rows, agg = [], np.zeros(len(C.ASSETS))
        for g, z in zip(goals, z_list):
            w = goal_allocation(g["years"], name)
            mu, sd = portfolio_stats(w)
            res = simulate(z, mu, sd, g["funding"], sip, g["target"], step_up)
            rows.append({"goal": g["name"], "alloc": alloc_dict(w), "equity_pct": round(equity_share(w), 1),
                         "exp_return": mu, "volatility": sd, **res})
            agg += g["funding"] * np.array(w)
        if agg.sum() > 0:
            overall = agg / agg.sum()
        else:
            overall = np.mean([goal_allocation(g["years"], name) for g in goals], axis=0) if goals else np.array([0, 0, 0, 0.5, 0.5])
        overall = np.array(tilt_for_existing(list(overall), snap["existing_equity_share"]))
        mu, sd = portfolio_stats(overall)
        options[name] = {
            "overall_alloc": alloc_dict(overall), "exp_return": mu, "volatility": sd,
            "bad_year": mu - 1.645 * sd,          # roughly a 1-in-20 bad year
            "stress_decline": mu - 2.0 * sd,      # a rarer, sharper stress scenario (item 14/24) — an analytical
                                                    # estimate from the assumed volatility, not a historical drawdown
            "sharpe": round(sharpe_ratio(mu, sd), 2),
            "goals": rows,
        }

    # 6) required risk (item 18's third angle) — a single, documented simplification: what annual
    #    return would the money-weighted horizon + total investable amount need to hit the
    #    money-weighted total of all dated goals? Compared against the Conservative/Moderate/
    #    Aggressive planning returns at that horizon's bucket to get a label. Shown for awareness;
    #    it does NOT override the willingness/capacity-driven recommendation above.
    weighted_horizon = prof["weighted_horizon_years"]
    total_target = sum(g["target"] for g in goals if g.get("target"))
    req_g = required_return(amount, total_target, weighted_horizon, sip, step_up) if total_target > 0 else 0.0
    bucket_here = R.bucket_for(weighted_horizon)
    cons_pr = planning_return(goal_allocation(weighted_horizon, "Conservative")) if weighted_horizon > C.CAPITAL_PROTECTION_YEARS else 0.0
    mod_pr = planning_return(goal_allocation(weighted_horizon, "Moderate")) if weighted_horizon > C.CAPITAL_PROTECTION_YEARS else 0.0
    aggr_pr = planning_return(goal_allocation(weighted_horizon, "Aggressive")) if weighted_horizon > C.CAPITAL_PROTECTION_YEARS else 0.0
    if total_target <= 0:
        required_label = "Not applicable"
    elif req_g <= cons_pr:
        required_label = "Low"
    elif req_g <= mod_pr:
        required_label = "Moderate"
    elif req_g <= aggr_pr:
        required_label = "Moderate-High"
    else:
        required_label = "High"
    prof["required_risk"] = {"label": required_label, "required_return": req_g, "bucket": bucket_here}

    # 7) plain-English notes about mismatches and gaps (item 16/17/38 — consistency checks)
    notes = []
    if override and override != prof["label"]:
        notes.append(f"You are viewing the {override} portfolio; based on your answers the suggested profile is {prof['label']}.")
    gap = prof["willingness"] - prof["capacity"]
    if gap >= 2.5:
        notes.append(f"You are more comfortable with risk (willingness {prof['willingness']}/10) than your situation "
                     f"can comfortably afford (capacity {prof['capacity']}/10), so your score follows the lower figure.")
    elif gap <= -2.5:
        notes.append(f"Your situation could support more risk (capacity {prof['capacity']}/10) than you are comfortable "
                     f"with (willingness {prof['willingness']}/10), so your score follows your comfort level. "
                     "Long goals usually need some growth, so consider the higher-risk options too.")
    if abs(prof["stated"] - prof["quiz"]) >= 4:
        notes.append("Your stated risk appetite and your answers to the scenario questions point in different directions, "
                     "so we gave more weight to the scenario answers.")
    if required_label in ("Moderate-High", "High") and prof["label"] != "Aggressive":
        notes.append(f"To reach your goals as entered, your money would need to grow at roughly {req_g*100:.1f}% a year "
                      f"(a 'Required Risk' of {required_label}) - higher than your recommended {prof['label']} profile "
                      "targets. Consider a larger amount, a later date, lower targets, or a higher-risk option.")
    if topup > 0:
        notes.append(f"Rs {topup:,.0f} of your investable amount was set aside first to build up your emergency fund "
                     f"(kept 100% liquid), before the rest was allocated to your goals.")
    if snap["high_interest_debt"]:
        notes.append("You reported some high-interest debt. Its cost likely exceeds typical investment returns, "
                     "so consider repaying it before increasing investments further.")
    for g in goals:
        if g["years"] <= C.CAPITAL_PROTECTION_YEARS:
            notes.append(f"'{g['name']}' is {g['years']:g} year or less away, so it is kept 100% in liquid funds.")
        elif g["bucket"] == "Short" and rec != "Conservative":
            eq = equity_share(goal_allocation(g["years"], rec))
            notes.append(f"'{g['name']}' is only {g['years']:g} years away, so equity is limited to {eq:.0f}% "
                         f"for this goal even though your profile is {rec}.")
        if g["kind"] == "retirement" and g["years"] <= 10 and rec == "Aggressive":
            notes.append(f"Retirement is only {g['years']:g} years away, yet the Aggressive option still carries high "
                         "equity exposure. Consider the Moderate option as retirement gets closer.")
    for g in goals:
        if g.get("funded_ratio") is not None and g["funded_ratio"] < 0.999:
            shortfall_rupees = (g["required"] or 0) - g["funding"]
            notes.append(f"'{g['name']}' is only {g['funded_ratio']*100:.0f}% funded at your current amount "
                         f"(about Rs {shortfall_rupees:,.0f} short per {'month' if sip else 'the plan'}). "
                         "Consider a larger amount, a later date, or a lower target.")
    if snap["existing_equity_share"] is not None and snap["existing_equity_share"] >= 0.75:
        notes.append(f"Your existing investments are already about {snap['existing_equity_share']*100:.0f}% equity, "
                     "so new money has been tilted a little more toward debt/liquid to avoid over-concentration.")

    health = financial_health(inp, snap, goals)
    overall_mix = options[rec]["overall_alloc"]
    distinct_classes = sum(1 for v in overall_mix.values() if v >= 5.0)
    health["Investment Diversification"] = "Low" if distinct_classes <= 2 else "Moderate" if distinct_classes == 3 else "Good"

    return {
        "mode": "SIP (monthly)" if sip else "Lumpsum", "amount": amount, "surplus": surplus,
        "sip_step_up": step_up,
        "profile": prof, "recommended": rec, "goals": goals, "options": options, "notes": notes,
        "assumptions": {a: {"expected_return": C.ASSUMPTIONS[a][0], "volatility": C.ASSUMPTIONS[a][1]} for a in C.ASSETS},
        "assumptions_note": C.ASSUMPTIONS_NOTE,
        "inflation": C.INFLATION,
        "snapshot": snap, "emergency_topup": emergency_topup, "financial_health": health,
    }
