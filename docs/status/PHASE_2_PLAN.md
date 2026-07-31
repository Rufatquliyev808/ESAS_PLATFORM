# ESAS Platform — Phase 2 icra planı

Status: PLANNED  
Başlama şərti: Phase 1 qəbul qapılarının tamamlanması

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

API versiyalanması, cursor, limit və xəta cavabı müqaviləsi:
`docs/architecture/PHASE_2_API_CONTRACT.md`

Audit ixracı və qəbul sübutu paketi müqaviləsi:
`docs/architecture/PHASE_2_AUDIT_EVIDENCE_EXPORT_CONTRACT.md`

Müqavilə sənədləri hazırlanıb, lakin Phase 2 istehsal kodu hələ başladılmayıb.

## Məqsəd

Saxlanmış xam tick məlumatını dəyişdirmədən oxumaq, müəyyən zaman aralığını
deterministik replay etmək və məlumat keyfiyyətini ölçmək.

Phase 2 ticarət qərarı, siqnal, proqnoz və order icrası yaratmır.

## İş ardıcıllığı

### 1. Oxuma sərhədi və məlumat müqaviləsi

- Xam tick cədvəli üçün yalnız-oxuma repository interfeysi yaratmaq.
- `symbol`, başlanğıc vaxtı, son vaxt və səhifələmə parametrlərini müəyyən etmək.
- Sıralamanı `timestamp` və sabit ikinci açarla deterministik etmək.
- Xam event-lərin dəyişdirilməsini və silinməsini qadağan edən testlər əlavə etmək.

Tamamlanma meyarı: eyni sorğu hər dəfə eyni ardıcıllıqda eyni tick-ləri qaytarır.

### 2. Replay sessiyası

- Replay sessiyasının identifikatorunu və giriş parametrlərini müəyyən etmək.
- Saxlanmış tick-ləri zaman ardıcıllığı ilə oxumaq.
- Replay sürətini real vaxtdan ayırmaq: addım-addım və maksimum sürət rejimi.
- Eyni giriş üçün təkrar istehsal edilə bilən nəticə yaratmaq.

Tamamlanma meyarı: eyni məlumat aralığı iki icrada eyni event ardıcıllığını verir.

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

Phase 1 bağlandıqdan sonra yalnız-oxuma tick repository müqaviləsini və onun
deterministik sıralama testlərini yaratmaq.
