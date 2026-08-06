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
- Pattern namizədi backtest v1 — indi bütün 6 hipotezi əhatə edir.
- `evaluated → accepted_for_shadow | rejected | insufficient_evidence`
  keçidi əlavə edildi.
- Pattern namizədi bölməsinin tam dövrü canlı brauzerdə vizual təsdiqləndi.
- **Phase 2 worker/scheduler müqaviləsi** (commit `4739854`, push edilib, CI yaşıl).
- **Multiple-testing reyestri** (commit `76e2e13`, push edilib, CI yaşıl).
- **Phase 9 SHADOW: run manifest + append-only event reyestri skeleti**
  (commit `404922a`, push edilib, CI yaşıl). Canlı sistem deyil.
- **Random-timing baseline müqayisəsi** (commit `6b5b210`, push edilib, CI yaşıl).
- **Tək-feature qaydası + əvvəlki qəbul edilmiş namizəd baseline-ları**
  (commit `4c8b2fa`, push edilib, CI yaşıl) — Phase 3/4-ün 4 baseline
  tələbi tam tətbiq olundu.
- **Real production baza `0005`-`0009` migrasiyalarına köçürüldü**
  (commit `66f8d51`, push edilib, CI yaşıl) — əvvəllər `0004`-də donub
  qalmışdı, "Qeydə alınmış namizədlər" siyahısı `HTTP 500` verirdi. Ehtiyat
  nüsxə götürüldü, doğrulandı, tətbiq edildi.
- **`blocked_by_data_quality` lifecycle vəziyyəti tətbiq edildi** (hələ
  commit edilməyib) — namizədin ilk backtest cəhdindən əvvəl replay
  sessiyasının keyfiyyət hesabatı yoxlanılır; `critical_count > 0`-dırsa
  namizəd `evaluated`-ə deyil, `blocked_by_data_quality`-yə keçir (API
  `409`). Backend `375 passed`, frontend lint/build/`10/10` test təmiz.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 3/4, `PROJECT_ROADMAP.md`-dən)

- Baseline müqayisəsi tamamlandı (4/4).
- `blocked_by_data_quality` tamamlandı.
- Qalan əlavə son vəziyyət: `invalid_leakage` (Phase 3-ün leakage/holdout
  qorumasına bağlıdır, hazırkı backtest v1 arxitekturasında train/holdout
  ayrılığı yoxdur — real məzmunu üçün əvvəlcə bu ayrılığın layihələndirilməsi
  lazımdır).
- Phase 9 sxeminin davamı (nəzəri portfolio/risk cədvəlləri) — yalnız
  istifadəçi ayrıca istəsə, çünki hələ real çağıranı yoxdur.
- Job-queue-nun frontend səthi — yalnız istifadəçi ayrıca istəsə.

## Vizual yoxlama qeydi

Tamamlandı (2026-08-05): Pattern namizədi bölməsinin tam dövrü canlı
brauzerdə uğurla yoxlanıldı; heç bir konsol xətası olmadı. Real bazaya
toxunulmadı. Ətraflı: `docs/status/CURRENT_STATE.md`.

2026-08-06: real production bazanın `0005`-`0009` migrasiyaları istifadəçi
ilə birlikdə canlı brauzerdə aşkarlanan `HTTP 500` xətasından yola çıxaraq
tətbiq edildi və doğrulandı.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
