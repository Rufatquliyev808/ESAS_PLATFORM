# ESAS Platform — Dəyişiklik Tarixçəsi

Bu fayl ESAS Platform-da edilən əsas dəyişiklikləri izləyir.

Format Semantic Versioning prinsipinə əsaslanır:

`MAJOR.MINOR.PATCH`

## Unreleased

### Added — Liquidity-level reaction backtest statistics (backend only, no API/UI yet)

- User asked for a much larger feature: multi-timeframe (30m/1h/4h/1d)
  liquidity levels with trend direction, a self-learning system that finds
  which indicator readings best predict whether price reverses or breaks
  through a level, a live signal saying "buy/sell expected" in literal
  terms, and a journal of those signals with entry price/points moved.
- **Declined the literal "buy/sell expected" framing**: it directly
  conflicts with the platform's research-only positioning enforced
  everywhere else in this codebase (every module carries
  `interpretation: "research_observation_not_trading_signal"`; tests
  assert the absence of buy/sell language). This request is, in
  substance, Phase 8 (Decision/Risk Layer) territory -- still `PLANNED`
  in the roadmap, coming after Phase 5-7. Confirmed with the user: the
  live indicator will use research language (bullish/bearish-leaning,
  historical reliability percentage) instead, and the first increment is
  backend/backtest statistics only, with no API or UI yet.
- `backend/app/analysis/bars.py`: added `M30` (1800s), `H4` (14400s), `D1`
  (86400s) timeframes for the requested 30m/1h/4h/1d granularities (`H1`
  already existed). `BAR_BUILDER_VERSION` `1.1.0 -> 1.2.0`.
- New `backend/app/analysis/liquidity_reaction.py`:
  `compute_liquidity_reaction_statistics(bars, pools, ...)` takes the
  `LiquidityPool` tuple already built by the existing
  `liquidity_sweep.py` (no pool-building logic duplicated). Unlike
  `liquidity_sweep.py`'s narrower "confirmed sweep" definition (which by
  construction only records touches that already reversed), this looks at
  *every* touch of a pool level and classifies the forward outcome over
  `horizon_bars`: `reversed` (price closes back on the approach side),
  `continued` (price closes through to the far side), or `ambiguous`
  (neither move clears `reaction_threshold_bps` -- excluded from the
  directional percentage rather than counted as either outcome).
  Overlapping touches of the same pool are purged with a `horizon_bars`
  embargo, matching the purge/embargo convention already used for
  pattern-candidate backtests. `buy_side` (resistance, approached from
  below) and `sell_side` (support, approached from above) pools are
  reported separately, each with a reversed-percentage and a 95%
  confidence interval computed as a binomial proportion
  (`p +/- 1.96 * sqrt(p(1-p)/n)`), gated on a minimum sample of 30
  directional touches (`insufficient_data` below that).
- Deliberately out of scope for this increment: running this across all
  four timeframes at once, a live "lean" indicator on the dashboard, the
  "self-learning" search over indicator-reading combinations (which will
  need its own multiple-testing correction, since it implies running many
  trials), and the signal journal UI. All planned as separate follow-up
  increments.
- Verification: new `test_liquidity_reaction.py` (10 tests) covering
  buy_side reversal/continuation/ambiguous classification, sell_side
  bounce/breakdown, purge/embargo, the insufficient-data/completed sample
  threshold, fingerprint determinism, unsafe-parameter rejection, and an
  empty pool list as a valid input. `test_analysis_bars.py`'s parametrized
  timeframe test now also covers `M30`/`H4`/`D1`. Full backend regression:
  `462 passed`. Frontend untouched.

### Added — Expand the live consensus panel with 5 more oscillators (Stochastic, CCI, Williams %R, MACD, ADX)

- Direct follow-up to the live indicator consensus panel: the user
  re-shared the TradingView reference image and asked to continue closing
  the gap (TradingView shows 11 oscillators, the first cut only had RSI).
  Chose to expand oscillators first.
- New `backend/app/analysis/oscillators.py`, deliberately kept separate
  from `indicators.py` (which stays untouched -- it's shared, stable
  infrastructure used across Phase 4's detectors, and none of them need
  these new oscillators): `calculate_stochastic_k()` (slow %K, SMA-
  smoothed raw %K; a zero-range window returns the neutral midpoint 50.0
  rather than dividing by zero), `calculate_cci()` (zero mean-deviation
  returns 0.0, CCI's own neutral value), `calculate_williams_r()` (zero-
  range midpoint -50.0), `calculate_macd()` (fast/slow EMA difference plus
  a signal EMA computed only over the already-ready MACD values),
  `calculate_adx()` (classic Wilder method, matching the same smoothing
  style already used for ATR/RSI in `indicators.py`, returning ADX along
  with its +DI/-DI components). All causal (closed bars only),
  deterministic, versioned, following the existing `indicators.py`
  conventions (ready/insufficient_data points, per-module fingerprinting).
- `backend/app/analysis/indicator_consensus.py`: `compute_indicator_consensus()`
  now takes a required `oscillators: OscillatorSetResult` parameter.
  Stochastic/CCI/Williams %R reuse a new shared
  `_classify_below_oversold_above_overbought()` helper (same oversold/
  overbought shape as RSI). MACD: bullish-leaning when the line is above
  its signal, bearish-leaning when below. **ADX is handled specially**: it
  measures trend *strength*, not direction, so a lean is only assigned
  when ADX is above the trending threshold (25) *and* +DI/-DI disagree in
  a clear direction; a weak trend (ADX <= 25) is reported neutral
  regardless of +DI/-DI, which is documented in the code. Oscillator count
  went from 1 to 6; `CONSENSUS_VERSION` `1.0.0 -> 2.0.0`.
- `backend/app/analysis/live_analysis.py`: now also calls
  `build_oscillator_set()` and exposes the raw oscillator series in a new
  `oscillators` response field, with `oscillator_fingerprint` /
  `oscillator_package_version` added to `lineage`.
  `LIVE_ANALYSIS_API_VERSION` `1.0.0 -> 1.1.0`.
- Frontend: `live-technical-summary-panel.tsx` gained a detail table per
  group (oscillators, moving averages) below the gauge cards -- indicator
  name, value, and a lean pill -- similar in spirit to TradingView's
  expandable indicator tables, reusing the existing `.status-pill`/
  `tone-*` styling.
