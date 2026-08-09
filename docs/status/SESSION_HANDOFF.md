# ESAS Platform — Sessiya handoff

Son yenilənmə: 2026-08-07

## Başlanğıc

- Əsas layihə: `D:\ESAS_PLATFORM`
- `AGENTS.md` sənədindəki oxuma sırasını tam icra et.
- Git statusunu, branch-i və son commitləri yoxla; mövcud dəyişiklikləri silmə və görülmüş işi təkrarlama.
- GitHub girişini `gh auth status` ilə yoxla; məxfi tokeni istəmə və çap etmə.
- Real xidmətlər (`tools/start-local-platform.ps1`/`stop-local-platform.ps1`)
  işə salınmış ola bilər — `netstat -ano | grep :8000` / `:3000` ilə yoxla.

## Cari vəziyyət (ətraflı: `docs/status/CURRENT_STATE.md`)

- **[KÖHNƏLMİŞ QEYD — YENİSİ AŞAĞIDA]** Real production baza indi (2026-08-09)
  `0011` migrasiyasındadır (`0001`-`0011` hamısı tətbiq edilib, `0010`
  Phase 9 portfolio ledger + `0011` statistical-analysis-jobs daxil — bax
  aşağıdakı "Commit/push vəziyyəti" bölməsi ətraflı üçün). Ehtiyat
  nüsxələr `.runtime/phase2-migration/` və `database/backups/`-dadır
  (hər ikisi `.gitignore`-da). Xam `tick_events`/sessiya sətirlərinə heç
  vaxt toxunulmayıb.
- **Phase 1: STABLE. Phase 2: STABLE. Phase 4: namizəd lifecycle-ı əsasən
  tamamlanıb. Phase 3: SA-001-SA-007 müqaviləsi TAM ƏHATƏ OLUNUB**
  (backend + frontend + async job resursu, bax aşağı). **Phase 9: hələ
  "DESIGN READY — NOT IMPLEMENTED"** — yalnız persistence skeleti + admin
  API/frontend tikilib (manifest + event reyestri + nəzəri
  portfolio/risk ledger), canlı qərar generatoru yoxdur.
- Pattern namizədi işi bu qatlardan ibarətdir:
  1. **Draft generator** — hesablama-zamanı 6 hipotez slotu.
  2. **Persistence/`registered`** — migration `0005`.
  3. **Data-quality bloku** — namizədin ilk backtest cəhdindən əvvəl
     replay sessiyasının keyfiyyət hesabatı yoxlanılır; kritik tapıntı
     varsa `registered → blocked_by_data_quality`.
  4. **Backtest v1** — bütün 6 hipotezi əhatə edir, 4/4 baseline
     müqayisəsi ilə tamamlanıb, üst-üstə düşən hadisələr üçün
     purge/embargo ilə.
  5. **Nəticələndirmə** — `evaluated → accepted_for_shadow | rejected |
     insufficient_evidence | invalid_leakage`, multiple-testing ailəvi
     xəta düzəlişi ilə.
  6. **Job-queue** — Phase 2 worker/scheduler mühərriki (mövcud sinxron
     `POST .../backtest` dəyişməz qalıb, job-queue əlavədir).
  Vəziyyət maşını tamdır: `draft → registered → evaluated →
  accepted_for_shadow | rejected | insufficient_evidence | invalid_leakage
  | blocked_by_data_quality → archived`.
- **Düzəldilmiş bug (1):** backtest funksiyası əvvəlcə səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, real namizədin `direction`
  sahəsi isə hipotez reyestrindən `"long"/"short"` gəlir. Düzəldilib.
- **Düzəldilmiş bug (2):** `enqueue_job`-da idempotency key hash-i
  `created_by` ilə birlikdə hesablanırdı, ownership qoruması dead code idi.
- **`blocked_by_data_quality` lifecycle vəziyyəti** (commit `4e46f0f`, PUSH
  EDİLİB, CI yaşıl).
- **`invalid_leakage` lifecycle vəziyyəti** (commit `2753fcc`, PUSH EDİLİB,
  CI yaşıl) — backtest v1-ə üst-üstə düşən tarixi hadisələr üçün
  purge/embargo (`_purge_overlapping_events()`, bütün namizədlər üçün
  tətbiq olunur). Xam siqnal kifayət idisə (`≥30`) amma purge onu aşağı
  salıbsa → `invalid_leakage`. `BACKTEST_VERSION 1.5.0`.
- **Phase 9 SHADOW nəzəri portfolio/risk ledger (section 6)** (commit
  `a502a70`, PUSH EDİLİB, CI yaşıl). `shadow_theoretical_positions`
  (migration `0010`), `shadow_portfolio_repository.py`:
  `open_theoretical_position()` (mövqe-səviyyəli risk limitlərini
  namizədin öz `risk_budget_json`-undan yoxlayır — eyni-vaxtda mövqe sayı,
  simvol+istiqamət konsentrasiyası, ümumi ehtiyat risk; limit keçilirsə
  `SHADOW_RISK_BLOCKED` event-i qeydə alır, mövqe açmır),
  `close_theoretical_position()`, `get_theoretical_portfolio_summary()`.
  **Şüurlu şəkildə kənarda:** gündəlik itki/drawdown (realized PnL zaman
  sırası tələb edir, canlı axın olmadan mənasız).
