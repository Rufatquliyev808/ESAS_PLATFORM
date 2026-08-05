# ESAS Platform — Növbəti tapşırıq

Status: BLOCKED — növbəti addım seçilməyib, istifadəçi təsdiqi tələb olunur
Prioritet: —
Mərhələ: Phase 4-ün qalan maddələri

## Tamamlanan (bu sessiya)

- `Causal FVG detektoru 1.0.0` (commit `1aa85c8`).
- Sidebar render-zamanı mutasiya lint düzəlişi (commit `7d49f97`).
- Draft pattern namizədi generatoru — 6 hipotez (commit `0a0f2d2`).
- Faza 2 rəsmi olaraq `STABLE` elan edildi (`docs/releases/PHASE_2_STABLE.md`).
- Pattern namizədi persistence/`registered` qatı (commit `14345fd`).
- Pattern namizədi backtest v1 — əvvəlcə yalnız `structure_break_long/short`.
- Backtest v1 genişləndirildi: `liquidity_sweep.py`-a tarixi `observations`
  əlavə edildi, `liquidity_sweep_reclaim_long/short` də backtest-ə qoşuldu.
  Yol ilə **vacib istiqamət bug-ı** düzəldildi (backtest real qeydə alınmış
  namizədlərdə həmişə uğursuz olurdu — bax `docs/status/CURRENT_STATE.md`).
  Backend `281 passed`, frontend build və `10/10` test.
- Backtest v1 **tamamlandı**: `market_structure.py`-a tarixi
  `observations` əlavə edildi (rejim transition-based hadisə semantikası —
  yalnız `confirmed_structure`-a keçid anı, davam edən rejim təkrarı yox).
  Backtest indi bütün 6 hipotezi əhatə edir. Backend `286 passed`, frontend
  build və `10/10` test.
- `evaluated → accepted_for_shadow | rejected | insufficient_evidence`
  keçidi əlavə edildi (`classify_backtest_verdict`,
  `POST .../{id}/classify`). `archive_pattern_candidate` bütün
  arxivləşdirilə bilən vəziyyətlərdən icazə verəcək şəkildə genişləndirildi.
  Backend `293 passed`, frontend build və `10/10` test.
- Pattern namizədi bölməsinin tam dövrü canlı brauzerdə, ayrıca birdəfəlik
  test bazası ilə vizual təsdiqləndi (real bazaya toxunulmadı, heç bir
  konsol xətası olmadı).
- **Phase 2 worker/scheduler müqaviləsi `pattern_candidate_backtest` üçün
  hərfi tətbiq edildi** (istifadəçinin iki dəfə açıq təsdiqi ilə): tam
  claim/lease/fencing/retry/audit/state-machine (`0007_analysis_jobs.sql`,
  `analysis_job_repository.py`, `workers/analysis_job_worker.py`), icra
  sürücüsü FastAPI `BackgroundTasks`. Yeni API: `POST .../backtest-jobs`,
  `GET .../backtest-jobs/{job_id}`, `POST .../backtest-jobs/{job_id}/cancel`,
  `GET /api/v2/analysis-jobs/metrics`. Yol ilə ikinci bir real bug tapılıb
  düzəldildi (idempotency key hash-i `created_by` daxil edirdi, ownership
  qoruması işə düşmürdü). Backend `321 passed`. **Frontend toxunulmayıb.**

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Açıq qərar — job-queue frontend səthi

Yeni async backtest-job endpoint-ləri üçün heç bir UI yoxdur. Mövcud
"Backtest et" düyməsi sinxron endpoint-dən istifadəni davam etdirir (heç nə
pozulmayıb). Növbəti addım seçilməzdən əvvəl istifadəçi ilə aydınlaşdırılmalı
sual: async job UI əlavə edilsinmi, yoxsa job-queue mühərriki hələlik yalnız
backend infrastrukturu (gələcək uzun-müddətli işlər üçün) olaraq qalsın?

## Namizəd növbəti addımlar (Phase 4, `PROJECT_ROADMAP.md`-dən)

- Job-queue-nun frontend səthi (yuxarıdakı açıq qərar).
- Multiple-testing reyestri (eyni məlumatda çoxlu hipotez sınağının
  qeydiyyatı — hələ yoxdur).
- SHADOW mərhələsi üçün hazırlıq (Phase 9, Phase 1-8 qəbulundan asılıdır).

## Vizual yoxlama qeydi

Tamamlandı (2026-08-05): Pattern namizədi bölməsinin tam dövrü (draft →
qeydiyyat → backtest → nəticələndirmə → arxivləşdirmə) ayrıca, birdəfəlik
test bazası ilə canlı brauzerdə uğurla yoxlanıldı; heç bir konsol xətası
olmadı. Real bazaya toxunulmadı. Ətraflı: `docs/status/CURRENT_STATE.md`.

Job-queue artımı (bu sessiya) yalnız backend testləri ilə yoxlanıldı;
canlı brauzerdə ayrıca vizual sınaqdan keçirilməyib (frontend-də UI-si
olmadığı üçün vizual sınaq mənasız olardı).

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