- Verified live in the browser end-to-end again (55 minutes of synthetic
  GOLD ticks this time, up from 30, so MACD's `slow(26) + signal(9) = 35`
  bar requirement is comfortably met and all 6 oscillators reach "ready"):
  confirmed correct values via a direct API call, then confirmed the
  panel renders the same six-row oscillator table and one-row moving-
  average table correctly. This time the browser-visibility override used
  for triggering a manual refresh was removed immediately after use
  (rather than left in place, which is what caused the request-loop
  artifact during the previous panel's verification) -- no request storm,
  no console errors. Real production services on ports 8000/3000 ran
  undisturbed throughout.
- Verification: `test_oscillators.py` (12 tests, including hand-verified
  exact values for CCI, Williams %R, and a constant-case MACD series) and
  updated `test_indicator_consensus.py` (now covers all 6 oscillators,
  including a dedicated MACD-crossover and weak-ADX-is-neutral test).
  Updated `test_live_technical_summary_api.py` for the new response
  shape. Full backend regression: `449 passed`. Frontend lint clean,
  `12/12` tests, production build clean.

### Added — Live indicator consensus panel on the main dashboard screen

- User asked to add a view similar to TradingView's "Technical Analysis"
  widget (an oscillator/moving-average Buy/Sell/Neutral consensus gauge)
  to ESAS's main screen. Two approaches were discussed -- embedding
  TradingView's own widget, or building our own equivalent computation --
  and the user chose to build our own.
- **Important boundary:** TradingView's "Покупать/Продавать" (Buy/Sell)
  language directly conflicts with the platform's "research only, not a
  trading signal" principle that every other module in this codebase
  enforces (`interpretation: "research_observation_not_trading_signal"`
  everywhere, tests asserting the absence of "buy"/"sell" wording). So the
  labeling was changed to neutral, observational language --
  "bullish_leaning" / "bearish_leaning" / "neutral" -- with a mandatory
  "TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT TÖVSİYƏSİ DEYİL" (this is a research
  observation, not a trading recommendation) banner on the panel.
- **Architectural departure from everything else built this session:**
  every prior analysis module operated on a `completed` replay session's
  fixed, fingerprinted snapshot (for reproducibility). This is the first
  analysis to run over a **live, constantly-changing** rolling window --
  no replay session is required at all, and repeated calls are expected
  to differ as new ticks arrive, so there is no dataset-drift guard (the
  opposite of every prior module).
- New `backend/app/analysis/indicator_consensus.py`:
  `compute_indicator_consensus()` classifies the latest RSI and EMA
  readings from an already-computed `IndicatorSetResult` (RSI < 30 ->
  bullish-leaning/oversold, > 70 -> bearish-leaning/overbought; close
  above/below EMA -> the corresponding lean), then counts oscillator vs.
  moving-average sub-totals and an overall consensus. Deliberately scoped
  to 2 indicators (RSI, EMA) rather than TradingView's ~16, reusing the
  already-tested `indicators.py` module unchanged; more indicators
  (Stochastic, CCI, ADX, MACD, additional MAs) are a future increment.
- New `backend/app/analysis/live_analysis.py`:
  `create_live_technical_summary()` builds bars directly from
  `iter_tick_batches` for the most recent `bar_limit` window ending at
  `datetime.now(UTC)` -- no `ReplaySession` involved -- then computes
  indicators and the consensus. The response's `lineage.reproducible` is
  explicitly `false`, with a note explaining why.
- New protected `GET /api/v2/live-technical-summary` endpoint (`symbol`,
  `timeframe`, `ema_period`, `rsi_period`, `atr_period`, `bar_limit` query
  params).
- Frontend: new `live-technical-summary-panel.tsx`, added to the default
  "Nəticələr" (results) screen, polling every 5s following the exact
  pattern already used by the main dashboard's own operational-status
  polling. Three gauge cards: oscillators (RSI), overall, moving averages
  (EMA).
- Verified live in the browser end-to-end (synthetic GOLD ticks in a
  disposable scratch database, temporary backend/frontend, real
  production database and services never touched): confirmed correct
  RSI/EMA computation via direct API call, then confirmed the panel
  renders the same classifications correctly on the dashboard. During
  verification, the automated browser's `document.visibilityState` was
  (as in earlier sessions) always `"hidden"`, which blocks the panel's
  polling gate exactly like it blocks the main dashboard's own polling;
  briefly overriding it to trigger one clean fetch confirmed correct
  rendering, and leaving the override in place (rather than restoring it)
  produced a rapid request loop -- but this reproduced identically on the
  *pre-existing, already-shipped* `/status/operational` polling as well,
  confirming it was an artifact of the override interacting with the
  automated browser's own internal visibility polling, not a bug in
  either the new panel or existing code. Real production services on
  ports 8000/3000 ran undisturbed throughout.
- Verification: new `test_indicator_consensus.py` (7 tests) and
  `test_live_technical_summary_api.py` (3 tests). New
  `frontend/tests/live-technical-summary-ui.test.mjs` source-text guard
  (matching the `shadow-runs-ui.test.mjs` convention) asserting the panel
  keeps its research-only banner and never uses buy/sell/order/position-
  size language. Full backend regression: `435 passed`. Frontend lint
  clean, `12/12` tests, production build clean.

### Added — Phase 3 SA-002: window range, absolute return magnitude, robust MAD (volatility)

- Direct continuation of SA-001: three of the contract's four descriptive
  volatility measures. Deliberately deferred: tick-to-tick return standard
  deviation, which needs a raw-tick pass -- every existing
  `backend/app/analysis/*` module (other than `bars.py` itself) operates
  only on already-built `MarketBar` tuples, and this increment preserves
  that boundary rather than special-casing one metric; it's planned as its
  own small follow-up.
- New `backend/app/analysis/volatility.py`: `compute_volatility(bars,
  return_series, ...)` takes the SA-001 return series and the same bars as
  input rather than recomputing anything -- single source of truth. A
  shared `DistributionSummary` (count/mean/median/std-dev/min/max/p05/p95)
  is reused for `window_range_absolute` (`high - low`, all bars --
  including single-tick windows, which are meaningless for *return* but
  perfectly valid for *range*), `window_range_relative` (`range / open`),
  and `window_log_return_abs` (only the return-eligible windows SA-001
  already filtered to tick_count >= 2). `robust_mad` is the median
  absolute deviation of the *signed* window log-returns around their own
  median -- a robust alternative to standard deviation. Each metric
  reports its own `n_total`/`n_valid` and gates independently on the
  minimum sample threshold, matching the contract's "each metric shows
  its own used/excluded observation count separately."
- `statistical_analysis.py`: generalized the orchestration-level
  `minimum_window_returns` parameter to `minimum_sample_size`, now shared
  by both the return series and volatility calls (the pure
  `compute_return_series()` function keeps its own precise parameter name
  unchanged -- only the orchestrator/API layer exposes one combined knob).
  `STATISTICAL_ANALYSIS_API_VERSION` `1.0.0 -> 1.1.0` for the new
  `volatility` field; the `statistical-analysis` endpoint's query param
  renamed accordingly (`?minimum_sample_size=`).
- This layer creates no signal, entry, position size, or order.
- Verification: new `test_volatility.py` (7 tests) covering the minimum-
  sample gate (met and unmet), single-tick windows counting toward range
  but not return, range-equals-high-minus-low, fingerprint determinism,
  mismatched symbol/timeframe rejection, and unsafe `minimum_sample`
  rejection. `test_replay_technical_analysis_api.py` updated for the new
  `volatility` field, `api_version`, and renamed query parameter. Full
  backend regression: `425 passed`. Frontend untouched.

### Added — Phase 3 statistical analysis kickoff: window/resampling foundation + SA-001 return series

- Starts Phase 3 (`PHASE_3_STATISTICAL_ANALYSIS_CONTRACT.md`), the next
  roadmap phase now that Phase 4's pattern-candidate lifecycle is
  substantially complete. The contract spans SA-001 through SA-007
  (returns, volatility, spread, tick rate, tick volume, session
  comparison, regime candidates); this increment deliberately scopes down
  to the foundation everything else depends on: fixed-window resampling
  plus the return series itself.
- `backend/app/analysis/bars.py`: added `S1` (1 second) and `S10` (10
  second) to `TIMEFRAME_SECONDS`, alongside the existing `M1/M5/M15/H1`,
  matching the contract's required window set. `BAR_BUILDER_VERSION`
  `1.0.0 -> 1.1.0`. The existing `build_closed_mid_bars()` (already
  causal, already refuses to forward-fill empty windows) is reused
  unchanged.
- New `backend/app/analysis/return_series.py`: `compute_return_series()`
  computes one log-return per closed window from that window's own first
  (open) and last (close) valid mid-price. A single-tick window has no
  first/last pair and is excluded, not counted as a zero-return
  observation. Returns descriptive statistics (count, mean, median,
  std-dev, min, max, p05/p25/p75/p95 via linear interpolation) once
  `n_valid` reaches a configurable minimum (default `30`); below that,
  `insufficient_data` is returned with all statistics `null` rather than
  a fabricated zero effect. An empty bar set (no ticks in range) is
  treated as a valid degenerate input, not an error, matching the
  existing detector-module convention (e.g. `fair_value_gap.py`).
- New `backend/app/analysis/statistical_analysis.py`:
  `create_replay_statistical_analysis()` orchestrates bar-building plus
  the return series for one completed replay session and timeframe, with
  the same dataset-drift guard used by `technical-analysis`/
  `strategy-analysis`. `MAX_STATISTICAL_ANALYSIS_WINDOWS = 50_000` bounds
  memory for now (the contract's full session range is analyzed, unlike
  `technical-analysis`'s "last N bars" window, since Phase 3 is a
  dataset-level descriptive-statistics concept).
- New protected, read-only `GET
  /api/v2/replay-sessions/{session_id}/statistical-analysis` endpoint
  (`timeframe`, `minimum_window_returns` query params), following the
  exact ownership/completed-state/dataset-drift conventions of the
  existing `technical-analysis` and `strategy-analysis` endpoints.
- Deliberately deferred to later increments: the contract's async
  job/persistence resource (`POST /api/v2/statistical-analyses`, with
  pagination and audit) -- out of scope for a first slice; the current
  endpoint is synchronous and stateless, matching how Phase 4's earliest
  analysis endpoints started. SA-002 through SA-007 (volatility, spread,
  tick rate, tick volume, sessions, regime), which build on this return
  series. A frontend panel, once more of Phase 3 exists to show.
- This layer creates no signal, entry, position size, or order; output
  carries `interpretation: "research_observation_not_trading_signal"`.
- Verification: new `test_return_series.py` (9 tests) covering
  determinism, single-tick exclusion, the insufficient-data threshold,
  empty input, percentile ordering, fingerprint determinism, mismatched
  symbol/timeframe rejection, and unsafe `minimum_window_returns`
  rejection. `test_analysis_bars.py`'s existing parametrized timeframe
  test now also covers `S1`/`S10`. 4 new API tests in
  `test_replay_technical_analysis_api.py` (protected/deterministic/
  research-only, default-insufficient-data below the minimum sample,
  ownership/completed-state/parameter safety, dataset drift). Full
  backend regression: `418 passed`. Frontend untouched.

### Added — Phase 9 SHADOW admin API + frontend (real caller for the persistence skeleton)

- Gives the previously-orphaned Phase 9 skeleton (run manifest, event
  registry, theoretical portfolio ledger) a genuine caller: a manually-
  operated admin surface, since no live decision generator (Phase 5-8)
  exists yet. Still **not** a live trading system -- `execution_allowed`
  stays structurally locked to `0` (DB CHECK constraint), and the panel
  only lets an operator create/observe SHADOW runs and theoretical
  positions by hand.
- 12 new protected endpoints under `/api/v2/shadow-runs...`: create,
  list (per-owner), detail, `start`/`complete`/`halt` transitions, list/
  record events, list/open theoretical positions, close a position, and a
  portfolio summary. Position-open returns HTTP 200 with
  `{"opened": false, "reason": ...}` when a risk limit blocks it (a
  contract-defined outcome, not an error). Closing a position first
  fetches the owning run and verifies the position belongs to it, before
  calling close, to avoid a close-then-check ordering bug.
- New `backend/app/models/shadow.py`: Pydantic request models for all of
  the above (`ShadowRunCreateRequest`, `ShadowRunTransitionRequest`,
  `ShadowEventCreateRequest`, `ShadowPositionOpenRequest`, etc.).
- New `backend/app/database/shadow_run_repository.list_shadow_runs()` and
  `shadow_portfolio_repository.list_theoretical_positions()` to support
  the list views.
- Frontend: new `shadow-runs-panel.tsx` section (wired into
  `dashboard-navigation.tsx` / `page.tsx`), carrying a mandatory
  "NƏZƏRİDİR -- REAL ƏMƏLİYYAT YOXDUR" banner and boundary text
  explaining no order is sent, no MT5 position is opened, and no real
  account balance is touched.
- Verified live in the browser end-to-end (disposable scratch database +
  temporary backend/frontend, real production database and services never
  touched): create run -> start -> open two positions -> third correctly
  blocked by `max_concurrent_positions` -> close a position -> record an
  event -> complete the run. Found and fixed a real bug during
  verification: `openPosition()` set the risk-block warning via
  `setDetailError(...)` *before* `await loadDetail(...)`, but `loadDetail`
  itself resets `detailError` to `null` on entry, silently wiping the
  warning before the user ever saw it -- fixed by reordering the two
  calls.
- Verification: new `test_shadow_runs_api.py` (13 tests) covering create/
  list/detail/lifecycle transitions/events/positions/risk-blocking/wrong-
  run 404. New `frontend/tests/shadow-runs-ui.test.mjs` source-text guard
  (matching the existing `pattern-hypothesis-registry-ui.test.mjs`
  convention) asserting the panel keeps its theoretical-only banner and
  never references order/position-sizing calls. Full backend regression:
  `404 passed`. Frontend lint/build/`11/11` tests clean.
- Migration `0010` (the portfolio ledger table this admin surface reads
  and writes) has only ever been tested against scratch/test databases --
  it has **not** been applied to the real production database
  (`database/ESAS_PLATFORM.sqlite`, currently on `0009`). Applying it
  requires separate explicit user permission, per standing policy.

### Added — Phase 9 SHADOW theoretical portfolio/risk ledger (section 6, skeleton continued)

- Continues the earlier Phase 9 run-manifest + event-registry skeleton
  with contract section 6 ("Nəzəri portfolio və risk"). **Still not a live
  SHADOW system** -- no real decision feed exists (Phase 5-8 remain
  design-only), so nothing writes to this table in production. No API or
  frontend was added, for the same reason as the earlier skeleton
  increment: there is no real caller yet.
- `0010_shadow_theoretical_positions.sql`: `shadow_theoretical_positions`
  has zero relationship to any real account or MT5 position by
  construction (only references `shadow_runs`/`shadow_run_participants`/
  `shadow_events`). A position's identity (run, participant, symbol,
  direction, size, reserved risk, open event) is frozen by trigger once
  opened; only state/close fields may change afterward.
- `backend/app/database/shadow_portfolio_repository.py`:
  `open_theoretical_position()` checks the run's own declared
  `risk_budget` for position-level limits (concurrent position count,
  same symbol+direction concentration, total reserved risk) and records a
  `SHADOW_RISK_BLOCKED` event instead of opening when a limit would be
  violated. `close_theoretical_position()` releases reserved risk.
  `get_theoretical_portfolio_summary()` provides minimal observability
  (open positions, total reserved risk, net realized theoretical PnL).
- Deliberately out of scope: daily-loss and drawdown limits, which are
  time-series concepts over realized PnL and would be meaningless without
  a live decision stream to realize any PnL against.
- Concurrency note: opening a position does an advisory limit check first
  (so a doomed open never gets an OPENED event recorded), then an
  authoritative re-check atomically with the insert itself. A rare race
  between two concurrent opens raises `ShadowPositionConflictError` --
  accepted for this skeleton since no real concurrent caller exists yet.
