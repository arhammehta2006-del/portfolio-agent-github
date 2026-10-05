"""
app.py - interactive front-end (Streamlit).
Run with:   streamlit run app.py

Flow:  How it works -> About you -> Financial life -> Money & goals -> Risk comfort -> Review -> Your plan
(plan page follows the Investor Snapshot -> Financial Health -> Risk Profile -> Goals -> Portfolio ->
Why This Fits -> Expected Results -> Risk Analysis -> Alternatives -> Action Plan -> Maintenance order,
with Compare/Goal tracker/What-if/Ask the advisor/Download kept as secondary tabs underneath it.)
"""
import html
import json
import os
import re

import altair as alt
import pandas as pd
import streamlit as st

import advisor as D
import allocation as A
import config as C
import risk as R
from utils import fmt_inr

st.set_page_config(page_title="Goal-Based Portfolio Planner", page_icon="📈", layout="wide")

STEPS = ["How it works", "About you", "Financial life", "Money & goals", "Risk comfort", "Review", "Your plan"]
GOAL_COLS = ["Goal name", "Cost today (Rs)", "Years to go", "Priority", "Inflation category"]
ASSET_COLORS = ["#9ecae1", "#3182bd", "#f0b429", "#2ca25f", "#0b6e4f"]
ASSET_SCALE = alt.Scale(domain=C.ASSETS, range=ASSET_COLORS)
DISCLAIMER = ("Educational guidance only, not personalised financial advice. Figures are estimates based on stated "
              "assumptions and are not guaranteed. Please consult a SEBI-registered advisor before investing.")

HEALTH_COLOR = {"Good": "🟢", "Strong": "🟢", "On Track": "🟢", "Healthy": "🟢",
                "Needs Attention": "🟡", "Behind Target": "🟡", "Moderate": "🟡", "Needs Review": "🟡",
                "At Risk": "🔴", "Significantly Behind": "🔴", "Low": "🔴",
                "Not assessed": "⚪"}

CUSTOM_CSS = """
<style>
:root { --accent: #0b6e4f; }
.block-container { padding-top: 2rem; max-width: 1100px; }
h1, h2, h3 { letter-spacing: -0.01em; }
div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 600; }
.snapshot-card {
    background: #fafaf8; border: 1px solid #e7e4da; border-radius: 10px;
    padding: 18px 20px; margin-bottom: 10px;
}
.reason-chip {
    background: #f3f7f5; border-left: 3px solid var(--accent); border-radius: 6px;
    padding: 10px 14px; margin-bottom: 8px; font-size: 0.95rem;
}
.health-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #ececec; font-size: 0.95rem; }
.health-row:last-child { border-bottom: none; }
.maintenance-box { background: #fafaf8; border: 1px solid #e7e4da; border-radius: 10px; padding: 16px 20px; }
</style>
"""


# ------------------------------------------------------------------ state helpers
def init_state():
    ss = st.session_state
    if "step" not in ss:
        ss.step = 0
    if "inputs" not in ss:
        ss.inputs = {
            "age": 28, "dependents": 0, "has_retirement": True, "retirement_age": 60, "monthly_expenses": 0,
            "mode": "SIP (monthly)", "amount": 10000, "sip_step_up": 0.0, "stated_risk": "Moderate",
            "quiz_idx": [None, None, None],
            "goals_df": pd.DataFrame({
                GOAL_COLS[0]: ["Vacation"], GOAL_COLS[1]: [150000.0], GOAL_COLS[2]: [2.0],
                GOAL_COLS[3]: ["Important"], GOAL_COLS[4]: ["Travel"],
            }),
            "employment": "Salaried", "monthly_income": 0, "emi_total": 0, "emi_high_interest": False,
            "existing_equity": 0, "existing_other": 0, "emergency_savings": 0,
            "has_health_insurance": True, "has_life_insurance": True, "sole_earner": False,
            "liquidity_need": "Some",
        }


def _num(x):
    return 0.0 if x is None or pd.isna(x) else float(x)


def _txt(x, default=""):
    s = "" if x is None or pd.isna(x) else str(x).strip()
    return s or default


def engine_inputs():
    """Convert what the user typed into the plain dict the engine expects."""
    i = st.session_state.inputs
    goals = [{
        "name": _txt(r.get(GOAL_COLS[0])), "cost": _num(r.get(GOAL_COLS[1])), "years": _num(r.get(GOAL_COLS[2])),
        "priority": _txt(r.get(GOAL_COLS[3]), "Important"), "inflation_category": _txt(r.get(GOAL_COLS[4]), "General"),
    } for r in i["goals_df"].to_dict("records")]
    quiz = [R.QUIZ[k]["options"][idx][1] for k, idx in enumerate(i["quiz_idx"]) if idx is not None]
    return {
        "age": int(i["age"]), "dependents": int(i["dependents"]), "has_retirement": bool(i["has_retirement"]),
        "retirement_age": int(i["retirement_age"]), "monthly_expenses": float(i["monthly_expenses"]),
        "mode": i["mode"], "amount": float(i["amount"]), "sip_step_up": float(i.get("sip_step_up") or 0.0) / 100.0,
        "goals": goals, "stated_risk": i["stated_risk"], "quiz": quiz,
        "employment": i["employment"], "monthly_income": float(i["monthly_income"]), "emi_total": float(i["emi_total"]),
        "emi_high_interest": bool(i["emi_high_interest"]),
        "existing_equity": float(i["existing_equity"]), "existing_other": float(i["existing_other"]),
        "emergency_savings": float(i["emergency_savings"]),
        "has_health_insurance": bool(i["has_health_insurance"]), "has_life_insurance": bool(i["has_life_insurance"]),
        "sole_earner": bool(i["sole_earner"]), "liquidity_need": i["liquidity_need"],
    }