- **Phase 9 SHADOW admin API + frontend** (commit `c380d08`, PUSH EDİLİB,
  CI yaşıl). İstifadəçinin "çağıranı düzəldək" tələbinə cavab — əvvəlki
  portfolio ledger artımının real çağıranı yox idi, indi var (əl ilə idarə
  olunan admin panel). 12 yeni qorunan endpoint
  (`POST/GET /api/v2/shadow-runs...` — yaratma, siyahı, detal, start/
  complete/halt keçidləri, event qeydiyyatı, mövqə açma/bağlama, portfolio
  xülasəsi). Yeni `backend/app/models/shadow.py` (Pydantic request
  modelləri). Frontend: yeni `shadow-runs-panel.tsx` bölməsi, məcburi
  `NƏZƏRİDİR — REAL ƏMƏLİYYAT YOXDUR` banneri ilə, `dashboard-navigation.tsx`
  və `page.tsx`-ə inteqrasiya olunub. Canlı brauzerdə (birdəfəlik test
  backend/frontend, real bazaya toxunmadan) tam dövr sınandı: run yaradıldı
  → başladıldı → 2 mövqə açıldı → 3-cü mövqə risk limiti ilə düzgün
  bloklandı → mövqə bağlandı → event qeydə alındı → run tamamlandı. Sınaq
  zamanı real bug tapılıb düzəldildi: `openPosition()`-da risk-blok
  xəbərdarlığı `setDetailError(...)`-dan sonra çağırılan `loadDetail()`
  öz növbəsində `detailError`-u sıfırlayırdı, xəbərdarlıq heç görünmürdü —
  çağırış sırası dəyişdirilərək düzəldildi. Backend `404 passed`, frontend
  lint/build/`11/11` test təmiz. Real bazaya toxunulmadı.
- **Phase 3 statistik analiz — pəncərə/resampling təməli + SA-001 gəlir
  seriyası** (commit `7467f95`, PUSH EDİLİB, CI yaşıl). `bars.py`-a
  `S1`/`S10` (1s/10s) pəncərələri (`BAR_BUILDER_VERSION 1.1.0`), yeni
  `return_series.py` (`compute_return_series()` — pəncərə-daxili
  log-return, tək-tick pəncərə return yaratmır, `insufficient_data` həddi),
  yeni `statistical_analysis.py` (orkestrasiya, dataset-drift qorumalı),
  yeni qorunan `GET .../statistical-analysis` endpoint-i.
- **Phase 3 SA-002 — pəncərə volatilitesi** (commit `1173d53`, PUSH
  EDİLİB, CI yaşıl). SA-001-in birbaşa davamı. Yeni `volatility.py`
  (`compute_volatility()` — artıq qurulmuş `return_series`-i və bar-ları
  girişi kimi qəbul edir, təkrar hesablama yoxdur):
  `window_range_absolute`/`window_range_relative` (`high-low`, bütün
  bar-lar, tək-tick pəncərələr də daxildir), `window_log_return_abs`
  (yalnız return-eligible pəncərələr), `robust_mad`. **Tick-to-tick return
  std-i qəsdən kənarda saxlanıldı** — yeni xam-tick keçidi tələb edir
  (hazırkı bütün analiz modulları yalnız artıq qurulmuş bar-lar üzərində
  işləyir), ayrıca kiçik artım kimi planlaşdırılıb.
  `minimum_window_returns` orkestrasiya qatında ümumi
  `minimum_sample_size`-a çevrildi. `STATISTICAL_ANALYSIS_API_VERSION
  1.0.0 → 1.1.0`.
- **Əsas ekrana canlı indikator konsensusu paneli** (commit `c2f559e`,
  PUSH EDİLİB, CI yaşıl). İstifadəçi TradingView-un "Texniki analiz"
  widget-inə (Al/Sat konsensus gauge-ları) bənzər bir görünüş istədi; iki
  seçim təklif edildi (TradingView widget-ini gömmək / öz hesablamamızı
  qurmaq) — istifadəçi öz hesablamamızı seçdi. **Vacib:** "Al/Sat" dili
  platformanın "yalnız tədqiqat" prinsipinə zidd olduğu üçün "Yuxarı
  meyl/Aşağı meyl/Neytral" etiketləməsi seçildi, "TƏDQİQAT MÜŞAHİDƏSİDİR —
  TİCARƏT TÖVSİYƏSİ DEYİL" banneri ilə. **Arxitektur fərqi:** bu, sessiyada
  indiyədək tikilmiş hər şeydən fərqli — əvvəlki analiz modulları
  `completed` replay sessiyalarının sabit snapshot-u üzərində işləyirdi,
  bu isə ilk dəfə **canlı, dəyişən** pəncərə üzərində (replay sessiyası
  TƏLƏB ETMİR) işləyir. Yeni `indicator_consensus.py`, yeni
  `live_analysis.py` (`create_live_technical_summary()`,
  `lineage.reproducible: false`), yeni `GET /api/v2/live-technical-summary`
  endpoint-i, yeni `live-technical-summary-panel.tsx` ("Nəticələr" əsas
  ekranında, mövcud 5s polling konvensiyası ilə). İlk versiyada yalnız
  RSI+EMA var idi (TradingView-un 16 göstəricisinə qarşı qəsdən 2).
