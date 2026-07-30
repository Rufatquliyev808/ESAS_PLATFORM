# ESAS Platform — Phase 1 qəbul vəziyyəti

Versiya: 1.1
Status: IN PROGRESS
Son yenilənmə: 2026-07-30

## Məqsəd

MT5-dən gələn tick məlumatını yoxlanılan, monitorinq olunan və nasazlıq zamanı
qorunan formada backend-ə çatdırmaq və xam şəkildə saxlamaq.

```text
MT5 Tick
→ ESAS MT5 Bridge
→ TICK_RECEIVED Event
→ HTTP
→ FastAPI Validation
→ SQLite Storage
→ Operational Monitoring
```

## Keçilmiş qəbul yoxlamaları

- Canlı MT5 tick axını backend və SQLite bazası ilə işləyir.
- Eyni `event_id` bazaya ikinci dəfə yazılmır.
- Backend dayandıqda event-lər disk əsaslı FIFO növbəsində saxlanılır.
- Backend bərpa olduqda növbə avtomatik batch-lərlə boşaldılır.
- EA və MT5 restartından sonra disk növbəsi bərpa olunur.
- Növbə `1000` eventdən `0` eventə uğurla boşaldılıb.
- Queue statusu və rədd edilmiş event sayı operational API-də görünür.
- Tarixi `7343` rədd edilmiş event silinmədən auditli şəkildə təsdiqlənib.
- Monitorinq paneli istifadəçi kodu və parol ilə qorunur.
- Panel real tick, Bridge, növbə və məlumat itkisi göstəricilərini göstərir.
- Backend yazma icazəsi startup və `/health` zamanı yoxlanılır.
- 30 dəqiqəlik canlı sınaqda `31844` yeni tick qəbul edilib.
- Sınağın sonunda növbə `0 / 1000`, SQLite `quick_check=ok` olub.
- 1 saatlıq canlı sınaqda `36506` yeni tick qəbul edilib, yeni rədd edilmiş event
  yaranmayıb və disk növbəsi `0 / 1000` qalıb.
- Lokal backend testləri: `12 passed`.
- GitHub Actions backend və frontend testləri `main` budağında keçib.
- PR #1 `main` budağına uğurla birləşdirilib.

## Qəbul qapıları

Phase 1 yalnız aşağıdakı qalan qapılar keçildikdən sonra bağlana bilər:

- [x] 1 saatlıq fasiləsiz canlı sabitlik sınağı
- [ ] 8–12 saatlıq fasiləsiz canlı sabitlik sınağı
- [ ] 24 saatlıq fasiləsiz canlı sabitlik sınağı
- [ ] MT5 disk növbəsi və retry davranışı üçün avtomatlaşdırılmış test
- [ ] Məlumat itkisi üzrə yekun hesabat
- [ ] Phase 1 release qeydləri
- [ ] Əsas status və konstitusiya sənədlərindəki köhnə kodlaşdırma problemlərinin aradan qaldırılması

## Cari risklər

- Canlı sınaqda bir dəfə backend bazaya yaza bilmədiyi üçün növbə dolub və `7343`
  event rədd edilib. Hadisə auditdə qorunur və təsdiqlənib.
- MQL5 növbə mexanizmi real sınaqlardan keçib, lakin ayrıca avtomatlaşdırılmış
  unit-test infrastrukturu hələ yoxdur.
- GitHub Actions istifadə etdiyi bəzi action versiyaları üçün Node.js 20
  deprecation xəbərdarlığı verir. Hazırkı testlər keçir.
- Frontend hazırda lokal istifadə üçündür; uzaqdan təhlükəsiz giriş üçün ayrıca
  HTTPS yerləşdirmə arxitekturası tələb olunur.

## Qərar

Phase 1 funksional olaraq işləyir, lakin uzunmüddətli qəbul və sənəd qapıları
tamamlanmadığı üçün rəsmi olaraq bağlanmır. Phase 2 kodlaşdırılması bu qapılar
keçilmədən başlanmamalıdır.
