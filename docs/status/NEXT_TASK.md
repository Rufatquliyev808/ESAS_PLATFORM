# ESAS Platform — Növbəti tapşırıq

Status: BLOCKED — növbəti addım seçilməyib, istifadəçi təsdiqi tələb olunur
Prioritet: istifadəçi 2026-08-09-da Phase 3→4→7→8→9→10 prioritet sırasını verdi (real ticarətə hazır analiz sistemi). Phase 3/4 artıq tamamlanıb (aşağıda təsdiqlənib).
Mərhələ: Phase 5 (Visual AI) davam edir — renderer + dataset lineage/manifest + label hesablanması + eksperiment qeydiyyatı/API (indi real spec saxlanması ilə) + frontend paneli tamamlanıb, dataset materiallaşdırma/model təlimi hələ yoxdur

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
- **Canlı konsensus 5 yeni osilatorla genişləndirildi** (hələ commit
  edilməyib) — istifadəçinin "Osilatorları genişlət" seçiminə cavab. Yeni
  `oscillators.py` (`indicators.py`-a toxunmadan): Stochastic %K(14,3),
  CCI(20), Williams %R(14), MACD(12,26,9), ADX(14)+DI/-DI (Wilder üsulu,
  `indicators.py`-dəki ATR/RSI hamarlama nümunəsi ilə eyni). Osilator sayı
  1-dən (yalnız RSI) 6-ya çıxdı. `CONSENSUS_VERSION 2.0.0`,
  `LIVE_ANALYSIS_API_VERSION 1.1.0`. Frontend-də hər qrup üçün detallı
  cədvəl (göstərici/dəyər/meyl) əlavə edildi. Canlı brauzerdə tam sınandı
  (real bazaya toxunmadan) — 6 osilator da düzgün göründü. Backend
  `449 passed`, frontend lint/build/`12/12` test təmiz.
- **Likvidlik-səviyyəsi reaksiya statistikası (yalnız backend)** (hələ
  commit edilməyib) — istifadəçinin çox-taymfreym likvidlik + reaksiya
  statistikası + "özü öyrənən sistem" + canlı siqnal + jurnal istəyinə
  cavab. **Canlı "alış/satış" dili platformanın prinsipinə zidd olduğu
  üçün rədd edildi** — tədqiqat dili ilə qurulacaq (yuxarı/aşağı meyl,
  tarixi faiz), və ilk addım kimi yalnız backend/backtest statistikası
  seçildi. `bars.py`-a `M30/H4/D1` əlavə edildi. Yeni
  `liquidity_reaction.py`: mövcud `liquidity_sweep.py`-ın pool-larını
  girişi kimi qəbul edir, hər toxunuşu `reversed`/`continued`/`ambiguous`
  təsnifləndirir (purge/embargo ilə), `buy_side`/`sell_side` üçün ayrı
  95% etibar intervallı reversed-faiz statistikası. Backend `462 passed`.
- **Likvidlik sisteminin qalan 3 addımı (çox-taymfreym, özü-öyrənən
  seqmentasiya, jurnal)** (commit `11f47ee`, push edilib, CI yaşıl) —
  istifadəçinin "1-dən
  başlayaq, soruşma, hamısını edək" tapşırığına cavab, ardıcıl təsdiqsiz
  tamamlandı. Yeni `liquidity_reaction_segments.py` (RSI/Stochastic/ADX
  şərtləri üzrə Bonferroni-düzəlişli seqment statistikası), yeni
  `liquidity_overview.py` (4 taymfreymin orkestrasiyası, trend + ən yaxın
  səviyyələr + reaksiya + seqmentlər), yeni `GET
  /api/v2/liquidity-overview` endpoint-i, yeni
  `liquidity-overview-panel.tsx` ("Nəticələr" ekranında, 90s polling,
  jurnal daxil — jurnal üçün yeni backend infrastrukturu tələb olunmadı,
  mövcud `ReactionEvent`-lər artıq bu məlumatı daşıyır). Canlı brauzerdə
  tam sınandı (15 günlük ossilasiya edən sintetik data, real bazaya
  toxunmadan). Backend `472 passed`, frontend lint/build/`13/13` test
  təmiz.