- **Canlı konsensus 5 yeni osilatorla genişləndirildi** (commit `9b033df`,
  PUSH EDİLİB, CI yaşıl). İstifadəçi TradingView şəklini yenidən göstərərək
  davam etməyi istədi; "Osilatorları genişlət" seçildi. Yeni
  `oscillators.py` (`indicators.py`-a TOXUNMADAN — Stochastic %K, CCI,
  Williams %R, MACD, ADX+DI/-DI, Wilder üsulu ilə). Osilator sayı 1-dən
  6-ya çıxdı. `CONSENSUS_VERSION 2.0.0`, `LIVE_ANALYSIS_API_VERSION 1.1.0`.
  Frontend-ə hər qrup üçün detallı cədvəl əlavə edildi. Canlı brauzerdə
  tam sınandı (55 dəqiqəlik sintetik tick-lər).
- **GitHub Actions genış miqyaslı fasilə yaşadı** (2026-08-06, `15:22`-dən
  `~20:00` UTC-ə qədər, githubstatus.com-da rəsmi təsdiqlənib) — `9b033df`
  push edildikdən sonra CI run dəfələrlə "queued"/"cancelled" arasında
  ilişib qaldı (bizim koddan asılı olmayan GitHub-tərəfli infrastruktur
  problemi). Fasilə bitdikdən sonra köhnə run "zombi" vəziyyətdə qaldı
  (həm "queued" göstərir, həm "completed"/"already running" deyirdi) —
  boş commit (`54b0137`, kod dəyişikliyi yoxdur, yalnız təmiz CI run
  tetiklədi) ilə həll edildi, CI yaşıl oldu.
- **Real production backend/frontend yenidən başladıldı** (2026-08-07,
  istifadəçinin ekran görüntüsündə "Canlı texniki analiz alına bilmədi"
  xətası göstərməsindən sonra) — kök səbəb: real backend prosesi yeni
  `/api/v2/live-technical-summary` endpoint-i əlavə edilməzdən ƏVVƏL işə
  salınmışdı, kod dəyişikliyi restart olmadan yüklənmir. `tools/stop-
  local-platform.ps1` → `tools/start-local-platform.ps1` ilə düzgün
  ssenari izlənildi (MT5 Bridge FIFO buferi tick itkisinin qarşısını
  aldı). Restart sonrası endpoint `404`-dən `401`-ə keçdi (kodun
  yükləndiyini təsdiqləyir), istifadəçi səhifəni yenilədikdən sonra panel
  düzgün işləməyə başladı.
- **Likvidlik-səviyyəsi reaksiya statistikası (yalnız backend)** (commit
  `5c4a186`, PUSH EDİLİB, CI yaşıl). İstifadəçi çox-taymfreym likvidlik +
  reaksiya statistikası + "özü öyrənən sistem" + canlı "alış/satış
  gözlənilir" siqnalı + jurnal istədi. **"Alış/satış" dili rədd edildi**
  (platformanın "yalnız tədqiqat" prinsipinə zidd, bu, əslində Phase 8 —
  hələ "PLANNED" — mövzusudur); istifadəçi tədqiqat dilini (yuxarı/aşağı
  meyl) və ilk addım kimi yalnız backend/backtest statistikasını təsdiqlədi.
  `bars.py`-a `M30/H4/D1` (`BAR_BUILDER_VERSION 1.2.0`), yeni
  `liquidity_reaction.py` — mövcud `liquidity_sweep.py`-ın pool-larını
  girişi kimi qəbul edir, hər toxunuşu `reversed`/`continued`/`ambiguous`
  təsnifləndirir (purge/embargo ilə), `buy_side`/`sell_side` üçün ayrı
  95% etibar intervallı statistika.
