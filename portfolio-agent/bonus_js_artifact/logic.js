/* Lakshya — goal-based portfolio engine, ported faithfully from the Python risk.py/allocation.py.
   Pure functions, no DOM dependency, so this exact code runs both in Node (for testing) and in the browser. */

// ============================================================ CONFIG (mirrors config.py)
const ASSETS = ["Liquid Fund", "Debt Fund", "Gold", "Large-cap Equity", "Mid-cap Equity"];

const ASSUMPTIONS = {
  "Liquid Fund": [0.060, 0.010],
  "Debt Fund": [0.070, 0.030],
  "Gold": [0.080, 0.140],
  "Large-cap Equity": [0.120, 0.170],
  "Mid-cap Equity": [0.140, 0.220],
};
const ASSUMPTIONS_NOTE = "Placeholder return/volatility assumptions - replace with figures computed from real historical data for a production submission.";

const CORR = [
  [1.00, 0.50, 0.00, 0.00, 0.00],
  [0.50, 1.00, 0.10, 0.10, 0.05],
  [0.00, 0.10, 1.00, 0.05, 0.05],
  [0.00, 0.10, 0.05, 1.00, 0.85],
  [0.00, 0.05, 0.05, 0.85, 1.00],
];

const INFLATION = 0.06;
const PLANNING_MARGIN = 0.01;
const RETIREMENT_MULTIPLE = 25;
const DEFAULT_WEALTH_YEARS = 15;
const N_SIMS = 1500;     // slightly below the Python build's 2000, kept brisk for an in-browser demo
const SEED = 42;

const CAPITAL_PROTECTION_YEARS = 1;
const SHORT_MAX_YEARS = 3;
const MEDIUM_MAX_YEARS = 7;

const CONSERVATIVE_BELOW = 4.0;
const AGGRESSIVE_FROM = 7.0;
const PROFILES = ["Conservative", "Moderate", "Aggressive"];

const PRIORITIES = ["Essential", "Important", "Aspirational"];
const PRIORITY_ORDER = { Essential: 0, Important: 1, Aspirational: 2 };

const GOAL_INFLATION = { General: 0.06, Education: 0.08, Healthcare: 0.09, Travel: 0.06, Housing: 0.07 };
const DEFAULT_GOAL_INFLATION_CATEGORY = "General";

const EMPLOYMENT_TYPES = ["Salaried", "Self-employed / business owner", "Freelancer / professional", "Student", "Retired", "Other"];

const EMERGENCY_MONTHS_BASE = {
  "Salaried": 4, "Self-employed / business owner": 8, "Freelancer / professional": 8,
  "Student": 3, "Retired": 6, "Other": 6,
};
const EMERGENCY_MONTHS_PER_DEPENDENT = 1;
const EMERGENCY_MONTHS_CAP = 12;

const EMPLOYMENT_CAPACITY_PTS = {
  "Salaried": 7, "Self-employed / business owner": 5, "Freelancer / professional": 4,
  "Student": 5, "Retired": 3, "Other": 5,
};

const HIGH_EMI_BURDEN_RATIO = 0.40;
const EXISTING_PORTFOLIO_OFFSET = 0.5;
const RISK_FREE_RATE = 0.065;

const ALLOC = {
  Short: {
    Conservative: [70, 30, 0, 0, 0],
    Moderate: [55, 35, 5, 5, 0],
    Aggressive: [40, 40, 5, 15, 0],
  },
  Medium: {
    Conservative: [10, 55, 10, 25, 0],
    Moderate: [5, 35, 10, 40, 10],
    Aggressive: [0, 20, 10, 45, 25],
  },
  Long: {
    Conservative: [0, 40, 10, 40, 10],
    Moderate: [0, 20, 10, 45, 25],
    Aggressive: [0, 5, 5, 50, 40],
  },
};

const STATED_SCORE = { Low: 3, Moderate: 6, High: 9 };

