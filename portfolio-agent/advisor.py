"""
advisor.py - the GenAI layer.
The AI NEVER calculates. It receives the numbers computed by allocation.py (as JSON) and explains them
in simple language. If no API key is set (or the call fails) a rule-based explanation is used instead,
so the demo never breaks.
"""
import json
import os
from utils import fmt_inr

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """You are the explanation layer of an educational, goal-based portfolio planning tool for \
first-time retail investors in India (age 22-40).

All numbers (risk scores, allocations, projections, probabilities, funding gaps, financial-health flags) were \
computed by the tool's own code and are given to you as JSON. Your job is to EXPLAIN them, not to compute anything.

Rules:
1. Use ONLY numbers that appear in the JSON. Never calculate new figures, invent returns, or estimate anything yourself.
2. Never promise or guarantee returns and never promise "maximum returns". Say the figures are estimates from stated assumptions.
3. Talk about asset classes only (liquid funds, debt funds, gold, large-cap equity, mid-cap equity). Do not name specific funds, stocks or companies.
4. Write in simple, friendly English with short sentences. Explain any jargon in a few words.
5. Always explain WHY the allocation fits THIS client: weave together their goals' timelines, risk appetite vs capacity vs
   required risk, dependents, income/debt situation, emergency-fund status and funding gaps - reference several of these
   together, the way a human adviser would, rather than a single generic reason.
6. If risk appetite, risk capacity and required risk point in different directions for this client, say so plainly and
   explain which one the recommendation followed and why (the tool always follows the LOWER of appetite/capacity; it
   never silently overrides that with required risk).
7. This is educational guidance, not personalised financial advice.
8. If the client asks something the JSON cannot answer, say what the tool can and cannot tell them.
Amounts are in Indian rupees."""

EXPLAIN_INSTRUCTION = """Write the client's plan explanation using exactly these markdown headings, in this order:

### Why this fits you
3 to 6 short bullet points, each in the form "**<their specific input>** - <the one portfolio decision it drove>".
Example style: "**Marriage in 4 years** - limits how much high-volatility equity goes toward that goal." Pick the
inputs that actually mattered most for THIS client (don't force a bullet for something that had no effect).

### Where your wishes and your situation pull in different directions
(include this section only if the JSON 'notes' list is not empty - turn the relevant notes into plain sentences)

### How the three options compare
### What to keep in mind

Keep the whole thing under 320 words. The first section must stay as short bullets, not paragraphs."""


def plan_context(plan):
    """Compact, rounded JSON-safe summary of the plan for the AI."""
    prof = plan["profile"]
    snap = plan["snapshot"]
    goals = []
    for g in plan["goals"]:
        goals.append({
            "name": g["name"], "priority": g.get("priority"), "years_to_go": g["years"], "horizon_bucket": g["bucket"],
            "inflation_category": g.get("inflation_category"),
            "target_in_future_rupees": round(g["target"]) if g["target"] else None,
            "needed_per_month_or_lumpsum": round(g["required"]) if g.get("required") else None,
            "allocated_amount": round(g["funding"]),
            "funded_percent": round(g["funded_ratio"] * 100) if g.get("funded_ratio") is not None else None,
        })
    options = {}
    for name, o in plan["options"].items():
        options[name] = {
            "overall_allocation_percent": o["overall_alloc"],
            "expected_yearly_return_percent": round(o["exp_return"] * 100, 1),
            "typical_yearly_ups_and_downs_percent": round(o["volatility"] * 100, 1),
            "return_in_a_bad_year_percent": round(o["bad_year"] * 100, 1),
            "sharpe_ratio": o["sharpe"],
            "per_goal": [{
                "goal": r["goal"], "equity_percent": r["equity_pct"],
                "chance_of_reaching_target_percent": None if r["prob"] is None else round(r["prob"] * 100),
                "typical_outcome_rupees": round(r["median"]),
                "typical_outcome_as_percent_of_target": None if r["median_pct"] is None else round(r["median_pct"] * 100),
            } for r in o["goals"]],
        }

    financial_profile = {
        "employment_income_known": snap["income_known"],
        "monthly_disposable_income_rupees": round(snap["disposable_income"]) if snap["income_known"] else None,
        "savings_rate_percent": round(snap["savings_rate"] * 100) if snap["savings_rate"] is not None else None,
        "emergency_fund_target_months": snap["emergency_months_target"],
        "emergency_fund_shortfall_rupees": round(snap["emergency_shortfall"]),
        "emergency_fund_topup_from_this_investment": round(plan["emergency_topup"]["funding"]),
        "high_emi_debt_burden": snap["high_emi_burden"],
        "high_interest_debt_reported": snap["high_interest_debt"],
        "existing_equity_share_percent": round(snap["existing_equity_share"] * 100) if snap["existing_equity_share"] is not None else None,
        "has_health_insurance": snap["has_health_insurance"],
        "has_life_insurance": snap["has_life_insurance"],
    }

    return {
        "mode": plan["mode"], "amount_rupees": round(plan["amount"]), "sip_step_up_percent": round(plan["sip_step_up"] * 100, 1),
        "risk": {"score_out_of_10": prof["score"], "label": prof["label"], "willingness": prof["willingness"],
                 "capacity": prof["capacity"], "required_risk_label": prof["required_risk"]["label"],
                 "money_weighted_horizon_years": prof["weighted_horizon_years"]},
        "recommended_option": plan["recommended"], "goals": goals, "options": options,
        "financial_profile": financial_profile, "financial_health_scorecard": plan["financial_health"],
        "notes": plan["notes"], "assumed_inflation": plan["inflation"],
        "return_assumptions": plan["assumptions"], "assumptions_note": plan["assumptions_note"],
    }


