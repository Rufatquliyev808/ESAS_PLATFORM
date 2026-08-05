# ESAS Platform — Dəyişiklik Tarixçəsi

Bu fayl ESAS Platform-da edilən əsas dəyişiklikləri izləyir.

Format Semantic Versioning prinsipinə əsaslanır:

`MAJOR.MINOR.PATCH`

## Unreleased

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
