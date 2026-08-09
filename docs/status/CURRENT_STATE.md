# ESAS Platform — Cari Vəziyyət

## 2026-08-09 — Tam vəziyyət doğrulaması + Phase 5 spec saxlanması düzəlişi

- İstifadəçi yeni sessiyada "əvvəlcə oxu, sonra faktla təsdiqlə, sonra
  davam et" tapşırığı verdi (AGENTS.md-in öz qaydası). Bütün konstitusiya/
  arxitektura sənədləri, `PROJECT_ROADMAP.md`, status sənədləri oxundu;
  Git (təmiz, `origin/main`=`0c20baa` ilə sinxron), testlər (backend
  `609/609`, frontend `18/18`, müstəqil işlədilib) və real production
  bazası (read-only, `database/ESAS_PLATFORM.sqlite`) yoxlanıldı.
- **Baza yoxlaması:** `quick_check: ok`, miqrasiyalar `0001`-`0011`
  tətbiq olunub (`0012` DOĞRU olaraq tətbiq edilməyib — sənədin dediyi
  kimi), `tick_events`=2,419,520, `replay_sessions`=7 — sənədlərlə
  üst-üstə düşür. Phase 3/4/5-in eksperiment cədvəlləri (0 sətir) —
  gözlənilən, çünki bunlar yalnız scratch bazalarda sınanıb.
- **Tapılan 2 problem:** (1) canlı tick axını ~41.5 saat köhnəlib (son
  tick `2026-08-07T20:57:59`) — MT5 Bridge tərəfi, bu sessiyanın
  həll etmə səlahiyyətindən kənardır, istifadəçiyə bildirildi; (2)
  `PROJECT_ROADMAP.md` Phase 5-i hələ "PLANNED" göstərirdi — düzəldildi
  (commit `71f67f0`).
- **Phase 5-də tapılan real dizayn boşluğu düzəldildi:** qeydiyyat
  API-si əvvəllər `render_spec_id`/`label_spec_id`-ni çağıranın verdiyi
  ixtiyari mətn kimi qəbul edirdi — heç nə onların real spec-ə uyğun
  olduğunu yoxlamırdı, gələcəkdə materiallaşdırma üçün bərpa etmək
  mümkün deyildi. Migration `0012`-yə (hələ production-a tətbiq
  edilməyib, təhlükəsiz redaktə edilə bilər) `render_spec_json`/
  `label_spec_json` sütunları əlavə edildi. `register_visual_experiment()`
  indi real `RenderSpec`/`LabelSpec` dataclass-larını qəbul edir, ID-ni
  server tərəfdə `render_spec_id()`/`label_spec_id()` funksiyalarından
  (renderer/labeller-in özünün istifadə etdiyi eyni funksiyalar) hesablayır.
- Frontend forması yeniləndi: 3 ixtiyari hash-yapışdırma sahəsi real
  `horizon_bars`/`up_threshold_bps`/`down_threshold_bps` rəqəm
  sahələrinə çevrildi; render spec standart dəyərlərdə qalır (UI-də hələ
  göstərilmir). Tam backend regressiyası: `609 passed`. Frontend:
  lint/build təmiz, `18/18` test. Canlı brauzerdə yenidən sınandı (yeni
  sahələrlə qeydiyyat, cavabda real `render_spec`/`label_spec` dəyərləri
  göründü), real 8000/3000 toxunulmadan.

## 2026-08-09 — Phase 5 (Visual AI): frontend paneli

- İstifadəçi frontend panelini seçdi (dataset materiallaşdırma əvəzinə
  — o, RenderSpec/LabelSpec-in faktiki dəyərlərinin harada saxlanacağı
  barədə ayrıca dizayn qərarı tələb edir, açıq qalan namizəd kimi
  qeyd edildi).
- Yeni `frontend/app/visual-experiments-panel.tsx`: "Qiymətləndirmə"
  qrupunda "Visual AI eksperimentləri" bölməsi — form (vaxt çərçivəsi,
  pəncərə uzunluğu, bar fingerprint/render spec id/label spec id əl ilə
  mətn sahələri kimi — hələ hesablama endpoint-i yoxdur) + qeydə
  alınmış eksperimentlərin cədvəli (cursor siyahı) + arxivləşdirmə.
  Bütün 14 lifecycle state-in Azərbaycanca etiketi var.
- **Wiring zamanı tapılan backend boşluğu**: `visual_experiment_
  repository.py`-da yalnız register/get/archive var idi, siyahı funksiyası
  yox idi — `list_visual_experiments()` (cursor-paginated,
  `list_pattern_candidates`-i təkrarlayır) + yeni imzalı cursor cütü
  (`cursor.py`-da) + `GET /api/v2/visual-experiments` endpoint-i əlavə
  edildi. 4 yeni backend test. Tam backend regressiyası: `609 passed`.
- `dashboard-navigation.tsx`/`page.tsx`/`replay-panel.tsx` digər bütün
  sessiya-əsaslı panellərlə eyni qaydada bağlandı. Yeni
  `visual-experiments-ui.test.mjs` + `dashboard-navigation.test.mjs`-ə
  əlavə. Frontend: lint təmiz, build təmiz, `18/18` test.
- **Canlı brauzerdə tam sınandı** (scratch backend port 8004 + scratch
  SQLite, tamamlanmış replay sessiyası ilə seed edilib, scratch frontend
  port 5173, real 8000/3000 toxunulmadan): əl ilə daxil edilmiş
  fingerprint/spec-id dəyərləri ilə eksperiment qeydə alındı, cədvəldə
  `registered` kimi göründü, arxivləşdirildi, cədvəl `archived`-ə
  yeniləndi və arxivləşdirmə düyməsi düzgün yoxa çıxdı. Konsol xətası
  yox.

## 2026-08-09 — Phase 5 (Visual AI): eksperiment qeydiyyatı/persistence

- İstifadəçi DB miqrasiyası tələb edən qata başlamağı açıq təsdiqlədi
  (AGENTS.md qaydasına görə əvvəlcə soruşuldu).
- Yeni migration `0012_visual_experiments.sql`: `visual_experiments`
  cədvəli + append-only `visual_experiment_audit` cədvəli,
  `pattern_candidates`-in strukturunu dəqiq təkrarlayır.
- **Bu sessiyada əvvəl tapılan `analysis_jobs` CHECK-constraint
  bloklanmasından çıxarılan dərs tətbiq edildi**: `lifecycle_state`
  CHECK-i müqavilənin TAM 14 vəziyyətini indi sadalayır (`registered`,
  `rendering`, `training`, `evaluated`, `accepted_for_shadow`,
  `rejected`, `archived`, `blocked_by_data_quality`, `invalid_leakage`,
  `non_reproducible`, `out_of_distribution`, `insufficient_evidence`,
  `failed`, `cancelled`) — hətta yalnız `registered`/`archived` bu
  addımda koda bağlı olsa da — çünki CHECK production-a çatandan sonra
  bu migration sistemi onu genişləndirə bilmir.
- Yeni `backend/app/database/visual_experiment_repository.py`:
  `register_visual_experiment()` yalnız DONDURULMUŞ konfiqurasiyanı
  saxlayır — heç bir şəkil render etmir, dataset qurmur, təlim
  aparmır. `experiment_id` konfiqurasiyadan deterministik hash-lənir
  (eyni sxem `render_spec_id`/`sample_id`/`label_spec_id` kimi) — eyni
  konfiqurasiyanın təkrar qeydiyyatı təbii idempotentdir.
  `get_visual_experiment()`/`archive_visual_experiment()` (yalnız
  `registered → archived`, hələlik) tamamlayır.
- Yeni `backend/app/models/visual_experiment.py` + 3 endpoint
  `main.py`-da: `POST /api/v2/visual-experiments`, `GET
  /api/v2/visual-experiments/{experiment_id}`, `POST
  .../{experiment_id}/archive`.
- Yeni `test_visual_experiment_repository.py` (12 test) +
  `test_visual_experiments_api.py` (10 test). Tam backend regressiyası:
  `605 passed`. Miqrasiya YALNIZ test bazasına tətbiq edildi — real
  production bazaya YOX (bu, ayrıca açıq təsdiq tələb edəcək).

## 2026-08-09 — Phase 5 (Visual AI): label hesablanması

- İstifadəçi "davam et" dedi — dataset lineage qatının təbii davamı.
- Yeni `backend/app/analysis/visual_label.py`: `compute_label(bars, *,
  observation_end_at, spec)` müşahidə pəncərəsinin son close-undan
  `spec.horizon_bars` bar sonrakı close-a qədər return-u
  UP/DOWN/FLAT kimi təsnifləndirir, əvvəlcədən qeydə alınmış
  `LabelSpec` həddinə görə. `bars` tam tarixi seriya olmalıdır (müşahidə
  pəncərəsi VƏ ondan sonrakı bar-lar) — renderer bu gələcək bar-ları
  HEÇ VAXT görmür, yalnız bu ayrıca keçid görür.
- `LabelSpec`-də dataset-üzrə optimallaşdırma məntiqi HEÇ YERDƏ yoxdur
  (yalnız bir nümunənin öz bar-larına baxır) — "class həddi bütün
  datasetə baxılaraq optimallaşdırılmır" qaydası belə təmin olunur.
- Horizon bar hələ mövcud deyilsə → `INCOMPLETE_HORIZON`
  (`label_value=None`), təxmin edilmir — birbaşa `visual_dataset.py`-ın
  mövcud `PENDING_HORIZON` məntiqinə bağlanır.
- **Test zamanı tapılıb düzəldilən:** dəqiq sərhəd dəyərləri (bps
  return tam `up_threshold_bps`/`down_threshold_bps`-ə düşəndə) adi
  float dəyirmiləşdirmə səs-küyü səbəbindən səhvən FLAT təsnif oluna
  bilirdi. `1e-9` epsilon əlavə edildi (yalnız float-səs-küyü qorunması,
  real data üçün davranış dəyişmir).
- Yeni `test_visual_label.py` (12 test). Tam backend regressiyası:
  `583 passed`.

## 2026-08-09 — Phase 5 (Visual AI): dataset lineage/manifest qatı

- İstifadəçi "davam et" dedi — renderin təbii davamı.
- Yeni `backend/app/analysis/visual_dataset.py`: müqavilənin lineage
  zəncirini (`sample_id → source_bar_fingerprint → render_spec_id →
  image_checksum → observation_end_at → label_spec_id →
  label_available_at → split_id`) tətbiq edir.
