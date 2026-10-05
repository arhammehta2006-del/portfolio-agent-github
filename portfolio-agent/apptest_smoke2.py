"""apptest_smoke2.py - second branch: no dependents, Lumpsum mode, Student employment."""
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
    at.button(key="intro_start").click().run(timeout=30)

    # dependents = 0 -> sole-earner checkbox should NOT appear
    at.number_input(key="w_age").set_value(21).run(timeout=30)
    at.number_input(key="w_deps").set_value(0).run(timeout=30)
    keys = [cb.key for cb in at.checkbox]
    print("Checkboxes with 0 dependents (expect NO w_sole):", keys)
    assert "w_sole" not in keys, "w_sole should be hidden when dependents == 0"
    at.checkbox(key="w_has_ret").set_value(False).run(timeout=30)   # no retirement planning
    at.button(key="next0").click().run(timeout=30)
    if dump_exceptions(at, "About you (branch 2)"):
        sys.exit(1)

    at.selectbox(key="w_employment").set_value("Student").run(timeout=30)
    print("Income label widget present:", "w_income" in [n.key for n in at.number_input])
    at.number_input(key="w_income").set_value(0).run(timeout=30)
    at.number_input(key="w_expenses").set_value(15000).run(timeout=30)
    # emi = 0 -> emi_high checkbox should not appear
    keys2 = [cb.key for cb in at.checkbox]
    print("Checkboxes with EMI=0 (expect NO w_emi_high):", keys2)
    assert "w_emi_high" not in keys2, "w_emi_high should be hidden when EMI == 0"
    # dependents = 0 -> protection-check checkboxes should not appear
    assert "w_health_ins" not in keys2 and "w_life_ins" not in keys2, "insurance checkboxes should be hidden when dependents == 0"
    at.button(key="next_fl").click().run(timeout=30)
    if dump_exceptions(at, "Financial life (branch 2)"):
        sys.exit(1)

    at.radio(key="w_mode").set_value("Lumpsum").run(timeout=30)
    at.number_input(key="w_amount").set_value(50000).run(timeout=30)
    slider_keys = [s.key for s in at.slider]
    print("Sliders with Lumpsum mode (expect NO w_stepup):", slider_keys)
    assert "w_stepup" not in slider_keys, "step-up slider should be hidden for Lumpsum mode"
    if dump_exceptions(at, "Money & goals (branch 2)"):
        sys.exit(1)
    at.button(key="next1").click().run(timeout=30)

    at.radio(key="w_stated").set_value("Low").run(timeout=30)
    at.radio(key="w_q0").set_value(at.radio(key="w_q0").options[0]).run(timeout=30)
    at.radio(key="w_q1").set_value(at.radio(key="w_q1").options[0]).run(timeout=30)
    at.radio(key="w_q2").set_value(at.radio(key="w_q2").options[0]).run(timeout=30)
    at.button(key="next2").click().run(timeout=30)
    if dump_exceptions(at, "Risk comfort (branch 2)"):
        sys.exit(1)

    print("Review warnings (branch 2):", [w.value for w in at.warning])
    at.button(key="next3").click().run(timeout=30)
    if dump_exceptions(at, "Results (branch 2)"):
        sys.exit(1)
    print("PASS: branch 2 (no dependents, lumpsum, student) reached Results cleanly.")
    print("Metrics:", [m.value for m in at.metric][:8])


if __name__ == "__main__":
    main()
