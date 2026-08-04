# ESAS Platform Phase 1 Stable buraxılış qeydləri

Version: `Phase 1 Stable`

Tarix: `2026-08-04`

Status: STABLE

## Qərar

Phase 1-in bütün qəbul qapıları keçib. MT5-dən backend və SQLite-a xam tick
məlumat axını, disk əsaslı növbə, avtomatik retry, monitorinq, autentifikasiya və
audit davranışı qəbul edilib.

## Rəsmi 24 saatlıq sübut

- Başlanğıc: `2026-08-03 08:33:13 +04:00`;
- müqayisə: `2026-08-04 11:44:06 +04:00`;
- müddət: `27.18 saat`;
- yeni tick: `340866`;
- yeni rədd edilmiş event: `0`;
- son disk növbəsi: `0 / 1000`;
- tick axını: `active`;
- SQLite `quick_check`: `ok`;
- məlumat itkisi təsdiqi və audit izi: qorundu;
- avtomatik nəticə: `PASSED`.

Lokal qəbul sübutları `.runtime/phase1-acceptance` qovluğunda saxlanılır və məxfi
məlumat daşımır.

## Yekun regressiya nəticələri

- Backend: `16 passed`;
- Frontend lint: passed;
- Frontend production build: passed;
- Frontend server-render: `1 passed`;
- MT5 Bridge: `0 errors, 0 warnings`;
- MQL5 disk növbəsi test faylı: `0 errors, 0 warnings`.

## Qalıq risklər

- `7343` tarixi rədd edilmiş event bərpa edilə bilmir; hadisə auditli şəkildə
  təsdiqlənib və sayğac qorunur.
- Disk növbəsi sərhədlidir; gələcək çox uzun backend kəsintisi ayrıca izlənməlidir.
- Frontend lokal yerləşdirmə üçündür; uzaq giriş üçün HTTPS və ayrıca production
  yerləşdirmə tələb olunur.
- Bu Stable qərarı məlumat qəbul qatına aiddir və real ticarət icazəsi vermir.

## Növbəti mərhələ

Phase 2 xam tick məlumatını dəyişdirmədən oxuyan repository sərhədi və
deterministik replay infrastrukturu ilə başlayır. Phase 2 siqnal, qərar və order
yaratmır.