@st.cache_data(show_spinner=False)
def cached_plan(sig, override, mult):
    return A.build_plan(json.loads(sig), override=override, amount_mult=mult)


def go(step):
    st.session_state.step = step
    st.rerun()


def suffix(mode):
    return "/month" if mode.startswith("SIP") else ""


# ------------------------------------------------------------------ chart helpers
def donut(alloc):
    df = pd.DataFrame({"Asset": list(alloc.keys()), "Percent": list(alloc.values())})
    df = df[df["Percent"] > 0]
    return (alt.Chart(df).mark_arc(innerRadius=55)
            .encode(theta=alt.Theta("Percent:Q"),
                    color=alt.Color("Asset:N", scale=ASSET_SCALE, legend=alt.Legend(orient="bottom", title=None)),
                    tooltip=["Asset:N", alt.Tooltip("Percent:Q", format=".1f")])
            .properties(height=260))


def options_chart(plan):
    rows = [{"Option": n, "Asset": a, "Percent": v, "Order": C.ASSETS.index(a)}
            for n, o in plan["options"].items() for a, v in o["overall_alloc"].items()]
    df = pd.DataFrame(rows)
    return (alt.Chart(df).mark_bar()
            .encode(y=alt.Y("Option:N", sort=C.PROFILES, title=None),
                    x=alt.X("sum(Percent):Q", title="% of portfolio"),
                    color=alt.Color("Asset:N", scale=ASSET_SCALE, legend=alt.Legend(orient="bottom", title=None)),
                    order=alt.Order("Order:Q"),
                    tooltip=["Option:N", "Asset:N", alt.Tooltip("sum(Percent):Q", format=".1f")])
            .properties(height=170, width="container"))


def chances_chart(plan):
    rows = [{"Goal": r["goal"], "Option": n, "Chance": r["prob"] * 100}
            for n, o in plan["options"].items() for r in o["goals"] if r["prob"] is not None]
    if not rows:
        return None
    return (alt.Chart(pd.DataFrame(rows)).mark_bar()
            .encode(x=alt.X("Option:N", sort=C.PROFILES, axis=alt.Axis(labels=False, title=None)),
                    y=alt.Y("Chance:Q", scale=alt.Scale(domain=[0, 100]), title="Chance of reaching target (%)"),
                    color=alt.Color("Option:N", sort=C.PROFILES),
                    column=alt.Column("Goal:N", title=None),
                    tooltip=["Goal:N", "Option:N", alt.Tooltip("Chance:Q", format=".0f")])
            .properties(width=110, height=220))


# ------------------------------------------------------------------ table helpers
def goals_table(plan):
    sip = plan["mode"].startswith("SIP")
    opt = plan["options"][plan["recommended"]]
    rows = []
    for g, r in zip(plan["goals"], opt["goals"]):
        rows.append({
            "Goal": g["name"], "Priority": g.get("priority", "-"), "Years": f"{g['years']:g}", "Horizon": g["bucket"],
            "Target (future Rs)": fmt_inr(g["target"]) if g["target"] else "No fixed target",
            "Needed": (fmt_inr(g["required"]) + suffix(plan["mode"])) if g.get("required") else "-",
            "Allocated": fmt_inr(g["funding"]) + suffix(plan["mode"]),
            "Funded": f"{g['funded_ratio'] * 100:.0f}%" if g.get("funded_ratio") is not None else "-",
            "Equity share": f"{r['equity_pct']:.0f}%",
        })
    return pd.DataFrame(rows)


def per_goal_alloc_table(plan):
    opt = plan["options"][plan["recommended"]]
    rows = []
    for r in opt["goals"]:
        row = {"Goal": r["goal"]}
        row.update({a: f"{v:.0f}%" for a, v in r["alloc"].items()})
        rows.append(row)
    return pd.DataFrame(rows)


def outcomes_table(plan):
    rows = []
    for n, o in plan["options"].items():
        for r in o["goals"]:
            rows.append({
                "Option": n + (" (suggested)" if n == plan["recommended"] else ""), "Goal": r["goal"],
                "Chance of reaching target": "n/a" if r["prob"] is None else f"{r['prob'] * 100:.0f}%",
                "Typical outcome": fmt_inr(r["median"]),
                "Typical as % of target": "n/a" if r["median_pct"] is None else f"{r['median_pct'] * 100:.0f}%",
                "Weak market (10th pct)": fmt_inr(r["p10"]), "Strong market (90th pct)": fmt_inr(r["p90"]),
            })
    return pd.DataFrame(rows)