- **Tarixi hərəkət diapazonu (excursion range)** (commit `e30f22a`, push
  edilib, CI yaşıl) —
  istifadəçi "gələcəyi proqnoz etmək" istəyini bildirdi ("filan nöqtədən
  filan nöqtəyə qədər gözlənilir"); eyni sərhəd izahı təkrarlandı, tarixi
  (backward-looking) aralıq seçildi. Yeni `ExcursionDistribution` — hər
  tərəf/nəticə üçün median/p25/p75/p90 (n≥30). Frontend-də hər cümlənin
  sonunda məcburi "Bu, gələcək proqnoz deyil" xəbərdarlığı (source-text
  guard testi ilə kilidlənib). Canlı brauzerdə tam sınandı. Backend
  `474 passed`, frontend lint/build/`13/13` test təmiz.
- **Phase 3 SA-003 — spread davranışı** (commit `ae03635`, push edilib, CI
  yaşıl) — istifadəçi əsas Phase 3 xəttinə qayıtmağı istədi. Yeni
  `spread.py` (mövcud `bars.py` spread_min/max/mean-dan, yeni xam-tick
  keçidi tələb olunmadı) — say/orta/median/std/min/maks/p05/p25/p75/p95/p99
  (mütləq və nisbi bps). `spread_points` şüurlu buraxılıb (metadata
  yoxdur). `statistical_analysis.py`-a inteqrasiya,
  `STATISTICAL_ANALYSIS_API_VERSION 1.2.0`. Backend `480 passed`.
  Frontend toxunulmayıb (bu endpoint-in hələ UI-si yoxdur).
- **Phase 3 SA-004 — tick sürəti/interval** (commit `243553a`, push edilib,
  CI yaşıl) — istifadəçinin "SA-004 (tövsiyə)" seçimi ilə. Yeni
  `tick_rate.py` — Phase 3-də İLK dəfə xam tick-lər üzərində birbaşa
  işləyən modul (əvvəlki SA-001/002/003 yalnız `bars.py`-ın artıq qurduğu
  bar-lar üzərində işləyirdi). `bars.py`-ın bid/ask etibarlılıq filtrini
  QƏSDƏN tətbiq etmir — tick sürəti qiymət keyfiyyətindən deyil, feed-in
  özündən asılıdır. Say/saniyə başına tick (pəncərə üzrə, `bars.py` ilə
  eyni epoch-aligned pəncərə tərifi), ardıcıl tick interval-larının
  median/p95/p99/maks-ı (bütün aralıq üzrə, pəncərə-üzrə deyil),
  eyni-timestamp tick sayı, boş/dolu/ümumi pəncərə sayı (hər zaman
  göstərilir, minimum_sample həddindən asılı olmadan). `statistical_
  analysis.py`-a inteqrasiya (ikinci `iter_tick_batches` keçidi ilə), yeni
  `tick_rate` sahəsi, `STATISTICAL_ANALYSIS_API_VERSION 1.2.0 → 1.3.0`.
  Yeni `test_tick_rate.py` (8 test). Tam backend regressiyası:
  `488 passed`. Frontend toxunulmayıb.
- **Phase 3 SA-002 tamamlanması — tick-to-tick return std-i** (hələ commit
  edilməyib) — SA-004/005-in açdığı xam-tick oxuma formasını istifadə
  edərək əvvəllər qəsdən kənarda saxlanmış SA-002 hissəsi tamamlandı.
  `volatility.py`-ın `compute_volatility()`-i indi `ticks`/`start_at`/
  `end_at` də qəbul edir, yeni `tick_return` sahəsi (tick-to-tick,
  pəncərəsiz mid-price log-return paylanması) qaytarır. `bars.py`-ın
  mid-price etibarlılıq filtri (bid/ask müsbət, ask≥bid) tətbiq edilir —
  tick_rate/tick_volume-dan fərqli olaraq bu, qiymət seriyasıdır.
  `VOLATILITY_VERSION 1.0.0 → 1.1.0`. `statistical_analysis.py`-a
  inteqrasiya (dördüncü `iter_tick_batches` keçidi),
  `STATISTICAL_ANALYSIS_API_VERSION 1.4.0 → 1.5.0`. `test_volatility.py`
  yeniləndi + 4 yeni test. Tam backend regressiyası: `500 passed`.
  Frontend toxunulmayıb.
- **Phase 3 SA-005 — tick-volume/flags** (commit `625ab98`, push edilib,
  CI yaşıl) —
  SA-004-ün davamı, eyni xam-tick oxuma formasını paylaşır. Yeni
  `tick_volume.py`: mövcud `volume` sahəsi MT5 tick-volume kimi
  etiketlənir (real birja həcmi deyil). `tick_volume` (hər tick-in xam
  volume dəyərinin paylanması, sıfır daxil) + ayrıca `n_zero_volume`/
  `n_positive_volume`; `window_volume_sum` (dolu pəncərə üzrə cəm, bir
  nöqtə/pəncərə, boş pəncərə sıfırla doldurulmur); `flag_combinations`
  (xam müşahidə olunan `flags` dəyərləri + sayı, ŞÜURLU ŞƏKİLDƏ deşifr
  edilmədən — versiyalanmış MT5 bit mapping yoxdur); `version_segments`
  (module_version/event_version üzrə say). `statistical_analysis.py`-a
  inteqrasiya (üçüncü `iter_tick_batches` keçidi), yeni `tick_volume`
  sahəsi, `STATISTICAL_ANALYSIS_API_VERSION 1.3.0 → 1.4.0`. Yeni
  `test_tick_volume.py` (9 test). Backend `496 passed`.
- **Phase 3 SA-002 tamamlanması — tick-to-tick return std-i** (commit
  `ef06731`, push edilib, CI yaşıl) — SA-004/005-in açdığı xam-tick oxuma
  formasını istifadə edərək əvvəllər qəsdən kənarda saxlanmış SA-002
  hissəsi tamamlandı. `volatility.py`-ın `compute_volatility()`-i indi
  `ticks`/`start_at`/`end_at` də qəbul edir, yeni `tick_return` sahəsi
  (tick-to-tick, pəncərəsiz mid-price log-return paylanması) qaytarır.
  `bars.py`-ın mid-price etibarlılıq filtri tətbiq edilir.
  `VOLATILITY_VERSION 1.0.0 → 1.1.0`. `STATISTICAL_ANALYSIS_API_VERSION
  1.4.0 → 1.5.0`. Backend `500 passed`.
- **Phase 3 SA-007 — bazar rejimi namizədləri** (commit `5037783`, push
  edilib, CI yaşıl) —
  istifadəçinin seçimi: SA-006 (sessiya müqayisəsi) əvəzinə SA-007
  (versiyalanmış təqvim tələb etmir, artıq tamamlanmış SA-001/002/003
  üzərində qurulur, yeni xam-tick keçidi tələb etmir). Yeni
  `regime_candidates.py`: hər pəncərəni 4 feature üzrə (volatilite
  səviyyəsi, spread səviyyəsi, tick sürəti — hamısı dataset-daxili median
  split ilə low/high, universal/annualized hədd YOXDUR; return
  istiqaməti — up/down/flat, tək-tick pəncərə üçün unknown) neytral,
  leksikoqrafik sıralı `regime_N` etiketinə təsnifləndirir (iqtisadi ad
  YOX — müqavilə bunu açıq tələb edir). `data_quality_status` real
  `create_replay_quality_report()` çağırışından (Phase 4-ün
  `blocked_by_data_quality` qapısında istifadə olunan eyni funksiya) gəlir,
  bütün pəncərələrə eyni tətbiq olunur (per-pəncərə keyfiyyət izlənmir).
  `statistical_analysis.py`-a inteqrasiya (yeni `regimes` sahəsi, yeni
  keyfiyyət-hesabatı çağırışı, yeni tick keçidi YOX),
  `STATISTICAL_ANALYSIS_API_VERSION 1.5.0 → 1.6.0`. Yeni
  `test_regime_candidates.py` (7 test — əl ilə yoxlanmış 4-kvadrant
  fixture, median split, leksikoqrafik regime təyini). Tam backend
  regressiyası: `507 passed`. Frontend toxunulmayıb.
- **Phase 3 SA-006 — sessiya müqayisəsi (təqvim-yoxdur deqradasiya
  rejimi)** (commit `78ad3ab`, push edilib, CI yaşıl) — Phase 3-ün SA-001-SA-007
  müqaviləsini tamamlayır. Müqavilə versiyalanmış simvol/broker təqvimi
  (timezone, DST, həftəsonu/bayram, üst-üstə düşən sessiya prioriteti)
  tələb edir, AMMA təqvim olmadıqda açıq deqradasiya rejimi TƏYİN EDİR:
  yalnız UTC saat dilimləri, əsla "London/NY" kimi adlandırılmadan,
  `calendar_unavailable` işarəsi ilə. Platformada belə təqvim yoxdur, ona
  görə bu artım məhz bu deqradasiya rejimini tətbiq edir (uydurma təqvim
  QURULMADI). Yeni `session_comparison.py`: pəncərələri `start_at`-ın xam
  UTC saatına (0-23) görə qruplaşdırır, hər qrup üçün return orta/median/
  std + orta üzərində 95% etibar intervalı, nümunə sayı, orta nisbi range
  (volatilite proksi) — hamısı artıq mövcud `bars.py`/`return_series.py`
  nəticəsindən, yeni xam-tick keçidi YOX. `calendar_unavailable: true` +
  məhdudiyyət mətni HƏMİŞƏ cavabda olur. `statistical_analysis.py`-a
  inteqrasiya (yeni `sessions` sahəsi), `STATISTICAL_ANALYSIS_API_VERSION
  1.6.0 → 1.7.0`. Yeni `test_session_comparison.py` (9 test). Tam backend
  regressiyası: `516 passed`. Frontend toxunulmayıb.

**Phase 3-ün SA-001-SA-007 müqaviləsi indi tam əhatə olunub** (SA-006
təqvim-yoxdur deqradasiya rejimində) **VƏ frontend paneli əlavə edildi**
(commit `9930dd6`, push edilib, CI yaşıl) — istifadəçinin "frontend panel
(tövsiyə)" seçimi ilə. Yeni `statistical-analysis-panel.tsx`: "Araşdırma"
qrupunda yeni "Statistik analiz" bölməsi (mövcud replay-session-seçimi
axını ilə), form (vaxt çərçivəsi + minimum nümunə) + 7 SA bölməsinin hər
biri üçün kart (status/n/orta/median/std/aralıq). Canlı brauzerdə tam
sınandı (birdəfəlik scratch backend/DB, 1,100 sintetik tick, real replay
sessiyası tamamlanana qədər işlədilib): M5-də (11 pəncərə) pəncərə-əsaslı
bölmələr düzgün `insufficient_data`, tick-səviyyəli metriklər (tick-return,
interval) öz nümunəsi ilə `completed`; M1-də (55 pəncərə) bütün 7 bölmə
`completed`, real dəyərlər (8 rejim, 100%-ə cəmlənən nisbətlər, dəqiq
flag/UTC-saat cədvəlləri). Konsol xətası yox, sorğu storm-u yox. Yeni
`statistical-analysis-ui.test.mjs`. Frontend: lint təmiz, `14/14` test,
build uğurlu.

**Async job/persistence resursu** (`POST /api/v2/statistical-analyses`)
(commit `af8eb7c`, push edilib, CI yaşıl) — istifadəçinin seçimi (SA-001-SA-007
tamamlandıqdan sonra). İcrası zamanı real maneə aşkarlandı: `analysis_jobs`
(migration `0007`) real bazaya artıq tətbiq edilib, `job_type` CHECK-i
yalnız `pattern_candidate_backtest`-i qəbul edir, migration sistemi
`DROP`/`DELETE`/`UPDATE` qadağan etdiyi üçün CHECK-i genişləndirmək
mümkün deyil. İstifadəçiyə bildirildi, "yeni ayrıca cədvəl + repository-ni
ümumiləşdir" seçildi. Yeni migration `0011_statistical_analysis_jobs.sql`
(eyni struktur, `job_type='statistical_analysis'`). `analysis_job_
repository.py` cədvəl-ad-marşrutlaşdırmasına ümumiləşdirildi (job_id
prefiksi ilə: `job_` — pattern-candidate, dəyişməz; `saj_` — statistical-
analysis) — job_id-yalnız funksiyalar (`get_job`, `send_heartbeat`,
`complete_job`, `fail_job`, `request_cancel`) əlavə sorğu/parametr
olmadan düzgün cədvələ yönləndirilir. Yeni worker handler
(`_run_statistical_analysis_job`), yeni `StatisticalAnalysisJobRequest`
modeli, 3 yeni endpoint (mövcud pattern-candidate-backtest job
endpoint-lərinin eyni nümunəsi: `POST .../statistical-analysis-jobs`
202, `GET .../statistical-analysis-jobs/{job_id}`, `POST
.../{job_id}/cancel`). **Yolüstü tapılıb düzəldilən bug:** mövcud
sinxron `GET .../statistical-analysis` endpoint-inin `timeframe`
regex-i köhnə idi (yalnız `S1|S10|M1|M5|M15|H1`, `M30/H4/D1` YOX) —
`bars.py`-ın faktiki dəstəyinə uyğunlaşdırıldı (SA-004-dən bəri və yeni
frontend panelinin seçicisi bu 3 dəyəri artıq təklif edirdi, 422 verirdi).
`test_migration_runner.py` yeniləndi (yeni migration sayı). `test_
analysis_job_repository.py`-a 5 yeni test. Yeni `test_statistical_
analysis_jobs_api.py` (7 test). Tam backend regressiyası: `528 passed`.
Real işləyən production backend-də restart-dan sonra yoxlanıldı: yeni
route `401` qaytarır (`404` yox) — kodun düzgün yükləndiyini təsdiqləyir.
Frontend toxunulmayıb (backend-only, API-səviyyəli artım).

**2026-08-09: migration `0010` VƏ `0011` real bazaya tətbiq edildi**
(istifadəçinin açıq təsdiqi ilə, `tools/phase2-migrate-production.py
--allow-production`) — ehtiyat nüsxə + doğrulama (`tick_events`/
`replay_sessions` sayları dəyişməz, `quick_check=ok`), real
backend/frontend yenidən başladıldı, yeni job endpoint-i `401` (`no such
table` YOX) qaytardı. Kod dəyişikliyi deyil, commit tələb olunmadı.

**Job-queue-nun frontend səthi** (commit hələ göndərilməyib) —
istifadəçinin seçimi (Phase 3 tam bitdikdən sonra). Yeni
`async-job-panel.tsx`: ortaq `useAsyncJob()` hook-u (idempotency key ilə
yaratma, 2s aralıqla `GET .../{job_id}` poll, ləğv, `onCompleted` —
useEffect-dən DEYİL, birbaşa poll/create handler-indən çağırılır ki,
"effect içində setState" lint qaydasına toxunmasın) + `JobStatusBadge` +
`isJobCancellable()`. `statistical-analysis-panel.tsx`-ə "Job kimi
başlat (asinxron)" düyməsi (nəticə eyni `setResult`-a axır, ayrıca
görünüş yoxdur). `pattern-candidates-panel.tsx`-ə `BacktestJobCell`
sub-komponenti (cədvəl sətri başına bir hook nüsxəsi) — "Job kimi
backtest et" düyməsi, tamamlandıqda eyni `backtests` state-i yenilənir
və `loadRegistered()` çağırılır (sync yolla eyni nəticə). **Canlı
brauzerdə tam sınandı** (scratch backend port 8002 + scratch DB,
scratch frontend port 5173 — port 5174 CORS allow-list-də olmadığı üçün
rədd edildi, real 8000/3000 toxunulmadan): həm pattern-candidate
backtest job-u (`job_` prefiksi) həm statistical-analysis job-u (`saj_`
prefiksi) tam icra olundu, nəticələr sync yol ilə eyni render-ə axdı,
konsol xətası yox. Yeni `async-job-panel-ui.test.mjs` (3 test).
Frontend: lint təmiz, `17/17` test, build uğurlu. Backend
toxunulmayıb.

