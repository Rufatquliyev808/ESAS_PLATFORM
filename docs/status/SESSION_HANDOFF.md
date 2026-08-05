# ESAS Platform — Sessiya handoff

Son yenilənmə: 2026-08-05

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
- Pattern namizədi işi üç qatdan ibarətdir:
  1. **Draft generator** — hesablama-zamanı 6 hipotez slotu
     (`pattern_candidate.py`, `GET .../pattern-candidates`).
  2. **Persistence/`registered`** — `candidate_confirmed` slotları dəyişməz
     qeyd edir (`pattern_candidate_repository.py`, migration `0005`,
     `POST/GET/GET{id}/archive`).
  3. **Backtest v1** — İNDİ BÜTÜN 6 HİPOTEZİ ƏHATƏ EDİR
     (`structure_break_*`, `liquidity_sweep_reclaim_*`,
     `market_structure_*`). `market_structure` üçün "tarixi hadisə" =
     rejimin `confirmed_structure`-a keçdiyi an (transition-based, davam
     edən rejimin sonrakı pivotları təkrar hadisə yaratmır — üst-üstə
     düşən nümunələrin qarşısını almaq üçün). Tarixi hadisə skanı, horizon
     nəticəsi, xərc ssenariləri, statistik etibarlılıq
     (`pattern_candidate_backtest.py`, migration `0006`,
     `POST/GET .../{id}/backtest`). Uğurlu ilk backtest `registered →
     evaluated` keçirir.
- **Düzəldilmiş bug (1):** backtest funksiyası əvvəlcə səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, real namizədin `direction`
  sahəsi isə hipotez reyestrindən `"long"/"short"` gəlir — bu, real axında
  backtest-i həmişə uğursuz edərdi. İndi istiqamət yalnız `hypothesis_id`-dən
  təyin olunur.
- Vəziyyət maşınının qalan hissəsindən (`running`, `accepted_for_shadow`,
  `rejected`, `blocked_by_data_quality`, `invalid_leakage`,
  `insufficient_evidence`, `failed`, `cancelled`) İNDİ `running`/`failed`/
  `cancelled` **iş növbəsi (job-queue) vasitəsilə tətbiq edilib** — bax
  aşağıdakı bölmə. Qalanlar (`blocked_by_data_quality`, `invalid_leakage`)
  hələ tətbiq edilməyib.
- **Yeni: Phase 2 worker/scheduler müqaviləsi `pattern_candidate_backtest`
  üçün hərfi tətbiq edildi** (istifadəçinin iki dəfə açıq təsdiqi ilə —
  "Tam həcmdə tiklə", sonra "Tam müqaviləni hərfi tiklə"):
  - `0007_analysis_jobs.sql`: `analysis_jobs` tam vəziyyət maşını
    (`queued/claimed/running/pausing/paused/retry_wait/completed/cancelled/
    interrupted/failed`), monoton `fencing_token`, lease, `state_version`
    optimistic lock + append-only `analysis_job_audit`.
  - `analysis_job_repository.py`: `enqueue_job` (idempotent, istifadəçi
    başına maks `3` aktiv iş), `claim_next_job` (vaxtı keçmiş lease-ləri
    əvvəlcə bərpa edir, fencing token artırır), `send_heartbeat`,
    `complete_job` (kooperativ cancel — işləyən işi yalnız öz tək batch
    sərhədində, bitəndə `cancelled`-ə çevirir), `fail_job` (yalnız
    `retryable=True` exponential backoff+jitter ilə təkrarlanır),
    `request_cancel`, `queue_metrics`.
  - **Düzəldilmiş bug (2):** `enqueue_job`-da idempotency key hash-i
    `created_by` ilə birlikdə hesablanırdı — fərqli istifadəçilər eyni key
    ilə heç vaxt toqquşmurdu, ownership qoruması faktiki dead code idi.
    Düzəldildi: hash indi yalnız `job_type:key`, ownership tapılan sətirdə
    real yoxlanır.
  - `workers/analysis_job_worker.py`: icra sürücüsü ayrıca worker prosesi
    DEYİL, FastAPI `BackgroundTasks` — DB claim/lease/fencing məntiqi düzgün
    olduğu üçün gələcək real worker prosesi tərəfindən dəyişmədən istifadə
    edilə bilər.
  - Yeni API: `POST .../pattern-candidates/{id}/backtest-jobs` (202),
    `GET .../backtest-jobs/{job_id}`, `POST .../backtest-jobs/{job_id}/cancel`,
    `GET /api/v2/analysis-jobs/metrics`. Mövcud sinxron `POST .../backtest`
    dəyişməz qalıb (əvəzləmə deyil, əlavədir).
  - **Frontend hələ toxunulmayıb** — bu, istifadəçi ilə açıq qərar tələb
    edən qeyd-açıq məsələdir (bax `docs/status/NEXT_TASK.md`).
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) var
  (sinxron endpoint-dən istifadə edir, job-queue-ya hələ bağlanmayıb).
