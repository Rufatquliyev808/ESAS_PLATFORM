# ESAS Platform — Cari Vəziyyət

Son yenilənmə: 2026-07-31
Cari mərhələ: Phase 1  
Status: IN PROGRESS  
Əsas budaq: `main`

## Phase 2 üçün bazardan asılı olmayan dizayn hazırlığı

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
- Sənədləşdirilmiş versiya: `1.6.0`
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

## Phase 1-in tamamlanması üçün qalan əsas işlər

1. Bazar açıq olduqda 24 saatlıq fasiləsiz canlı sabitlik sınağını keçirmək.
2. Sınağın sonunda avtomatik qəbul müqayisəsini və bütün əsas testləri yenidən
   keçirmək.
3. Nəticələri sənədləşdirib Phase 1-i yekun review üçün hazırlamaq.
4. Bütün qəbul qapıları keçərsə Phase 1-i rəsmi bağlamaq.

## Növbəti əsas texniki prioritet

Bazar açıldıqda 24 saatlıq fasiləsiz canlı sabitlik sınağını yenidən başlatmaq.

## Phase 1 RC1 release qeydləri

`docs/releases/PHASE_1_RC1.md` faylında backend `0.2.0`, MT5 Bridge `1.5.0`,
frontend `0.1.0`, qəbul sübutları, geriyə uyğunluq, məlum məlumat itkisi və qalıq
risklər sənədləşdirildi.

Buraxılış `Release Candidate` statusundadır. 24 saatlıq canlı qəbul sınağı
keçmədən `Stable` elan edilməyəcək.

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
