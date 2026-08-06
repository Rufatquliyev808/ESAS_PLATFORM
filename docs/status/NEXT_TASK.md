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
- **Phase 2 worker/scheduler müqaviləsi `pattern_candidate_backtest` üçün
  hərfi tətbiq edildi** (commit `4739854`, push edilib, CI yaşıl).
- **Multiple-testing reyestri əlavə edildi** (commit `76e2e13`, push
  edilib, CI yaşıl).
- **Phase 9 SHADOW: run manifest + append-only event reyestri skeleti**
  (commit `404922a`, push edilib, CI yaşıl). Canlı sistem deyil.
- **Random-timing baseline müqayisəsi** (commit `6b5b210`, push edilib,
  CI yaşıl).
- **Tək-feature qaydası + əvvəlki qəbul edilmiş namizəd baseline-ları**
  (hələ commit edilməyib) — Phase 3/4-ün 4 baseline tələbi indi TAM
  tətbiq olunub:
  1. no-signal (örtülü, mövcud sıfır-CI testi);
  2. təsadüfi-zaman (əvvəlki artım);
  3. tək-feature qaydası — sabit, tənzimlənməyən RSI 30/70 reversal
     qaydası (`_single_feature_rsi_reversal_raw_returns`);
  4. əvvəlki qəbul edilmiş namizəd — eyni hipotez üzrə qlobal (bütün
     sessiyalar üzrə) ən son `accepted_for_shadow` namizədlə müqayisə
     (`get_latest_accepted_candidate_for_hypothesis`).
  Namizəd indi bütün 4 baseline-ı keçməlidir ki, `accepted_for_shadow`
  olsun. `BACKTEST_VERSION 1.4.0`. Backend `368 passed`.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 3/4, `PROJECT_ROADMAP.md`-dən)

- Baseline müqayisəsi tamamlandı (4/4) — bu bölmə üzrə açıq iş qalmadı.
- `blocked_by_data_quality` lifecycle vəziyyəti — replay sessiyasının
  keyfiyyət hesabatında critical tapıntı varsa namizədi bloklasın.
- Phase 9 sxeminin davamı (nəzəri portfolio/risk cədvəlləri) — yalnız
  istifadəçi ayrıca istəsə, çünki hələ real çağıranı yoxdur.
- Job-queue-nun frontend səthi — yalnız istifadəçi ayrıca istəsə.

## Vizual yoxlama qeydi

Tamamlandı (2026-08-05): Pattern namizədi bölməsinin tam dövrü canlı
brauzerdə uğurla yoxlanıldı; heç bir konsol xətası olmadı. Real bazaya
toxunulmadı. Ətraflı: `docs/status/CURRENT_STATE.md`.

Bu sessiyanın sonrakı bütün artımları (job-queue, multiple-testing, Phase 9
skeleti, 4 baseline) yalnız backend testləri ilə yoxlanıldı; frontend-ə
toxunulmadığı üçün canlı brauzerdə ayrıca vizual sınaq mənasız olardı.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
