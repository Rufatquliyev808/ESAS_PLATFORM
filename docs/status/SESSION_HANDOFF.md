# ESAS Platform — Sessiya handoff

Son yenilənmə: 2026-08-06

## Başlanğıc

- Əsas layihə: `D:\ESAS_PLATFORM`
- `AGENTS.md` sənədindəki oxuma sırasını tam icra et.
- Git statusunu, branch-i və son commitləri yoxla; mövcud dəyişiklikləri silmə və görülmüş işi təkrarlama.
- GitHub girişini `gh auth status` ilə yoxla; məxfi tokeni istəmə və çap etmə.

## Cari vəziyyət (ətraflı: `docs/status/CURRENT_STATE.md`)

- **Phase 1: STABLE. Phase 2 (Replay və məlumat keyfiyyəti): STABLE**
  (`docs/releases/PHASE_2_STABLE.md`). **Phase 4: IN PROGRESS** (cari aktiv
  mərhələ). **Phase 9: hələ "DESIGN READY — NOT IMPLEMENTED"** — yalnız
  persistence skeleti tikilib, canlı sistem yoxdur.
- Phase 4 detektorları (hamısı causal/no-lookahead, frontend-də ayrıca
  kartlar): bazar strukturu, likvidlik süpürməsi, BOS/CHoCH, retest, FVG.
- Pattern namizədi işi bu qatlardan ibarətdir:
  1. **Draft generator** — hesablama-zamanı 6 hipotez slotu.
  2. **Persistence/`registered`** — `candidate_confirmed` slotları dəyişməz
     qeyd edir (migration `0005`).
  3. **Backtest v1** — bütün 6 hipotezi əhatə edir (migration `0006`),
     **İNDİ 4/4 BASELINE MÜQAYİSƏSİ İLƏ TAMAMLANDI** (bax aşağıda).
  4. **Nəticələndirmə** — `evaluated → accepted_for_shadow | rejected |
     insufficient_evidence`, multiple-testing ailəvi xəta düzəlişi VƏ
     əvvəlki qəbul edilmiş namizədlə müqayisə ilə.
  5. **Job-queue** — `pattern_candidate_backtest` üçün Phase 2
     worker/scheduler mühərriki. Mövcud sinxron `POST .../backtest`
     dəyişməz qalıb, job-queue əlavədir.
- **Düzəldilmiş bug (1):** backtest funksiyası əvvəlcə səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, real namizədin `direction`
  sahəsi isə hipotez reyestrindən `"long"/"short"` gəlir. Düzəldilib.
- **Phase 2 worker/scheduler müqaviləsi `pattern_candidate_backtest` üçün
  hərfi tətbiq edildi** (commit `4739854`, PUSH EDİLİB, CI yaşıl).
  **Düzəldilmiş bug (2):** `enqueue_job`-da idempotency key hash-i
  `created_by` ilə birlikdə hesablanırdı, ownership qoruması dead code idi.
  **Frontend toxunulmayıb** — istifadəçi qərarı: hələlik lazım deyil.
- **Multiple-testing reyestri əlavə edildi** (commit `76e2e13`, PUSH
  EDİLİB, CI yaşıl) — `0008_multiple_testing_trials.sql`
  (`family_key = replay_session_id`, hər backtest icrasında şərtsiz
  qeydiyyat), `bonferroni_corrected_scenario()` (`alpha=0.05/m` düzəlişli
  CI, saxlanmış artefaktı dəyişmir). Frontend toxunulmayıb.
- **Phase 9 SHADOW run manifest + append-only event reyestri skeleti**
  (commit `404922a`, PUSH EDİLİB, CI yaşıl). **Diqqət: bu canlı SHADOW
  deyil** — Phase 5-8 yoxdur, heç bir istehsalat kodu bu cədvəllərə
  yazmır. API əlavə edilmədi (real çağıran yoxdur).