- **Likvidlik sisteminin qalan 3 addımı** (commit `11f47ee`, PUSH EDİLİB,
  CI yaşıl) — çox-taymfreym orkestrasiyası, "özü öyrənən sistem", jurnal.
  İstifadəçi "1-dən başlayaq, soruşma, hamısını edək" dedi — 3 addım
  ardıcıl təsdiqsiz tamamlandı, tədqiqat dili qaydası eyni qaldı. Yeni
  `liquidity_reaction_segments.py` (RSI/Stochastic/ADX şərtləri üzrə
  Bonferroni-düzəlişli seqment statistikası, `ReactionEvent`-ə `bar_index`
  əlavə edildi), yeni `liquidity_overview.py` (4 taymfreymin
  orkestrasiyası — trend, ən yaxın müqavimət/dəstək, reaksiya,
  seqmentlər), yeni `GET /api/v2/liquidity-overview` endpoint-i, yeni
  `liquidity-overview-panel.tsx` ("Nəticələr" ekranında, 90s polling +
  manual "Yenilə"). Jurnal yeni backend infrastrukturu tələb etmədi —
  mövcud `ReactionEvent`-lər artıq lazım olan məlumatı daşıyırdı.
- **Real production backend/frontend YENƏ yenidən başladıldı** (2026-08-07,
  eyni gün, ikinci dəfə) — istifadəçi real dashboard-da "Likvidlik icmalı
  alına bilmədi" gördü (eyni kök səbəb: yeni `/api/v2/liquidity-overview`
  endpoint-i restart-dan əvvəl əlavə edilmişdi). Eyni təhlükəsiz stop/start
  ssenari izlənildi, `404` → `401`-ə keçdi.