- Verification: new `test_shadow_portfolio_repository.py` (10 tests)
  covering open/close, each of the three risk limits, an empty risk
  budget never blocking, ownership, optimistic locking, and invalid
  input rejection. `test_migration_runner.py` counters updated for
  `0010`. Full backend regression: `391 passed`. Frontend untouched.
- This layer creates no real risk, position, or order; it is a
  structurally-safe theoretical ledger foundation for a future Phase 9
  implementation.

### Added — `invalid_leakage` lifecycle state via overlap purge/embargo

- A real, previously-unguarded statistical validity gap: backtest v1
  counted every historical trigger event as an independent trade even when
  two triggers' `[entry, entry + horizon_bars)` windows overlapped,
  silently inflating the effective sample size and confidence interval
  with correlated, near-duplicate observations. Genuine causal (future-
  information) leakage is already structurally prevented in every detector
  (the extensive "no lookahead" test suites exist for exactly this), so
  there was nothing meaningful left to add there; overlap was the real gap
  matching the Phase 3 contract's "overlapping horizons require purge/
  embargo" requirement.
- `pattern_candidate_backtest.py` gains `_purge_overlapping_events()`:
  walks chronologically, discarding any event whose entry bar falls inside
  the previously-kept event's `[entry, entry + horizon_bars)` window. Applied
  unconditionally for every candidate (silently improves statistical
  validity), not only when later flagged. `PatternCandidateBacktest` gains
  `raw_event_count` and `discarded_for_overlap`.
- `classify_replay_pattern_candidate` now checks: if the raw trigger count
  was itself ample (>= `MIN_EFFECTIVE_SAMPLE`) but purging collapsed the
  independent sample below the reliability floor, the outcome is
  `invalid_leakage`, not `insufficient_evidence` -- the two mean different
  things (evidence inflated by overlap vs. the pattern genuinely hasn't
  fired enough times yet).
- `invalid_leakage` added to `CLASSIFICATION_OUTCOMES` and
  `ARCHIVABLE_STATES` in `pattern_candidate_repository.py`.
  `BACKTEST_VERSION` bumped `1.4.0 -> 1.5.0`.
- Frontend: `LIFECYCLE_LABELS` gains a label for the new state.
- Verification: 2 new tests in `test_pattern_candidate_backtest.py`
  covering purge behavior with exact expected counts; 2 existing baseline
  tests re-tuned to space their synthetic events `horizon_bars` apart so
  they aren't incidentally affected by the new purge; 1 new test in
  `test_pattern_candidate_repository.py`; 3 new tests in
  `test_replay_pattern_candidates_classification.py` covering the leakage
  transition, the no-purge normal path, and the "raw signal was never
  ample" case staying `insufficient_evidence`. Full backend regression:
  `381 passed`. Frontend lint clean, production build succeeds, `10/10`
  tests pass.
- This layer creates no strategy, entry, risk sizing, or order; it both
  improves statistical validity for every candidate and separately flags
  evidence that was inflated by overlap.

### Added — `blocked_by_data_quality` lifecycle state

- Implements one of the Phase 4 contract's pre-declared (migration `0005`
  CHECK constraint) but previously unimplemented terminal lifecycle
  states. Before a pattern candidate's first backtest attempt, its replay
  session's quality report is now checked; if it has any `critical`
  finding, the candidate moves straight to `blocked_by_data_quality`
  instead of `evaluated`, and no backtest evidence is ever produced from
  data that isn't trustworthy enough to draw a conclusion from.
- `pattern_candidate_repository.py` gains
  `block_pattern_candidate_for_data_quality()` -- reachable only from
  `registered` (raw ticks and quality rules are both immutable, so a
  session that passed once stays passed; there is nothing to re-check for
  a candidate that already reached `evaluated`). `blocked_by_data_quality`
  was added to `ARCHIVABLE_STATES` so a blocked candidate can still be
  archived.
- `evaluate_replay_pattern_candidate_backtest` now calls
  `create_replay_quality_report()` (only when the candidate is still
  `registered`) and raises `PatternCandidateBlockedByDataQualityError` on
  a critical finding; the backtest endpoint maps this to `409`.
- Frontend: `LIFECYCLE_LABELS` gains a label for the new state, and the
  "Backtest et" button is hidden for a blocked candidate (matching the
  existing `archived` treatment) -- this is the first change in several
  increments to actually touch the frontend, since the user is looking
  directly at this table.
- Verification: 5 new tests in `test_pattern_candidate_repository.py`
  (transition, wrong-state rejection, ownership/optimistic-lock,
  archivability) and a new `test_replay_pattern_candidates_data_quality.py`
  (3 tests) proving the gate end-to-end with a real DQ-005 (bid > ask)
  finding: blocks on first attempt, rejects a second attempt, and the API
  returns 409. Full backend regression: `375 passed`. Frontend lint clean,
  production build succeeds, `10/10` tests pass.
- This layer creates no strategy, entry, risk sizing, or order; it only
  prevents drawing a statistical conclusion from data that is not
  trustworthy.

### Added — Single-feature rule and previous-accepted-candidate baselines (Phase 3/4 baseline comparison complete, 4/4)

- Completes the Phase 3/4 contract's four required baseline comparisons
  (no-signal, random-timing, single-feature rule, previously-accepted
  candidate). A candidate must now clear all four to be classified
  `accepted_for_shadow`.
- **Single-feature rule:** `pattern_candidate_backtest.py` gains
  `_single_feature_rsi_reversal_raw_returns()` -- a classic, fixed
  (non-tunable) RSI reversal rule: bullish entries on RSI crossing up
  through 30, bearish on crossing down through 70. The thresholds are
  deliberately fixed (`SINGLE_FEATURE_RSI_LOW/HIGH_THRESHOLD`), not
  configurable -- a tunable baseline would itself become a multiple-testing
  parameter-shopping surface. `run_pattern_candidate_backtest` gains an
  `rsi: IndicatorSeries | None = None` parameter (wired from
  `context.indicators.rsi` in `evaluate_replay_pattern_candidate_backtest`);
  without RSI data the baseline is simply skipped, not blocking.
- **Previously-accepted candidate:** `pattern_candidate_repository.py`
  gains `get_latest_accepted_candidate_for_hypothesis()` -- the most
  recently classified `accepted_for_shadow` candidate for the same
  hypothesis, globally across all replay sessions (unlike the
  multiple-testing family, which is session-scoped). If classification
  would otherwise produce `accepted_for_shadow` and such a candidate
  exists, the new candidate's net return must exceed it or the outcome
  becomes `rejected` instead.
- `BacktestCostScenario` gains three more fields
  (`single_feature_baseline_sample_size/mean_return_percent`,
  `beats_single_feature_baseline`); `bonferroni_corrected_scenario()`
  re-checks this baseline too, so the correction cannot bypass it.
  `PatternCandidateClassificationOutcome` gains
  `previous_accepted_candidate_comparison`, exposed via the classify
  endpoint's `meta.previous_accepted_candidate_comparison`.
  `BACKTEST_VERSION` bumped `1.3.0 -> 1.4.0`.
- No frontend changes.
- Verification: 4 new tests in `test_pattern_candidate_backtest.py`
  (single-feature field presence, skip-without-RSI, a scenario that beats
  random-timing but fails single-feature, and the Bonferroni interaction),
  4 new tests in `test_pattern_candidate_repository.py` for the new query,
  and a new `test_replay_pattern_candidates_classification.py` (4 tests)
  proving the previous-candidate gate end-to-end with synthetic stored
  backtest results. Full backend regression: `368 passed`.
- This layer creates no strategy, entry, risk sizing, or order; the change
  only makes the `accepted_for_shadow` decision statistically stricter.

### Added — Random-timing baseline comparison for pattern candidate backtests

- Implements one of the Phase 3/4 contract's four required baselines
  (no-signal, random-timing, single-feature rule, previously-accepted
  candidate) -- random-timing, scoped down with the user's agreement. The
  no-signal baseline was already implicit (the existing CI test already
  compares against a zero-return baseline); single-feature-rule and
  previous-candidate comparisons remain open follow-up items.
- `pattern_candidate_backtest.py` gains
  `_random_timing_baseline_raw_returns()`: draws a deterministic (seeded),
  hypothesis-blind sample of entry points from the same bar series, using
  the same direction convention, horizon, and cost model as the real
  backtest. The seed is derived only from already-fixed inputs (candidate
  id, hypothesis id, horizon, bar count, first/last bar timestamps), so the
  same inputs always draw the same "random" sample (reproducibility). This
  guards against an apparent edge that is actually indistinguishable from
  generic market drift or volatility over the period.
- `BacktestCostScenario` gains three fields:
  `random_timing_baseline_sample_size`,
  `random_timing_baseline_mean_return_percent`,
  `beats_random_timing_baseline`. The acceptance rule now requires clearing
  *both* the zero baseline *and* the random-timing baseline to be
  `supportive_evidence`; clearing zero but not the baseline produces a new
  `ci_does_not_exceed_random_timing_baseline` reason, which
  `classify_backtest_verdict` already routes to `rejected` (no signature
  change needed there).
- `bonferroni_corrected_scenario()` updated to also re-check the
  random-timing baseline against the corrected confidence interval -- the
  multiple-testing correction can no longer accidentally bypass the
  baseline check.
- `BACKTEST_VERSION` bumped `1.2.0 -> 1.3.0` (result schema changed, so
  fingerprints naturally differ from prior runs).
- No frontend changes; the new fields are present in the API response but
  not yet rendered (TypeScript's structural typing simply ignores the
  extra fields, no breakage).
- Verification: 4 new tests in `test_pattern_candidate_backtest.py`
  (baseline field presence, determinism, a scenario that clears zero but
  fails the baseline, and the Bonferroni/baseline interaction). Full
  backend regression: `356 passed` -- no existing test needed updating,
  since every other fixture either stays below the n=30 sample floor or
  happened to already clear the new bar.
- This layer creates no strategy, entry, risk sizing, or order; the change
  only makes the `accepted_for_shadow` decision statistically stricter.

### Added — Phase 9 SHADOW run manifest + append-only event registry (persistence skeleton only)

- **This is not a live SHADOW system.** `PHASE_9_SHADOW_VALIDATION_CONTRACT.md`
  remains "DESIGN READY — NOT IMPLEMENTED" and depends on Phase 1-8
  acceptance; Phase 5-8 (Visual AI, news/fundamental analysis, Knowledge
  Base, Decision/Risk) are still design-only, so there is no real decision
  feed. This change implements only the contract's section 3 (run manifest
  pre-registration) and section 9 (append-only event families) persistence
  layer -- nothing in production writes to these tables yet.
- `0009_shadow_runs.sql`: `shadow_runs` (immutable manifest -- planned end
  time, code commit, config hash, feature/claim versions, symbol/timeframe/
  session/regime scope, minimum observation duration/sample size, primary/
  secondary metrics, failure rules, theoretical fill model, risk budget,
  data-quality policy, approver, rollback plan), `shadow_run_participants`
  (champion/challenger roles, append-only), `shadow_events` (the 9 event
  families from the contract, append-only).
