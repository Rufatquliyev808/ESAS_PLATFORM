# ESAS Platform — Növbəti tapşırıq

Status: BLOCKED — növbəti addım seçilməyib, istifadəçi təsdiqi tələb olunur
Prioritet: —
Mərhələ: Phase 3 (statistik analiz) — Phase 4-ün namizəd lifecycle-ı əsasən tamamlanıb

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
- **`blocked_by_data_quality` lifecycle vəziyyəti tətbiq edildi** (commit
  `4e46f0f`, push edilib, CI yaşıl) — namizədin ilk backtest cəhdindən
  əvvəl replay sessiyasının keyfiyyət hesabatı yoxlanılır; `critical_count
  > 0`-dırsa namizəd `evaluated`-ə deyil, `blocked_by_data_quality`-yə
  keçir (API `409`).
- **`invalid_leakage` lifecycle vəziyyəti tətbiq edildi** (commit
  `2753fcc`, push edilib, CI yaşıl) — backtest v1-ə üst-üstə düşən tarixi
  hadisələr üçün purge/embargo əlavə edildi (bütün namizədlər üçün,
  statistik doğruluğu artırır); əgər xam siqnal kifayət idi (`≥30`) amma
  purge onu `30`-dan aşağı salıbsa, namizəd `insufficient_evidence`-ə
  deyil `invalid_leakage`-ə keçir.
- **Phase 9 SHADOW: nəzəri portfolio/risk ledger (section 6)** (commit
  `a502a70`, push edilib, CI yaşıl) — `shadow_theoretical_positions`
  cədvəli (migration `0010`), mövqe-səviyyəli risk limitləri. Gündəlik
  itki/drawdown şüurlu şəkildə kənarda saxlanılıb.
- **Phase 9 SHADOW-a admin API + frontend əlavə edildi** (commit
  `c380d08`, push edilib, CI yaşıl) — istifadəçinin "çağıranı düzəldək" tələbinə cavab: 12 yeni
  qorunan endpoint (`/api/v2/shadow-runs...`) + yeni `shadow-runs-panel.tsx`
  bölməsi (NƏZƏRİDİR banneri ilə). Canlı brauzerdə real qərar generatoru
  olmadan (əl ilə, admin kimi) tam sınandı: run yaradıldı → başladıldı →
  risk limiti ilə mövqə düzgün bloklandı → mövqə bağlandı → event qeydə
  alındı → tamamlandı. Sınaq zamanı real bug tapılıb düzəldildi (risk-blok
  xəbərdarlığı `loadDetail()`-un öz sıfırlanması ilə görünmədən itirdi).
  Backend `404 passed`, frontend lint/build/`11/11` test təmiz. Real
  bazaya toxunulmadı.
- **Phase 3 statistik analiz başladı: pəncərə/resampling təməli + SA-001
  gəlir seriyası** (commit `7467f95`, push edilib, CI yaşıl) — Phase 4-ün namizəd
  lifecycle-ı əsasən tamamlandığı üçün istifadəçinin təsdiqi ilə Phase 3-ə
  keçildi. `bars.py`-a `S1`/`S10` (1s/10s) pəncərələri əlavə edildi (əvvəllər
  yalnız `M1/M5/M15/H1`). Yeni `return_series.py`: hər pəncərənin öz ilk/son
  etibarlı mid-price-ı ilə log-return (tək-tick pəncərə return yaratmır),
  say/orta/median/std/min/maks/p05-p95 statistikası,
  `n_valid<minimum_window_returns` olduqda `insufficient_data`. Yeni qorunan
  `GET .../statistical-analysis` endpoint-i (mövcud `technical-analysis`
  nümunəsi ilə, dataset-drift qorumalı). Async job/persistence resursu
  (müqavilənin `POST /api/v2/statistical-analyses`-i) və frontend hələ
  əlavə edilmədi — ilk artım qəsdən kiçik saxlanıldı. Backend `418 passed`.
- **Phase 3 SA-002 (volatilite) — pəncərə range-i, mütləq return, robust MAD**
  (commit `1173d53`, push edilib, CI yaşıl) — SA-001-in birbaşa davamı. Yeni `volatility.py`:
  `window_range_absolute`/`window_range_relative` (`high-low`, bütün
  bar-lar), `window_log_return_abs` (yalnız return-eligible pəncərələr),
  `robust_mad`. Tick-to-tick return std-i (contract-ın ayrıca bəndi) qəsdən
  kənarda saxlanıldı — yeni xam-tick keçidi tələb edir, ayrıca kiçik artım
  kimi planlaşdırılıb. `minimum_window_returns` parametri orkestrasiya
  qatında ümumi `minimum_sample_size`-a çevrildi.
  `STATISTICAL_ANALYSIS_API_VERSION 1.1.0`.
