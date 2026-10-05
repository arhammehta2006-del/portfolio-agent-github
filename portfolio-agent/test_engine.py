"""
test_engine.py - automated checks for the expanded risk/allocation engine.
Run with:  python test_engine.py
No pytest dependency needed (keeps it runnable in any Python 3 env for the viva).
"""
import sys
import traceback

import allocation as A
import risk as R
import config as C

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def base_input(**overrides):
    inp = {
        "age": 28, "dependents": 0, "has_retirement": True, "retirement_age": 60, "monthly_expenses": 40000,
        "mode": "SIP (monthly)", "amount": 20000, "stated_risk": "Moderate", "quiz": [6, 6, 6],
        "goals": [{"name": "Vacation", "cost": 150000, "years": 2, "priority": "Important", "inflation_category": "Travel"}],
        "employment": "Salaried", "monthly_income": 0, "emi_total": 0, "emi_high_interest": False,
        "existing_equity": 0, "existing_other": 0, "emergency_savings": 0,
        "has_health_insurance": True, "has_life_insurance": True, "sole_earner": False,
        "liquidity_need": "Some", "sip_step_up": 0.0,
    }
    inp.update(overrides)
    return inp


def run_case(name, inp, override=None, mult=1.0):
    print(f"\n=== {name} ===")
    errors, warnings = R.validate(inp)
    print("  errors:", errors)
    print("  warnings:", warnings)
    plan = A.build_plan(inp, override=override, amount_mult=mult)
    return plan


def sums_to_100(alloc_dict, tol=0.6):
    return abs(sum(alloc_dict.values()) - 100.0) <= tol