- `build_visual_sample()` bir `CanonicalImage`-i `VisualSample`-ə
  çevirir. **Label DƏYƏRİNİN hesablanması qəsdən kənarda saxlanıldı**
  (müqavilə tələb edir ki, label "ayrıca" — Phase 4 qaydasına görə —
  hesablansın, render-ə təsir etməsin); bu qat yalnız çağıranın verdiyi
  label-i qeyd edir və `label_available_at`-in müşahidə pəncərəsi
  bağlanmazdan ƏVVƏL ola bilməyəcəyini yoxlayır. `label_available_at`
  verilməyibsə → `label_status=PENDING_HORIZON` ("horizon tamamlanmayan
  nümunə təlimə daxil edilmir" qaydasına uyğun).
- `assign_time_based_splits()` — purged walk-forward bölgü. HEÇ VAXT
  təsadüfi deyil (müqavilə: "Random image split qadağandır; zaman
  əsaslı bölgü məcburidir"): label-lənmiş nümunə öz
  `[observation_window_start_at, label_available_at)` intervalının 2
  zaman sərhədinə görə haraya düşdüyünə əsasən təyin olunur; sərhədi
  KƏSƏN nümunə heç bir tərəfə verilmir, `PURGED_BOUNDARY_OVERLAP` kimi
  saxlanılır (səssiz silinmir) — əks halda eyni tarixi hadisə iki
  bölgüyə sıza bilərdi. Label-siz nümunələr heç vaxt bölünmür.
- `build_dataset_manifest()` hər nümunəni symbol/timeframe/split/label-
  status/quality-flags üzrə sayır — heç nə manifestdən silinmir. Phase
  3-ün SA-006/SA-007 sessiya/rejim məlumatı hələ birləşdirilməyib
  (ayrıca gələcək addım kimi qeyd edildi).
- Yeni `test_visual_dataset.py` (18 test): label-status keçidləri,
  sample-id determinizmi, səbəbiyyət validasiyası, bütün 3 split nəticəsi
  + hər iki sərhəd-keçmə purge halı, pending-horizon nümunələrin heç vaxt
  bölünməməsi, manifest tamlığı/determinizmi. Tam backend regressiyası:
  `571 passed`. Frontend/API toxunulmayıb.

## 2026-08-09 — Phase 5 (Visual AI) başladı: deterministik kanonik qrafik renderi

- İstifadəçi platform-wide audit-dən sonra "phase 5" dedi. Müqavilə
  (`PHASE_5_VISUAL_AI_CONTRACT.md`) böyük həcmdə iş tələb etdiyi üçün
  (render → dataset lineage → API/lifecycle → model təlimi → frontend)
  Phase 3-dəki kimi kiçik addımlara bölünməsi təklif edildi.
  İstifadəçi ilk addım kimi **deterministik qrafik renderini** seçdi (heç
  bir ML asılılığı yoxdur, tam testlənə bilər, hər şey bundan asılıdır).
- Yeni `backend/app/analysis/visual_render.py`:
  `render_canonical_chart(bars, *, bar_fingerprint, spec)` yalnız Phase
  4-ün bağlanmış `MarketBar`-larından şam qrafiki PNG-si yaradır — heç
  vaxt label, nəticə və ya gələcək bar qəbul etmir, ona görə müqavilənin
  səbəbiyyət sərhədi TİKİNTİ İLƏ (konstruksiya ilə) qorunur. **Heç bir
  yeni asılılıq YOXDUR** — PNG encoding stdlib `zlib`/`struct`-dan əl ilə
  yazılıb (sabit filter tipi, timestamp chunk-ları yoxdur).
  `image_checksum` PNG-ə sıxılmış bytes üzərində deyil, xam piksel
  buferi üzərində hesablanır — müqavilənin "eyni PİKSEL checksum-u"
  ifadəsinə dəqiq uyğundur və zlib versiyasından/platformadan asılı
  deyil.
- `RenderSpec` konfiqurasiya edilə bilən geometriya/rəng sahələrini
  daşıyır; kanal sayı (3) və rəng məkanı (`rgb8`) sabit konstantlardır
  (çağıran tərəfindən dəyişdirilə bilməz) ki, format kanonik qalsın.
  `render_spec_id()` eksperiment qeydiyyatı üçün spec-i hash-ləyir.
- `CanonicalImage` müqavilənin tələb etdiyi hər şeyi qeyd edir: pəncərə
  ilk/son bar lineage-i, `known_at` (son barın öz `end_at`-i — hər
  pikselin real mövcud ola biləcəyi ən erkən an), qiymət şkalası,
  layer-lər, və bar-lar arasındakı boşluğu FABRİKASİYA EDİLMİŞ şam
  ƏLAVƏ ETMƏDƏN işarələyən missing-data maskası
  (`missing_bar_indices`/`quality_flags`).
- Yeni `test_visual_render.py` (16 test): validasiya, determinizm (eyni
  giriş+spec → eyni checksum və PNG bytes; fərqli spec → fərqli
  `render_spec_id`/checksum), boşluq aşkarlanması, səbəbiyyət
  (`known_at`/lineage), və real PNG bytes-dən dekodlanmış piksel
  rənglərinin (bullish/bearish şam gövdəsi, arxa fon) yoxlanması (test
  üçün yazılmış kiçik, yalnız-stdlib PNG dekoderi ilə). Tam backend
  regressiyası: `553 passed`. Frontend toxunulmayıb — qəsdən kiçik
  saxlanıldı (Phase 3-ün SA-001 ilə başladığı eyni prinsip).

## 2026-08-09 — Platform-wide audit: köhnə sənəd statusları düzəldildi, npm audit boşluqları həll edildi

- İstifadəçi "platformani umumi ceklist et" dedi — nə qalıb/uyğunsuzdur,
  onları yekunlaşdıraq, sonra qalan iş siyahısı ver.
- Yoxlanıldı, sağlam tapıldı: backend `537 passed`, frontend lint/build/
  `17/17` test, `TODO/FIXME/XXX/HACK` yoxdur, real production DB
  (migration `0001`-`0011`, `quick_check=ok`), real backend/frontend
  (8000/3000, hər ikisi `200`).
- Tapılıb düzəldilib (docs commit `83c5f91`, push edilib):
  - `PHASE_2_WORKER_SCHEDULER_CONTRACT.md` və
    `PHASE_3_STATISTICAL_ANALYSIS_CONTRACT.md`-in "DESIGN READY — NOT
    IMPLEMENTED" statusu → IMPLEMENTED (hər ikisi bu sessiyada tam
    qurulub, test edilib, frontend-i də var).
  - `SESSION_HANDOFF.md`/`NEXT_TASK.md`-də artıq push edilmiş async-job-
    resursu və hərəkətli-ortalama işləri üçün köhnə "hələ commit
    edilməyib" işarələri düzəldildi.
  - Köhnə, izlənilməyən `.tmp/` qovluğu (19MB, 2026-08-05 pytest scratch)
    `.gitignore`-a əlavə edildi.
- `npm audit` (npm audit fix commit `297377e`, push edilib): production
  asılılıqlarında (`--omit=dev`) 4 HIGH boşluq (`next`/`postcss`/`sharp`)
  tapıldı. Əvvəlcə "major/breaking `next` yüksəlişi" kimi düşünülmüşdü,
  amma yoxlayanda faktiki düzəliş `16.2.6 → 16.3.0` (eyni major daxilində
  kiçik yüksəliş) oldu. `next` + `eslint-config-next` birlikdə
  yüksəldildi, `js-yaml`/`fast-uri`/`brace-expansion`/`@babel/core` üçün
  təhlükəsiz (`--force` olmadan) transitive düzəlişlər tətbiq edildi.
  Production asılılıqları indi `0 boşluq`. Qalan 11 tapıntı yalnız
  dev-tooling-dədir (`vite`/`wrangler`/`@cloudflare/vite-plugin` və s.,
  production-a getmir) — düzəlişi Cloudflare deploy pipeline-ına təsir
  edə biləcək `--force` breaking dəyişikliklər tələb etdiyi üçün ayrıca
  saxlanıldı. **Canlı yoxlandı**: real frontend (3000) yeni asılılıqlarla
  yenidən başladıldı, `vinext build`/`vinext dev` uğurlu, login səhifəsi
  düzgün render olundu, konsol xətası yox.

## 2026-08-09 — Canlı konsensus panelinin hərəkətli ortalamaları genişləndirildi (1 EMA → 8 SMA/EMA)

- İstifadəçi "davam et, plan üzrə" dedi. Bu münasibətlə əvvəlcə
  `PROJECT_ROADMAP.md` faktiki vəziyyətə uyğunlaşdırıldı (Phase 3/Phase 4
  checklist-ləri COMPLETED işarələndi — əvvəllər bütün SA-00x sətirləri
  `[ ]` göstərirdi, halbuki iş çoxdan bitmişdi). Sonra istifadəçiyə "növbəti
  böyük mərhələ Phase 5 (Visual AI)-yə başlayaqmı, yoxsa kiçik namizədlərdən
  birini seçəkmi" sualı verildi — "kiçik namizədlərdən biri" seçildi, sonra
  "canlı konsensus panelinin hərəkətli ortalamaları" seçildi.
- Yeni `backend/app/analysis/moving_averages.py`: `calculate_sma()` (yeni,
  causal, forward-fill yoxdur) + `build_moving_average_set()` — 4 sabit
  dövr (10/20/30/50) × SMA/EMA = 8 seriya (TradingView-un widget-indəki 8
  MA sətrinə uyğun). **`indicators.py`-a TOXUNMUR** (`oscillators.py`-ın
  əvvəlki artımda saxladığı eyni prinsip — bu, paylaşılan/stabil paket,
  digər bütün analiz modulları ona etibar edir). EMA-nın özü TƏKRAR
  yazılmayıb: `build_moving_average_set()` hər dövr üçün `indicators.py`-ın
  artıq mövcud `calculate_ema()`-sını birbaşa çağırır — kod bazasında
  yalnız BİR EMA implementasiyası qalır.
- `indicator_consensus.py`: `compute_indicator_consensus()` indi
  `moving_averages: MovingAverageSetResult` parametri qəbul edir və bütün
  8 seriyanı təsnifləndirir (əvvəlki tək EMA əvəzinə), mövcud generic
  `_classify_price_vs_average()` helper-indən istifadə edərək.
  `CONSENSUS_VERSION 2.0.0 → 3.0.0`.
- `live_analysis.py`: hərəkətli ortalama dəstini digər dəstlərin (indikator/
  osilator) yanında qurur, canlı xülasə cavabına yeni `moving_averages`
  sahəsi əlavə edir. `LIVE_ANALYSIS_API_VERSION 1.1.0 → 1.2.0`.
- Frontend: `live-technical-summary-panel.tsx` artıq `consensus.
  moving_averages`-i GENERIC şəkildə render edirdi (cədvəl və gauge hər
  ikisi array üzərində iterasiya edir, tək-elementli fərziyyə yox idi) —
  yalnız `indicatorLabel()` funksiyasına `sma.close.N` üçün `SMA (N)`
  formatı əlavə etmək kifayət etdi (`ema.close.N` artıq mövcud idi).
- **Canlı brauzerdə tam sınandı** (birdəfəlik scratch backend port 8003 +
  scratch SQLite (1,200 sintetik GOLD tick, son 60 dəqiqə — 50-dövrlük
  SMA/EMA-nın warm-up-dan çıxması üçün kifayət), birdəfəlik frontend port
  5173, real production 8000/3000 toxunulmadan): "Hərəkətli ortalamalar"
  cədvəli bütün 8 sətri real hesablanmış dəyərlərlə göstərdi (SMA/EMA ×
  10/20/30/50), sintetik yuxarı trendə uyğun 8/8 "yuxarı meyl"
  təsnifatı, gauge kartı düzgün cəmləndi, "bütün indikatorlar hazırdır"
  mətni göründü. Konsol xətası yox, polling 5 saniyəlik templə qaldı
  (yoxlama pəncərəsində 3 sorğu, storm yox).
- Yoxlama: yeni `test_moving_averages.py` (`8` test — əl ilə yoxlanmış
  SMA dəyərləri, dövr-altı `insufficient_data`, tam dəstdə dövr/tip
  sırası, xüsusi dövrlər, EMA-nın `indicators.py`-ın `calculate_ema()`-si
  ilə DƏQİQ eyni nəticəni verdiyinin təsdiqi, boş giriş, təhlükəsiz
  parametr rəddi, fingerprint determinizmi). `test_indicator_consensus.py`
  8-seriyalı fixture üçün yenidən yazıldı. `test_live_technical_summary_api.py`
  yeni API/consensus versiyalarına və `moving_averages` sahəsinə
  uyğunlaşdırıldı. `tests/live-technical-summary-ui.test.mjs`-ə
  `sma.close.`/`ema.close.` etiket dəstəyinin yoxlanması əlavə edildi.
  Tam backend regressiyası: `537 passed`. Frontend: lint təmiz, `17/17`
  test, production build uğurlu.

## 2026-08-09 — Job-queue-nun frontend səthi (pattern-candidate-backtest VƏ statistical-analysis job-ları)

- İstifadəçi seçdi: "Job-queue-nun frontend səthi (tövsiyə)" — hər iki
  job növünün artıq real işlək (VƏ real bazaya tətbiq edilmiş) async
  API-ları var idi, amma heç birinin UI-si yox idi.
- Yeni `frontend/app/async-job-panel.tsx`: ortaq, iki job növü arasında
  paylaşılan `useAsyncJob<TResult>()` hook-u:
  - `create(body)` — idempotency key (`crypto.randomUUID()`) ilə `POST`,
    tamamlanmayıbsa avtomatik poll başladır.
  - Poll: `GET .../{job_id}`, 2 saniyə aralıqla, son vəziyyətə çatana
    qədər (`completed`/`cancelled`/`failed`).
  - `cancel()` — `POST .../{job_id}/cancel`.
  - `onCompleted(result)` — **useEffect-dən DEYİL**, birbaşa poll/create
    handler-inin özündən çağırılır (React-in "effect body-də setState
    çağırma" lint qaydasına toxunmamaq üçün — ilk versiyada bu qaydaya
    toxunmuşdu, ESLint tutdu, `useAsyncJob`-a `onCompleted` parametri
    əlavə edərək düzəldildi).
  - `JobStatusBadge` (mövcud `.status-pill`/`.tone-*` CSS-dən istifadə
    edir) + `isJobCancellable()` helper-i.
- `statistical-analysis-panel.tsx`-ə: mövcud "Analizi hesabla" düyməsinin
  yanında yeni "Job kimi başlat (asinxron)" düyməsi (eyni forma
  state-indən istifadə edir). `onCompleted: setResult` — asinxron nəticə
  MƏHZ sinxron yolun istifadə etdiyi eyni state-ə axır, ona görə eyni 7
  SA kartı render olunur, ayrıca/təkrarlanan görünüş yoxdur.
- `pattern-candidates-panel.tsx`-ə: yeni `BacktestJobCell`
  sub-komponenti — hər qeydə alınmış namizəd sətri üçün AYRICA
  `useAsyncJob` nüsxəsi (hook-lar dövr içində birbaşa çağırıla bilmədiyi
  üçün alt-komponent lazım idi). "Job kimi backtest et" düyməsi mövcud
  sync "Backtest et" düyməsinin yanında. Tamamlandıqda eyni `backtests`
  state-i yenilənir və `loadRegistered()` çağırılır — sync yolla EYNİ
  nəticə göstərilir (ssenari siyahısı, lifecycle keçidi).
- Minimal yeni CSS: `.async-job-meta` (kiçik flex sətir — status
  badge/cəhd sayı/ləğv düyməsi), qalan hər şey mövcud class-lardan.
- **Canlı brauzerdə tam sınandı** (birdəfəlik scratch backend port 8002
  + scratch SQLite, birdəfəlik frontend port 5173 — port 5174 əvvəlcə
  sınandı, backend-in CORS allow-list-i (yalnız 3000/5173) tərəfindən
  rədd edildi, bu, gələcək sessiyalar üçün faydalı bir xatırlatmadır;
  real production 8000/3000 toxunulmadan): backend-in öz repository
  funksiyaları ilə tamamlanmış replay sessiyası + qeydə alınmış
  `structure_break_long` pattern namizədi yaradıldı.
  - "Job kimi backtest et" klikləndi: job_id `job_` prefiksi ilə qayıtdı
    (mövcud `analysis_jobs` cədvəli), bir poll dövründə tamamlandı,
    ssenari siyahısı və lifecycle vəziyyəti ("Backtest edilib") sync
    yolla eyni göründü, "Nəticələndir" düyməsi düzgün göründü.
  - Statistik analiz panelində M1-ə keçilib "Job kimi başlat (asinxron)"
    klikləndi: job_id `saj_` prefiksi ilə qayıtdı (yeni
    `statistical_analysis_jobs` cədvəli), tamamlandı, bütün 7 SA kartı
    M1-əsaslı dəyərlərlə yeniləndi (20 pəncərə, defolt M5-dəki 4-dən
    artıq) — asinxron nəticənin sync ilə EYNİ render yoluna axdığını
    təsdiqlədi.
  - Konsol xətası yox, sorğu storm-u yox hər iki halda.
- Yoxlama: yeni `tests/async-job-panel-ui.test.mjs` (3 test — hook
  export-ları mövcuddur və buy/sell dili yoxdur, hər iki panel hook-u öz
  job endpoint-inə bağlayır, statistik analiz panelinin `onCompleted`-i
  ortaq `setResult`-a axır). Frontend: lint təmiz, `17/17` test,
  production build uğurlu. Backend toxunulmayıb (hər iki job API-si
  əvvəlki artımda artıq göndərilib və sınanıb).

## 2026-08-09 — Migration `0010` və `0011` real bazaya tətbiq edildi

- İstifadəçi "platformanı yenidən işə sal" dedi, sonra migration
  `0011`-i real bazaya tətbiq etməyi açıq təsdiqlədi ("davam et").
  `tools/phase2-migrate-production.py --allow-production` istifadə
  edildi — bu, ehtiyat nüsxə götürür, BÜTÜN gözləyən migrasiyaları
  tətbiq edir (yalnız istənilən biri deyil), `quick_check` doğrulayır.
  Nəticədə **həm `0010` (Phase 9-un `shadow_theoretical_positions`
  cədvəli, əvvəllər tətbiq edilməmiş qalmışdı) HƏM `0011`
  (`statistical_analysis_jobs`/`statistical_analysis_job_audit`)** eyni
  icrada tətbiq olundu.
- Doğrulama: tətbiqdən əvvəl/sonra `tick_events` sayı dəyişməz
  (2,419,520), `replay_sessions` sayı dəyişməz (7), `PRAGMA quick_check`
  həm ehtiyat nüsxədə həm tətbiq edilmiş bazada `ok`. Hər iki migrasiya
  yalnız əlavəedici (`CREATE TABLE`/`CREATE INDEX`/`CREATE TRIGGER`,
  heç bir `DROP`/`DELETE`/`UPDATE` yoxdur).
- Real backend/frontend `tools/stop-local-platform.ps1` →
  `start-local-platform.ps1` ilə yenidən başladıldı (MT5 Bridge FIFO
  buferini qorumaq üçün). Doğrulama: `/health` `200`, yeni `POST .../
  statistical-analysis-jobs` endpoint-i etibarsız sessiya ilə `401`
  qaytardı (`no such table` YOX) — yeni cədvəllərin canlı və əlçatan
  olduğunu təsdiqlədi.
- Ehtiyat nüsxə: `.runtime/phase2-migration/ESAS_PLATFORM-before-phase2-<timestamp>.sqlite`
  (`.gitignore`-da, commit edilmir).
- Bu, kod dəyişikliyi deyil — commit/push tələb olunmur, yalnız real baza
  vəziyyəti dəyişdi.

## 2026-08-09 — Phase 3 statistik analiz üçün async job/persistence resursu

- İstifadəçi seçdi: "Async job resursu (tövsiyə)" — SA-001-SA-007 VƏ
  frontend paneli tamamlandıqdan sonra. Müqavilənin `POST /api/v2/
  statistical-analyses` konseptual resursu — statistik analiz indiyədək
  sinxron və DB-siz-nəticə idi (pattern-candidate backtest-lərin əksinə,
  onun artıq job-queue-su var idi).
- **İcrası zamanı real maneə aşkarlandı:** `analysis_jobs` (migration
  `0007`) job-queue üçün eyni struktura malikdir, AMMA onun `job_type`
  CHECK məhdudiyyəti yalnız `'pattern_candidate_backtest'`-i qəbul edir
  və bu migration ARTIQ real production bazasına tətbiq edilib. Bu
  platformanın migration sistemi təhlükəsizlik səbəbindən `DROP`/
  `DELETE`/`UPDATE` statement-lərini tamamilə qadağan edir — deməli CHECK
  məhdudiyyətini genişləndirmək üçün standart SQLite üsulu (cədvəli
  yenidən qurmaq) bu sistemdə mümkün deyil. İstifadəçiyə açıq bildirildi,
  3 seçim təklif edildi; "yeni ayrıca cədvəl + repository-ni
  ümumiləşdir" seçildi.
- Yeni migration `0011_statistical_analysis_jobs.sql`: `statistical_
  analysis_jobs` cədvəli — `analysis_jobs` ilə eyni struktur, AMMA
  `CHECK (job_type = 'statistical_analysis')`, öz append-only
  `statistical_analysis_job_audit` cədvəli və indeksləri ilə.
- `backend/app/database/analysis_job_repository.py` **cədvəl-ad-
  marşrutlaşdırmasına ümumiləşdirildi** — sərt şəkildə `analysis_jobs`-a
  bağlı olmaq əvəzinə, hər job növü öz (job cədvəli, audit cədvəli,
  job_id prefiksi) üçlüyünə uyğunlaşdırılıb. Yalnız `job_id` ilə işləyən
  funksiyalar (`get_job`, `send_heartbeat`, `complete_job`, `fail_job`,
  `request_cancel`) `job_id`-nin prefiksinə görə düzgün cədvələ
  yönləndirilir (`job_` — pattern-candidate-backtest, DƏYIŞMƏDƏN, real
  bazadakı mövcud sətirlərlə geriyə uyğunluq üçün; `saj_` — statistical-
  analysis, yeni) — əlavə sorğu və ya əlavə parametrə ehtiyac olmadan.
  `queue_metrics()` indi dəstəklənməyən `job_type`-ı da rədd edir (əvvəllər
  səssizcə boş nəticə qaytarırdı). Faydalı yan effekt: hər-istifadəçi
  aktiv-job həddi indi hər job-növü ailəsi üçün təbii olaraq müstəqildir
  (hər ailənin öz cədvəli olduğu üçün).
- `backend/app/workers/analysis_job_worker.py`: yeni
  `_run_statistical_analysis_job()` handler-i
  `create_replay_statistical_analysis()`-ə göndərir; mövcud
  qeyri-təkrarlanan-xəta siyahısı bu handler-in ata biləcəyi bütün
  xətaları artıq əhatə edirdi (yeni idxal yalnız).
- Yeni `backend/app/models/statistical_analysis.py`
  (`StatisticalAnalysisJobRequest`) və 3 yeni endpoint — mövcud
  pattern-candidate-backtest job endpoint-lərinin DƏQİQ eyni nümunəsi:
  `POST .../statistical-analysis-jobs` (202, növbəyə əlavə edir +
  `BackgroundTask` növbəni boşaldır), `GET .../statistical-analysis-jobs/
  {job_id}` (status, tamamlandıqdan sonra tam statistik analiz nəticəsi —
  ayrıca "nəticələr" endpoint-i yoxdur, mövcud job növü ilə eyni), `POST
  .../statistical-analysis-jobs/{job_id}/cancel`.
- **Yolüstü tapılıb düzəldilən real bug:** mövcud sinxron `GET .../
  statistical-analysis` endpoint-inin `timeframe` sorğu parametri regex-i
  köhnə idi (yalnız `S1|S10|M1|M5|M15|H1` — `bars.py`-a SA-004-dən
  bəri əlavə edilmiş `M30`/`H4`/`D1` YOX idi) — bu, yeni frontend
  panelinin taymfreym seçicisinin təklif etdiyi 3 dəyərin backend
  tərəfindən `422` ilə rədd edilməsi demək idi. `bars.py`-ın faktiki
  `TIMEFRAME_SECONDS`-ına uyğunlaşdırıldı.
- Yoxlama: `test_migration_runner.py` yeni migration sayına uyğunlaşdırıldı.
  `test_analysis_job_repository.py`-a 5 yeni test (ayrıca-cədvəl
  marşrutlaşdırması, yeni cədvəl üzərindən tam lifecycle, iki ailə
  arasında job_id toqquşma təhlükəsizliyi, müstəqil queue metrikaları,
  dəstəklənməyən job_type rəddi). Yeni `test_statistical_analysis_jobs_api.py`
  (7 test, mövcud pattern-candidate-backtest job API test faylının eyni
  nümunəsi ilə). Tam backend regressiyası: `528 passed`. **Real işləyən
  production backend-də restart-dan sonra yoxlanıldı**: yeni route `401`
  qaytarır (`404` yox) — kodun düzgün yükləndiyini təsdiqləyir. (Yazıldığı
  zaman migration `0011` real bazaya hələ tətbiq edilməmişdi; eyni gün,
  aşağıdakı qeyddə göründüyü kimi, istifadəçinin təsdiqi ilə tətbiq
  edildi.) Frontend toxunulmayıb (backend-only, API-səviyyəli artım, UI
  dəyişikliyi yoxdur).

## 2026-08-07 — Phase 3 SA-001-SA-007 üçün frontend panel

- İstifadəçi seçdi: "Frontend panel (tövsiyə)" — SA-001-SA-007 tamamlandıqdan
  sonra heç birinin UI-si olmadığı üçün bu, async job resursundan və digər
  "yalnız istəsə" namizədlərdən üstün tutuldu.
- Yeni `frontend/app/statistical-analysis-panel.tsx`: mövcud
  `technical-analysis-panel.tsx`/`replay-panel.tsx` axınının eyni
  konvensiyası (replay sessiyası seçimi → tamamlanmış sessiya tələbi →
  forma + nəticə kartları). Yeni "Statistik analiz" menyu bəndi
  (`dashboard-navigation.tsx`-də "Araşdırma" qrupunda, "Texniki
  göstəricilər"-in yanında).
  - Forma: vaxt çərçivəsi (S1-D1) + minimum nümunə həddi.
  - 7 kart: SA-001 (gəlir seriyası), SA-002 (volatilite — range/log-return/
    tick-to-tick return/robust MAD), SA-003 (spread), SA-004 (tick sürəti),
    SA-005 (tick-volume + flag cədvəli), SA-007 (rejim cədvəli, "ixtiyari
    ad" xəbərdarlığı ilə), SA-006 (UTC saat cədvəli, `calendar_unavailable`
    məhdudiyyəti + "adlandırılmış sessiya deyil" xəbərdarlığı ilə).
  - Mövcud `.analysis-card`/`.analysis-controls`/`.research-pill`/
    `.table-wrap` CSS-indən istifadə edir — yeni CSS əlavə edilmədi.
- **Canlı brauzerdə tam sınandı** (birdəfəlik scratch backend port 8001-də
  + scratch SQLite bazası, birdəfəlik frontend port 5173-də, real
  production backend/frontend 8000/3000 toxunulmadan): 1,100 sintetik
  GOLD tick (3s aralıqla, 55 dəqiqə, ossilasiya edən qiymət, dəyişən
  volume/flags) bazaya əlavə edildi, backend-in öz repository
  funksiyaları ilə (create→start→run_max_speed_replay) real `completed`
  replay sessiyası yaradıldı. Brauzerdə daxil olundu, "Statistik analiz"
  bölməsi açıldı:
  - Defolt M5-də (11 pəncərə, defolt minimum 30-dan az): bütün
    pəncərə-əsaslı bölmələr düzgün `insufficient_data`, AMMA tick-səviyyəli
    metriklər (tick-to-tick return, tick interval) öz 1,099-nöqtəlik
    nümunəsi ilə düzgün `completed` — bu, dizaynın tam gözlədiyi
    fərqləndirmədir.
  - M1-ə keçdikdə (55 pəncərə): bütün 7 bölmə `completed`, real
    hesablanmış dəyərlərlə — 8 fərqli rejim (nisbətləri tam 100%-ə
    cəmlənir), flag cədvəli sintetik məlumatdakı 977/123 bölgüsünə dəqiq
    uyğun, tək UTC 08:00 saat qrupu real 95% etibar intervalı ilə.
  - Konsol xətası yox, sorğu axını təmiz (hər vaxt-çərçivəsi dəyişikliyinə
    bir sorğu, storm yox).
- Yoxlama: yeni `tests/statistical-analysis-ui.test.mjs` (mənbə-mətn
  qoruması — TƏDQİQAT banneri, buy/sell dili yox, rejim/sessiya
  xəbərdarlıqları mövcud, bütün 7 SA-00x işarəsi mövcud).
  `tests/dashboard-navigation.test.mjs` yeni bölmə üçün yeniləndi.
  Frontend: lint təmiz, `14/14` test, production build uğurlu.
- **Bu artımla Phase 3-ün SA-001-SA-007 müqaviləsi HƏM backend HƏM
  frontend baxımından tam əhatə olunur.**

## 2026-08-07 — Phase 3 SA-006: sessiya müqayisəsi (təqvim-yoxdur deqradasiya rejimi) — SA-001-SA-007 tamamlandı

- İstifadəçi "davam et" dedi. SA-007-dən sonra qalan yeganə Phase 3
  namizədi SA-006 idi. Müqavilə versiyalanmış simvol/broker təqvimi
  (timezone, DST, həftəsonu/bayram, üst-üstə düşən sessiya prioriteti)
  tələb edir, AMMA təqvim olmadıqda özü açıq bir deqradasiya rejimi
  müəyyənləşdirir: "Təqvim yoxdursa yalnız UTC saat dilimləri göstərilir
  və `calendar_unavailable` məhdudiyyəti yazılır. UTC saat statistikası
  'London', 'New York' və ya başqa bazar sessiyası adlandırılmır."
  Platformada real broker təqvimi olmadığı üçün bu artım MƏHZ bu
  deqradasiya rejimini tətbiq etdi — uydurma təqvim qurulmadı, istifadəçi
  ilə ayrıca dizayn müzakirəsinə ehtiyac olmadı (müqavilənin özü fallback-i
  tam təyin edib).
- Yeni `backend/app/analysis/session_comparison.py`:
  `compute_session_comparison()` — pəncərələri `start_at`-ın xam UTC
  saatına (0-23) görə qruplaşdırır (heç bir adlandırılmış sessiya YOX).
  Hər saat qrupu üçün: return orta/median/standart sapma + ortalama
  üzərində 95% etibar intervalı (`Z_95=1.96 * std/√n`, digər modullardakı
  eyni CI konvensiyası), nümunə sayı, orta nisbi range (volatilite
  proksisi). Hamısı artıq mövcud `bars.py`/`return_series.py`
  nəticələrindən hesablanır — yeni xam-tick keçidi YOX.
  `calendar_unavailable: true` və məhdudiyyət mətni HƏR CAVABDA mövcuddur
  (gözdən qaçırıla bilməz). Qruplar arası fərq açıq şəkildə "yalnız bu
  dataset-in təsviri, ticarət üstünlüyü deyil" kimi sənədləşdirilib
  (həm docstring-də, həm cavab formasında).
- `statistical_analysis.py`-a inteqrasiya: yeni `sessions` sahəsi.
  `STATISTICAL_ANALYSIS_API_VERSION 1.6.0 → 1.7.0`.
- Frontend toxunulmayıb (Phase 3-ün digər addımları ilə eyni ardıcıllıq).
- Yoxlama: yeni `test_session_comparison.py` (`9` test — məhdudiyyət
  mətninin həmişə mövcudluğu, UTC-saat qruplaşdırılması (adlandırılmış
  sessiya yox), əl ilə yoxlanmış orta/median/CI (4-pəncərəlik fixture),
  hər qrup üçün ayrı insufficient_data həddi, boş giriş, fingerprint
  determinizmi, uyğunsuz simvol rəddi, təhlükəsiz parametr rəddi).
  `test_replay_technical_analysis_api.py` yeniləndi (`api_version 1.7.0`,
  `sessions` sahəsi, həm `completed` həm `insufficient_data` hallarında).
  Tam backend regressiyası: `516 passed`.
- **Bu artımla Phase 3-ün SA-001-SA-007 statistik analiz müqaviləsi tam
  əhatə olunur** (SA-006 təqvim-yoxdur deqradasiya rejimində). Qalan:
  real broker təqvimi qurulsa SA-006-nı "rəsmi" rejimə keçirmək (yalnız
  istifadəçi ayrıca istəsə), async job/persistence resursu
  (`POST /api/v2/statistical-analyses`) və frontend paneli (heç bir
  SA-00x-in hələ UI-si yoxdur).

## 2026-08-07 — Phase 3 SA-007: bazar rejimi namizədləri

- İstifadəçi "davam et" dedi. SA-006 (sessiya müqayisəsi) versiyalanmış
  simvol/broker təqvimi tələb etdiyi üçün daha böyük, yeni infrastrukturlu
  iş idi; SA-007 isə artıq tamamlanmış SA-001/002/003-ün üzərində qurula
  bilirdi (yeni xam-tick keçidi tələb etmir) — istifadəçiyə iki seçim
  təklif edildi, SA-007 seçildi.
- Yeni `backend/app/analysis/regime_candidates.py`:
  `compute_regime_candidates()` — hər pəncərəni artıq mövcud 4 feature
  üzrə təsnifləndirir:
  - **Volatilite** (pəncərə range-i/open), **spread** (pəncərə orta
    spread-i, bps) və **tick sürəti** (pəncərə tick sayı) hər biri dataset
    DAXİLİNDƏ median split ilə `low`/`high`-a bölünür — universal və ya
    illikləşdirilmiş hədd YOXDUR, ona görə bir "tier" yalnız EYNİ icra
    daxilində mənalıdır, fərqli icralar arasında müqayisə edilə bilməz.
  - **Return istiqaməti**: pəncərənin log-return işarəsindən `up`/`down`/
    `flat`; tək-tick pəncərə üçün (hesablanan return yoxdur) `unknown`.
  - Müşahidə olunan hər fərqli (volatilite, spread, tick-sürəti,
    istiqamət) kombinasiyası ixtiyari, leksikoqrafik sıralı `regime_N`
    etiketi alır — müqavilə açıq tələb edir ki, rejim adları ("trend",
    "range", "riskli") ayrıca validasiya olunmadan iqtisadi məna
    daşımasın, bura heç bir belə validasiya edilməyib. Nəticədə **rejim
    etiketləri fərqli dataset-lər və ya fərqli pəncərə dəstləri arasında
    SABİT DEYİL** — yalnız hər rejimə bağlı feature tuple-ı müqayisə
    edilə bilər.
  - `data_quality_status` — bütün sessiyanın Phase 2 keyfiyyət statusu
    (`pass`/`review`/`fail`), REAL `create_replay_quality_report()`
    çağırışından (Phase 4-ün `blocked_by_data_quality` qapısında
    istifadə olunan EYNİ funksiya) — bütün pəncərələrə eyni tətbiq
    olunur, çünki platforma per-pəncərə keyfiyyət izləmir, yalnız
    sessiya-səviyyəli.
- `statistical_analysis.py`-a inteqrasiya: yeni `regimes` sahəsi, yeni
  keyfiyyət-hesabatı çağırışı (yeni tick keçidi YOX — bu modul yalnız
  artıq qurulmuş bar-lar/return_series üzərində işləyir).
  `STATISTICAL_ANALYSIS_API_VERSION 1.5.0 → 1.6.0`.
- Frontend toxunulmayıb (Phase 3-ün digər addımları ilə eyni ardıcıllıq).
- Yoxlama: yeni `test_regime_candidates.py` (`7` test — əl ilə qurulmuş
  4-kvadrant fixture: 2 bar aşağı volatilite/spread/tick-sürəti (return
  up/down fərqli), 2 bar yuxarı (return down/up fərqli) — median split-in
  dəqiq nəticəsi VƏ leksikoqrafik regime təyini (`"high..."` < `"low..."`
  əlifba sırasına görə) əl ilə doğrulanıb; tək-tick `unknown` istiqamət;
  insufficient_data həddi; etibarsız keyfiyyət-statusu rəddi; uyğunsuz
  simvol rəddi; təhlükəsiz parametr rəddi). `test_replay_technical_
  analysis_api.py` yeniləndi (`api_version 1.6.0`, `regimes` sahəsi, həm
  `completed` həm `insufficient_data` hallarında). Tam backend
  regressiyası: `507 passed`.

## 2026-08-07 — Phase 3 SA-002 tamamlanması: tick-to-tick return standart sapması

- İstifadəçi "davam et" dedi — SA-005-in davamı olaraq, əvvəllər SA-002
  ilk təqdim edildikdə (2026-08-06) qəsdən kənarda saxlanmış hissə
  (tick-to-tick, pəncərəsiz return standart sapması) indi SA-004/005-in
  açdığı xam-tick oxuma formasından istifadə edərək tamamlandı — bu, ən
  kiçik, "artıq açıq qalmış işi bağlayan" addım idi (SA-006 versiyalanmış
  təqvim, SA-007 isə SA-002-005-dən asılı olduğu üçün daha böyükdür).
- `backend/app/analysis/volatility.py`: `compute_volatility()` indi əlavə
  olaraq xam `ticks` (+ `start_at`/`end_at`) qəbul edir, yeni `tick_return`
  sahəsi qaytarır — hər ardıcıl tick cütünün mid-price-ından hesablanan
  log-return-un paylanması (say/orta/median/std/min/maks/p05/p95).
  `tick_rate.py`/`tick_volume.py`-dan **fərqli** olaraq (onlar bütün
  tick-ləri sayır, qiymət etibarlılığından asılı olmadan) bu, özü bir
  QİYMƏT seriyasıdır, ona görə `bars.py`-ın mid-price etibarlılıq filtrini
  (bid/ask müsbət, sonlu, ask≥bid) irsən alır. `VOLATILITY_VERSION
  1.0.0 → 1.1.0`.
- `statistical_analysis.py`-a inteqrasiya (dördüncü ayrıca
  `iter_tick_batches` keçidi), `STATISTICAL_ANALYSIS_API_VERSION
  1.4.0 → 1.5.0`.
- Frontend toxunulmayıb (Phase 3-ün digər addımları ilə eyni ardıcıllıq).
- Yoxlama: `test_volatility.py` yeni tələb olunan parametrlərə uyğun
  yeniləndi + 4 yeni test (sabit-return fixture-u — hər tick-to-tick
  log-return dəqiq 0.01, etibarsız bid/ask-ın xaric edilməsi, uyğunsuz
  simvol rəddi, təhlükəsiz start/end rəddi). `test_replay_technical_
  analysis_api.py` yeniləndi (`api_version 1.5.0`, `tick_return` sahəsi —
  həm də göstərir ki, eyni cavabda pəncərə-səviyyəli metriklər
  `insufficient_data` olsa belə, tick-səviyyəli metrik fərqli nümunə
  ölçüsü ilə `completed` ola bilər). Tam backend regressiyası:
  `500 passed`.

## 2026-08-07 — Phase 3 SA-005: tick-volume və flags

- İstifadəçi "davam et" dedi — SA-004-ün birbaşa davamı olaraq SA-005
  (tövsiyə edilən növbəti addım idi: SA-004-ün açdığı xam-tick oxuma
  formasını birbaşa paylaşır, SA-006 versiyalanmış təqvim tələb edir,
  SA-007 əvvəlki SA-002-005-dən asılıdır).
- Yeni `backend/app/analysis/tick_volume.py`: `compute_tick_volume_statistics()`
  — mövcud `volume` sahəsi **MT5 tick-volume** kimi etiketlənir (müqavilə
  onu real birja həcmi, order-book dərinliyi və ya icra edilə bilən
  likvidlik hesab etmir). `tick_rate.py` ilə eyni dizayn: xam tick-lər
  üzərində birbaşa işləyir, `bars.py`-ın bid/ask etibarlılıq filtri
  tətbiq edilmir (volume/flags qiymət keyfiyyətindən asılı deyil).
  - `tick_volume`: hər tick-in xam volume dəyərinin paylanması (bütün
    tick-lər, sıfır daxil) + ayrıca `n_zero_volume`/`n_positive_volume`
    sayları.
  - `window_volume_sum`: dolu (epoch-aligned) pəncərə üzrə bir nöqtə —
    həmin pəncərənin ümumi volume-u, SA-003/004-ün "pəncərə başına bir
    nöqtə, boş pəncərə sıfırla doldurulmur" konvensiyası ilə eyni.
  - `flag_combinations`: müşahidə olunan xam `flags` dəyərləri və sayları,
    **ŞÜURLU ŞƏKİLDƏ deşifr edilmədən** — müqavilə flags semantikasının
    ayrıca versiyalanmış MT5 bit mapping olmadan şərh edilməməsini tələb
    edir, platformada belə bir mapping yoxdur.
  - `version_segments`: `module_version`/`event_version` cütü üzrə say —
    aralığın bridge/schema yenilənməsini əhatə edib-etmədiyini göstərir.
- `statistical_analysis.py`-a inteqrasiya: SA-001-004 ilə eyni
  orkestratora əlavə edildi (üçüncü ayrıca `iter_tick_batches` keçidi),
  yeni `tick_volume` sahəsi. `STATISTICAL_ANALYSIS_API_VERSION
  1.3.0 → 1.4.0`.
- Frontend toxunulmayıb (SA-001-004 ilə eyni ardıcıllıq).
- Yoxlama: yeni `test_tick_volume.py` (`9` test — əl ilə yoxlanmış
  persentillər, sıfır/müsbət volume ayrı sayımı, pəncərə-cəm bucketing-i,
  flag kombinasiyası sıralaması, versiya-seqment qruplaşdırılması, boş
  giriş, fingerprint determinizmi, təhlükəsiz parametr rəddi).
  `test_replay_technical_analysis_api.py` yeniləndi (`api_version 1.4.0`,
  `tick_volume` sahəsi, həm `completed` həm `insufficient_data`
  hallarında). Tam backend regressiyası: `496 passed`.

## 2026-08-07 — Phase 3 SA-004: tick sürəti və interval

- İstifadəçi "platformanı qaldığımız yerdən düzəldək" dedi — SA-003-dən
  sonra Phase 3-ün növbəti addımı olaraq seçim təklif edildi, istifadəçi
  **SA-004 (tick sürəti)**-ni seçdi (tövsiyə edilən seçim idi: SA-005
  eyni xam-tick keçidini tələb edir, SA-006 versiyalanmış təqvim tələb
  edir — daha böyük iş, SA-007 əvvəlki SA-002-005-dən asılıdır).
- Yeni `backend/app/analysis/tick_rate.py`: `compute_tick_rate_statistics()`
  — Phase 3-də **İLK dəfə** xam tick-lər üzərində birbaşa işləyən modul
  (SA-001/002/003-ün hamısı yalnız `bars.py`-ın artıq qurduğu bar-lar
  üzərində işləyirdi, çünki bu, mid-price seriyası tələb edirdi). Tick
  sürəti isə qiymət keyfiyyətindən asılı deyil (feed-in özünün xüsusiyyəti),
  ona görə `bars.py`-ın bid/ask müsbətlik/etibarlılıq filtri **qəsdən
  tətbiq edilmir** — parse oluna bilən timestamp-i olan HƏR tick sayılır.
  - `window_tick_count` / `window_ticks_per_second`: hər dolu pəncərənin
    (bars.py ilə eyni epoch-aligned pəncərə tərifi) öz tick sayı/saniyə
    başına tick-i bir populyasiya nöqtəsi kimi, SA-003-ün pəncərə-üzrə
    spread aqreqasiyası ilə eyni konvensiya.
  - `interval_seconds`: kanonik sıralanmış ardıcıl tick-lər arasındakı
    fərq (saniyə), **bütün sorğu aralığı üzrə** aqreqasiya edilir (pəncərə-
    üzrə deyil — tək pəncərədə adətən öz persentili üçün kifayət qədər
    tick olmur).
  - `same_timestamp_tick_count`: sıfır-saniyəlik fərqlərin sayı.
  - `total_window_count` / `populated_window_count` / `empty_window_count`
    — həmişə göstərilir, `minimum_sample` həddindən asılı deyil. **Şüurlu
    şəkildə buraxılıb:** ayrıca "qismən sərhəd pəncərəsi" sayı (modulun öz
    docstring-ində izah olunub — epoch-aligned pəncərələmə artıq
    `start_at`/`end_at` ilə kəsilən pəncərəni digərləri kimi eyni cür
    rəftar edir, `bars.py` da eyni şeyi edir).
- `statistical_analysis.py`-a inteqrasiya: SA-001/002/003 ilə eyni
  orkestratora əlavə edildi, yeni `tick_rate` sahəsi. Bar-qurma
  generator-u artıq istehlak olunduğu üçün ikinci ayrıca
  `iter_tick_batches` keçidi əlavə edildi (liquidity_overview.py-ın hər
  taymfreym üçün ayrıca sorğu konvensiyası ilə eyni yanaşma).
  `STATISTICAL_ANALYSIS_API_VERSION 1.2.0 → 1.3.0`.
- Frontend toxunulmayıb (SA-001/002/003-lə eyni ardıcıllıq — bu endpoint-in
  hələ UI-si yoxdur).
- Yoxlama: yeni `test_tick_rate.py` (`8` test — SA-003-ün 30-qiymətlik
  fixture formasını təkrar istifadə edən əl ilə yoxlanmış interval
  persentilləri, pəncərə bucketing-i, boş pəncərə sayımı, eyni-timestamp
  sayımı, aralıqdan kənar tick-lərin xaric edilməsi, fingerprint
  determinizmi, təhlükəsiz parametr rəddi).
  `test_replay_technical_analysis_api.py` yeniləndi (`api_version 1.3.0`,
  `tick_rate` sahəsi, həm `completed` həm `insufficient_data` hallarında).
  Tam backend regressiyası: `488 passed`.

## 2026-08-07 — Phase 3 SA-003: spread davranışı

- İstifadəçi "sistemin ümumi düzəlişinə qaldığımız yerdən davam edək"
  dedi — TradingView-dan ilhamlanan canlı konsensus/likvidlik paneli
  (indi bitmiş) əlavə/yan iş idi; əsas xətt Phase 3-dür. SA-003 (spread
  davranışı) seçildi — SA-002-dən sonra roadmap-ın növbəti məntiqi addımı.
- Yeni `backend/app/analysis/spread.py`: `compute_spread_statistics()` —
  `bars.py`-ın ARTIQ hər pəncərə üçün causal olaraq saxladığı
  `spread_min`/`spread_max`/`spread_mean`-dan istifadə edir (yeni xam-tick
  keçidi TƏLƏB OLUNMADI). Hər pəncərənin öz `spread_mean`-ini (mütləq, VƏ
  `spread_mean/close*10000` ilə bps-lə nisbi) populyasiya nöqtəsi kimi
  götürüb, bütün pəncərələr üzərində say/orta/median/std/min/maks/
  p05/p25/p75/p95/p99 hesablayır (`n≥30` həddi, aşağıda `insufficient_data`).
  **Şüurlu şəkildə buraxılıb:** `spread_points` (point/digit-lə ölçülən
  variant) — platformada təsdiqlənmiş simvol point/digit metadata mənbəyi
  yoxdur, müqavilə bunu "yoxdursa uydurulmur" deyə açıq qadağan edir.
- `statistical_analysis.py`-a inteqrasiya: SA-001/SA-002 ilə eyni
  orkestratora (`create_replay_statistical_analysis`) əlavə edildi, yeni
  `spread` sahəsi. `STATISTICAL_ANALYSIS_API_VERSION 1.1.0 → 1.2.0`.
- Frontend toxunulmayıb (bu endpoint-in hələ UI-si yoxdur — SA-001/SA-002
  artımlarında da eyni ardıcıllıq izlənilib).
- Yoxlama: yeni `test_spread.py` (`6` test — 30 nümunəlik əl ilə
  yoxlanmış persentillər (p05/p25/p75/p95/p99 dəqiq hesablanıb),
  `insufficient_data` həddi, nisbi spread-in qiymətlə düzgün miqyaslanması,
  boş giriş, fingerprint determinizmi, təhlükəsiz parametr rəddi).
  `test_replay_technical_analysis_api.py` yeniləndi (`api_version 1.2.0`,
  `spread` sahəsi). Tam backend regressiyası: `480 passed`.

## 2026-08-07 — Tarixi hərəkət diapazonu (excursion range) — "proqnoz" tələbinin tədqiqat-dilli qarşılığı

- İstifadəçi (real backend/frontend restart edilib jurnal göstərildikdən
  sonra) dedi: hazırkı analiz "faktiki qalxış/düşüş" göstərir, amma
  **"gələcəyi proqnoz etmək"** lazımdır — "filan nöqtədən filan nöqtəyə
  qədər düşüş/qalxış gözlənilir" formasında. **Bu, əvvəlki iki dəfə
  müzakirə edilən eyni sərhəddir** — "gözlənilir" sözü ilə konkret qiymət
  hədəfi vermək artıq proqnozdur (Phase 8 mövzusu). İstifadəçiyə iki
  seçim təklif edildi: (1) tarixi hərəkət aralığı (backward-looking,
  "keçmişdə belə olub") — tövsiyə edilən, (2) hərfi "gözlənilir" dili.
  İstifadəçi **tarixi hərəkət aralığını** seçdi.
- `backend/app/analysis/liquidity_reaction.py`: yeni `ExcursionDistribution`
  dataclass-ı — hər tərəf (`buy_side`/`sell_side`) üçün, HƏM `reversed`
  HƏM `continued` nəticələr üçün ayrıca, tarixi `excursion_bps`
  (artıq mövcud `ReactionEvent.excursion_bps`-dən) paylanmasının median/
  p25/p75/p90 persentilləri (`n≥30` həddi, aşağıda `insufficient_data`).
  `ReactionStatistics`-ə `reversed_excursion`/`continued_excursion`
  sahələri əlavə edildi. `REACTION_VERSION 1.1.0 → 1.2.0`.
  `liquidity_reaction_segments.py`-ın `_baseline_statistics`-i də uyğun
  yeniləndi (`SEGMENT_VERSION 1.1.0`).
- Frontend: `liquidity-overview-panel.tsx`-ə hər tərəf üçün 2 yeni cümlə
  ("Geri qayıtdıqda hərəkət:.../Keçdikdə hərəkət:...") — point/bps
  formatında p25–p75 aralığı, median, n. **Hər cümlənin sonunda məcburi
  xəbərdarlıq: "Bu, gələcək proqnoz deyil — keçmiş toxunmaların tarixi
  hərəkət diapazonudur."** — bu, yalnız stilistik seçim deyil, source-text
  guard testi ilə də kilidlənib (`gələcək proqnoz deyil` mütləq olmalıdır,
  `gözlənilir` sözü isə mütləq olmamalıdır).
- **Canlı brauzerdə tam sınandı** (mövcud 15 günlük sintetik data ilə,
  birdəfəlik test backend/frontend, real bazaya toxunmadan): real hesablanan
  dəyərlər (məs. M30 buy_side reversed: median 32bps/13.77 point, p25-p75
  15-32bps) brauzerdə dəqiq eyni mətnlə göründü, hər cümlənin sonunda
  xəbərdarlıq mövcud idi, konsol xətası yox. Real production backend/
  frontend (8000/3000) sınaq boyu toxunulmadan işlədi.
- Backend `474 passed`. Frontend: lint təmiz, `13/13` test, production
  build uğurlu.

## 2026-08-07 — Likvidlik sisteminin qalan 3 addımı: çox-taymfreym UI, özü-öyrənən seqmentasiya, jurnal

- İstifadəçi əvvəlki artımdan sonra "1-dən başlayaq, soruşma, hamısını
  edək" dedi — yəni bütün 4 addımı (çox-taymfreym orkestrasiyası, canlı UI,
  özü-öyrənən sistem, jurnal) ara-sıra təsdiq soruşmadan ardıcıl tamamlamaq
  tapşırığı. Tədqiqat dili (yuxarı/aşağı meyl, "alış/satış" yox) qaydası
  eyni qaldı.
- Yeni `backend/app/analysis/liquidity_reaction_segments.py`
  (**"özü öyrənən sistem"**): `find_indicator_segments()` — hər toxunma
  anındakı RSI/Stochastic/ADX oxusunu (artıq mövcud `indicators.py`/
  `oscillators.py`-dan, `ReactionEvent.bar_index` ilə uyğunlaşdırılır) 5
  sabit şərtlə (`rsi_oversold/overbought`, `stochastic_oversold/overbought`,
  `adx_trending`) yoxlayır, hər şərtin tarixi geri-qayıtma faizini bazaya
  qarşı müqayisə edir. **5 şərt eyni məlumat üzərində sınandığı üçün**
  Bonferroni-düzəlişli etibar intervalı istifadə olunur
  (`alpha=(1-0.95)/5`, `NormalDist().inv_cdf`) — düzəlişsiz sınaqda təsadüfən
  "əhəmiyyətli" görünən şərt tapmaq riski aradan qalxır. Şərt yalnız
  düzəlişli CI-nın aşağı sərhədi bazanın nöqtə qiymətindən yuxarı olduqda
  "bazadan üstündür" sayılır. `ReactionEvent`-ə `bar_index` sahəsi əlavə
  edildi (`REACTION_VERSION 1.0.0 → 1.1.0`).
- Yeni `backend/app/analysis/liquidity_overview.py`
  (**çox-taymfreym orkestrasiyası**): `create_liquidity_overview()` — 4
  taymfreymi (`M30/H1/H4/D1`) paralel emal edir, hər biri üçün canlı bar
  qurur (replay sessiyası tələb etmir, `live_analysis.py` ilə eyni
  arxitektur), `market_structure` → trend (`bullish`/`bearish`/`neutral`),
  `liquidity_sweep` → pool-lar → ən yaxın müqavimət/dəstək (cari qiymətdən
  məsafə bps-lə), `liquidity_reaction` → reaksiya statistikası,
  `liquidity_reaction_segments` → seqment nəticələri. Yeni qorunan
  `GET /api/v2/liquidity-overview` endpoint-i (`symbol`, `horizon_bars`,
  `reaction_threshold_bps`).
- Frontend: yeni `liquidity-overview-panel.tsx` — "Nəticələr" əsas
  ekranında, `live-technical-summary-panel`-in altında. Hər taymfreym üçün
  kart: trend pill-i, cari qiymət, ən yaxın müqavimət/dəstək (point və bps
  ilə), tədqiqat dilli reaksiya cümləsi ("tarixən X% geri qayıdıb, 95% CI
  ...", "alış/satış gözlənilir" YOXDUR), bazadan üstün seqmentlərin siyahısı
  (yalnız `exceeds_baseline=true` olanlar göstərilir), və **jurnal**
  (`<details>`, son 30 toxunma: vaxt, səviyyə, nəticə, point/bps) —
  istifadəçinin "jurnalı olsun" tələbinin dəqiq qarşılığı, yeni backend
  infrastrukturu tələb etmədi (mövcud `ReactionEvent`-lərin özü artıq bu
  məlumatı daşıyır). **Qəsdən 5 saniyəlik deyil, 90 saniyəlik polling** +
  manual "Yenilə" düyməsi — bu endpoint hər çağırışda 4 taymfreymin tam
  backtest statistikasını yenidən hesablayır (real datada ~1.4s), 5s
  polling mənasız yük olardı.
- **Canlı brauzerdə tam sınandı** (15 günlük, ossilasiya edən sintetik
  GOLD tick-ləri — 21,600 tick, birdəfəlik test backend/frontend, real
  bazaya toxunmadan): endpoint birbaşa yoxlanıldı — M30/H1/H4 üçün
  mənalı nəticələr (məs. M30 buy_side: 834 toxunma, 57.7% geri qayıtma,
  RSI-overbought seqmenti 84.7%-ə çatır; H4 sell_side: 100% geri qayıtma,
  n=35), D1 düzgün `insufficient_data` (yalnız 15 bar). Brauzerdə bütün 4
  kart, seqment siyahıları və jurnal (30 sətir, vaxt/qiymət/nəticə/point
  ilə) düzgün göründü, konsol xətası yox, sorğu axını təmiz (4 sorğu,
  storm yox — əvvəlki artımdan öyrənilmiş dərs tətbiq edildi: panelin öz
  "Yenilə" düyməsi JS-lə birbaşa klikləndi, `visibilityState` override-i
  istifadə edilmədi). Real production backend/frontend (8000/3000) sınaq
  boyu toxunulmadan işlədi.
- Backend `472 passed`. Frontend: lint təmiz, `13/13` test, production
  build uğurlu.

## 2026-08-07 — Likvidlik-səviyyəsi reaksiya statistikası (backend, hələ UI/API yoxdur)

- İstifadəçi çox-taymfreym likvidlik səviyyələri + reaksiya statistikası +
  "özü öyrənən sistem" + canlı "alış/satış gözlənilir" siqnalı + jurnal
  istədi. **Vacib sərhəd:** "alış/satış gözlənilir" dili platformanın
  "yalnız tədqiqat, siqnal deyil" prinsipinə birbaşa zidddir — istifadəçiyə
  aydınlaşdırıldı ki, bu, əslində Phase 8 (Decision/Risk Layer, hələ
  "PLANNED") mövzusudur, roadmap-da Phase 5-7-dən sonra gəlir. İstifadəçi
  təsdiqlədi: canlı göstərici **tədqiqat dili ilə** ("yuxarı/aşağı meyl",
  tarixi etibarlılıq faizi ilə), "alış/satış" sözləri olmadan qurulacaq, VƏ
  ilk artım kimi **yalnız backend/backtest statistikası** (hələ UI/API
  yoxdur) seçildi.
- `backend/app/analysis/bars.py`-a `M30` (1800s), `H4` (14400s), `D1`
  (86400s) əlavə edildi (istifadəçinin istədiyi 30m/1h/4h/1d dəstəyi üçün
  — `H1` artıq var idi). `BAR_BUILDER_VERSION 1.1.0 → 1.2.0`.
- Yeni `backend/app/analysis/liquidity_reaction.py`:
  `compute_liquidity_reaction_statistics(bars, pools, ...)` — mövcud
  `liquidity_sweep.py`-ın **artıq qurduğu** `LiquidityPool`-ları girişi
  kimi qəbul edir (təkrar pool-tikmə yoxdur). Hər dəfə qiymət bir pool
  səviyyəsinə TOXUNDUQDA (yalnız artıq `liquidity_sweep.py`-ın filtrlədiyi
  "təsdiqlənmiş sweep" alt-çoxluğu deyil — bütün toxunuşlar), `horizon_bars`
  irəli baxaraq nəticəni təsnifləndirir: **`reversed`** (qiymət yaxınlaşdığı
  tərəfə geri bağlanır) vs **`continued`** (qiymət səviyyədən keçib digər
  tərəfə bağlanır) vs **`ambiguous`** (heç biri `reaction_threshold_bps`
  həddini keçmir — nə "geri qayıtdı" sayılır, nə "keçdi", statistikadan
  kənarlaşdırılır). Üst-üstə düşən toxunuşlar `horizon_bars` embargo ilə
  təmizlənir (Phase 4-ün `_purge_overlapping_events()` konvensiyası ilə
  eyni). `buy_side` (müqavimət, aşağıdan yaxınlaşma) və `sell_side`
  (dəstək, yuxarıdan yaxınlaşma) ayrı hesablanır — hər biri üçün
  `reversed_percent` + 95% etibar intervalı (binomial proporsiya CI:
  `p ± 1.96*sqrt(p(1-p)/n)`, `n≥30` həddi ilə, `insufficient_data`
  aşağıda).
- **Şüurlu şəkildə kənarda qalıb (növbəti artımlara saxlanılıb):** çox-
  taymfreym orkestrasiyası (30m/1h/4h/1d-ni birlikdə çağıran API),
  "özü öyrənən sistem" (hansı indikator kombinasiyası daha yaxşı proqnoz
  verir), canlı "meyl" göstəricisi, jurnal/tarixçə UI-si. Bunların hamısı
  bu backtest statistikası əsasında qurulacaq, amma hələ toxunulmayıb.
- Yoxlama: yeni `test_liquidity_reaction.py` (`10` test — buy_side
  reversal/continuation/ambiguous, sell_side reversal/continuation, purge/
  embargo, `insufficient_data`/`completed` həddi, fingerprint determinizmi,
  təhlükəsiz parametr rəddi, boş pool siyahısının etibarlı giriş olması).
  `test_analysis_bars.py`-ın parametrized testi `M30/H4/D1`-i də əhatə
  etdi. Tam backend regressiyası: `462 passed`. Frontend toxunulmayıb.

## 2026-08-06 — Canlı indikator konsensusu 5 yeni osilatorla genişləndirildi

- İstifadəçi TradingView şəklini yenidən göstərərək canlı konsensus panelini
  daha da yaxınlaşdırmağı istədi; təklif edilən seçimlərdən "Osilatorları
  genişlət"i seçdi. Əvvəlki artımda yalnız RSI var idi (TradingView-un 11
  osilatoruna qarşı 1) — indi 6 osilator var: RSI, Stochastic %K(14,3),
  CCI(20), Williams %R(14), MACD(12,26,9), ADX(14) (+DI/-DI ilə).
- Yeni `backend/app/analysis/oscillators.py`: `indicators.py`-a TOXUNMADAN
  (Phase 4-ün stabil, geniş istifadə olunan `IndicatorSetResult`-u
  qorunur), tamamilə ayrı, yalnız bu konsensus üçün lazım olan 5 yeni
  osilator hesablaması:
  - `calculate_stochastic_k()` — xam %K(period) `smoothing` pəncərəsi
    üzərində SMA ilə hamarlanır; sıfır-range pəncərə `50.0` (neytral
    orta nöqtə) qaytarır, xəta atmır.
  - `calculate_cci()` — Commodity Channel Index; sıfır mean-deviation
    (flat bazar) `0.0` (artıq CCI-nin öz neytral dəyəri) qaytarır.
  - `calculate_williams_r()` — sıfır-range pəncərə `-50.0` (orta nöqtə).
  - `calculate_macd()` — sürətli/yavaş EMA fərqi + siqnal xətti (siqnalın
    öz EMA-sı yalnız MACD xətti artıq hazır olan nöqtələr üzərində
    hesablanır).
  - `calculate_adx()` — Wilder-in klassik üsulu (`indicators.py`-dəki
    ATR/RSI hamarlama nümunəsi ilə eyni), +DI/-DI ilə birlikdə.
  Bütün funksiyalar causal (yalnız bağlanmış barlar), deterministik
  fingerprint daşıyır, `insufficient_data`/`ready` konvensiyasını izləyir.
- `backend/app/analysis/indicator_consensus.py`: `compute_indicator_consensus()`
  indi `oscillators: OscillatorSetResult` parametri də qəbul edir (məcburi).
  Yeni təsnifat qaydaları: Stochastic/CCI/Williams %R — RSI ilə eyni
  oversold/overbought şablonu (ortaq `_classify_below_oversold_above_overbought()`
  helper-i ilə); MACD — xətt siqnaldan yuxarı/aşağı; **ADX xüsusidir** —
  ADX tənhaca istiqamət göstərmir (yalnız trend gücünü ölçür), ona görə
  yalnız `ADX>25` (trend mövcuddur) VƏ +DI/-DI müqayisəsi ilə birlikdə
  meyl təyin edilir, əks halda (zəif trend) neytral sayılır — bu, sənədli
  şəkildə izah olunub. `CONSENSUS_VERSION 1.0.0 → 2.0.0` (oscillators
  tuple 1-dən 6-ya çıxdı).
- `backend/app/analysis/live_analysis.py`: yeni `build_oscillator_set()`
  çağırışı əlavə edildi, nəticə `oscillators` sahəsi kimi cavaba əlavə
  olundu (hər 8 seriyanın xam dəyərləri: stochastic_k, cci, adx, plus_di,
  minus_di, macd_line, macd_signal, williams_r), lineage-ə
  `oscillator_fingerprint`/`oscillator_package_version` əlavə edildi.
  `LIVE_ANALYSIS_API_VERSION 1.0.0 → 1.1.0`.
- Frontend: `live-technical-summary-panel.tsx`-ə hər osilator/hərəkətli-
  ortalama qrupu üçün detallı cədvəl (`IndicatorTable`) əlavə edildi —
  TradingView-un "Осцилляторы >" açılan cədvəlinə bənzər (göstərici adı,
  dəyər, meyl pill-i), mövcud `.status-pill`/`tone-*` konvensiyası ilə.
  Gauge kart başlıqları "(RSI)"/"(EMA)"-dan sadə "Osilatorlar"/"Hərəkətli
  ortalamalar"-a dəyişdi (indi çoxlu göstərici əhatə edir).
- **Canlı brauzerdə tam sınandı** (55 dəqiqəlik sintetik GOLD tick-ləri —
  bütün 6 osilator "ready" olsun deyə MACD-in `slow(26)+signal(9)=35`
  bar tələbini qarşılamaq üçün əvvəlki 30 dəqiqədən artırıldı —
  birdəfəlik test backend/frontend, real bazaya toxunmadan): endpoint
  birbaşa `curl` ilə yoxlanıldı (6 osilator da düzgün hesablanıb
  təsnifləndi), sonra brauzerdə panel — 3 gauge kartı VƏ hər ikisinin
  detallı cədvəli — dəqiq eyni dəyərlərlə göründü. Konsol xətası yoxdu,
  sorğu axını təmiz idi (əvvəlki artımın override-artefaktından
  öyrənilərək bu dəfə override dərhal silindi). Real production
  backend/frontend (8000/3000) toxunulmadan işlədi.
- Backend `449 passed`. Frontend: lint təmiz, `12/12` test, production
  build uğurlu.

## 2026-08-06 — Əsas ekrana canlı indikator konsensusu paneli əlavə edildi

- İstifadəçi TradingView-un "Texniki analiz" widget-ini (osilator/hərəkətli
  ortalama Al/Sat/Neytral konsensusu) göstərərək bunu ESAS-ın əsas ekranına
  əlavə etməyi istədi. İki yanaşma təklif edildi (TradingView widget-ini
  gömmək / öz hesablamamızı qurmaq); istifadəçi **öz hesablamamızı
  quraq**-ı seçdi.
- **Vacib sərhəd:** TradingView-un "Покупать/Продавать" (Al/Sat) dili
  platformanın "yalnız tədqiqat, ticarət siqnalı deyil" prinsipinə birbaşa
  ziddir (bütün mövcud modullar `interpretation:
  "research_observation_not_trading_signal"` daşıyır, testlər "buy"/"sell"
  sözlərinin olmadığını yoxlayır). Ona görə etiketləmə fərqli seçildi:
  "Yuxarı meyl / Aşağı meyl / Neytral" (bullish_leaning/bearish_leaning/
  neutral), "TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT TÖVSİYƏSİ DEYİL" banneri ilə.
- **Arxitektur fərqi:** bu, sessiyada indiyədək tikilmiş HƏR ŞEYDƏN
  fərqlidir — əvvəlki bütün analiz modulları `completed` vəziyyətindəki
  **replay sessiyalarının** sabit, fingerprint-lənmiş snapshot-u üzərində
  işləyirdi (reproducibility üçün). Bu, ilk dəfə **canlı, dəyişən**
  pəncərə üzərində işləyən analiz — real çağırışdan çağırışa fərqli nəticə
  gözlənilir, ona görə heç bir dataset-drift qorumasına ehtiyac yoxdur
  (əksinə, "dəyişməzlik" gözlənilmir).
- Yeni `backend/app/analysis/indicator_consensus.py`:
  `compute_indicator_consensus()` — artıq mövcud `IndicatorSetResult`-un
  (RSI, EMA) son dəyərlərini götürüb Bullish/Bearish/Neytral təsnifatına
  çevirir (RSI<30 → yuxarı meyl [oversold], RSI>70 → aşağı meyl
  [overbought]; qiymət EMA-dan yuxarı/aşağı → uyğun meyl). Osilator/
  hərəkətli-ortalama alt-cəmləri və ümumi konsensus hesablanır.
  **Şüurlu şəkildə kiçik saxlanıldı:** TradingView-un 16 göstəricisinə
  qarşı yalnız 2 (RSI + EMA) — Stochastic/CCI/ADX/MACD/SMA və s. hələ yox
  (mövcud `indicators.py`-a toxunmadan, yalnız artıq test edilmiş RSI/EMA
  üzərində), sonrakı artımlarda genişlənə bilər.
- Yeni `backend/app/analysis/live_analysis.py`:
  `create_live_technical_summary()` — replay sessiyası TƏLƏB ETMİR, birbaşa
  `iter_tick_batches`-dən son N barlıq (bar_limit) canlı pəncərəni qurur
  (`end_at = datetime.now(UTC)`), indikatorları hesablayır, konsensusu
  çıxarır. `lineage.reproducible: false` açıq şəkildə qeyd olunur.
- Yeni qorunan `GET /api/v2/live-technical-summary` endpoint-i
  (`symbol`, `timeframe`, `ema_period`, `rsi_period`, `atr_period`,
  `bar_limit` parametrləri).
- Frontend: yeni `live-technical-summary-panel.tsx` — "Nəticələr" (defolt/
  əsas) ekranına əlavə olundu, mövcud 5 saniyəlik səhifə-aktiv-olduqda
  polling konvensiyası ilə (`page.tsx`-dəki eyni nümunə). 3 gauge kartı:
  Osilatorlar (RSI), Ümumi, Hərəkətli ortalamalar (EMA).
- **Canlı brauzerdə tam sınandı** (birdəfəlik test backend/frontend,
  real bazaya toxunmadan): sintetik GOLD tick-ləri (360 ədəd, 30 dəqiqə)
  scratch bazaya əlavə edildi, endpoint birbaşa `curl` ilə də
  yoxlanıldı (düzgün RSI/EMA/konsensus nəticələri), sonra brauzerdə panel
  düzgün göründü (real hesablanmış "Aşağı meyl"/"Neytral"/"Yuxarı meyl"
  dəyərləri ilə). Sınaq zamanı avtomatlaşdırılmış brauzer mühitinin
  `document.visibilityState`-i həmişə "hidden" olduğu üçün (bu sessiyada
  əvvəllər də qeyd edilib) müvəqqəti/təhlükəsiz şəkildə override edilərək
  tək təmiz refresh tetiklənidi — override-i uzun saxlamaq (silinmədən)
  avtomatlaşdırılmış brauzerin öz daxili compositing/görünüş yoxlamaları
  ilə toqquşaraq sürətli təkrar sorğu axınına səbəb oldu (bu, YALNIZ test
  alətinin artefaktı idi — override silinən kimi ani şəkildə dayandı,
  həm köhnə `/status/operational` pollingi, həm yeni panel eyni cür
  təsirləndi, deməli tətbiq kodunda problem yox idi). Real production
  backend/frontend (8000/3000) bütün sınaq boyu toxunulmadan işləməyə
  davam etdi.
- Backend `435 passed`. Frontend: lint təmiz, `12/12` test, production
  build uğurlu.

## 2026-08-06 — Phase 3 SA-002: pəncərə range-i, mütləq return və robust MAD (volatilite)

- İstifadəçinin tövsiyəsi ilə (SA-001-in birbaşa davamı olduğu üçün) SA-002
  (volatilite) seçildi. Bu artım müqavilənin dörd təsviri ölçüsündən üçünü
  əhatə edir: pəncərə mid-price range-i (mütləq və nisbi), pəncərə
  log-return-un mütləq dəyəri, robust median absolute deviation (MAD).
  **Kənarda qalıb:** "tick-return standart sapması" (tick-to-tick, pəncərə
  olmadan) — bu, yeni bir xam-tick keçidi tələb edir (hazırkı bütün
  `backend/app/analysis/*` modulları yalnız `bars.py`-ın artıq qurduğu
  `MarketBar`-lar üzərində işləyir, `bars.py` istisna olmaqla heç biri xam
  tick oxumur); ayrıca, kiçik artım kimi saxlanılıb.
- Yeni `backend/app/analysis/volatility.py`: `compute_volatility(bars,
  return_series, ...)` — artıq qurulmuş `return_series`-i (SA-001-dən) VƏ
  bar-ları giriş kimi qəbul edir (təkrar hesablama yoxdur, tək mənbə).
  Ümumi `DistributionSummary` (say/orta/median/std/min/maks/p05/p95) üç
  yerdə təkrar istifadə olunur: `window_range_absolute` (`high-low`, bütün
  bar-lar, tick_count≥1 kifayətdir — tək-tick pəncərə range üçün etibarlıdır,
  return üçün deyil), `window_range_relative` (`range/open`),
  `window_log_return_abs` (yalnız `return_series`-in özünün artıq süzdüyü
  tick_count≥2 pəncərələr). `robust_mad` — imzalı return-ların median-dan
  mütləq kənarlaşmasının median-ı (əl-hər metrik öz `n_valid`-ini ayrıca
  göstərir — müqavilənin "hər metric istifadə etdiyi və kənarlaşdırdığı
  müşahidə sayını ayrıca göstərir" tələbi).
- `statistical_analysis.py`-a inteqrasiya: `minimum_window_returns`
  parametri daha ümumi `minimum_sample_size`-a çevrildi (indi həm
  return-series, həm volatility eyni həddi paylaşır; `return_series.py`-ın
  öz daxili parametri `minimum_window_returns` olaraq dəyişməz qalıb —
  yalnız orkestrasiya qatında ümumi ad istifadə olunur).
  `STATISTICAL_ANALYSIS_API_VERSION 1.0.0 → 1.1.0` (yeni `volatility`
  sahəsi). API sorğu parametri də uyğun yeniləndi
  (`?minimum_sample_size=`).
- Bu qat siqnal, giriş, risk ölçüsü və order yaratmır.
- Yoxlama: yeni `test_volatility.py` (`7` test — minimum həddən yuxarı/aşağı
  davranış, tək-tick pəncərənin range-ə daxil amma return-a xaric
  edilməsi, range dəyərinin `high-low`-a bərabərliyi, fingerprint
  determinizmi, uyğunsuz simvol/timeframe rəddi, təhlükəsiz
  `minimum_sample` rəddi). API testləri (`test_replay_technical_analysis_api.py`)
  `volatility` sahəsini və yeni `api_version`-u əhatə edəcək şəkildə
  yeniləndi. Tam backend regressiyası: `425 passed`. Frontend toxunulmayıb.

## 2026-08-06 — Phase 3 statistik analiz başladı: pəncərə/resampling təməli + SA-001 gəlir seriyası

- İstifadəçinin təsdiqi ilə (Phase 4-ün namizəd lifecycle-ı əsasən
  tamamlandığı üçün) Phase 3-ə (`PHASE_3_STATISTICAL_ANALYSIS_CONTRACT.md`)
  keçildi. Müqavilə böyükdür (SA-001-dən SA-007-yə qədər) — ilk artım kimi
  təməl pəncərə/resampling infrastrukturu və SA-001 (gəlir seriyası)
  seçildi, çünki qalan bölmələr (volatilite, spread, tick sürəti və s.) bu
  pəncərə seriyasından asılıdır.
- `backend/app/analysis/bars.py`: `TIMEFRAME_SECONDS`-a `S1` (1 saniyə) və
  `S10` (10 saniyə) əlavə edildi (müqavilənin "1s, 10s, 1m, 5m, 15m, 1h"
  tələbinə uyğun; əvvəllər yalnız `M1/M5/M15/H1` var idi). `BAR_BUILDER_VERSION
  1.0.0 → 1.1.0`. Mövcud `build_closed_mid_bars()` funksiyası dəyişmədən
  yenidən istifadə olundu (əvvəllər tikilmiş, artıq forward-fill etməyən,
  boş pəncərəni doldurmayan mid-price OHLC qurucusu).
- Yeni `backend/app/analysis/return_series.py`: `compute_return_series()` —
  hər qapalı pəncərənin öz ilk (open) və son (close) etibarlı mid-price-ı
  ilə log-return hesablayır (`r = ln(close/open)`). **Tək-tick pəncərə heç
  bir return yaratmır** (xaric edilir, sıfır kimi sayılmır) — müqavilənin
  "bir qiymətli pəncərə return yaratmır" tələbi. Nəticə: say, orta, median,
  standart sapma, min, maks, p05/p25/p75/p95 (xətti interpolyasiya üsulu,
  `n_valid` konfiqurasiya olunan minimumdan (defolt `30`) azdırsa
  `insufficient_data`, boş nəticə sıfır effekt kimi göstərilmir). Boş
  `bars` girişi (diapazonda heç bir tick yoxdursa) də etibarlı, deqradasiya
  olunan giriş kimi işlənir (xəta atmır) — digər detektor modullarının
  konvensiyasına uyğun (məs. `fair_value_gap.py`).
- Yeni `backend/app/analysis/statistical_analysis.py`:
  `create_replay_statistical_analysis()` — tamamlanmış replay sessiyası
  üçün (dataset-drift qoruması, `technical-analysis`/`strategy-analysis`
  ilə eyni nümunə) bir `timeframe` üzrə bar qurur və gəlir seriyasını
  hesablayır. `MAX_STATISTICAL_ANALYSIS_WINDOWS = 50_000` təhlükəsizlik
  həddi (sessiyanın tam diapazonu emal olunur, `technical-analysis`-dəki
  kimi "son N bar" məhdudiyyəti yoxdur — Phase 3 dataset-səviyyəli təsviri
  statistika üçün bu, məntiqi cəhətdən düzgündür).
- Yeni qorunan, yalnız-oxuma `GET
  /api/v2/replay-sessions/{session_id}/statistical-analysis` endpoint-i
  (`timeframe`, `minimum_window_returns` sorğu parametrləri) — mövcud
  `technical-analysis`/`strategy-analysis` endpoint-lərinin eyni nümunəsi
  ilə (ownership, `409`/`403`/`422`/`404`, dataset-drift `409`).
- **Şüurlu şəkildə kənarda qalıb (növbəti artımlara saxlanılıb):**
  müqavilənin `POST /api/v2/statistical-analyses` async job/persistence
  resursu (Phase 2 job-queue ilə, səhifələnmə, audit) — bu, ilk artımda
  həddindən artıq həcmli olardı; hazırkı endpoint sinxron və DB-siz-nəticə
  (digər Phase 4 analiz endpoint-lərinin ilk versiyaları kimi). SA-002-dən
  SA-007-yə qədər (volatilite, spread, tick sürəti, tick-volume, sessiya,
  rejim) — bu pəncərə seriyası üzərində qurulacaq. Frontend paneli —
  Phase 3-ün daha çox hissəsi hazır olanda əlavə olunacaq (Phase 4-ün ilk
  artımlarında da eyni ardıcıllıq izlənilib).
- Bu qat siqnal, giriş, risk ölçüsü və order yaratmır; yalnız təsviri
  statistikadır (`interpretation: "research_observation_not_trading_signal"`).
- Yoxlama: yeni `test_return_series.py` (`9` test — determinizm,
  tək-tick-in xaric edilməsi, `insufficient_data` həddi, boş giriş,
  percentile sıralaması, fingerprint determinizmi, uyğunsuz
  simvol/timeframe rəddi, təhlükəsiz `minimum_window_returns`).
  `test_analysis_bars.py`-da mövcud parametrized test `S1`/`S10`-u da
  əhatə etdi. `test_replay_technical_analysis_api.py`-a `4` yeni API testi
  (qorunma+determinizm+tədqiqat-yalnız, defolt minimumdan aşağı
  `insufficient_data`, ownership/completed/parametr təhlükəsizliyi,
  dataset-drift). Tam backend regressiyası: `418 passed`. Frontend
  toxunulmayıb.

## 2026-08-06 — Phase 9 SHADOW-a "çağıran" əlavə edildi: admin API + frontend

- İstifadəçi Phase 9 skeletinin "real çağıranı yoxdur" qeydinə görə əl ilə
  idarə oluna bilən admin API + frontend bölməsi istədi. Bu, real qərar
  generatoru (Phase 5-8) DEYİL — insan operator SHADOW run yarada, event
  qeydə ala, nəzəri mövqe aça/bağlaya bilər. `execution_allowed` DB
  səviyyəsində `0`-a qıfıllı qalır, dəyişməz.
- `shadow_run_repository.py`-a `list_shadow_runs()` əlavə edildi (owner
  üzrə, sadə həddli siyahı — SHADOW run-ları nadir, uzunmüddətli
  eksperimentlərdir, `pattern_candidates`/`replay_sessions` kimi yüksək
  həcmli axın deyil, ona görə imzalı keyset cursor-a ehtiyac yoxdur).
  `shadow_portfolio_repository.py`-a `list_theoretical_positions()`.
- `backend/app/models/shadow.py` (yeni): bütün SHADOW sorğuları üçün
  Pydantic modelləri.
- `backend/app/main.py`-a 12 yeni qorunan endpoint: `POST/GET
  /api/v2/shadow-runs`, `GET .../{id}`, `POST .../{id}/start|complete|halt`,
  `GET/POST .../{id}/events`, `GET/POST .../{id}/positions`, `POST
  .../{id}/positions/{position_id}/close`, `GET
  .../{id}/portfolio-summary`. Risk-bloklu mövqe açılışı `200`
  status-la `{"opened": false, "reason": ...}` qaytarır (bu, xəta deyil,
  müqavilənin gözlədiyi qanuni nəticədir).
- Frontend: yeni `shadow-runs-panel.tsx` bölməsi (`dashboard-navigation.tsx`,
  `page.tsx`-ə qoşulub) — **"NƏZƏRİDİR — REAL ƏMƏLİYYAT YOXDUR"** bannerini
  həmişə göstərir. Run siyahısı + yaratma formu, run təfərrüatı
  (iştirakçılar, vəziyyət, start/complete/halt düymələri), nəzəri mövqe
  aç/bağla formu, event qeydiyyat formu, portfolio xülasəsi.
- **Canlı brauzerdə tam sınandı** (real bazaya toxunmadan — birdəfəlik
  test backend-i port 8001-də, frontend 5173-də, sonra tamamilə
  təmizləndi): run yaradıldı → başladıldı → 2 mövqe açıldı → 3-cü mövqə
  risk limiti ilə düzgün bloklandı (`max_concurrent_positions_exceeded`)
  → mövqə bağlandı → event qeydə alındı → run tamamlandı. Brauzer
  konsolunda heç bir xəta olmadı.
- **Sınaq zamanı tapılan real bug düzəldildi:** `openPosition`-da risk-blok
  xəbərdarlığı (`setDetailError`) `loadDetail()`-dan ƏVVƏL çağırılırdı,
  amma `loadDetail` özü `detailError`-u sıfırlayır — nəticədə xəbərdarlıq
  istifadəçiyə heç vaxt görünmürdü (dərhal təmizlənirdi). Sıra
  dəyişdirildi (`loadDetail` sonra `setDetailError`), brauzerdə yenidən
  sınanıb təsdiqləndi.
- Yoxlama: yeni `test_shadow_runs_api.py` (`13` test) — tam HTTP axını
  (yaratma, siyahı, keçidlər, event/mövqe CRUD, risk bloku, səhv
  run-a bağlı mövqeni bağlamağa cəhd `404`). Yeni `shadow-runs-ui.test.mjs`
  (mənbə-mətn yoxlaması, digər panellərlə eyni konvensiya). Tam backend
  regressiyası: `404 passed`. Frontend: lint təmiz, `11/11` test, production
  build uğurlu.
- Real production bazaya heç nə tətbiq edilmədən (migration `0010` hələ
  yalnız kodda/test bazalarında).

## 2026-08-06 — Phase 9 SHADOW: nəzəri portfolio/risk ledger (section 6, skelet davamı)

- Əvvəlki artımda tikilmiş SHADOW run manifest + event reyestri skeletinin
  davamı: müqavilənin 6-cı bölməsi ("Nəzəri portfolio və risk"). **Hələ də
  canlı SHADOW sistemi deyil** — real qərar generatoru (Phase 5-8) yoxdur,
  heç bir istehsalat kodu bu cədvələ yazmır. API/frontend əlavə edilmədi
  (əvvəlki skelet artımındakı eyni səbəbdən: real çağıran yoxdur).
- `0010_shadow_theoretical_positions.sql`: `shadow_theoretical_positions`
  cədvəli — real hesaba/MT5 mövqeyinə heç bir əlaqəsi yoxdur (yalnız
  `shadow_runs`/`shadow_run_participants`/`shadow_events`-ə istinad edir).
  Mövqenin kimliyi (`shadow_run_id`, `symbol`, `direction`, ölçü, ehtiyat
  risk, açılış event-i) trigger ilə dəyişməzdir; yalnız `state`/`closed_at`/
  `close_event_id`/`theoretical_pnl_percent` dəyişə bilər.
- `backend/app/database/shadow_portfolio_repository.py`:
  `open_theoretical_position()` — müqavilənin mövqe-səviyyəli risk
  limitlərini (eyni-vaxtda mövqe sayı, simvol+istiqamət konsentrasiyası,
  ümumi ehtiyat risk) namizədin öz `risk_budget_json`-undan yoxlayır; limit
  keçilirsə mövqe açmır, əvəzinə `SHADOW_RISK_BLOCKED` event-i qeydə alır
  (bu event növü artıq əvvəlki skelet artımında təyin olunmuşdu).
  `close_theoretical_position()` — ehtiyat riski azad edir.
  `get_theoretical_portfolio_summary()` — açıq mövqe sayı, ümumi ehtiyat
  risk, bağlanmış mövqe sayı, xalis nəzəri PnL (müşahidə üçün).
- **Şüurlu şəkildə kənarda qalıb:** gündəlik itki və drawdown limitləri —
  bunlar realized PnL zaman sırası üzərində hesablanan konseptlərdir, heç
  bir canlı qərar axını olmadan mənasız olardı. Kodda və sənədlərdə açıq
  qeyd olunub.
- Atomiklik qeydi: mövqe açılışı iki addımlı-təhlükəsizdir — məsləhət
  xarakterli ilkin limit yoxlaması (boş yerə `OPENED` event-i yazılmasın
  deyə), sonra əsl yoxlama+insert EYNİ tranzaksiyada (yarışı bağlayır).
  Nadir yarış halında `ShadowPositionConflictError` atılır — real paralel
  çağıran hələ olmadığı üçün qəbul edilən, sənədləşdirilmiş məhdudiyyət.
- Yoxlama: yeni `test_shadow_portfolio_repository.py` (`10` test) —
  mövqe açılışı/bağlanışı, 3 risk limitinin hər biri, boş risk büdcəsi
  heç vaxt bloklamır, ownership, optimistic lock, səhv giriş rədd edilməsi.
  `test_migration_runner.py` sayğacları `0010`-a uyğunlaşdırıldı. Tam
  backend regressiyası: `391 passed`. Frontend toxunulmayıb.
- Bu qat heç bir real risk, mövqe və ya order yaratmır; yalnız gələcək
  Phase 9 tətbiqi üçün strukturca təhlükəsiz nəzəri hesab əsasıdır.

## 2026-08-06 — `invalid_leakage` lifecycle vəziyyəti: üst-üstə düşən hadisələr üçün purge/embargo

- Real, əvvəllər qorunmayan bir statistik boşluq tapıldı və düzəldildi:
  backtest v1 hər tarixi tetikləməni (məs. `horizon_bars=5` ilə ard-arda 2
  bar məsafəli tetikləmələr) **müstəqil nümunə** kimi sayırdı, halbuki
  onların [giriş, çıxış] pəncərələri üst-üstə düşəndə nəticələr korrelyasiya
  olunur — bu, effektiv nümunə sayını və etibar intervalını süni şəkildə
  şişirdirdi. Əsl "gələcək məlumat sızması" (causal leakage) hər detektorda
  artıq struktur olaraq qarşısı alınıb (bütün "no-lookahead" testləri) —
  orada əlavə ediləcək məzmunlu bir şey yox idi; real boşluq üst-üstə düşmə
  idi (Phase 3-ün "üst-üstə düşən horizon-lar purge/embargo tələb edir"
  tələbi).
- `pattern_candidate_backtest.py`-a `_purge_overlapping_events()` əlavə
  edildi: xronoloji sırayla, əvvəlki saxlanmış hadisənin
  `[giriş, giriş+horizon_bars)` pəncərəsinə düşən sonrakı hadisələr atılır
  (embargo). **Bütün namizədlər üçün tətbiq olunur** (yalnız bayraqlanan
  hallarda deyil) — statistik doğruluğu səssizcə artırır.
  `PatternCandidateBacktest`-ə `raw_event_count`/`discarded_for_overlap`
  sahələri əlavə edildi. `BACKTEST_VERSION 1.5.0`.
- `replay_pattern_candidates.py`-nın `classify_replay_pattern_candidate`-i
  indi: əgər xam hadisə sayı kifayət idi (`≥30`) AMMA purge-dan sonra
  effektiv nümunə `30`-dan aşağı düşübsə → namizəd `invalid_leakage`-ə
  keçir (`insufficient_evidence`-ə DEYİL — bu fərq vacibdir: birincisi
  "sübut üst-üstə düşmə ilə şişirdilib", ikincisi "hələ kifayət qədər
  tarixi hadisə baş verməyib").
- `pattern_candidate_repository.py`: `CLASSIFICATION_OUTCOMES` və
  `ARCHIVABLE_STATES`-ə `invalid_leakage` əlavə edildi.
- Frontend: `LIFECYCLE_LABELS`-ə "Etibarsız — sübut üst-üstə düşən
  hadisələrlə şişirdilib" etiketi əlavə edildi.
- Yoxlama: `test_pattern_candidate_backtest.py`-a `2` yeni test (purge
  davranışı, dəqiq say təsdiqi ilə: `40` xam hadisədən `8`-i qalır,
  horizon=5 ilə); mövcud `2` baseline testi yeni purge davranışına uyğun
  yenidən konfiqurasiya edildi (hadisələr artıq `horizon_bars` qədər
  aralıqla yerləşdirilib ki, baseline testləri təsadüfən purge-la
  qarışmasın). `test_pattern_candidate_repository.py`-a `1` yeni test.
  Yeni `test_replay_pattern_candidates_classification.py`-a `3` yeni test
  (leakage keçidi, purge olmadıqda normal axın, xam siqnal əvvəlcədən azdısa
  `insufficient_evidence` qalması). Tam backend regressiyası: `381 passed`.
  Frontend: lint təmiz, `10/10` test, production build uğurlu.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; dəyişiklik həm
  bütün namizədlər üçün statistik doğruluğu artırır, həm də üst-üstə düşmə
  ilə şişirdilmiş "sübutu" ayrıca aşkarlayır.

## 2026-08-06 — `blocked_by_data_quality` lifecycle vəziyyəti tətbiq edildi

- Phase 4 müqaviləsinin əvvəlcədən deklarasiya edilmiş (migration `0005`-in
  CHECK-i) amma məntiqsiz qalan son vəziyyətlərindən biri indi real işləyir:
  bir namizədin **ilk** backtest cəhdindən əvvəl onun replay sessiyasının
  keyfiyyət hesabatı yoxlanılır — `critical_count > 0`-dırsa, namizəd
  `evaluated`-ə DEYİL, birbaşa `blocked_by_data_quality`-yə keçir və heç bir
  backtest sübutu istehsal olunmur.
- `pattern_candidate_repository.py`-a `block_pattern_candidate_for_data_quality()`
  əlavə edildi — yalnız `registered`-dən əlçatandır (xam tick-lər və
  keyfiyyət qaydaları dəyişməz olduğu üçün `evaluated`-ə çatmış namizəddə
  yenidən yoxlamağa ehtiyac yoxdur). `ARCHIVABLE_STATES`-ə də əlavə edildi —
  bloklanmış namizəd arxivləşdirilə bilir.
- `replay_pattern_candidates.py`-nın `evaluate_replay_pattern_candidate_backtest`-i
  indi `create_replay_quality_report(session_id=...)` çağırır (yalnız
  namizəd hələ `registered`-dirsə) və kritik tapıntı aşkarlansa
  `PatternCandidateBlockedByDataQualityError` atır. API-də bu, `409`
  statusu ilə görünür (`POST .../backtest`).
- Frontend: `LIFECYCLE_LABELS`-ə "Bloklanıb — məlumat keyfiyyəti kritik
  tapıntı göstərir" əlavə edildi; bloklanmış sətirdə "Backtest et" düyməsi
  gizlədilir (arxivləşdirmə düyməsi qalır).
- Yoxlama: `test_pattern_candidate_repository.py`-a `5` yeni test (keçid,
  səhv-vəziyyət rəddi, ownership/optimistic-lock, arxivləşdirmə); yeni
  `test_replay_pattern_candidates_data_quality.py` (`3` test) — real DQ-005
  (bid>ask) tapıntısı ilə uc-uca sübut (bloklanma, ikinci cəhdin rəddi, API
  `409`) və kritik tapıntı olmadıqda normal axının pozulmadığı. Tam backend
  regressiyası: `375 passed`. Frontend: lint təmiz, `10/10` test, production
  build uğurlu.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; yalnız etibarsız
  məlumat üzərində statistik nəticə çıxarılmasının qarşısını alır.

## 2026-08-06 — Real production baza `0005`-`0009` migrasiyalarına köçürüldü

- İstifadəçi frontend-də "Qeydə alınmış namizədlər" siyahısının `HTTP 500`
  verdiyini bildirdi. Kök səbəb: real `database/ESAS_PLATFORM.sqlite`
  yalnız `0004` migrasiyasında idi — bu sessiyada (və əvvəlki sessiyada)
  görülən bütün Pattern namizədi/job-queue/multiple-testing/Phase 9 işi
  qəsdən yalnız müvəqqəti test bazalarında aparılmışdı (AGENTS.md qaydası:
  real bazaya toxunmazdan əvvəl ayrıca icazə). `pattern_candidates`
  cədvəli mövcud olmadığı üçün siyahı endpoint-i `sqlite3.OperationalError:
  no such table` ilə çökürdü (draft hesablama DB-siz işlədiyi üçün
  təsirlənmirdi).
- İstifadəçinin açıq təsdiqindən sonra: real bazanın **tam surətində**
  (kopiya) `0005`-`0009` əvvəlcə sınandı — təmiz tətbiq olundu, yalnız 5
  yeni cədvəl əlavə etdi, mövcud `tick_events`/`replay_sessions` sətir
  sayları dəyişmədi (yalnız əlavəedici `CREATE TABLE/INDEX/TRIGGER`, heç
  bir `DROP/DELETE/UPDATE` yoxdur).
- Sonra: backend/frontend rəsmi `tools/stop-local-platform.ps1` ilə
  dayandırıldı (MT5 Bridge FIFO buferi tick itkisinin qarşısını alır),
  real bazanın `database/backups/ESAS_PLATFORM_pre-0005-0009_<UTC
  timestamp>.sqlite` adlı tam ehtiyat nüsxəsi götürüldü (`quick_check=ok`
  təsdiqləndi), migrasiyalar birbaşa real fayla tətbiq edildi.
- Doğrulama: `quick_check=ok`, `tick_events` sayı dəyişməz qaldı,
  `replay_sessions` sayı `7`-də qaldı, bütün `0001`-`0009` `schema_migrations`
  cədvəlində qeydə alındı. Backend/frontend `tools/start-local-platform.ps1`
  ilə yenidən başladıldı; `/health`, `/status/operational` (tick axını
  `active`) və `GET /api/v2/pattern-candidates` (əvvəllər 500, indi `200`,
  boş siyahı — real bazada hələ heç bir namizəd qeydə alınmayıb) təsdiqləndi.
- `database/backups/` `.gitignore`-a əlavə edildi (böyük SQLite ehtiyat
  nüsxələrinin təsadüfən commit edilməsinin qarşısını almaq üçün).
- Bu, sessiya ərzində real bazaya edilən YEGANƏ dəyişiklikdir; xam
  `tick_events` və mövcud sessiya/audit sətirlərinə heç toxunulmayıb.

## 2026-08-06 — Phase 3/4 baseline müqayisəsi tamamlandı (4/4)

- Qalan iki baseline əlavə edildi: **tək-feature qaydası** və **əvvəlki
  qəbul edilmiş namizəd**. Phase 3/4 müqaviləsinin bütün 4 baseline-ı
  (no-signal, təsadüfi-zaman, tək-feature, əvvəlki namizəd) indi tam
  tətbiq olunub.
- **Tək-feature qaydası:** `pattern_candidate_backtest.py`-a
  `_single_feature_rsi_reversal_raw_returns()` əlavə edildi — sabit
  (tənzimlənməyən) klassik RSI reversal qaydası: RSI 30-dan yuxarı keçəndə
  bullish, 70-dən aşağı keçəndə bearish giriş. Hədlər **qəsdən sabit**
  saxlanıldı (30/70, `SINGLE_FEATURE_RSI_LOW/HIGH_THRESHOLD`) — tənzimlənə
  bilən olsaydı, bu baseline özü multiple-testing "parametr alış-verişi"
  səthinə çevrilərdi. `run_pattern_candidate_backtest` indi `rsi:
  IndicatorSeries | None = None` parametri qəbul edir (`context.indicators.rsi`
  vasitəsilə real çağırışda ötürülür); RSI yoxdursa baseline sadəcə boş
  keçir, bloklamır.
- **Əvvəlki qəbul edilmiş namizəd:** `pattern_candidate_repository.py`-a
  `get_latest_accepted_candidate_for_hypothesis()` əlavə edildi — eyni
  `hypothesis_id` üzrə (bütün sessiyalar üzrə **qlobal**, multiple-testing
  ailəsindən fərqli olaraq sessiya ilə məhdudlaşmır) ən son
  `accepted_for_shadow` namizədi tapır. `classify_replay_pattern_candidate`
  indi: əgər qərar `accepted_for_shadow` olacaqdısa VƏ eyni hipotez üzrə
  əvvəlki qəbul edilmiş namizəd varsa, yeni namizədin (düzəlişli) orta
  gəliri əvvəlkini keçməlidir — keçməzsə `rejected`-ə düşür.
- `BacktestCostScenario`-ya daha 3 sahə: `single_feature_baseline_*` (3
  sahə). Qərar qaydası: namizəd indi sıfırı, təsadüfi-zaman baseline-ını
  VƏ tək-feature baseline-ını **hamısını birlikdə** keçməlidir.
  `bonferroni_corrected_scenario()` da uyğunlaşdırıldı (düzəliş heç bir
  baseline yoxlamasını gizlədə bilməz). `classify_replay_pattern_candidate`
  `PatternCandidateClassificationOutcome`-a `previous_accepted_candidate_comparison`
  sahəsi əlavə etdi; API-də `meta.previous_accepted_candidate_comparison`
  altında görünür. `BACKTEST_VERSION 1.4.0`.
- Frontend toxunulmayıb.
- Yoxlama: `test_pattern_candidate_backtest.py`-a `4` yeni test (tək-feature
  sahələri, RSI-siz skip, sıfırı+təsadüfi-zamanı keçib tək-feature-i
  keçməyən ssenari, Bonferroni+tək-feature qarşılıqlı təsiri).
  `test_pattern_candidate_repository.py`-a `4` yeni test (əvvəlki qəbul
  edilmiş namizəd sorğusu: tapılmır/tapılır/özünü xaric edir/fərqli
  hipotezi görməzdən gəlir). Yeni
  `test_replay_pattern_candidates_classification.py` (`4` test) —
  `classify_replay_pattern_candidate`-i uc-uca, sintetik saxlanmış
  backtest nəticələri ilə, əvvəlki-namizəd qapısının həqiqətən qərarı
  dəyişdiyini sübut edir. Tam backend regressiyası: `368 passed`.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; dəyişiklik yalnız
  `accepted_for_shadow` qərarının statistik ciddiliyini daha da artırır.

## 2026-08-06 — Backtest v1-ə təsadüfi-zaman baseline müqayisəsi əlavə edildi

- Phase 3/4 müqaviləsinin "Baseline və müqayisə" tələbindən (no-signal,
  təsadüfi-zaman, tək-feature, əvvəlki namizəd) yalnız **təsadüfi-zaman
  baseline-ı** tətbiq edildi (istifadəçi ilə həcm razılaşdırıldı). No-signal
  baseline artıq örtülü şəkildə mövcud idi (mövcud CI-testi sıfır bazasına
  qarşı yoxlayır); tək-feature qaydası və əvvəlki namizəd müqayisəsi ayrıca
  namizəd kimi qeyd olundu (`docs/status/NEXT_TASK.md`).
- `pattern_candidate_backtest.py`-a `_random_timing_baseline_raw_returns()`
  əlavə edildi: eyni bar seriyasından, eyni istiqamət konvensiyası və
  horizon ilə, **seed-lənmiş (deterministik) təsadüfi** giriş nöqtələri
  seçib eyni cost modeli ilə nəticələndirir. Seed yalnız artıq sabit
  girişlərdən (candidate_id, hypothesis_id, horizon_bars, bar sayı, ilk/son
  bar vaxtı) hesablanır — eyni giriş həmişə eyni "təsadüfi" nümunəni verir
  (reproducibility). Bu, "strategiya sadəcə bazar dreyfini/volatilliyini
  tutur" riskini aşkarlayır: real namizədin orta gəliri sıfırı keçsə də,
  eyni dövrdə hipotezə kor təsadüfi girişlərin ortasından aşağı qalırsa,
  bu, real səbəbiyyət əlaqəsi deyil.
- `BacktestCostScenario`-ya 3 yeni sahə əlavə edildi:
  `random_timing_baseline_sample_size`,
  `random_timing_baseline_mean_return_percent`,
  `beats_random_timing_baseline`. Qərar qaydası genişləndirildi: namizəd
  indi YALNIZ sıfır bazasını deyil, **HƏM DƏ** təsadüfi-zaman baseline-ını
  keçdikdə `supportive_evidence` sayılır; sıfırı keçib baseline-ı keçməyən
  hal yeni `ci_does_not_exceed_random_timing_baseline` səbəbi ilə
  `insufficient_evidence`-ə düşür, bu da `classify_backtest_verdict`
  vasitəsilə `rejected`-ə aparır (mövcud reason-əsaslı budaqlanma
  dəyişmədən işlədi, yeni parametr əlavə etməyə ehtiyac olmadı).
- `bonferroni_corrected_scenario()` uyğunlaşdırıldı: düzəlişli CI indi HƏM
  sıfır, HƏM DƏ (varsa) təsadüfi-zaman baseline-ı ilə müqayisə olunur —
  multiple-testing düzəlişi baseline yoxlamasını gizlədə bilməz.
- `BACKTEST_VERSION` `1.2.0 → 1.3.0` (nəticə sxemi dəyişdi, fingerprint-lər
  təbii şəkildə fərqlənəcək).
- Frontend toxunulmayıb — yeni sahələr backend cavabında mövcuddur, amma
  UI-də göstərilmir (TypeScript struktur tipləşdirməsi əlavə sahələri
  sadəcə görməzdən gəlir, heç bir kəsilmə yoxdur).
- Yoxlama: `test_pattern_candidate_backtest.py`-a `4` yeni test (baseline
  sahələrinin mövcudluğu, determinizm, sıfırı keçib baseline-ı keçməyən
  real ssenari, Bonferroni+baseline qarşılıqlı təsiri). Tam backend
  regressiyası: `356 passed` (heç bir mövcud test pozulmadı — bütün digər
  test fixture-ları ya kiçik nümunəli (n<30, artıq `insufficient_evidence`),
  ya da yeni yoxlamanı təbii keçdi).
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; dəyişiklik yalnız
  `accepted_for_shadow` qərarının statistik ciddiliyini daha da artırır.

## 2026-08-06 — Phase 9 SHADOW: run manifest + append-only event reyestri skeleti

- **Diqqət — bu, CANLI SHADOW SİSTEMİ DEYİL.** `PHASE_9_SHADOW_VALIDATION_CONTRACT.md`
  hələ də "DESIGN READY — NOT IMPLEMENTED" statusundadır və Phase 1-8
  qəbulundan asılıdır (hazırda yalnız Phase 1/2 STABLE-dır). Phase 5-8
  (Visual AI, xəbər/fundamental analiz, Knowledge Base, Decision/Risk) hələ
  yalnız dizayn sənədləridir — real qərar generatoru yoxdur. Bu artım
  yalnız müqavilənin 3-cü (run manifestinin əvvəlcədən qeydiyyatı) və 9-cu
  (append-only event ailələri) bölmələrindəki **persistence skeletini**
  tikir; heç bir istehsalat kodu bu cədvəllərə hələ yazmır.
- `0009_shadow_runs.sql`: `shadow_runs` (dəyişməz manifest — planlaşdırılan
  bitmə vaxtı, kod commit-i, konfiqurasiya hash-i, feature/claim
  versiyaları, simvol/timeframe/sessiya/rejim əhatəsi, minimum müşahidə
  müddəti/nümunə sayı, əsas/ikinci metriklər, uğursuzluq qaydaları, nəzəri
  fill modeli, risk büdcəsi, məlumat keyfiyyəti siyasəti, təsdiqləyən şəxs,
  rollback planı), `shadow_run_participants` (champion/challenger rolları,
  append-only), `shadow_events` (9 hadisə ailəsi, append-only).
- **İki struktur invariantı, tətbiq kodundan asılı olmadan DB səviyyəsində
  qorunur:**
  - `execution_allowed` sütunu `CHECK (execution_allowed = 0)` ilə
    məcburidir — heç bir gələcək kod dəyişikliyi bunu `1`-ə çevirə bilməz
    (müqavilənin "execution_allowed=false bütün SHADOW qərarlarında
    məcburidir" tələbi).
  - `shadow_events.event_type` CHECK-i yalnız 9 `SHADOW_*` adını icazə
    verir — heç bir `ORDER_*` event növü mümkün deyil. Əlavə olaraq
    payload-da `order_id`/`mt5_ticket` kimi qadağan olunmuş açarlar
    `record_shadow_event`-də rədd edilir.
  - `prevent_shadow_run_manifest_mutation` trigger-i manifestin bütün
    substantiv sahələrini `INSERT`-dən sonra dondurur (yalnız
    `state`/`state_version`/`halt_reason`/`updated_at` dəyişə bilər) —
    müqavilənin "Run başladıqdan sonra hədəf, metrik və hədlər
    dəyişdirilmir" tələbi.
- `backend/app/database/shadow_run_repository.py`: `register_shadow_run`
  (tam manifest, dəqiq 1 champion + istənilən sayda challenger tələb edir),
  `get_shadow_run`, `start_shadow_run` (registered→started),
  `complete_shadow_run` (started→completed), `halt_shadow_run`
  (registered/started→halted, istənilən an — order cəhdinə kritik
  təhlükəsizlik cavabı üçün).
- `backend/app/database/shadow_event_repository.py`: `record_shadow_event`,
  `list_shadow_run_events`.
- **API endpoint-ləri əlavə edilmədi** — hazırda bu reyestri çağıracaq real
  bir SHADOW icra mühərriki yoxdur (Phase 5-8 yox), ona görə boş API
  səthi əlavə etmək əvəzinə yalnız düzgünlüyü test-lərlə sübut edilmiş
  persistence qatı saxlanıldı. Real çağıran (Phase 5-8-in nəticəsi) hazır
  olanda API əlavə ediləcək.
- Yoxlama: yeni `test_shadow_run_repository.py` (`13` test),
  `test_shadow_event_repository.py` (`6` test) — manifest immutability,
  `execution_allowed` DB-səviyyəli qıfıl, append-only trigger-lər,
  lifecycle keçidləri, ownership/optimistic-lock, qadağan olunmuş payload
  açarları daxil. `test_migration_runner.py` sayğacları `0009`-a
  uyğunlaşdırıldı. Tam backend regressiyası: `352 passed`.
- Bu qat heç bir bazar müşahidəsi, qərar, nəzəri mövqe və ya order
  yaratmır; yalnız gələcək Phase 9 tətbiqi üçün strukturca təhlükəsiz
  saxlama əsasıdır.

## 2026-08-06 — Multiple-testing reyestri: nəticələndirmə artıq ailəvi xəta düzəlişi tətbiq edir

- Phase 3/4 müqaviləsinin "Multiple-testing qeydiyyatı olmadan namizəd qəbul
  edilmir" tələbi tətbiq edildi. Əvvəllər `evaluated → accepted_for_shadow`
  qərarı yalnız tək backtest-in düz (heç bir düzəliş olmadan) 95% etibar
  intervalından çıxarılırdı — eyni replay sessiyasında (eyni məlumatda) neçə
  fərqli hipotez/parametr sınandığından asılı olmayaraq. Bu, statistik
  cəhətdən səhv idi: çox sayda sınaqdan yalnız ən yaxşı görünəni
  nəticələndirmək yanlış müsbət ehtimalını artırır.
- `0008_multiple_testing_trials.sql`: append-only `multiple_testing_trials`
  reyestri — `family_key` (= `replay_session_id`, "eyni məlumat"),
  `family_sequence` (ailə daxilində artan sıra), `backtest_id` üzrə
  `UNIQUE` (idempotent qeydiyyat).
- `backend/app/database/multiple_testing_repository.py`: `register_trial`
  (idempotent), `count_family_trials`, `list_family_trials`.
- **Qeydiyyat nöqtəsi vacibdir:** `evaluate_replay_pattern_candidate_backtest`
  HƏR backtest icrasını **şərtsiz** qeydə alır — sonradan nəticələndirilsin
  ya yox. Əks halda istifadəçi 10 backtest işlədib yalnız ən yaxşısını
  nəticələndirməklə düzəlişdən yayına bilərdi.
- `pattern_candidate_backtest.py`-a `bonferroni_corrected_scenario()` əlavə
  edildi: saxlanmış (düzəlişsiz) backtest artefaktına toxunmadan, yalnız
  nəticələndirmə anında ailənin cari ümumi sınaq sayından (`m`) Bonferroni
  düzəlişli `alpha=0.05/m` və dəqiq `z` (`statistics.NormalDist().inv_cdf`)
  ilə CI-ni yenidən hesablayır. Yalnız `supportive_evidence` ssenarilər
  yenidən hesablanır (düzəliş yalnız aralığı genişləndirə bilər, artıq
  yetərsiz olanı "xilas edə" bilməz).
- `classify_replay_pattern_candidate` indi düzəlişli statusdan qərar verir;
  qaytardığı `PatternCandidateClassificationOutcome` `family_trial_count`
  və `corrected_scenario`-nu daşıyır. API cavabında `meta.multiple_testing`
  altında görünür (`data` sahəsi dəyişməyib, geriyə uyğundur).
- Frontend toxunulmayıb — mövcud "Nəticələndir" düyməsi dəyişmədən işləyir,
  yalnız serverdəki qərar məntiqi düzəldi.
- Yoxlama: yeni `test_multiple_testing_repository.py` (`6` test),
  `pattern_candidate_backtest.py`-a `5` yeni bonferroni testi,
  `test_pattern_candidates_backtest_api.py`-a `2` inteqrasiya testi (ailə
  sayının bir neçə namizəd/təkrar backtest üzrə düzgün toplandığını yoxlayır).
  `test_migration_runner.py` sayğacları `0008`-ə uyğunlaşdırıldı. Tam backend
  regressiyası: `333 passed`.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; düzəliş yalnız
  `accepted_for_shadow` qərarının statistik ciddiliyini artırır.

## 2026-08-05 — Phase 2 worker/scheduler müqaviləsi hərfi tətbiq edildi (`pattern_candidate_backtest`)

- İstifadəçinin iki dəfə açıq təsdiqi ilə (`Tam həcmdə tiklə` → `Tam
  müqaviləni hərfi tiklə`) `PHASE_2_WORKER_SCHEDULER_CONTRACT.md`-dəki tam
  claim/lease/fencing/retry/audit/state-machine/observability modeli
  tətbiq edildi — yalnız `pattern_candidate_backtest` iş növü üçün (müqavilədə
  adı çəkilən 5 iş növünə bu, 6-cı olaraq əlavə edildi; digər 5-i hələ
  yoxdur, real ehtiyac yalnız backtest üçündür).
- Ayrıca worker prosesi qurulmadı — icra sürücüsü FastAPI `BackgroundTasks`-dır;
  claim/lease/fencing DB məntiqi isə düzgün və gələcək real worker tərəfindən
  təkrar istifadə edilə bilər şəkildə yazılıb.
- `0007_analysis_jobs.sql`: `analysis_jobs` (tam vəziyyət maşını —
  `queued/claimed/running/pausing/paused/retry_wait/completed/cancelled/
  interrupted/failed`, monoton `fencing_token`, lease, `state_version`
  optimistic lock, idempotency) + append-only `analysis_job_audit`.
- `backend/app/database/analysis_job_repository.py`: `enqueue_job`
  (idempotent, istifadəçi başına maksimum `3` aktiv iş), `claim_next_job`
  (prioritet+yaranma vaxtı üzrə, vaxtı keçmiş lease-ləri əvvəlcə `interrupted`
  kimi bərpa edir və fencing token-i artırır), `send_heartbeat`,
  `complete_job` (işləyərkən `cancel_requested` görsə `cancelled`-ə keçir,
  nəticəni saxlamır), `fail_job` (yalnız `retryable=True` olanlar exponential
  backoff+jitter ilə `max_attempts`-a qədər təkrarlanır), `request_cancel`
  (queued/retry_wait dərhal, running yalnız kooperativ — tək batch sərhədində
  `complete_job` tərəfindən icra olunur), `queue_metrics`.
- **Real bug tapıldı və düzəldildi:** `enqueue_job`-da idempotency key hash-i
  `created_by` ilə birlikdə hesablanırdı, ona görə fərqli istifadəçilər eyni
  key ilə heç vaxt DB sətrində toqquşmurdu — nəzəri `AnalysisJobOwnershipError`
  qoruması faktiki heç vaxt işə düşə bilməzdi (dead code). Düzəliş: hash indi
  yalnız `job_type:key` üzrədir, ownership yoxlanışı tapılan sətirdə real
  aparılır. Reqressiya testi: `test_enqueue_rejects_key_reused_by_another_user`.
- `backend/app/workers/analysis_job_worker.py`: `run_worker_once` (bir işi
  claim edib tam icra edir — uğur/retry/fail bütün yolları), `drain_queue`
  (bir çağırışda ən çox `max_jobs` iş, sonsuz dövr riski yoxdur). Xəta
  təsnifatı: bilinən domain xətaları (`PatternCandidateNotFoundError` və s.)
  → `retryable=False`; `sqlite3.OperationalError` → `retryable=True`; digər
  gözlənilməz xətalar → `retryable=False` (worker sərhədində şüurlu geniş
  `except`, iş növbəsini bir pis işin çökdürməməsi üçün).
- Yeni API-lər: `POST .../pattern-candidates/{id}/backtest-jobs` (202,
  enqueue + arxa planda dərhal icra), `GET .../backtest-jobs/{job_id}`,
  `POST .../backtest-jobs/{job_id}/cancel`, `GET
  /api/v2/analysis-jobs/metrics`. Mövcud sinxron `POST .../backtest`
  endpoint-i dəyişməz saxlanıldı — job-əsaslı yol əlavədir, əvəzləmə deyil.
- **Frontend hələ toxunulmayıb** — yeni async job endpoint-ləri üçün UI
  yoxdur, mövcud "Backtest et" düyməsi sinxron endpoint-dən istifadə etməyə
  davam edir. Bu, istifadəçi ilə ayrıca müzakirə tələb edən açıq qərardır.
- Yoxlama: yeni `test_analysis_job_repository.py` (`17` test),
  `test_analysis_job_worker.py` (`4` test, real replay session + tick
  data ilə tam uğurlu backtest icrası daxil), `test_analysis_jobs_api.py`
  (`7` test). `test_migration_runner.py` sayğacları `0007`-ə uyğunlaşdırıldı.
  Tam backend regressiyası: `321 passed`. Frontend toxunulmadığı üçün
  ayrıca frontend sınağı aparılmadı.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; iş növbəsi yalnız
  mövcud sinxron backtest hesablamasını asinxron şəkildə işə salır.

## 2026-08-05 — Pattern namizədi UI-si canlı brauzerdə vizual təsdiqləndi

- Real `database/ESAS_PLATFORM.sqlite`-a **toxunulmadı**. Ayrıca, birdəfəlik
  test bazası (`.venv` ilə yeni SQLite fayl, `0001-0006` migrasiyaları
  tətbiq edilmiş) yaradıldı, sintetik GOLD tick zigzag-ı (67 tick) əlavə
  edildi və tam bir replay sessiyası (`max_speed`, `completed`) quruldu.
- Backend `127.0.0.1:8001`-də, frontend `127.0.0.1:5173`-də (hər ikisi
  müvəqqəti, yalnız bu yoxlama üçün) işə salındı; CORS artıq `5173`-ə
  icazə verdiyi üçün əlavə konfiqurasiya lazım olmadı.
- Brauzerdə tam giriş edildi və **Pattern namizədləri** bölməsinin bütün
  dövrü uğurla yoxlanıldı: draft hesablama (M1 vaxt çərçivəsində
  `market_structure_short` real olaraq `candidate_confirmed` göstərdi,
  Python-da əvvəlcədən yoxlanmış nəticə ilə tam üst-üstə düşdü) → "Draft
  kimi qeydə al" → "Backtest et" (n=1, 3 ssenari, "Sübut yetərli deyil") →
  "Nəticələndir" (→ `insufficient_evidence`) → "Arxivləşdir" (→
  `Arxivləşdirilib`). Bütün addımlarda UI mətnləri gözlənilən nəticələri
  göstərdi, brauzer konsolunda **heç bir xəta olmadı**.
- "Bazar strukturu" bölməsi də ayrıca yoxlanıldı — düzgün render olundu.
- Yoxlamadan sonra bütün müvəqqəti proseslər dayandırıldı, `frontend/.env.local`
  silindi, test bazası scratchpad-də qaldı (layihəyə heç nə commit edilmədi).
- Bu, sessiya boyu qeyd edilən "canlı brauzerdə yoxlanmayıb" qeydini
  bağlayır.

## 2026-08-05 — Backtest verdiktindən avtomatik nəticələndirmə (Phase 4)

- Vəziyyət maşınının növbəti addımı: `evaluated → accepted_for_shadow |
  rejected | insufficient_evidence` keçidi əlavə edildi
  (`classify_backtest_verdict`, `POST /api/v2/pattern-candidates/{id}/classify`).
- Verdikt yalnız son backtest-in **"normal" xərc ssenarisindən** deterministik
  hesablanır, yeni statistika yoxdur:
  - `supportive_evidence` → `accepted_for_shadow` (Phase 9 SHADOW hələ
    yoxdur — bu, real ticarət icazəsi vermir, yalnız tarixi sübutun
    əvvəlcədən müəyyən edilmiş həddi keçdiyini qeyd edir);
  - `insufficient_evidence` + səbəb `effective_sample_below_30` →
    `insufficient_evidence` (bəlkə də sadəcə daha çox məlumat lazımdır);
  - `insufficient_evidence` + digər səbəb (kifayət qədər nümunə var, amma
    etibar intervalı sıfırı keçir) → `rejected` (bu, əskik məlumat deyil,
    əksinə sübut).
- `archive_pattern_candidate` genişləndirildi: əvvəllər yalnız `registered`
  vəziyyətindən arxivləşdirmək mümkün idi, indi `evaluated`,
  `accepted_for_shadow`, `rejected`, `insufficient_evidence`-dən də mümkündür.
- Frontend: "Nəticələndir" düyməsi və LIFECYCLE_LABELS ilə aydın vəziyyət
  mətnləri, "real ticarət icazəsi deyil" xəbərdarlığı.
- Yoxlama: backend `293 passed`; frontend production build və `10/10`
  test, lint təmiz.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; `accepted_for_shadow`
  real ticarət icazəsi deyil.

## 2026-08-05 — Backtest v1 bütün 6 hipotezi əhatə edir (Phase 4)

- `market_structure.py`-a tarixi `observations` sahəsi əlavə edildi.
  Dizayn qərarı: hər istiqamət üçün yalnız **rejimin təsdiqlənməyə
  keçdiyi an** (transition into `confirmed_structure`) bir hadisə kimi
  qeyd olunur — davam edən eyni rejimin sonrakı hər pivotu YENİDƏN hadisə
  yaratmır. Səbəb: əks halda uzun bir trend onlarla üst-üstə düşən,
  yüksək korrelyasiyalı "nümunə" yaradardı və effektiv nümunə sayını
  süni artırardı (purged-validation prinsipinə zidd).
- Backtest v1 indi `market_structure_long/short`-u da dəstəkləyir —
  bütün 6 hipotez əhatə olunub.
- Yoxlama: backend `286 passed` (yeni market_structure tarixi hadisə
  testləri, backtest-ə market_structure inteqrasiya testləri); frontend
  production build və `10/10` test, lint təmiz.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır.

## 2026-08-05 — Backtest v1 genişləndirilməsi və istiqamət bug-ı düzəldildi (Phase 4)

- **Vacib düzəliş:** `run_pattern_candidate_backtest` səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, amma real qeydə alınmış
  namizədin `direction` sahəsi hipotez reyestrindən `"long"/"short"` gəlir.
  Bu, real axında backtest-i həmişə `ValueError` ilə uğursuz edərdi (əvvəlki
  testlərdə fixture-larda əl ilə "bullish" yazıldığı üçün gizlənmişdi).
  Düzəliş: funksiya artıq `direction` parametrini qəbul etmir, istiqaməti
  yalnız `hypothesis_id`-dən (`HYPOTHESIS_EVENT_DIRECTION` xəritəsi) təyin
  edir.
- `liquidity_sweep.py`-a `observations: tuple[...]` sahəsi əlavə edildi —
  əvvəllər yalnız son süpürmə saxlanılırdı, indi hər hovuzun tarixi
  süpürmə hadisəsi (varsa) qorunur. Geriyə uyğun, əlavəedici dəyişiklik.
- Backtest v1 indi `liquidity_sweep_reclaim_long/short`-u da dəstəkləyir
  (əvvəllər yalnız `structure_break_long/short`). `market_structure`
  hələ kənarda qalır — o, davamlı rejim konsepsiyasıdır (diskret hadisə
  deyil), tarixi hadisə semantikası üçün ayrıca dizayn qərarı tələb edir.
- Yoxlama: backend `281 passed` (yeni liquidity_sweep tarixi hadisə testi,
  yenilənmiş backtest testləri — istiqamət bug-ının reqressiya testi
  daxil); frontend production build və `10/10` test, lint təmiz.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır.

## 2026-08-05 — Pattern namizədi backtest v1 (Phase 4)

- Backtest v1 **yalnız** `structure_break_long`/`structure_break_short`
  hipotezlərini dəstəkləyir — səbəb: yalnız bu ikisinin arxasındakı
  detektorlar (`bos_choch.observations`, `retest.observations`) **bütün
  tarixi təkrarları** saxlayır. `market_structure` və `liquidity_sweep`
  hazırda yalnız son müşahidəni saxlayır; onları backtest etmək statistik
  cəhətdən mənasız (1 nümunə) olardı, ona görə v1-ə şüurlu şəkildə
  daxil edilmədi.
- `run_pattern_candidate_backtest` (`pattern_candidate_backtest.py`):
  hipotezin bütün tarixi `confirmed_retest` hadisələrini tapır, hər biri
  üçün giriş = təsdiq barının öz bağlanışı (mövcud `forward_closed_bar_outcome`
  konvensiyası ilə eyni), çıxış = horizon bar sonrakı bağlanış. Normal/pis/stress
  xərc ssenariləri, effektiv nümunə sayı, hit rate, 95% etibar intervalı
  (`statistical_reliability.py` ilə eyni düstur və `n≥30` həddi) hesablanır.
- `0006_pattern_candidate_backtests.sql`: append-only backtest nəticələri
  cədvəli. `0005` migrasiyası (bu sessiyada yaradılıb, heç bir real bazaya
  tətbiq edilməyib) `lifecycle_state` CHECK-i müqavilədəki tam vəziyyət
  lüğəti ilə (`evaluated` daxil) əvvəlcədən genişləndirilərək düzəldildi —
  DROP-based rebuild lazım olmasın deyə.
- Yeni endpoint-lər: `POST/GET /api/v2/pattern-candidates/{id}/backtest`.
  İlk uğurlu backtest namizədi `registered → evaluated`-ə keçirir; təkrar
  işlətmə `evaluated`-də qalır, amma yeni backtest sətri və audit qeydi
  əlavə edir (heç bir əvvəlki nəticə silinmir/üzərinə yazılmır).
- Frontend: qeydə alınmış namizədlər cədvəlində "Backtest et" düyməsi və
  ssenari nəticələri (n, net %, sübut statusu).
- Yoxlama: backend `277 passed` (yeni backtest pure `7` + repository `5` +
  API `3` test); frontend production build və `10/10` test, lint təmiz.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; "evaluated" real
  ticarət icazəsi deyil, yalnız tarixi simulyasiyadır.

## 2026-08-05 — Pattern namizədi persistence/`registered` qatı (Phase 4)

- `0005_pattern_candidates.sql` migrasiyası: `pattern_candidates` (dəyişməz
  qeydiyyat, `lifecycle_state IN ('registered','archived')`, optimistic
  `state_version` lock) və append-only `pattern_candidate_audit` cədvəlləri
  əlavə edildi.
- `backend/app/database/pattern_candidate_repository.py`: `register_pattern_candidate`
  (yalnız `candidate_confirmed` slotlar, `candidate_id`-ə görə idempotent),
  `get_pattern_candidate`, `list_pattern_candidates` (owner-scoped keyset
  pagination), `archive_pattern_candidate` (ownership + optimistic lock).
- `replay_pattern_candidates.py`-a `register_replay_pattern_candidate`
  əlavə edildi: server HƏMİŞƏ sessiyanı yenidən hesablayır, klient heç vaxt
  evidence/condition_state göndərmir — yalnız real, hazırkı causal nəticə
  qeydə alına bilir.
- Yeni qorunan API-lər (müqavilədə göstərilən adlarla): `POST
  /api/v2/pattern-candidates`, `GET /api/v2/pattern-candidates`, `GET
  /api/v2/pattern-candidates/{id}`, `POST /api/v2/pattern-candidates/{id}/archive`.
  `features`/`backtest` alt-resursları hələ tətbiq edilməyib (backtest
  infrastrukturu yoxdur).
- Frontend: hər `candidate_confirmed` kartında "Draft kimi qeydə al" düyməsi,
  ayrıca "Qeydə alınmış namizədlər" cədvəli (bütün sessiyalar, owner-scoped)
  və "Arxivləşdir" əməliyyatı əlavə edildi.
- Şüurlu şəkildə kənarda: `running`, `evaluated`, `accepted_for_shadow`,
  `rejected` və digər backtest-asılı vəziyyətlər tətbiq edilməyib — bunlar
  backtest mühərriki olmadan mənasız/saxta olardı.
- Yoxlama: backend `262 passed` (yeni `test_pattern_candidate_repository.py`
  `7` test + `test_pattern_candidates_persistence_api.py` `4` test; mövcud
  `test_migration_runner.py` sayğacları `0005`-ə uyğunlaşdırıldı); frontend
  production build və `10/10` test, lint təmiz.
- Bu qat strategiya, siqnal, giriş, risk ölçüsü və order yaratmır; "registered"
  vəziyyəti real ticarət icazəsi deyil.

## 2026-08-05 — Phase 2 rəsmi bağlanışı (STABLE)

Phase 2 (Replay və məlumat keyfiyyəti) rəsmi olaraq bağlanıb. Qərar və rəsmi
qəbul sübutu: `docs/releases/PHASE_2_STABLE.md`.

- Bütün Phase 2 roadmap bəndləri (`PROJECT_ROADMAP.md`) tamamlanmış idi;
  bu addım yalnız Phase 1-dəki kimi rəsmi qəbul sənədini yazdı — yeni kod
  dəyişikliyi yoxdur.
- Əsas sübut mənbəyi: 2026-08-04 tarixli real `GOLD` intervalı üzərində
  aparılmış `step`/`max_speed` cross-mode qəbul sınağı
  (`.runtime/phase2-acceptance/phase2-replay-latest.json`), nəticə `PASSED`,
  kritik tapıntı `0`, xam tick sayı dəyişməz (`1,258,269`).
- Tarixi `DQ-009` (`542` warning, `received_at` < `event_timestamp`) qalıq
  keyfiyyət qeydi kimi sənədləşdirilib; kök səbəb MT5 Bridge `1.6.1`-də
  düzəldilib, canlı axına aid deyil, Phase 2 xam məlumatı dəyişdirmədiyi üçün
  tarixi tick-lər geriyə düzəldilməyib.
- `PROJECT_ROADMAP.md`-də Phase 2 statusu `IN PROGRESS`-dən
  `COMPLETED — STABLE`-ə, cari mərhələ `Phase 4`-ə yeniləndi.
- Kod, test və CI dəyişmədi — bu, sənədləşdirmə/qərar addımıdır.

## 2026-08-05 — Draft pattern namizədi generatoru (Phase 4)

- `pattern_candidate 1.0.0` əlavə edildi (`backend/app/strategies/pattern_candidate.py`):
  mövcud causal detektorların (bazar strukturu, likvidlik süpürməsi, BOS/CHoCH+retest)
  nəticələrini `pattern_hypothesis_registry`-dəki 6 hipotezə (market_structure_long/short,
  liquidity_sweep_reclaim_long/short, structure_break_long/short) birləşdirir.
- Hər namizəd yalnız `draft` lifecycle vəziyyətindədir; `candidate_confirmed`,
  `no_candidate` və `insufficient_data` şərt statusları açıq ayrılır. Backtest,
  label/horizon ölçümü, persistence/state machine və qəbul/rədd qərarı bu artıma
  daxil deyil — `PHASE_4_PATTERN_TECHNICAL_ANALYSIS_CONTRACT.md`-də ayrıca sonrakı
  addımlar kimi qeyd olunub.
- Yeni qorunan, yalnız-oxuma `GET /api/v2/replay-sessions/{session_id}/pattern-candidates`
  endpoint-i əlavə edildi (`replay_pattern_candidates.py`); ownership, completed-state
  və dataset-drift qoruması digər analiz endpoint-ləri ilə eynidir.
- `ReplayAnalysisContext` mövcud `market_structure`/`liquidity_sweep`/`bos_choch`/
  `retest` nəticələrini artıq dataclass kimi də daşıyır (əvvəllər yalnız dict idi);
  bu, `replay_strategy.py` kimi mövcud çağırış yerlərini pozmayıb.
- Frontend-də "Pattern namizədləri" bölməsi əlavə edildi
  (`pattern-candidates-panel.tsx`): 6 slotu ayrı kartlarda, `draft` etiketi və
  "backtest/label/qəbul qərarı yoxdur" xəbərdarlığı ilə göstərir.
- Yoxlama: backend `251 passed` (yeni `test_pattern_candidate.py` — `6` test,
  `test_replay_technical_analysis_api.py`-a `2` yeni API testi); frontend
  production build və `10/10` test keçdi, lint təmizdir.
- Bu qat strategiya, siqnal, giriş, risk ölçüsü və order yaratmır; "draft" statusu
  real ticarət icazəsi deyil.
- Canlı brauzerdə vizual yoxlama edilməyib (əvvəlki sessiyalardakı eyni xarici
  mühit məhdudiyyətinə görə); yalnız avtomatlaşdırılmış test/build sübutu var.

## 2026-08-05 — Causal Fair Value Gap 1.0.0 tamamlandı

- `fair_value_gap 1.0.0` üç ardıcıl bağlanmış bar arasında yaranan bullish/bearish
  qiymət boşluğunu yalnız bağlanmış barlarla izləyir; boşluq yalnız yaranandan
  sonrakı barlarla `open`, `partially_filled`, `filled` və ya `invalidated`
  vəziyyətinə keçir, gələcək bar boşluğun yaranmasına təsir etmir.
- Minimum boşluq (bps) konfiqurasiya olunur; `insufficient_data` və `no_gap`
  halları açıq göstərilir. Nəticə bar fingerprint-inə bağlı deterministik
  SHA-256 izi daşıyır və `replay_analysis` cavabına (`ANALYSIS_API_VERSION 1.5.0`)
  əlavə edilib.
- Frontend-də ayrıca "Fair Value Gap" menyusu və tədqiqat kartı əlavə edildi;
  köhnə backend cavabı üçün uyğunluq xəbərdarlığı qorunur.
- Tam yoxlama: backend `243 passed` (yeni `fair_value_gap` modul testləri daxil);
  frontend production build və `9/9` test keçdi.
- Bu qat strategiya, siqnal, giriş, risk ölçüsü və order yaratmır.
- Commit `1aa85c8` ilə edildi və istifadəçi təsdiqi ilə `origin/main`-ə push edildi.

## 2026-08-05 — Sidebar lint düzəlişi və CI yaşıl

- `dashboard-navigation.tsx`-də `eslint-plugin-react-hooks 7.x`-in
  `react-hooks/immutability` qaydasını pozan render-zamanı `previousGroup`
  mutasiyası aradan qaldırıldı; menyu qrup başlığı indi render-dən əvvəl
  modul səviyyəsində hesablanan sabit massivdən (`MENU_ENTRIES`) götürülür.
- Bu düzəliş FVG detektorundan asılı deyildi, əvvəldən mövcud koddan qaynaqlanırdı.
- Lokal `npm run lint`, `npm run test` (build + `9/9` test) təmiz keçdi.
- Commit `7d49f97` ilə `origin/main`-ə push edildi.
- GitHub Actions "Tests" iş axını (run `31011108501`) Backend və Frontend
  (lint daxil) job-larının hər ikisində **uğurlu** nəticə verdi; `main` budağı
  indi CI-də yaşıldır.

## 2026-08-05 — Causal retest 1.0.0 tamamlandı

- No-lookahead retest müşahidəsi backend və frontend-ə əlavə edildi.
- Tam backend regressiyası: `239 passed`; frontend hədəf testi və lint keçdi.
- Növbəti müstəqil mərhələ causal FVG detektorudur və ayrıca təsdiq tələb edir.

## Phase 4 causal BOS/CHoCH detektoru

2026-08-05 tarixində `bos_choch 1.0.0` tamamlandı. Təsdiqlənmiş causal bazar strukturu
pivotları yalnız təsdiq barından sonra gələn bağlanmış barların close qiyməti ilə yoxlanır.
Mövcud struktur rejimi ilə eyni istiqamətli qırılma BOS, əks istiqamətli qırılma CHoCH kimi
müşahidə olunur; rejim məlum deyilsə nəticə ayrıca `unclassified_break` qalır. Bullish və bearish
nəticələr, yetərsiz, qırılma olmayan və eyni barda iki istiqamətin qırıldığı ziddiyyətli hallar
ayrıdır. Parametrlər, upstream izlər və nəticə deterministik fingerprint ilə saxlanır. Frontend
nəticələri sadə Azərbaycan dilində ayrı kartlarda göstərir. Bu qat yalnız tarixi tədqiqatdır;
siqnal, giriş, risk ölçüsü və order yaratmır. Tam yoxlama: backend `236 passed`; frontend `4`
test, lint və production build keçdi.

## Phase 4 causal likvidlik süpürməsi detektoru

2026-08-05 tarixində `liquidity_sweep 1.0.0` tamamlandı. Təsdiqlənmiş causal pivotlardan
equal-high/equal-low hovuzları mərhələli snapshot kimi yaradılır; sonradan gələn pivot əvvəlki
hovuzun tarixini dəyişmir. Sweep yalnız hovuz məlum olduqdan sonra bağlanmış barın wick məsafəsi
və səviyyəyə geri bağlanması ilə təsdiqlənir. Bullish, bearish, yetərsiz, sweep olmayan və eyni
barda iki tərəfin süpürüldüyü ziddiyyətli hallar ayrıdır. Konfiqurasiya və upstream izlər
deterministik fingerprint-də saxlanır. Frontend nəticələri ayrı tədqiqat kartlarında göstərir.
Qat siqnal, giriş, risk ölçüsü və order yaratmır.
Tam yoxlama: backend `232 passed`; frontend `4` test, lint və production build keçdi.

## Phase 4 causal bazar strukturu detektoru

2026-08-05 tarixində `market_structure 1.0.0` tamamlandı. Yalnız bağlanmış barlardan
istifadə edən pivot qaydası sağ tərəfdəki barlar bağlandıqdan sonra təsdiq verir; buna görə
gələcək məlumat əvvəlki HH/HL və LH/LL nəticəsinə sızmır. Yüksəliş və eniş müşahidələri,
yetərsiz və ziddiyyətli hallar, pivotun bar vaxtı ilə təsdiq vaxtı və deterministik fingerprint
ayrıca saxlanılır. Frontend nəticəni iki müstəqil araşdırma kartında göstərir. Tam backend
`227 passed`; frontend `4` test, lint və production build keçdi. Qat ticarət siqnalı,
mövqe ölçüsü və order yaratmır.

## Phase 4 xronoloji walk-forward müqayisə təməli

2026-08-04 tarixində `chronological_holdout_comparison 1.0.0` əlavə edildi. EMA və
RSI nəticələri təsadüfi qarışdırılmadan xronoloji inkişaf və toxunulmamış yoxlama
intervallarına ayrılır. İnkişaf sərhədindən sonrakı qiymətə ehtiyac duyan nəticələr
inkişaf hesabından ayrıca çıxarılır; yoxlama qiymətlərinin dəyişməsi inkişaf yekununu
dəyişmir. Manifest strategiya parametrlərini, bölgünü, nəticə üfüqünü və bütün upstream
fingerprint-ləri saxlayır. Frontend 60/40, 70/30 və 80/20 bölgülərini, hər intervalın
əhatəsini, istiqamətini, orta xərcsiz dəyişməsini və sərhəddən çıxarılan nümunələri
Azərbaycan dilində ayrı göstərir. Qat yalnız tarixi tədqiqatdır, canlı siqnal və order
yaratmır. Tam backend `189 passed`, frontend lint/build və `3` test keçdi.

## Phase 4 tarixi nəticə ölçmə infrastrukturu

2026-08-04 tarixində `forward_closed_bar_outcome 1.0.0` əlavə edildi. EMA və RSI
müşahidələri seçilən üfüqdən sonrakı qapalı barın qiymət dəyişikliyi ilə ölçülür. Hazır,
yetkinləşməmiş və warm-up nəticələri ayrıdır; yuxarı/aşağı/dəyişməz istiqamət və rejim üzrə
orta dəyişiklik göstərilir. Gələcək bar yalnız nəticəni etiketləyir, ilkin müşahidəni və
əvvəlki hesablamaları dəyişmir. Hər nəticə dataset, bar və strategiya fingerprint-inə
bağlanır. Frontend-də hər strategiyanın öz tarixi nəticə bölməsi və üfüq seçimi var.
Bu qat uğur və ya al/sat siqnalı deyil, order yaratmır. Tam backend `181 passed`, frontend
lint/build və `3` test nəticəsi uğurludur.

## Phase 4 ikinci strategiya müşahidə modulu

2026-08-04 tarixində `rsi_regime_observation 1.0.0` əlavə edildi. Causal RSI yalnız
bağlanmış barlarda aşağı, neytral və yüksək rejimlərə ayrılır; hədlər konfiqurasiya olunur.
Warm-up, inclusive sərhədlər, determinizm və no-lookahead sınaqları keçir. EMA və RSI
frontend laboratoriyasında ayrı kartlardır və hər biri öz versiya/fingerprint izini göstərir.
Qat yalnız tədqiqat üçündür, siqnal və order yaratmır. Tam backend `173 passed`, frontend
lint/build və `3` test nəticəsi uğurludur.

## Phase 2 real replay qəbul sübutu

2026-08-04 tarixində production bazası yoxlanmış SQLite backup-dan sonra Phase 2
sxeminə keçirildi və real `GOLD` intervalı ilə qəbul sınağı tamamlandı.

- Eyni 60 saniyəlik, `542` tick-lik dataset iki `step` və iki `max_speed`
  sessiyasında müstəqil icra edildi.
- Dörd sessiyanın dataset və nəticə fingerprint-ləri eyni oldu; cross-mode
  müqayisəsi keçdi.
- Xam tick sayı sınaqdan əvvəl və sonra `1,258,269` qaldı.
- Qəbul nəticəsi `PASSED`, kritik keyfiyyət tapıntısı `0` oldu.
- `DQ-009` bütün `542` tarixi tick üçün `received_at` vaxtının `event_timestamp`-dan
  əvvəl görünməsini xəbərdarlıq kimi qeyd etdi. Kök səbəb broker server vaxtının UTC
  işarəsi ilə göndərilməsi idi.
- MT5 Bridge `1.6.1` yeni event-lərdə broker server vaxtını UTC-yə normallaşdırır;
  mövcud xam tick-lər dəyişdirilmədi. Canlı qəbulda yeni tick-lərin gecikməsi təxminən
  `0.74 saniyə`, event/source vaxt fərqi `0 ms`, növbə isə `0 / 1000` oldu.
- Backend `133 passed`; frontend lint, build və render testi keçdi.
- İlk yalnız-oxuma texniki analiz əsası quruldu: `bar-builder 1.0.0` replay
  tick-lərindən `M1`, `M5`, `M15` və `H1` üzrə yalnız tam bağlanmış UTC mid-price
  şamları yaradır. Nəticə mənbə lineage-i və deterministik fingerprint daşıyır,
  boş/açıq şamlar doldurulmur və xam tick bazasına yazılmır. Modul testləri `9 passed`,
  tam backend regressiyası `142 passed` nəticəsi verdi.
- Yalnız-oxuma `indicator-package 1.0.0` əlavə edildi. EMA ayrıca SMA seed və eksponensial
  yenilənmə, RSI və ATR isə Wilder hesablaması ilə yalnız bağlanmış şamlardan qurulur.
  Warm-up tamamlanmayan hər nöqtə `insufficient_data` kimi işarələnir; nəticə bar
  fingerprint-inə bağlanır və gələcək şam əvvəlki nöqtələri dəyişmir. Yeni indikator
  testləri `11 passed`, tam backend regressiyası `153 passed` nəticəsi verdi.
- Sübut faylı `.runtime/phase2-acceptance/phase2-replay-latest.json` yolunda saxlanır
  və xam tick payload-u ehtiva etmir.

## Replay idarəetmə dashboard-u

2026-08-04 tarixində qorunan monitorinq panelinə Phase 2 replay idarəetməsi əlavə edildi.

- İstifadəçi simvol, vaxt intervalı və `step/max_speed` rejimi ilə sessiya yarada bilir.
- Sessiya siyahısı, detalı, lifecycle əmrləri, event səhifələri və tamamlanmış
  sessiyanın keyfiyyət hesabatı bir ekrandan idarə olunur.
- Əmrlər unikal idempotency açarı və cari `state_version` ilə göndərilir.
- Loading, empty, API xətası, conflict və bitmiş giriş sessiyası göstərilir.
- Mobil görünüş və klaviatura ilə istifadə qorunur.
- Replay siyahısı və detal API-si istifadəçi sahibliyini serverdə də məcburi edir.
- Frontend lint/build/render və tam backend `133 passed` nəticəsi ilə keçdi.
- Bölmə ticarət qərarı və əməliyyatı vermir.

## Public replay keyfiyyət hesabatı

2026-08-04 tarixində
`GET /api/v2/replay-sessions/{session_id}/quality-report` endpoint-i əlavə edildi.

- Yalnız sessiyanın sahibi tamamlanmış replay hesabatını oxuya bilir.
- Public cavab `data` və `meta.api_version=2` contract-ı ilə versiyalanır.
- Mövcud report ID və content fingerprint deterministik saxlanır.
- Daxili quality-report endpoint-i geriyə uyğun qalıb.
- Xam tick dəyişməzliyi və təkrar hesabat reproduksiyası testlərlə təsdiqlənib.
- Tam backend nəticəsi `132 passed`.

## Replay event oxuma API-si

2026-08-04 tarixində qorunan
`GET /api/v2/replay-sessions/{session_id}/events` endpoint-i əlavə edildi.

- Yalnız sessiyanın sahibi event-ləri oxuya bilir.
- Sıra `(event_timestamp, event_id)` üzrə deterministikdir.
- Cursor imzalanır, istifadəçiyə və sessiyaya bağlanır və vaxtı məhduddur.
- Sessiya yaradıldıqdan sonra gələn tick-lər snapshot sərhədini keçə bilmir.
- Səhifələr arasında dublikat və boşluq yaranmır; xam tick-lər dəyişmir.
- Tam backend nəticəsi `129 passed`.

## Replay lifecycle command API-si

2026-08-04 tarixində qorunan
`POST /api/v2/replay-sessions/{session_id}/commands` endpoint-i əlavə edildi.

- `start`, `step`, `pause`, `resume` və `cancel` qanuni vəziyyətlərdə işləyir.
- Dəyişiklik yalnız sessiyanın sahibinə icazə verilir.
- `Idempotency-Key` açıq saxlanmır; SHA-256 hash-i append-only command jurnalına yazılır.
- `expected_state_version` köhnə yazını `409` ilə təhlükəsiz rədd edir.
- Session, progress/checkpoint, audit və idempotency qeydi eyni transaction-da saxlanır.
- Audit xətası bütün əməliyyatı geri qaytarır və xam tick-lər dəyişmir.
- Tam backend nəticəsi `125 passed`; frontend lint və production build keçdi.

Son yenilənmə: 2026-08-06
Cari mərhələ: Phase 4
Status: PHASE 1 STABLE — PHASE 2 STABLE — PHASE 4 IN PROGRESS
Əsas budaq: `main`

## Phase 1 yekun qəbul nəticəsi

- Rəsmi canlı sınaq `2026-08-03 08:33:13 +04:00` tarixində başlayıb və
  `2026-08-04 11:44:06 +04:00` tarixində müqayisə edilib.
- `27.18` saat ərzində `340866` yeni tick qəbul olunub.
- Yeni rədd edilmiş event yaranmayıb; sayğac `7343` səviyyəsində qalıb.
- Disk növbəsi `0 / 1000`, tick axını `active`, SQLite `quick_check=ok` qalıb.
- Məlumat itkisi təsdiqi və audit izi qorunub; avtomatik nəticə `PASSED` olub.
- Yekun regressiya: backend `16 passed`, frontend lint/build/render keçib, MT5
  Bridge və MQL5 queue test faylı `0 errors, 0 warnings` ilə kompilyasiya edilib.
- Phase 1 rəsmi bağlanıb və məlumat qəbul qatı `Stable` qəbul edilib. Bu qərar
  real ticarət və ya order icazəsi vermir.

## Phase 2 üçün bazardan asılı olmayan dizayn hazırlığı

- Phase 2-nin ilk istehsal kodu tamamlandı: SQLite bazasını `mode=ro` və
  `query_only` ilə açan tick replay repository-si əlavə edildi.
- Repository `[start_at, end_at)` intervalı, simvol sərhədi, `1..1000` limit və
  `(event_timestamp, event_id)` keyset səhifələməsi tətbiq edir.
- Eyni timestamp-li tick-lərin deterministik ardıcıllığı, səhifələr arasında
  boşluq/dublikat olmaması, boş interval, validation və xam sətirlərin
  dəyişməzliyi yoxlanıldı: yeni testlər `6 passed`, tam backend `22 passed`.
- Canlı bazada migration edilməyib, mövcud API dəyişdirilməyib və ticarət/order
  funksiyası əlavə olunmayıb.
- Versiyalanmış migration runner-i əlavə edildi: SHA-256 checksum nəzarəti,
  eksklüziv transaction, xətada rollback, təkrar icrada no-op və dağıdıcı SQL-in
  ilkin rəddi tətbiq olunur.
- `idx_tick_events_replay(symbol, event_timestamp, event_id)` indeksi yalnız
  müvəqqəti bazada tətbiq və query planında təsdiq edildi; canlı database faylına
  toxunulmadı və production yolu default olaraq açıq icazəsiz rədd edilir.
- Migration üzrə yeni `6` test və tam backend üzrə `28` test keçdi.
- Replay dataset snapshot modulu əlavə edildi: seçilmiş interval sabit read
  transaction-ında maksimum `1000`-lik batch-lərlə oxunur, bütün dataset yaddaşa
  yüklənmir.
- Snapshot tick sayını, ilk/son `(event_timestamp, event_id)` mövqeyini və kanonik
  `event_id` axınından versiyalanmış SHA-256 fingerprint-i hesablayır.
- Snapshot üzrə `7` yeni test və tam backend üzrə `35` test keçdi; canlı baza,
  mövcud API və ticarət sərhədləri dəyişdirilmədi.
- `0002` migration-u ilə `replay_sessions`, sessiya siyahı/state/owner indeksləri,
  `replay_session_audit` və append-only qoruyucu trigger-lər əlavə edildi.
- Müvəqqəti bazada rejim, vəziyyət, interval, tick/progress constraint-ləri,
  foreign key, `ON DELETE RESTRICT`, audit `UPDATE/DELETE` bloklanması və Phase 1
  sətirlərinin qorunması yoxlanıldı.
- Schema/migration hədəf testləri `16 passed`, tam backend `45 passed` oldu; canlı
  database faylına migration tətbiq edilmədi.
- Replay sessiyası yaratma repository-si əlavə edildi: qeyri-şəffaf kriptoqrafik
  session ID, immutable girişlər, snapshot metadatası və ilkin `create` audit sətri
  eyni transaction daxilində saxlanılır.
- Dolu dataset ilkin `created`, boş dataset ilkin `completed` vəziyyətində yaradılır;
  audit insert xətası sessiya insert-ini də tam rollback edir.
- Sessiya repository-si üzrə `11` yeni test və tam backend üzrə `56` test keçdi;
  xam tick məlumatı, canlı baza, API və ticarət sərhədləri dəyişdirilmədi.
- Replay sessiyasının qanuni `start`, `pause`, `resume`, `complete`, `cancel`,
  `interrupt` və `fail` keçidləri repository sərhədində tətbiq edildi.
- Terminal vəziyyətdən keçid, gözlənilməyən cari vəziyyət, geriyə gedən və dataset
  ölçüsünü aşan progress, yaxud datasetə aid olmayan checkpoint fail-closed rədd edilir.
- Vəziyyət, progress, checkpoint və append-only audit eyni transaction-da saxlanılır;
  audit xətasında bütün keçid rollback edilir və immutable sessiya girişləri qorunur.
- Sessiya yaradılması və həyat dövrü üzrə hədəf testlər `22 passed`, tam backend
  `67 passed` oldu; canlı baza, API, frontend və worker dəyişdirilmədi.
- `step` rejimi üçün `1..1000` tick həddində atomik batch emalı əlavə edildi;
  checkpoint-dən sonrakı tick-lər kanonik sıra ilə oxunur və son batch sessiyanı
  avtomatik `completed` edir.
- `0003` migration-u addım əmrlərini unikal idempotency açarı ilə append-only saxlayır;
  eyni parametrli təkrar əmr əvvəlki nəticəni qaytarır, fərqli parametrli təkrar açar
  fail-closed rədd edilir.
- Progress, checkpoint, audit və idempotency qeydi bir transaction-dadır; məcburi
  audit xətası bütün addımı rollback edir.
- `step` repository-si üzrə `8` yeni test, hədəf paket üzrə `25 passed` və tam backend
  üzrə `75 passed` nəticəsi əldə edildi; yalnız müvəqqəti test bazaları istifadə olundu.
- `max_speed` orchestrator-u əlavə edildi: hər transaction-da maksimum `1000` tick
  emal edir, bütün dataset-i yaddaşa yükləmir və hər batch-dən sonra vəziyyəti yenidən
  yoxlayır.
- Pause/resume və restart son uğurlu checkpoint-dən boşluqsuz davam edir; completed
  sessiya yenidən emal olunmur, audit xətasında cari batch rollback edilir.
- Hər yeni və restart olunmuş icrada dataset say, sərhəd və fingerprint ilə yenidən
  təsdiqlənir; tick sayı eyni qalsa belə event əvəzlənməsi fail-closed aşkarlanır.
- `max_speed` üzrə `9` yeni test və tam backend üzrə `84 passed` nəticəsi əldə edildi;
  canlı baza, API, frontend və ticarət sərhədləri dəyişdirilmədi.
- Tamamlanmış `step` və `max_speed` sessiyaları üçün dəyişməz nəticə manifesti əlavə
  edildi. Manifest intervalı, rejimi, müqavilə versiyalarını, dataset izini və
  domen-ayrılmış kanonik nəticə fingerprint-ini daşıyır.
- Eyni dataset-in fərqli icra və manifest batch ölçülərində eyni fingerprint verməsi,
  natamam sessiyanın və dəyişmiş/uyğun olmayan dataset və müqavilələrin fail-closed
  rəddi yoxlanıldı. `8` yeni test və tam backend üzrə `92 passed` nəticəsi əldə edildi;
  canlı baza, API, frontend və ticarət sərhədləri dəyişdirilmədi.
- İlk streaming məlumat keyfiyyəti analizatoru əlavə edildi: `DQ-002` geriyə gedən
  mənbə vaxtını source/module seqmentində, `DQ-004` konfiqurasiya olunan zaman
  boşluğunu, `DQ-011` isə ardıcıl eyni payload namizədini ayrıca aşkarlayır.
- Eyni timestamp-li qanuni tick, hədd sərhədləri, module keçidi, fərqli batch
  ölçülərində deterministik nəticə, stabil finding ID və xam tick dəyişməzliyi
  yoxlanıldı; `5` yeni test və tam backend üzrə `97 passed` nəticəsi əldə edildi.
- Tamamlanmış replay sessiyasını nəticə manifesti ilə bağlayan keyfiyyət hesabatı
  əlavə edildi. Hesabat tapıntı səviyyələrindən deterministik `pass`, `review` və
  `fail` statusu, səviyyə sayları, stabil report ID və məzmun fingerprint-i yaradır.
- `DQ-005` mənfi spread qaydası critical səviyyədə əlavə edildi; sıfır qiymət bu
  qaydaya düşmür. Hesabat üzrə `5` yeni test, bütün backend üzrə `102 passed` oldu.
- `DQ-003` event/source vaxt fərqi, `DQ-006` sıfır və natamam qiymət cütü, `DQ-007`
  qeyri-sonlu/mənfi ədəd, `DQ-008` event müqaviləsi və `DQ-009` qəbul gecikməsi
  qaydaları dəqiq warning/critical sərhədləri ilə streaming analizatora əlavə edildi.
- Dəqiq hədlər, mənfi qəbul gecikməsi, sıfır qiymətin spread-dən ayrılması və
  hesabat regressiyası yoxlanıldı; tam backend üzrə `105 passed` nəticəsi əldə edildi.
- `DQ-010` tick sürəti, interval və spread paylanmalarını sabit yaddaşla hesablayır;
  sıfır/natamam qiymət cütləri ayrıca sayılır və nəticə replay hesabatının məzmun
  fingerprint-inə daxildir. Tam backend üzrə `108 passed` nəticəsi əldə edildi.
- Tamamlanmış replay keyfiyyət hesabatı autentifikasiyalı daxili read-only endpoint-ə
  çıxarıldı; giriş, mövcud olmayan və tamamlanmamış sessiya sərhədləri yoxlanıldı.
  Tam backend üzrə `110 passed` nəticəsi əldə edildi.

- Phase 11 üçün tam qərar-nəticə lineage-i, abstain/risk-block daxil selection-bias
  qoruması, yetişmiş label, model performansı və drift monitorinqi, təhlükəsiz REVIEW,
  dəyişməz yeni model versiyası, yenidən SHADOW qapısı, Knowledge Base governance-i və
  rollback müqaviləsi hazırlandı; canlı model özbaşına dəyişmir və risk artırılmır.
- Phase 10 üçün default-bağlı məhdud icra, dəyişməz run manifesti, təzə manual təsdiq,
  atomik pre-trade risk qapısı, idempotent order həyatı, broker reconciliation, davamlı
  kill switch və audit müqaviləsi hazırlandı; bu yalnız gələcək dizayndır, MT5 order
  interfeysi və real ticarət aktivləşdirilməyib.
- Phase 9 üçün real bazar axınında order-siz SHADOW müşahidəsi, səbəbiyyətə uyğun
  nəzəri fill və portfolio, champion/challenger müqayisəsi, restart/kəsinti qoruması,
  statistik qəbul qapısı və yalnız məhdud icra baxışına tövsiyə müqaviləsi hazırlandı;
  tətbiq Phase 1–8 qəbulundan asılıdır və brokerə heç bir əmr göndərmir.
- Phase 8 üçün deterministik analiz birləşdirməsi, izahlı qərar proposal-u, abstain,
  müstəqil risk qapısı, nəzəri mövqe ölçüsü, portfolio limitləri, halt, manual
  müdaxilə və SHADOW eligibility müqaviləsi hazırlandı; tətbiq Phase 1–7 qəbulundan
  asılıdır və real order yaratmır.
- Phase 7 üçün versiyalanmış bilik claim-i, evidence graph, scope və bazar rejimi
  uyğunluğu, etibarlılıq müddəti, zidd sübut, REVIEW trigger-ləri, governance və
  təhlükəsiz retrieval müqaviləsi hazırlandı; tətbiq Phase 1–6 qəbulundan asılıdır.
- Phase 6 üçün xəbər mənbə/lisenziya reyestri, dərc və qəbul vaxtının ayrılması,
  revision və fundamental vintage qorunması, entity mapping, point-in-time analiz,
  təsir ölçümü və standart event sərhədi müqaviləsi hazırlandı; tətbiq Phase 1–5
  qəbulundan asılıdır.
- Phase 5 üçün deterministik qrafik renderi, Visual AI dataset lineage-i, zaman və
  label sızması qoruması, model reproduksiyası, statistik baseline müqayisəsi və
  SHADOW sərhədi müqaviləsi hazırlandı; tətbiq Phase 1–4 qəbulundan asılıdır.
- Replay oxuması, məlumat keyfiyyəti, sessiya həyat dövrü, frontend ekranları və
  təhlükəsiz database migration müqavilələri hazırlanıb.
- Performans və yaddaş sınağı müqaviləsi hazırlanıb: kiçik, orta, böyük və stress
  dataset pillələri; replay, keyfiyyət analizi, paralel SQLite yazma/oxuma,
  migration, qorunan API və frontend ölçüləri müəyyən edilib.
- Yük və migration sınaqlarının canlı `database/ESAS_PLATFORM.sqlite` üzərində
  aparılması qadağandır; onlar yalnız sintetik müvəqqəti bazada işləyəcək.
- Phase 2 giriş və icazə müqaviləsi hazırlanıb: müşahidəçi, operator, auditor və
  administrator rolları, ownership, yüksək riskli əməliyyatların yenidən
  autentifikasiyası və append-only təhlükəsizlik auditi müəyyən edilib.
- Heç bir rol xam tick və audit sətrini dəyişə, siqnal və ya order yarada bilməz.
- Phase 2 müşahidə və xəbərdarlıq müqaviləsi hazırlanıb: platforma sağlamlığı,
  replay vəziyyəti və məlumat keyfiyyəti ayrılıb; metric, təhlükəsiz log,
  correlation ID, xəta kateqoriyaları, heartbeat, alert və fail-closed qaydaları
  müəyyən edilib.
- Məlumat keyfiyyəti tapıntısı avtomatik platforma nasazlığı sayılmır;
  xəbərdarlığın təsdiqi sayğacı silmir və problemi həll olunmuş göstərmir.
- Phase 2 saxlama və ehtiyat nüsxə müqaviləsi hazırlanıb: xam tick və auditin
  müddətsiz qorunması, backup manifesti, bərpa sınağı, disk hədləri və təhlükəsiz
  təmizləmə qaydaları müəyyən edilib.
- Phase 2 konfiqurasiya və təhlükəsiz startup müqaviləsi hazırlanıb: mühit
  profilləri, secret sərhədi, startup preflight, funksiya açarları, rotasiya,
  rollback və uzaq giriş tələbləri müəyyən edilib.
- Phase 2 API müqaviləsi hazırlanıb: `/api/v2` versiyalanması, asinxron işlər,
  imzalanmış snapshot cursor-u, ölçü və rate limitləri, idempotency, optimistic
  locking və sabit xəta envelope-u müəyyən edilib.
- Phase 2 worker və scheduler müqaviləsi hazırlanıb: Phase 1-dən ayrı davamlı job
  növbəsi, claim/lease/fencing, prioritet və ədalət, retry, checkpoint, restart
  bərpası, backpressure və təhlükəsiz shutdown qaydaları müəyyən edilib.
- Phase 2 audit və qəbul sübutu ixrac müqaviləsi hazırlanıb: sanitizasiya edilmiş
  ZIP/JSONL paket, manifest, checksum, rəqəmsal imza, offline verifier,
  chain-of-custody və acceptance `pass/fail/inconclusive` qaydaları müəyyən edilib.
- Phase 3 tədqiqat və statistik validasiya müqaviləsi hazırlanıb: əvvəlcədən
  qeydiyyat, zaman əsaslı train/validation/holdout bölgüsü, leakage və overfitting
  qoruması, walk-forward, baseline, multiple-testing, real icra xərcləri və
  SHADOW hazırlığına keçid qapıları müəyyən edilib.
- Phase 3 statistik analiz nəticə müqaviləsi hazırlanıb: mid-price və log-return,
  volatilite, spread, tick sürəti, MT5 tick-volume, sessiya təqvimi, neytral bazar
  rejimi, uncertainty, məlumat keyfiyyəti qapısı, API və frontend təqdimatı
  müəyyən edilib.
- Phase 4 pattern və texniki analiz müqaviləsi hazırlanıb: deterministik bar,
  yalnız bağlanmış barlardan causal indikator, dəyişməz pattern namizədi, label və
  horizon ayrılığı, realist backtest, xərc/risk göstəriciləri və SHADOW hazırlığı
  qapıları müəyyən edilib.
- Bu işlər dizayndır. Phase 2 istehsal kodu Phase 1-in rəsmi qəbulundan əvvəl
  başladılmayıb.

## 2026-07-30 canlı bərpa sınağı

- Backend-in verilənlər bazasına yaza bilmədiyi real nasazlıq aşkarlandı.
- MT5 Bridge disk növbəsi `1000 / 1000` həddinə çatdı.
- Backend düzgün istifadəçi icazəsi ilə başladıldıqdan sonra yazma bərpa olundu.
- Gözləyən bütün event-lər FIFO qaydasında göndərildi və növbə `0 / 1000` oldu.
- Canlı tick axını yenidən `active` vəziyyətinə qayıtdı.
- Hadisə zamanı rədd edilmiş `7343` event audit göstəricisi kimi qorunur.
- Frontend-də boş növbənin keçmiş `queue_full` xətasına görə dolu göstərilməsi
  düzəldildi; məlumat itkisi xəbərdarlığı ayrıca saxlanılır.
- Backend başlanğıcında verilənlər bazasına geri qaytarılan yazma sınağı əlavə
  edildi; sınaq bazada heç bir cədvəl və ya məlumat saxlamır.
- `/health` verilənlər bazası yazıla bilmədikdə `503` qaytarır.
- Tick saxlanması zamanı SQLite xətası baş verdikdə `/events/ticks` `503` qaytarır
  və MT5 Bridge eventləri növbəyə əlavə edə bilir.
- Avtomatik backend testləri: `12 passed`.
- Tarixi `7343` rədd edilmiş event silinmədən saxlanılır və qorunan API vasitəsilə
  auditli şəkildə təsdiqlənə bilər.
- Təsdiq edən istifadəçi, təsdiq vaxtı və həmin anda olan rədd edilmiş event sayı ayrıca
  saxlanılır.
- Rədd edilmiş event sayı təsdiqlənmiş saydan yuxarı qalxarsa məlumat itkisi xəbərdarlığı
  avtomatik yenidən aktivləşir.
- Canlı backend yoxlamasında tick axını `active`, disk növbəsi `0 / 1000`,
  `loss_acknowledged=false` və `rejected_events=7343` göstərildi.
- Canlı qəbul sınağında `7343` tarixi rədd edilmiş event `RUFAT-091084` istifadəçisi
  tərəfindən təsdiqləndi.
- Təsdiqdən sonra API `status=ok`, `tick_stream.status=active`, `queue_count=0`,
  `loss_acknowledged=true` və `acknowledged_rejected_events=7343` qaytardı.
- Audit sətri SQLite bazasında istifadəçi, say və UTC vaxtı ilə saxlanıldı; tarixi
  rədd edilmiş event sayğacı silinmədi.
- 30 dəqiqəlik canlı sabitlik sınağında tick sayı `126685`-dən `158529`-a yüksəldi:
  `31844` yeni tick itkisiz saxlanıldı.
- Sınağın sonunda backend `/health=ok`, operational status `ok`, tick axını `active`,
  disk növbəsi `0 / 1000` və SQLite `quick_check=ok` oldu.
- Tarixi `7343` rədd edilmiş event üçün audit təsdiqi qorundu və yeni rədd edilmiş
  event qeydə alınmadı.
- 1 saatlıq canlı sabitlik sınağında tick sayı `169948`-dən `206454`-ə yüksəldi:
  `36506` yeni tick qəbul edildi.
- Sınağın sonunda yeni rədd edilmiş event `0`, disk növbəsi `0 / 1000`, backend
  health `ok`, operational status `ok` və SQLite `quick_check=ok` oldu.
- 12.62 saatlıq fasiləsiz canlı sınaqda tick sayı `209018`-dən `419186`-ya
  yüksəldi: `210168` yeni tick qəbul edildi.
- 12.62 saatlıq sınağın sonunda yeni rədd edilmiş event `0`, disk növbəsi
  `0 / 1000`, backend health `ok`, operational status `ok` və SQLite
  `quick_check=ok` oldu.
- Sınaqdan sonra backend `12 passed`, frontend lint, build və render testləri keçdi.
- PR #1 üçün GitHub Actions daxilində iki Backend və iki Frontend check-i uğurla
  tamamlandı.
- PR #1 `main` budağına merge commit ilə birləşdirildi.
- Merge commit üçün GitHub Actions Backend və Frontend testləri uğurla keçdi.
- Canlı restart sınağından sonra tick axını `active`, disk növbəsi `0 / 1000` oldu.
- `tools/start-local-platform.ps1` backend və frontend-i bir əmrlə başladır, mövcud
  sağlam prosesləri tanıyır və təkrar proses yaratmır.
- `tools/stop-local-platform.ps1` yalnız başlatma skriptinin qeydə aldığı, PID və
  başlanma vaxtı uyğun gələn prosesləri dayandırır.
- Başlatma skripti backend `/health` və frontend HTTP cavabını gözləyir; uğursuz
  başlanğıcda yaratdığı proses ağacını təhlükəsiz dayandırır.
- Başlatma və dayandırma skriptlərinin PowerShell sintaksisi, canlı backend
  sağlamlığı və frontend `200` cavabı yoxlanıldı.
- Phase 1 uzunmüddətli sınaqları üçün başlanğıc və son göstəriciləri lokal JSON
  sübutunda saxlayan qəbul aləti əlavə edildi.
- Qəbul aləti health, operational status, tick artımı, disk növbəsi, rejection,
  məlumat itkisi təsdiqi, SQLite `quick_check` və audit sayını avtomatik yoxlayır.
- Alətin real backend yoxlamasında tick artımı və dəyişməyən rejection düzgün
  hesablandı; məxfi məlumat sübut faylına yazılmadı və minimum 24 saat qapısı
  erkən müqayisəni düzgün rədd etdi.
- Starlette-in rəsmi tövsiyəsinə uyğun `httpx2 2.9.1` test transportu əlavə
  edildi; backend testləri `12 passed` nəticəsi ilə xəbərdarlıqsız keçdi.
- GitHub Actions `checkout@v6`, `setup-python@v6` və `setup-node@v6` versiyalarına
  yeniləndi; action runtime Node.js 24-ə keçirildi.

## Layihənin məqsədi

ESAS Platform bazar məlumatlarını toplayan, qoruyan, analiz edən və statistik olaraq sübut edilmiş nəticələr əsasında gələcəkdə qərar verə bilən modul platformadır.

Platforma əvvəlcədən seçilmiş strategiyanı sübut etməyə çalışmır. Strategiyalar müşahidə, toplanmış məlumat və statistik yoxlama nəticəsində yaranmalıdır.

## Cari Phase 1 məqsədi

Etibarlı və yoxlanıla bilən tick məlumatı axını yaratmaq:

```text
MT5 Tick
→ ESAS MT5 Bridge
→ TICK_RECEIVED Event
→ HTTP
→ FastAPI Validation
→ SQLite Storage
→ Tick Statistics
→ Operational Monitoring
```

## Tamamlanmış işlər

- Platformanın konstitusiya sənədləri yaradılıb.
- Ümumi arxitektura hazırlanıb.
- Standart event müqaviləsi müəyyən edilib.
- MT5 Bridge canlı tick qəbul edir.
- Tick məlumatı `TICK_RECEIVED` event-inə çevrilir.
- Event JSON formatında serializasiya edilir.
- Event HTTP vasitəsilə backend-ə göndərilir.
- FastAPI event strukturunu yoxlayır.
- Tick-lər SQLite bazasında saxlanılır.
- Eyni `event_id` ikinci dəfə bazaya yazılmır.
- Tick statistikası endpoint-i yaradılıb.
- Operational status endpoint-i yaradılıb.
- `waiting`, `active` və `stale` axın vəziyyətləri nəzərdə tutulub.
- Real MT5 axını ilə `active` və `stale` vəziyyətləri yoxlanılıb.
- Sınaq zamanı 172 tick-in saxlanması müşahidə edilib.
- Uğursuz HTTP göndərişləri üçün ilkin yaddaş FIFO buferi yaradılıb.
- Backend bərpa olduqda buferdəki event-lərin FIFO batch şəklində avtomatik göndərilməsi real MT5 axını ilə yoxlanılıb.
- Layihə GitHub-a yüklənib.

## Mövcud API endpoint-ləri

- `GET /health`
- `POST /events/ticks`
- `POST /status/bridge`
- `GET /statistics/ticks`
- `GET /status/operational`

## Cari modul vəziyyəti

### Backend

- Texnologiya: FastAPI
- Verilənlər bazası: SQLite
- Versiya: `0.3.0`
- Tick doğrulaması və saxlanması işləyir.
- Operational monitoring işləyir.

### MT5 Bridge

- Status: `EXPERIMENTAL`
- Sənədləşdirilmiş versiya: `1.6.1`
- Canlı tick oxunması işləyir.
- Event yaradılması işləyir.
- HTTP göndərişi işləyir.
- Uğursuz event-in disk əsaslı davamlı FIFO növbəsinə əlavə edilməsi işləyir.
- Növbədəki event-lər EA və MT5 restartından sonra bərpa olunur.
- Event-lər backend bərpa olduqda konfiqurasiya olunan batch ölçüsü ilə
  avtomatik göndərilir.
- Qəbul edilməyən event sayı restartlar arasında davamlı saxlanılır.
- Queue vəziyyəti və xəta səbəbi backend operational API-yə göndərilir.

### Frontend

- `frontend` qovluğunda Phase 1 monitorinq paneli yaradılıb.
- Panel yalnız backend API vasitəsilə məlumat alır.
- Tick, MT5 Bridge, disk növbəsi və rədd edilən event vəziyyətlərini göstərir.
- Məlumat 5 saniyədə bir yenilənir və müvəqqəti API xətasında son uğurlu
  göstəricilər qorunur.
- Brauzer səhifəsi arxa planda olduqda avtomatik sorğular dayandırılır; səhifə
  yenidən görünəndə və bağlantı bərpa olunanda məlumat dərhal təzələnir.
- Başlıq hissəsində sorğunun vəziyyətini göstərən əl ilə yeniləmə idarəsi var.
- Bir neçə Bridge olduqda növbə və rejection göstəriciləri ümumiləşdirilir;
  simvol/Bridge filtri ayrıca mənbənin vəziyyətini göstərir.
- Lokal lint, production build və server-render testi keçir.

## Məlum problemlər

1. Bridge operational vəziyyəti backend restartından sonra ilk status hesabatına
   qədər `waiting` olur.
2. Çox yüksək tick sürəti üçün retry batch ölçüsünün yekun uzunmüddətli yoxlaması
   24 saatlıq canlı qəbul sınağında aparılacaq.
3. Frontend yalnız lokal backend ilə işləyir; production hostinq üçün backend-in
   şəbəkədən əlçatan HTTPS ünvanı tələb olunur.

## Son tamamlanan texniki dəyişiklik

- Phase 2 SQLite sxemi və təhlükəsiz migration müqaviləsi hazırlandı. Replay
  sessiyası, checkpoint, append-only audit, idempotency, keyfiyyət hesabatı və
  tapıntı cədvəlləri müəyyən edildi.
- Real migration-dan əvvəl online backup, `quick_check`, sətir sayları və xam
  event fingerprint-i; migration-dan sonra isə eyni sübutların müqayisəsi və
  ayrıca bərpa sınağı tələb olunur.
- Real bazada heç bir migration icra edilməyib və xam `tick_events` cədvəlinə
  toxunulmayıb.
- Phase 2 frontend replay və məlumat keyfiyyəti ekranlarının funksional
  müqaviləsi hazırlandı. Qorunan naviqasiya, sessiya yaratma, addım və maksimum
  sürət idarəsi, progress, keyfiyyət tapıntıları və təhlükəsiz xəta davranışı
  müəyyən edildi.
- Frontend-in analiz qaydalarını özü hesablamaması, bazar fasiləsini məlumat
  itkisi kimi təqdim etməməsi, order və al/sat idarəsi göstərməməsi qorundu.
- Phase 2 replay sessiyasının həyat dövrü hazırlandı. `step` və `max_speed`
  rejimləri, dəyişməz giriş parametrləri, dataset fingerprint, checkpoint,
  backend restartından sonra `interrupted` vəziyyəti və idempotent idarəetmə
  əmrləri müəyyən edildi.
- Replay sessiyası yalnız törəmə vəziyyət və audit yaza bilər; xam tick məlumatını
  dəyişdirmək, siqnal yaratmaq və order açmaq müqavilə ilə qadağandır.
- Phase 2 məlumat keyfiyyəti müqaviləsi hazırlandı. Boşluq, timestamp,
  mənfi spread, natamam qiymət, qəbul gecikməsi və müqavilə uyğunsuzluğu
  qaydaları versiyalanmış formada müəyyən edildi.
- Bazar sessiyası təqvimi olmadan uzun fasilənin avtomatik məlumat itkisi
  sayılmaması və sıfır qiymətlərin səhv müsbət nəticə yaratmaması sənəddə
  qorundu.
- Phase 2 üçün yalnız-oxuma tick replay müqaviləsi hazırlandı. Müqavilə sabit
  `[start_at, end_at)` aralığını, `event_timestamp + event_id` deterministik
  sırasını, cursor səhifələməni, qorunan API sərhədini və məlumatın
  dəyişməzliyini təsdiqləyən qəbul testlərini müəyyən edir.
- Bu hazırlıq yalnız dizayn və qəbul meyarlarıdır; Phase 1 bağlanmadan Phase 2
  istehsal kodu başladılmayıb.

- MT5 tick və status qəbulu minimum 32 simvolluq ayrıca Bridge açarı ilə
  qorundu; açarsız və səhv açarlı sorğular `401` cavabı alır.
- Backend versiyası `0.3.0`, MT5 Bridge versiyası `1.6.0` edildi.
- Backend `16 / 16` test, MQL5 kompilyasiyası `0 errors, 0 warnings` nəticəsi
  verdi.
- Backend `0.3.0` və MT5 Bridge `1.6.0` eyni məxfi açarla canlı qoşuldu.
  Qısa qəbul müqayisəsində 3 saniyədə `15` yeni tick qəbul edildi, axın
  `active`, növbə `0 / 1000` və ümumi status `ok` oldu.
- Backend və frontend cavablarına keşdən qorunma, clickjacking, MIME sniffing,
  referrer və lazımsız brauzer icazələrinə qarşı təhlükəsizlik başlıqları
  əlavə edildi.
- Təhlükəsizlik başlıqları backend API və frontend server-render testlərində
  avtomatik təsdiqlənir; backend `15 / 15`, frontend lint, production build və
  server-render testləri uğurla keçdi.
- Monitorinq panelinin `Çıxış` əməliyyatı server tərəfli sessiya ləğvi ilə
  tamamlandı; çıxışdan sonra köhnə bearer nişanı yenidən istifadə edilə bilmir.
- Hər giriş üçün unikal sessiya identifikatoru yaradılır və backend restartı
  bütün əvvəlki monitorinq sessiyalarını etibarsız edir.
- Sessiya ləğvi testi daxil olmaqla backend `15 / 15`, frontend lint,
  production build və server-render testləri uğurla keçdi.
- Monitorinq girişinə eyni şəbəkə ünvanı üzrə uğursuz cəhd məhdudiyyəti əlavə
  edildi: 5 ardıcıl səhvdən sonra 15 dəqiqəlik müvəqqəti bloklama tətbiq olunur.
- Uğurlu giriş əvvəlki səhv cəhd sayğacını sıfırlayır və bloklanmış giriş
  sorğuları `429 Too Many Requests` cavabı alır.
- Backend giriş təhlükəsizliyi testləri daxil olmaqla `14 / 14`, frontend lint,
  production build və server-render testləri uğurla keçdi.

Frontend çoxsaylı Bridge və simvol üçün optimallaşdırılıb. Əsas kartlar bütün
Bridge-lərin növbə və rejection göstəricilərini düzgün ümumiləşdirir, seçim
filtri isə ayrıca Bridge-in versiyasını, növbəsini və audit vəziyyətini göstərir.
Məlumat itkisi təsdiqi yalnız konkret Bridge seçildikdə aparılır.

## Phase 1-in tamamlanması

Bütün qəbul qapıları keçib və Phase 1 `2026-08-04` tarixində rəsmi bağlanıb.

## Növbəti əsas texniki prioritet

Bağlanmış replay şamları üzərində versiyalanmış və deterministik ilk indikator
paketini (`EMA`, `RSI`, `ATR`) qurmaq; warm-up tamamlanmadıqda nəticəni açıq şəkildə
`insufficient_data` saxlamaq və ticarət qərarı/order icrasından ayrı tutmaq.

## Phase 2 replay yaratma API-si

- `POST /api/v2/replay-sessions` dashboard sessiyası ilə qorunur və `symbol`,
  `[start_at, end_at)` intervalı, eləcə də `step|max_speed` rejimini qəbul edir.
- Naməlum sahə, timezone-suz vaxt, boş/tərs interval və naməlum rejim fail-closed
  `422` cavabı alır; uğurlu yaradılma `202 Accepted` qaytarır.
- Snapshot, replay sessiyası və ilkin append-only audit mövcud repository
  transaction-u ilə atomik saxlanılır; audit xətası bütün yazını geri qaytarır.
- Məlumatlı dataset `created`, boş dataset təhlükəsiz `completed` vəziyyətində
  yaradılır və yaradıcı istifadəçi `operator` rolu ilə auditə yazılır.
- API testləri xam tick dəyişməzliyini, uğursuz audit rollback-ini və etibarsız
  sorğuların heç bir yazı yaratmamasını təsdiqləyir.
- Replay API hədəf testləri `11 passed`, tam backend `121 passed` nəticəsi verir;
  bütün testlər yalnız müvəqqəti SQLite bazasında işləyir.

## Böyük baza üçün frontend cavab müddəti düzəlişi

- Canlı bazada tick sayı `1.22` milyonu keçdikdə operational və statistika
  cavablarının əvvəlki `3` saniyə həddini aşdığı ölçüldü.
- Frontend sorğu müddəti `10` saniyəyə qaldırıldı və `event_id` primary key-inin
  artıq təmin etdiyi unikallıq üçün lazımsız `COUNT(DISTINCT event_id)` skanı
  çıxarıldı.
- Backend `116 passed`, frontend lint/build/render və GitHub yoxlamaları keçdi;
  düzəliş PR `#5` ilə `main` budağına birləşdirildi.

## Phase 2 replay oxuma API-si

- `GET /api/v2/replay-sessions` giriş sessiyası ilə qorunur və sessiyaları
  `created_at DESC, session_id DESC` sabit sırası ilə qaytarır.
- Səhifələmə cursor-u HMAC ilə imzalanır, istifadəçiyə və replay resursuna bağlanır,
  bir saat sonra etibarsız olur; dəyişdirilmiş cursor təhlükəsiz `400` alır.
- `GET /api/v2/replay-sessions/{session_id}` checkpoint daxil olmaqla saxlanmış
  sessiya metadatasını qaytarır, mövcud olmayan sessiya təhlükəsiz `404` alır.
- API yalnız oxuyur; xam tick, replay progress və audit məlumatını dəyişmir.
- Yeni API testləri `6 passed`, tam backend `116 passed`; frontend lint, build və
  render regressiyası keçib.

## Phase 1 RC1 release qeydləri

`docs/releases/PHASE_1_RC1.md` faylında backend `0.2.0`, MT5 Bridge `1.5.0`,
frontend `0.1.0`, qəbul sübutları, geriyə uyğunluq, məlum məlumat itkisi və qalıq
risklər sənədləşdirildi.

RC1 bütün qəbul qapılarını keçib. Stable qərarı və yekun sübutlar
`docs/releases/PHASE_1_STABLE.md` faylında sənədləşdirilib.

## Məlumat itkisi üzrə yekun hesabat

`docs/status/DATA_LOSS_REPORT.md` faylında `7343` tarixi rədd edilmiş event üzrə
kök səbəb, təsir dairəsi, audit izi, düzəlişlər, qəbul sübutları və qalıq risklər
sənədləşdirildi.

Hesabat tarixi məlumat itkisini bərpa edilmiş kimi göstərmir. Audit təsdiqi
itkinin görüldüyünü və qəbul edildiyini bildirir; payload-ları saxlanmayan
`7343` event bərpa edilə bilməz.

## UTF-8 kodlaşdırma auditi

2026-07-31 tarixində Git-də izlənən bütün `64` layihə faylı sərt UTF-8 decoder
ilə yoxlanıldı.

- Etibarsız UTF-8 faylı: `0`.
- Mojibake nümunəsi olan mətn faylı: `0`.
- Lazımsız UTF-8 BOM olan fayl: `0`.
- Repo üçün UTF-8 və LF qaydasını sabitləşdirən `.editorconfig` əlavə edildi.

Əvvəl Windows PowerShell-də görünən pozulmuş hərflər fayl məlumatının korlanması
deyil, Windows PowerShell 5-in BOM-suz UTF-8 fayllarını default kodlaşdırma ilə
oxumasının nəticəsi idi. Belə fayllar `Get-Content -Encoding utf8` ilə düzgün
göstərilir.

## Avtomatlaşdırılmış MT5 queue və retry qəbul testi

2026-07-31 tarixində `ESAS_PersistentQueue_Test` real MT5 terminalında işləndi.

- MQL5 kompilyasiyası: `0 errors, 0 warnings`.
- Avtomatik assertion nəticəsi: `44 / 44`, uğursuzluq `0`.
- FIFO sırası və yalnız ilk eventin acknowledgement ilə silinməsi yoxlanıldı.
- Pending event və rejection metriyinin restart simulyasiyasından sonra bərpası
  yoxlanıldı.
- Uğursuz göndəriş simulyasiyasında event növbədə saxlanıldı.
- Retry batch limitindən sonra qalan event restart simulyasiyasında bərpa edildi.
- Queue-full, serialization rejection və korlanmış jurnal aşkarlanması yoxlanıldı.
- Test unikal açarlar istifadə etdi və yaratdığı müvəqqəti faylları təmizlədi.

## Queue health monitorinqinin son canlı sınağı

2026-07-30 tarixində MT5 Bridge `1.5.0` və backend `0.2.0` birlikdə yoxlanıldı.

- Bridge hər 5 saniyədə `POST /status/bridge` hesabatı göndərdi.
- Operational API `bridge_delivery.status=healthy` göstərdi.
- `queue_count=0`, `queue_capacity=1000` göstərildi.
- `rejected_events=0`, `last_queue_error=none` göstərildi.
- Tick axını `active` oldu.
- Backend testləri `7 passed` nəticəsi verdi.
- MT5 layihə və terminal kompilyasiyaları `0 errors, 0 warnings` nəticəsi verdi.

## Backend test bazasının təcridi

2026-07-30 tarixində backend testləri canlı bazadan ayrıldı.

- Hər test ayrıca müvəqqəti SQLite faylı istifadə edir.
- Test bitdikdə database yolu production default dəyərinə qaytarılır.
- İdempotency testinin ilk cavabı deterministik olaraq `stored` olur.
- Operational status test database yolunun canlı bazadan fərqli olduğunu
  təsdiqləyir.
- Canlı `database/ESAS_PLATFORM.sqlite` testlər tərəfindən istifadə edilmir.
- Bütün `7` backend testi keçdi.

## Avtomatik GitHub test axını

2026-07-30 tarixində `.github/workflows/tests.yml` əlavə edildi.

- Workflow `main`, `agent/**` push-larında və pull request-lərdə başlayır.
- Python `3.13` təmiz GitHub runner mühitində qurulur.
- Backend dependency-ləri kilidlənmiş requirements faylından quraşdırılır.
- `module.json` JSON validation-dan keçirilir.
- Backend və test Python mənbələri compile edilir.
- `pytest` cache yazmadan icra olunur.
- Workflow lokal YAML validation və `7 passed` nəticəsi ilə yoxlanıldı.

## Disk növbəsi üzrə son canlı sınaq

2026-07-30 tarixində backend bağlı olduğu halda MT5 Bridge `1.4.0` yenidən
başladıldı.

- Başlanğıcda diskdən `queue_count=1000` bərpa edildi.
- FIFO növbə faylı EA restartı zamanı qorundu.
- Backend başladıldıqdan sonra event-lər hər dövrdə maksimum 50-lik batch-lərlə
  göndərildi.
- Növbə təxminən 16 saniyədə `1000`-dən `0`-a endi.
- Son batch `delivered=24 | queue_count=0` nəticəsi verdi.
- Operational endpoint tick axınını `active` göstərdi.
- Backend bazasında ümumi tick sayı `33570` oldu.
- Həm layihə, həm MT5 terminal nüsxəsi `0 errors, 0 warnings` ilə kompilyasiya
  edildi.
- Backend testləri `5 passed` nəticəsi verdi.

Sınaqda növbənin `1000` limitinə çatdığı da müşahidə edildi. Mövcud növbə
qorundu, lakin limitdən sonra gələn event-lər saxlanıla bilmədiyi üçün növbəti
prioritet itki sayğacı və queue health monitorinqidir.
## Qorunan texniki analiz API-si

2026-08-04 tarixində tamamlanmış replay sessiyaları üçün yalnız-oxuma texniki analiz
endpoint-i hazırlandı.

- Yalnız sessiya sahibi və yalnız `completed` sessiya nəticəni görə bilər.
- `M1`, `M5`, `M15`, `H1` qapalı şamları və EMA, RSI, ATR seriyaları təqdim edilir.
- Periodlar və qaytarılan şam sayı təhlükəsiz limitlərlə yoxlanılır.
- Dataset sessiyanın ilkin fingerprint-i ilə yenidən yoxlanılır; drift aşkar edilərsə
  nəticə verilmir.
- Dataset, bar və indikator versiyaları/fingerprint-ləri cavabda saxlanılır.
- Warm-up nöqtələri `insufficient_data` kimi açıq görünür.
- Endpoint strategiya, al/sat siqnalı və order yaratmır.
- Yeni API testləri və tam backend regressiyası `156 passed` nəticəsi verdi; frontend
  lint və production build yoxlamaları keçdi.

## Texniki analiz təqdimat qatı

2026-08-04 tarixində tamamlanmış replay sessiyalarının texniki analiz nəticələri
qorunan frontend panelinə çıxarıldı.

- İstifadəçi `M1`, `M5`, `M15`, `H1` timeframe, EMA/RSI/ATR periodları və görünən
  bar sayını seçə bilir.
- Bağlanış qiyməti və EMA eyni qrafikdə, RSI və ATR isə bir-birindən asılı olmayan
  ayrıca kartlarda göstərilir.
- Kifayət etməyən warm-up barları gizlədilmir və Azərbaycan dilində izah olunur.
- Dataset, bar və indikator fingerprint/versiya izi ayrıca açılan məlumat mənbəyi
  bölməsində saxlanılır.
- Boş nəticə, yüklənmə, API xətası və mobil görünüş üçün ayrıca vəziyyətlər quruldu.
- Panel yalnız tamamlanmış və istifadəçiyə məxsus replay sessiyasından açılır; alış/satış
  siqnalı vermir və order yaratmır.
- Frontend lint, production build və `2` frontend testi keçdi; tam backend regressiyası
  ayrıca runtime test qovluğu ilə `156 passed` nəticəsi verdi.

## Versiyalanmış strategiya modul müqaviləsi

2026-08-04 tarixində texniki indikatorlar üzərində yalnız tədqiqat məqsədli strategiya
modul sərhədi quruldu.

- Ümumi strategiya kontraktı, nəticə modeli və EXPERIMENTAL həyat dövrü yaradıldı.
- İlk istinad modulu `ema_close_relation` `1.0.0` olaraq ayrıca paketləndi.
- Modul yalnız bağlanmış barın close qiymətini eyni barın causal EMA-sı ilə müqayisə edir.
- Nəticə dataset, bar və indikator fingerprint-lərinə bağlanır və öz SHA-256
  fingerprint-ini yaradır.
- Warm-up `insufficient_data` kimi saxlanır; nəticə al/sat siqnalı və order yaratmır.
- Determinizm, warm-up, boş məlumat, zaman uyğunluğu və no-lookahead testləri keçirildi.

## Strategiya nəticəsi API-si və müqayisə görünüşü

2026-08-04 tarixində versiyalanmış strategiyaların tamamlanmış replay üzərində
işlədilməsi üçün qorunan, yalnız-oxuma təqdimat qatı tamamlandı.

- `/api/v2/replay-sessions/{session_id}/strategy-analysis` yalnız sessiya sahibinə və
  yalnız tamamlanmış replay məlumatına xidmət edir.
- Texniki analiz və strategiya eyni yoxlanmış dataset, bağlanmış bar və indikator
  kontekstini paylaşır; dataset drift nəticəni dayandırır.
- İlk modul `ema_close_relation` ayrıca versiya, lifecycle, parametr, sayım və
  fingerprint izi ilə qaytarılır.
- Frontenddə strategiya nəticəsi ayrıca kartda EMA-dan yuxarı/aşağı/bərabər payları,
  warm-up sayını və hesablama izini sadə Azərbaycan dilində göstərir.
- Görünüş mobil ölçüyə uyğunlaşır və gələcək modulların ayrıca kart kimi əlavə
  olunmasına hazırdır.
- Nəticə yalnız araşdırma müşahidəsidir; al/sat qərarı, mövqe ölçüsü və order yaratmır.
- Hədəf testləri `11 passed`, tam backend regressiyası `164 passed`, frontend lint,
  production build və `3` frontend testi uğurla keçdi.

## Çoxpəncərəli walk-forward sabitlik ölçümü

2026-08-04 tarixində EMA və RSI tədqiqat modullarının müxtəlif zaman hissələrində
sabitliyini ayrıca göstərən çoxpəncərəli qiymətləndirmə qatı tamamlandı.

- `expanding_chronological_validation_windows 1.0.0` ən azı iki, ən çox səkkiz
  ardıcıl yoxlama pəncərəsini deterministik yaradır.
- Hər növbəti pəncərənin inkişaf hissəsi yalnız əvvəlki məlumatla genişlənir;
  yoxlama pəncərələri üst-üstə düşmür və təsadüfi qarışdırılmır.
- İnkişaf sərhədini keçən gələcək nəticələr həmin inkişaf hesabından çıxarılır.
- Hər pəncərə inkişaf/yoxlama indeksləri, ayrıca bar fingerprint-ləri və upstream
  strategiya/nəticə fingerprint-ləri ilə izlənir.
- Əhatə, yetişmiş/yetişməmiş/tətbiq olunmayan müşahidələr və xərcsiz tarixi
  dəyişiklik ayrıca saxlanır.
- Frontend iki-beş pəncərə seçimini, hər pəncərənin tarixini, müşahidə sayını,
  yuxarı/aşağı bölgüsünü, çəkili orta dəyişiklik və pəncərələrarası aralığı göstərir.
- Kiçik dataset nəticəni uydurmur və `insufficient_data` kimi açıq göstərilir.
- Hədəf backend sınaqları `24 passed`, tam backend regressiyası `198 passed`,
  frontend lint, production build və `3` frontend testi uğurla keçdi.
- Bu qat yalnız tarixi tədqiqat üçündür; canlı siqnal, risk ölçüsü və order yaratmır.

## Tarixi əməliyyat xərci və stress ssenariləri

2026-08-05 tarixində EMA və RSI walk-forward nəticələri üçün şəffaf xərc fərziyyəsi
qatı tamamlandı.

- `historical_cost_stress_adjustment 1.0.0` normal, pis və stress ssenarilərini eyni
  deterministik qayda ilə bütün yoxlama pəncərələrinə tətbiq edir.
- Xam xərcsiz nəticə dəyişdirilmir; xərcdən sonrakı nəticə, ümumi xərc və əhatə ayrıca
  saxlanılır.
- Spread, komissiya, slippage və gecikmə `basis point` vahidi ilə açıq göstərilir və
  broker faktı deyil, tədqiqat fərziyyəsi kimi işarələnir.
- Konfiqurasiya, upstream multi-window fingerprint-i və nəticə öz SHA-256 izi ilə
  təkrar istehsal edilə bilir.
- Sıfır, mənfi, həddən artıq və natamam xərc, yanlış stress sırası, determinism və
  bütün pəncərələrdə eyni qayda testlərlə qorunur.
- Frontend normal, pis və stress kartlarında xam/xalis tarixi dəyişikliyi və xərc
  tərkibini sadə Azərbaycan dilində göstərir.
- Hədəf backend yoxlamaları `27 passed`, tam backend regressiyası `216 passed`,
  frontend lint, production build və `3` frontend testi uğurla keçdi.
- Qat ticarət mənfəəti hesablamır; siqnal, mövqe ölçüsü, risk icazəsi və order yaratmır.

## Statistik etibarlılıq və sıfır baza müqayisəsi

2026-08-05 tarixində EMA və RSI üzrə xərclərdən sonrakı walk-forward nəticələrinə
versiyalanmış qeyri-müəyyənlik qatı əlavə edildi.

- `purged_validation_mean_vs_zero_baseline 1.0.0` yalnız xronoloji validation
  müşahidələrindən və hər nəticə üfüqünə bir müşahidədən istifadə edir.
- Normal, pis və stress ssenariləri qarışdırılmadan ayrıca qiymətləndirilir.
- Effektiv nümunə sayı, orta xalis dəyişiklik, nümunə standart sapması, standartlaşdırılmış
  effekt ölçüsü və 95% etibar intervalı saxlanılır.
- Sadə baseline sıfır faiz dəyişiklikdir. Nəticə yalnız effektiv nümunə ən azı 30 olduqda,
  variasiya sıfır olmadıqda və intervalın aşağı sərhədi sıfırdan yuxarı olduqda
  `supportive_evidence` sayılır; digər hallar açıq səbəblə `insufficient_evidence` qalır.
- API müqaviləsi `1.2.0` versiyasına qaldırıldı və bütün nəticələr upstream fingerprint-lərlə
  təkrar istehsal edilə bilir.
- Frontend “Sübut yetərlidir / Sübut yetərli deyil” sərhədini, nümunə sayını, ortanı,
  95% intervalı və effekt ölçüsünü sadə Azərbaycan dilində göstərir.
- Tam backend regressiyası `222 passed`; frontend `3` test, lint və production build keçdi.
- Bu nəticə ticarət siqnalı, mənfəət zəmanəti, risk icazəsi və order deyil.
- 2026-08-05: `pattern_hypothesis_registry 1.0.0` tamamlandı. Bazar strukturu,
  likvidlik süpürməsi, BOS/CHoCH/retest və sonrakı zona modelləri üçün LONG/SHORT
  hipotezləri ayrıca, versiyalanmış və maşınla oxunan formada qeydiyyata alındı.
- Qorunan `/api/v2/research/pattern-hypotheses` endpoint-i və sadə Azərbaycan dilində
  frontend kartları əlavə edildi. Şəkillər sübut deyil, yalnız hipotez mənbəyidir.
- Reyestr heç bir siqnal, giriş, risk ölçüsü və order yaratmır. Növbəti mərhələ ayrıca
  təsdiqdən sonra causal HH/HL və LH/LL detektorunun tərifidir.
- Yoxlama: backend `224 passed`; frontend `4` test, lint və production build keçdi.

## 2026-08-05 — Bölmə əsaslı frontend iş sahəsi

- Uzun, alt-alta açılan monitorinq səhifəsi sol menyu və mərkəzi iş paneli ilə əvəz edildi.
- Standart açılan bölmə `Nəticələr`dir; istifadəçi başqa bölməni seçənədək ümumi GOLD xülasəsi görünür.
- Menyuda nəticələr, canlı vəziyyət, replay, texniki göstəricilər, bazar strukturu,
  likvidlik, BOS/CHoCH, retest, strategiya müqayisəsi və hipotez reyestri ayrıca bölmələrdir.
- Hər bölmə cari rəqəmi, GOLD-a mümkün təsirin sadə dildə izahını və açılan
  `Nəyə əsaslanır?` tədris qeydini göstərir.
- Texniki analiz alt panelləri seçilmiş menyuya görə ayrı göstərilir; mövcud hesablamalar və API müqavilələri dəyişdirilməyib.
- Masaüstü üçün sabit sol menyu, dar ekranlar üçün üfüqi və responsiv menyu əlavə edildi.
- Təhlükəsizlik sərhədi saxlanılıb: ekranlar araşdırma/monitorinq üçündür, siqnal və ticarət əməliyyatı yaratmır.
- Yoxlama: frontend production build və bütün `8/8` frontend testi uğurla keçdi.

## 2026-08-05 — Frontend fokus və istifadə təlimatı düzəlişi

- Replay sessiyalarının tam idarəetməsi yalnız `Replay sessiyaları` menyusunda göstərilir.
- Digər analiz bölmələrində yalnız seçilmiş replay-in qısa konteksti, aid analiz və
  `Sessiyanı dəyiş` keçidi göstərilir.
- Hər bölməyə yeni istifadəçi üçün üç addımlı istifadə qaydası əlavə edildi.
- Texniki `Phase 2` başlığı istifadəçi görünüşündən çıxarıldı.
- Platforma araşdırma/monitorinq rejimindədir; bu görünüşlər ticarət siqnalı deyil.
- Yoxlama: frontend production build və bütün `9/9` frontend testi uğurla keçdi.