**PROJECT_ROADMAP.md faktiki vəziyyətə uyğunlaşdırıldı** (commit
`348717e`, push edilib, CI yaşıl) — Phase 3 və Phase 4-ün checklist-ləri
COMPLETED işarələndi (əvvəllər hamısı `[ ]` idi, faktiki iş çoxdan
bitmişdi). Növbəti böyük mərhələ (Phase 5, Visual AI) qeyd edildi,
istifadəçinin ayrıca təsdiqini gözləyir.

**Canlı konsensus panelinin hərəkətli ortalamaları genişləndirildi**
(commit `7a6f1b7`, push edilib, CI yaşıl) — istifadəçinin seçimi
(Phase 5-dən əvvəl kiçik namizəd). Yeni `backend/app/analysis/moving_averages.py`:
`calculate_sma()` (yeni) + `build_moving_average_set()` (4 dövr ×
SMA/EMA = 8 seriya; `indicators.py`-a TOXUNMUR, `calculate_ema()`-nı
birbaşa çağırır, təkrar EMA implementasiyası yoxdur).
`indicator_consensus.py` indi 8 seriyanı təsnifləndirir (əvvəllər 1),
`CONSENSUS_VERSION 2.0.0 → 3.0.0`. `live_analysis.py`-a yeni
`moving_averages` sahəsi, `LIVE_ANALYSIS_API_VERSION 1.1.0 → 1.2.0`.
Frontend-də `live-technical-summary-panel.tsx` artıq generic idi (siyahı
üzrə render edir), yalnız `indicatorLabel()`-ə `sma.close.N` üçün format
əlavə edildi. **Canlı brauzerdə tam sınandı** (scratch backend port 8003
+ 1,200 sintetik tick 60 dəqiqəlik, scratch frontend port 5173, real
8000/3000 toxunulmadan): bütün 8 sətir real dəyərlərlə göründü, 8/8
yuxarı meyl (sintetik uptrend-ə uyğun), konsol xətası yox, polling 5s
tempində qaldı (storm yox). Yeni `test_moving_averages.py` (8 test),
`test_indicator_consensus.py` yenidən yazıldı (8-seriyalı fixture).
`test_live_technical_summary_api.py` yeniləndi. Tam backend
regressiyası: `537 passed`. Frontend: lint təmiz, `17/17` test, build
uğurlu.

