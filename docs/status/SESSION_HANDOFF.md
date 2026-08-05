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
  mərhələ).
- Phase 4 detektorları (hamısı causal/no-lookahead, frontend-də ayrıca
  kartlar): bazar strukturu, likvidlik süpürməsi, BOS/CHoCH, retest, FVG.
- Pattern namizədi işi bu qatlardan ibarətdir:
  1. **Draft generator** — hesablama-zamanı 6 hipotez slotu
     (`pattern_candidate.py`, `GET .../pattern-candidates`).
  2. **Persistence/`registered`** — `candidate_confirmed` slotları dəyişməz
     qeyd edir (`pattern_candidate_repository.py`, migration `0005`,
     `POST/GET/GET{id}/archive`).
  3. **Backtest v1** — bütün 6 hipotezi əhatə edir (`structure_break_*`,
     `liquidity_sweep_reclaim_*`, `market_structure_*`).
     (`pattern_candidate_backtest.py`, migration `0006`,
     `POST/GET .../{id}/backtest`). Uğurlu ilk backtest `registered →
     evaluated` keçirir.
  4. **Nəticələndirmə** — `evaluated → accepted_for_shadow | rejected |
     insufficient_evidence` (`POST .../{id}/classify`), İNDİ
     **multiple-testing ailəvi xəta düzəlişi ilə** (bax aşağıda).
  5. **Job-queue** — `pattern_candidate_backtest` backtest-lərini asinxron
     icra edə bilən Phase 2 worker/scheduler mühərriki (bax aşağıda).
     Mövcud sinxron `POST .../backtest` dəyişməz qalıb, job-queue əlavədir.
- **Düzəldilmiş bug (1):** backtest funksiyası əvvəlcə səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, real namizədin `direction`
  sahəsi isə hipotez reyestrindən `"long"/"short"` gəlir. İndi istiqamət
  yalnız `hypothesis_id`-dən təyin olunur.
- **Phase 2 worker/scheduler müqaviləsi `pattern_candidate_backtest` üçün
  hərfi tətbiq edildi** (istifadəçinin iki dəfə açıq təsdiqi ilə — "Tam
  həcmdə tiklə", sonra "Tam müqaviləni hərfi tiklə"):
  - `0007_analysis_jobs.sql` + `analysis_job_repository.py`: tam vəziyyət
    maşını (`queued/claimed/running/.../completed/cancelled/interrupted/
    failed`), claim/lease/fencing, exponential backoff+jitter retry,
    kooperativ cancel (yalnız tək batch sərhədində), append-only audit.
  - **Düzəldilmiş bug (2):** `enqueue_job`-da idempotency key hash-i
    `created_by` ilə birlikdə hesablanırdı — ownership qoruması dead code
    idi. Düzəldildi: hash indi yalnız `job_type:key`.
  - `workers/analysis_job_worker.py`: icra sürücüsü ayrıca worker prosesi
    DEYİL, FastAPI `BackgroundTasks`.
  - Yeni API: `POST .../pattern-candidates/{id}/backtest-jobs` (202),
    `GET .../backtest-jobs/{job_id}`, `POST .../backtest-jobs/{job_id}/cancel`,
    `GET /api/v2/analysis-jobs/metrics`.
  - **Frontend toxunulmayıb** — istifadəçi qərarı: ayrıca UI hələlik
    lazım deyil.
- **Multiple-testing reyestri əlavə edildi** (Phase 3/4 müqaviləsinin
  "multiple-testing qeydiyyatı olmadan namizəd qəbul edilmir" tələbi):
  - `0008_multiple_testing_trials.sql` + `multiple_testing_repository.py`:
    append-only reyestr, `family_key = replay_session_id` (eyni məlumat),
    hər backtest icrasında **şərtsiz** qeydiyyat (nəticələndirilsin ya yox).
  - `bonferroni_corrected_scenario()`: nəticələndirmə anında ailənin cari
    ümumi sınaq sayından (`m`) `alpha=0.05/m` düzəlişli CI hesablayır;
    saxlanmış backtest artefaktına toxunmur, yalnız qərara təsir edir.
  - `classify_replay_pattern_candidate` düzəlişli statusdan qərar verir;
    API cavabında `meta.multiple_testing.{family_trial_count,
    corrected_scenario}` görünür (`data` sahəsi dəyişməyib).
  - Frontend toxunulmayıb — "Nəticələndir" düyməsi dəyişmədən işləyir.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var (sinxron endpoint-dən istifadə edir).
- Backend `333 passed` (job-queue + multiple-testing artımları daxil).
  Frontend bu iki artımda toxunulmadığı üçün ayrıca sınaqdan keçirilməyib
  (əvvəlki artımda `293 passed`, production build və `10/10` test, lint
  təmiz idi).

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `4739854`-ə qədər (job-queue artımı push
  edilib, CI yaşıl).
- **Yeni: multiple-testing reyestri artımı hələ commit edilməyib** — kod
  yazılıb, `333 passed` ilə yoxlanılıb, sənədlər yenilənib, amma AGENTS.md
  qaydasına görə commit/push istifadəçinin ayrıca açıq təsdiqini gözləyir.
  İşçi qovluqda `.tmp/` (əvvəlki sessiyanın pytest qalıqları, untracked,
  əhəmiyyətsiz) də qalıb.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi** (heç bir
  real bazaya tətbiq edilmədən) ki, `lifecycle_state` CHECK-i başdan tam
  müqavilə lüğətini əhatə etsin. `0007` və `0008` isə adi əlavə
  migrasiyalardır (heç bir mövcud cədvələ toxunmur).

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində).
- Frontend: son toxunulan artımda (`293 passed` ilə eyni zamanda) `npm run
  lint` və `npm run test` təmiz idi. Sonrakı iki artım (job-queue,
  multiple-testing) frontend-ə toxunmayıb.
- Canlı brauzerdə vizual yoxlama (2026-08-05, əvvəlki sessiya): Pattern
  namizədi bölməsinin tam dövrü sınandı, heç bir konsol xətası olmadı. Bu
  iki backend-yalnız artım üçün ayrıca vizual sınaq mənasız idi (frontend
  dəyişməyib).

## Növbəti mərhələ

İstifadəçi ilə razılaşdırılıb: **SHADOW mərhələsinə hazırlıq (Phase 9)**.
Diqqət: Phase 9 Phase 1-8 qəbulundan asılıdır; hazırda Phase 1/2 STABLE,
Phase 3/4 hələ tam qəbul edilməyib — SHADOW-a keçidin dəqiq həcmi (hərfi
Phase 9 tətbiqi, yoxsa dizayn/hazırlıq işi) sessiyanın əvvəlində
aydınlaşdırılmalıdır.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir.
