# ESAS Platform — Dəyişiklik Tarixçəsi

Bu fayl ESAS Platform-da edilən əsas dəyişiklikləri izləyir.

Format Semantic Versioning prinsipinə əsaslanır:

`MAJOR.MINOR.PATCH`

## Unreleased

### Added

- Phase 2 streaming tick keyfiyyəti analizatorunun ilk qaydaları əlavə edildi:
  geriyə gedən source timestamp, parametrli ardıcıl zaman boşluğu və `event_id`
  dublikatından ayrılmış ardıcıl payload namizədi; stabil finding ID, limitli nümunə,
  batch-dən asılı olmayan nəticə və xam məlumat dəyişməzliyi, tam backend `97 passed`.
- Phase 2 deterministik replay nəticə manifesti əlavə edildi: tamamlanmış `step` və
  `max_speed` sessiyaları üçün immutable giriş, dataset və müqavilə metadatası,
  streaming kanonik nəticə fingerprint-i və iki müstəqil icra üçün fail-closed
  reproduksiya sübutu; `8` yeni test, tam backend `92 passed`.
- Phase 2 `max_speed` replay orchestrator-u əlavə edildi: maksimum `1000` tick-lik
  transaction batch-ləri, checkpoint əsaslı restart, pause sərhədi, terminal no-op,
  dataset fingerprint təsdiqi və audit rollback; `9` yeni test, tam backend
  `84 passed`.
- Phase 2 replay `step` rejimi əlavə edildi: hər əmrdə `1..1000` deterministik tick,
  boşluqsuz checkpoint irəliləməsi, son batch-də atomik tamamlanma və persistent
  idempotency; addım qeydləri append-only qorunur, `8` yeni test və tam backend
  `75 passed`.
- Replay sessiyası üçün qanuni vəziyyət keçidləri, terminal vəziyyət qoruması,
  optimistic conflict, monoton progress və datasetə bağlı checkpoint əlavə edildi;
  sessiya yenilənməsi ilə append-only audit eyni transaction-da yazılır, hədəf
  testlər `22 passed`, tam backend `67 passed`.
- Replay sessiyasını snapshot metadatası və ilkin append-only audit sətri ilə eyni
  transaction-da yaradan repository əlavə edildi; boş dataset birbaşa `completed`
  olur, audit xətası tam rollback verir; `11` yeni test, tam backend `56 passed`.
- `0002` migration-u ilə replay sessiyası sxemi, siyahı/state/owner indeksləri və
  foreign key/trigger ilə qorunan append-only sessiya auditi əlavə edildi; sxem və
  migration hədəf testləri `16 passed`, tam backend `45 passed` nəticəsi verdi.
- Phase 2 replay dataset snapshot-u əlavə edildi: sabit read transaction-ında batch
  oxuması, tick sayı, ilk/son kanonik mövqe və versiyalanmış SHA-256 fingerprint;
  snapshot testləri `7 passed`, tam backend `35 passed` nəticəsi verdi.
- Phase 2 üçün versiyalanmış, SHA-256 checksum nəzarətli və transaction əsaslı
  migration runner-i əlavə edildi; təkrar icra no-op, dəyişmiş migration və dağıdıcı
  SQL fail-closed olur, production yolu açıq icazə tələb edir.
- Replay sorğusu üçün `idx_tick_events_replay(symbol, event_timestamp, event_id)`
  indeksi əlavə edildi və müvəqqəti SQLite bazasında query planı ilə yoxlanıldı;
  migration testləri `6 passed`, tam backend `28 passed` nəticəsi verdi.
- Phase 2 üçün yalnız-oxuma SQLite tick repository-si, `[start_at, end_at)` zaman
  sərhədi, deterministik `(event_timestamp, event_id)` keyset səhifələməsi və xam
  tick dəyişməzliyini qoruyan 6 test əlavə edildi; tam backend nəticəsi `22 passed`.
- Phase 1-in rəsmi 27.18 saatlıq canlı qəbul sınağı `PASSED` nəticəsi ilə
  tamamlandı: `340866` yeni tick, `0` yeni rejection, növbə `0 / 1000`, SQLite
  `quick_check=ok` və bütün avtomatik qəbul qapıları keçdi.
- Phase 1 Stable qəbul qeydləri və Phase 2 yalnız-oxuma repository tapşırığı.