**Platform-wide audit (istifadəçinin "ümumi checklist" tapşırığı)** (docs
commit `83c5f91` + npm audit fix commit `297377e`, hər ikisi push edilib,
CI yaşıl) — backend (537 test), frontend (lint/build/`17/17` test),
real production DB (migration `0001`-`0011`, `quick_check=ok`) və real
xidmətlər (8000/3000, hər ikisi `200`) yoxlanıldı, hamısı sağlam.
`TODO/FIXME/XXX/HACK` axtarışı təmiz. Tapılıb düzəldilən: (1)
`PHASE_2_WORKER_SCHEDULER_CONTRACT.md` və
`PHASE_3_STATISTICAL_ANALYSIS_CONTRACT.md`-in köhnə "DESIGN READY — NOT
IMPLEMENTED" statusu → IMPLEMENTED-ə düzəldildi; (2)
`SESSION_HANDOFF.md`/`NEXT_TASK.md`-də artıq push edilmiş işlər üçün
köhnə "hələ commit edilməyib" işarələri düzəldildi; (3) izlənilməyən,
köhnə `.tmp/` qovluğu (19MB) `.gitignore`-a əlavə edildi; (4) `npm audit`
— production asılılıqlarında (`next`/`postcss`/`sharp`) 4 HIGH boşluq
tapıldı, `next` yalnız `16.2.6 → 16.3.0` (kiçik, eyni-major yüksəliş,
əvvəlcə düşünüldüyü kimi major/breaking DEYİL) + təhlükəsiz transitive
düzəlişlərlə (`js-yaml`/`fast-uri`/`brace-expansion`/`@babel/core`) həll
edildi, production asılılıqları indi `0 boşluq`. Canlı yoxlandı: real
frontend (3000) yenidən başladıldı, login səhifəsi düzgün render olundu,
konsol xətası yox.

