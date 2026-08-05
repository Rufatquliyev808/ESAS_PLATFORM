# ESAS Platform — Növbəti tapşırıq

Status: BLOCKED — növbəti addım seçilməyib, istifadəçi təsdiqi tələb olunur
Prioritet: —
Mərhələ: Phase 4-ün qalan maddələri + Phase 9 skeleti

## Tamamlanan (bu sessiya)

- `Causal FVG detektoru 1.0.0` (commit `1aa85c8`).
- Sidebar render-zamanı mutasiya lint düzəlişi (commit `7d49f97`).
- Draft pattern namizədi generatoru — 6 hipotez (commit `0a0f2d2`).
- Faza 2 rəsmi olaraq `STABLE` elan edildi (`docs/releases/PHASE_2_STABLE.md`).
- Pattern namizədi persistence/`registered` qatı (commit `14345fd`).
- Pattern namizədi backtest v1 — indi bütün 6 hipotezi əhatə edir.
- `evaluated → accepted_for_shadow | rejected | insufficient_evidence`
  keçidi əlavə edildi.
- Pattern namizədi bölməsinin tam dövrü canlı brauzerdə vizual təsdiqləndi.
- **Phase 2 worker/scheduler müqaviləsi `pattern_candidate_backtest` üçün
  hərfi tətbiq edildi** (commit `4739854`, push edilib, CI yaşıl): tam
  claim/lease/fencing/retry/audit/state-machine, icra sürücüsü FastAPI
  `BackgroundTasks`. Yeni API: `POST/GET/POST-cancel .../backtest-jobs`,
  `GET /api/v2/analysis-jobs/metrics`. Frontend toxunulmayıb (istifadəçi
  qərarı: hələlik lazım deyil).
- **Multiple-testing reyestri əlavə edildi** (commit `76e2e13`, push
  edilib, CI yaşıl): `evaluated → accepted_for_shadow` qərarı artıq eyni
  replay sessiyasında sınanan bütün backtest-lərin sayına görə Bonferroni
  ailəvi xəta düzəlişi tətbiq edir. Qeydiyyat hər backtest icrasında
  şərtsizdir.
- **Phase 9 SHADOW: run manifest + append-only event reyestri skeleti**
  (hələ commit edilməyib) — `0009_shadow_runs.sql`,
  `shadow_run_repository.py`, `shadow_event_repository.py`. **Bu, canlı
  SHADOW sistemi DEYİL** — Phase 5-8 (real qərar generatoru) hələ yoxdur,
  ona görə bu cədvəllərə hələ heç bir istehsalat kodu yazmır. Yalnız
  müqavilənin 3/9-cu bölmələrindəki persistence sxemi + iki DB-səviyyəli
  struktur invariantı (`execution_allowed` həmişə `0`, manifest
  `INSERT`-dən sonra dəyişməz) tikilib və test edilib. API endpoint-i
  şüurlu şəkildə əlavə edilmədi (real çağıran yoxdur). Backend `352 passed`.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Açıq sual — Phase 9-un davamı

SHADOW skeleti (manifest + event reyestri) hazırdır, amma **real işləyən
heç nə yoxdur**: heç bir kod bu cədvəllərə yazmır, çünki Phase 5-8 (Visual
AI, xəbər/fundamental, Knowledge Base, Decision/Risk) hələ yalnız dizayn
sənədləridir. Növbəti addım seçilməzdən əvvəl istifadəçi ilə aydınlaşdırıla
bilər:
- daha çox Phase 9 sxemi (məs. nəzəri portfolio/risk müqaviləsi, section 6)
  eyni "skelet" formatında tikilsin, yoxsa;
- fokus geriyə, Phase 3/4-ün qalan, real istifadə olunan işlərinə
  qaytarılsın (Phase 4 hələ formal olaraq IN PROGRESS, tam qəbul
  edilməyib).

## Vizual yoxlama qeydi

Tamamlandı (2026-08-05): Pattern namizədi bölməsinin tam dövrü canlı
brauzerdə uğurla yoxlanıldı; heç bir konsol xətası olmadı. Real bazaya
toxunulmadı. Ətraflı: `docs/status/CURRENT_STATE.md`.

Job-queue, multiple-testing və Phase 9 skeleti artımları (bu sessiya)
yalnız backend testləri ilə yoxlanıldı; frontend-ə toxunulmadığı üçün canlı
brauzerdə ayrıca vizual sınaq mənasız olardı.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