- Phase 11 üçün tam feedback lineage-i, selection-bias və label maturity qoruması,
  performans/drift monitorinqi, təhlükəsiz REVIEW cavabı, immutable model versiyası,
  yenidən SHADOW promotion qapısı, Knowledge Base governance-i və rollback müqaviləsi.
- Phase 10 üçün default-bağlı məhdud icra, execution lease və dəyişməz manifest,
  manual təsdiq, atomik pre-trade risk qapısı, idempotent order həyatı, broker
  reconciliation, kill switch, audit və rollback müqaviləsi.
- Phase 9 üçün real bazar axınında order-siz SHADOW müşahidəsi, causal nəzəri fill,
  xərc və nəzəri portfolio hesabı, champion/challenger müqayisəsi, restart təhlükəsizliyi,
  statistik qəbul və məhdud icra baxışına keçid müqaviləsi.
- Phase 8 üçün deterministik analiz birləşdirməsi, izahlı qərar proposal-u,
  abstain, müstəqil risk qapısı, nəzəri mövqe ölçüsü, portfolio limitləri, halt,
  manual müdaxilə və order-siz SHADOW eligibility müqaviləsi.
- Phase 7 üçün versiyalanmış bilik claim-i, dəyişməz sübut qrafı, scope/rejim
  uyğunluğu, etibarlılıq müddəti, zidd bilik, REVIEW, governance və təhlükəsiz
  retrieval müqaviləsi.
- Phase 6 üçün xəbər mənbə/lisenziya reyestri, point-in-time xəbər və revision,
  iqtisadi buraxılış, fundamental vintage, entity mapping, sentiment sərhədi,
  causal təsir ölçümü və təhlükəsiz event əlaqəsi müqaviləsi.
- Phase 5 üçün deterministik qrafik renderi, Visual AI dataset lineage-i, leakage
  qoruması, zaman əsaslı bölgü, model reproduksiyası, statistik baseline müqayisəsi
  və təhlükəsiz SHADOW hazırlığı müqaviləsi.
- Phase 4 üçün deterministik bar, causal texniki feature, pattern namizədi, label,
  realist backtest, xərc/risk nəticələri və SHADOW hazırlığı müqaviləsi.
- Phase 3 üçün volatilite, spread, tick sürəti, MT5 tick-volume, sessiya müqayisəsi,
  neytral bazar rejimi, uncertainty, keyfiyyət qapısı və nəticə API-si müqaviləsi.
- Phase 3 statistik, texniki analiz və gələcək AI tədqiqatları üçün əvvəlcədən
  qeydiyyat, leakage/overfitting qoruması, toxunulmaz holdout, walk-forward,
  multiple-testing, real icra xərcləri və SHADOW qəbul qapıları müqaviləsi.
- Phase 2 analiz işləri üçün Phase 1 tick növbəsindən ayrılmış davamlı job növbəsi,
  worker claim/lease/fencing, ədalətli scheduler, retry, qəza sonrası bərpa və
  təhlükəsiz shutdown müqaviləsi əlavə edildi.

### Fixed

- Cari vəziyyət və dəyişiklik tarixçəsində artıq tamamlanmış Phase 1 işlərinin
  qalan və planlaşdırılmış işlər kimi göstərilməsi aradan qaldırıldı.
- GitHub Actions checkout, Python və Node qurulum addımları Node 24 əsaslı rəsmi
  major versiyalara yeniləndi.
- Starlette `TestClient` üçün rəsmi `httpx2` keçidi tamamlandı və backend
  testlərindəki köhnəlmə xəbərdarlığı aradan qaldırıldı.
- Boşaldılmış disk növbəsinin keçmiş `queue_full` xətasına görə hələ də dolu
  göstərilməsi düzəldildi.
- Backend əlçatan olmadıqda status nişanının ingiliscə `unavailable` göstərilməsi
  Azərbaycan dilinə uyğunlaşdırıldı.
- Backend başlanğıcında və `/health` yoxlamasında SQLite bazasına real yazma
  imkanı yoxlanılır.
- İşləmə zamanı SQLite yazma xətası baş verdikdə tick endpoint-i nəzarətsiz xəta
  əvəzinə aydın `503` cavabı qaytarır.

### Added

- Phase 2 audit və qəbul sübutu ixrac müqaviləsi: sanitizasiya edilmiş ZIP/JSONL
  paket, manifest, checksum, rəqəmsal imza, offline verifier, chain-of-custody
  və acceptance `pass`, `fail`, `inconclusive` qaydaları.