**Phase 5 (Visual AI) başladı — deterministik kanonik qrafik renderi**
(commit `f4c8ce2`, push edilib, CI yaşıl) — istifadəçinin "phase 5"
seçimi, ilk addım kimi render (heç bir ML asılılığı yoxdur, tam
testlənə bilər). Yeni `backend/app/analysis/visual_render.py`: yalnız
Phase 4-ün bağlanmış barlarından PNG şam qrafiki, heç bir yeni asılılıq
(stdlib `zlib`/`struct`), `image_checksum` xam piksel bufer üzərində
(müqavilənin "eyni piksel checksum-u" tələbinə dəqiq uyğun).
`CanonicalImage` lineage/known_at/missing-data maskasını daşıyır. Yeni
`test_visual_render.py` (16 test). Tam backend regressiyası:
`553 passed`.

**Phase 5 — dataset lineage/manifest qatı** (commit `a736cc1`, push
edilib, CI yaşıl) — istifadəçinin "davam et" tapşırığı, renderin təbii
davamı. Yeni `backend/app/analysis/visual_dataset.py`: müqavilənin
lineage zəncirini (`sample_id → ... → split_id`) tətbiq edir;
`build_visual_sample()` (label DƏYƏRİ hesablanmır, qəsdən kənarda —
yalnız çağıranın verdiyini qeyd edir və səbəbiyyəti yoxlayır);
`assign_time_based_splits()` (zaman-əsaslı, TƏSADÜFİ DEYİL, sərhəd-kəsən
nümunələr purge edilir, səssiz silinmir); `build_dataset_manifest()`
(heç nə silinmir). Yeni `test_visual_dataset.py` (18 test). Tam backend
regressiyası: `571 passed`.