def action_plan(plan):
    """Item 12/44: concrete next steps, not just an allocation. Every line traces to a computed number."""
    sip = plan["mode"].startswith("SIP")
    tips = []
    for g in plan["goals"]:
        if g.get("required") and g.get("funded_ratio") is not None and g["funded_ratio"] < 0.999:
            gap = max(0.0, g["required"] - g["funding"])
            tips.append(f"'{g['name']}': increase funding by about {fmt_inr(gap)}{suffix(plan['mode'])}, "
                        "or push the goal date out, to fully fund it.")
    et = plan["emergency_topup"]
    if et["required"] > 0 and et["funding"] < et["required"] - 0.5:
        tips.append(f"Keep building your emergency fund - about {fmt_inr(et['required'] - et['funding'])} more "
                    "is needed to reach your target buffer.")
    snap = plan["snapshot"]
    if snap["high_interest_debt"]:
        tips.append("Prioritise repaying high-interest debt before increasing investments further.")
    if not snap["has_health_insurance"]:
        tips.append("Consider adequate health insurance coverage as part of your overall plan.")
    if plan["financial_health"].get("Insurance Protection") == "Needs Review" and snap["has_health_insurance"]:
        tips.append("Consider adequate life insurance cover, since you are a primary earner with dependents.")
    if not tips:
        tips.append("Your plan looks on track based on what you've entered. Revisit it if your goals, income or dependents change.")
    return tips


def plan_markdown(plan, explanation):
    prof = plan["profile"]
    lines = ["# My goal-based investment plan", "", f"_{DISCLAIMER}_", "",
             f"**Investing:** {fmt_inr(plan['amount'])}{suffix(plan['mode'])} ({plan['mode']})  ",
             f"**Risk score:** {prof['score']}/10 - suggested profile: **{plan['recommended']}**  ",
             f"**Risk appetite / capacity / required:** {prof['willingness']}/10 / {prof['capacity']}/10 / {prof['required_risk']['label']}  ",
             "", "## Explanation", explanation, "", "## Financial health"]
    for k, v in plan["financial_health"].items():
        lines.append(f"- **{k}:** {v}")
    lines += ["", "## Goals"]
    for _, row in goals_table(plan).iterrows():
        lines.append(f"- **{row['Goal']}** ({row['Priority']}, {row['Years']} yrs, {row['Horizon']}): target {row['Target (future Rs)']}, "
                     f"allocated {row['Allocated']}, funded {row['Funded']}, equity {row['Equity share']}")
    lines += ["", "## The three options (overall mix)"]
    for n, o in plan["options"].items():
        mix = ", ".join(f"{a} {v:.0f}%" for a, v in o["overall_alloc"].items() if v > 0)
        lines.append(f"- **{n}{' (suggested)' if n == plan['recommended'] else ''}:** {mix} | expected return "
                     f"{o['exp_return'] * 100:.1f}% | Sharpe {o['sharpe']:.2f} | bad-year {o['bad_year'] * 100:.1f}%")
    lines += ["", "## Action plan"] + [f"- {t}" for t in action_plan(plan)]
    lines += ["", "## Assumptions", plan["assumptions_note"],
              f"Inflation assumed at {plan['inflation'] * 100:.0f}% a year (goal-specific rates may differ - see the Assumptions panel). "
              f"Probabilities come from {C.N_SIMS:,} simulated futures."]
    return "\n".join(lines)


# ------------------------------------------------------------------ sidebar
def sidebar():
    st.sidebar.title("📈 Portfolio Planner")
    step = st.session_state.step
    for i, s in enumerate(STEPS):
        mark = "✅" if i < step else "▶️" if i == step else "⬜"
        st.sidebar.markdown(f"{mark} {s}")
    st.sidebar.divider()
    with st.sidebar.expander("Assumptions & methodology"):
        st.caption("Return & volatility assumptions (by asset class):")
        st.dataframe(pd.DataFrame([{"Asset": a, "Exp. return": f"{v[0] * 100:.1f}%", "Volatility": f"{v[1] * 100:.1f}%"}
                                   for a, v in C.ASSUMPTIONS.items()]), hide_index=True)
        st.caption(C.ASSUMPTIONS_NOTE)
        st.caption("Inflation by goal type (item 23 - different expenses inflate at different rates):")
        st.dataframe(pd.DataFrame([{"Goal type": k, "Assumed inflation": f"{v*100:.0f}%"} for k, v in C.GOAL_INFLATION.items()]),
                    hide_index=True)
        st.caption(f"Planning margin {C.PLANNING_MARGIN * 100:.0f} pt | risk-free rate (for Sharpe) {C.RISK_FREE_RATE*100:.1f}% | "
                   f"{C.N_SIMS:,} simulations | emergency-fund months and EMI-burden threshold are stated planning "
                   "heuristics, not regulatory requirements - see config.py.")
        st.caption("User-provided: age, income, goals, risk answers. Model-estimated: required return, funding gaps, "
                   "probabilities. Default assumptions: all return/inflation/emergency-fund figures above.")
    st.sidebar.caption(DISCLAIMER)