- Backend `321 passed` (job-queue artımı daxil). Frontend bu artımda
  toxunulmadığı üçün ayrıca sınaqdan keçirilməyib (əvvəlki artımda `293
  passed`, production build və `10/10` test, lint təmiz idi).
- `evaluated → accepted_for_shadow | rejected | insufficient_evidence`
  keçidi əlavə edildi — verdikt yalnız son backtest-in "normal" ssenari
  statusundan deterministik hesablanır. `archive_pattern_candidate` bütün
  arxivləşdirilə bilən vəziyyətlərdən (`registered/evaluated/
  accepted_for_shadow/rejected/insufficient_evidence`) icazə verəcək
  şəkildə genişləndirildi (əvvəllər yalnız `registered`-dən mümkün idi).

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `1b891db`-yə qədər. Sessiya ərzində 9 commit
  ardıcıl push edildi və hər biri ayrıca CI-də (Backend + Frontend) yaşıl
  nəticə aldı: `1aa85c8` → `7d49f97` → `0a0f2d2` → `847249b` → `14345fd` →
  `73bf580` → `90133ac` → `4fcaff6` → `1b891db` (sonuncu push edilmiş).
- **Yeni: job-queue artımı (bu bölmədəki "Phase 2 worker/scheduler"
  dəyişiklikləri) hələ commit edilməyib** — kod yazılıb, `321 passed` ilə
  yoxlanılıb, sənədlər yenilənib, amma AGENTS.md qaydasına görə commit/push
  istifadəçinin ayrıca açıq təsdiqini gözləyir.
  İşçi qovluqda `.tmp/` (əvvəlki sessiyanın pytest qalıqları, untracked,
  əhəmiyyətsiz) da qalıb.
- Diqqət: istifadəçi bir dəfə eyni lint düzəlişini paralel bir fon
  sessiyasında da (`task_b2a032b5`) başlatmışdı; nəticəsi bu sessiyaya
  gəlməyib. Növbəti sessiya `git fetch`/`git log origin/main` ilə
  gözlənilməz commit olub-olmadığını yoxlamalıdır (ehtiyat tədbiri kimi).
- `0005` migrasiyası bu sessiyada bir dəfə **amend edildi** (heç bir real
  bazaya tətbiq edilmədən) ki, `lifecycle_state` CHECK-i başdan tam
  müqavilə lüğətini əhatə etsin — SQLite-də CHECK genişləndirmək DROP tələb
  edir, migration runner isə DROP-u təhlükəsizlik naminə bloklayır. Əgər
  başqa migrasiya artıq tətbiq edilibsə, bu barədə diqqətli ol.

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində).
- Frontend: `npm run lint` və `npm run test` (build + testlər) təmiz.
- **Canlı brauzerdə vizual yoxlama tamamlandı** (əvvəlki sessiyalardakı
  "naməlum xarici mühit məhdudiyyəti" səbəbi bu dəfə aradan qalxdı —
  problem sadəcə brauzer sekmesinin "hidden" `visibilityState`-də olması
  idi, "Yenilə" düyməsinə əl ilə klikləməklə aradan qalxdı). Ayrıca,
  birdəfəlik test bazası (port `8001`/`5173`, real `database/
  ESAS_PLATFORM.sqlite`-a toxunulmadan) ilə Pattern namizədləri
  bölməsinin tam dövrü (draft → qeydiyyat → backtest → nəticələndirmə →
  arxivləşdirmə) və "Bazar strukturu" bölməsi sınandı; brauzer konsolunda
  heç bir xəta olmadı. Bütün müvəqqəti proseslər və fayllar (`.env.local`
  daxil) təmizləndi.

## Növbəti mərhələ

Seçilməyib. Job-queue mühərriki (`pattern_candidate_backtest` üçün
`running`/`failed`/`cancelled`) hazırdır, amma commit/push və frontend
səthi açıq qalır. Namizədlər (`docs/status/NEXT_TASK.md`): job-queue
frontend UI-si (əlavə edilsinmi?), multiple-testing reyestri, SHADOW
hazırlığı. İstifadəçinin ayrıca təsdiqi tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir.