- Two structural invariants enforced at the database level, not just in
  application code:
  - `execution_allowed` has `CHECK (execution_allowed = 0)` -- no future
    code change can ever flip it to true.
  - `shadow_events.event_type`'s CHECK constraint is the entire allow-list
    of the 9 `SHADOW_*` types; no `ORDER_*` event type can exist. A
    `prevent_shadow_run_manifest_mutation` trigger freezes every
    substantive manifest field after insert (only `state`/`state_version`/
    `halt_reason`/`updated_at` may change afterward), matching "Run
    başladıqdan sonra hədəf, metrik və hədlər dəyişdirilmir."
- `backend/app/database/shadow_run_repository.py`: `register_shadow_run`
  (requires exactly one champion participant plus any number of
  challengers), `get_shadow_run`, `start_shadow_run`, `complete_shadow_run`,
  `halt_shadow_run` (reachable from any non-terminal state, for the
  contract's "any order-adapter call halts the run immediately" rule).
- `backend/app/database/shadow_event_repository.py`: `record_shadow_event`
  (also rejects payloads containing reserved broker/order key names as a
  second guard beyond the event-type allow-list), `list_shadow_run_events`.
- No API endpoints were added -- there is no real caller yet (Phase 5-8
  don't exist), so exposing an unused API surface was deliberately skipped.
- Verification: new `test_shadow_run_repository.py` (13 tests) and
  `test_shadow_event_repository.py` (6 tests) cover manifest immutability,
  the `execution_allowed` DB-level lock, append-only triggers, lifecycle
  transitions, ownership/optimistic-locking, and forbidden payload keys.
  `test_migration_runner.py` counters updated for `0009`. Full backend
  regression: `352 passed`.
- This layer creates no market observation, decision, theoretical position,
  or order; it is purely a structurally-safe storage foundation for a
  future Phase 9 implementation.

### Added — Multiple-testing registry with Bonferroni correction for classification

- Implements the Phase 3/4 contract requirement "multiple-testing
  qeydiyyatı olmadan namizəd qəbul edilmir" (a candidate cannot be
  accepted without multiple-testing registration). Previously,
  `evaluated -> accepted_for_shadow` was decided from a single backtest's
  own uncorrected 95% confidence interval, regardless of how many other
  hypothesis/parameter variants had been tried against the same replay
  session -- a real family-wise error problem (running many backtests and
  only classifying the best-looking one inflates the false-positive rate).
- `0008_multiple_testing_trials.sql`: append-only `multiple_testing_trials`
  registry, keyed by `family_key` (the replay session, i.e. "same data")
  with a `UNIQUE(backtest_id)` idempotency guard.
- `backend/app/database/multiple_testing_repository.py`: `register_trial`,
  `count_family_trials`, `list_family_trials`.
- Registration happens unconditionally on every backtest run
  (`evaluate_replay_pattern_candidate_backtest`), whether or not the
  candidate is ever classified -- otherwise the correction could be
  dodged by simply not classifying unfavorable runs.
- `pattern_candidate_backtest.py` gains `bonferroni_corrected_scenario()`:
  recomputes a scenario's confidence interval at classification time using
  `alpha = 0.05 / family_trial_count` (`statistics.NormalDist().inv_cdf`
  for the exact critical value), without mutating the stored backtest
  artifact. Only a `supportive_evidence` scenario is recomputed -- the
  correction can only narrow the interval, never rescue an already
  insufficient one.
- `classify_replay_pattern_candidate` now decides from the corrected
  status/reason; its result is exposed via the classify endpoint's
  `meta.multiple_testing.{family_trial_count, corrected_scenario}` (the
  `data` field is unchanged, fully backward compatible).
- No frontend changes; the existing "Nəticələndir" button keeps working,
  only the server-side decision logic changed.
- Verification: new `test_multiple_testing_repository.py` (6 tests), 5 new
  Bonferroni tests in `test_pattern_candidate_backtest.py`, 2 new
  integration tests in `test_pattern_candidates_backtest_api.py`
  (multi-candidate/multi-run family counting). `test_migration_runner.py`
  counters updated for `0008`. Full backend regression: `333 passed`.
- This layer creates no strategy, entry, risk sizing, or order; the
  correction only makes the `accepted_for_shadow` decision statistically
  stricter.

### Added — Phase 2 worker/scheduler contract, applied literally to `pattern_candidate_backtest`

- Implements the full `PHASE_2_WORKER_SCHEDULER_CONTRACT.md` job-queue
  model — claim/lease/fencing-token single-executor guarantee, heartbeat
  lease renewal, exponential-backoff-with-jitter retry (capped, up to
  `max_attempts`), cooperative pause/cancel honored at the single batch
  boundary, expired-lease reclaim for crash/restart recovery, per-user
  active-job cap, and append-only audit trail — scoped to the
  `pattern_candidate_backtest` job type (added as a 6th type; the contract
  names 5 others that do not exist yet).
- `0007_analysis_jobs.sql`: `analysis_jobs` (full state machine) +
  append-only `analysis_job_audit`.
- `backend/app/database/analysis_job_repository.py`: `enqueue_job`,
  `claim_next_job`, `send_heartbeat`, `complete_job`, `fail_job`,
  `request_cancel`, `queue_metrics`.
- `backend/app/workers/analysis_job_worker.py`: `run_worker_once`,
  `drain_queue`. The execution driver is FastAPI `BackgroundTasks`, not a
  standalone worker process — the claim/lease/fencing DB logic is correct
  and reusable by a real future worker regardless.
- New endpoints: `POST /api/v2/pattern-candidates/{id}/backtest-jobs`
  (202), `GET .../backtest-jobs/{job_id}`, `POST
  .../backtest-jobs/{job_id}/cancel`, `GET /api/v2/analysis-jobs/metrics`.
  The existing synchronous `POST .../backtest` endpoint is unchanged.
- **Bug found and fixed:** `enqueue_job`'s idempotency key hash included
  `created_by`, so two different users could never collide on the same key
  in the first place — the `AnalysisJobOwnershipError` cross-user
  protection was dead code. Fixed by hashing only `job_type:key`, with
  ownership checked against the row actually found. Regression test:
  `test_enqueue_rejects_key_reused_by_another_user`.
- No standalone frontend surface was added for the new async endpoints in
  this change; the existing pattern-candidates panel keeps using the
  synchronous backtest endpoint.
- Verification: new `test_analysis_job_repository.py` (17 tests),
  `test_analysis_job_worker.py` (4 tests), `test_analysis_jobs_api.py` (7
  tests); `test_migration_runner.py` counters updated for `0007`. Full
  backend regression: `321 passed`. Frontend untouched, so no frontend
  suite was re-run this increment.
- This layer creates no strategy, entry, risk sizing, or order; the job
  queue only runs the existing synchronous backtest computation
  asynchronously.

### Added — Automatic backtest-driven classification (evaluated -> outcome)

- New `evaluated -> accepted_for_shadow | rejected | insufficient_evidence`
  transition (`classify_backtest_verdict`,
  `POST /api/v2/pattern-candidates/{id}/classify`). The verdict is derived
  solely from the candidate's latest backtest "normal" cost scenario, with
  no new computation: `supportive_evidence` -> `accepted_for_shadow`
  (Phase 9 SHADOW does not exist yet, so this records only that the
  historical evidence met the predeclared statistical bar, not a trading
  authorization); `insufficient_evidence` with reason
  `effective_sample_below_30` stays `insufficient_evidence` (may just need
  a longer replay interval); any other `insufficient_evidence` reason
  (large-enough sample whose confidence interval does not clear the zero
  baseline) becomes `rejected`, since that is refuting evidence rather than
  missing data.
- `archive_pattern_candidate` now accepts any archivable state
  (`registered`, `evaluated`, `accepted_for_shadow`, `rejected`,
  `insufficient_evidence`), not only `registered`.
- Frontend adds a "Nəticələndir" action once a candidate is `evaluated`,
  with clear lifecycle labels and an explicit "not a trading authorization"
  disclaimer.
- Verification: backend `293 passed`, frontend production build and
  `10/10` tests passed, lint clean.
- This layer creates no strategy, entry, risk sizing, or order.
  `accepted_for_shadow` is a classification, not a live-trading decision.

### Added — Market structure historical events complete backtest v1 coverage

- `market_structure.py` gains an `observations` field recording every
  transition into a confirmed HH/HL (bullish) or LH/LL (bearish) regime.
  Only the transition is recorded, not every later pivot that keeps an
  already-confirmed regime going -- otherwise a single long-lived trend
  would produce many overlapping, highly correlated "events" and inflate
  an effective sample size dishonestly, violating the purged-validation
  principle already used elsewhere in this codebase.
- Backtest v1 now covers `market_structure_long/short`, completing
  coverage of all 6 pattern hypotheses.
- Verification: backend `286 passed` (new market_structure historical
  event tests, backtest integration tests), frontend production build and
  `10/10` tests passed, lint clean.

### Fixed — Pattern candidate backtest direction bug, and liquidity sweep backtest coverage

- **Bug fix:** `run_pattern_candidate_backtest` incorrectly accepted a
  `direction` parameter expected to be `"bullish"/"bearish"`, but a
  registered candidate's stored `direction` field actually comes from the
  hypothesis registry's `"long"/"short"` vocabulary. This would have made
  every real backtest run fail with a `ValueError` in production; it went
  unnoticed in v1's own tests because those fixtures hand-wrote `"bullish"`
  directly. The function no longer accepts a `direction` parameter at all
  -- it derives the causal direction solely from `hypothesis_id`.
- `liquidity_sweep.py` gains an `observations` field recording every
  historical pool-sweep-and-reclaim event (previously only the latest
  confirmed sweep per direction was kept). Additive, backward compatible.
- Backtest v1 now also supports `liquidity_sweep_reclaim_long/short`, in
  addition to `structure_break_long/short`. `market_structure` remains out
  of scope -- it is a continuous regime concept, not a discrete event, and
  needs its own historical-event design before it can be backtested
  honestly.
- Verification: backend `281 passed`, frontend production build and
  `10/10` tests passed, lint clean.

### Added — Pattern candidate backtest v1 (Phase 4, partial)

- `run_pattern_candidate_backtest` scans every historical `confirmed_retest`
  event for a candidate's hypothesis and simulates a theoretical trade per
  event: entry at the confirming bar's own close (matching the existing
  `forward_closed_bar_outcome` convention), exit at the close `horizon_bars`
  later. Produces normal/adverse/stress cost scenarios, hit rate, effective
  sample size, and a 95% confidence interval using the same threshold
  (n >= 30) and formula already used by `statistical_reliability.py`.
- v1 intentionally only supports `structure_break_long`/`structure_break_short`
  -- these are the only hypotheses whose upstream detectors
  (`bos_choch.observations`, `retest.observations`) already expose every
  historical confirmation rather than just the latest one. Backtesting
  `market_structure`/`liquidity_sweep` today would only ever have one
  sample, which would be statistically dishonest.
- New `pattern_candidate_backtests` append-only table (migration `0006`).
  Migration `0005` (added earlier this session, never applied to any real
  database) was amended in place to pre-declare the full contract-defined
  `lifecycle_state` vocabulary (including `evaluated`), since SQLite cannot
  widen a CHECK constraint without a table rebuild and this migration
  runner refuses DROP statements by design.
