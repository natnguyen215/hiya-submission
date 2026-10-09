// Browser check of the whole app: real Chrome pages, the running server, and its LLM (Gemini, or none).
// It covers what the pytest tests cannot: the React views, the counselor's card buttons, and what
// each role sees. It is optional and not part of `tasks.py test`, so Playwright is not a dependency.
//
// Run it (the server must be running, see the README):
//   npm install --prefix .pw playwright@1.56.1     (once; .pw/ is outside git)
//   NODE_PATH=.pw/node_modules node eval/browser_check.js [live|sim|all]
// It launches Playwright's Chromium, or set CHANNEL=chrome to use the installed Chrome.
// Gemini cost: about 15 requests for "live" and 35 for each simulated script.
//
// "live": typed turns in the counselor and parent pages: a card, "I'll clarify", "Not an issue",
//         the button giving up focus, a broad summon, End call and the recap.
// "sim":  the observer plays each script in SCRIPTS (default demo_call; only the observer's scripts) as text only, then checks
//         who saw which cards and the recap in every page.
const { chromium } = require("playwright");

const BASE = process.env.BASE || "http://localhost:8000";
const results = [];

function check(name, ok, detail = "") {
  results.push(!!ok);
  console.log(`${ok ? "PASS" : "FAIL"} ${name}${detail ? " — " + detail : ""}`);
}

async function open(context, path) {
  const page = await context.newPage();
  page.on("pageerror", (error) => console.log(`[page error ${path}] ${error.message}`));
  await page.goto(BASE + path);
  await page.waitForSelector(".topbar", { timeout: 15000 });
  return page;
}

async function openRoom(browser, name) {
  const context = await browser.newContext();
  const room = `${name}-${Date.now()}`; // a fresh room, so an earlier call can't interfere
  return {
    context,
    observer: await open(context, `/observer?room=${room}`),
    counselor: await open(context, `/call?room=${room}&role=counselor`),
    parent: await open(context, `/call?room=${room}&role=parent`),
  };
}

async function say(page, text) {
  await page.fill(".composer input", text);
  await page.press(".composer input", "Enter");
}

const beaconLines = (page) => page.$$eval(".transcript .turn-beacon .turn-text", (turns) => turns.map((t) => t.innerText));

async function beaconIsQuiet(page) {
  await page.waitForSelector(".speaking-banner", { state: "detached", timeout: 60000 }).catch(() => {});
}

