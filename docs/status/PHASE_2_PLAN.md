# ESAS Platform — Phase 2 icra planı

Status: IN PROGRESS
Başlama şərti: TAMAMLANIB — Phase 1 Stable

Detallı oxuma müqaviləsi:
`docs/architecture/PHASE_2_REPLAY_CONTRACT.md`

Məlumat keyfiyyəti müqaviləsi:
`docs/architecture/PHASE_2_DATA_QUALITY_CONTRACT.md`

Replay sessiyası və həyat dövrü müqaviləsi:
`docs/architecture/PHASE_2_REPLAY_SESSION_CONTRACT.md`

Frontend replay və məlumat keyfiyyəti ekran müqaviləsi:
`docs/frontend/PHASE2_REPLAY_QUALITY_DASHBOARD.md`

Verilənlər bazası sxemi və təhlükəsiz migration müqaviləsi:
`docs/architecture/PHASE_2_DATABASE_SCHEMA.md`

Performans, yaddaş və yük sınağı müqaviləsi:
`docs/architecture/PHASE_2_PERFORMANCE_TEST_CONTRACT.md`

Giriş, rol, permission və təhlükəsizlik auditi müqaviləsi:
`docs/architecture/PHASE_2_ACCESS_CONTROL_CONTRACT.md`

Müşahidə, xəta kateqoriyası və xəbərdarlıq müqaviləsi:
`docs/architecture/PHASE_2_OBSERVABILITY_CONTRACT.md`

Saxlama, ehtiyat nüsxə, bərpa və təhlükəsiz təmizləmə müqaviləsi:
`docs/architecture/PHASE_2_RETENTION_BACKUP_CONTRACT.md`

Konfiqurasiya, məxfi açarlar və təhlükəsiz startup müqaviləsi:
`docs/architecture/PHASE_2_CONFIGURATION_STARTUP_CONTRACT.md`

Worker, job növbəsi, prioritet və qəza sonrası bərpa müqaviləsi:
`docs/architecture/PHASE_2_WORKER_SCHEDULER_CONTRACT.md`

API versiyalanması, cursor, limit və xəta cavabı müqaviləsi:
`docs/architecture/PHASE_2_API_CONTRACT.md`

Audit ixracı və qəbul sübutu paketi müqaviləsi:
`docs/architecture/PHASE_2_AUDIT_EVIDENCE_EXPORT_CONTRACT.md`

Müqavilə sənədləri hazırlanıb və Phase 2 istehsal kodunun yalnız-oxuma repository
sərhədi başladılıb.

## Məqsəd

Saxlanmış xam tick məlumatını dəyişdirmədən oxumaq, müəyyən zaman aralığını
deterministik replay etmək və məlumat keyfiyyətini ölçmək.

Phase 2 ticarət qərarı, siqnal, proqnoz və order icrası yaratmır.

## İş ardıcıllığı

### 1. Oxuma sərhədi və məlumat müqaviləsi

- [x] Xam tick cədvəli üçün yalnız-oxuma repository interfeysi yaratmaq.
- [x] `symbol`, başlanğıc vaxtı, son vaxt və səhifələmə parametrlərini müəyyən etmək.
- [x] Sıralamanı `event_timestamp` və `event_id` ilə deterministik etmək.
- [x] Xam event-lərin dəyişdirilmədiyini təsdiqləyən test əlavə etmək.
- [x] Keyset səhifələməsində boşluq və dublikat yaranmadığını yoxlamaq.

Tamamlanma meyarı: KEÇİB — eyni sorğu hər dəfə eyni ardıcıllıqda eyni tick-ləri
qaytarır; yeni repository testləri `6 passed`, tam backend paketi `22 passed`.

### 1.1. Migration və replay indeksi

- [x] Versiyalanmış migration fayllarını ardıcıllıqla oxuyan runner yaratmaq.
- [x] SHA-256 checksum uyğunsuzluğunu fail-closed rədd etmək.
- [x] Migration-u eksklüziv transaction daxilində tətbiq etmək və xətada rollback etmək.
- [x] Təkrar icranı təhlükəsiz no-op etmək.
- [x] Dağıdıcı SQL-i ilkin təhlükəsizlik sərhədində rədd etmək.
- [x] Canlı baza üçün açıq icazə tələb etmək.
- [x] `(symbol, event_timestamp, event_id)` replay indeksini yaratmaq və query planında
  istifadəsini təsdiqləmək.

Tamamlanma meyarı: KEÇİB — migration testləri `6 passed`, tam backend paketi
`28 passed`; bütün dəyişikliklər yalnız müvəqqəti test bazalarında yoxlanılıb.

