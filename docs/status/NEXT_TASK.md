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

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 4, `PROJECT_ROADMAP.md`-dən)

- **Vəziyyət maşınının qalan hissəsi** — `running` (async/job-based icra,
  hazırda backtest sinxron olaraq birbaşa `evaluated`-ə keçir),
  `blocked_by_data_quality`, `invalid_leakage`, `failed`, `cancelled`.
  Bunların hamısı CHECK constraint-də icazəlidir (`0005` migrasiyası), amma
  tətbiq məntiqi yoxdur və hazırkı sinxron backtest üçün əsaslı ehtiyac
  görünmür (job-növbəsi tələb edən uzun əməliyyat yoxdur).
- Multiple-testing reyestri (eyni məlumatda çoxlu hipotez sınağının
  qeydiyyatı — hələ yoxdur).
- SHADOW mərhələsi üçün hazırlıq (Phase 9, Phase 1-8 qəbulundan asılıdır).

## Vizual yoxlama qeydi

Pattern namizədi bölməsi (draft, qeydiyyat, arxivləşdirmə, backtest daxil)
canlı brauzerdə açılıb baxılmayıb (yalnız avtomatlaşdırılmış test/build).
Növbəti sessiya imkan olduqda bunu real replay sessiyası ilə vizual
təsdiqləməlidir.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
