#!/usr/bin/env node
/**
 * Drives the live Database Surgeon web UI for an OpenScreen recording.
 * Timing targets ~110–120s. Narrator speaks from docs/SPEAK_ALONG_SCRIPT.md.
 *
 *   npx --yes playwright install chromium
 *   node scripts/demo_ui_walkthrough.mjs
 */
import { chromium } from "playwright";
import { setTimeout as sleep } from "node:timers/promises";

const BASE = process.env.DEMO_BASE || "http://127.0.0.1:3100";
const HOLD = Number(process.env.DEMO_HOLD_MS || 3500);

async function pause(ms, label) {
  if (label) console.log(`… ${label} (${ms}ms)`);
  await sleep(ms);
}

async function pickSystem(page, value) {
  const sel = page.locator('select[aria-label="Research system"]');
  if (await sel.count()) {
    await sel.selectOption(value).catch(async () => {
      await sel.selectOption({ label: new RegExp(value.replace(/-/g, ".?"), "i") }).catch(() => {});
    });
  }
}

async function pickBaseline(page, value) {
  const sel = page.locator('select[aria-label="Research baseline"]');
  if (await sel.count()) await sel.selectOption(value).catch(() => {});
}

async function clickTab(page, name) {
  const tab = page.getByRole("tab", { name: new RegExp(name, "i") }).or(
    page.getByRole("button", { name: new RegExp(name, "i") }),
  );
  if (await tab.count()) await tab.first().click().catch(() => {});
}

async function main() {
  console.log("Launching Chromium — grant OpenScreen a few seconds, then speak.");
  const browser = await chromium.launch({
    headless: false,
    args: ["--window-size=1440,900", "--window-position=80,40"],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  await page.goto(`${BASE}/research`, { waitUntil: "networkidle" });
  await page.evaluate(() => {
    document.title = "Database Surgeon";
  });
  console.log("READY — start OpenScreen record on window 'Database Surgeon'");
  await pause(HOLD, "hold for recorder");

  // A — Problem: open-raw
  console.log("PART A problem");
  await pickSystem(page, "open-raw");
  await pickBaseline(page, "frontier-raw");
  await pause(9000, "open-raw stats");

  // B — Harness
  console.log("PART B harness");
  await pickSystem(page, "open-harness");
  await pause(5000, "open-harness KPIs");
  // hover / scroll charts
  await page.mouse.wheel(0, 420);
  await pause(3500, "tradeoff charts");
  await page.mouse.wheel(0, -420);

  // D early — system parade (measurements)
  console.log("PART D system parade");
  for (const sys of ["rules-only", "fw-fast-raw", "frontier-raw", "fw-fast-harness", "open-harness"]) {
    await pickSystem(page, sys);
    await pause(2200, sys);
  }

  // Paired statistics
  console.log("PART D paired stats");
  await clickTab(page, "Paired statistics");
  await pickBaseline(page, "open-raw");
  await pickSystem(page, "open-harness");
  await pause(7000, "McNemar vs open-raw");
  await pickBaseline(page, "frontier-raw");
  await pause(4000, "McNemar vs frontier");

  // Query evidence
  await clickTab(page, "Query evidence");
  await pause(4000, "query evidence");

  // C — Live surgery
  console.log("PART C live surgery");
  await page.goto(`${BASE}/demo`, { waitUntil: "networkidle" });
  await page.evaluate(() => {
    document.title = "Database Surgeon";
  });
  await page.getByRole("button", { name: /Judge pitch/i }).click().catch(() => {});
  await pause(5000, "judge pitch KPIs");

  await page.getByRole("button", { name: /Live surgery/i }).click();
  await pause(1500, "surgery tab");

  // Tier 1
  const presets = page.locator(".preset-card");
  if (await presets.count()) await presets.nth(0).click();
  await pause(800);
  await page.getByRole("button", { name: /Run surgery|Replay recorded trace/i }).first().click();
  await pause(7000, "tier1 result");

  // Tier 2
  if (await presets.count()) await presets.nth(1).click();
  await pause(800);
  await page.getByRole("button", { name: /Replay recorded trace|Run surgery/i }).first().click();
  await pause(9000, "tier2 correlated");

  // Tier 3
  if (await presets.count()) await presets.nth(2).click();
  await pause(800);
  await page.getByRole("button", { name: /Replay recorded trace|Run surgery/i }).first().click();
  await pause(8000, "tier3 null trap");

  // Experiments ledger
  await page.getByRole("button", { name: /Experiments/i }).click().catch(() => {});
  await pause(5000, "experiments ledger");

  // Close on pitch
  await page.getByRole("button", { name: /Judge pitch/i }).click().catch(() => {});
  await pause(4000, "close");

  console.log("DONE walkthrough");
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
