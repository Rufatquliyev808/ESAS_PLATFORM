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
  mərhələ). **Phase 9: hələ "DESIGN READY — NOT IMPLEMENTED"** (bax aşağıda
  — yalnız persistence skeleti tikilib, canlı sistem yoxdur).
- Phase 4 detektorları (hamısı causal/no-lookahead, frontend-də ayrıca
  kartlar): bazar strukturu, likvidlik süpürməsi, BOS/CHoCH, retest, FVG.
- Pattern namizədi işi bu qatlardan ibarətdir:
  1. **Draft generator** — hesablama-zamanı 6 hipotez slotu.
  2. **Persistence/`registered`** — `candidate_confirmed` slotları dəyişməz
     qeyd edir (migration `0005`).
  3. **Backtest v1** — bütün 6 hipotezi əhatə edir (migration `0006`).
  4. **Nəticələndirmə** — `evaluated → accepted_for_shadow | rejected |
     insufficient_evidence`, **multiple-testing ailəvi xəta düzəlişi ilə**
     (bax aşağıda).
  5. **Job-queue** — `pattern_candidate_backtest` üçün Phase 2
     worker/scheduler mühərriki (bax aşağıda). Mövcud sinxron
     `POST .../backtest` dəyişməz qalıb, job-queue əlavədir.
- **Düzəldilmiş bug (1):** backtest funksiyası əvvəlcə səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, real namizədin `direction`
  sahəsi isə hipotez reyestrindən `"long"/"short"` gəlir. Düzəldilib.
- **Phase 2 worker/scheduler müqaviləsi `pattern_candidate_backtest` üçün
  hərfi tətbiq edildi** (commit `4739854`, PUSH EDİLİB, CI yaşıl):
  claim/lease/fencing/retry/audit/state-machine (`0007_analysis_jobs.sql`),
  icra sürücüsü FastAPI `BackgroundTasks`. Yeni API: `POST/GET/POST-cancel
  .../backtest-jobs`, `GET /api/v2/analysis-jobs/metrics`.
  **Düzəldilmiş bug (2):** `enqueue_job`-da idempotency key hash-i
  `created_by` ilə birlikdə hesablanırdı, ownership qoruması dead code idi.
  **Frontend toxunulmayıb** — istifadəçi qərarı: hələlik lazım deyil.
- **Multiple-testing reyestri əlavə edildi** (commit `76e2e13`, PUSH
  EDİLİB, CI yaşıl) — Phase 3/4-ün "multiple-testing qeydiyyatı olmadan
  namizəd qəbul edilmir" tələbi: `0008_multiple_testing_trials.sql`
  (`family_key = replay_session_id`, hər backtest icrasında şərtsiz
  qeydiyyat), `bonferroni_corrected_scenario()` (`alpha=0.05/m` düzəlişli
  CI, saxlanmış artefaktı dəyişmir). `classify_replay_pattern_candidate`
  düzəlişli statusdan qərar verir; API `meta.multiple_testing` altında
  görünür. Frontend toxunulmayıb.
- **YENİ, HƏLƏ COMMIT EDİLMƏYİB: Phase 9 SHADOW run manifest + append-only
  event reyestri skeleti.** `0009_shadow_runs.sql`,
  `shadow_run_repository.py`, `shadow_event_repository.py`. **Diqqət: bu
  canlı SHADOW deyil** — Phase 5-8 (real qərar generatoru) yoxdur, heç bir
  istehsalat kodu bu cədvəllərə yazmır. Yalnız müqavilənin 3/9-cu
  bölmələrinin persistence sxemi + iki DB-səviyyəli struktur invariantı
  (`execution_allowed` CHECK-lə `0`-a qıfıllanıb, manifest `INSERT`-dən
  sonra trigger ilə dəyişməzdir) tikilib. API əlavə edilmədi (real çağıran
  yoxdur). `19` yeni test (`test_shadow_run_repository.py` `13`,
  `test_shadow_event_repository.py` `6`).
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var (sinxron endpoint-dən istifadə edir). Son üç artım
  (job-queue, multiple-testing, Phase 9 skeleti) frontend-ə toxunmayıb.
- Backend `352 passed` (bütün artımlar daxil, Phase 9 skeleti daxil olmaqla).

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `76e2e13`-ə qədər (job-queue + multiple-testing
  push edilib, hər ikisi CI-də yaşıl).
- **Yeni: Phase 9 skeleti artımı hələ commit edilməyib** — kod yazılıb,
  `352 passed` ilə yoxlanılıb, sənədlər yenilənib, amma AGENTS.md qaydasına
  görə commit/push istifadəçinin ayrıca açıq təsdiqini gözləyir.
  İşçi qovluqda `.tmp/` (əvvəlki sessiyanın pytest qalıqları, untracked,
  əhəmiyyətsiz) də qalıb.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi** (heç bir
  real bazaya tətbiq edilmədən). `0007`, `0008`, `0009` isə adi əlavə
  migrasiyalardır (heç bir mövcud cədvələ toxunmur).

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində).
- Frontend: son toxunulan artımda (`293 passed` ilə eyni zamanda) `npm run
  lint` və `npm run test` təmiz idi. Sonrakı üç artım (job-queue,
  multiple-testing, Phase 9 skeleti) frontend-ə toxunmayıb.
- Canlı brauzerdə vizual yoxlama (2026-08-05, əvvəlki sessiya): Pattern
  namizədi bölməsinin tam dövrü sınandı, heç bir konsol xətası olmadı.
  Sonrakı backend-yalnız artımlar üçün ayrıca vizual sınaq mənasız idi.

## Növbəti mərhələ

Seçilməyib. Phase 9 skeleti hazırdır, amma real işləyən heç nə yoxdur
(Phase 5-8 olmadan heç bir kod bu cədvəllərə yazmır). Açıq sual
(`docs/status/NEXT_TASK.md`): daha çox Phase 9 sxemi (nəzəri
portfolio/risk) eyni skelet formatında davam etsin, yoxsa fokus Phase 3/4-ün
qalan real işlərinə qaytarılsın. İstifadəçinin ayrıca təsdiqi tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir.