- **Tarixi hərəkət diapazonu (excursion range)** (commit `e30f22a`, PUSH
  EDİLİB, CI yaşıl). İstifadəçi "gələcəyi proqnoz etmək" istədi ("filan
  nöqtədən filan nöqtəyə qədər gözlənilir") — **eyni sərhəd üçüncü dəfə
  izah edildi**, tədqiqat-dilli (backward-looking) versiya seçildi. Yeni
  `ExcursionDistribution` (`reversed`/`continued` üçün ayrı, median/p25/
  p75/p90, `n≥30`), `ReactionStatistics`-ə əlavə edildi. Frontend-də hər
  cümlənin sonunda məcburi "Bu, gələcək proqnoz deyil" xəbərdarlığı,
  source-text guard testi ilə kilidlənib.
- **Real production backend/frontend ÜÇÜNCÜ dəfə yenidən başladıldı**
  (2026-08-07, istifadəçinin sadə "restart et" tələbi ilə) — excursion
  range dəyişikliyi mövcud `/api/v2/liquidity-overview` cavab formasını
  dəyişdiyi üçün restart lazım idi. Eyni təhlükəsiz ssenari, `401`
  təsdiqləndi.
- **Phase 3 SA-003 — spread davranışı** (commit `ae03635`, PUSH EDİLİB, CI
  yaşıl). İstifadəçi "sistemin ümumi düzəlişinə qaldığımız yerdən davam
  edək" dedi — TradingView/likvidlik işi yan iş idi, əsas xətt (Phase 3)
  seçilib davam etdirildi. Yeni `spread.py` — mövcud `bars.py`
  `spread_min`/`max`/`mean`-dan (yeni xam-tick keçidi tələb OLUNMADI),
  say/orta/median/std/min/maks/p05/p25/p75/p95/p99 (mütləq və nisbi bps).
  `spread_points` şüurlu buraxılıb (point/digit metadata yoxdur).
  `statistical_analysis.py`-a inteqrasiya
  (`STATISTICAL_ANALYSIS_API_VERSION 1.2.0`). Backend `480 passed`.
  Frontend toxunulmayıb (bu endpoint-in hələ UI-si yoxdur).
- **Phase 3 SA-004 — tick sürəti/interval** (commit `243553a`, PUSH
  EDİLİB, CI yaşıl). İstifadəçi "platformanı qaldığımız yerdən düzəldək"
  dedi, SA-004 (tövsiyə edilən) seçildi. Yeni `tick_rate.py` — Phase 3-də
  İLK dəfə xam tick-lər üzərində birbaşa işləyən modul (əvvəlki
  SA-001/002/003 yalnız `bars.py` bar-ları üzərində idi); `bars.py`-ın
  bid/ask etibarlılıq filtri QƏSDƏN tətbiq edilmir (tick sürəti qiymət
  keyfiyyətindən asılı deyil). Pəncərə üzrə tick sayı/saniyə başına tick,
  bütün aralıq üzrə ardıcıl tick interval median/p95/p99/maks,
  eyni-timestamp sayı, boş/dolu/ümumi pəncərə sayı (həmişə göstərilir).
  `statistical_analysis.py`-a inteqrasiya (ikinci `iter_tick_batches`
  keçidi ilə), `STATISTICAL_ANALYSIS_API_VERSION 1.2.0 → 1.3.0`. Yeni
  `test_tick_rate.py` (8 test). Backend `488 passed`.
- **Phase 3 SA-005 — tick-volume/flags** (commit `625ab98`, PUSH EDİLİB,
  CI yaşıl). İstifadəçi "davam et" dedi, SA-004-ün birbaşa davamı olaraq
  SA-005 seçildi (eyni xam-tick oxuma formasını paylaşır). Yeni
  `tick_volume.py` — mövcud `volume` sahəsi MT5 tick-volume kimi
  etiketlənir (real birja həcmi deyil). Hər tick-in xam volume paylanması
  + sıfır/müsbət sayı; pəncərə üzrə cəm (bir nöqtə/dolu pəncərə); `flags`
  dəyərləri və sayları ŞÜURLU ŞƏKİLDƏ deşifr edilmədən (versiyalanmış MT5
  bit mapping yoxdur); module/event versiyası üzrə seqmentlər.
  `statistical_analysis.py`-a inteqrasiya (üçüncü `iter_tick_batches`
  keçidi), `STATISTICAL_ANALYSIS_API_VERSION 1.3.0 → 1.4.0`. Yeni
  `test_tick_volume.py` (9 test). Backend `496 passed`.
- **Phase 3 SA-002 tamamlanması — tick-to-tick return standart sapması**
  (commit `ef06731`, PUSH EDİLİB, CI yaşıl). İstifadəçi "davam et" dedi,
  SA-002-nin əvvəllər qəsdən kənarda saxlanmış hissəsi (indi SA-004/005-in
  xam-tick oxuma formasından istifadə edərək) tamamlandı. `volatility.py`-ın
  `compute_volatility()`-i indi `ticks`/`start_at`/`end_at` də qəbul edir,
  yeni `tick_return` sahəsi (tick-to-tick, pəncərəsiz mid-price log-return
  paylanması). `bars.py`-ın mid-price etibarlılıq filtri tətbiq edilir
  (tick_rate/tick_volume-dan fərqli olaraq — bu, qiymət seriyasıdır).
  `VOLATILITY_VERSION 1.0.0 → 1.1.0`. `STATISTICAL_ANALYSIS_API_VERSION
  1.4.0 → 1.5.0`. `test_volatility.py` yeniləndi + 4 yeni test. Backend
  `500 passed`.
- **Phase 3 SA-007 — bazar rejimi namizədləri** (commit `5037783`, PUSH
  EDİLİB, CI yaşıl). İstifadəçi "davam et" dedi; SA-006 (sessiya) vs SA-007
  seçimi təklif edildi (SA-006 versiyalanmış təqvim tələb edir — daha
  böyük iş), istifadəçi SA-007-ni seçdi. Yeni `regime_candidates.py` —
  hər pəncərəni artıq mövcud 4 feature (volatilite/spread/tick-sürəti —
  dataset-daxili median split ilə low/high, universal hədd YOX; return
  istiqaməti — up/down/flat/unknown) üzrə neytral, leksikoqrafik sıralı
  `regime_N` etiketinə təsnifləndirir (iqtisadi ad YOX, rejim etiketləri
  fərqli icralar arasında sabit deyil). `data_quality_status` real
  `create_replay_quality_report()`-dan. `STATISTICAL_ANALYSIS_API_VERSION
  1.5.0 → 1.6.0`. Yeni `test_regime_candidates.py` (7 test). Backend
  `507 passed`.
- **Phase 3 SA-006 — sessiya müqayisəsi (təqvim-yoxdur deqradasiya
  rejimi) — SA-001-SA-007 tamamlandı** (commit `78ad3ab`, PUSH EDİLİB, CI
  yaşıl). İstifadəçi "davam et" dedi; SA-006 yeganə qalan namizəd idi.
  Müqavilə versiyalanmış simvol/broker təqvimi tələb edir, AMMA təqvim
  olmadıqda öz açıq deqradasiya rejimini müəyyənləşdirir (yalnız UTC saat
  dilimləri, "London/NY" adlandırılmadan, `calendar_unavailable` işarəsi
  ilə) — platformada real təqvim olmadığı üçün MƏHZ bu rejim tətbiq
  edildi, uydurma təqvim qurulmadı. Yeni `session_comparison.py`:
  pəncərələri xam UTC saatına (0-23) görə qruplaşdırır, hər qrup üçün
  return orta/median/std + 95% CI, nümunə sayı, orta nisbi range — yeni
  xam-tick keçidi YOX. `STATISTICAL_ANALYSIS_API_VERSION 1.6.0 → 1.7.0`.
  Yeni `test_session_comparison.py` (9 test). Backend `516 passed`.
- **Frontend panel Phase 3 SA-001-SA-007 üçün** (commit `9930dd6`, PUSH
  EDİLİB, CI yaşıl). İstifadəçi "Frontend panel (tövsiyə)" seçdi — heç bir
  SA-00x-in UI-si yox idi. Yeni `statistical-analysis-panel.tsx`
  ("Araşdırma" qrupunda yeni "Statistik analiz" bölməsi, mövcud
  replay-session-seçimi axını ilə) — forma (vaxt çərçivəsi + minimum
  nümunə) + 7 SA bölməsi üçün kart. **Canlı brauzerdə tam sınandı**
  (birdəfəlik scratch backend port 8001 + scratch SQLite, birdəfəlik
  frontend port 5173, real production 8000/3000 toxunulmadan): 1,100
  sintetik tick, real `completed` replay sessiyası
  (create→start→run_max_speed_replay). M5-də (11 pəncərə) pəncərə-əsaslı
  bölmələr düzgün `insufficient_data`, tick-səviyyəli metriklər öz
  nümunəsi ilə `completed`; M1-də (55 pəncərə) bütün 7 bölmə `completed`,
  real dəyərlər (8 rejim 100%-ə cəmlənir, flag cədvəli 977/123 dəqiq
  uyğun). Konsol xətası yox, sorğu storm-u yox. Yeni
  `statistical-analysis-ui.test.mjs`. Frontend: lint təmiz, `14/14` test,
  build uğurlu. Bu ilə Phase 3-ün SA-001-SA-007 müqaviləsi HƏM backend HƏM
  frontend baxımından tam əhatə olundu.
- **YENİ, HƏLƏ COMMIT EDİLMƏYİB: Phase 3 statistik analiz üçün async
  job/persistence resursu.** İstifadəçi "Async job resursu (tövsiyə)"
  seçdi. Ətraflı: `docs/status/CURRENT_STATE.md`. Qısaca: **icrası zamanı
  real maneə aşkarlandı** — `analysis_jobs` (migration `0007`) real
  bazaya artıq tətbiq edilib, `job_type` CHECK-i yalnız
  `pattern_candidate_backtest`-i qəbul edir, migration sistemi
  `DROP`/`DELETE`/`UPDATE` qadağan etdiyi üçün CHECK-i genişləndirmək
  mümkün deyil. İstifadəçiyə bildirildi, "yeni ayrıca cədvəl + repository
  ümumiləşdirmə" seçildi. Yeni migration `0011_statistical_analysis_jobs.sql`
  (eyni struktur, `job_type='statistical_analysis'`). `analysis_job_
  repository.py` cədvəl-marşrutlaşdırmasına ümumiləşdirildi (job_id
  prefiksi ilə: `job_` dəyişməz/pattern-candidate, `saj_` yeni/statistical-
  analysis). Yeni worker handler, yeni `StatisticalAnalysisJobRequest`,
  3 yeni endpoint (mövcud pattern-candidate-backtest job endpoint-lərinin
  eyni nümunəsi). **Yolüstü düzəldilən bug:** `GET .../statistical-analysis`
  endpoint-inin köhnə `timeframe` regex-i (`M30/H4/D1` yox idi) —
  `bars.py`-a uyğunlaşdırıldı. Yeni `test_statistical_analysis_jobs_api.py`
  (7 test) + `test_analysis_job_repository.py`-a 5 yeni test. Tam backend
  regressiyası: `528 passed`. Real işləyən production backend-də
  restart-dan sonra yoxlanıldı (`401`, `404` yox). Frontend toxunulmayıb.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var. "Nəticələr" (defolt) bölməsində indi canlı indikator
  konsensusu paneli (6 osilator + 1 hərəkətli ortalama) VƏ çox-taymfreym
  likvidlik icmalı paneli (tarixi hərəkət diapazonu daxil) də var.
  "Araşdırma" qrupunda indi yeni "Statistik analiz" bölməsi də var (Phase
  3 SA-001-SA-007, replay-session-seçimi axını ilə).

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `983b2a9`-ə qədər (job-queue,
  multiple-testing, Phase 9 manifest/event skeleti, bütün baseline-lar,
  real DB migrasiyası, `blocked_by_data_quality`, `invalid_leakage`, Phase 9
  portfolio ledger, Phase 9 admin API + frontend, Phase 3 SA-001 gəlir
  seriyası, Phase 3 SA-002 volatilite, əsas ekranın canlı indikator
  konsensusu paneli (RSI+EMA), 5 yeni osilator, boş CI-düzəliş commit-i,
  likvidlik-səviyyəsi reaksiya statistikası (yalnız backend), likvidlik
  sisteminin qalan 3 addımı, tarixi hərəkət diapazonu, Phase 3 SA-003
  spread davranışı, Phase 3 SA-004 tick sürəti, Phase 3 SA-005
  tick-volume/flags, Phase 3 SA-002 tamamlanması (tick-to-tick return
  std), Phase 3 SA-007 bazar rejimi namizədləri, Phase 3 SA-006 sessiya
  müqayisəsi, Phase 3 SA-001-SA-007 üçün frontend panel, Phase 3 async
  job/persistence resursu (migration `0011`), migration `0010`/`0011`-in
  real bazaya tətbiqinin sənədləşdirilməsi — hamısı push edilib, CI-də
  yaşıl).
- **Yeni, hələ commit edilməyib:** Job-queue-nun frontend səthi (kod +
  testlər + sənədlər), yuxarıda təsvir edilib. AGENTS.md qaydasına görə
  commit/push istifadəçinin ayrıca açıq təsdiqini gözləyir.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi**. `0006`-
  `0009` real bazaya əvvəllər tətbiq edilmişdi. **2026-08-09: `0010`
  (Phase 9 portfolio ledger) VƏ `0011` (`statistical_analysis_jobs`) eyni
  icrada real bazaya tətbiq edildi** — istifadəçinin "platformanı
  yenidən işə sal, sonra davam et" tələbindən sonra, migration `0011`-i
  tətbiq etmək açıq təsdiqləndi. `tools/phase2-migrate-production.py
  --allow-production` istifadə edildi (ehtiyat nüsxə + BÜTÜN gözləyən
  migrasiyaları tətbiq edir, təkcə istənilən deyil — ona görə `0010` da
  bu icrada "pulsuz" tətbiq oldu). Doğrulama: `tick_events` (2,419,520)
  və `replay_sessions` (7) sayları dəyişməz, `quick_check=ok` (ehtiyat
  nüsxə + tətbiq edilmiş baza hər ikisində). Real backend/frontend
  stop→start ilə yenidən başladıldı, `/health` `200`, yeni job
  endpoint-i `401` qaytardı (`no such table` YOX) — cədvəllər canlı və
  əlçatandır. Ehtiyat nüsxə: `.runtime/phase2-migration/`
  (gitignored). Bu, kod dəyişikliyi deyil, commit/push tələb olunmadı.

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində). Job-queue
  frontend artımı backend-ə toxunmayıb, `528 passed` dəyişməz qalır.
