/* jsdom smoke test for the assembled index.html + app.js + logic.js artifact.
   Drives the wizard through two branches (mirroring the Python build's
   apptest_smoke.py / apptest_smoke2.py coverage) and checks for no exceptions
   plus the expected conditional fields / plan output. */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

let FAILS = 0;
function check(label, cond) {
  if (cond) console.log("  PASS  " + label);
  else { console.log("  FAIL  " + label); FAILS++; }
}

function newDom() {
  let html = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
  html = html.replace(/<script src="logic\.js"><\/script>\s*<script src="app\.js"><\/script>\s*<script>App\.init\(\);<\/script>/, "");
  const dom = new JSDOM(html, { runScripts: "dangerously", url: "file://" + __dirname + "/" });
  dom.window.HTMLElement.prototype.scrollIntoView = function () {};
  const logicSrc = fs.readFileSync(path.join(__dirname, "logic.js"), "utf8");
  const appSrc = fs.readFileSync(path.join(__dirname, "app.js"), "utf8");
  dom.window.eval(logicSrc);
  dom.window.eval(appSrc);
  dom.window.eval("App.init();");
  return dom;
}

function setVal(doc, selector, value, evt) {
  const el = doc.querySelector(selector);
  if (!el) throw new Error("missing selector " + selector);
  el.value = value;
  el.dispatchEvent(new doc.defaultView.Event(evt || "input", { bubbles: true }));
}
function click(doc, selector) {
  const el = doc.querySelector(selector);
  if (!el) throw new Error("missing selector " + selector);
  el.click();
}
function clickNth(doc, selector, n) {
  const els = doc.querySelectorAll(selector);
  if (!els[n]) throw new Error("missing nth selector " + selector + " [" + n + "]");
  els[n].click();
}
function text(doc, selector) {
  const el = doc.querySelector(selector);
  return el ? el.textContent : null;
}