- Phase 2 API müqaviləsi: `/api/v2` versiyalanması, asinxron replay və keyfiyyət
  işi, imzalanmış snapshot cursor-u, sorğu və rate limitləri, idempotency,
  optimistic locking və standart xəta envelope-u.
- Phase 2 konfiqurasiya və təhlükəsiz startup müqaviləsi: mühit profilləri,
  məxfi açar sərhədi, startup preflight, funksiya açarları, rotasiya, rollback
  və uzaq giriş tələbləri.
- Phase 2 saxlama və ehtiyat nüsxə müqaviləsi: xam məlumat və auditin qorunması,
  backup manifesti, bərpa sınağı, RPO/RTO hədəfləri, disk təzyiqi və iki mərhələli
  təhlükəsiz təmizləmə qaydaları.
- Phase 2 müşahidə və xəbərdarlıq müqaviləsi: platforma sağlamlığı, replay
  vəziyyəti və məlumat keyfiyyətini ayıran status modeli, aşağı kardinal
  metric-lər, təhlükəsiz strukturlaşdırılmış log, correlation ID, versiyalanmış
  xəta kateqoriyaları, worker heartbeat, alert həyat dövrü və fail-closed
  bütövlük qaydaları.
- Phase 2 giriş və icazə müqaviləsi: müşahidəçi, operator, auditor və
  administrator rolları, permission matrisi, replay ownership-i, yüksək riskli
  əməliyyatlarda təzə autentifikasiya, təhlükəsiz bootstrap və append-only audit
  qaydaları. Heç bir rol xam tick, audit, siqnal və order səlahiyyəti almır.
- Phase 2 performans və yaddaş sınağı müqaviləsi: yalnız sintetik müvəqqəti
  bazada işləyən ölçü pillələri, replay, keyfiyyət analizi, paralel SQLite
  yazma/oxuma, migration, qorunan API və frontend üçün ölçülə bilən qəbul
  hədləri, bütövlük qapıları və audit edilən sübut formatı.
- Phase 2 SQLite sxem və migration müqaviləsi: replay sessiyası, checkpoint,
  append-only audit, idempotency, keyfiyyət hesabatı cədvəlləri, replay indeksi,
  online backup, bütövlük sübutu və təhlükəsiz bərpa meyarları.
- Phase 2 frontend funksional müqaviləsi: replay sessiyası yaratma və idarəetmə,
  addım rejimi, progress, məlumat keyfiyyəti hesabatı, təhlükəsiz xəta davranışı,
  responsive və əlçatanlıq qəbul meyarları.
- Phase 2 replay sessiyasının həyat dövrü müqaviləsi: dəyişməz giriş,
  dataset fingerprint, `step` və `max_speed` rejimləri, checkpoint, restart
  davranışı, idempotent idarəetmə əmrləri və append-only audit tələbləri.
- Phase 2 tick məlumat keyfiyyəti müqaviləsi: versiyalanmış boşluq, timestamp,
  spread, qiymət, gecikmə və müqavilə uyğunluğu qaydaları; audit edilən hesabat
  formatı və sintetik qəbul testləri. Bazar sessiyası məlum olmadan fasilə
  avtomatik məlumat itkisi sayılmır.
- Phase 2 üçün yalnız-oxuma tick replay müqaviləsi: sabit vaxt aralığı,
  deterministik `event_timestamp + event_id` sırası, cursor səhifələmə,
  təhlükəsizlik sərhədi və qəbul meyarları. Bu dəyişiklik yalnız dizayndır;
  Phase 2 istehsal kodu başladılmayıb.

- Tick və Bridge status qəbulunu qoruyan minimum 32 simvolluq
  `X-ESAS-Bridge-Key` autentifikasiyası və MT5 `InpBackendBridgeKey` parametri.
- Backend `0.3.0` və MT5 Bridge `1.6.0` məxfi açarla canlı qoşuldu; qısa qəbul
  yoxlamasında tick sayı artdı, axın `active`, növbə `0 / 1000` qaldı.
- Backend və frontend cavabları üçün `no-store`, clickjacking, MIME sniffing,
  referrer və lazımsız brauzer icazələrinə qarşı təhlükəsizlik başlıqları.
- Server tərəfindən izlənən unikal sessiya identifikatoru və çıxış zamanı həmin
  sessiyanı dərhal etibarsızlaşdıran qorunan `POST /auth/logout` endpoint-i.