### 2. Replay sessiyası

- [x] Sabit read transaction daxilində batch-lərlə dataset identifikasiya axını yaratmaq.
- [x] Tick sayı, ilk/son kanonik mövqe və deterministik fingerprint hesablamaq.
- [x] Boş dataset üçün sabit fingerprint və `NULL` sərhədlər qaytarmaq.
- [x] Replay sessiyası cədvəlini interval, rejim, vəziyyət və progress constraint-ləri
  ilə migration vasitəsilə yaratmaq.
- [x] Sessiya auditini foreign key, `ON DELETE RESTRICT` və append-only trigger-lərlə
  qorumaq.
- [x] Replay sessiyasının qeyri-şəffaf identifikatorunu və giriş parametrlərini
  müəyyən etmək.
- [x] Snapshot, sessiya və ilkin audit yaradılmasını atomik repository sərhədinə
  bağlamaq.
- [x] Qanuni vəziyyət keçidlərini və terminal vəziyyətlərin bağlanmasını tətbiq etmək.
- [x] Monoton progress, datasetə bağlı checkpoint və optimistic state conflict
  nəzarətini tətbiq etmək.
- [x] Sessiya keçidi, checkpoint və append-only audit sətrini eyni transaction-da
  atomik yazmaq.
- Saxlanmış tick-ləri zaman ardıcıllığı ilə oxumaq.
- Replay sürətini real vaxtdan ayırmaq: addım-addım və maksimum sürət rejimi.
- Eyni giriş üçün təkrar istehsal edilə bilən nəticə yaratmaq.

Aralıq nəticə: snapshot testləri `7 passed`; sessiya yaradılması və həyat dövrü üzrə
hədəf testlər `22 passed`, tam backend `67 passed`. Eyni məlumat aralığı iki icrada
eyni say, sərhədlər və fingerprint verir; sessiya yaradılması, vəziyyət keçidi,
checkpoint və uyğun audit ya birlikdə yazılır, ya da tam rollback olur.

Tamamlanma meyarı: sessiya həyat dövrü də əlavə edildikdən sonra eyni məlumat aralığı
iki icrada eyni event ardıcıllığını verir.

### 3. Məlumat keyfiyyəti

- Zaman boşluqlarını aşkarlamaq.
- Geriyə gedən və ya uyğunsuz timestamp-ləri aşkarlamaq.
- Dublikat və ardıcıllıq pozuntularını hesablamaq.
- Bid/ask uyğunsuzluğu və mənfi spread hallarını hesablamaq.
- Tick sürəti və spread paylanmasını simvol üzrə hesablamaq.

Tamamlanma meyarı: hər analiz nəticəsi istifadə olunan zaman aralığı və qayda
versiyası ilə audit edilə bilir.

### 4. API

- Replay yaratmaq və vəziyyətini oxumaq üçün backend endpoint-ləri.
- Məlumat keyfiyyəti hesabatını oxumaq üçün qorunan endpoint.
- Böyük məlumat aralığında yaddaş limitini qoruyan səhifələmə və ya streaming.
- `/api/v2`, imzalanmış snapshot cursor-u, idempotency, rate limit və standart
  xəta envelope-u tətbiq etmək.

Tamamlanma meyarı: frontend bazaya birbaşa qoşulmadan bütün nəticələri API-dən alır.

### 5. Monitorinq paneli

- Replay sessiyalarının vəziyyəti.
- Simvol və zaman aralığı üzrə məlumat keyfiyyəti kartları.
- Boşluq, dublikat, ardıcıllıq və spread xəbərdarlıqları.
- Hesabatın qayda versiyası və yaradılma vaxtı.

Tamamlanma meyarı: panel yalnız müşahidə və analiz göstərir, qərar və ticarət etmir.

## Test strategiyası

- Repository sərhədi üçün unit testlər.
- Deterministik replay üçün təkrar icra testi.
- Süni boşluq, dublikat və timestamp pozuntusu fixture-ləri.
- Böyük zaman aralığı üçün performans və yaddaş testi.
- Backend API və autentifikasiya testləri.
- Frontend lint, build və render testi.
- GitHub Actions daxilində bütün Phase 2 testləri.

## İlk texniki tapşırıq

Tamamlanıb: yalnız-oxuma tick repository-si və deterministik sıralama testləri.

Növbəti texniki tapşırıq: `step` rejimi üçün `1..1000` həddində deterministik tick
batch emalını, checkpoint irəliləməsini və idempotency sərhədini hazırlamaq.