def main():
    # ---- TC1: minimal defaults (user skips the whole financial-life step) ----
    inp1 = base_input()
    p1 = run_case("TC1 minimal defaults", inp1)
    check("TC1 overall alloc sums to 100 for every option",
          all(sums_to_100(o["overall_alloc"]) for o in p1["options"].values()))
    check("TC1 emergency fund not assessed when expenses present but no stated target gap avoided crash",
          p1["financial_health"]["Emergency Fund"] in ("Good", "Needs Attention", "At Risk", "Not assessed"))
    check("TC1 required risk label computed without crashing", p1["profile"]["required_risk"]["label"] is not None)

    # ---- TC2: emergency fund shortfall should be carved out first ----
    inp2 = base_input(monthly_expenses=30000, emergency_savings=0, employment="Self-employed / business owner",
                       amount=25000, mode="SIP (monthly)")
    p2 = run_case("TC2 emergency fund shortfall (self-employed, no buffer)", inp2)
    months, target = R.emergency_fund_target(inp2)
    check("TC2 emergency target uses self-employed months", months == C.EMERGENCY_MONTHS_BASE["Self-employed / business owner"],
          f"got {months}")
    check("TC2 top-up amount > 0 since no savings exist", p2["emergency_topup"]["funding"] > 0,
          p2["emergency_topup"])
    check("TC2 top-up capped at available amount", p2["emergency_topup"]["funding"] <= inp2["amount"] + 1e-6)
    check("TC2 a note about the emergency top-up appears", any("emergency fund" in n.lower() for n in p2["notes"]))

    # ---- TC3: high EMI burden + SIP exceeding disposable income ----
    inp3 = base_input(monthly_income=50000, monthly_expenses=30000, emi_total=25000, emi_high_interest=True,
                       amount=10000, mode="SIP (monthly)")
    errors3, warnings3 = R.validate(inp3)
    check("TC3 high EMI burden warning fires", any("debt burden" in w.lower() for w in warnings3), warnings3)
    check("TC3 SIP-vs-disposable-income warning fires",
          any("disposable income" in w.lower() for w in warnings3), warnings3)
    p3 = run_case("TC3 high EMI burden", inp3)
    check("TC3 high-interest debt note appears", any("high-interest debt" in n.lower() for n in p3["notes"]))
    check("TC3 debt level flagged in financial health", p3["financial_health"]["Debt Level"] == "Needs Attention")

    # ---- TC4: existing portfolio already equity-heavy -> new money tilts away from equity ----
    inp4a = base_input(existing_equity=800000, existing_other=200000, amount=15000)
    inp4b = base_input(existing_equity=0, existing_other=0, amount=15000)
    p4a = run_case("TC4a existing equity-heavy (80%)", inp4a)
    p4b = run_case("TC4b no existing holdings (baseline)", inp4b)
    rec = p4a["recommended"]
    eq_a = p4a["options"][rec]["overall_alloc"]["Large-cap Equity"] + p4a["options"][rec]["overall_alloc"]["Mid-cap Equity"]
    eq_b = p4b["options"][p4b["recommended"]]["overall_alloc"]["Large-cap Equity"] + p4b["options"][p4b["recommended"]]["overall_alloc"]["Mid-cap Equity"]
    check("TC4 existing-equity-heavy client gets LOWER new-money equity share than baseline", eq_a < eq_b,
          f"with-existing={eq_a} baseline={eq_b}")
    check("TC4 a note explains the tilt", any("tilted" in n.lower() for n in p4a["notes"]))

    # ---- TC5: goal priority changes funding order under a budget constraint ----
    inp5 = base_input(amount=5000, has_retirement=False, goals=[
        {"name": "Big Aspirational Trip", "cost": 500000, "years": 1, "priority": "Aspirational", "inflation_category": "Travel"},
        {"name": "Essential Medical Buffer", "cost": 500000, "years": 1, "priority": "Essential", "inflation_category": "Healthcare"},
    ])
    p5 = run_case("TC5 priority-based funding order", inp5)
    essential = next(g for g in p5["goals"] if g["name"] == "Essential Medical Buffer")
    aspirational = next(g for g in p5["goals"] if g["name"] == "Big Aspirational Trip")
    check("TC5 Essential goal gets funded before Aspirational despite same date",
          essential["funding"] >= aspirational["funding"],
          f"essential={essential['funding']} aspirational={aspirational['funding']}")

    # ---- TC6: step-up SIP reduces the required starting contribution vs a flat SIP ----
    inp6_flat = base_input(amount=100000, mode="SIP (monthly)", sip_step_up=0.0, has_retirement=False,
                            goals=[{"name": "House", "cost": 3000000, "years": 10, "priority": "Important", "inflation_category": "Housing"}])
    inp6_step = base_input(amount=100000, mode="SIP (monthly)", sip_step_up=0.10, has_retirement=False,
                            goals=[{"name": "House", "cost": 3000000, "years": 10, "priority": "Important", "inflation_category": "Housing"}])
    p6_flat = run_case("TC6a flat SIP", inp6_flat)
    p6_step = run_case("TC6b step-up SIP (10%/yr)", inp6_step)
    req_flat = next(g for g in p6_flat["goals"] if g["name"] == "House")["required"]
    req_step = next(g for g in p6_step["goals"] if g["name"] == "House")["required"]
    check("TC6 step-up SIP needs a SMALLER first-month contribution than a flat SIP for the same target",
          req_step < req_flat, f"flat={req_flat:.0f} step_up={req_step:.0f}")

    # ---- TC7: goal-specific inflation (Education should inflate a target faster than General) ----
    inp7 = base_input(has_retirement=False, goals=[
        {"name": "Education Goal", "cost": 1000000, "years": 10, "priority": "Essential", "inflation_category": "Education"},
        {"name": "General Goal", "cost": 1000000, "years": 10, "priority": "Essential", "inflation_category": "General"},
    ])
    goals7 = R.build_goals(inp7)
    edu = next(g for g in goals7 if g["name"] == "Education Goal")
    gen = next(g for g in goals7 if g["name"] == "General Goal")
    check("TC7 Education-category goal inflates to a HIGHER future target than General for the same cost/years",
          edu["target"] > gen["target"], f"edu={edu['target']:.0f} gen={gen['target']:.0f}")

    # ---- TC8: aggressive + retirement within 10 years triggers a de-risking note ----
    inp8 = base_input(age=52, retirement_age=60, stated_risk="High", quiz=[10, 10, 10], monthly_expenses=50000,
                       goals=[])
    p8 = run_case("TC8 near-retirement aggressive flag", inp8, override="Aggressive")
    check("TC8 near-retirement high-equity note appears when viewing Aggressive",
          any("retirement" in n.lower() and "closer" in n.lower() for n in p8["notes"]), p8["notes"])

    # ---- TC9: Sharpe ratio and stress_decline are present and sane ----
    p9 = p1
    for name, o in p9["options"].items():
        check(f"TC9 {name} has a finite Sharpe ratio", isinstance(o["sharpe"], float))
        check(f"TC9 {name} stress_decline <= bad_year (a stress scenario should be at least as bad)",
              o["stress_decline"] <= o["bad_year"] + 1e-9, f"{name}: stress={o['stress_decline']} bad_year={o['bad_year']}")

    # ---- TC10: lumpsum mode still works end to end (no SIP-specific crash) ----
    inp10 = base_input(mode="Lumpsum", amount=500000)
    p10 = run_case("TC10 lumpsum mode", inp10)
    check("TC10 lumpsum plan builds without error and sums to 100",
          all(sums_to_100(o["overall_alloc"]) for o in p10["options"].values()))

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED:")
        for f in FAILURES:
            print("  -", f)
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("\nUNHANDLED EXCEPTION:")
        traceback.print_exc()
        sys.exit(1)