- New endpoints: `POST/GET /api/v2/pattern-candidates/{id}/backtest`. A
  candidate's first successful backtest moves it `registered -> evaluated`;
  re-runs stay `evaluated` but append a new immutable backtest row and
  audit entry rather than overwriting the previous result.
- Frontend adds a "Backtest et" action per supported registered candidate
  with an inline per-scenario result summary.
- Verification: backend `277 passed` (7 new pure-function tests, 5 new
  repository tests, 3 new API tests), frontend production build and `10/10`
  tests passed, lint clean.
- This layer creates no strategy, entry, risk sizing, or order. "Evaluated"
  is a historical simulation status, not a trading or execution decision.

### Added — Pattern candidate persistence and `registered` lifecycle (Phase 4, partial)

- New `pattern_candidates` and append-only `pattern_candidate_audit` tables
  (migration `0005`). A candidate can only be persisted from an already
  `candidate_confirmed` draft slot; registration is idempotent by
  `candidate_id` and archiving uses an optimistic `state_version` lock.
- `register_replay_pattern_candidate` always recomputes the candidate
  server-side from the completed replay session before persisting -- the
  client never supplies evidence or condition state directly.
- New protected endpoints: `POST /api/v2/pattern-candidates`,
  `GET /api/v2/pattern-candidates`, `GET /api/v2/pattern-candidates/{id}`,
  `POST /api/v2/pattern-candidates/{id}/archive`.
- Frontend adds a "Draft kimi qeydə al" action on confirmed slots and a
  registered-candidates table with archive support.
- Intentionally out of scope: `running`, `evaluated`, `accepted_for_shadow`,
  `rejected`, and other backtest-dependent lifecycle states -- there is no
  backtest engine yet, so those transitions would be unearned.
- Verification: backend `262 passed` (7 new repository tests, 4 new API
  tests; existing migration-count assertions updated for migration `0005`),
  frontend production build and `10/10` tests passed, lint clean.
- This layer creates no strategy, signal, entry, risk sizing, or order.

### Added — Phase 2 Stable release decision

- Phase 2 (replay and data quality) formally declared `STABLE`
  (`docs/releases/PHASE_2_STABLE.md`), based on the 2026-08-04 real-data
  acceptance run (`PASSED`, 0 critical findings, raw tick count unchanged).
  `PROJECT_ROADMAP.md` status updated accordingly. Documentation only, no
  code or test changes.

### Added — Draft pattern candidate generator (Phase 4, partial)

- `pattern_candidate 1.0.0` combines the existing causal detectors (market
  structure, liquidity sweep, BOS/CHoCH + retest) into draft, versioned
  pattern candidate slots for the 6 hypotheses already defined in the pattern
  hypothesis registry (`market_structure_long/short`,
  `liquidity_sweep_reclaim_long/short`, `structure_break_long/short`).
- Every slot carries a fixed `draft` lifecycle state plus an explicit
  `candidate_confirmed`, `no_candidate`, or `insufficient_data` condition
  state and cites the evidence from its source detector.
- New protected, read-only `GET /api/v2/replay-sessions/{session_id}/pattern-candidates`
  endpoint and a "Pattern namizədləri" frontend section.
- This increment intentionally excludes backtesting, label/horizon
  measurement, persistence/state machine transitions beyond `draft`, and any
  accept/reject decision — those remain separate future steps per
  `PHASE_4_PATTERN_TECHNICAL_ANALYSIS_CONTRACT.md`.
- Verification: backend `251 passed`, frontend production build and `10/10`
  tests passed, lint clean.
- This layer creates no strategy, signal, entry, risk sizing, or order.

### Fixed — Sidebar render-time mutation (lint)

- `dashboard-navigation.tsx`-də menyu qrup başlığını göstərmək üçün render
  zamanı dəyişən mutasiya edilirdi; bu `eslint-plugin-react-hooks 7.x`-in
  `react-hooks/immutability` qaydasını pozurdu və CI-ni bloklayırdı. Qrup
  bayrağı indi render-dən əvvəl sabit massivdə hesablanır.

### Added — Causal Fair Value Gap detector

- `fair_value_gap 1.0.0` üç ardıcıl bağlanmış bar arasında yaranan bullish/bearish
  qiymət boşluğunu izləyir; boşluq yalnız yaranandan sonrakı bağlanmış barlarla
  `open`, `partially_filled`, `filled` və ya `invalidated` vəziyyətinə keçir.
- `no_gap` və `insufficient_data` halları açıq göstərilir; minimum boşluq (bps)
  konfiqurasiya olunur, nəticə deterministik SHA-256 izi daşıyır.
- Frontend "Fair Value Gap" menyusunda bullish/bearish kartları, doldurulma
  faizini və köhnə backend cavabı üçün uyğunluq xəbərdarlığını göstərir.
- Yoxlama: backend `243 passed`, frontend production build və `9/9` test keçdi.
- Bu qat strategiya, siqnal, giriş, risk ölçüsü və order yaratmır.

### Added — Causal retest detector

- `retest 1.0.0` BOS/CHoCH qırılmasından sonra səviyyəyə geri dönüşü yalnız sonrakı bağlanmış barlarla müşahidə edir.
- Bullish və bearish nəticələr ayrıdır; statuslar açıq, parametrlər versiyalanmış və nəticə deterministikdir.
- Frontend iki istiqaməti sadə Azərbaycan dilində ayrıca göstərir.
- Yoxlama: retest/API `13 passed`, tam backend `239 passed`, frontend hədəf testi və lint keçdi.
- Bu qat strategiya, siqnal, giriş, risk ölçüsü və order yaratmır.

### Added — Causal BOS/CHoCH detector

- `bos_choch 1.0.0` əlavə edildi. Detektor yalnız əvvəlcədən təsdiqlənmiş causal pivotları
  sonrakı bağlanmış barların close qiyməti ilə yoxlayır; pivot təsdiqindən əvvəlki qırılmalar nəzərə alınmır.
- Bullish və bearish BOS/CHoCH müşahidələri ayrıdır; `insufficient_data`, `no_break`,
  `unclassified_break` və `conflicting` halları açıq göstərilir.
- Minimum close məsafəsi, pivotun köhnəlmə limiti, upstream konfiqurasiyası və deterministik
  SHA-256 izi nəticəyə daxil edilir.
- Frontend-də iki istiqamət ayrı Azərbaycan dilli tədqiqat kartlarında göstərilir.
- Tam yoxlama: backend `236 passed`; frontend `4` test, lint və production build keçdi.
- Bu qat siqnal, giriş, risk ölçüsü və order yaratmır; retest, FVG və order-block daxil deyil.

### Added — Causal liquidity sweep detector

- `liquidity_sweep 1.0.0` əlavə edildi. Detektor yalnız əvvəlcədən təsdiqlənmiş causal
  pivotlardan equal-high/equal-low hovuzları yaradır və sonrakı bağlanmış barda wick sweep
  ilə səviyyəyə geri bağlanmanı müşahidə edir.
- Bullish və bearish müşahidələr ayrıdır; `insufficient_data`, `no_sweep` və `conflicting`
  halları açıq göstərilir.
- Hovuz toleransı, minimum toxunuş, minimum sweep məsafəsi və köhnəlmə limiti
  versiyalanır; nəticə deterministik SHA-256 izi daşıyır.
- Frontend-də likvidlik hovuzları və iki istiqamət ayrıca, yalnız tədqiqat görünüşündə verilir.
- Tam yoxlama: backend `232 passed`; frontend `4` test, lint və production build keçdi.
- Bu qat siqnal, giriş, risk ölçüsü və order yaratmır.

### Added — Causal market structure detector

- `market_structure 1.0.0` əlavə edildi. Detektor yalnız bağlanmış barlardan və sağ
  tərəfdə təsdiqlənmiş pivotlardan istifadə edərək HH/HL və LH/LL müşahidələrini hesablayır.
- LONG və SHORT müşahidələri, yetərsiz və ziddiyyətli hallar frontend-də ayrı göstərilir.
- Bərabərlik toleransı, pivot qaydası, təsdiq vaxtı və deterministik SHA-256 izi saxlanılır;
  gələcək bar əvvəlki nəticəyə daxil edilmir.
- Tam yoxlama: backend `227 passed`; frontend `4` test, lint və production build keçdi.
- Bu qat yalnız tədqiqat üçündür; siqnal, giriş, risk ölçüsü və order yaratmır.

### Added — Pattern hypothesis registry

- `pattern_hypothesis_registry 1.0.0` əlavə edildi. Bazar strukturu, likvidlik süpürməsi,
  BOS/CHoCH/retest və gələcək zona modelləri ayrıca versiyalanmış hipotezlərdir.
- LONG və SHORT qaydaları qarışdırılmır; tələblər, invalidasiya halları, timeframe-lər,
  readiness və deterministik fingerprint saxlanır.
- Qorunan read-only API və Azərbaycan dilində frontend reyestri əlavə edildi.
- Tam yoxlama: backend `224 passed`; frontend `4` test, lint və production build keçdi.
- Bu qat siqnal, risk ölçüsü və order yaratmır.

### Added

- Versiyalanmış `purged_validation_mean_vs_zero_baseline 1.0.0` statistik etibarlılıq
  qiymətləndiricisi əlavə edildi. EMA və RSI üçün normal, pis və stress xərcli validation
  nəticələri sıfır faiz dəyişiklik bazası ilə ayrıca müqayisə olunur; effektiv nümunə sayı,
  95% etibar intervalı, effekt ölçüsü, açıq yetərsizlik səbəbi və SHA-256 lineage saxlanılır.
  Frontend nəticəni “Sübut yetərlidir / Sübut yetərli deyil” kimi izah edir və bunun siqnal
  və ya mənfəət zəmanəti olmadığını göstərir. Tam backend `222 passed`, frontend test/lint/build
  yoxlamaları uğurla keçdi.

- Versiyalanmış `historical_cost_stress_adjustment 1.0.0` xərc və stress qatı əlavə
  edildi. EMA və RSI-nin dəyişməz xam walk-forward nəticələri yanında spread,
  komissiya, slippage və gecikmənin normal, pis və stress fərziyyələri eyni
  deterministik qayda ilə göstərilir. Hər ssenari ümumi xərc, xərcdən sonrakı tarixi
  dəyişiklik, əhatə, bütün pəncərələrin nəticəsi və SHA-256 fingerprint saxlayır.
  Frontend fərziyyələri `bps` vahidi ilə, broker faktı olmadığını və nəticənin siqnal,
  risk icazəsi və order yaratmadığını Azərbaycan dilində göstərir. Hədəf backend
  yoxlamaları `27 passed`, tam backend regressiyası `216 passed`, frontend lint/build
  və `3` test uğurla keçdi.