**Phase 5 — label hesablanması** (hələ commit edilməyib) —
istifadəçinin "davam et" tapşırığı, dataset lineage qatının davamı.
Yeni `backend/app/analysis/visual_label.py`: `compute_label()`
əvvəlcədən qeydə alınmış `LabelSpec` həddinə görə UP/DOWN/FLAT
təsnifatı, horizon tamamlanmayıbsa `INCOMPLETE_HORIZON`
(`visual_dataset.py`-ın `PENDING_HORIZON`-una bağlanır). Dataset-üzrə
optimallaşdırma məntiqi heç yerdə yoxdur (kod strukturu ilə qorunur).
Test zamanı tapılan float dəyirmiləşdirmə bug-ı (dəqiq sərhəd
dəyərləri) `1e-9` epsilon ilə düzəldildi. Yeni `test_visual_label.py`
(12 test). Tam backend regressiyası: `583 passed`. Bununla Phase 5-in
render→dataset→label əsas backend zənciri tamamlandı.

**Phase 5 — eksperiment qeydiyyatı/persistence API-si** (hələ commit
edilməyib) — istifadəçinin açıq təsdiqi (DB miqrasiyası tələb etdiyi
üçün əvvəlcə soruşuldu). Yeni migration `0012_visual_experiments.sql`
(`pattern_candidates`-in strukturunu təkrarlayır; `lifecycle_state`
CHECK-i TAM 14 vəziyyəti indi sadalayır — `analysis_jobs`
CHECK-blokundan çıxarılan dərs). Yeni
`visual_experiment_repository.py`: `register_visual_experiment()`
(yalnız DONDURULMUŞ konfiqurasiya, `experiment_id` deterministik
hash-lənir, təbii idempotent), `get_visual_experiment()`,
`archive_visual_experiment()`. Yeni `models/visual_experiment.py` + 3
endpoint (`POST/GET .../visual-experiments`, `POST .../archive`). Yeni
`test_visual_experiment_repository.py` (12 test) +
`test_visual_experiments_api.py` (10 test). Tam backend regressiyası:
`605 passed`. **Miqrasiya YALNIZ test bazasına tətbiq edildi, real
production bazaya YOX** — bu ayrıca açıq təsdiq tələb edəcək.

