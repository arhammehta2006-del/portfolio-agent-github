# Bonus: live-demo JS artifact (not the primary submission)

This folder is the source for the zero-setup live demo:
https://claude.ai/artifact/Uqyro7k5BdMbkatJnLopLm

It's a faithful JavaScript port of `../risk.py` + `../allocation.py` (see `../ARCHITECTURE.md`
and `../TEST_REPORT.md` section 4), wrapped in a self-contained wizard UI, published as a Claude
Artifact. The Python/Streamlit app one level up is the primary submitted prototype — this is
included only so the link above can be reproduced/audited, and so the source for its free
Claude-powered "Ask the advisor" agent is on hand if asked about at the demo.

- `logic.js` — the ported deterministic engine
- `app.js` — the wizard UI + the tool-use agent (`sample` capability) + the download feature
- `index.html` — page shell (styling, theme tokens)
- `test_logic.js` — 22 checks on the ported engine (`node test_logic.js`)
- `smoke_test.js` — 29 end-to-end checks on the assembled wizard via jsdom (`node smoke_test.js`,
  needs `npm install jsdom` first)
