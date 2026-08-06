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
     **İNDİ TƏSADÜFİ-ZAMAN BASELINE MÜQAYİSƏSİ İLƏ** (bax aşağıda).
  4. **Nəticələndirmə** — `evaluated → accepted_for_shadow | rejected |
     insufficient_evidence`, multiple-testing ailəvi xəta düzəlişi ilə.
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
  yazmır. Yalnız persistence sxemi + iki DB-səviyyəli struktur invariantı
  (`execution_allowed` CHECK-lə `0`-a qıfıllanıb, manifest `INSERT`-dən
  sonra trigger ilə dəyişməzdir). API əlavə edilmədi (real çağıran yoxdur).
- **YENİ, HƏLƏ COMMIT EDİLMƏYİB: Backtest v1-ə təsadüfi-zaman baseline
  müqayisəsi əlavə edildi.** Phase 3/4-ün 4 baseline tələbindən (no-signal,
  təsadüfi-zaman, tək-feature, əvvəlki namizəd) yalnız bu biri — istifadəçi
  ilə həcm razılaşdırıldı. `_random_timing_baseline_raw_returns()`: eyni
  bar seriyasından, eyni istiqamət/horizon ilə, **seed-lənmiş deterministik
  təsadüfi** girişlər (seed yalnız sabit girişlərdən — reproducibility).
  `BacktestCostScenario` 3 yeni sahə daşıyır
  (`random_timing_baseline_sample_size/mean_return_percent`,
  `beats_random_timing_baseline`). Qərar qaydası: namizəd indi HƏM sıfırı,
  HƏM DƏ baseline-ı keçməlidir ki, `supportive_evidence` olsun —
  keçməyəndə yeni `ci_does_not_exceed_random_timing_baseline` səbəbi ilə
  `rejected`-ə aparır. `bonferroni_corrected_scenario()` da uyğunlaşdırıldı
  (düzəliş baseline yoxlamasını gizlədə bilməz). `BACKTEST_VERSION 1.3.0`.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var (sinxron endpoint-dən istifadə edir). Son dörd artım
  (job-queue, multiple-testing, Phase 9 skeleti, baseline) frontend-ə
  toxunmayıb — yeni sahələr backend cavabında var, UI-də göstərilmir.
- Backend `356 passed` (bütün artımlar daxil).

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `404922a`-ə qədər (job-queue, multiple-testing,
  Phase 9 skeleti — üçü də push edilib, CI-də yaşıl).
- **Yeni: təsadüfi-zaman baseline artımı hələ commit edilməyib** — kod
  yazılıb, `356 passed` ilə yoxlanılıb, sənədlər yenilənib, amma AGENTS.md
  qaydasına görə commit/push istifadəçinin ayrıca açıq təsdiqini gözləyir.
  İşçi qovluqda `.tmp/` (əvvəlki sessiyanın pytest qalıqları, untracked,
  əhəmiyyətsiz) də qalıb.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi** (heç bir
  real bazaya tətbiq edilmədən). `0007`, `0008`, `0009` isə adi əlavə
  migrasiyalardır. Bu artımda yeni migration yoxdur (yalnız
  `pattern_candidate_backtest.py`-ın nəticə sxemi genişləndi).

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində).
- Frontend: son toxunulan artımda (`293 passed` ilə eyni zamanda) `npm run
  lint` və `npm run test` təmiz idi. Sonrakı dörd artım (job-queue,
  multiple-testing, Phase 9 skeleti, baseline) frontend-ə toxunmayıb.
- Canlı brauzerdə vizual yoxlama (2026-08-05, əvvəlki sessiya): Pattern
  namizədi bölməsinin tam dövrü sınandı, heç bir konsol xətası olmadı.
  Sonrakı backend-yalnız artımlar üçün ayrıca vizual sınaq mənasız idi.

## Növbəti mərhələ

Seçilməyib. Namizədlər (`docs/status/NEXT_TASK.md`): baseline
müqayisəsinin qalanı (tək-feature qaydası, əvvəlki namizəd müqayisəsi),
`blocked_by_data_quality` lifecycle vəziyyəti, Phase 9 sxeminin davamı
(yalnız istəsə). İstifadəçinin ayrıca təsdiqi tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir.