- Eyni şəbəkə ünvanından ardıcıl 5 uğursuz giriş cəhdindən sonra 15 dəqiqəlik
  müvəqqəti bloklama və uğurlu girişdə səhv sayğacının sıfırlanması.
- Monitorinq panelində əl ilə yeniləmə düyməsi və yenilənmə vəziyyəti.
- Çoxsaylı MT5 Bridge üçün ümumi göstəricilər və ayrıca simvol/Bridge filtri.
- Phase 1 uzunmüddətli sınaqlarında başlanğıc və son göstəriciləri təhlükəsiz
  JSON sübutu kimi saxlayan və qəbul meyarlarını avtomatik müqayisə edən alət.
- Backend `0.2.0`, MT5 Bridge `1.5.0` və frontend `0.1.0` üçün qəbul sübutlarını,
  geriyə uyğunluğu və Stable keçid şərtlərini göstərən Phase 1 RC1 release qeydləri.
- `7343` tarixi rədd edilmiş event üzrə kök səbəb, audit izi, düzəlişlər və qalıq
  riskləri ayıran yekun Phase 1 məlumat itkisi hesabatı.
- Bütün izlənən layihə mətnləri üçün UTF-8 auditi və kodlaşdırmanı sabitləşdirən
  repo səviyyəli `.editorconfig`.
- MT5 disk növbəsi və retry semantikası üçün real MQL5 fayl API-si ilə işləyən
  avtomatlaşdırılmış qəbul testi; nəticə `44 / 44`, uğursuzluq `0`.
- 12.62 saatlıq canlı sabitlik sınağında `210168` yeni tick qəbul edildi; disk
  növbəsi `0 / 1000` qaldı, yeni rədd edilmiş event yaranmadı və bütün yekun
  backend/frontend yoxlamaları keçdi.
- Phase 1 üçün yenidən qurulmuş qəbul vəziyyəti sənədi və aydın qalan qəbul qapıları.
- Phase 2 replay və məlumat keyfiyyəti mərhələsi üçün ardıcıl icra planı.
- 1 saatlıq canlı sabitlik sınağında `36,506` yeni tick qəbul edildi; yeni rədd
  edilmiş event yaranmadı və növbə `0 / 1000` qaldı.
- Tarixi məlumat itkisini silmədən istifadəçi tərəfindən təsdiqləmək üçün audit cədvəli.
- Qorunan `POST /status/loss/acknowledge` endpoint-i.
- Monitorinq panelində itki hadisəsini təsdiqləmə düyməsi, təsdiq vaxtı və istifadəçi izi.
- Rədd edilən event sayı təsdiqlənmiş həddi keçdikdə xəbərdarlığı yenidən aktiv edən versiyalı təsdiq mexanizmi.
- `7343` tarixi rədd edilmiş event üçün canlı istifadəçi təsdiqi və audit izi yoxlanıldı.
- 30 dəqiqəlik canlı sabitlik sınağında `31,844` yeni tick qəbul edildi; disk növbəsi
  `0 / 1000`, verilənlər bazası bütövlüyü `ok` və ümumi status `ok` qaldı.
- PR #1 üçün GitHub Actions push və pull request axınlarında Backend və Frontend
  testləri uğurla keçdi.
- PR #1 Draft vəziyyətindən çıxarılaraq review üçün hazır edildi.
- Backend və frontend üçün bir-əmrlik təhlükəsiz lokal başlatma skripti.
- Yalnız qeydə aldığı prosesləri dayandıran lokal dayandırma skripti.
- Proses PID-si ilə yanaşı başlanma vaxtını yoxlayan təhlükəsiz proses idarəetməsi.
- Lokal başlatma və dayandırma əməliyyat sənədi.
- İstifadəçi kodu və parol ilə qorunan monitorinq girişi.
- Səkkiz saatlıq imzalanmış backend sessiyası və qorunan monitorinq API-ləri.
- Giriş və icazəsiz API sorğuları üçün avtomatik backend testləri.
- Azərbaycan dilində Phase 1 canlı monitorinq paneli.
- Tick axını, MT5 Bridge, disk növbəsi və rədd edilən event kartları.
- Beş saniyəlik avtomatik yenilənmə və API xətasında son uğurlu məlumatın qorunması.
- Frontend üçün responsive desktop, tablet və mobil quruluş.
- Frontend lint, production build və server-render testi.
- Lokal frontend ünvanları üçün məhdud backend CORS icazəsi.
- GitHub Actions daxilində ayrıca frontend test işi.

