# ESAS Platform — Növbəti tapşırıq

Status: BLOCKED — növbəti addım seçilməyib, istifadəçi təsdiqi tələb olunur
Prioritet: —
Mərhələ: Phase 4-ün qalan maddələri

## Tamamlanan (bu sessiya)

- `Causal FVG detektoru 1.0.0` (commit `1aa85c8`).
- Sidebar render-zamanı mutasiya lint düzəlişi (commit `7d49f97`).
- Draft pattern namizədi generatoru — 6 hipotez, `GET /pattern-candidates`
  endpoint-i, frontend bölməsi (commit `0a0f2d2`).
- Faza 2 rəsmi olaraq `STABLE` elan edildi (`docs/releases/PHASE_2_STABLE.md`).
- Pattern namizədi persistence/`registered` qatı: `pattern_candidates` +
  append-only audit cədvəlləri, `POST/GET/GET{id}/archive` API-ləri, frontend
  qeydiyyat/arxivləşdirmə. Backend `262 passed`, frontend build və `10/10`
  test.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 4, `PROJECT_ROADMAP.md`-dən)

- **Pattern namizədlərinin yaradılması — hələ də hissəvi.** İndi `draft`
  (hesablama-zamanı) və `registered`/`archived` (persist edilmiş) var. Qalan:
  `running`, `evaluated`, `accepted_for_shadow`, `rejected` və backtest-asılı
  digər vəziyyətlər — bunlar backtest mühərriki olmadan tətbiq edilə bilməz.
- **Backtesting** — realist xərc/slippage/gecikmə ilə tarixi icra
  simulyasiyası. Bu, `registered` namizədi `running`/`evaluated`-ə aparan
  addımdır və indiki üçün ən məntiqli davam nöqtəsidir.
- Uğursuz eksperimentlərin arxivləşdirilməsi (qismən: `archive` API-si var,
  amma "uğursuz" backtest nəticəsi anlayışı hələ yoxdur).
- SHADOW mərhələsi üçün hazırlıq.

## Vizual yoxlama qeydi

Yeni "Pattern namizədləri" bölməsi (qeydiyyat/arxivləşdirmə daxil) canlı
brauzerdə açılıb baxılmayıb (yalnız avtomatlaşdırılmış test/build). Növbəti
sessiya imkan olduqda bunu real replay sessiyası ilə vizual təsdiqləməlidir.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
