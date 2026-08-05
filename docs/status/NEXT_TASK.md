# ESAS Platform — Növbəti tapşırıq

Status: BLOCKED — növbəti addım seçilməyib, istifadəçi təsdiqi tələb olunur
Prioritet: —
Mərhələ: Phase 4-ün qalan maddələri

## Tamamlanan (bu sessiya)

- `Causal FVG detektoru 1.0.0` (commit `1aa85c8`).
- Sidebar render-zamanı mutasiya lint düzəlişi (commit `7d49f97`).
- Draft pattern namizədi generatoru — 6 hipotez (market_structure, liquidity_sweep,
  structure_break long/short), `GET /pattern-candidates` endpoint-i, frontend
  bölməsi. Backend `251 passed`, frontend build və `10/10` test.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 4, `PROJECT_ROADMAP.md`-dən)

- **Pattern namizədlərinin yaradılması — hissəvi tamamlandı.** Qalan hissə:
  `draft → registered → running → evaluated → accepted_for_shadow | rejected → archived`
  vəziyyət maşını, persistence (yeni cədvəl/migration), tam CRUD API
  (`POST/GET/archive`), multiple-testing reyestri. Bax
  `docs/architecture/PHASE_4_PATTERN_TECHNICAL_ANALYSIS_CONTRACT.md`.
- Backtesting — realist xərc/slippage/gecikmə ilə tarixi icra simulyasiyası
  (pattern namizədi backtest edilmədən `registered`-dən irəli gedə bilməz).
- Uğursuz eksperimentlərin arxivləşdirilməsi.
- SHADOW mərhələsi üçün hazırlıq.

## Kənar (əlaqəsiz, kiçik) iş

- Faza 2 formal olaraq "Stable" elan edilməyib (Faza 1-dəki kimi rəsmi qəbul
  sənədi yoxdur) — bütün roadmap bəndləri `[x]` olsa da, formal bağlanış sənədi yazılmayıb.

## Vizual yoxlama qeydi

Yeni "Pattern namizədləri" bölməsi canlı brauzerdə açılıb baxılmayıb (yalnız
avtomatlaşdırılmış test/build). Növbəti sessiya imkan olduqda bunu real replay
sessiyası ilə vizual təsdiqləməlidir.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
