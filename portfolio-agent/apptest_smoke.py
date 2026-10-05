"""
apptest_smoke.py - drives app.py through its full step flow using Streamlit's AppTest,
to catch runtime errors (as opposed to test_engine.py, which only checks the pure logic).
Run with: python apptest_smoke.py
"""
import sys
from streamlit.testing.v1 import AppTest


def dump_exceptions(at, label):
    if at.exception:
        print(f"\n!!! EXCEPTION at {label} !!!")
        for e in at.exception:
            print(e)
        return True
    return False


def main():
    at = AppTest.from_file("app.py")
    at.run(timeout=30)
    if dump_exceptions(at, "initial load (How it works)"):
        sys.exit(1)
    print("PASS: initial load, title:", at.title[0].value if at.title else "(none)")

    # Step 0 -> 1: click "Build my plan"
    at.button(key="intro_start").click().run(timeout=30)
    if dump_exceptions(at, "after intro click"):
        sys.exit(1)
    print("PASS: moved to About you")

    # Step 1: About you - set age/dependents, enable retirement, enable sole earner
    at.number_input(key="w_age").set_value(30).run(timeout=30)
    at.number_input(key="w_deps").set_value(2).run(timeout=30)
    if dump_exceptions(at, "About you inputs"):
        sys.exit(1)
    # sole earner checkbox should now be visible since deps > 0
    sole_keys = [cb.key for cb in at.checkbox]
    print("Checkboxes visible on About you:", sole_keys)
    if "w_sole" in sole_keys:
        at.checkbox(key="w_sole").set_value(True).run(timeout=30)
    at.button(key="next0").click().run(timeout=30)
    if dump_exceptions(at, "About you -> Financial life"):
        sys.exit(1)
    print("PASS: moved to Financial life")

    # Step 2: Financial life
    at.selectbox(key="w_employment").set_value("Self-employed / business owner").run(timeout=30)
    at.number_input(key="w_income").set_value(60000).run(timeout=30)
    at.number_input(key="w_expenses").set_value(35000).run(timeout=30)
    at.number_input(key="w_emi").set_value(10000).run(timeout=30)
    if dump_exceptions(at, "Financial life after emi"):
        sys.exit(1)
    emi_high_keys = [cb.key for cb in at.checkbox]
    print("Checkboxes visible on Financial life (after EMI>0):", emi_high_keys)
    if "w_emi_high" in emi_high_keys:
        at.checkbox(key="w_emi_high").set_value(True).run(timeout=30)
    at.number_input(key="w_existing_equity").set_value(200000).run(timeout=30)
    at.number_input(key="w_existing_other").set_value(50000).run(timeout=30)
    at.number_input(key="w_emergency").set_value(10000).run(timeout=30)
    at.radio(key="w_liquidity").set_value("Significant").run(timeout=30)
    health_keys = [cb.key for cb in at.checkbox]
    print("Checkboxes visible (protection check, deps>0):", health_keys)
    if "w_health_ins" in health_keys:
        at.checkbox(key="w_health_ins").set_value(False).run(timeout=30)
    if dump_exceptions(at, "Financial life full fill"):
        sys.exit(1)
    at.button(key="next_fl").click().run(timeout=30)
    if dump_exceptions(at, "Financial life -> Money & goals"):
        sys.exit(1)
    print("PASS: moved to Money & goals")

    # Step 3: Money & goals (keep default goal row from init_state, just set mode/amount/step-up)
    at.radio(key="w_mode").set_value("SIP (monthly)").run(timeout=30)
    at.number_input(key="w_amount").set_value(15000).run(timeout=30)
    slider_keys = [s.key for s in at.slider]
    print("Sliders visible on Money & goals:", slider_keys)
    if "w_stepup" in slider_keys:
        at.slider(key="w_stepup").set_value(10).run(timeout=30)
    if dump_exceptions(at, "Money & goals fill"):
        sys.exit(1)
    at.button(key="next1").click().run(timeout=30)
    if dump_exceptions(at, "Money & goals -> Risk comfort"):
        sys.exit(1)
    print("PASS: moved to Risk comfort")

    # Step 4: Risk comfort
    at.radio(key="w_stated").set_value("High").run(timeout=30)
    at.radio(key="w_q0").set_value(at.radio(key="w_q0").options[2]).run(timeout=30)
    at.radio(key="w_q1").set_value(at.radio(key="w_q1").options[2]).run(timeout=30)
    at.radio(key="w_q2").set_value(at.radio(key="w_q2").options[2]).run(timeout=30)
    if dump_exceptions(at, "Risk comfort fill"):
        sys.exit(1)
    at.button(key="next2").click().run(timeout=30)
    if dump_exceptions(at, "Risk comfort -> Review"):
        sys.exit(1)
    print("PASS: moved to Review")
    print("Review warnings/errors shown:", [w.value for w in at.warning] + [e.value for e in at.error])

    at.button(key="next3").click().run(timeout=30)
    if dump_exceptions(at, "Review -> Results"):
        sys.exit(1)
    print("PASS: moved to Results (final plan page)")
    print("Metrics on results page:", [m.value for m in at.metric][:8])

    # Exercise the what-if slider and the advanced-risk-analysis expander on the results page
    expander_labels = [exp.label for exp in at.expander]
    print("Expanders present on results page:", expander_labels)

    print("\nALL APPTEST STEPS COMPLETED WITHOUT EXCEPTION.")


if __name__ == "__main__":
    main()