# ------------------------------------------------------------------ step 0: how it works
def step_intro():
    st.title("Build your plan around your life.")
    st.markdown("Tell us what you're investing for, and we'll turn it into a portfolio you can understand - "
                "not just a number, but the reasoning behind it.")
    cols = st.columns(5)
    for col, (n, label) in zip(cols, enumerate([
        "Tell us about your finances", "Add your financial goals", "Understand your risk profile",
        "Get your personalised portfolio", "Compare alternative strategies"], start=1)):
        col.markdown(f"**Step {n}**")
        col.caption(label)
    st.write("")
    if st.button("Build my plan →", type="primary", key="intro_start"):
        go(1)


# ------------------------------------------------------------------ step 1: about you
def step_about():
    inp = st.session_state.inputs
    st.subheader("Step 1 of 5 · About you")
    c1, c2 = st.columns(2)
    age = c1.number_input("Your age", 18, 70, int(inp["age"]), key="w_age")
    deps = c2.number_input("People who depend on you financially (spouse, children, parents)", 0, 10,
                           int(inp["dependents"]), key="w_deps",
                           help="Household responsibilities affect how much risk your situation can really afford, "
                                "separately from how much risk you say you're comfortable with.")
    has_ret = st.checkbox("I also want to plan for retirement", value=bool(inp["has_retirement"]), key="w_has_ret")
    ret_age = inp["retirement_age"]
    if has_ret:
        ret_age = st.number_input("Retirement age", 35, 80, max(int(inp["retirement_age"]), 35), key="w_ret_age")
    if deps > 0:
        sole = st.checkbox("I am the sole or primary income earner in my household", value=bool(inp["sole_earner"]), key="w_sole")
    else:
        sole = False
    if st.button("Next →", type="primary", key="next0"):
        inp.update(age=int(age), dependents=int(deps), has_retirement=bool(has_ret), retirement_age=int(ret_age),
                   sole_earner=bool(sole))
        go(2)


# ------------------------------------------------------------------ step 2: financial life
def step_financial_life():
    inp = st.session_state.inputs
    st.subheader("Step 2 of 5 · Your financial life")
    st.caption("This helps us check what you can actually afford to invest, and whether anything needs attention "
               "before building a long-term portfolio.")

    employment = st.selectbox("Employment type", C.EMPLOYMENT_TYPES,
                              index=C.EMPLOYMENT_TYPES.index(inp["employment"]) if inp["employment"] in C.EMPLOYMENT_TYPES else 0,
                              key="w_employment")
    income_label = {"Student": "Your monthly income, if any (Rs)", "Retired": "Your monthly pension/income (Rs)"}.get(
        employment, "Your monthly take-home income (Rs)")
    c1, c2 = st.columns(2)
    income = c1.number_input(income_label, 0, 10_000_000, int(inp["monthly_income"]), step=1000, key="w_income",
                             help="Optional, but needed to check whether your planned investment is actually affordable.")
    expenses = c2.number_input("Monthly household expenses (Rs)", 0, 10_000_000, int(inp["monthly_expenses"]), step=1000,
                               key="w_expenses", help="Used for your emergency-fund target and (if planning retirement) your retirement corpus.")

    c3, c4 = st.columns(2)
    emi = c3.number_input("Total monthly EMIs / loan payments (Rs)", 0, 10_000_000, int(inp["emi_total"]), step=500, key="w_emi")
    emi_high = c4.checkbox("Some of this debt is high-interest (e.g. credit card, personal loan)",
                           value=bool(inp["emi_high_interest"]), key="w_emi_high") if emi > 0 else False

    st.markdown("**Existing investments** (so we don't recommend a portfolio that ignores what you already hold - item 19)")
    c5, c6 = st.columns(2)
    existing_equity = c5.number_input("Current value in equity / equity mutual funds (Rs)", 0, 100_000_000,
                                      int(inp["existing_equity"]), step=5000, key="w_existing_equity")
    existing_other = c6.number_input("Current value in debt/FDs/gold/other investments (Rs)", 0, 100_000_000,
                                     int(inp["existing_other"]), step=5000, key="w_existing_other")

    st.markdown("**Emergency fund**")
    emergency_savings = st.number_input("Money already set aside as an emergency fund (Rs)", 0, 100_000_000,
                                        int(inp["emergency_savings"]), step=5000, key="w_emergency",
                                        help="Kept separately from your long-term investments, in something liquid like a savings or liquid fund.")
    months, target = R.emergency_fund_target({**inp, "employment": employment, "monthly_expenses": expenses, "dependents": inp["dependents"]})
    if expenses > 0:
        st.caption(f"Based on your employment type and dependents, a buffer of about {months:g} months of expenses "
                   f"(~{fmt_inr(target)}) is a reasonable target.")

    liquidity = st.radio("How much of this investment might you need to access unexpectedly?",
                         ["Very little", "Some", "Significant"],
                         index=["Very little", "Some", "Significant"].index(inp["liquidity_need"]), horizontal=True, key="w_liquidity")

    if inp["dependents"] > 0:
        st.markdown("**Protection check** (we don't recommend insurance products - just flag a gap if one exists)")
        c7, c8 = st.columns(2)
        health = c7.checkbox("I have health insurance", value=bool(inp["has_health_insurance"]), key="w_health_ins")
        life = c8.checkbox("I have life insurance / term cover", value=bool(inp["has_life_insurance"]), key="w_life_ins")
    else:
        health, life = inp["has_health_insurance"], inp["has_life_insurance"]

    c1, c2, _ = st.columns([1, 1, 4])
    if c1.button("← Back", key="back_fl"):
        inp.update(employment=employment, monthly_income=float(income), monthly_expenses=float(expenses),
                   emi_total=float(emi), emi_high_interest=bool(emi_high), existing_equity=float(existing_equity),
                   existing_other=float(existing_other), emergency_savings=float(emergency_savings),
                   liquidity_need=liquidity, has_health_insurance=bool(health), has_life_insurance=bool(life))
        go(1)
    if c2.button("Next →", type="primary", key="next_fl"):
        inp.update(employment=employment, monthly_income=float(income), monthly_expenses=float(expenses),
                   emi_total=float(emi), emi_high_interest=bool(emi_high), existing_equity=float(existing_equity),
                   existing_other=float(existing_other), emergency_savings=float(emergency_savings),
                   liquidity_need=liquidity, has_health_insurance=bool(health), has_life_insurance=bool(life))
        go(3)


