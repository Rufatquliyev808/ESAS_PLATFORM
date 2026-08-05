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
- Pattern namizədi backtest v1 — yalnız `structure_break_long/short` üçün
  tarixi hadisə skanı + horizon nəticəsi + xərc ssenariləri + statistik
  etibarlılıq. Backend `277 passed`, frontend build və `10/10` test.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 4, `PROJECT_ROADMAP.md`-dən)

- **Backtest əhatəsini genişləndirmək** — `market_structure` və
  `liquidity_sweep` detektorlarına tam tarixi `observations` siyahısı əlavə
  etmək (hazırda yalnız son müşahidə saxlanılır), sonra bu 4 hipotezi də
  backtest v1-ə qoşmaq. Bu, geriyə uyğun, əlavəedici dəyişiklikdir (yeni
  sahə), amma iki əsas, artıq stabil detektoru (bir neçə frontend/backend
  istehlakçısı olan) diqqətlə genişləndirmək tələb edir.
- **Vəziyyət maşınının qalanı** — `running` (async/job-based icra, hazırda
  sinxron `evaluated`-ə birbaşa keçir), `accepted_for_shadow`, `rejected`,
  `blocked_by_data_quality`, `invalid_leakage`, `insufficient_evidence`,
  `failed`, `cancelled`. CHECK constraint artıq bunları icazə verir
  (`0005` migrasiyası), yalnız tətbiq məntiqi yoxdur.
- Multiple-testing reyestri (eyni məlumatda çoxlu hipotez sınağının
  qeydiyyatı — hələ yoxdur).
- SHADOW mərhələsi üçün hazırlıq.

## Vizual yoxlama qeydi

Pattern namizədi bölməsi (draft, qeydiyyat, arxivləşdirmə, backtest daxil)
canlı brauzerdə açılıb baxılmayıb (yalnız avtomatlaşdırılmış test/build).
Növbəti sessiya imkan olduqda bunu real replay sessiyası ilə vizual
təsdiqləməlidir.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