const QUIZ = [
  {
    q: "Your investments fall 20% in one month because markets are nervous. What would you do?",
    options: [["Sell everything to stop further loss", 2], ["Do nothing and wait for recovery", 6], ["Invest more, prices are lower now", 10]],
  },
  {
    q: "Which 5-year outcome would you prefer?",
    options: [["Steady ~7% a year, almost no chance of loss", 2], ["~10% a year on average, with dips of up to 15%", 6], ["~13% a year on average, with dips of up to 30%", 10]],
  },
  {
    q: "Markets fall just before you need the money for a goal. How much does hitting the exact date matter?",
    options: [["Very important, I cannot delay", 2], ["I could delay by a year or so", 6], ["I am flexible, the date can move", 10]],
  },
];

// ============================================================ small helpers
function mean(arr) { return arr.reduce((a, b) => a + b, 0) / arr.length; }
function clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }

// Seeded PRNG (mulberry32) + Box-Muller normal draw. Deterministic per goal index, so the SAME
// inputs always reproduce the SAME plan (item 41 - reproducibility), even though the exact numeric
// values differ from the Python build's numpy RNG (a different algorithm, not a bug).
function mulberry32(seed) {
  let a = seed;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function makeNormalSampler(seed) {
  const rng = mulberry32(seed);
  let spare = null;
  return function () {
    if (spare !== null) { const s = spare; spare = null; return s; }
    let u = 0, v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();
    const mag = Math.sqrt(-2.0 * Math.log(u));
    spare = mag * Math.sin(2.0 * Math.PI * v);
    return mag * Math.cos(2.0 * Math.PI * v);
  };
}

// ============================================================ risk.py port
function bucketFor(years) {
  if (years <= SHORT_MAX_YEARS) return "Short";
  if (years <= MEDIUM_MAX_YEARS) return "Medium";
  return "Long";
}

function emergencyFundTarget(inp) {
  const baseMonths = EMERGENCY_MONTHS_BASE[inp.employment] ?? 6;
  let months = baseMonths + EMERGENCY_MONTHS_PER_DEPENDENT * (inp.dependents || 0);
  months = Math.min(months, EMERGENCY_MONTHS_CAP);
  const expenses = inp.monthlyExpenses || 0;
  return { months, target: months * expenses };
}

function financialSnapshot(inp) {
  const income = inp.monthlyIncome || 0;
  const expenses = inp.monthlyExpenses || 0;
  const emi = inp.emiTotal || 0;
  const disposable = Math.max(0, income - expenses - emi);
  const savingsRate = income > 0 ? disposable / income : null;

  const { months, target } = emergencyFundTarget(inp);
  const current = inp.emergencySavings || 0;
  const shortfall = Math.max(0, target - current);

  const emiRatio = income > 0 ? emi / income : null;
  const highEmiBurden = emiRatio !== null && emiRatio > HIGH_EMI_BURDEN_RATIO;
  const highInterestDebt = !!inp.emiHighInterest;

  const existingEquity = inp.existingEquity || 0;
  const existingOther = inp.existingOther || 0;
  const existingTotal = existingEquity + existingOther;
  const existingEquityShare = existingTotal > 0 ? existingEquity / existingTotal : null;

  return {
    incomeKnown: income > 0,
    monthlyIncome: income, monthlyExpenses: expenses, emiTotal: emi,
    disposableIncome: disposable, savingsRate,
    emergencyMonthsTarget: months, emergencyTarget: target,
    emergencyCurrent: current, emergencyShortfall: shortfall,
    emiRatio, highEmiBurden, highInterestDebt,
    existingEquity, existingOther, existingTotal, existingEquityShare,
    hasHealthInsurance: inp.hasHealthInsurance !== false,
    hasLifeInsurance: inp.hasLifeInsurance !== false,
    soleEarner: !!inp.soleEarner,
    liquidityNeed: inp.liquidityNeed || "Some",
  };
}

function validateInputs(inp) {
  const errors = [], warnings = [];
  const age = inp.age || 0;
  if (!(age >= 18 && age <= 70)) errors.push("Age should be between 18 and 70.");
  if ((inp.amount || 0) <= 0) errors.push("Please enter an investable amount greater than zero.");
  if (inp.hasRetirement) {
    const ra = inp.retirementAge || 0;
    if (ra <= age) errors.push("Retirement age must be greater than your current age.");
    else if (ra - age > 45) warnings.push("Retirement is more than 45 years away, projections that far out are very uncertain.");
  }
  (inp.goals || []).forEach((g, i) => {
    const name = (g.name || "").trim();
    const years = g.years || 0, cost = g.cost || 0;
    if (!name && (years || cost)) errors.push(`Goal ${i + 1}: please give it a name.`);
    if (name && years <= 0) errors.push(`Goal '${name}': years to go must be more than 0.`);
    if (name && years > 50) errors.push(`Goal '${name}': years to go looks too large (max 50).`);
    if (name && cost < 0) errors.push(`Goal '${name}': cost cannot be negative.`);
  });
  if ((inp.mode || "").startsWith("SIP") && inp.amount > 0 && inp.amount < 500) {
    warnings.push("Most funds need at least Rs 500 per month for a SIP.");
  }
  if (cleanGoals(inp).length === 0 && !inp.hasRetirement) {
    warnings.push("No goals entered, we will treat your money as general long-term wealth building.");
  }

  const snap = financialSnapshot(inp);
  if (snap.emergencyShortfall > 0 && snap.emergencyCurrent === 0) {
    warnings.push(`You do not yet have an emergency fund. Based on your situation, aim for about ${snap.emergencyMonthsTarget} months of expenses in a liquid fund before taking market risk.`);
  } else if (snap.emergencyShortfall > 0) {
    warnings.push(`Your emergency fund is short by about Rs ${Math.round(snap.emergencyShortfall).toLocaleString("en-IN")} of its ${snap.emergencyMonthsTarget}-month target. We'll top this up before investing the rest.`);
  }
  if (snap.incomeKnown) {
    const sipAmount = (inp.mode || "").startsWith("SIP") ? inp.amount : 0;
    if (sipAmount > snap.disposableIncome * 1.0001) {
      warnings.push(`Your monthly SIP (Rs ${sipAmount.toLocaleString("en-IN")}) is more than your disposable income (income minus expenses and EMIs, about Rs ${Math.round(snap.disposableIncome).toLocaleString("en-IN")}/month). Consider a smaller SIP, or review your expenses/EMIs.`);
    }
    if (snap.highEmiBurden) {
      warnings.push(`Your EMIs are about ${Math.round(snap.emiRatio * 100)}% of your income, a high debt burden. If any of this debt carries a high interest rate, consider repaying it before increasing investments.`);
    }
  }
  if (!snap.hasHealthInsurance) {
    warnings.push("You reported no health insurance. Consider addressing this protection gap alongside your investment plan, especially with dependents to support.");
  }
  if ((inp.dependents || 0) > 0 && snap.soleEarner && !snap.hasLifeInsurance) {
    warnings.push("You are the primary income earner with dependents but reported no life insurance. Consider addressing this protection gap as part of your overall financial plan.");
  }
  return { errors, warnings };
}

function cleanGoals(inp) {
  return (inp.goals || [])
    .map((g) => ({
      name: (g.name || "").trim(), years: parseFloat(g.years) || 0, cost: parseFloat(g.cost) || 0,
      priority: g.priority || "Important", inflationCategory: g.inflationCategory || DEFAULT_GOAL_INFLATION_CATEGORY,
    }))
    .filter((g) => g.name && g.years > 0);
}

function buildGoals(inp) {
  const goals = [];
  cleanGoals(inp).forEach((g) => {
    const infl = GOAL_INFLATION[g.inflationCategory] ?? GOAL_INFLATION[DEFAULT_GOAL_INFLATION_CATEGORY];
    if (g.cost > 0) {
      goals.push({
        name: g.name, years: g.years, kind: "goal", todayValue: g.cost,
        target: g.cost * Math.pow(1 + infl, g.years),
        priority: g.priority, inflationCategory: g.inflationCategory, inflationRate: infl,
      });
    } else {
      goals.push({ name: g.name, years: g.years, kind: "open", todayValue: null, target: null,
        priority: g.priority, inflationCategory: g.inflationCategory, inflationRate: infl });
    }
  });
  if (inp.hasRetirement && inp.retirementAge > inp.age) {
    const yrs = inp.retirementAge - inp.age;
    const exp = inp.monthlyExpenses || 0;
    const infl = GOAL_INFLATION.General;
    let todayVal = null, target = null;
    if (exp > 0) { todayVal = exp * 12 * RETIREMENT_MULTIPLE; target = todayVal * Math.pow(1 + infl, yrs); }
    goals.push({ name: "Retirement", years: yrs, kind: "retirement", todayValue: todayVal, target,
      priority: "Essential", inflationCategory: "General", inflationRate: infl });
  }
  goals.forEach((g) => { g.bucket = bucketFor(g.years); });
  return goals;
}

function weightedHorizon(goals) {
  if (!goals.length) return 10.0;
  const sized = goals.filter((g) => g.todayValue).map((g) => g.todayValue);
  const fallback = sized.length ? mean(sized) : 1.0;
  const weights = goals.map((g) => g.todayValue || fallback);
  const totW = weights.reduce((a, b) => a + b, 0);
  return weights.reduce((s, w, i) => s + w * goals[i].years, 0) / totW;
}

function riskProfile(inp, goals) {
  const stated = STATED_SCORE[inp.statedRisk] ?? 6;
  const quiz = mean(inp.quiz && inp.quiz.length ? inp.quiz : [6]);
  const willingness = 0.4 * stated + 0.6 * quiz;

  const age = inp.age;
  const agePts = age <= 30 ? 9 : age <= 40 ? 7 : age <= 50 ? 5 : age <= 60 ? 3 : 2;
  const dep = inp.dependents || 0;
  const depPts = dep === 0 ? 9 : dep === 1 ? 7 : dep === 2 ? 5 : 3;
  const horizon = weightedHorizon(goals);
  const horizonPts = clamp(1 + 0.6 * horizon, 1, 10);

  const snap = financialSnapshot(inp);
  const coverage = snap.emergencyTarget > 0 ? Math.min(1, snap.emergencyCurrent / snap.emergencyTarget) : 1.0;
  const emergencyPts = 2 + 7 * coverage;

  let employmentPts = EMPLOYMENT_CAPACITY_PTS[inp.employment] ?? 5;
  if (snap.highEmiBurden) employmentPts = Math.max(1, employmentPts - 2);

  const capacity = mean([agePts, depPts, horizonPts, emergencyPts, employmentPts]);
  const score = Math.round(clamp(Math.min(willingness, capacity), 1, 10) * 10) / 10;
  const label = score < CONSERVATIVE_BELOW ? "Conservative" : score >= AGGRESSIVE_FROM ? "Aggressive" : "Moderate";

  return {
    score, label,
    willingness: Math.round(willingness * 10) / 10, capacity: Math.round(capacity * 10) / 10,
    stated, quiz: Math.round(quiz * 10) / 10,
    components: { age: agePts, dependents: depPts, horizon: Math.round(horizonPts * 10) / 10,
      emergencyFund: Math.round(emergencyPts * 10) / 10, employment: employmentPts },
    weightedHorizonYears: Math.round(horizon * 10) / 10,
  };
}

// ============================================================ allocation.py port
function goalAllocation(years, profile) {
  if (years <= CAPITAL_PROTECTION_YEARS) return [1, 0, 0, 0, 0];
  const row = ALLOC[bucketFor(years)][profile];
  return row.map((x) => x / 100);
}
function allocDict(weights) {
  const out = {};
  ASSETS.forEach((a, i) => { out[a] = Math.round(weights[i] * 1000) / 10; });
  return out;
}
function equityShare(weights) { return (weights[3] + weights[4]) * 100; }

function tiltForExisting(weights, existingEquityShare) {
  if (existingEquityShare === null || existingEquityShare === undefined) return weights;
  const w = weights.slice();
  const targetEquity = w[3] + w[4];
  const diff = existingEquityShare - targetEquity;
  if (Math.abs(diff) < 1e-6 || targetEquity <= 0) return w;
  let shift = EXISTING_PORTFOLIO_OFFSET * diff * targetEquity;
  shift = clamp(shift, -targetEquity, targetEquity);
  w[3] -= shift * (w[3] / targetEquity);
  w[4] -= shift * (w[4] / targetEquity);
  w[1] += shift;
  if (w[1] < 0) { w[0] += w[1]; w[1] = 0; }
  for (let i = 0; i < w.length; i++) w[i] = Math.max(0, w[i]);
  const s = w.reduce((a, b) => a + b, 0);
  return s > 0 ? w.map((x) => x / s) : w;
}

const MU = ASSETS.map((a) => ASSUMPTIONS[a][0]);
const SD = ASSETS.map((a) => ASSUMPTIONS[a][1]);
const COV = SD.map((sdi, i) => SD.map((sdj, j) => sdi * sdj * CORR[i][j]));

function portfolioStats(w) {
  const mu = w.reduce((s, wi, i) => s + wi * MU[i], 0);
  let variance = 0;
  for (let i = 0; i < w.length; i++) for (let j = 0; j < w.length; j++) variance += w[i] * COV[i][j] * w[j];
  return { mu, sd: Math.sqrt(Math.max(0, variance)) };
}
function sharpeRatio(mu, sd) { return sd > 1e-9 ? (mu - RISK_FREE_RATE) / sd : 0; }
function planningReturn(w) {
  const { mu, sd } = portfolioStats(w);
  return Math.max(0, mu - 0.5 * sd * sd - PLANNING_MARGIN);
}

function sipFutureValue(c0, months, rm, stepUp) {
  let v = 0;
  for (let t = 0; t < months; t++) {
    const yearIdx = Math.floor(t / 12);
    v += c0 * Math.pow(1 + stepUp, yearIdx);
    v *= (1 + rm);
  }
  return v;
}

function requiredFunding(target, years, g, sip, stepUp = 0) {
  if (sip) {
    const months = Math.max(1, Math.round(years * 12));
    const rm = Math.pow(1 + g, 1 / 12) - 1;
    if (stepUp <= 1e-9) return rm < 1e-9 ? target / months : (target * rm) / (Math.pow(1 + rm, months) - 1);
    let lo = 0, hi = Math.max(target, 1);
    for (let i = 0; i < 60; i++) {
      const mid = (lo + hi) / 2;
      const fv = sipFutureValue(mid, months, rm, stepUp);
      if (fv < target) lo = mid; else hi = mid;
    }
    return hi;
  }
  return target / Math.pow(1 + g, years);
}

function requiredReturn(amount, target, years, sip, stepUp = 0) {
  if (amount <= 0 || target <= 0 || years <= 0) return 0;
  let lo = -0.5, hi = 0.5;
  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    let fv;
    if (sip) {
      const rm = Math.pow(1 + mid, 1 / 12) - 1;
      fv = sipFutureValue(amount, Math.max(1, Math.round(years * 12)), rm, stepUp);
    } else {
      fv = amount * Math.pow(1 + mid, years);
    }
    if (fv < target) lo = mid; else hi = mid;
  }
  return hi;
}