# ------------------------------------------------------------------ step 3: money & goals
def step_money():
    inp = st.session_state.inputs
    st.subheader("Step 3 of 5 · Your money and goals")
    mode = st.radio("How will you invest?", ["SIP (monthly)", "Lumpsum"], horizontal=True, key="w_mode",
                    index=0 if inp["mode"].startswith("SIP") else 1)
    label = "Monthly SIP amount (Rs)" if mode.startswith("SIP") else "One-time amount to invest (Rs)"
    amount = st.number_input(label, 0, 100_000_000, int(inp["amount"]), step=1000, key="w_amount")
    step_up = inp["sip_step_up"]
    if mode.startswith("SIP"):
        step_up = st.slider("Expected annual increase to your SIP (step-up), %", 0, 25, int(inp["sip_step_up"]), 1, key="w_stepup",
                            help="If your income is likely to grow, a rising SIP reaches the same goal with a smaller starting amount.")
    st.markdown("**Your goals** - add one row per goal. Enter the cost in *today's* rupees; we adjust for inflation using "
               "a rate that depends on the goal type. Use cost 0 for an open-ended goal. Set priority so we know what to "
               "fund first if your amount can't cover everything.")
    edited = st.data_editor(
        inp["goals_df"], num_rows="dynamic", key="w_goals",
        column_config={
            GOAL_COLS[0]: st.column_config.TextColumn("Goal name", help="e.g. Marriage, Child's education, Vacation"),
            GOAL_COLS[1]: st.column_config.NumberColumn("Cost today (Rs)", min_value=0, step=10000, format="%.0f"),
            GOAL_COLS[2]: st.column_config.NumberColumn("Years to go", min_value=0.5, max_value=50, step=0.5, format="%.1f"),
            GOAL_COLS[3]: st.column_config.SelectboxColumn("Priority", options=C.PRIORITIES, default="Important"),
            GOAL_COLS[4]: st.column_config.SelectboxColumn("Inflation category", options=list(C.GOAL_INFLATION.keys()),
                                                            default="General"),
        })
    c1, c2, _ = st.columns([1, 1, 4])
    if c1.button("← Back", key="back1"):
        go(2)
    if c2.button("Next →", type="primary", key="next1"):
        inp.update(mode=mode, amount=int(amount), sip_step_up=float(step_up), goals_df=edited.copy())
        go(4)


# ------------------------------------------------------------------ step 4: risk comfort
def step_risk():
    inp = st.session_state.inputs
    st.subheader("Step 4 of 5 · How do you feel about risk?")
    levels = ["Low", "Moderate", "High"]
    stated = st.radio("In general, how would you describe your risk appetite?", levels,
                      index=levels.index(inp["stated_risk"]), horizontal=True, key="w_stated")
    st.markdown("Now three quick scenarios. Your answers tell us more than a label does.")
    idxs = []
    for k, q in enumerate(R.QUIZ):
        opts = [o[0] for o in q["options"]]
        choice = st.radio(f"{k + 1}. {q['q']}", opts, index=inp["quiz_idx"][k], key=f"w_q{k}")
        idxs.append(None if choice is None else opts.index(choice))
    complete = all(i is not None for i in idxs)
    if not complete:
        st.caption("Please answer all three scenarios to continue.")
    c1, c2, _ = st.columns([1, 2, 3])
    if c1.button("← Back", key="back2"):
        inp.update(stated_risk=stated, quiz_idx=idxs)
        go(3)
    if c2.button("Review my profile →", type="primary", key="next2", disabled=not complete):
        inp.update(stated_risk=stated, quiz_idx=idxs)
        go(5)