async function main() {
console.log("=== Branch A: dependents + SIP + step-up, EMI high-interest, no life insurance ===");
{
  const dom = newDom();
  const win = dom.window, doc = win.document;
  win.onerror = (msg) => { console.log("  FAIL  uncaught error: " + msg); FAILS++; };

  click(doc, "#app .primary"); // intro -> about you
  check("A: reached About You", doc.querySelector("h2").textContent === "About you");

  setVal(doc, "#app input[type=number]", "35"); // age (first number input)
  // dependents is the 2nd number input on this step
  doc.querySelectorAll("#app input[type=number]")[1].value = "2";
  doc.querySelectorAll("#app input[type=number]")[1].dispatchEvent(new win.Event("input", { bubbles: true }));
  click(doc, "#app .primary");
  check("A: reached Financial life", doc.querySelector("h2").textContent === "Financial life");

  const nums2 = () => doc.querySelectorAll("#app input[type=number]");
  nums2()[0].value = "80000"; nums2()[0].dispatchEvent(new win.Event("input", { bubbles: true })); // income
  nums2()[1].value = "40000"; nums2()[1].dispatchEvent(new win.Event("input", { bubbles: true })); // expenses
  nums2()[2].value = "20000"; nums2()[2].dispatchEvent(new win.Event("input", { bubbles: true })); // EMI -> should reveal high-interest checkbox
  check("A: EMI high-interest checkbox appears after EMI>0", !!Array.from(doc.querySelectorAll("#app label")).find((l) => l.textContent.includes("high-interest debt")));
  // check the high-interest checkbox + sole earner checkbox (dependents>0 reveals it) + leave life insurance UNCHECKED (default checked -> uncheck to trigger warning)
  const checkboxes = () => doc.querySelectorAll("#app input[type=checkbox]");
  check("A: sole-earner + life-insurance checkboxes appear (dependents>0)", checkboxes().length >= 3);
  // toggle emiHighInterest (first checkbox on this step), soleEarner, and uncheck hasLifeInsurance
  checkboxes()[0].click(); // emiHighInterest
  const soleEarnerCb = Array.from(checkboxes()).find((c) => c.closest("label").textContent.includes("sole/primary"));
  const lifeInsCb = Array.from(checkboxes()).find((c) => c.closest("label").textContent.includes("life insurance"));
  soleEarnerCb.click();
  lifeInsCb.click(); // was checked by default -> unchecked now
  click(doc, "#app .primary");
  check("A: reached Money & goals", doc.querySelector("h2").textContent === "How will you invest?");

  setVal(doc, "#app input[type=number]", "15000"); // amount
  setVal(doc, "#app input[type=range]", "0.10"); // step-up slider
  // fill the default goal row
  const goalInputs = doc.querySelectorAll(".goal-row input");
  goalInputs[0].value = "House"; goalInputs[0].dispatchEvent(new win.Event("input", { bubbles: true })); // name
  goalInputs[1].value = "10"; goalInputs[1].dispatchEvent(new win.Event("input", { bubbles: true })); // years
  goalInputs[2].value = "3000000"; goalInputs[2].dispatchEvent(new win.Event("input", { bubbles: true })); // cost
  const inflSelect = doc.querySelectorAll(".goal-row select")[1];
  inflSelect.value = "Housing"; inflSelect.dispatchEvent(new win.Event("change", { bubbles: true }));
  click(doc, "#app .primary");
  check("A: reached Risk comfort", doc.querySelector("h2").textContent === "How do you feel about risk?");

  clickNth(doc, "#app .choice", 2); // statedRisk = High (3rd of Low/Moderate/High)
  // answer each quiz question with its last (highest-risk) option
  doc.querySelectorAll(".field").forEach(() => {});
  const quizBlocksGroups = doc.querySelectorAll(".choice-grid");
  quizBlocksGroups.forEach((grp) => { const opts = grp.querySelectorAll(".choice-block"); opts[opts.length - 1].click(); });
  click(doc, "#app .primary");
  check("A: reached Review", doc.querySelector("h2").textContent === "Review");

  click(doc, "#app .primary"); // See my plan
  check("A: reached results with no crash", doc.querySelector("h1") && doc.querySelector("h1").textContent === "Your plan");
  check("A: scorecard rendered", doc.querySelectorAll(".score-item").length > 0);
  check("A: alt-grid rendered with 3 cards", doc.querySelectorAll(".alt-card").length === 3);
  check("A: goals table has a row for House", text(doc, "table.plan-table").includes("House"));
  check("A: health insurance gap NOT flagged (has insurance)", !doc.querySelector("#app").innerHTML.includes("no health insurance"));

  // exercise tabs
  const tabBtns = doc.querySelectorAll(".tab-btn");
  const whatifBtn = Array.from(tabBtns).find((b) => b.textContent === "What-if");
  whatifBtn.click();
  check("A: What-if tab shows goal selector", !!doc.querySelector("#app select"));
  const amtInputs = doc.querySelectorAll("#app input[type=number]");
  if (amtInputs.length) { amtInputs[0].value = "20000"; amtInputs[0].dispatchEvent(new win.Event("input", { bubbles: true })); }
  if (amtInputs.length > 1) { amtInputs[1].value = "8"; amtInputs[1].dispatchEvent(new win.Event("input", { bubbles: true })); }
  const calcBtn = Array.from(doc.querySelectorAll("button")).find((b) => b.textContent === "Calculate");
  if (calcBtn) calcBtn.click();
  check("A: What-if produced a result banner", doc.querySelector(".banner.info") !== null);

  const advisorBtn = Array.from(doc.querySelectorAll(".tab-btn")).find((b) => b.textContent === "Ask the advisor");
  advisorBtn.click();
  const faqBtn = doc.querySelector(".suggest-row button");
  faqBtn.click();
  check("A: advisor FAQ produced a chat message", doc.querySelectorAll(".chat-msg").length === 2);

  // free-text "Ask" with no window.claude present (as in this headless test) must fall back gracefully,
  // never throw, and never silently do nothing
  const advisorInput = doc.getElementById("advisorInput");
  advisorInput.value = "What if I invest more?";
  advisorInput.dispatchEvent(new win.Event("input", { bubbles: true }));
  await win.App.askFree();
  check("A: free-text Ask falls back without a live AI capability", doc.querySelectorAll(".chat-msg").length === 4);
  check("A: free-text fallback answer references the question asked", doc.querySelectorAll(".chat-msg.bot")[1].textContent.includes("What if I invest more?"));

  // alt-grid override
  const viewInsteadBtns = doc.querySelectorAll(".alt-grid button");
  if (viewInsteadBtns.length) {
    viewInsteadBtns[0].click();
    check("A: alt-grid override rebuilt the plan without crashing", doc.querySelector("h1").textContent === "Your plan");
  }
}

console.log("=== Branch B: no dependents, Lumpsum, Student, no goals (open wealth-building) ===");
{
  const dom = newDom();
  const win = dom.window, doc = win.document;
  win.onerror = (msg) => { console.log("  FAIL  uncaught error: " + msg); FAILS++; };

  click(doc, "#app .primary");
  setVal(doc, "#app input[type=number]", "22"); // age
  const empSelect = doc.querySelector("#app select");
  empSelect.value = "Student"; empSelect.dispatchEvent(new win.Event("change", { bubbles: true }));
  // uncheck "Include retirement as a goal"
  doc.querySelector("#app input[type=checkbox]").click();
  check("B: retirement age field hidden once unchecked", !doc.querySelector("#app").innerHTML.includes("retirement age"));
  click(doc, "#app .primary");

  check("B: reached Financial life", doc.querySelector("h2").textContent === "Financial life");
  const bNums = doc.querySelectorAll("#app input[type=number]");
  bNums[1].value = "15000"; bNums[1].dispatchEvent(new win.Event("input", { bubbles: true })); // expenses (income left blank, is bNums[0])
  check("B: no EMI -> high-interest checkbox absent", !Array.from(doc.querySelectorAll("#app label")).some((l) => l.textContent.includes("high-interest debt")));
  check("B: no dependents -> sole-earner/life-insurance checkboxes absent", doc.querySelectorAll("#app input[type=checkbox]").length === 1);
  click(doc, "#app .primary");

  check("B: reached Money & goals", doc.querySelector("h2").textContent === "How will you invest?");
  clickNth(doc, "#app .choice", 1); // Lumpsum
  setVal(doc, "#app input[type=number]", "500000"); // amount
  check("B: step-up slider hidden in Lumpsum mode", !doc.querySelector("#app input[type=range]"));
  // remove the default empty goal row entirely isn't possible (min 1 row), leave name blank -> cleanGoals filters it out
  click(doc, "#app .primary");

  check("B: reached Risk comfort", doc.querySelector("h2").textContent === "How do you feel about risk?");
  click(doc, "#app .primary"); // leave quiz unanswered -> defaults
  check("B: reached Review", doc.querySelector("h2").textContent === "Review");
  click(doc, "#app .primary");

  check("B: reached results with no crash", doc.querySelector("h1") && doc.querySelector("h1").textContent === "Your plan");
  check("B: a 'no goals' / wealth-building note or goal present", doc.querySelector("table.plan-table") !== null);
  check("B: financial health scorecard still renders with no income", doc.querySelectorAll(".score-item").length > 0);

  const dlBtn = Array.from(doc.querySelectorAll(".tab-btn")).find((b) => b.textContent === "Download");
  dlBtn.click();
  check("B: Download tab renders", !!Array.from(doc.querySelectorAll("button")).find((b) => b.textContent.includes("Copy plan summary")));
}

console.log("\n" + "=".repeat(60));
if (FAILS > 0) { console.log(FAILS + " CHECK(S) FAILED"); process.exit(1); }
else { console.log("ALL CHECKS PASSED."); }
}

main();