- Versiyalanmış `expanding_chronological_validation_windows 1.0.0` sabitlik ölçümü
  əlavə edildi. EMA və RSI nəticələri yalnız keçmişi genişlənən inkişaf məlumatı və
  üst-üstə düşməyən ardıcıl yoxlama pəncərələri ilə ölçülür. Hər pəncərə ayrıca manifest,
  bar fingerprint-i və upstream strategiya/nəticə izini saxlayır; əhatə, yetişməmiş
  müşahidələr və xərcsiz tarixi dəyişiklik qarışdırılmır. Frontend pəncərə sayı seçimini,
  müsbət/mənfi/düz pəncərələri, çəkili ortanı və pəncərələrarası aralığı Azərbaycan
  dilində ayrıca göstərir. Tam backend `198 passed`, frontend lint/build və `3` test
  uğurla keçdi; qat canlı siqnal, mövqe ölçüsü və order yaratmır.

- Versiyalanmış `chronological_holdout_comparison 1.0.0` walk-forward təməli əlavə
  edildi. EMA və RSI nəticələri xronoloji inkişaf və toxunulmamış yoxlama intervallarına
  ayrılır; gələcək yoxlama qiymətinə keçən nəticə inkişaf hesabından çıxarılır. Manifest
  parametrləri, bölgünü, üfüqü və upstream fingerprint-ləri saxlayır. Frontend 60/40,
  70/30 və 80/20 bölgüsünü və hər hissənin nəticəsini ayrı göstərir. Tam backend
  `189 passed`, frontend lint/build və `3` test keçdi; qat siqnal və order yaratmır.

- Versiyalanmış `forward_closed_bar_outcome 1.0.0` tədqiqat qiymətləndiricisi əlavə edildi.
  EMA və RSI müşahidələrinin yalnız sonrakı qapalı bar nəticələri seçilən üfüqdə ölçülür;
  yetkin, yetkinləşməmiş və warm-up nəticələri, istiqamət və rejim üzrə orta dəyişiklik
  ayrıca saxlanır. Gələcək məlumat ilkin müşahidəyə daxil olmur. Frontend hər modulda
  ayrıca tarixi nəticə bölməsi və üfüq seçimi göstərir. Tam backend `181 passed`, frontend
  lint/build və `3` test keçdi; qat siqnal və order yaratmır.

- `rsi_regime_observation` `1.0.0` müstəqil tədqiqat modulu əlavə edildi. Modul causal
  RSI-ni konfiqurasiya olunan aşağı/neytral/yüksək rejimlərə ayırır, inclusive sərhədləri,
  warm-up, determinizm və no-lookahead davranışını test edir. EMA və RSI frontend-də ayrıca
  kartlarda müqayisə olunur. Tam backend `173 passed`, frontend lint/build və `3` test keçdi.

- Tamamlanmış replay sessiyalarında versiyalanmış strategiyaları işlədən qorunan
  `strategy-analysis` API-si və müasir müqayisə laboratoriyası əlavə edildi. İlk
  `ema_close_relation` kartı EMA-dan yuxarı/aşağı/bərabər müşahidələri, warm-up,
  versiya, lifecycle və fingerprint izini göstərir. Qat yalnız araşdırma üçündür;
  al/sat qərarı, mövqe ölçüsü və order yaratmır. Tam backend `164 passed`, frontend
  lint/build və `3` test nəticəsi uğurludur.

- Versiyalanmış, müstəqil və yalnız tədqiqat məqsədli strategiya modul müqaviləsi əlavə
  edildi. `ema_close_relation` `1.0.0` istinad modulu bağlanmış barları causal EMA ilə
  müqayisə edir, warm-up vəziyyətini saxlayır və nəticəni dataset/bar/indicator
  fingerprint-lərinə bağlayır. Modul EXPERIMENTAL-dır, ticarət siqnalı və order yaratmır.

- Tamamlanmış replay sessiyasının EMA, RSI və ATR nəticələrini göstərən qorunan texniki
  analiz frontend paneli əlavə edildi. İstifadəçi timeframe, indikator periodları və
  görünən bar sayını seçə bilir; EMA qiymətlə birlikdə, RSI və ATR ayrıca kartlarda
  göstərilir. Warm-up, boş/yüklənmə/xəta vəziyyətləri, mobil görünüş və fingerprint
  lineage bölməsi əlavə edildi. Panel araşdırma məqsədlidir, siqnal və order yaratmır;
  frontend lint/build və `2` frontend testi, tam backend `156 passed` nəticəsi verdi.

- Tamamlanmış replay sessiyası üçün qorunan, yalnız-oxuma texniki analiz API-si əlavə
  edildi. Endpoint `M1`, `M5`, `M15`, `H1`, EMA/RSI/ATR periodları və təhlükəsiz şam
  limitini qəbul edir; yalnız sessiya sahibinə xidmət göstərir, açıq sessiyanı və dataset
  driftini rədd edir, warm-up statusunu və dataset/bar/indicator lineage fingerprint-lərini
  cavabda saxlayır. Nəticə ticarət siqnalı və order yaratmır.

- Bağlanmış replay şamları üçün deterministik, yalnız-oxuma `EMA`, `RSI` və `ATR`
  indikator paketi əlavə edildi. Hər indikator ayrıca versiyalanmış series yaradır,
  warm-up nöqtələrini `insufficient_data` kimi saxlayır, gələcək şamın keçmiş nəticəyə
  sızmasını qadağan edir və nəticəni bar fingerprint-inə bağlayır. Yeni 11 indikator
  testi və tam `153 passed` backend regressiyası keçdi.

- Replay tick-lərindən yalnız tam bağlanmış `M1`, `M5`, `M15` və `H1` mid-price
  şamları yaradan deterministik, yalnız-oxuma bar generatoru əlavə edildi. Generator
  UTC epoch sərhədlərindən, sabit `event_timestamp + event_id` sırasından, mənbə
  fingerprint-indən və versiyalanmış nəticə fingerprint-indən istifadə edir; boş və
  açıq şamları süni doldurmur. Yeni 9 modul testi və tam `142 passed` backend
  regressiyası keçdi.

### Fixed

- MT5 broker server vaxtının səhvən UTC kimi işarələnməsi düzəldildi. Bridge `1.6.1`
  yeni tick-lərdə server/UTC fərqini 15 dəqiqəlik təhlükəsiz addımla normallaşdırır,
  `event_timestamp` və `source_time_msc` eyni kanonik UTC vaxtını daşıyır. Mövcud xam
  tick-lər dəyişdirilmədi; canlı qəbulda əvvəlki təxminən `-10799 saniyə` əvəzinə
  müsbət təxminən `0.74 saniyə` qəbul gecikməsi və `0 ms` event/source fərqi ölçüldü.

### Added

- Production bazası yoxlanmış SQLite backup-dan sonra Phase 2 sxeminə keçirildi;
  real `GOLD` intervalında iki `step` və iki `max_speed` replay ilə deterministik
  qəbul sınağı `PASSED` oldu. `542` tick üzrə dataset/nəticə fingerprint-ləri eyni,
  cross-mode nəticəsi bərabər və xam tick sayı dəyişməz qaldı. Təhlükəsiz migration
  və qəbul sübutu üçün açıq production icazəsi tələb edən iki operator aləti əlavə
  edildi; `DQ-009` saat normallaşdırma xəbərdarlığı növbəti prioritet kimi qeydə alındı.

- Qorunan dashboard-a Phase 2 replay idarəetməsi əlavə edildi: sessiya yaratma,
  siyahı/detal, qanuni lifecycle əmrləri, cursor-lu event baxışı və tamamlanmış
  sessiyanın keyfiyyət hesabatı; API list/detail ownership sərtləşdirildi,
  frontend lint/build/render və tam backend `133 passed`.

- Replay keyfiyyət hesabatı qorunan public v2 API-yə çıxarıldı: ownership,
  completed-state qapısı, stabil `data/meta` contract-ı, deterministik report
  reproduksiyası və daxili endpoint geriyə uyğunluğu; tam backend `132 passed`.
- Replay event-ləri üçün qorunan, yalnız-oxuma v2 API əlavə edildi: sessiya sahibinin
  girişi, deterministik `(event_timestamp, event_id)` səhifələməsi, sessiya və
  istifadəçiyə bağlı imzalanmış cursor, sabit snapshot son sərhədi və xam tick
  toxunulmazlığı; tam backend `129 passed`.
- Qorunan replay lifecycle command API-si əlavə edildi: `start`, `step`, `pause`,
  `resume` və `cancel` əmrləri üçün ownership, hash-lənmiş idempotency açarı,
  `state_version` optimistic lock, atomik session/audit/command yazısı və xam tick
  toxunulmazlığı; tam backend `125 passed`, frontend lint/build keçdi.
- Qorunan `POST /api/v2/replay-sessions` endpoint-i əlavə edildi: ciddi giriş
  validation-u, autentifikasiyalı yaradıcı audit izi, atomik snapshot/session/audit
  yazısı, boş dataset üçün təhlükəsiz `completed` davranışı və xam tick
  dəyişməzliyi; replay API testləri `11 passed`, tam backend `121 passed`.
- Phase 2 replay sessiyalarının autentifikasiyalı siyahı və detal API-si əlavə
  edildi: `created_at + session_id` deterministik keyset səhifələmə, istifadəçiyə
  bağlı imzalanmış və vaxtı məhdud cursor, təhlükəsiz 400/404 cavabları; tam backend
  `116 passed`, frontend lint/build/render yoxlamaları keçdi.
- Tamamlanmış replay keyfiyyət hesabatı autentifikasiyalı, yalnız oxuma üçün daxili
  endpoint-dən təqdim edilir; təhlükəsiz 404/409 cavabları ilə tam backend `110 passed`.
- `DQ-010` üçün sabit yaddaşlı, deterministik tick intervalı və spread statistikaları
  əlavə edildi və replay keyfiyyət hesabatının fingerprint-inə bağlandı; tam backend
  `108 passed`.
- `DQ-003`, `DQ-006`, `DQ-007`, `DQ-008` və `DQ-009` keyfiyyət qaydaları əlavə
  edildi: source/event vaxt fərqi, qiymət cütü, ədədi etibarlılıq, event müqaviləsi
  və qəbul gecikməsi dəqiq sərhədlərlə yekun hesabat statusuna bağlandı; tam backend
  `105 passed`.
- Replay manifesti ilə bağlı deterministik məlumat keyfiyyəti hesabatı əlavə edildi:
  `pass/review/fail` status qapısı, səviyyə sayları, stabil report ID və məzmun
  fingerprint-i; `DQ-005` mənfi spread critical qaydası və tam backend `102 passed`.
- Phase 2 streaming tick keyfiyyəti analizatorunun ilk qaydaları əlavə edildi:
  geriyə gedən source timestamp, parametrli ardıcıl zaman boşluğu və `event_id`
  dublikatından ayrılmış ardıcıl payload namizədi; stabil finding ID, limitli nümunə,
  batch-dən asılı olmayan nəticə və xam məlumat dəyişməzliyi, tam backend `97 passed`.
- Phase 2 deterministik replay nəticə manifesti əlavə edildi: tamamlanmış `step` və
  `max_speed` sessiyaları üçün immutable giriş, dataset və müqavilə metadatası,
  streaming kanonik nəticə fingerprint-i və iki müstəqil icra üçün fail-closed
  reproduksiya sübutu; `8` yeni test, tam backend `92 passed`.
