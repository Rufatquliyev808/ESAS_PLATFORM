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

- **Real production baza (`database/ESAS_PLATFORM.sqlite`) hazırda `0009`
  migrasiyasındadır** (əvvəllər `0004`-də donub qalmışdı — istifadəçi
  brauzerdə `HTTP 500` gördü, kök səbəb tapılıb düzəldildi, istifadəçinin
  açıq təsdiqi ilə). Ehtiyat nüsxə `database/backups/`-dadır
  (`.gitignore`-a əlavə edilib). Xam `tick_events`/sessiya sətirlərinə
  toxunulmayıb. **`0010` (bu sessiyanın Phase 9 portfolio ledger artımı)
  yalnız test bazalarında sınanıb — real bazaya HƏLƏ TƏTBİQ EDİLMƏYİB**,
  çünki heç bir real çağıran yoxdur (bu, canlı SHADOW sisteminin bir
  hissəsi deyil, yalnız gələcək üçün skelet). Real bazaya tətbiq lazım
  olduqda ayrıca icazə tələb olunacaq.
- **Phase 1: STABLE. Phase 2: STABLE. Phase 4: namizəd lifecycle-ı əsasən
  tamamlanıb. Phase 3: İN PROGRESS** (cari aktiv mərhələ — indicə
  başlanıb). **Phase 9: hələ "DESIGN READY — NOT IMPLEMENTED"** — yalnız
  persistence skeleti + admin API/frontend tikilib (manifest + event
  reyestri + nəzəri portfolio/risk ledger), canlı qərar generatoru yoxdur.
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
- **YENİ, HƏLƏ COMMIT EDİLMƏYİB: Likvidlik sisteminin qalan 3 addımı**
  (çox-taymfreym orkestrasiyası, "özü öyrənən sistem", jurnal). İstifadəçi
  "1-dən başlayaq, soruşma, hamısını edək" dedi — 3 addım ardıcıl
  təsdiqsiz tamamlandı, tədqiqat dili qaydası eyni qaldı. Ətraflı:
  `docs/status/CURRENT_STATE.md`. Qısaca: yeni
  `liquidity_reaction_segments.py` (RSI/Stochastic/ADX şərtləri üzrə
  Bonferroni-düzəlişli seqment statistikası, `ReactionEvent`-ə `bar_index`
  əlavə edildi, `REACTION_VERSION 1.1.0`), yeni `liquidity_overview.py`
  (4 taymfreymin orkestrasiyası — trend, ən yaxın müqavimət/dəstək,
  reaksiya, seqmentlər), yeni `GET /api/v2/liquidity-overview` endpoint-i,
  yeni `liquidity-overview-panel.tsx` ("Nəticələr" ekranında, 90s polling
  + manual "Yenilə" — bu endpoint hər çağırışda 4 taymfreymin tam
  backtest statistikasını yenidən hesablayır). Jurnal yeni backend
  infrastrukturu tələb etmədi — mövcud `ReactionEvent`-lər artıq lazım
  olan məlumatı (vaxt/qiymət/nəticə/point) daşıyırdı. Canlı brauzerdə tam
  sınandı (15 günlük ossilasiya edən sintetik data — M30/H1/H4 mənalı
  statistika verdi, D1 düzgün `insufficient_data`). Backend `472 passed`,
  frontend lint/build/`13/13` test təmiz.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var. "Nəticələr" (defolt) bölməsində indi canlı indikator
  konsensusu paneli (6 osilator + 1 hərəkətli ortalama) VƏ çox-taymfreym
  likvidlik icmalı paneli də var.

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `5c4a186`-ə qədər (job-queue,
  multiple-testing, Phase 9 manifest/event skeleti, bütün baseline-lar,
  real DB migrasiyası, `blocked_by_data_quality`, `invalid_leakage`, Phase 9
  portfolio ledger, Phase 9 admin API + frontend, Phase 3 SA-001 gəlir
  seriyası, Phase 3 SA-002 volatilite, əsas ekranın canlı indikator
  konsensusu paneli (RSI+EMA), 5 yeni osilator, boş CI-düzəliş commit-i,
  likvidlik-səviyyəsi reaksiya statistikası (yalnız backend) — hamısı
  push edilib, CI-də yaşıl).
- **Yeni, hələ commit edilməyib:** Likvidlik sisteminin qalan 3 addımı
  (çox-taymfreym orkestrasiyası, özü-öyrənən seqmentasiya, jurnal — kod +
  testlər + sənədlər), yuxarıda təsvir edilib. AGENTS.md qaydasına görə
  commit/push istifadəçinin ayrıca açıq təsdiqini gözləyir (istifadəçi bu
  artım üçün "soruşma, hamısını et" dedi — dizayn seçimlərini soruşmadan
  tikdim, amma commit/push ritualını yenə də izlədim). İşçi qovluqda
  `.tmp/` (əvvəlki sessiyanın pytest qalıqları, untracked, əhəmiyyətsiz)
  də qalıb.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi**. `0006`-
  `0009` real bazaya tətbiq edilib. `0010` (bu artımın portfolio ledger
  cədvəli) yalnız kodda/test bazalarında mövcuddur, real bazaya tətbiq
  edilməyib (real çağıran yoxdur, ehtiyac yarandıqda ayrıca icazə tələb
  olunur).

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində). Bu artımla `472
  passed`.
- Frontend: bu artımda (çox-taymfreym likvidlik icmalı paneli) lint təmiz,
  `13/13` test, production build uğurlu.
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

## Növbəti mərhələ

Seçilməyib. Phase 3-ün SA-001 (gəlir seriyası) və SA-002 (pəncərə
volatilitesi) tamamlandı, əsas ekrana canlı indikator konsensusu paneli
əlavə edildi və 5 yeni osilatorla (Stochastic, CCI, Williams %R, MACD,
ADX) genişləndirildi, likvidlik-səviyyəsi reaksiya statistikasının
istifadəçinin təsvir etdiyi 4 addımı da (çox-taymfreym, seqmentasiya,
canlı UI, jurnal) tamamlandı. Namizədlər (`docs/status/NEXT_TASK.md`):
SA-002-nin qalan hissəsi (tick-to-tick return std-i), SA-003-SA-007
(spread, tick sürəti, tick-volume, sessiya, rejim), hərəkətli
ortalamaların genişləndirilməsi (SMA, əlavə dövrlər), likvidlik
seqmentasiyasına əlavə şərtlər, Phase 9-un qalan bölmələri (istəsə),
job-queue-nun frontend səthi (istəsə). İstifadəçinin ayrıca təsdiqi
tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir. Real bazaya (`database/ESAS_PLATFORM.sqlite`) hər hansı
dəyişiklikdən əvvəl ayrıca açıq icazə al.
