import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../app/visual-experiments-panel.tsx", import.meta.url);

test("visual experiments panel stays research-only and registers only frozen configuration", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /Phase 5 — tədqiqat konfiqurasiyası · ticarət siqnalı deyil/);
  assert.match(source, /model təlim\s+etmir/);
  assert.match(source, /api\/v2\/visual-experiments/);
  assert.match(source, /source_bar_fingerprint/);
  assert.match(source, /label_spec: \{/);
  assert.match(source, /horizon_bars: horizonBars/);
  assert.match(source, /up_threshold_bps: upThresholdBps/);
  assert.match(source, /down_threshold_bps: downThresholdBps/);
  assert.match(source, /observation_window_bars/);
  assert.match(source, /train_end_at/);
  assert.match(source, /validation_end_at/);
  assert.match(source, /Eksperimenti qeydə al/);
  assert.match(source, /expected_state_version: experiment\.state_version/);
  assert.match(source, /Arxivləşdir/);
  assert.match(source, /Model təlimi, qiymətləndirmə və qəbul\/rədd qərarı hələ yoxdur/);
  assert.match(source, /Heç bir vəziyyət real ticarət icazəsi vermir/);
  // Rendering job workflow: create, restore-after-refresh, cancel, and
  // completion result (sample count + dataset fingerprint) must all be wired.
  assert.match(source, /rendering-jobs`/);
  assert.match(source, /Dataset yarat/);
  assert.match(source, /RENDERING_JOB_STORAGE_PREFIX/);
  assert.match(source, /localStorage\.getItem\(storageKey\)/);
  assert.match(source, /asyncJob\.restore\(rememberedJobId\)/);
  assert.match(source, /localStorage\.setItem\(storageKey/);
  assert.match(source, /localStorage\.removeItem\(storageKey\)/);
  assert.match(source, /isJobCancellable/);
  assert.match(source, /Ləğv et/);
  assert.match(source, /result\.sample_count/);
  assert.match(source, /result\.manifest\.dataset_fingerprint/);
  assert.match(source, /experiment\.lifecycle_state !== "registered"/);
  const lowered = source.toLowerCase();
  assert.doesNotMatch(lowered, /placeorder|sendorder|positionsize|"buy"|'buy'|"sell"|'sell'/);
  // All 14 lifecycle states from the Phase 5 contract must be labelled.
  for (const state of [
    "registered", "rendering", "training", "evaluated", "accepted_for_shadow",
    "rejected", "archived", "blocked_by_data_quality", "invalid_leakage",
    "non_reproducible", "out_of_distribution", "insufficient_evidence",
    "failed", "cancelled",
  ]) {
    assert.match(source, new RegExp(`${state}:`));
  }
});