function simulate(seed, mu, sd, funding, sip, target, stepUp, years) {
  const months = Math.max(1, Math.round(years * 12));
  const sims = N_SIMS;
  if (funding <= 0) return { median: 0, p10: 0, p90: 0, prob: target ? 0 : null, medianPct: target ? 0 : null };
  const normal = makeNormalSampler(seed);
  const v = new Float64Array(sims);
  if (!sip) v.fill(funding);
  const mm = mu / 12, sm = sd / Math.sqrt(12);
  for (let t = 0; t < months; t++) {
    const yearIdx = Math.floor(t / 12);
    const contrib = sip ? funding * Math.pow(1 + stepUp, yearIdx) : 0;
    for (let s = 0; s < sims; s++) {
      if (sip) v[s] += contrib;
      const z = normal();
      const r = Math.max(mm + sm * z, -0.95);
      v[s] *= (1 + r);
    }
  }
  const sorted = Array.from(v).sort((a, b) => a - b);
  const pct = (p) => sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
  const median = pct(0.5), p10 = pct(0.10), p90 = pct(0.90);
  const prob = target ? v.reduce((c, x) => c + (x >= target ? 1 : 0), 0) / sims : null;
  const medianPct = target ? median / target : null;
  return { median, p10, p90, prob, medianPct };
}