**Tam vəziyyət doğrulaması + spec saxlanması düzəlişi** (commit hələ
edilməyib — bax aşağı) — istifadəçi yeni sessiyada tam yoxlama tapşırığı
verdi (sənədlər, Git, testlər, real baza read-only). Hər şey təsdiqləndi,
2 problem tapıldı: canlı tick axını ~41.5 saat köhnəlib (MT5 Bridge
tərəfi, bu sessiyanın həll etmə səlahiyyətindən kənar),
`PROJECT_ROADMAP.md` Phase 5-i "PLANNED" göstərirdi (düzəldildi, commit
`71f67f0`). Sonra əvvəlki addımın açıq qalmış sualı həll edildi:
`register_visual_experiment()` indi real `RenderSpec`/`LabelSpec`
qəbul edir (əvvəllər ixtiyari mətn idi), ID-ni server tərəfdə hesablayır,
migration `0012`-yə `render_spec_json`/`label_spec_json` əlavə edildi
(hələ production-a tətbiq edilməyib, təhlükəsiz redaktə edildi).
Frontend forması real `horizon_bars`/threshold sahələrinə keçdi. Tam
backend regressiyası: `609 passed` (say dəyişmədi). Frontend: lint/build
təmiz, `18/18` test. Canlı brauzerdə yenidən sınandı.

**Phase 5 — frontend paneli** (hələ commit edilməyib) — istifadəçinin
"frontend panel (tövsiyə)" seçimi. Yeni `visual-experiments-panel.tsx`
+ naviqasiya bağlantısı. Wiring zamanı tapılan boşluq: siyahı endpoint-i
yox idi — `list_visual_experiments()` + `GET /api/v2/visual-experiments`
+ imzalı cursor əlavə edildi (4 yeni backend test, `609 passed`).
Canlı brauzerdə tam dövr (qeydiyyat → siyahı → arxivləşdirmə) sınandı,
real bazaya toxunulmadan. Frontend: lint/build təmiz, `18/18` test.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 3/4, `PROJECT_ROADMAP.md`-dən)

- Baseline müqayisəsi tamamlandı (4/4).
- `blocked_by_data_quality` tamamlandı.
- `invalid_leakage` tamamlandı (purge/embargo əsaslı).
- Backtest v1-in son vəziyyət maşını indi tamdır: `draft → registered →
  evaluated → accepted_for_shadow | rejected | insufficient_evidence |
  invalid_leakage | blocked_by_data_quality → archived`.
- Phase 9: manifest + event + portfolio skeleti VƏ admin API/frontend
  tamamlandı. Migration `0010` real bazaya 2026-08-09-da tətbiq edildi
  (əvvəllər kod/test bazalarında sınanmışdı). Qalan
  bölmələr (champion/challenger müqayisə mühərriki section 7,
  kəsinti/restart section 8) — yalnız istifadəçi ayrıca istəsə, çünki hələ
  real qərar generatoru (Phase 5-8) yoxdur.
- **Job-queue-nun frontend səthi tamamlandı** (`async-job-panel.tsx`,
  həm pattern-candidate-backtest həm statistical-analysis job-ları üçün,
  təfərrüat yuxarıda).
- **Phase 3 statistik analiz — SA-001-SA-007 müqaviləsi, frontend paneli
  VƏ async job resursu tam əhatə olunub** (pəncərə/resampling təməli +
  SA-001 gəlir seriyası + SA-002 pəncərə volatilitesi (tick-to-tick return
  std-i daxil) + SA-003 spread davranışı + SA-004 tick sürəti + SA-005
  tick-volume/flags + SA-006 sessiya müqayisəsi (təqvim-yoxdur deqradasiya
  rejimi) + SA-007 bazar rejimi namizədləri + `statistical-analysis-panel.tsx`
  + `POST/GET .../statistical-analysis-jobs`, təfərrüat yuxarıda).
  Namizəd (yalnız istifadəçi ayrıca istəsə): real versiyalanmış
  simvol/broker təqvimi qurulsa SA-006 "rəsmi" rejimə keçirilə bilər.
- **Əsas ekranın canlı indikator konsensusu paneli tamamlandı** — indi 6
  osilator (RSI, Stochastic, CCI, Williams %R, MACD, ADX) + 8 hərəkətli
  ortalama (SMA/EMA × 10/20/30/50 dövr, TradingView-un 8 MA-sına uyğun)
  əhatə edir (təfərrüat yuxarıda).
- **Likvidlik-səviyyəsi reaksiya statistikası — istifadəçinin təsvir
  etdiyi 4 addımın hamısı tamamlandı**: 1) çox-taymfreym orkestrasiyası
  (M30/H1/H4/D1), 2) canlı meyl göstəricisi (tədqiqat dili ilə, əsas
  ekranda), 3) "özü öyrənən sistem" (indikator seqmentasiyası, Bonferroni
  düzəlişli), 4) jurnal (son 30 toxunma, vaxt/qiymət/nəticə/point).
  Namizədlər (yalnız istifadəçi ayrıca istəsə): daha çox indikator şərti
  seqmentasiyaya əlavə etmək (hazırda 5: RSI/Stochastic oversold-
  overbought, ADX trending), taymfreym-üzrə sazlanabilir `horizon_bars`/
  `reaction_threshold_bps` UI-də, real production bazada faktiki nə qədər
  tarixi məlumat olduğunu yoxlamaq (D1/H4 üçün kifayət qədər gün tarixçəsi
  olmaya bilər — sintetik yoxlamada gördüyümüz kimi bu qrasefully
  `insufficient_data` kimi göstərilir, xəta vermir).