def _call_llm(system, messages, api_key, model, max_tokens=900):
    import anthropic  # imported here so the app still runs without the package
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(model=model, max_tokens=max_tokens, system=system, messages=messages)
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def generate_explanation(plan, api_key=None, model=None):
    """Returns (markdown_text, used_ai, error_message)."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return fallback_explanation(plan), False, None
    try:
        ctx = json.dumps(plan_context(plan), indent=1)
        msg = f"Here is the client's plan as JSON:\n{ctx}\n\n{EXPLAIN_INSTRUCTION}"
        text = _call_llm(SYSTEM_PROMPT, [{"role": "user", "content": msg}], api_key, model or DEFAULT_MODEL)
        return text, True, None
    except Exception as e:
        return fallback_explanation(plan), False, f"AI call failed ({type(e).__name__}: {e}). Showing the built-in explanation instead."


def answer_question(plan, history, question, api_key=None, model=None):
    """history: list of {'role','content'}. Returns (answer, used_ai, error)."""
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ("The **Ask the advisor** live chat isn't enabled in this deployment (no AI connection is "
                "configured here). The *Your plan* and *Compare options* tabs above show the full reasoning "
                "and numbers behind your recommendation."), False, None
    try:
        system = SYSTEM_PROMPT + "\n\nThe client's plan (JSON):\n" + json.dumps(plan_context(plan), indent=1)
        msgs = list(history) + [{"role": "user", "content": question}]
        return _call_llm(system, msgs, api_key, model or DEFAULT_MODEL, max_tokens=600), True, None
    except Exception as e:
        return "Sorry, I could not reach the AI service just now.", False, f"{type(e).__name__}: {e}"


# ---------- rule-based fallback (no AI needed) ----------
_BUCKET_REASON = {
    "Short": "the money is needed soon, so it is kept mostly in safer funds (a market fall right before the date could derail the goal)",
    "Medium": "there is some time to recover from dips, so it mixes safer funds with some growth assets",
    "Long": "there is plenty of time to ride out market ups and downs, so growth assets can carry more of the load",
}


def fallback_explanation(plan):
    prof, rec, snap = plan["profile"], plan["recommended"], plan["snapshot"]
    opt = plan["options"][rec]
    lines = ["### Why this fits you",
             f"- **Risk score {prof['score']}/10 ({prof['label']})** - the lower of your comfort with risk "
             f"({prof['willingness']}/10) and what your situation can afford ({prof['capacity']}/10); this profile "
             "drives the mix below."]
    for g, row in zip(plan["goals"], opt["goals"]):
        lines.append(f"- **{g['name']}** ({g['years']:g} years, {g['bucket'].lower()}-term, {g.get('priority', 'Important')} priority) "
                     f"- about {row['equity_pct']:.0f}% in equity, because {_BUCKET_REASON[g['bucket']]}.")
    if plan["emergency_topup"]["funding"] > 0:
        lines.append(f"- **No full emergency fund yet** - Rs {plan['emergency_topup']['funding']:,.0f} of this plan's "
                     "money was set aside first, kept fully liquid, before funding your goals.")
    if snap["high_emi_burden"]:
        lines.append("- **High EMI burden** - this reduces how much market risk your situation can really afford, "
                     "pulling your recommended profile toward the safer side.")
    if plan["notes"]:
        lines += ["", "### Where your wishes and your situation pull in different directions"]
        lines += [f"- {n}" for n in plan["notes"]]
    lines += ["", "### How the three options compare"]
    for name, o in plan["options"].items():
        tag = " (suggested)" if name == rec else ""
        eq = o["overall_alloc"]["Large-cap Equity"] + o["overall_alloc"]["Mid-cap Equity"]
        lines.append(f"- **{name}{tag}:** about {eq:.0f}% in equity overall, expected return around {o['exp_return']*100:.1f}% a year, "
                     f"Sharpe ratio {o['sharpe']:.2f}, and in a bad year roughly {o['bad_year']*100:.1f}%.")
    lines += ["", "### What to keep in mind",
              "These figures are estimates based on stated assumptions, not guarantees. Markets can do better or worse. "
              "This tool is for education and does not replace a registered financial advisor."]
    return "\n".join(lines)