- Phase 2 `max_speed` replay orchestrator-u əlavə edildi: maksimum `1000` tick-lik
  transaction batch-ləri, checkpoint əsaslı restart, pause sərhədi, terminal no-op,
  dataset fingerprint təsdiqi və audit rollback; `9` yeni test, tam backend
  `84 passed`.
- Phase 2 replay `step` rejimi əlavə edildi: hər əmrdə `1..1000` deterministik tick,
  boşluqsuz checkpoint irəliləməsi, son batch-də atomik tamamlanma və persistent
  idempotency; addım qeydləri append-only qorunur, `8` yeni test və tam backend
  `75 passed`.
- Replay sessiyası üçün qanuni vəziyyət keçidləri, terminal vəziyyət qoruması,
  optimistic conflict, monoton progress və datasetə bağlı checkpoint əlavə edildi;
  sessiya yenilənməsi ilə append-only audit eyni transaction-da yazılır, hədəf
  testlər `22 passed`, tam backend `67 passed`.
- Replay sessiyasını snapshot metadatası və ilkin append-only audit sətri ilə eyni
  transaction-da yaradan repository əlavə edildi; boş dataset birbaşa `completed`
  olur, audit xətası tam rollback verir; `11` yeni test, tam backend `56 passed`.
- `0002` migration-u ilə replay sessiyası sxemi, siyahı/state/owner indeksləri və
  foreign key/trigger ilə qorunan append-only sessiya auditi əlavə edildi; sxem və
  migration hədəf testləri `16 passed`, tam backend `45 passed` nəticəsi verdi.
- Phase 2 replay dataset snapshot-u əlavə edildi: sabit read transaction-ında batch
  oxuması, tick sayı, ilk/son kanonik mövqe və versiyalanmış SHA-256 fingerprint;
  snapshot testləri `7 passed`, tam backend `35 passed` nəticəsi verdi.
- Phase 2 üçün versiyalanmış, SHA-256 checksum nəzarətli və transaction əsaslı
  migration runner-i əlavə edildi; təkrar icra no-op, dəyişmiş migration və dağıdıcı
  SQL fail-closed olur, production yolu açıq icazə tələb edir.
- Replay sorğusu üçün `idx_tick_events_replay(symbol, event_timestamp, event_id)`
  indeksi əlavə edildi və müvəqqəti SQLite bazasında query planı ilə yoxlanıldı;
  migration testləri `6 passed`, tam backend `28 passed` nəticəsi verdi.
- Phase 2 üçün yalnız-oxuma SQLite tick repository-si, `[start_at, end_at)` zaman
  sərhədi, deterministik `(event_timestamp, event_id)` keyset səhifələməsi və xam
  tick dəyişməzliyini qoruyan 6 test əlavə edildi; tam backend nəticəsi `22 passed`.
- Phase 1-in rəsmi 27.18 saatlıq canlı qəbul sınağı `PASSED` nəticəsi ilə
  tamamlandı: `340866` yeni tick, `0` yeni rejection, növbə `0 / 1000`, SQLite
  `quick_check=ok` və bütün avtomatik qəbul qapıları keçdi.
- Phase 1 Stable qəbul qeydləri və Phase 2 yalnız-oxuma repository tapşırığı.

- Phase 11 üçün tam feedback lineage-i, selection-bias və label maturity qoruması,
  performans/drift monitorinqi, təhlükəsiz REVIEW cavabı, immutable model versiyası,
  yenidən SHADOW promotion qapısı, Knowledge Base governance-i və rollback müqaviləsi.
- Phase 10 üçün default-bağlı məhdud icra, execution lease və dəyişməz manifest,
  manual təsdiq, atomik pre-trade risk qapısı, idempotent order həyatı, broker
  reconciliation, kill switch, audit və rollback müqaviləsi.
- Phase 9 üçün real bazar axınında order-siz SHADOW müşahidəsi, causal nəzəri fill,
  xərc və nəzəri portfolio hesabı, champion/challenger müqayisəsi, restart təhlükəsizliyi,
  statistik qəbul və məhdud icra baxışına keçid müqaviləsi.
- Phase 8 üçün deterministik analiz birləşdirməsi, izahlı qərar proposal-u,
  abstain, müstəqil risk qapısı, nəzəri mövqe ölçüsü, portfolio limitləri, halt,
  manual müdaxilə və order-siz SHADOW eligibility müqaviləsi.
- Phase 7 üçün versiyalanmış bilik claim-i, dəyişməz sübut qrafı, scope/rejim
  uyğunluğu, etibarlılıq müddəti, zidd bilik, REVIEW, governance və təhlükəsiz
  retrieval müqaviləsi.
- Phase 6 üçün xəbər mənbə/lisenziya reyestri, point-in-time xəbər və revision,
  iqtisadi buraxılış, fundamental vintage, entity mapping, sentiment sərhədi,
  causal təsir ölçümü və təhlükəsiz event əlaqəsi müqaviləsi.
- Phase 5 üçün deterministik qrafik renderi, Visual AI dataset lineage-i, leakage
  qoruması, zaman əsaslı bölgü, model reproduksiyası, statistik baseline müqayisəsi
  və təhlükəsiz SHADOW hazırlığı müqaviləsi.
- Phase 4 üçün deterministik bar, causal texniki feature, pattern namizədi, label,
  realist backtest, xərc/risk nəticələri və SHADOW hazırlığı müqaviləsi.
- Phase 3 üçün volatilite, spread, tick sürəti, MT5 tick-volume, sessiya müqayisəsi,
  neytral bazar rejimi, uncertainty, keyfiyyət qapısı və nəticə API-si müqaviləsi.
- Phase 3 statistik, texniki analiz və gələcək AI tədqiqatları üçün əvvəlcədən
  qeydiyyat, leakage/overfitting qoruması, toxunulmaz holdout, walk-forward,
  multiple-testing, real icra xərcləri və SHADOW qəbul qapıları müqaviləsi.
- Phase 2 analiz işləri üçün Phase 1 tick növbəsindən ayrılmış davamlı job növbəsi,
  worker claim/lease/fencing, ədalətli scheduler, retry, qəza sonrası bərpa və
  təhlükəsiz shutdown müqaviləsi əlavə edildi.

### Fixed

- `1.22` milyondan çox tick olan canlı bazada sağlam backend-in frontend tərəfindən
  vaxtından əvvəl əlçatmaz sayılması düzəldildi: sorğu müddəti təhlükəsiz artırıldı
  və primary key ilə zəmanətli event unikallığının lazımsız təkrar skanı çıxarıldı;
  PR `#5` üzrə bütün backend/frontend GitHub yoxlamaları keçdi.
- Cari vəziyyət və dəyişiklik tarixçəsində artıq tamamlanmış Phase 1 işlərinin
  qalan və planlaşdırılmış işlər kimi göstərilməsi aradan qaldırıldı.
- GitHub Actions checkout, Python və Node qurulum addımları Node 24 əsaslı rəsmi
  major versiyalara yeniləndi.
- Starlette `TestClient` üçün rəsmi `httpx2` keçidi tamamlandı və backend
  testlərindəki köhnəlmə xəbərdarlığı aradan qaldırıldı.
- Boşaldılmış disk növbəsinin keçmiş `queue_full` xətasına görə hələ də dolu
  göstərilməsi düzəldildi.
- Backend əlçatan olmadıqda status nişanının ingiliscə `unavailable` göstərilməsi
  Azərbaycan dilinə uyğunlaşdırıldı.
- Backend başlanğıcında və `/health` yoxlamasında SQLite bazasına real yazma
  imkanı yoxlanılır.
- İşləmə zamanı SQLite yazma xətası baş verdikdə tick endpoint-i nəzarətsiz xəta
  əvəzinə aydın `503` cavabı qaytarır.

### Added

- Phase 2 audit və qəbul sübutu ixrac müqaviləsi: sanitizasiya edilmiş ZIP/JSONL
  paket, manifest, checksum, rəqəmsal imza, offline verifier, chain-of-custody
  və acceptance `pass`, `fail`, `inconclusive` qaydaları.
- Phase 2 API müqaviləsi: `/api/v2` versiyalanması, asinxron replay və keyfiyyət
  işi, imzalanmış snapshot cursor-u, sorğu və rate limitləri, idempotency,
  optimistic locking və standart xəta envelope-u.
- Phase 2 konfiqurasiya və təhlükəsiz startup müqaviləsi: mühit profilləri,
  məxfi açar sərhədi, startup preflight, funksiya açarları, rotasiya, rollback
  və uzaq giriş tələbləri.
- Phase 2 saxlama və ehtiyat nüsxə müqaviləsi: xam məlumat və auditin qorunması,
  backup manifesti, bərpa sınağı, RPO/RTO hədəfləri, disk təzyiqi və iki mərhələli
  təhlükəsiz təmizləmə qaydaları.
- Phase 2 müşahidə və xəbərdarlıq müqaviləsi: platforma sağlamlığı, replay
  vəziyyəti və məlumat keyfiyyətini ayıran status modeli, aşağı kardinal
  metric-lər, təhlükəsiz strukturlaşdırılmış log, correlation ID, versiyalanmış
  xəta kateqoriyaları, worker heartbeat, alert həyat dövrü və fail-closed
  bütövlük qaydaları.
- Phase 2 giriş və icazə müqaviləsi: müşahidəçi, operator, auditor və
  administrator rolları, permission matrisi, replay ownership-i, yüksək riskli
  əməliyyatlarda təzə autentifikasiya, təhlükəsiz bootstrap və append-only audit
  qaydaları. Heç bir rol xam tick, audit, siqnal və order səlahiyyəti almır.
- Phase 2 performans və yaddaş sınağı müqaviləsi: yalnız sintetik müvəqqəti
  bazada işləyən ölçü pillələri, replay, keyfiyyət analizi, paralel SQLite
  yazma/oxuma, migration, qorunan API və frontend üçün ölçülə bilən qəbul
  hədləri, bütövlük qapıları və audit edilən sübut formatı.
- Phase 2 SQLite sxem və migration müqaviləsi: replay sessiyası, checkpoint,
  append-only audit, idempotency, keyfiyyət hesabatı cədvəlləri, replay indeksi,
  online backup, bütövlük sübutu və təhlükəsiz bərpa meyarları.
- Phase 2 frontend funksional müqaviləsi: replay sessiyası yaratma və idarəetmə,
  addım rejimi, progress, məlumat keyfiyyəti hesabatı, təhlükəsiz xəta davranışı,
  responsive və əlçatanlıq qəbul meyarları.
- Phase 2 replay sessiyasının həyat dövrü müqaviləsi: dəyişməz giriş,
  dataset fingerprint, `step` və `max_speed` rejimləri, checkpoint, restart
  davranışı, idempotent idarəetmə əmrləri və append-only audit tələbləri.
- Phase 2 tick məlumat keyfiyyəti müqaviləsi: versiyalanmış boşluq, timestamp,
  spread, qiymət, gecikmə və müqavilə uyğunluğu qaydaları; audit edilən hesabat
  formatı və sintetik qəbul testləri. Bazar sessiyası məlum olmadan fasilə
  avtomatik məlumat itkisi sayılmır.
