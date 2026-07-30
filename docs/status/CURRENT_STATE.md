# ESAS Platform — Cari Vəziyyət

Son yenilənmə: 2026-07-29  
Cari mərhələ: Phase 1  
Status: IN PROGRESS  
Əsas budaq: `main`

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
- Canlı restart sınağından sonra tick axını `active`, disk növbəsi `0 / 1000` oldu.
- `tools/start-local-platform.ps1` backend və frontend-i bir əmrlə başladır, mövcud
  sağlam prosesləri tanıyır və təkrar proses yaratmır.
- `tools/stop-local-platform.ps1` yalnız başlatma skriptinin qeydə aldığı, PID və
  başlanma vaxtı uyğun gələn prosesləri dayandırır.
- Başlatma skripti backend `/health` və frontend HTTP cavabını gözləyir; uğursuz
  başlanğıcda yaratdığı proses ağacını təhlükəsiz dayandırır.
- Başlatma və dayandırma skriptlərinin PowerShell sintaksisi, canlı backend
  sağlamlığı və frontend `200` cavabı yoxlanıldı.

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
- Versiya: `0.2.0`
- Tick doğrulaması və saxlanması işləyir.
- Operational monitoring işləyir.

### MT5 Bridge

- Status: `EXPERIMENTAL`
- Sənədləşdirilmiş versiya: `1.5.0`
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
- Lokal lint, production build və server-render testi keçir.

## Məlum problemlər

1. Azərbaycan hərfləri bəzi köhnə sənədlərdə pozulmuş görünür.
2. Phase 1 status sənədinin Markdown quruluşunda problem var.
3. Queue sayğacları üçün ayrıca avtomatlaşdırılmış MQL5 unit test infrastrukturu
   yoxdur.
4. Bridge operational vəziyyəti backend restartından sonra ilk status hesabatına
   qədər `waiting` olur.
5. Çox yüksək tick sürəti üçün retry batch ölçüsünün uzunmüddətli testi aparılmayıb.
6. MT5 buferi üçün avtomatlaşdırılmış unit test yoxdur.
7. Frontend real MT5 axını ilə vizual qəbul sınağından keçirilməlidir.
8. Frontend yalnız lokal backend ilə işləyir; production hostinq üçün backend-in
   şəbəkədən əlçatan HTTPS ünvanı tələb olunur.
9. Backend testlərində `httpx` ilə bağlı deprecation xəbərdarlığı mövcuddur.

## Son tamamlanan texniki dəyişiklik

MT5 Bridge backend kəsilməsi zamanı event-ləri disk əsaslı davamlı FIFO
növbəsində saxlayır. EA və ya MT5 yenidən başladıqda növbəni bərpa edir. Backend
bərpa olduqda gözləyən event-ləri konfiqurasiya olunan batch ölçüsü ilə avtomatik
göndərir.

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

Phase 1 frontend monitorinq panelini real MT5 axını ilə vizual qəbul sınağından
keçirmək.

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