function financialHealth(inp, snap, goals) {
  const card = {};
  if (snap.emergencyTarget <= 0) card["Emergency Fund"] = "Not assessed";
  else if (snap.emergencyShortfall <= 0) card["Emergency Fund"] = "Good";
  else if (snap.emergencyCurrent / snap.emergencyTarget >= 0.5) card["Emergency Fund"] = "Needs Attention";
  else card["Emergency Fund"] = "At Risk";

  if (snap.emiRatio === null) card["Debt Level"] = "Not assessed";
  else if (snap.highEmiBurden) card["Debt Level"] = "Needs Attention";
  else card["Debt Level"] = "Healthy";

  if (snap.savingsRate === null) card["Savings Rate"] = "Not assessed";
  else if (snap.savingsRate >= 0.3) card["Savings Rate"] = "Strong";
  else if (snap.savingsRate >= 0.15) card["Savings Rate"] = "Good";
  else card["Savings Rate"] = "Needs Attention";

  const ret = goals.find((g) => g.kind === "retirement");
  if (!ret) card["Retirement Planning"] = "Not assessed";
  else if (ret.fundedRatio === null || ret.fundedRatio === undefined) card["Retirement Planning"] = "On Track";
  else if (ret.fundedRatio >= 0.95) card["Retirement Planning"] = "On Track";
  else if (ret.fundedRatio >= 0.7) card["Retirement Planning"] = "Behind Target";
  else card["Retirement Planning"] = "Significantly Behind";

  const needsLifeCover = (inp.dependents || 0) > 0 && snap.soleEarner && !snap.hasLifeInsurance;
  card["Insurance Protection"] = (!snap.hasHealthInsurance || needsLifeCover) ? "Needs Review" : "Good";
  return card;
}