- Phase 2 üçün yalnız-oxuma tick replay müqaviləsi: sabit vaxt aralığı,
  deterministik `event_timestamp + event_id` sırası, cursor səhifələmə,
  təhlükəsizlik sərhədi və qəbul meyarları. Bu dəyişiklik yalnız dizayndır;
  Phase 2 istehsal kodu başladılmayıb.

- Tick və Bridge status qəbulunu qoruyan minimum 32 simvolluq
  `X-ESAS-Bridge-Key` autentifikasiyası və MT5 `InpBackendBridgeKey` parametri.
- Backend `0.3.0` və MT5 Bridge `1.6.0` məxfi açarla canlı qoşuldu; qısa qəbul
  yoxlamasında tick sayı artdı, axın `active`, növbə `0 / 1000` qaldı.
- Backend və frontend cavabları üçün `no-store`, clickjacking, MIME sniffing,
  referrer və lazımsız brauzer icazələrinə qarşı təhlükəsizlik başlıqları.
- Server tərəfindən izlənən unikal sessiya identifikatoru və çıxış zamanı həmin
  sessiyanı dərhal etibarsızlaşdıran qorunan `POST /auth/logout` endpoint-i.
- Eyni şəbəkə ünvanından ardıcıl 5 uğursuz giriş cəhdindən sonra 15 dəqiqəlik
  müvəqqəti bloklama və uğurlu girişdə səhv sayğacının sıfırlanması.
- Monitorinq panelində əl ilə yeniləmə düyməsi və yenilənmə vəziyyəti.
- Çoxsaylı MT5 Bridge üçün ümumi göstəricilər və ayrıca simvol/Bridge filtri.
- Phase 1 uzunmüddətli sınaqlarında başlanğıc və son göstəriciləri təhlükəsiz
  JSON sübutu kimi saxlayan və qəbul meyarlarını avtomatik müqayisə edən alət.
- Backend `0.2.0`, MT5 Bridge `1.5.0` və frontend `0.1.0` üçün qəbul sübutlarını,
  geriyə uyğunluğu və Stable keçid şərtlərini göstərən Phase 1 RC1 release qeydləri.
- `7343` tarixi rədd edilmiş event üzrə kök səbəb, audit izi, düzəlişlər və qalıq
  riskləri ayıran yekun Phase 1 məlumat itkisi hesabatı.
- Bütün izlənən layihə mətnləri üçün UTF-8 auditi və kodlaşdırmanı sabitləşdirən
  repo səviyyəli `.editorconfig`.
- MT5 disk növbəsi və retry semantikası üçün real MQL5 fayl API-si ilə işləyən
  avtomatlaşdırılmış qəbul testi; nəticə `44 / 44`, uğursuzluq `0`.
- 12.62 saatlıq canlı sabitlik sınağında `210168` yeni tick qəbul edildi; disk
  növbəsi `0 / 1000` qaldı, yeni rədd edilmiş event yaranmadı və bütün yekun
  backend/frontend yoxlamaları keçdi.
- Phase 1 üçün yenidən qurulmuş qəbul vəziyyəti sənədi və aydın qalan qəbul qapıları.
- Phase 2 replay və məlumat keyfiyyəti mərhələsi üçün ardıcıl icra planı.
- 1 saatlıq canlı sabitlik sınağında `36,506` yeni tick qəbul edildi; yeni rədd
  edilmiş event yaranmadı və növbə `0 / 1000` qaldı.
- Tarixi məlumat itkisini silmədən istifadəçi tərəfindən təsdiqləmək üçün audit cədvəli.
- Qorunan `POST /status/loss/acknowledge` endpoint-i.
- Monitorinq panelində itki hadisəsini təsdiqləmə düyməsi, təsdiq vaxtı və istifadəçi izi.
- Rədd edilən event sayı təsdiqlənmiş həddi keçdikdə xəbərdarlığı yenidən aktiv edən versiyalı təsdiq mexanizmi.
- `7343` tarixi rədd edilmiş event üçün canlı istifadəçi təsdiqi və audit izi yoxlanıldı.
- 30 dəqiqəlik canlı sabitlik sınağında `31,844` yeni tick qəbul edildi; disk növbəsi
  `0 / 1000`, verilənlər bazası bütövlüyü `ok` və ümumi status `ok` qaldı.
- PR #1 üçün GitHub Actions push və pull request axınlarında Backend və Frontend
  testləri uğurla keçdi.
- PR #1 Draft vəziyyətindən çıxarılaraq review üçün hazır edildi.
- Backend və frontend üçün bir-əmrlik təhlükəsiz lokal başlatma skripti.
- Yalnız qeydə aldığı prosesləri dayandıran lokal dayandırma skripti.
- Proses PID-si ilə yanaşı başlanma vaxtını yoxlayan təhlükəsiz proses idarəetməsi.
- Lokal başlatma və dayandırma əməliyyat sənədi.
- İstifadəçi kodu və parol ilə qorunan monitorinq girişi.
- Səkkiz saatlıq imzalanmış backend sessiyası və qorunan monitorinq API-ləri.
- Giriş və icazəsiz API sorğuları üçün avtomatik backend testləri.
- Azərbaycan dilində Phase 1 canlı monitorinq paneli.
- Tick axını, MT5 Bridge, disk növbəsi və rədd edilən event kartları.
- Beş saniyəlik avtomatik yenilənmə və API xətasında son uğurlu məlumatın qorunması.
- Frontend üçün responsive desktop, tablet və mobil quruluş.
- Frontend lint, production build və server-render testi.
- Lokal frontend ünvanları üçün məhdud backend CORS icazəsi.
- GitHub Actions daxilində ayrıca frontend test işi.

- MT5 Bridge `1.5.0` üçün davamlı rejected-event sayğacı.
- `queue_full`, serializasiya, disk və corruption xəta kateqoriyaları.
- `POST /status/bridge` operational status qəbulu.
- `GET /status/operational` daxilində `bridge_delivery` göstəriciləri.
- Bridge queue statusu üçün backend validation və API testləri.
- Backend testləri üçün hər testə məxsus müvəqqəti SQLite bazası.
- Test bazasının canlı `ESAS_PLATFORM.sqlite` faylından tam ayrılması.
- Push və pull request-lər üçün GitHub Actions backend test workflow-u.
- CI daxilində module manifest və Python source validation.
- MT5 Bridge `1.4.0` üçün disk əsaslı davamlı FIFO event növbəsi.
- Restart zamanı pending event-lərin bərpası.
- Uzunluq prefiksli ikili jurnal və davamlı acknowledgement checkpoint-i.
- Queue dizaynı üçün `ADR-0001`.
- Canlı backend outage, EA restart və recovery sınağı.
- Layihənin davamlı yaddaş sistemi.
- Codex üçün daimi `AGENTS.md` iş qaydaları.
- Cari vəziyyət üçün `docs/status/CURRENT_STATE.md`.
- Növbəti tapşırıq üçün `docs/status/NEXT_TASK.md`.
- Layihə dəyişikliklərini izləmək üçün `CHANGELOG.md`.
- MT5 Bridge üçün timer əsaslı FIFO retry mexanizmi.
- Konfiqurasiya olunan retry intervalı.
- Konfiqurasiya olunan batch göndəriş ölçüsü.
- Backend bərpa olduqda buferin avtomatik boşaldılması.
- Retry və batch nəticələri üçün operational log mesajları.

### Changed

- Monitorinq panelinin avtomatik yenilənməsi yalnız brauzer səhifəsi görünəndə
  işləyir; səhifəyə qayıdanda və bağlantı bərpa olunanda dərhal davam edir.
- Frontend tarix və say formatlayıcılarını hər renderdə yenidən yaratmır və
  tamamlanmamış sorğuları səhifədən çıxarkən təhlükəsiz dayandırır.
- Əsas monitorinq kartları ilk Bridge-lə məhdudlaşmır; növbə və rejection
  göstəricilərini bütün görünən Bridge-lər üzrə hesablayır.

### Planned

- Phase 2 yalnız-oxuma tick repository-si və deterministik sıralama testləri.

## Backend 0.1.0 — 2026-07-27

### Added

- FastAPI tətbiqinin ilkin versiyası.
- `GET /health` endpoint-i.
- `POST /events/ticks` endpoint-i.
- `GET /statistics/ticks` endpoint-i.
- `GET /status/operational` endpoint-i.
- Pydantic vasitəsilə `TICK_RECEIVED` event yoxlaması.
- SQLite verilənlər bazasının avtomatik yaradılması.
- Tick event-lərinin saxlanması.
- Eyni `event_id` üçün idempotent yazma.
- Tick statistikalarının hesablanması.
- `waiting`, `active` və `stale` operational statusları.
- Backend API testləri.

### Validated

- Canlı MT5 tick-lərinin backend-ə çatması.
- Tick-lərin SQLite bazasında saxlanması.
- `active` axın vəziyyəti.
- 30 saniyədən sonra `stale` axın vəziyyəti.
- Sınaq zamanı 172 saxlanmış tick.

## ESAS MT5 Bridge 0.2.0 — 2026-07-27

### Added

- MT5-dən canlı tick məlumatının oxunması.
- Standart `TICK_RECEIVED` event yaradılması.
- Event ID yaradılması.
- UTC timestamp yaradılması.
- JSON serializasiyası.
- HTTP POST transportu.
- Backend endpoint konfiqurasiyası.
- Strategy Tester daxilində HTTP məhdudiyyəti xəbərdarlığı.
- Uğursuz event-lər üçün ilkin FIFO yaddaş buferi.

### Known limitations

- HTTP göndərişi hər tick üçün sinxron icra olunur.
- Buferdə saxlanmış event-lər avtomatik təkrar göndərilmir.
- RAM buferi MT5 bağlandıqda itir.
- Bufer dolması siyasəti tam müəyyən edilməyib.
- Modul versiyası bütün fayllarda uyğunlaşdırılmayıb.

## 2026-08-05 — Bölmə əsaslı frontend iş sahəsi

### Added

- Sol naviqasiya menyusu və seçilmiş bölməni göstərən mərkəzi panel.
- Standart `Nəticələr` görünüşü.
- Hər bölmə üçün GOLD-a mümkün təsir, cari rəqəm və açılan tədris izahı.
- Bölmələr üzrə ayrılmış replay, texniki analiz, struktur, likvidlik, BOS/CHoCH,
  retest, strategiya və hipotez görünüşləri.
- Responsiv menyu və frontend naviqasiya müqavilə testləri.

### Validation

- Frontend production build uğurludur.
- Frontend testləri: `8/8 passed`.

## 2026-08-05 — Frontend fokus və istifadə təlimatı

### Changed

- Tam replay idarəetməsi yalnız `Replay sessiyaları` menyusunda saxlanıldı.
- Analiz bölmələri qısa replay konteksti, aid nəticə və `Sessiyanı dəyiş` keçidi ilə sadələşdirildi.
- Hər bölməyə üç addımlı istifadə təlimatı əlavə edildi.
- İstifadəçi görünüşündən texniki `Phase 2` başlığı çıxarıldı.

### Validation

- Frontend production build uğurludur.
- Frontend testləri: `9/9 passed`.