# ------------------------------------------------------------------ step 5: review
def step_review():
    einp = engine_inputs()
    errors, warnings = R.validate(einp)
    st.subheader("Review · here is what we understood")
    for e in errors:
        st.error(e)
    for w in warnings:
        st.warning(w)
    if not errors:
        goals = R.build_goals(einp)
        prof = R.risk_profile(einp, goals)
        c = st.columns(4)
        c[0].metric("Risk appetite", f"{prof['willingness']}/10", help="How comfortable you say you are with ups and downs.")
        c[1].metric("Risk capacity", f"{prof['capacity']}/10", help="How much risk your age, dependents, goals and emergency fund can really afford.")
        c[2].metric("Suggested profile", prof["label"], help="The lower of appetite and capacity - never higher than either.")
        c[3].metric("Your score", f"{prof['score']}/10")
        st.progress(min(prof["score"] / 10, 1.0))
        st.caption("Your suggested profile is the LOWER of your comfort with risk and what your situation can afford. "
                   "On the next page you'll also see 'Required Risk' - what your goals would actually need.")
        st.markdown(f"**Investing:** {fmt_inr(einp['amount'])}{suffix(einp['mode'])} ({einp['mode']})"
                   + (f", stepping up {einp['sip_step_up']*100:.0f}%/year" if einp["mode"].startswith("SIP") and einp["sip_step_up"] > 0 else ""))
        if goals:
            st.dataframe(pd.DataFrame([{
                "Goal": g["name"], "Priority": g.get("priority", "-"), "Years to go": f"{g['years']:g}", "Horizon": g["bucket"],
                "Target (future Rs)": fmt_inr(g["target"]) if g["target"] else "No fixed target"} for g in goals]),
                hide_index=True)
        preview = cached_plan(json.dumps(einp, sort_keys=True, default=str), None, 1.0)
        for n in preview["notes"][:4]:
            st.info(n)
    c1, c2, _ = st.columns([1, 2, 3])
    if c1.button("← Edit answers", key="back3"):
        go(4)
    if c2.button("Generate my plan →", type="primary", key="next3", disabled=bool(errors)):
        go(6)


# ------------------------------------------------------------------ step 6: results
def get_explanation(plan, sig, api_key, model, force=False):
    ex = st.session_state.get("expl")
    if force or not ex or ex["sig"] != sig:
        with st.spinner("Writing your personalised explanation..."):
            text, used, err = D.generate_explanation(plan, api_key, model)
        st.session_state.expl = {"sig": sig, "text": text, "used_ai": used, "err": err}
    return st.session_state.expl


def render_reasoning_chips(markdown_text):
    """Split the AI/fallback text's first '### Why this fits you' section into visual chip cards (UI item 13)."""
    lines = markdown_text.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.strip().startswith("### Why this fits you")) + 1
    except StopIteration:
        return markdown_text, "\n".join(lines)
    end = next((i for i in range(start, len(lines)) if lines[i].strip().startswith("###")), len(lines))
    bullets = [l.strip("- ").strip() for l in lines[start:end] if l.strip().startswith("-")]
    rest = "\n".join(lines[end:])

    def _chip_inner(b):
        # escape first (so any literal <, >, & in a goal name etc. can't break the markup or inject
        # HTML), THEN turn **markdown bold** into real <b> tags - bullets reach here as markdown text,
        # not HTML, and this div is rendered with unsafe_allow_html=True.
        escaped = html.escape(b)
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)

    chips_html = "".join(f'<div class="reason-chip">{_chip_inner(b)}</div>' for b in bullets) if bullets else ""
    return chips_html, rest


