const L = require("./logic.js");

let FAILS = 0;
function check(label, cond, detail) {
  if (cond) { console.log("  PASS  " + label); }
  else { console.log("  FAIL  " + label + "  " + (detail !== undefined ? JSON.stringify(detail) : "")); FAILS++; }
}
function sumsTo100(allocDict, tol = 0.6) {
  const sum = Object.values(allocDict).reduce((a, b) => a + b, 0);
  return Math.abs(sum - 100) <= tol;
}

function baseInput(overrides) {
  const inp = {
    age: 28, dependents: 0, hasRetirement: true, retirementAge: 60, monthlyExpenses: 40000,
    mode: "SIP (monthly)", amount: 20000, statedRisk: "Moderate", quiz: [6, 6, 6],
    goals: [{ name: "Vacation", cost: 150000, years: 2, priority: "Important", inflationCategory: "Travel" }],
    employment: "Salaried", monthlyIncome: 0, emiTotal: 0, emiHighInterest: false,
    existingEquity: 0, existingOther: 0, emergencySavings: 0,
    hasHealthInsurance: true, hasLifeInsurance: true, soleEarner: false,
    liquidityNeed: "Some", sipStepUp: 0,
  };
  return Object.assign({}, inp, overrides);
}

console.log("=== TC1 minimal defaults ===");
const inp1 = baseInput();
const p1 = L.buildPlan(inp1);
check("TC1 overall alloc sums to 100 for every option", Object.values(p1.options).every((o) => sumsTo100(o.overallAlloc)));
check("TC1 required risk label computed without crashing", !!p1.profile.requiredRisk.label);

console.log("=== TC2 emergency fund shortfall (self-employed, no buffer) ===");
const inp2 = baseInput({ monthlyExpenses: 30000, emergencySavings: 0, employment: "Self-employed / business owner", amount: 25000 });
const p2 = L.buildPlan(inp2);
const { months } = L.emergencyFundTarget(inp2);
check("TC2 emergency target uses self-employed months", months === 8, months);
check("TC2 top-up amount > 0 since no savings exist", p2.emergencyTopup.funding > 0, p2.emergencyTopup);
check("TC2 top-up capped at available amount", p2.emergencyTopup.funding <= inp2.amount + 1e-6);
check("TC2 a note about the emergency top-up appears", p2.notes.some((n) => n.toLowerCase().includes("emergency fund")));

console.log("=== TC3 high EMI burden + SIP exceeding disposable income ===");
const inp3 = baseInput({ monthlyIncome: 50000, monthlyExpenses: 30000, emiTotal: 25000, emiHighInterest: true, amount: 10000 });
const { warnings: w3 } = L.validateInputs(inp3);
check("TC3 high EMI burden warning fires", w3.some((w) => w.toLowerCase().includes("debt burden")), w3);
check("TC3 SIP-vs-disposable-income warning fires", w3.some((w) => w.toLowerCase().includes("disposable income")), w3);
const p3 = L.buildPlan(inp3);
check("TC3 high-interest debt note appears", p3.notes.some((n) => n.toLowerCase().includes("high-interest debt")));
check("TC3 debt level flagged in financial health", p3.financialHealth["Debt Level"] === "Needs Attention");

console.log("=== TC4 existing portfolio tilt ===");
const inp4a = baseInput({ existingEquity: 800000, existingOther: 200000, amount: 15000 });
const inp4b = baseInput({ existingEquity: 0, existingOther: 0, amount: 15000 });
const p4a = L.buildPlan(inp4a), p4b = L.buildPlan(inp4b);
const recA = p4a.recommended, recB = p4b.recommended;
const eqA = p4a.options[recA].overallAlloc["Large-cap Equity"] + p4a.options[recA].overallAlloc["Mid-cap Equity"];
const eqB = p4b.options[recB].overallAlloc["Large-cap Equity"] + p4b.options[recB].overallAlloc["Mid-cap Equity"];
check("TC4 existing-equity-heavy client gets LOWER new-money equity share than baseline", eqA < eqB, { eqA, eqB });
check("TC4 a note explains the tilt", p4a.notes.some((n) => n.toLowerCase().includes("tilted")));

