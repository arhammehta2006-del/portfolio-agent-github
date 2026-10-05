# AI-Use Declaration

AI was used in **two distinct ways** on this project — as a development tool while building it,
and optionally as a runtime feature inside the finished app. These are kept separate below because
they matter differently for grading the "model/data/prompt design" criterion.

## 1. AI as a development tool (how this codebase was built)

**Tool used:** Claude (Anthropic), via Claude Code, an AI coding assistant.

**What it was used for:** writing and modifying the Python code (`app.py`, `risk.py`,
`allocation.py`, `advisor.py`, `config.py`), writing the automated tests
(`test_engine.py`, `apptest_smoke.py`, `apptest_smoke2.py`), writing this documentation set, and
building the bonus JavaScript artifact (`logic.js`, `app.js`) as a faithful port of the same logic
for a zero-setup live demo.

**What was NOT delegated to AI:** the problem definition, target customer (first-time Indian
retail investors, 22–40), the choice of what the tool should and shouldn't do, which of the
project's requested features to prioritise under time constraints (the human team reviewed the
full 94-item spec and the resulting `CHANGES_BACKLOG.md` triage), and verification that the
numbers the engine produces are sane — every change was checked against automated tests before
being accepted, and this submission pass additionally included a manual screenshot review that
caught and fixed a real rendering bug (see `TEST_REPORT.md`, "A real bug found and fixed").

**How outputs were verified:** `test_engine.py` (10 test cases against the deterministic engine),
`apptest_smoke.py`/`apptest_smoke2.py` (2 full end-to-end UI runs via Streamlit's `AppTest`), and
a manual Playwright-driven screenshot walkthrough of the live app — see `TEST_REPORT.md` for full
results. Nothing in this submission is AI output that went unchecked.

## 2. AI as a runtime feature (what the deployed app itself does with AI)

**Design principle, enforced throughout:** the AI layer only *explains* numbers the deterministic
engine has already computed. It never performs a calculation, and the app is fully functional with
it switched off.

- **Python app (`advisor.py`):** if an `ANTHROPIC_API_KEY` is set server-side (an environment
  variable, or a Streamlit Cloud "secret" when deployed — never a box the visitor types into), the
  app calls the Claude API to turn the engine's computed numbers into plain-English reasoning chips
  and a narrative, and to answer follow-up questions in "Ask the advisor." With no key set (the
  default — no one needs an API key, or to pay anything, to use or grade this app), a deterministic
  rule-based template produces an equivalent explanation instead, and "Ask the advisor" says plainly
  that live chat isn't enabled in this deployment. The prompt passed to Claude includes only the
  pre-computed plan data (never raw financial instructions) and an explicit instruction not to
  invent numbers.
- **Bonus JS artifact (`app.js`):** the "Ask the advisor" tab optionally calls Claude live through
  the Claude Artifact platform's `sample` capability — free to use (billed to the viewer's own
  Claude session, not a project API key). This goes one step further architecturally: Claude is
  given **tools** onto the page's own functions (`estimate_required_return`, `get_goal_status`) and
  decides for itself when to call them to get a new number, rather than being asked to estimate one
  in prose — a genuine tool-use agent pattern. If that capability is unavailable in a given view
  (e.g. opened outside claude.ai, or the viewer declines the permission prompt), it falls back to a
  template pointer instead of breaking; this fallback path is covered by `smoke_test.js`.

## Model used

Claude (Anthropic) throughout — both for development assistance and, optionally, at runtime in the
deployed app (model set by `advisor.DEFAULT_MODEL`/`ANTHROPIC_MODEL`, server-side only, in the Python
app; the Claude Artifact uses whichever model the viewer's own Claude account is on).