function buildPlan(inp, override = null, amountMult = 1.0) {
  const sip = (inp.mode || "").startsWith("SIP");
  const stepUp = sip ? (inp.sipStepUp || 0) : 0;
  const goals = buildGoals(inp);
  const prof = riskProfile(inp, goals);
  const rec = override || prof.label;
  const amount = inp.amount * amountMult;
  const snap = financialSnapshot(inp);

  goals.forEach((g) => { g.planReturn = planningReturn(goalAllocation(g.years, rec)); });

  let avail = amount;
  const topupNeeded = snap.emergencyShortfall;
  const topup = topupNeeded > 0 ? Math.min(topupNeeded, avail) : 0;
  avail -= topup;
  const emergencyTopup = { required: topupNeeded, funding: topup, fundedRatio: topupNeeded > 0 ? topup / topupNeeded : 1.0 };

  const targeted = goals.filter((g) => g.target !== null);
  targeted.sort((a, b) => {
    const pa = PRIORITY_ORDER[a.priority] ?? 1, pb = PRIORITY_ORDER[b.priority] ?? 1;
    return pa !== pb ? pa - pb : a.years - b.years;
  });
  targeted.forEach((g) => {
    g.required = requiredFunding(g.target, g.years, g.planReturn, sip, stepUp);
    g.funding = Math.min(g.required, avail);
    g.fundedRatio = g.required > 0 ? g.funding / g.required : 1.0;
    avail -= g.funding;
  });
  goals.forEach((g) => { if (g.target === null) { g.required = null; g.funding = 0; g.fundedRatio = null; } });

  let surplus = Math.max(avail, 0);
  if (surplus > 0.5) {
    const openGoals = goals.filter((g) => g.target === null);
    if (openGoals.length) {
      openGoals.forEach((g) => { g.funding += surplus / openGoals.length; });
    } else {
      const longest = goals.length ? Math.max(...goals.map((g) => g.years)) : 0;
      const yrs = longest >= MEDIUM_MAX_YEARS ? longest : DEFAULT_WEALTH_YEARS;
      goals.push({ name: "Long-term wealth building (surplus)", years: yrs, kind: "wealth", todayValue: null, target: null,
        bucket: bucketFor(yrs), priority: "Aspirational", inflationCategory: "General", inflationRate: GOAL_INFLATION.General,
        required: null, funding: surplus, fundedRatio: null, planReturn: 0 });
    }
  }

  const options = {};
  PROFILES.forEach((name) => {
    const rows = []; let agg = [0, 0, 0, 0, 0];
    goals.forEach((g, i) => {
      const w = goalAllocation(g.years, name);
      const { mu, sd } = portfolioStats(w);
      const res = simulate(SEED + i, mu, sd, g.funding, sip, g.target, stepUp, g.years);
      rows.push({ goal: g.name, alloc: allocDict(w), equityPct: Math.round(equityShare(w) * 10) / 10, expReturn: mu, volatility: sd, ...res });
      agg = agg.map((v, k) => v + g.funding * w[k]);
    });
    const aggSum = agg.reduce((a, b) => a + b, 0);
    let overall = aggSum > 0 ? agg.map((v) => v / aggSum)
      : (goals.length ? (() => {
          const stack = goals.map((g) => goalAllocation(g.years, name));
          return [0, 1, 2, 3, 4].map((k) => mean(stack.map((row) => row[k])));
        })() : [0, 0, 0, 0.5, 0.5]);
    overall = tiltForExisting(overall, snap.existingEquityShare);
    const { mu, sd } = portfolioStats(overall);
    options[name] = {
      overallAlloc: allocDict(overall), expReturn: mu, volatility: sd,
      badYear: mu - 1.645 * sd, stressDecline: mu - 2.0 * sd,
      sharpe: Math.round(sharpeRatio(mu, sd) * 100) / 100,
      goals: rows,
    };
  });

  const wh = prof.weightedHorizonYears;
  const totalTarget = goals.reduce((s, g) => s + (g.target || 0), 0);
  const reqG = totalTarget > 0 ? requiredReturn(amount, totalTarget, wh, sip, stepUp) : 0;
  const consPr = wh > CAPITAL_PROTECTION_YEARS ? planningReturn(goalAllocation(wh, "Conservative")) : 0;
  const modPr = wh > CAPITAL_PROTECTION_YEARS ? planningReturn(goalAllocation(wh, "Moderate")) : 0;
  const aggrPr = wh > CAPITAL_PROTECTION_YEARS ? planningReturn(goalAllocation(wh, "Aggressive")) : 0;
  let requiredLabel;
  if (totalTarget <= 0) requiredLabel = "Not applicable";
  else if (reqG <= consPr) requiredLabel = "Low";
  else if (reqG <= modPr) requiredLabel = "Moderate";
  else if (reqG <= aggrPr) requiredLabel = "Moderate-High";
  else requiredLabel = "High";
  prof.requiredRisk = { label: requiredLabel, requiredReturn: reqG, bucket: bucketFor(wh) };

  const notes = [];
  if (override && override !== prof.label) {
    notes.push(`You are viewing the ${override} portfolio; based on your answers the suggested profile is ${prof.label}.`);
  }
  const gap = prof.willingness - prof.capacity;
  if (gap >= 2.5) {
    notes.push(`You are more comfortable with risk (willingness ${prof.willingness}/10) than your situation can comfortably afford (capacity ${prof.capacity}/10), so your score follows the lower figure.`);
  } else if (gap <= -2.5) {
    notes.push(`Your situation could support more risk (capacity ${prof.capacity}/10) than you are comfortable with (willingness ${prof.willingness}/10), so your score follows your comfort level. Long goals usually need some growth, so consider the higher-risk options too.`);
  }
  if (Math.abs(prof.stated - prof.quiz) >= 4) {
    notes.push("Your stated risk appetite and your answers to the scenario questions point in different directions, so we gave more weight to the scenario answers.");
  }
  if ((requiredLabel === "Moderate-High" || requiredLabel === "High") && prof.label !== "Aggressive") {
    notes.push(`To reach your goals as entered, your money would need to grow at roughly ${(reqG * 100).toFixed(1)}% a year (a 'Required Risk' of ${requiredLabel}) - higher than your recommended ${prof.label} profile targets. Consider a larger amount, a later date, lower targets, or a higher-risk option.`);
  }
  if (topup > 0) {
    notes.push(`Rs ${Math.round(topup).toLocaleString("en-IN")} of your investable amount was set aside first to build up your emergency fund (kept 100% liquid), before the rest was allocated to your goals.`);
  }
  if (snap.highInterestDebt) {
    notes.push("You reported some high-interest debt. Its cost likely exceeds typical investment returns, so consider repaying it before increasing investments further.");
  }
  goals.forEach((g) => {
    if (g.years <= CAPITAL_PROTECTION_YEARS) {
      notes.push(`'${g.name}' is ${g.years}${g.years===1?' year':' years'} or less away, so it is kept 100% in liquid funds.`);
    } else if (g.bucket === "Short" && rec !== "Conservative") {
      const eq = equityShare(goalAllocation(g.years, rec));
      notes.push(`'${g.name}' is only ${g.years} years away, so equity is limited to ${eq.toFixed(0)}% for this goal even though your profile is ${rec}.`);
    }
    if (g.kind === "retirement" && g.years <= 10 && rec === "Aggressive") {
      notes.push(`Retirement is only ${g.years} years away, yet the Aggressive option still carries high equity exposure. Consider the Moderate option as retirement gets closer.`);
    }
  });
  goals.forEach((g) => {
    if (g.fundedRatio !== null && g.fundedRatio !== undefined && g.fundedRatio < 0.999) {
      const shortfallRupees = (g.required || 0) - g.funding;
      notes.push(`'${g.name}' is only ${Math.round(g.fundedRatio * 100)}% funded at your current amount (about Rs ${Math.round(shortfallRupees).toLocaleString("en-IN")} short per ${sip ? "month" : "the plan"}). Consider a larger amount, a later date, or a lower target.`);
    }
  });
  if (snap.existingEquityShare !== null && snap.existingEquityShare >= 0.75) {
    notes.push(`Your existing investments are already about ${Math.round(snap.existingEquityShare * 100)}% equity, so new money has been tilted a little more toward debt/liquid to avoid over-concentration.`);
  }

  const health = financialHealth(inp, snap, goals);
  const overallMix = options[rec].overallAlloc;
  const distinctClasses = Object.values(overallMix).filter((v) => v >= 5.0).length;
  health["Investment Diversification"] = distinctClasses <= 2 ? "Low" : distinctClasses === 3 ? "Moderate" : "Good";

  return {
    mode: sip ? "SIP (monthly)" : "Lumpsum", amount, surplus, sipStepUp: stepUp,
    profile: prof, recommended: rec, goals, options, notes,
    assumptions: Object.fromEntries(ASSETS.map((a) => [a, { expectedReturn: ASSUMPTIONS[a][0], volatility: ASSUMPTIONS[a][1] }])),
    assumptionsNote: ASSUMPTIONS_NOTE, inflation: INFLATION,
    snapshot: snap, emergencyTopup, financialHealth: health,
  };
}

const Lakshya = {
  ASSETS, ASSUMPTIONS, ASSUMPTIONS_NOTE, GOAL_INFLATION, EMPLOYMENT_TYPES, PRIORITIES, PROFILES, QUIZ,
  N_SIMS, RISK_FREE_RATE,
  bucketFor, emergencyFundTarget, financialSnapshot, validateInputs, cleanGoals, buildGoals, riskProfile,
  goalAllocation, allocDict, equityShare, tiltForExisting, portfolioStats, sharpeRatio, planningReturn,
  requiredFunding, requiredReturn, simulate, financialHealth, buildPlan,
};

if (typeof module !== "undefined" && module.exports) module.exports = Lakshya;
if (typeof window !== "undefined") window.Lakshya = Lakshya;
