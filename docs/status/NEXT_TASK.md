# ESAS Platform — Növbəti tapşırıq

Status: BLOCKED — növbəti addım seçilməyib, istifadəçi təsdiqi tələb olunur
Prioritet: —
Mərhələ: Phase 3/4-ün qalan maddələri

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
  Frontend toxunulmayıb (istifadəçi qərarı: hələlik lazım deyil).
- **Multiple-testing reyestri əlavə edildi** (commit `76e2e13`, push
  edilib, CI yaşıl): `evaluated → accepted_for_shadow` qərarı eyni replay
  sessiyasında sınanan bütün backtest-lərin sayına görə Bonferroni ailəvi
  xəta düzəlişi tətbiq edir.
- **Phase 9 SHADOW: run manifest + append-only event reyestri skeleti**
  (commit `404922a`, push edilib, CI yaşıl). **Bu, canlı SHADOW sistemi
  DEYİL** — Phase 5-8 yoxdur, heç bir istehsalat kodu bu cədvəllərə
  yazmır. Yalnız persistence sxemi + iki DB-səviyyəli struktur invariantı.
  API əlavə edilmədi (real çağıran yoxdur).
- **Backtest v1-ə təsadüfi-zaman baseline müqayisəsi əlavə edildi** (hələ
  commit edilməyib) — Phase 3/4-ün "Baseline və müqayisə" tələbindən
  yalnız bu bir baseline (istifadəçi ilə həcm razılaşdırıldı; no-signal
  artıq örtülü var idi, tək-feature və əvvəlki-namizəd müqayisəsi hələ
  yoxdur). Namizədin orta gəliri indi HƏM sıfırı, HƏM DƏ eyni bar
  seriyasından seed-lənmiş (deterministik) təsadüfi girişlərin ortasını
  keçməlidir ki, `accepted_for_shadow` olsun — əks halda "sadəcə bazar
  dreyfini tutur" riski `rejected`-ə aparır. Bonferroni düzəlişi ilə
  qarşılıqlı işləyir (düzəliş baseline yoxlamasını gizlədə bilməz).
  `BACKTEST_VERSION` `1.3.0`-a qalxdı. Backend `356 passed`.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 3/4, `PROJECT_ROADMAP.md`-dən)

- Baseline müqayisəsinin qalan hissəsi: tək-feature qaydası (məs. mövcud
  `rsi_regime_observation`-dan sadə hədd qaydası) və əvvəlki qəbul edilmiş
  namizədlə müqayisə.
- `blocked_by_data_quality` lifecycle vəziyyəti — replay sessiyasının
  keyfiyyət hesabatında critical tapıntı varsa namizədi bloklasın.
- Phase 9 sxeminin davamı (nəzəri portfolio/risk cədvəlləri) — yalnız
  istifadəçi ayrıca istəsə, çünki hələ real çağıranı yoxdur.

## Vizual yoxlama qeydi

Tamamlandı (2026-08-05): Pattern namizədi bölməsinin tam dövrü canlı
brauzerdə uğurla yoxlanıldı; heç bir konsol xətası olmadı. Real bazaya
toxunulmadı. Ətraflı: `docs/status/CURRENT_STATE.md`.

Job-queue, multiple-testing, Phase 9 skeleti və baseline müqayisəsi
artımları (bu sessiya) yalnız backend testləri ilə yoxlanıldı; frontend-ə
toxunulmadığı üçün canlı brauzerdə ayrıca vizual sınaq mənasız olardı.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