- **Əsas ekrana canlı indikator konsensusu paneli əlavə edildi** (hələ
  commit edilməyib) — istifadəçinin TradingView-un texniki analiz
  widget-inə bənzər görünüş istəyinə cavab, öz hesablamamızla (research-safe
  etiketləmə ilə). Yeni `indicator_consensus.py` (RSI+EMA-dan Bullish/
  Bearish/Neytral təsnifatı, TradingView-un 16 göstəricisinə qarşı qəsdən
  2), yeni `live_analysis.py` (replay sessiyası TƏLƏB ETMİR, canlı pəncərə,
  `reproducible: false`), yeni `GET /api/v2/live-technical-summary`
  endpoint-i, yeni `live-technical-summary-panel.tsx` ("Nəticələr" əsas
  ekranında, "TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT TÖVSİYƏSİ DEYİL" banneri
  ilə). Canlı brauzerdə tam sınandı (real bazaya toxunmadan). Backend
  `435 passed`, frontend lint/build/`12/12` test təmiz.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 3/4, `PROJECT_ROADMAP.md`-dən)

- Baseline müqayisəsi tamamlandı (4/4).
- `blocked_by_data_quality` tamamlandı.
- `invalid_leakage` tamamlandı (purge/embargo əsaslı).
- Backtest v1-in son vəziyyət maşını indi tamdır: `draft → registered →
  evaluated → accepted_for_shadow | rejected | insufficient_evidence |
  invalid_leakage | blocked_by_data_quality → archived`.
- Phase 9: manifest + event + portfolio skeleti VƏ admin API/frontend
  tamamlandı. Real bazaya migration `0010` hələ tətbiq edilməyib (ayrıca
  icazə tələb olunacaq, real istifadəyə başlanmaq istənsə). Qalan
  bölmələr (champion/challenger müqayisə mühərriki section 7,
  kəsinti/restart section 8) — yalnız istifadəçi ayrıca istəsə, çünki hələ
  real qərar generatoru (Phase 5-8) yoxdur.
- Job-queue-nun frontend səthi — yalnız istifadəçi ayrıca istəsə.
- **Phase 3 statistik analiz davam edir** (pəncərə/resampling təməli +
  SA-001 gəlir seriyası + SA-002 pəncərə volatilitesi, təfərrüat yuxarıda).
  Növbəti namizədlər: SA-002-nin qalan hissəsi (tick-to-tick return std-i —
  yeni xam-tick keçidi tələb edir), SA-003 (spread davranışı), SA-004
  (tick sürəti), SA-005 (tick-volume), SA-006 (sessiya müqayisəsi —
  versiyalanmış təqvim tələb edir), SA-007 (bazar rejimi namizədləri).
  Sonra: async job/persistence resursu (`POST /api/v2/statistical-analyses`)
  və frontend paneli.
- **Əsas ekranın canlı indikator konsensusu paneli tamamlandı** (RSI+EMA,
  təfərrüat yuxarıda). Namizədlər: konsensusu daha çox indikatorla
  genişləndirmək (Stochastic, CCI, ADX, MACD, əlavə MA dövrləri) — yalnız
  istifadəçi ayrıca istəsə.

## Vizual yoxlama qeydi

Tamamlandı (2026-08-05): Pattern namizədi bölməsinin tam dövrü canlı
brauzerdə uğurla yoxlanıldı; heç bir konsol xətası olmadı. Real bazaya
toxunulmadı. Ətraflı: `docs/status/CURRENT_STATE.md`.

2026-08-06: real production bazanın `0005`-`0009` migrasiyaları istifadəçi
ilə birlikdə canlı brauzerdə aşkarlanan `HTTP 500` xətasından yola çıxaraq
tətbiq edildi və doğrulandı. Eyni gün, Phase 9 admin panelinin tam dövrü
də (real bazaya toxunmadan, birdəfəlik test backend/frontend ilə) canlı
brauzerdə sınandı. Yenə eyni gün, əsas ekranın yeni canlı indikator
konsensusu paneli (birdəfəlik test backend/frontend, sintetik GOLD
tick-ləri ilə) canlı brauzerdə sınandı — düzgün RSI/EMA/konsensus
nəticələri göstərildi. Real production backend/frontend (8000/3000)
sınaq boyu toxunulmadan işlədi.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