- Frontend bu artımla (`async-job-panel.tsx` + iki panelin inteqrasiyası)
  lint təmiz, `17/17` test, production build uğurlu. **Canlı brauzerdə
  tam sınandı** — həm pattern-candidate-backtest job-u (`job_` prefiksi)
  həm statistical-analysis job-u (`saj_` prefiksi) uğurla tamamlandı,
  nəticələr sync yolla eyni render-ə axdı, konsol xətası yox. Port
  5174 CORS allow-list-i tərəfindən rədd edildi (yalnız 3000/5173 icazəli
  — gələcək sessiyalar üçün qeyd).
- Real production backend/frontend bu sessiyada iki dəfə yenidən
  başladıldı: (1) istifadəçinin sərəncamı ilə (`platformanin backend ve
  frontedini yeniden ise sal`) — kod dəyişikliyini yükləmək üçün; (2)
  migration `0010`/`0011` real bazaya tətbiq edildikdən sonra. Hər iki
  dəfə `/health` `200`, yeni `POST .../statistical-analysis-jobs`
  route-u sağlam cavab verdi. Real DB indi `0011`-ə qədər tam
  yenilənmişdir.
- Canlı brauzerdə vizual yoxlama (2026-08-05, əvvəlki sessiya): Pattern
  namizədi bölməsinin tam dövrü sınandı. 2026-08-06-da real bazanın
  `HTTP 500` problemi istifadəçi ilə birlikdə canlı brauzerdə aşkarlanıb
  düzəldilib; eyni gün Phase 9 admin panelinin tam dövrü də (birdəfəlik
  test backend/frontend ilə, real bazaya toxunmadan) canlı brauzerdə
  sınanıb, bir real bug tapılıb düzəldilib. Yenə eyni gün, əsas ekranın
  yeni canlı indikator konsensusu paneli (sintetik GOLD tick-ləri,
  birdəfəlik test backend/frontend ilə) canlı brauzerdə sınanıb — düzgün
  RSI/EMA/konsensus nəticələri göstərilib. Sınaq zamanı avtomatlaşdırılmış
  brauzer mühitinin `document.visibilityState`-i "hidden" olduğu üçün
  (əvvəlki sessiyalarda da qeyd edilib) müvəqqəti override ilə tək təmiz
  refresh tetiklənib; override-i silmədən saxlamaq test alətinin öz daxili
  compositing yoxlamaları ilə toqquşaraq sürətli sorğu axınına səbəb oldu
  (YALNIZ test artefaktı — köhnə `/status/operational` pollingi də eyni
  cür təsirləndi, tətbiq kodunda problem yox idi; override silinən kimi
  dərhal dayandı). Real production backend/frontend (8000/3000) sınaq
  boyu toxunulmadan işlədi. Eyni gün, konsensus paneli 5 yeni osilatorla
  genişləndirildikdən sonra da (55 dəqiqəlik sintetik tick-lər, override-i
  bu dəfə dərhal silmə intizamı ilə) yenidən canlı brauzerdə sınanıb —
  bütün 6 osilator + EMA cədvəldə düzgün göründü, konsol xətası yox,
  sorğu axını təmiz idi.
