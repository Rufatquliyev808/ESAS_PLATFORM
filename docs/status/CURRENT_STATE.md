# ESAS Platform — Cari Vəziyyət

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

Son yenilənmə: 2026-08-04
Cari mərhələ: Phase 2
Status: PHASE 1 STABLE — PHASE 2 IN PROGRESS
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