async function live(browser) {
  const { context, counselor, parent } = await openRoom(browser, "check-live");
  await counselor.click("button:has-text('Start call')");
  await counselor.waitForSelector(".transcript .turn-beacon");
  const opening = (await beaconLines(counselor))[0];
  check("opening line says Beacon is an AI and teaches the wake word", /AI assistant/.test(opening) && /my name/.test(opening));
  await beaconIsQuiet(counselor);

  // A misunderstanding → a card → "I'll clarify": Beacon waits one extra counselor turn, then asks.
  await say(counselor, "Daniel's total aid package is $31,500.");
  await say(parent, "Oh, thank goodness, so it's covered.");
  const card = await counselor.waitForSelector(".nudges .flag-nudged", { timeout: 60000 }).catch(() => null);
  check("'so it's covered' gives the counselor a card", card);
  if (card) {
    check("the parent sees no card", (await parent.$$(".flag-card")).length === 0);
    await counselor.click(".nudges .flag-nudged button:has-text(\"I'll clarify\")");
    await counselor.waitForSelector(".flag-note:has-text('Beacon will wait for you')");
    const focused = await counselor.evaluate(() => document.activeElement?.tagName);
    check("the card button gives up focus after the click", focused !== "BUTTON", focused);
    await counselor.keyboard.press("Space");
    check("Space after the click does not press 'Not an issue'", (await counselor.$$(".nudges .flag-dismissed")).length === 0);
    const before = (await beaconLines(counselor)).length;
    await say(counselor, "Okay, let's move on to housing for a second.");
    await counselor.waitForTimeout(12000); // time for the analysis and the pause
    check("after 'I'll clarify', Beacon waits through one counselor turn", (await beaconLines(counselor)).length === before);
    await say(counselor, "Housing and meals are estimated at $16,500 for the year.");
    const asked = await counselor
      .waitForFunction((n) => document.querySelectorAll(".transcript .turn-beacon").length > n, before, { timeout: 45000 })
      .then(() => true, () => false);
    check("Beacon asks after the extra turn", asked);
    await beaconIsQuiet(counselor);
  }

  // A second misunderstanding → "Not an issue": Beacon never speaks about it.
  await say(counselor, "Daniel was also selected for verification.");
  await say(parent, "Oh good, so we're verified?");
  const verification = ".nudges .flag-nudged:has-text('verif')";
  const card2 = await counselor.waitForSelector(verification, { timeout: 60000 }).catch(() => null);
  check("'so we're verified?' gives the counselor a card", card2);
  if (card2) {
    await counselor.click(`${verification} button:has-text('Not an issue')`);
    await counselor.waitForSelector(".nudges .flag-dismissed:has-text('Dismissed')");
    check("a dismissed card shows 'Dismissed'", true);
    await say(counselor, "Next, you'll accept the awards in the student portal.");
    await counselor.waitForTimeout(8000);
    await say(counselor, "You'll get an email confirmation after you submit.");
    await counselor.waitForTimeout(12000);
    const aboutVerification = (await beaconLines(counselor)).filter((line) => /verif/i.test(line));
    check("Beacon never speaks about a dismissed card", aboutVerification.length === 0, aboutVerification.join(" / "));
  }

  // The broad summon that once timed out.
  const before = (await beaconLines(counselor)).length;
  const started = Date.now();
  await say(parent, "Beacon, what is all the info that you have");
  const answered = await counselor
    .waitForFunction((n) => document.querySelectorAll(".transcript .turn-beacon").length > n, before, { timeout: 45000 })
    .then(() => true, () => false);
  const answer = (await beaconLines(counselor)).slice(before).join(" / ");
  check("a broad summon gets an answer", answered, `${((Date.now() - started) / 1000).toFixed(1)} s: ${answer}`);

  await beaconIsQuiet(counselor);
  await counselor.click("button:has-text('End call')");
  await parent.waitForSelector(".family-recap, .recap-error", { timeout: 120000 });
  check("the recap appears in the parent page", (await parent.$$(".family-recap")).length === 1);
  await context.close();
}

async function simulate(browser, script) {
  const { context, observer, counselor, parent } = await openRoom(browser, `check-${script}`);
  await observer.selectOption("select", script);
  check(`${script}: "Text only" is ticked by default`, await observer.isChecked("text=Text only (no audio) >> input"));
  await observer.click("button:has-text('Play')");
  await observer.waitForSelector(".progress >> text=Finished", { timeout: 15 * 60 * 1000 });
  for (const page of [observer, counselor, parent]) {
    await page.waitForSelector(".family-recap, .recap-error", { timeout: 120000 });
  }
  const allCards = await observer.$$eval(".area-flags .flag-card", (cards) => cards.length);
  const counselorCards = await counselor.$$eval(".nudges .flag-card", (cards) => cards.length);
  check(`${script}: the parent page has no cards and no Beacon panel`, (await parent.$$(".flag-card, .nudges")).length === 0);
  check(`${script}: the counselor sees at most the observer's cards`, counselorCards <= allCards, `${counselorCards} of ${allCards}`);
  check(`${script}: the recap is ready`, (await parent.$$(".family-recap")).length === 1);
  check(`${script}: the recap has no unverified numbers`, (await parent.$$(".recap-unverified")).length === 0);
  const errors = await observer.$$eval(".log-error", (entries) => entries.map((e) => e.innerText));
  check(`${script}: no errors in the Decision Log`, errors.length === 0, errors.slice(0, 2).join(" | "));
  console.log(`  Beacon said: ${(await beaconLines(observer)).slice(1).join(" / ") || "(only the opening line)"}`);
  await context.close();
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.CHANNEL });
  const which = process.argv[2] || "all";
  try {
    if (which === "all" || which === "live") await live(browser);
    if (which === "all" || which === "sim") {
      for (const script of (process.env.SCRIPTS || "demo_call").split(",")) await simulate(browser, script);
    }
  } catch (error) {
    check("no unexpected exception", false, error.stack);
  } finally {
    await browser.close();
    const passed = results.filter(Boolean).length;
    console.log(`\n${passed}/${results.length} checks passed`);
    process.exitCode = passed === results.length ? 0 : 1;
  }
})();
