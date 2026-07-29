# ESAS Platform — Cari Vəziyyət

Son yenilənmə: 2026-07-29  
Cari mərhələ: Phase 1  
Status: IN PROGRESS  
Əsas budaq: `main`

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
- `GET /statistics/ticks`
- `GET /status/operational`

## Cari modul vəziyyəti

### Backend

- Texnologiya: FastAPI
- Verilənlər bazası: SQLite
- Versiya: `0.1.0`
- Tick doğrulaması və saxlanması işləyir.
- Operational monitoring işləyir.

### MT5 Bridge

- Status: `EXPERIMENTAL`
- Sənədləşdirilmiş versiya: `0.2.0`
- Canlı tick oxunması işləyir.
- Event yaradılması işləyir.
- HTTP göndərişi işləyir.
- Uğursuz event-in RAM buferinə əlavə edilməsi işləyir.
- Buferdəki event-lər backend bərpa olduqda saniyəlik interval və konfiqurasiya olunan batch ölçüsü ilə avtomatik göndərilir.

### Frontend

- `frontend` qovluğu mövcuddur.
- Hazır frontend tətbiqi yoxdur.
- İlk frontend Phase 1 monitorinq paneli olmalıdır.
- Frontend yalnız backend API vasitəsilə məlumat almalıdır.

## Məlum problemlər

1. Azərbaycan hərfləri bəzi köhnə sənədlərdə pozulmuş görünür.
2. Phase 1 status sənədinin Markdown quruluşunda problem var.
3. RAM buferindəki məlumat MT5 bağlandıqda itir.
4. Bufer dolması və məlumat itkisi siyasəti tam müəyyən edilməyib.
5. Çox yüksək tick sürəti üçün retry batch ölçüsünün uzunmüddətli testi aparılmayıb.
6. MT5 buferi üçün avtomatlaşdırılmış unit test yoxdur.
7. Frontend spesifikasiyası hazırlanmayıb.
8. Test verilənlər bazası əsas verilənlər bazasından ayrılmayıb.
9. Backend testlərində `httpx` ilə bağlı deprecation xəbərdarlığı mövcuddur.

## Son tamamlanan texniki dəyişiklik

MT5 Bridge backend kəsilməsi zamanı event-ləri RAM əsaslı FIFO buferində saxlayır. Backend bərpa olduqda gözləyən event-ləri konfiqurasiya olunan batch ölçüsü ilə avtomatik göndərir.

Real MT5 sınağında:

- backend dayandırıldıqda event-lər buferdə saxlanılıb;
- uğursuz retry zamanı event-lər silinməyib;
- backend bərpa olduqda 3 event göndərilib;
- sınağın sonunda `buffer_count=0` olub;
- MT5 kompilyasiyası `0 errors, 0 warnings` nəticəsi verib;
- backend testləri `5 passed` nəticəsi verib.

## Phase 1-in tamamlanması üçün qalan əsas işlər

1. Layihə yaddaşı və yol xəritəsini tamamlamaq.
2. Sənədlərin kodlaşdırmasını düzəltmək.
3. MT5 buferinin retry mexanizmini yaratmaq.
4. Disk əsaslı davamlı event növbəsini layihələndirmək.
5. Backend monitorinq göstəricilərini genişləndirmək.
6. Avtomatlaşdırılmış testləri artırmaq.
7. İlk frontend monitorinq panelini yaratmaq.
8. Uzunmüddətli sabitlik testi aparmaq.
9. Phase 1 nəticələrini sənədləşdirmək.
10. Phase 1-i rəsmi şəkildə bağlamaq.

## Növbəti əsas texniki prioritet

RAM buferindəki event-lərin MT5 və ya kompüter bağlandıqda itməməsi üçün disk əsaslı davamlı event növbəsinin layihələndirilməsi.