- **Random-timing baseline müqayisəsi** (commit `6b5b210`, PUSH EDİLİB,
  CI yaşıl) — `_random_timing_baseline_raw_returns()`, seed-lənmiş
  deterministik təsadüfi girişlər. `BACKTEST_VERSION 1.3.0`.
- **YENİ, HƏLƏ COMMIT EDİLMƏYİB: Tək-feature qaydası + əvvəlki qəbul
  edilmiş namizəd baseline-ları.** Phase 3/4-ün 4 baseline tələbi indi TAM
  tətbiq olunub:
  - **Tək-feature:** `_single_feature_rsi_reversal_raw_returns()` — sabit
    (tənzimlənməyən) RSI 30/70 reversal qaydası. `run_pattern_candidate_backtest`
    `rsi: IndicatorSeries | None = None` qəbul edir
    (`context.indicators.rsi` real çağırışda ötürülür); RSI yoxdursa
    baseline boş keçir, bloklamır.
  - **Əvvəlki namizəd:** `get_latest_accepted_candidate_for_hypothesis()`
    (`pattern_candidate_repository.py`) — eyni hipotez üzrə **qlobal**
    (bütün sessiyalar, multiple-testing ailəsindən fərqli) ən son
    `accepted_for_shadow` namizədi tapır. `classify_replay_pattern_candidate`
    əgər qərar `accepted_for_shadow` olacaqdısa və əvvəlki varsa, yeni
    namizədin orta gəliri əvvəlkini keçməlidir, yoxsa `rejected`.
  - `BacktestCostScenario`-ya daha 3 sahə (`single_feature_baseline_*`).
    `bonferroni_corrected_scenario()` uyğunlaşdırıldı. API-də
    `meta.previous_accepted_candidate_comparison`. `BACKTEST_VERSION 1.4.0`.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var (sinxron endpoint-dən istifadə edir). Bu sessiyanın
  sonrakı bütün artımları (job-queue, multiple-testing, Phase 9 skeleti,
  4 baseline) frontend-ə toxunmayıb — yeni sahələr backend cavabında var,
  UI-də göstərilmir.
- Backend `368 passed` (bütün artımlar daxil).

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `6b5b210`-ə qədər (job-queue, multiple-testing,
  Phase 9 skeleti, random-timing baseline — dördü də push edilib, CI-də
  yaşıl).
- **Yeni: tək-feature + əvvəlki-namizəd baseline artımı hələ commit
  edilməyib** — kod yazılıb, `368 passed` ilə yoxlanılıb, sənədlər
  yenilənib, amma AGENTS.md qaydasına görə commit/push istifadəçinin
  ayrıca açıq təsdiqini gözləyir. İşçi qovluqda `.tmp/` (əvvəlki
  sessiyanın pytest qalıqları, untracked, əhəmiyyətsiz) də qalıb.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi** (heç bir
  real bazaya tətbiq edilmədən). `0007`, `0008`, `0009` isə adi əlavə
  migrasiyalardır. Bu artımda yeni migration yoxdur (yalnız
  `pattern_candidate_backtest.py`/`pattern_candidate_repository.py`
  genişləndi).

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində).
- Frontend: son toxunulan artımda (`293 passed` ilə eyni zamanda) `npm run
  lint` və `npm run test` təmiz idi. Sonrakı beş artım frontend-ə
  toxunmayıb.
- Canlı brauzerdə vizual yoxlama (2026-08-05, əvvəlki sessiya): Pattern
  namizədi bölməsinin tam dövrü sınandı, heç bir konsol xətası olmadı.
  Sonrakı backend-yalnız artımlar üçün ayrıca vizual sınaq mənasız idi.

## Növbəti mərhələ

Seçilməyib. Baseline müqayisəsi tamamlandı (4/4). Namizədlər
(`docs/status/NEXT_TASK.md`): `blocked_by_data_quality` lifecycle
vəziyyəti, Phase 9 sxeminin davamı (yalnız istəsə), job-queue-nun frontend
səthi (yalnız istəsə). İstifadəçinin ayrıca təsdiqi tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir.