- **Phase 5 (Visual AI) — növbəti namizəd addım**: renderer, dataset
  lineage/manifest qatı, label hesablanması, eksperiment
  qeydiyyatı/persistence API-si VƏ frontend paneli tamamlandı (yalnız
  `registered ↔ archived` keçidi işlək; `rendering/training/evaluated/...`
  state-ləri CHECK-də var, amma koda hələ bağlanmayıb). Növbəti təbii
  addımlar: (1) real render→dataset→label icrası — qeydiyyatdan keçmiş
  bir eksperiment üçün faktiki şəkilləri/nümunələri qurub saxlamaq
  (RenderSpec/LabelSpec artıq real dəyərlərlə saxlanılır — bu sual HƏLL
  OLUNDU); (2) `rendering`/`training` state keçidləri; (3) model təlimi
  (ML asılılığı, GPU qərarı) — daha böyük, ayrıca qərar tələb edən addım.
  İstifadəçinin prioritet sırasına görə (Phase 3→4→7→8→9→10) Phase 5
  "əhəmiyyətli yeni həcm" kimi qeyd edilib, Phase 3/4-dən sonra əlavə
  addımdır — bu barədə istifadəçi ilə aydınlaşdırma lazım ola bilər.
- **Platform-wide audit-dən qalan, hələ həll edilməmiş tapıntılar**
  (yalnız istifadəçi ayrıca istəsə): `npm audit`-də qalan 11 tapıntı hamısı
  yalnız dev-tooling-dədir (`vite`/`wrangler`/`@cloudflare/vite-plugin`/
  `undici`/`ws`/`esbuild`/`vinext`-in `image-size`-ı/`react-server-dom-
  webpack`, production-a getmir) — düzəlişi `--force` ilə breaking
  dəyişikliklər (bəziləri hətta downgrade) tələb edir, Cloudflare deploy
  pipeline-ına təsir riski var, ayrıca qərar kimi saxlanıldı. Digər
  `docs/architecture/PHASE_2_*` alt-müqavilələrinin (API, Observability,
  Audit Evidence Export, Access Control, Configuration Startup,
  Performance Test, Retention Backup) status başlıqları da "DESIGN
  READY" göstərir — `PHASE_2_STABLE.md`-yə görə Stable qərarı YALNIZ
  replay/keyfiyyət qatına aiddir, ona görə bunların hər biri statusu
  dəyişdirilmədən əvvəl ayrıca yoxlanmalıdır.
  `PHASE_4_PATTERN_TECHNICAL_ANALYSIS_CONTRACT.md`-in "PARTIALLY
  IMPLEMENTED" başlığı da roadmap-ın Phase 4 COMPLETED qeydi ilə
  müqayisədə yoxlanılmalıdır.

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
sınaq boyu toxunulmadan işlədi. Yenə eyni gün, konsensus paneli 5 yeni
osilatorla (Stochastic, CCI, Williams %R, MACD, ADX) genişləndirildikdən
sonra da (55 dəqiqəlik sintetik GOLD tick-ləri, bütün 6 osilator "ready"
olsun deyə) yenidən canlı brauzerdə sınandı — düzgün nəticələr, konsol
xətası yox, real bazaya toxunulmadı.

2026-08-07: likvidlik sisteminin qalan 3 addımı (çox-taymfreym UI, özü-
öyrənən seqmentasiya, jurnal) tamamlandıqdan sonra canlı brauzerdə
sınandı (15 günlük ossilasiya edən sintetik GOLD tick-ləri, birdəfəlik
test backend/frontend ilə) — 4 taymfreym kartı, seqment siyahıları və
30-sətirlik jurnal düzgün göründü, konsol xətası yox, sorğu axını təmiz.
Real production backend/frontend (8000/3000) sınaq boyu toxunulmadan
işlədi.

2026-08-07 (davamı, eyni gün): istifadəçi real dashboard-da "Likvidlik
icmalı alına bilmədi" xətası gördü (real backend yeni endpoint-dən
ƏVVƏL başladılmışdı — kod restart olmadan yüklənmir); real backend/
frontend `tools/stop-local-platform.ps1` → `tools/start-local-platform.ps1`
ilə yenidən başladıldı, `404` → `401`-ə keçdi, düzəldi. Sonra, tarixi
hərəkət diapazonu (excursion range) əlavə edildikdən sonra da eyni
sintetik data ilə canlı brauzerdə sınandı — hər cümlənin sonunda "Bu,
gələcək proqnoz deyil" xəbərdarlığı düzgün göründü, konsol xətası yox.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
