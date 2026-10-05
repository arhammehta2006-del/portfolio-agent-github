/* Lakshya — wizard UI + results rendering. Pure DOM string-rendering, no framework.
   Delegated via a global `App` object referenced from inline handlers in the rendered HTML
   (simplest reliable pattern for a single self-contained artifact page). */
(function () {
  const L = window.Lakshya;
  const STEPS = ["How it works", "About you", "Financial life", "Money & goals", "Risk comfort", "Review", "Your plan"];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function fmtINR(n) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    const neg = n < 0; n = Math.abs(Math.round(n));
    return (neg ? "-" : "") + "₹" + n.toLocaleString("en-IN");
  }
  function fmtPct(x, d) {
    if (x === null || x === undefined || isNaN(x)) return "—";
    return (x * 100).toFixed(d === undefined ? 1 : d) + "%";
  }
  function fmtNum(x, d) {
    if (x === null || x === undefined || isNaN(x)) return "—";
    return x.toFixed(d === undefined ? 1 : d);
  }
  function statusTone(s) {
    if (["Good", "On Track", "Strong", "Healthy"].includes(s)) return "good";
    if (["Needs Attention", "Behind Target", "Moderate"].includes(s)) return "warn";
    if (["At Risk", "Significantly Behind", "Low"].includes(s)) return "bad";
    return "muted";
  }
  function dot(tone) { return { good: "🟢", warn: "🟡", bad: "🔴", muted: "⚪" }[tone] || "⚪"; }
  const ASSET_COLORS = { "Liquid Fund": "var(--c-liquid)", "Debt Fund": "var(--c-debt)", "Gold": "var(--c-gold)", "Large-cap Equity": "var(--c-lc)", "Mid-cap Equity": "var(--c-mc)" };

  function freshGoal() { return { name: "", cost: "", years: "", priority: "Important", inflationCategory: "General" }; }

  const state = {
    step: 0,
    maxStepReached: 0,
    inputs: {
      age: 28, dependents: 0, hasRetirement: true, retirementAge: 60,
      soleEarner: false, employment: "Salaried", monthlyIncome: "", monthlyExpenses: "",
      emiTotal: "", emiHighInterest: false, existingEquity: "", existingOther: "",
      emergencySavings: "", liquidityNeed: "Some", hasHealthInsurance: true, hasLifeInsurance: true,
      mode: "SIP (monthly)", amount: "", sipStepUp: 0,
      goals: [freshGoal()],
      statedRisk: "Moderate", quiz: [6, 6, 6],
    },
    quizChoice: [null, null, null],
    stepError: "",
    plan: null,
    override: null,
    reviewWarnings: [],
    activeTab: "tracker",
    whatIf: { goalIdx: 0, amount: "", years: "" },
    advisorLog: [],
    advisorBusy: false,
  };

  // ============================================================ runtime capabilities (sample + downloads)
  // Free to use: billed to the viewer's own Claude session, not to any API key the team would pay for.
  // Resolves to null outside a claude.ai artifact viewer (e.g. this file opened directly, or under Node
  // for testing) — every call site below is written to degrade to a deterministic fallback on null.
  let sampleCap = null;
  let downloadsCap = null;
  async function initCaps() {
    if (typeof window === "undefined" || !window.claude || typeof window.claude.use !== "function") return;
    try { sampleCap = await window.claude.use("sample"); } catch (e) { sampleCap = null; }
    try { downloadsCap = await window.claude.use("downloads"); } catch (e) { downloadsCap = null; }
    render();
  }

  function setField(key, value, kind) {
    if (kind === "num") value = value === "" ? "" : parseFloat(value);
    state.inputs[key] = value;
    render();
  }
  function toggleField(key) { state.inputs[key] = !state.inputs[key]; render(); }
  function setChoice(key, value) { state.inputs[key] = value; render(); }
  function setGoalField(idx, key, value, kind) {
    if (kind === "num") value = value === "" ? "" : parseFloat(value);
    state.inputs.goals[idx][key] = value;
    render();
  }
  function addGoal() { state.inputs.goals.push(freshGoal()); render(); }
  function removeGoal(idx) { state.inputs.goals.splice(idx, 1); render(); }
  function setQuiz(qIdx, optIdx, points) { state.quizChoice[qIdx] = optIdx; state.inputs.quiz[qIdx] = points; render(); }

  function goStep(i) { state.step = i; state.stepError = ""; window.scrollTo(0, 0); render(); }
  function next() {
    const err = validateStep(state.step);
    if (err) { state.stepError = err; render(); return; }
    state.stepError = "";
    if (state.step === 5) { // Review -> build plan
      const inp = state.inputs;
      const { errors, warnings } = L.validateInputs(inp);
      if (errors.length) { state.stepError = errors.join(" "); render(); return; }
      state.reviewWarnings = warnings;
      state.override = null;
      state.plan = L.buildPlan(inp);
      state.activeTab = "tracker";
    }
    state.step = Math.min(STEPS.length - 1, state.step + 1);
    state.maxStepReached = Math.max(state.maxStepReached, state.step);
    window.scrollTo(0, 0);
    render();
  }
  function back() { state.stepError = ""; state.step = Math.max(0, state.step - 1); window.scrollTo(0, 0); render(); }

  function validateStep(i) {
    const inp = state.inputs;
    if (i === 1) {
      if (!inp.age || inp.age < 18 || inp.age > 70) return "Please enter an age between 18 and 70.";
      if (inp.hasRetirement && (!inp.retirementAge || inp.retirementAge <= inp.age)) return "Retirement age must be greater than your current age.";
    }
    if (i === 2) {
      if (inp.monthlyExpenses === "" || inp.monthlyExpenses === null || isNaN(inp.monthlyExpenses) || inp.monthlyExpenses < 0) return "Please enter your monthly expenses.";
    }
    if (i === 3) {
      if (!inp.amount || inp.amount <= 0) return "Please enter an investable amount greater than zero.";
    }
    return "";
  }

  function setOverride(name) {
    state.override = name === state.plan.profile.label ? null : name;
    state.plan = L.buildPlan(state.inputs, state.override || null);
    render();
  }

  function setTab(t) { state.activeTab = t; render(); }

  function runWhatIf() {
    const g = state.plan.goals[state.whatIf.goalIdx];
    const amount = parseFloat(state.whatIf.amount) || 0;
    const years = parseFloat(state.whatIf.years) || g.years;
    if (!g.target || amount <= 0 || years <= 0) { state.whatIf.result = "Enter a positive amount and years to see the required growth rate."; render(); return; }
    const sip = state.plan.mode.startsWith("SIP");
    const req = L.requiredReturn(amount, g.target, years, sip, state.plan.sipStepUp);
    state.whatIf.result = `To reach ${fmtINR(g.target)} for '${esc(g.name)}' with ${sip ? "a monthly SIP of" : "a lump sum of"} ${fmtINR(amount)} over ${years} years, you'd need roughly ${fmtPct(req, 1)} annualised growth.`;
    render();
  }

  const ADVISOR_FAQ = [
    { q: "Why this risk profile?", a: (p) => `Your profile follows the lower of your comfort with risk (${p.profile.willingness}/10) and what your situation can support (${p.profile.capacity}/10), giving a score of ${p.profile.score}/10 — ${p.recommended}. See 'Why this fits' above for the full breakdown.` },
    { q: "What if I invest more each month?", a: (p) => `Investing more shortens how long each goal takes to reach its target, or raises the odds of hitting it on time. Use the What-if tab to test a specific number.` },
    { q: "Is this guaranteed?", a: () => `No. All figures are estimates from historical-style assumptions, not guarantees — markets can underperform or outperform these assumptions in any given period. This tool is educational, not personalised financial advice.` },
    { q: "What about taxes?", a: () => `This plan does not account for capital gains tax, STT, or other taxes on withdrawals, which will reduce your actual take-home proceeds. Please factor this in separately or consult a tax advisor.` },
    { q: "How often should I review this?", a: () => `At least once a year, and any time your income, expenses, dependents, or goals change materially.` },
  ];
  function askAdvisor(i) {
    const item = ADVISOR_FAQ[i];
    state.advisorLog.push({ q: item.q, a: item.a(state.plan) });
    render();
  }

  // ---- real agent: gives Claude tools onto this page's own deterministic engine, so it computes
  // new numbers by calling L.requiredReturn() etc itself rather than guessing them in free text.
  function advisorTools() {
    const p = state.plan;
    return [
      {
        name: "estimate_required_return",
        description: "Computes the annualised growth rate needed to reach one of the user's goals (by exact name) with a hypothetical contribution amount and number of years. Returns {requiredAnnualReturnPct, goalTargetRupees}, or {error} if the goal has no fixed rupee target.",
        inputSchema: {
          type: "object",
          properties: {
            goalName: { type: "string", description: "Exact goal name from the user's plan." },
            amount: { type: "number", description: p.mode.startsWith("SIP") ? "Hypothetical monthly SIP amount in rupees." : "Hypothetical lump sum amount in rupees." },
            years: { type: "number", description: "Hypothetical number of years to the goal." },
          },
          required: ["goalName", "amount", "years"],
        },
        execute: (input) => {
          const g = p.goals.find((x) => x.name === String(input.goalName));
          if (!g || g.target == null) return { error: "No goal with that exact name has a fixed rupee target. Known goals with targets: " + p.goals.filter((x) => x.target != null).map((x) => x.name).join(", ") };
          const amount = Number(input.amount), years = Number(input.years);
          if (!(amount > 0) || !(years > 0)) return { error: "amount and years must both be positive numbers." };
          const sip = p.mode.startsWith("SIP");
          const req = L.requiredReturn(amount, g.target, years, sip, p.sipStepUp);
          return { requiredAnnualReturnPct: Math.round(req * 1000) / 10, goalTargetRupees: Math.round(g.target) };
        },
      },
      {
        name: "get_goal_status",
        description: "Returns the current funding status for one of the user's goals by exact name: rupee target, funding allocated, percent funded, years to go, and priority. Use this before answering any question about how a specific goal is doing.",
        inputSchema: { type: "object", properties: { goalName: { type: "string" } }, required: ["goalName"] },
        execute: (input) => {
          const g = p.goals.find((x) => x.name === String(input.goalName));
          if (!g) return { error: "No goal with that exact name. Known goals: " + p.goals.map((x) => x.name).join(", ") };
          return {
            years: g.years, priority: g.priority,
            target: g.target != null ? Math.round(g.target) : null,
            funding: Math.round(g.funding),
            fundedPct: g.fundedRatio != null ? Math.round(g.fundedRatio * 1000) / 10 : null,
          };
        },
      },
    ];
  }

  function buildAdvisorPrompt(question) {
    return `You are a careful, plain-English financial explainer embedded in Lakshya, an educational goal-based `
      + `investing app for first-time Indian retail investors. You are NOT a SEBI-registered investment adviser `
      + `and must never invent new personalised advice — only explain numbers this app's deterministic engine has `
      + `already computed, and call the provided tools to get any new what-if number instead of guessing one. `
      + `Keep the answer under 120 words, plain language, use the ₹ symbol for rupees, no markdown tables.\n\n`
      + `Here is the user's current plan:\n${planSummaryText()}\n\nUser question: ${question}`;
  }

  function fallbackAdvisorAnswer(q) {
    return `Live AI answers aren't available in this view right now, so here's a general pointer instead: try the `
      + `What-if tab to test a specific amount or timeline, or check "Why this fits you" and the notes above — most `
      + `plan-specific questions are already covered there. (Your question: "${q}")`;
  }

  let streamingAnswer = null; // { q, text } while a live call is in flight
  function updateStreamingDom() {
    const el = document.getElementById("liveAnswer");
    if (el && streamingAnswer) el.textContent = streamingAnswer.text;
  }

  async function askFree() {
    const box = document.getElementById("advisorInput");
    const q = box ? box.value.trim() : "";
    if (!q || state.advisorBusy) return;
    if (box) box.value = "";

    if (!sampleCap) {
      state.advisorLog.push({ q, a: fallbackAdvisorAnswer(q) });
      render();
      return;
    }

    state.advisorBusy = true;
    streamingAnswer = { q, text: "Thinking…" };
    render();
    try {
      const res = await sampleCap(buildAdvisorPrompt(q), {
        modelTier: "quick",
        tools: advisorTools(),
        onText: ({ text }) => { streamingAnswer.text = text; updateStreamingDom(); },
      });
      state.advisorLog.push({ q, a: res.text });
    } catch (e) {
      const kept = e && e.text ? e.text : null;
      if (e && e.code === "not_granted") {
        state.advisorLog.push({ q, a: fallbackAdvisorAnswer(q) });
      } else {
        state.advisorLog.push({ q, a: (kept || fallbackAdvisorAnswer(q)) + (kept ? "" : "\n\n(Live AI answer failed — showing a general pointer instead.)") });
      }
    }
    streamingAnswer = null;
    state.advisorBusy = false;
    render();
  }

  function planSummaryText() {
    const p = state.plan, inp = state.inputs;
    const lines = [];
    lines.push("LAKSHYA — GOAL-BASED PORTFOLIO PLAN");
    lines.push("Generated: " + new Date().toLocaleString("en-IN"));
    lines.push("");
    lines.push(`Investor: age ${inp.age}, ${inp.dependents} dependent(s), ${inp.employment}`);
    lines.push(`Investing: ${p.mode}, ${fmtINR(p.amount)}${p.mode.startsWith("SIP") ? "/month" : ""}`);
    lines.push(`Recommended profile: ${p.recommended} (score ${p.profile.score}/10)`);
    lines.push("");
    lines.push("GOALS");
    p.goals.forEach((g) => {
      lines.push(`- ${g.name} (${g.years} yrs, ${g.priority}): target ${fmtINR(g.target)}, funding ${fmtINR(g.funding)}${p.mode.startsWith("SIP") ? "/mo" : ""}, funded ${g.fundedRatio != null ? fmtPct(g.fundedRatio, 0) : "n/a"}`);
    });
    lines.push("");
    lines.push("RECOMMENDED OVERALL ALLOCATION");
    const rec = p.options[p.recommended];
    Object.entries(rec.overallAlloc).forEach(([k, v]) => lines.push(`- ${k}: ${v}%`));
    lines.push("");
    lines.push("NOTES");
    p.notes.forEach((n) => lines.push("- " + n));
    lines.push("");
    lines.push("Educational prototype, not personalised financial advice.");
    return lines.join("\n");
  }

  async function download(btn) {
    const text = planSummaryText();
    const label = btn ? btn.textContent : null;
    const restore = () => { if (btn && label) btn.textContent = label; };

    if (downloadsCap) {
      try {
        await downloadsCap.save({ filename: "lakshya-plan-summary.txt", data: text });
        if (btn) { btn.textContent = "Saved ✓"; setTimeout(restore, 1800); }
        return;
      } catch (e) {
        if (e && e.code === "declined") return; // viewer said no — nothing more to do
        // any other failure (e.g. unavailable in this view) falls through to the clipboard fallback below
      }
    }

    const fail = () => {
      const ta = document.getElementById("planSummaryBox");
      if (ta) { ta.hidden = false; ta.focus(); ta.select(); }
      if (btn) btn.textContent = "Select the text below and copy";
      setTimeout(restore, 2500);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        if (btn) btn.textContent = "Copied ✓";
        setTimeout(restore, 1800);
      }).catch(fail);
    } else fail();
  }

  // ============================================================ RENDER: step shells
  function renderSteprail() {
    const rail = STEPS.map((_, i) => {
      const cls = i < state.step ? "done" : i === state.step ? "current" : "";
      return `<div class="seg ${cls}"></div>`;
    }).join("");
    document.getElementById("steprail").innerHTML = rail;
    document.getElementById("stepcaption").textContent = `Step ${state.step + 1} of ${STEPS.length} — ${STEPS[state.step]}`;
    document.getElementById("topHint").textContent = state.step === 6 ? "Your plan" : "Lakshya helps you plan";
  }

  function errorBanner() { return state.stepError ? `<div class="banner err">${esc(state.stepError)}</div>` : ""; }

  function render() {
    renderSteprail();
    const app = document.getElementById("app");
    const fns = [renderIntro, renderAboutYou, renderFinancialLife, renderMoneyGoals, renderRiskComfort, renderReview, renderResults];
    app.innerHTML = `<div class="step-enter">${fns[state.step]()}</div>`;
  }

  // ---- Step 0: Intro
  function renderIntro() {
    return `
      <div class="card">
        <h1>Plan your money, your way.</h1>
        <p>Tell us a bit about your life, your goals, and how you feel about risk. Lakshya works out a
        goal-based investment plan with real numbers — how much to invest, where it should go, and the
        odds of getting there — in about three minutes.</p>
        <p class="muted">Everything stays on this page. Nothing is uploaded or shared.</p>
      </div>
      <div class="actions"><button class="primary" onclick="App.next()">Get started</button></div>`;
  }

  // ---- Step 1: About you
  function renderAboutYou() {
    const i = state.inputs;
    return `
      ${errorBanner()}
      <div class="card">
        <h2>About you</h2>
        <div class="row2">
          <div class="field"><label>Your age</label>
            <input type="number" min="18" max="70" value="${i.age}" oninput="App.setField('age', this.value, 'num')">
          </div>
          <div class="field"><label>Dependents</label>
            <input type="number" min="0" max="10" value="${i.dependents}" oninput="App.setField('dependents', this.value, 'num')">
            <div class="hint">Children, parents, or anyone financially dependent on you.</div>
          </div>
        </div>
        <div class="field"><label>Employment</label>
          <select onchange="App.setField('employment', this.value)">
            ${L.EMPLOYMENT_TYPES.map((t) => `<option value="${esc(t)}" ${i.employment === t ? "selected" : ""}>${esc(t)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label class="chk"><input type="checkbox" ${i.hasRetirement ? "checked" : ""} onchange="App.toggleField('hasRetirement')"> Include retirement as a goal</label>
        </div>
        ${i.hasRetirement ? `
        <div class="field"><label>Expected retirement age</label>
          <input type="number" min="${(i.age || 18) + 1}" max="80" value="${i.retirementAge}" oninput="App.setField('retirementAge', this.value, 'num')">
        </div>` : ""}
      </div>
      <div class="actions">
        <button class="ghost" onclick="App.back()">Back</button>
        <button class="primary" onclick="App.next()">Continue</button>
      </div>`;
  }

  // ---- Step 2: Financial life
  function renderFinancialLife() {
    const i = state.inputs;
    const { months } = L.emergencyFundTarget(i);
    return `
      ${errorBanner()}
      <div class="card">
        <h2>Financial life</h2>
        <p class="muted">This helps us size your emergency fund and check how much you can safely invest — all optional except monthly expenses.</p>
        <div class="row2">
          <div class="field amt"><label>Monthly income (take-home)</label>
            <div class="amt"><span class="prefix">₹</span><input type="number" min="0" value="${i.monthlyIncome}" oninput="App.setField('monthlyIncome', this.value, 'num')"></div>
          </div>
          <div class="field amt"><label>Monthly expenses *</label>
            <div class="amt"><span class="prefix">₹</span><input type="number" min="0" value="${i.monthlyExpenses}" oninput="App.setField('monthlyExpenses', this.value, 'num')"></div>
          </div>
        </div>
        <div class="field amt"><label>Total monthly EMI / loan payments</label>
          <div class="amt"><span class="prefix">₹</span><input type="number" min="0" value="${i.emiTotal}" oninput="App.setField('emiTotal', this.value, 'num')"></div>
        </div>
        ${(parseFloat(i.emiTotal) || 0) > 0 ? `
        <div class="field"><label class="chk"><input type="checkbox" ${i.emiHighInterest ? "checked" : ""} onchange="App.toggleField('emiHighInterest')"> Some of this is high-interest debt (credit card, personal loan)</label></div>` : ""}
        <div class="row2">
          <div class="field amt"><label>Existing equity investments</label>
            <div class="amt"><span class="prefix">₹</span><input type="number" min="0" value="${i.existingEquity}" oninput="App.setField('existingEquity', this.value, 'num')"></div>
            <div class="hint">Stocks, equity mutual funds, equity-heavy PF.</div>
          </div>
          <div class="field amt"><label>Existing non-equity investments</label>
            <div class="amt"><span class="prefix">₹</span><input type="number" min="0" value="${i.existingOther}" oninput="App.setField('existingOther', this.value, 'num')"></div>
            <div class="hint">FDs, debt funds, PPF, gold, etc.</div>
          </div>
        </div>
        <div class="field amt"><label>Current emergency fund savings</label>
          <div class="amt"><span class="prefix">₹</span><input type="number" min="0" value="${i.emergencySavings}" oninput="App.setField('emergencySavings', this.value, 'num')"></div>
          <div class="hint">Based on your employment and dependents, we'd suggest about ${months} months of expenses as a safety buffer.</div>
        </div>
        <div class="field"><label>How soon might you need to access this money?</label>
          <div class="choices">
            ${["Low", "Some", "High"].map((v) => `<div class="choice ${i.liquidityNeed === v ? "sel" : ""}" onclick="App.setChoice('liquidityNeed','${v}')">${v} liquidity need</div>`).join("")}
          </div>
        </div>
        <div class="field"><label class="chk"><input type="checkbox" ${i.hasHealthInsurance ? "checked" : ""} onchange="App.toggleField('hasHealthInsurance')"> I have health insurance</label></div>
        ${(parseFloat(i.dependents) || 0) > 0 ? `
        <div class="field"><label class="chk"><input type="checkbox" ${i.soleEarner ? "checked" : ""} onchange="App.toggleField('soleEarner')"> I am the sole/primary income earner for my dependents</label></div>
        <div class="field"><label class="chk"><input type="checkbox" ${i.hasLifeInsurance ? "checked" : ""} onchange="App.toggleField('hasLifeInsurance')"> I have life insurance</label></div>` : ""}
      </div>
      <div class="actions">
        <button class="ghost" onclick="App.back()">Back</button>
        <button class="primary" onclick="App.next()">Continue</button>
      </div>`;
  }

  // ---- Step 3: Money & goals
  function renderMoneyGoals() {
    const i = state.inputs;
    return `
      ${errorBanner()}
      <div class="card">
        <h2>How will you invest?</h2>
        <div class="field">
          <div class="choices">
            ${["SIP (monthly)", "Lumpsum"].map((m) => `<div class="choice ${i.mode === m ? "sel" : ""}" onclick="App.setChoice('mode','${m}')">${m}</div>`).join("")}
          </div>
        </div>
        <div class="field amt"><label>${i.mode.startsWith("SIP") ? "Monthly SIP amount *" : "Lump sum amount *"}</label>
          <div class="amt"><span class="prefix">₹</span><input type="number" min="0" value="${i.amount}" oninput="App.setField('amount', this.value, 'num')"></div>
        </div>
        ${i.mode.startsWith("SIP") ? `
        <div class="field"><label>Annual step-up: ${fmtPct(i.sipStepUp, 0)}</label>
          <input type="range" min="0" max="0.25" step="0.05" value="${i.sipStepUp}" oninput="App.setField('sipStepUp', this.value, 'num')">
          <div class="hint">Automatically grow your SIP amount each year (e.g. with an expected salary hike).</div>
        </div>` : ""}
      </div>
      <div class="card">
        <h2>Your goals</h2>
        <p class="muted">Add anything you're investing toward. Leave cost blank for general long-term wealth building with a time horizon.</p>
        ${i.goals.map((g, idx) => `
          <div class="goal-row">
            ${i.goals.length > 1 ? `<button class="rm" onclick="App.removeGoal(${idx})">✕ remove</button>` : ""}
            <div class="row2">
              <div class="field"><label>Goal name</label><input type="text" value="${esc(g.name)}" oninput="App.setGoalField(${idx},'name', this.value)" placeholder="e.g. House down payment"></div>
              <div class="field"><label>Years to go</label><input type="number" min="0" max="50" value="${g.years}" oninput="App.setGoalField(${idx},'years', this.value, 'num')"></div>
            </div>
            <div class="row2">
              <div class="field"><label>Cost today (optional)</label>
                <div class="amt"><span class="prefix">₹</span><input type="number" min="0" value="${g.cost}" oninput="App.setGoalField(${idx},'cost', this.value, 'num')"></div>
              </div>
              <div class="field"><label>Priority</label>
                <select onchange="App.setGoalField(${idx},'priority', this.value)">
                  ${L.PRIORITIES.map((p) => `<option value="${p}" ${g.priority === p ? "selected" : ""}>${p}</option>`).join("")}
                </select>
              </div>
            </div>
            <div class="field"><label>Cost category (affects assumed inflation)</label>
              <select onchange="App.setGoalField(${idx},'inflationCategory', this.value)">
                ${Object.keys(L.GOAL_INFLATION).map((c) => `<option value="${c}" ${g.inflationCategory === c ? "selected" : ""}>${c} (${fmtPct(L.GOAL_INFLATION[c], 0)}/yr)</option>`).join("")}
              </select>
            </div>
          </div>`).join("")}
        <div class="add-goal" onclick="App.addGoal()">+ Add another goal</div>
      </div>
      <div class="actions">
        <button class="ghost" onclick="App.back()">Back</button>
        <button class="primary" onclick="App.next()">Continue</button>
      </div>`;
  }

  // ---- Step 4: Risk comfort
  function renderRiskComfort() {
    const i = state.inputs;
    return `
      ${errorBanner()}
      <div class="card">
        <h2>How do you feel about risk?</h2>
        <div class="field"><label>In general, I'd describe my risk appetite as:</label>
          <div class="choices">
            ${["Low", "Moderate", "High"].map((v) => `<div class="choice ${i.statedRisk === v ? "sel" : ""}" onclick="App.setChoice('statedRisk','${v}')">${v}</div>`).join("")}
          </div>
        </div>
      </div>
      <div class="card">
        <h2>A few scenarios</h2>
        ${L.QUIZ.map((item, qi) => `
          <div class="field">
            <div class="q-text">${qi + 1}. ${esc(item.q)}</div>
            <div class="choice-grid">
              ${item.options.map((opt, oi) => `
                <div class="choice-block ${state.quizChoice[qi] === oi ? "sel" : ""}" onclick="App.setQuiz(${qi},${oi},${opt[1]})">${esc(opt[0])}</div>`).join("")}
            </div>
          </div>`).join("")}
      </div>
      <div class="actions">
        <button class="ghost" onclick="App.back()">Back</button>
        <button class="primary" onclick="App.next()">Continue</button>
      </div>`;
  }

  // ---- Step 5: Review
  function renderReview() {
    const i = state.inputs;
    const goalLines = i.goals.filter((g) => g.name && g.years).map((g) =>
      `<li>${esc(g.name)} — ${g.years} yrs${g.cost ? `, ${fmtINR(g.cost)} today` : " (open-ended)"}, ${g.priority}</li>`).join("") || "<li class='muted'>No named goals — your money will go toward general wealth building.</li>";
    return `
      ${errorBanner()}
      <div class="card">
        <h2>Review</h2>
        <div class="row2">
          <div>
            <p><b>About you</b> <button class="linklike" onclick="App.goStep(1)">edit</button></p>
            <p class="muted">${i.age} yrs old, ${i.dependents} dependents, ${esc(i.employment)}${i.hasRetirement ? `, retiring at ${i.retirementAge}` : ""}</p>
          </div>
          <div>
            <p><b>Financial life</b> <button class="linklike" onclick="App.goStep(2)">edit</button></p>
            <p class="muted">Income ${fmtINR(i.monthlyIncome) || "—"}, expenses ${fmtINR(i.monthlyExpenses)}, EMI ${fmtINR(i.emiTotal) || "₹0"}</p>
          </div>
        </div>
        <div class="row2">
          <div>
            <p><b>Investing</b> <button class="linklike" onclick="App.goStep(3)">edit</button></p>
            <p class="muted">${esc(i.mode)}, ${fmtINR(i.amount)}${i.mode.startsWith("SIP") ? "/month" : ""}</p>
          </div>
          <div>
            <p><b>Risk comfort</b> <button class="linklike" onclick="App.goStep(4)">edit</button></p>
            <p class="muted">Stated: ${i.statedRisk}, scenario avg: ${fmtNum(L && i.quiz.reduce((a, b) => a + b, 0) / i.quiz.length, 1)}/10</p>
          </div>
        </div>
        <p><b>Goals</b> <button class="linklike" onclick="App.goStep(3)">edit</button></p>
        <ul>${goalLines}</ul>
      </div>
      <div class="actions">
        <button class="ghost" onclick="App.back()">Back</button>
        <button class="primary" onclick="App.next()">See my plan</button>
      </div>`;
  }

  // ---- Step 6: Results
  function renderResults() {
    const p = state.plan;
    if (!p) return `<div class="card"><p>Something went wrong building your plan. <button class="linklike" onclick="App.goStep(5)">Go back</button></p></div>`;
    const inp = state.inputs;
    const rec = p.options[p.recommended];

    const warnBanners = state.reviewWarnings.map((w) => `<div class="banner warn">${esc(w)}</div>`).join("");

    const scorecard = Object.entries(p.financialHealth).map(([k, v]) => `
      <div class="score-item"><span class="dot">${dot(statusTone(v))}</span><div class="val">${esc(v)}</div><div class="label">${esc(k)}</div></div>`).join("");

    const riskBarPct = Math.round((p.profile.score / 10) * 100);
    const reqRisk = p.profile.requiredRisk;

    const goalRows = p.goals.map((g) => `
      <tr>
        <td>${esc(g.name)}<div class="faint">${esc(g.priority)}${g.kind === "retirement" ? " · retirement" : ""}</div></td>
        <td class="num">${g.years}y</td>
        <td class="num">${g.target != null ? fmtINR(g.target) : "open"}</td>
        <td class="num">${g.required != null ? fmtINR(g.required) + (p.mode.startsWith("SIP") ? "/mo" : "") : "—"}</td>
        <td class="num">${g.fundedRatio != null ? fmtPct(g.fundedRatio, 0) : "—"}</td>
      </tr>`).join("");

    const allocBar = Object.entries(rec.overallAlloc).filter(([, v]) => v > 0).map(([k, v]) =>
      `<div class="alloc-seg" style="width:${v}%; background:${ASSET_COLORS[k]}">${v >= 8 ? v + "%" : ""}</div>`).join("");
    const legend = Object.entries(rec.overallAlloc).map(([k, v]) =>
      `<span><span class="sw" style="background:${ASSET_COLORS[k]}"></span>${esc(k)} ${v}%</span>`).join("");

    const chips = reasoningChips(p, inp).map((c) => `<div class="reason-chip">${mdBold(c)}</div>`).join("");

    const scenarioRows = rec.goals.map((g) => `
      <div class="scenario-row">
        <div class="nm">${esc(g.goal)}</div>
        <div class="v">${fmtINR(g.median)}</div>
        <div class="v">${fmtINR(g.p10)}</div>
        <div class="v">${g.prob != null ? fmtPct(g.prob, 0) : "—"}</div>
      </div>`).join("");

    const altCards = L.PROFILES.map((name) => {
      const o = p.options[name];
      const isRec = name === p.recommended;
      return `<div class="alt-card ${isRec ? "rec" : ""}">
        <div class="nm">${name}${isRec ? " ✓ recommended" : ""}</div>
        <div class="kv"><span>Equity</span><span class="v">${fmtPct((o.overallAlloc["Large-cap Equity"] + o.overallAlloc["Mid-cap Equity"]) / 100, 0)}</span></div>
        <div class="kv"><span>Exp. return</span><span class="v">${fmtPct(o.expReturn, 1)}</span></div>
        <div class="kv"><span>Volatility</span><span class="v">${fmtPct(o.volatility, 1)}</span></div>
        <div class="kv"><span>Sharpe</span><span class="v">${o.sharpe}</span></div>
        ${!isRec ? `<div class="actions" style="margin-top:10px"><button class="ghost" style="padding:7px 12px;font-size:0.82rem" onclick="App.setOverride('${name}')">View this instead</button></div>` : ""}
      </div>`;
    }).join("");

    const actionSteps = actionPlan(p, inp).map((s) => `<li>${esc(s)}</li>`).join("");

    const tabs = ["tracker", "whatif", "advisor", "download"];
    const tabLabel = { tracker: "Goal tracker", whatif: "What-if", advisor: "Ask the advisor", download: "Download" };

    return `
      ${warnBanners}
      <div class="card">
        <h1>Your plan</h1>
        <p class="muted">${inp.age} yrs · ${inp.dependents} dependent(s) · ${esc(inp.employment)} · ${esc(p.mode)} of ${fmtINR(p.amount)}${p.mode.startsWith("SIP") ? "/month" : ""} · weighted horizon ${p.profile.weightedHorizonYears} yrs</p>
      </div>

      <h2>Financial health</h2>
      <div class="scorecard">${scorecard}</div>

      <h2>Risk profile: ${p.recommended}</h2>
      <div class="metric-row">
        <div class="metric"><div class="mv">${p.profile.score}/10</div><div class="ml">Overall score</div></div>
        <div class="metric"><div class="mv">${p.profile.willingness}/10</div><div class="ml">Willingness</div></div>
        <div class="metric"><div class="mv">${p.profile.capacity}/10</div><div class="ml">Capacity</div></div>
        <div class="metric"><div class="mv">${reqRisk.label}</div><div class="ml">Required risk</div></div>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:${riskBarPct}%"></div></div>

      <h2>Goals &amp; timeline</h2>
      <table class="plan-table">
        <thead><tr><th>Goal</th><th>Horizon</th><th>Target</th><th>Funding needed</th><th>Funded</th></tr></thead>
        <tbody>${goalRows}</tbody>
      </table>
      ${p.emergencyTopup.funding > 0 ? `<div class="banner info">${fmtINR(p.emergencyTopup.funding)} of your amount is set aside first to build your emergency fund (kept 100% liquid).</div>` : ""}

      <h2>Recommended portfolio</h2>
      <div class="alloc-bar">${allocBar}</div>
      <div class="legend">${legend}</div>
      <div class="metric-row">
        <div class="metric"><div class="mv">${fmtPct(rec.expReturn, 1)}</div><div class="ml">Expected return</div></div>
        <div class="metric"><div class="mv">${fmtPct(rec.volatility, 1)}</div><div class="ml">Volatility</div></div>
        <div class="metric"><div class="mv">${rec.sharpe}</div><div class="ml">Sharpe ratio</div></div>
        <div class="metric"><div class="mv">${fmtPct(rec.badYear, 1)}</div><div class="ml">Bad-year return</div></div>
      </div>

      <h2>Why this fits you</h2>
      ${chips}

      <h2>Expected results</h2>
      <div class="scenario-head"><div></div><div class="v">Median</div><div class="v">Weak case (P10)</div><div class="v">Odds of hitting target</div></div>
      ${scenarioRows}

      <details class="adv">
        <summary>Risk analysis — Sharpe ratio &amp; stress scenarios</summary>
        <p class="muted">Sharpe ratio measures return earned per unit of risk taken, versus a ${fmtPct(L.RISK_FREE_RATE, 1)} risk-free rate — higher is better.
        "Bad year" is a statistically unlucky (1-in-20) single-year outcome; "stress decline" is a more severe 1-in-40 estimate.</p>
        <div class="metric-row">
          <div class="metric"><div class="mv">${fmtPct(rec.stressDecline, 1)}</div><div class="ml">Stress decline</div></div>
        </div>
      </details>

      <h2>Compare alternatives</h2>
      <div class="alt-grid">${altCards}</div>

      <h2>Action plan</h2>
      <ol>${actionSteps}</ol>

      <details class="adv">
        <summary>All notes from your plan</summary>
        <ul>${p.notes.map((n) => `<li>${esc(n)}</li>`).join("") || "<li class='muted'>No additional notes.</li>"}</ul>
      </details>

      <div class="tabs">
        ${tabs.map((t) => `<button class="tab-btn ${state.activeTab === t ? "active" : ""}" onclick="App.setTab('${t}')">${tabLabel[t]}</button>`).join("")}
      </div>
      ${renderTab(p, inp)}

      <div class="actions">
        <button class="ghost" onclick="App.goStep(5)">Back to review</button>
        <button class="ghost" onclick="App.restart()">Start over</button>
      </div>`;
  }

  function renderTab(p, inp) {
    if (state.activeTab === "tracker") {
      return `<div class="card">${p.goals.map((g) => `
        <div style="margin-bottom:14px">
          <div class="kv" style="display:flex;justify-content:space-between;font-size:0.9rem;margin-bottom:4px"><b>${esc(g.name)}</b><span class="mono">${g.fundedRatio != null ? fmtPct(g.fundedRatio, 0) : "—"}</span></div>
          <div class="progress-track"><div class="progress-fill" style="width:${g.fundedRatio != null ? Math.min(100, g.fundedRatio * 100) : 0}%"></div></div>
        </div>`).join("")}</div>`;
    }
    if (state.activeTab === "whatif") {
      const goals = p.goals.filter((g) => g.target != null);
      if (!goals.length) return `<div class="card muted">No goals with a fixed cost to test — add a goal cost to use this tab.</div>`;
      return `<div class="card">
        <p class="muted">Pick a goal and try a different amount or timeline to see the growth rate it would need.</p>
        <div class="field"><label>Goal</label>
          <select onchange="App.setWhatIfGoal(this.value)">
            ${goals.map((g, idx) => `<option value="${p.goals.indexOf(g)}" ${state.whatIf.goalIdx === p.goals.indexOf(g) ? "selected" : ""}>${esc(g.name)}</option>`).join("")}
          </select>
        </div>
        <div class="row2">
          <div class="field amt"><label>${p.mode.startsWith("SIP") ? "Monthly amount" : "Lump sum"}</label>
            <div class="amt"><span class="prefix">₹</span><input type="number" value="${state.whatIf.amount}" oninput="App.setWhatIf('amount', this.value)"></div>
          </div>
          <div class="field"><label>Years</label><input type="number" value="${state.whatIf.years}" oninput="App.setWhatIf('years', this.value)"></div>
        </div>
        <button class="primary" onclick="App.runWhatIf()">Calculate</button>
        ${state.whatIf.result ? `<div class="banner info" style="margin-top:12px">${esc(state.whatIf.result)}</div>` : ""}
      </div>`;
    }
    if (state.activeTab === "advisor") {
      const live = !!sampleCap;
      return `<div class="card">
        <p class="muted">Quick questions, answered instantly from your plan:</p>
        <div class="suggest-row">${ADVISOR_FAQ.map((f, i) => `<button class="ghost" onclick="App.askAdvisor(${i})">${esc(f.q)}</button>`).join("")}</div>
        ${state.advisorLog.map((m) => `<div class="chat-msg user">${esc(m.q)}</div><div class="chat-msg bot">${mdBold(m.a)}</div>`).join("")}
        ${streamingAnswer ? `<div class="chat-msg user">${esc(streamingAnswer.q)}</div><div class="chat-msg bot" id="liveAnswer">${esc(streamingAnswer.text)}</div>` : ""}
        <div class="field" style="margin-top:14px">
          <label>Ask anything about your plan${live ? " — answered live by Claude, using this page's own numbers as tools" : " (live AI isn't available in this view, so you'll get a general pointer)"}</label>
          <textarea id="advisorInput" rows="2" placeholder="e.g. What if I invest ₹5,000 more a month toward my House goal?"></textarea>
        </div>
        <button class="primary" ${state.advisorBusy ? "disabled" : ""} onclick="App.askFree()">${state.advisorBusy ? "Thinking…" : "Ask"}</button>
      </div>`;
    }
    if (state.activeTab === "download") {
      return `<div class="card">
        <p>${downloadsCap ? "Save a plain-text summary of this plan." : "Copy a plain-text summary of this plan to paste into an email, doc, or notes app."}</p>
        <button class="primary" onclick="App.download(this)">${downloadsCap ? "Download plan summary (.txt)" : "Copy plan summary"}</button>
        <textarea id="planSummaryBox" hidden rows="10" style="margin-top:12px" readonly>${esc(planSummaryText())}</textarea>
      </div>`;
    }
    return "";
  }

  function setWhatIfGoal(v) { state.whatIf.goalIdx = parseInt(v, 10); state.whatIf.result = null; render(); }
  function setWhatIf(key, v) { state.whatIf[key] = v; }

  function mdBold(s) { return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>"); }

  // ---- deterministic "why this fits" chips (template-based, mirrors advisor.fallback_explanation)
  function reasoningChips(p, inp) {
    const c = [];
    const prof = p.profile;
    c.push(`**Age ${inp.age}** — contributed ${prof.components.age}/10 to your risk capacity; younger investors generally have more time to recover from market dips.`);
    c.push(`**${inp.dependents} dependent${inp.dependents === 1 ? "" : "s"}** — worth ${prof.components.dependents}/10; fewer financial dependents gives you more room to take risk.`);
    c.push(`**Weighted goal horizon of ${prof.weightedHorizonYears} years** — worth ${prof.components.horizon}/10; longer time horizons can absorb short-term volatility.`);
    c.push(`**Emergency fund coverage** — worth ${prof.components.emergencyFund}/10 toward capacity; a fuller safety buffer means market dips are less likely to force you to sell investments.`);
    c.push(`**Employment: ${esc(inp.employment)}** — worth ${prof.components.employment}/10; income stability affects how much investment risk is prudent.`);
    c.push(`**Stated comfort "${inp.statedRisk}"** blended with your **scenario quiz answers** (avg ${prof.quiz}/10) gave a willingness score of ${prof.willingness}/10.`);
    c.push(`Combining willingness (${prof.willingness}/10) and capacity (${prof.capacity}/10), your final score is **${prof.score}/10**, recommending the **${p.recommended}** portfolio.`);
    if (p.emergencyTopup.funding > 0) c.push(`Part of your amount (**${fmtINR(p.emergencyTopup.funding)}**) is funding your emergency fund first, before the rest goes toward your goals.`);
    if (p.snapshot.existingEquityShare !== null && p.snapshot.existingEquityShare >= 0.75) c.push(`Your **existing investments are already ~${Math.round(p.snapshot.existingEquityShare * 100)}% equity**, so new money is tilted a little more toward debt/liquid to avoid over-concentration.`);
    return c;
  }

  function actionPlan(p, inp) {
    const steps = [];
    const sip = p.mode.startsWith("SIP");
    if (p.emergencyTopup.funding > 0) {
      steps.push(`Set aside ${fmtINR(p.emergencyTopup.funding)}${sip ? " per month" : ""} into a liquid fund until your emergency fund reaches ${fmtINR(p.snapshot.emergencyTarget)}.`);
    }
    p.goals.filter((g) => g.target != null).sort((a, b) => (L.PRIORITIES.indexOf(a.priority) - L.PRIORITIES.indexOf(b.priority)) || (a.years - b.years))
      .forEach((g) => {
        steps.push(`Fund '${g.name}' with ${fmtINR(g.funding)}${sip ? "/month" : ""}, targeting ${fmtINR(g.target)} in ${g.years} years (currently ${g.fundedRatio != null ? fmtPct(g.fundedRatio, 0) : "—"} funded).`);
      });
    if (p.snapshot.highInterestDebt) steps.push("Prioritise repaying your high-interest debt — its cost likely exceeds typical investment returns.");
    if (!p.snapshot.hasHealthInsurance) steps.push("Look into health insurance — a protection gap can derail an investment plan during a medical emergency.");
    if ((inp.dependents || 0) > 0 && p.snapshot.soleEarner && !p.snapshot.hasLifeInsurance) steps.push("As the primary earner for your dependents, consider term life insurance alongside this investment plan.");
    steps.push("Set up the SIPs / lump-sum allocations above with your chosen mutual fund platform or advisor.");
    steps.push("Revisit this plan at least once a year, or sooner after any major income or life change.");
    return steps;
  }

  function restart() {
    state.step = 0; state.maxStepReached = 0; state.plan = null; state.override = null;
    state.inputs = {
      age: 28, dependents: 0, hasRetirement: true, retirementAge: 60,
      soleEarner: false, employment: "Salaried", monthlyIncome: "", monthlyExpenses: "",
      emiTotal: "", emiHighInterest: false, existingEquity: "", existingOther: "",
      emergencySavings: "", liquidityNeed: "Some", hasHealthInsurance: true, hasLifeInsurance: true,
      mode: "SIP (monthly)", amount: "", sipStepUp: 0,
      goals: [freshGoal()], statedRisk: "Moderate", quiz: [6, 6, 6],
    };
    state.quizChoice = [null, null, null]; state.advisorLog = []; state.activeTab = "tracker";
    render();
  }

  window.App = {
    setField, toggleField, setChoice, setGoalField, addGoal, removeGoal, setQuiz,
    next, back, goStep, setOverride, setTab, runWhatIf, setWhatIfGoal, setWhatIf, askAdvisor, askFree, download, restart,
    init() { render(); initCaps(); },
  };
})();