console.log("=== TC5 priority-based funding order ===");
const inp5 = baseInput({
  amount: 5000, hasRetirement: false,
  goals: [
    { name: "Big Aspirational Trip", cost: 500000, years: 1, priority: "Aspirational", inflationCategory: "Travel" },
    { name: "Essential Medical Buffer", cost: 500000, years: 1, priority: "Essential", inflationCategory: "Healthcare" },
  ],
});
const p5 = L.buildPlan(inp5);
const essential = p5.goals.find((g) => g.name === "Essential Medical Buffer");
const aspirational = p5.goals.find((g) => g.name === "Big Aspirational Trip");
check("TC5 Essential funded before Aspirational despite same date", essential.funding >= aspirational.funding, { essential: essential.funding, aspirational: aspirational.funding });

console.log("=== TC6 step-up SIP ===");
const inp6a = baseInput({ amount: 100000, sipStepUp: 0, hasRetirement: false, goals: [{ name: "House", cost: 3000000, years: 10, priority: "Important", inflationCategory: "Housing" }] });
const inp6b = baseInput({ amount: 100000, sipStepUp: 0.10, hasRetirement: false, goals: [{ name: "House", cost: 3000000, years: 10, priority: "Important", inflationCategory: "Housing" }] });
const p6a = L.buildPlan(inp6a), p6b = L.buildPlan(inp6b);
const reqFlat = p6a.goals.find((g) => g.name === "House").required;
const reqStep = p6b.goals.find((g) => g.name === "House").required;
check("TC6 step-up SIP needs a SMALLER first-month contribution than flat SIP", reqStep < reqFlat, { reqFlat, reqStep });

console.log("=== TC7 goal-specific inflation ===");
const inp7 = baseInput({ hasRetirement: false, goals: [
  { name: "Edu", cost: 1000000, years: 10, priority: "Essential", inflationCategory: "Education" },
  { name: "Gen", cost: 1000000, years: 10, priority: "Essential", inflationCategory: "General" },
]});
const goals7 = L.buildGoals(inp7);
const edu = goals7.find((g) => g.name === "Edu"), gen = goals7.find((g) => g.name === "Gen");
check("TC7 Education inflates to a HIGHER target than General", edu.target > gen.target, { edu: edu.target, gen: gen.target });

console.log("=== TC8 near-retirement aggressive flag ===");
const inp8 = baseInput({ age: 52, retirementAge: 60, statedRisk: "High", quiz: [10, 10, 10], monthlyExpenses: 50000, goals: [] });
const p8 = L.buildPlan(inp8, "Aggressive");
check("TC8 near-retirement high-equity note appears", p8.notes.some((n) => n.toLowerCase().includes("retirement") && n.toLowerCase().includes("closer")), p8.notes);

console.log("=== TC9 Sharpe & stress metrics ===");
Object.entries(p1.options).forEach(([name, o]) => {
  check(`TC9 ${name} has a finite Sharpe ratio`, typeof o.sharpe === "number" && !isNaN(o.sharpe));
  check(`TC9 ${name} stress_decline <= bad_year`, o.stressDecline <= o.badYear + 1e-9, { stress: o.stressDecline, bad: o.badYear });
});

console.log("=== TC10 lumpsum mode ===");
const inp10 = baseInput({ mode: "Lumpsum", amount: 500000 });
const p10 = L.buildPlan(inp10);
check("TC10 lumpsum plan builds and sums to 100", Object.values(p10.options).every((o) => sumsTo100(o.overallAlloc)));

console.log("=== TC11 determinism: same inputs -> same plan ===");
const p11a = L.buildPlan(baseInput({ amount: 12345 }));
const p11b = L.buildPlan(baseInput({ amount: 12345 }));
check("TC11 recommended profile is identical across runs", p11a.recommended === p11b.recommended);
check("TC11 overall equity % is identical across runs", p11a.options[p11a.recommended].overallAlloc["Large-cap Equity"] === p11b.options[p11b.recommended].overallAlloc["Large-cap Equity"]);
check("TC11 goal median outcome is identical across runs", p11a.goals[0] && p11b.goals[0] ? p11a.options[p11a.recommended].goals[0].median === p11b.options[p11b.recommended].goals[0].median : true);

console.log("\n" + "=".repeat(60));
if (FAILS > 0) { console.log(FAILS + " CHECK(S) FAILED"); process.exit(1); }
else { console.log("ALL CHECKS PASSED."); }
