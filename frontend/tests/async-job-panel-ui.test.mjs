import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const jobPanelSource = await readFile(new URL("../app/async-job-panel.tsx", import.meta.url), "utf8");
const patternCandidatesSource = await readFile(new URL("../app/pattern-candidates-panel.tsx", import.meta.url), "utf8");
const statisticalAnalysisSource = await readFile(new URL("../app/statistical-analysis-panel.tsx", import.meta.url), "utf8");

test("async job hook exposes create/cancel/poll without action-language leaks", () => {
  assert.match(jobPanelSource, /export function useAsyncJob/);
  assert.match(jobPanelSource, /export function JobStatusBadge/);
  assert.match(jobPanelSource, /export function isJobCancellable/);
  const lowered = jobPanelSource.toLowerCase();
  assert.doesNotMatch(lowered, /"buy"|'buy'|"sell"|'sell'|gözlənilir/);
});

test("pattern candidates panel offers an async backtest-job alternative to the sync endpoint", () => {
  assert.match(patternCandidatesSource, /from "\.\/async-job-panel"/);
  assert.match(patternCandidatesSource, /pattern-candidates\/\$\{candidateId\}\/backtest-jobs/);
  assert.match(patternCandidatesSource, /BacktestJobCell/);
});

test("statistical analysis panel offers an async job alternative to the sync endpoint", () => {
  assert.match(statisticalAnalysisSource, /from "\.\/async-job-panel"/);
  assert.match(statisticalAnalysisSource, /replay-sessions\/\$\{sessionId\}\/statistical-analysis-jobs/);
  // The async result must feed the same rendering path as the sync result,
  // not a separate/duplicated result view.
  assert.match(statisticalAnalysisSource, /onCompleted:\s*setResult/);
});