- MT5 Bridge `1.5.0` üçün davamlı rejected-event sayğacı.
- `queue_full`, serializasiya, disk və corruption xəta kateqoriyaları.
- `POST /status/bridge` operational status qəbulu.
- `GET /status/operational` daxilində `bridge_delivery` göstəriciləri.
- Bridge queue statusu üçün backend validation və API testləri.
- Backend testləri üçün hər testə məxsus müvəqqəti SQLite bazası.
- Test bazasının canlı `ESAS_PLATFORM.sqlite` faylından tam ayrılması.
- Push və pull request-lər üçün GitHub Actions backend test workflow-u.
- CI daxilində module manifest və Python source validation.
- MT5 Bridge `1.4.0` üçün disk əsaslı davamlı FIFO event növbəsi.
- Restart zamanı pending event-lərin bərpası.
- Uzunluq prefiksli ikili jurnal və davamlı acknowledgement checkpoint-i.
- Queue dizaynı üçün `ADR-0001`.
- Canlı backend outage, EA restart və recovery sınağı.
- Layihənin davamlı yaddaş sistemi.
- Codex üçün daimi `AGENTS.md` iş qaydaları.
- Cari vəziyyət üçün `docs/status/CURRENT_STATE.md`.
- Növbəti tapşırıq üçün `docs/status/NEXT_TASK.md`.
- Layihə dəyişikliklərini izləmək üçün `CHANGELOG.md`.
- MT5 Bridge üçün timer əsaslı FIFO retry mexanizmi.
- Konfiqurasiya olunan retry intervalı.
- Konfiqurasiya olunan batch göndəriş ölçüsü.
- Backend bərpa olduqda buferin avtomatik boşaldılması.
- Retry və batch nəticələri üçün operational log mesajları.

### Changed

- Monitorinq panelinin avtomatik yenilənməsi yalnız brauzer səhifəsi görünəndə
  işləyir; səhifəyə qayıdanda və bağlantı bərpa olunanda dərhal davam edir.
- Frontend tarix və say formatlayıcılarını hər renderdə yenidən yaratmır və
  tamamlanmamış sorğuları səhifədən çıxarkən təhlükəsiz dayandırır.
- Əsas monitorinq kartları ilk Bridge-lə məhdudlaşmır; növbə və rejection
  göstəricilərini bütün görünən Bridge-lər üzrə hesablayır.

### Planned

- Phase 2 yalnız-oxuma tick repository-si və deterministik sıralama testləri.

## Backend 0.1.0 — 2026-07-27

### Added

- FastAPI tətbiqinin ilkin versiyası.
- `GET /health` endpoint-i.
- `POST /events/ticks` endpoint-i.
- `GET /statistics/ticks` endpoint-i.
- `GET /status/operational` endpoint-i.
- Pydantic vasitəsilə `TICK_RECEIVED` event yoxlaması.
- SQLite verilənlər bazasının avtomatik yaradılması.
- Tick event-lərinin saxlanması.
- Eyni `event_id` üçün idempotent yazma.
- Tick statistikalarının hesablanması.
- `waiting`, `active` və `stale` operational statusları.
- Backend API testləri.

### Validated

- Canlı MT5 tick-lərinin backend-ə çatması.
- Tick-lərin SQLite bazasında saxlanması.
- `active` axın vəziyyəti.
- 30 saniyədən sonra `stale` axın vəziyyəti.
- Sınaq zamanı 172 saxlanmış tick.

## ESAS MT5 Bridge 0.2.0 — 2026-07-27

### Added

- MT5-dən canlı tick məlumatının oxunması.
- Standart `TICK_RECEIVED` event yaradılması.
- Event ID yaradılması.
- UTC timestamp yaradılması.
- JSON serializasiyası.
- HTTP POST transportu.
- Backend endpoint konfiqurasiyası.
- Strategy Tester daxilində HTTP məhdudiyyəti xəbərdarlığı.
- Uğursuz event-lər üçün ilkin FIFO yaddaş buferi.

### Known limitations

- HTTP göndərişi hər tick üçün sinxron icra olunur.
- Buferdə saxlanmış event-lər avtomatik təkrar göndərilmir.
- RAM buferi MT5 bağlandıqda itir.
- Bufer dolması siyasəti tam müəyyən edilməyib.
- Modul versiyası bütün fayllarda uyğunlaşdırılmayıb.
