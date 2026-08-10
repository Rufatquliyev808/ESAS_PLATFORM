import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const jobPanelSource = await readFile(new URL("../app/async-job-panel.tsx", import.meta.url), "utf8");
const patternCandidatesSource = await readFile(new URL("../app/pattern-candidates-panel.tsx", import.meta.url), "utf8");
const statisticalAnalysisSource = await readFile(new URL("../app/statistical-analysis-panel.tsx", import.meta.url), "utf8");
const visualExperimentsSource = await readFile(new URL("../app/visual-experiments-panel.tsx", import.meta.url), "utf8");

test("async job hook exposes create/cancel/poll/restore without action-language leaks", () => {
  assert.match(jobPanelSource, /export function useAsyncJob/);
  assert.match(jobPanelSource, /export function JobStatusBadge/);
  assert.match(jobPanelSource, /export function isJobCancellable/);
  // restore lets a caller re-attach to an already-known job_id (e.g.
  // remembered across a page reload) without creating a duplicate job.
  assert.match(jobPanelSource, /restore: pollDetail/);
  const lowered = jobPanelSource.toLowerCase();
  assert.doesNotMatch(lowered, /"buy"|'buy'|"sell"|'sell'|gözlənilir/);
});

test("visual experiments panel offers an async rendering-job workflow with reload-safe restore", () => {
  assert.match(visualExperimentsSource, /from "\.\/async-job-panel"/);
  assert.match(visualExperimentsSource, /visual-experiments\/\$\{experiment\.experiment_id\}\/rendering-jobs/);
  assert.match(visualExperimentsSource, /RenderingJobCell/);
  assert.match(visualExperimentsSource, /asyncJob\.restore/);
});

test("visual experiments panel offers an async training+evaluation job workflow", () => {
  assert.match(visualExperimentsSource, /visual-experiments\/\$\{experiment\.experiment_id\}\/training-jobs/);
  assert.match(visualExperimentsSource, /TrainingJobCell/);
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