def step_results(api_key, model):
    einp = engine_inputs()
    sig = json.dumps(einp, sort_keys=True, default=str)
    plan = cached_plan(sig, None, 1.0)
    prof, rec = plan["profile"], plan["recommended"]
    opt = plan["options"][rec]
    snap = plan["snapshot"]
    if st.session_state.get("chat_sig") != sig:      # new inputs -> fresh chat
        st.session_state.chat, st.session_state.chat_sig = [], sig

    top = st.columns([5, 1, 1])
    top[0].title("Your plan is ready.")
    if top[1].button("✏️ Edit", key="edit_answers"):
        go(1)
    if top[2].button("↺ Restart", key="restart"):
        for k in ["step", "inputs", "expl", "chat", "chat_sig"]:
            st.session_state.pop(k, None)
        st.rerun()

    # ---------- 1. Investor snapshot ----------
    st.markdown(f"#### {rec}")
    st.caption(f"Built for a {prof['weighted_horizon_years']:g}-year money-weighted horizon, "
              f"{einp['dependents']} dependent(s), and a {prof['label'].lower()} risk profile.")
    m = st.columns(4)
    m[0].metric("Risk score", f"{prof['score']}/10")
    m[1].metric("Investing", fmt_inr(plan["amount"]) + suffix(plan["mode"]))
    m[2].metric("Goals", len(plan["goals"]))
    m[3].metric("Required risk", prof["required_risk"]["label"],
               help="What your goals would need to grow at, given your amount and dates - shown for awareness; "
                    "it does not override the appetite/capacity-based recommendation above.")

    # ---------- 2. Financial health ----------
    st.markdown("### Your financial foundation")
    health = plan["financial_health"]
    cols = st.columns(len(health))
    for col, (k, v) in zip(cols, health.items()):
        col.markdown(f"{HEALTH_COLOR.get(v, '⚪')} **{k}**")
        col.caption(v)

    # ---------- 3. Risk profile (three angles) ----------
    with st.expander("Why these risk numbers? (Appetite vs Capacity vs Required)"):
        st.markdown(f"- **Risk appetite** {prof['willingness']}/10 - how you say you feel about ups and downs.")
        st.markdown(f"- **Risk capacity** {prof['capacity']}/10 - what your age, dependents, goal horizon, EMI load "
                   "and emergency fund can really afford.")
        st.markdown(f"- **Required risk** {prof['required_risk']['label']} - what your goals, as entered, would actually need.")
        st.caption("The recommendation always follows the LOWER of appetite and capacity. Required risk is shown "
                  "for awareness - if it's higher than your recommended profile, see the note below about adjusting "
                  "your amount, dates, or targets.")

    # ---------- 4/5. Goals, timeline & recommended portfolio ----------
    st.markdown("### Your goals")
    st.dataframe(goals_table(plan), hide_index=True)
    if plan["emergency_topup"]["funding"] > 0:
        st.info(f"Rs {plan['emergency_topup']['funding']:,.0f} of this amount was set aside first for your "
               f"emergency fund (100% liquid) before funding the goals above.")
    if plan["surplus"] > 0.5:
        st.info(f"After fully funding your goals, {fmt_inr(plan['surplus'])}{suffix(plan['mode'])} was left over and "
               "has been placed in open-ended long-term wealth building.")

    st.markdown(f"### Recommended overall mix ({rec})")
    left, right = st.columns(2)
    left.altair_chart(donut(opt["overall_alloc"]))
    right.dataframe(pd.DataFrame([{"Asset": a, "Share": f"{v:.1f}%"} for a, v in opt["overall_alloc"].items()]),
                    hide_index=True)
    right.caption(f"Expected return about {opt['exp_return'] * 100:.1f}% a year; typical yearly ups and downs "
                 f"about ±{opt['volatility'] * 100:.1f}%.")
    with st.expander("See the asset mix for each goal"):
        st.dataframe(per_goal_alloc_table(plan), hide_index=True)

    # ---------- 6. Why this fits you ----------
    st.markdown("### Why this fits you")
    ex = get_explanation(plan, sig, api_key, model)
    chips_html, rest_md = render_reasoning_chips(ex["text"])
    if chips_html:
        st.markdown(CUSTOM_CSS + chips_html, unsafe_allow_html=True)
    st.markdown(rest_md)
    st.caption("Explanation written by AI from the tool's calculated numbers." if ex["used_ai"]
              else "Built-in explanation (this deployment runs on the tool's own rule-based writer, "
                   "with no live AI connection).")
    if ex["err"]:
        st.warning(ex["err"])
    if st.button("Regenerate explanation", key="regen"):
        get_explanation(plan, sig, api_key, model, force=True)
        st.rerun()

    # ---------- 7. Expected results (scenarios) ----------
    st.markdown("### Expected results")
    st.caption("Three scenarios from the simulated outcomes, for your goal-by-goal plan under the recommended option.")
    for g, row in zip(plan["goals"], opt["goals"]):
        if row["p10"] == 0 and row["p90"] == 0 and row["median"] == 0:
            continue
        sc = st.columns(4)
        sc[0].markdown(f"**{g['name']}**")
        sc[1].metric("Conservative", fmt_inr(row["p10"]))
        sc[2].metric("Expected", fmt_inr(row["median"]))
        sc[3].metric("Optimistic", fmt_inr(row["p90"]))
    st.caption("Your actual outcome may fall anywhere within or outside this range. These are not guarantees.")

    # ---------- 8. Risk analysis (advanced, behind an expander per item 20 UI) ----------
    with st.expander("View advanced risk analysis"):
        for name, o in plan["options"].items():
            st.markdown(f"**{name}**" + (" (suggested)" if name == rec else ""))
            rc = st.columns(4)
            rc[0].metric("Expected return", f"{o['exp_return']*100:.1f}%")
            rc[1].metric("Volatility", f"{o['volatility']*100:.1f}%", help="How much this portfolio may fluctuate year to year.")
            rc[2].metric("Sharpe ratio", f"{o['sharpe']:.2f}", help="Return earned per unit of risk taken; higher is generally better risk-adjusted performance.")
            rc[3].metric("Stress decline", f"{o['stress_decline']*100:.1f}%", help="A rarer, sharper one-year decline than the 'bad year' figure - an analytical estimate, not a historical drawdown.")

    # ---------- 9. Alternatives / compare ----------
    st.markdown("### Compare alternatives")
    cols = st.columns(3)
    for col, name in zip(cols, C.PROFILES):
        o = plan["options"][name]
        col.markdown(f"##### {name}" + (" ✅ suggested" if name == rec else ""))
        col.metric("Expected return / year", f"{o['exp_return'] * 100:.1f}%")
        col.metric("Typical ups and downs", f"±{o['volatility'] * 100:.1f}%")
        col.metric("A bad year (1 in 20)", f"{o['bad_year'] * 100:.1f}%")
    st.altair_chart(options_chart(plan))

    # ---------- 10. Action plan ----------
    st.markdown("### Action plan")
    for tip in action_plan(plan):
        st.markdown(f"- {tip}")

    # ---------- 11. Portfolio maintenance ----------
    with st.expander("Portfolio maintenance (rebalancing & reviews)"):
        st.markdown(
            "**Rebalancing:** review your mix at least once a year, or sooner if any asset class drifts more than "
            "about 5 percentage points from its target, or after a major life event.\n\n"
            "**Goal-based de-risking:** as an important goal gets closer, gradually move the money needed for it "
            "out of equity and into safer assets (this already happens automatically as a goal moves between "
            "horizon buckets in this tool).\n\n"
            "**Redistribution triggers:** reconsider your plan after a marriage, new child, new home, job change, "
            "or a significant change in income or expenses."
        )

    st.divider()
    _secondary_tabs(plan, sig, api_key, model, opt, rec)
    st.divider()
    st.caption(DISCLAIMER)