- 2026-08-07: likvidlik sisteminin qalan 3 addımı canlı brauzerdə sınandı
  (15 günlük ossilasiya edən sintetik GOLD tick-ləri — 21,600 tick,
  birdəfəlik test backend/frontend ilə). Bu dəfə override-artefaktından
  tamamilə qaçınmaq üçün panelin öz "Yenilə" düyməsi birbaşa JS-lə
  klikləndi (visibilityState override-i istifadə edilmədi) — 4 sorğu,
  storm yox. M30/H1/H4 üçün mənalı statistika (məs. M30 buy_side: 834
  toxunma, 57.7% geri qayıtma; RSI-overbought seqmenti 84.7%-ə çatır),
  D1 düzgün `insufficient_data`. Jurnal (30 sətir) düzgün göründü, konsol
  xətası yox. Real production backend/frontend sınaq boyu toxunulmadan
  işlədi.
- 2026-08-07 (davamı): tarixi hərəkət diapazonu əlavə edildikdən sonra da
  eyni sintetik data ilə canlı brauzerdə sınandı (eyni "Yenilə"-klik
  metodu ilə, storm yox) — hər cümlənin sonunda "Bu, gələcək proqnoz
  deyil" xəbərdarlığı düzgün göründü, real hesablanan median/p25/p75
  dəyərləri dəqiq eyni mətnlə render olundu, konsol xətası yox.