def _secondary_tabs(plan, sig, api_key, model, opt, rec):
    t_goals, t_whatif, t_chat, t_dl = st.tabs(["Goal tracker", "What-if", "Ask the advisor", "Download"])

    with t_goals:
        st.markdown("How likely is each goal to be met? We simulate "
                   f"{C.N_SIMS:,} possible market futures and count how often the target is reached.")
        for g in plan["goals"]:
            if g.get("funded_ratio") is not None:
                st.progress(min(g["funded_ratio"], 1.0),
                           text=f"{g['name']}: {g['funded_ratio'] * 100:.0f}% funded "
                                f"({fmt_inr(g['funding'])}{suffix(plan['mode'])} of {fmt_inr(g['required'])}{suffix(plan['mode'])} needed)")
            else:
                st.progress(1.0, text=f"{g['name']}: open-ended, receives {fmt_inr(g['funding'])}{suffix(plan['mode'])}")
        chart = chances_chart(plan)
        if chart is not None:
            st.altair_chart(chart)
        st.dataframe(outcomes_table(plan), hide_index=True)

    with t_whatif:
        st.markdown("Change the inputs and see the effect instantly.")
        w1, w2 = st.columns(2)
        mult = w1.slider("Amount, as % of what you entered", 25, 300, 100, 5, key="wi_mult") / 100
        choice = w2.selectbox("Risk profile to test", ["Suggested"] + C.PROFILES, key="wi_prof")
        wi = cached_plan(sig, None if choice == "Suggested" else choice, mult)
        wi_opt = wi["options"][wi["recommended"]]
        base_prob = {r["goal"]: r["prob"] for r in opt["goals"]}
        rows = []
        for g, r in zip(wi["goals"], wi_opt["goals"]):
            b = base_prob.get(g["name"])
            rows.append({
                "Goal": g["name"],
                "Funded": f"{g['funded_ratio'] * 100:.0f}%" if g.get("funded_ratio") is not None else "-",
                "Chance of reaching target": "n/a" if r["prob"] is None else f"{r['prob'] * 100:.0f}%",
                "Change vs your plan": "-" if (r["prob"] is None or b is None) else f"{(r['prob'] - b) * 100:+.0f} pts",
                "Typical outcome": fmt_inr(r["median"]),
            })
        k = st.columns(3)
        k[0].metric("Amount tested", fmt_inr(wi["amount"]) + suffix(wi["mode"]))
        k[1].metric("Profile tested", wi["recommended"])
        k[2].metric("Expected return / year", f"{wi_opt['exp_return'] * 100:.1f}%")
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        st.altair_chart(donut(wi_opt["overall_alloc"]))

    with t_chat:
        st.markdown("Ask anything about *your* plan. The advisor only uses the numbers calculated above.")
        suggestions = ["Why is my equity share what it is?", "Why is my short-term goal so safe?",
                      "What could I change to reach my goals?"]
        sc = st.columns(3)
        for i, s in enumerate(suggestions):
            if sc[i].button(s, key=f"sq{i}"):
                st.session_state.pending_q = s
        for msg in st.session_state.chat:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        q = st.chat_input("Ask about your plan...") or st.session_state.pop("pending_q", None)
        if q:
            history = list(st.session_state.chat)
            with st.spinner("Thinking..."):
                answer, used, err = D.answer_question(plan, history, q, api_key, model)
            st.session_state.chat += [{"role": "user", "content": q}, {"role": "assistant", "content": answer}]
            if err:
                st.warning(err)
            st.rerun()

    with t_dl:
        ex = st.session_state.get("expl") or {"text": ""}
        st.download_button("⬇️ Download my plan (Markdown)", plan_markdown(plan, ex["text"]),
                           file_name="my_investment_plan.md", mime="text/markdown")
        st.download_button("⬇️ Download goal table (CSV)", goals_table(plan).to_csv(index=False),
                           file_name="my_goal_plan.csv", mime="text/csv")


# ------------------------------------------------------------------ main
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
init_state()
sidebar()
# No API key is collected from the user in this deployment - AI explanations stay fully optional and are
# only ever switched on via a server-side ANTHROPIC_API_KEY (e.g. a Streamlit Cloud "secret"), never a
# public input box. With no key set, the app runs entirely on its own built-in rule-based explanations.
api_key, model = os.environ.get("ANTHROPIC_API_KEY"), D.DEFAULT_MODEL
step = st.session_state.step
if step > 0:
    st.progress((step - 1) / (len(STEPS) - 2), text=f"{STEPS[step]}")
{0: step_intro, 1: step_about, 2: step_financial_life, 3: step_money, 4: step_risk, 5: step_review,
 6: lambda: step_results(api_key, model)}[step]()