- 2026-08-07 (davamı): Phase 3 SA-001-SA-007 frontend paneli canlı
  brauzerdə tam sınandı — bu dəfə tamamlanmış REPLAY SESSİYASI tələb
  edən ilk panel yoxlaması, ona görə fərqli quraşdırma istifadə edildi:
  birdəfəlik scratch backend (port 8001, ayrıca SQLite bazası) + 1,100
  sintetik GOLD tick (3s aralıqla, 55 dəqiqə) + backend-in öz repository
  funksiyaları ilə (`create_replay_session`→`transition_replay_session`
  ("start")→`run_max_speed_replay`) real `completed` sessiya yaradıldı —
  bu, `_prepare()` pytest fixture-larının eyni ardıcıllığıdır, UI-dən
  DEYİL. Birdəfəlik frontend (port 5173, `NEXT_PUBLIC_ESAS_API_URL`
  scratch backend-ə yönləndirilib) ilə daxil olundu, "Statistik analiz"
  bölməsi açıldı: defolt M5-də (11 pəncərə, defolt minimum 30-dan az)
  pəncərə-əsaslı bölmələr düzgün `insufficient_data`, AMMA tick-səviyyəli
  metriklər (tick-return, interval) öz 1,099-nöqtəlik nümunəsi ilə düzgün
  `completed` — bu, backend-in dizayn etdiyi fərqləndirmənin frontend-də
  də düzgün göründüyünü sübut edir. M1-ə keçdikdə (55 pəncərə, forma
  seçici React controlled-component olduğu üçün JS-lə native value
  setter + `change`/submit event-ləri ilə dəyişdirildi — `read_page`
  aksesibilite ağacı bu səhifədə form elementlərinə çatmadan kəsildiyi
  üçün) bütün 7 bölmə `completed`, real dəyərlərlə — 8 fərqli rejim
  (nisbətlər tam 100%-ə cəmlənir), flag cədvəli sintetik datadakı
  977/123 bölgüsünə dəqiq uyğun, tək UTC 08:00 saat qrupu real 95%
  etibar intervalı ilə. Konsol xətası yox, sorğu axını təmiz (hər
  vaxt-çərçivəsi dəyişikliyinə bir sorğu, storm yox). Scratch backend/
  frontend prosesləri PID ilə dayandırıldı, scratch SQLite faylı silindi.
  Real production backend/frontend (8000/3000) sınaq boyu toxunulmadan
  işlədi.

## Növbəti mərhələ

Seçilməyib. **Phase 3-ün SA-001-SA-007 statistik analiz müqaviləsi indi
backend, frontend VƏ async job resursu baxımından tam əhatə olunub**
(SA-001-SA-007 hamısı, `statistical-analysis-panel.tsx`, `POST/GET
.../statistical-analysis-jobs` — migration `0011` real bazaya tətbiq
edildi, 2026-08-09) **VƏ job-queue-nun frontend səthi tamamlandı**
(`async-job-panel.tsx`, həm pattern-candidate-backtest həm
statistical-analysis job-ları üçün, canlı brauzerdə tam sınanıb); əsas
ekrana canlı indikator konsensusu paneli əlavə edildi və 5 yeni
osilatorla (Stochastic, CCI, Williams %R, MACD, ADX) genişləndirildi;
likvidlik-səviyyəsi reaksiya statistikasının istifadəçinin təsvir etdiyi
4 addımı da (çox-taymfreym, seqmentasiya, canlı UI, jurnal) tamamlandı,
üzərinə tarixi hərəkət diapazonu (excursion range) əlavə edildi.
Namizədlər (`docs/status/NEXT_TASK.md`, hamısı yalnız istifadəçi ayrıca
istəsə): real versiyalanmış broker təqvimi qurulsa SA-006-nı "rəsmi"
rejimə keçirmək, hərəkətli ortalamaların genişləndirilməsi (SMA, əlavə
dövrlər), likvidlik seqmentasiyasına əlavə şərtlər, Phase 9-un qalan
bölmələri. İstifadəçinin ayrıca təsdiqi tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir. Real bazaya (`database/ESAS_PLATFORM.sqlite`) hər hansı
dəyişiklikdən əvvəl ayrıca açıq icazə al.
