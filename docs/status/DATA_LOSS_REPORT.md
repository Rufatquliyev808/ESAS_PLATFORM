# Phase 1 məlumat itkisi üzrə yekun hesabat

Status: CLOSED WITH ACKNOWLEDGED HISTORICAL LOSS

Hesabat tarixi: `2026-07-31`

Əhatə olunan mənbə: `esas.mt5.bridge`

Əhatə olunan simvol: `GOLD`

## İcra xülasəsi

2026-07-30 tarixində backend prosesinin SQLite bazasına yaza bilməməsi nəticəsində
MT5 Bridge eventləri disk növbəsinə toplamağa başladı. Növbə `1000 / 1000`
tutumuna çatdıqdan sonra əlavə `7343` event növbəyə yazıla bilmədi və Bridge-in
davamlı rejection sayğacında qeydə alındı.

Backend-in yazma imkanı bərpa edildikdən sonra növbədə qorunmuş `1000` event FIFO
ardıcıllığı ilə backend-ə göndərildi və növbə `0 / 1000` oldu. Növbə limitindən
sonra rədd edilmiş `7343` eventin payload-ları saxlanmadığı üçün həmin tarixi
məlumat bərpa edilə bilməz.

Hadisə texniki baxımdan nəzarət altına alınıb və istifadəçi tərəfindən auditli
şəkildə təsdiqlənib. “Təsdiqlənib” ifadəsi tarixi məlumatın bərpa edildiyini
bildirmir; yalnız itkinin görüldüyünü və qəbul edildiyini göstərir.

## Təsir dairəsi

| Göstərici | Dəyər |
|---|---:|
| Disk növbəsinin tutumu | `1000` event |
| Bərpa edilərək göndərilən növbə | `1000` event |
| Rədd edilmiş və bərpa olunmayan event | `7343` |
| Təsirlənən mənbə | `esas.mt5.bridge` |
| Təsirlənən simvol | `GOLD` |
| Hazırkı disk növbəsi | `0 / 1000` |
| Sonrakı sabitlik sınaqlarında yeni rejection | `0` |

Məlum itki `7343` rədd edilmiş eventlə məhdudlaşdırılır. Bu say Bridge metrics
faylında davamlı saxlanır və operational API vasitəsilə göstərilir. Tarixi
eventlərin payload-ları mövcud olmadığı üçün onların bazar məzmununu sonradan
yenidən qurmaq mümkün deyil.

## Kök səbəb

Birbaşa səbəb backend prosesinin SQLite bazasına yaza bilməməsi idi. Backend
eventi uğurla saxlaya bilmədikdə HTTP çatdırılması uğursuz oldu və Bridge eventləri
disk növbəsinə əlavə etdi. Növbə sərhədli olduğuna görə `1000` eventdən sonra
gələn eventlər qəbul edilmədi.

Hadisənin böyüməsinə təsir edən amillər:

- backend başlanğıcında bazaya real yazma imkanının əvvəlcədən yoxlanmaması;
- növbə və rejection göstəricilərinin ilkin mərhələdə paneldə görünməməsi;
- sərhədli disk növbəsinin dolduqdan sonra yeni event payload-larını saxlaya
  bilməməsi.

## Bərpa və düzəlişlər

Hadisədən sonra aşağıdakılar tətbiq edildi:

- backend düzgün fayl icazələri ilə başladıldı və SQLite yazması bərpa edildi;
- növbədəki `1000` event FIFO batch-lərlə göndərildi;
- backend startup və `/health` zamanı geri qaytarılan real SQLite yazma sınağı
  əlavə edildi;
- runtime SQLite yazma xətası üçün aydın `503` cavabı əlavə edildi;
- Bridge queue count, capacity, rejection count və son queue xətasını backend-ə
  göndərir;
- monitorinq panelində növbə və məlumat itkisi ayrıca göstərilir;
- rejection sayğacı restartlar arasında davamlı saxlanılır;
- rejection sayı əvvəl təsdiqlənmiş həddi keçdikdə xəbərdarlıq yenidən aktivləşir;
- queue və retry semantikası üçün avtomatlaşdırılmış MQL5 qəbul testi əlavə
  edildi.

## Audit izi

SQLite `loss_acknowledgements` cədvəlində saxlanılan dəyişdirilməmiş audit sətri:

| Sahə | Dəyər |
|---|---|
| `acknowledgement_id` | `1` |
| `source` | `esas.mt5.bridge` |
| `symbol` | `GOLD` |
| `rejected_events` | `7343` |
| `acknowledged_by` | `RUFAT-091084` |
| `acknowledged_at` | `2026-07-30T11:05:20.134Z` |

Audit zamanı SQLite `quick_check` nəticəsi `ok` olub. Rejection sayğacı
silinməyib və `7343` olaraq qorunur.

## Sonrakı qəbul sübutları

- 30 dəqiqəlik sınaq: `31844` yeni tick, yeni rejection `0`, növbə `0 / 1000`.
- 1 saatlıq sınaq: `36506` yeni tick, yeni rejection `0`, növbə `0 / 1000`.
- 12.62 saatlıq sınaq: `210168` yeni tick, yeni rejection `0`, növbə `0 / 1000`.
- Backend regressiya testləri: `12 passed`.
- MQL5 queue/retry qəbul testi: `44 / 44`, uğursuzluq `0`,
  kompilyasiya `0 errors, 0 warnings`.

## Qalıq risklər

- `7343` tarixi event bərpa edilməyib və bərpa edilə bilməz.
- Növbə gələcəkdə yenidən tutuma çatarsa yeni event itkisi mümkündür; rejection
  sayğacı və monitorinq bunu aşkar edir, lakin limitsiz saxlama təmin etmir.
- Çox yüksək tick sürətində uzunmüddətli retry batch davranışı 24 saatlıq canlı
  qəbul sınağında hələ təsdiqlənməlidir.
- 2026-07-31 tarixində başlanmış 24 saatlıq sınaq cümə bazar bağlanmasına görə
  qəbul sınağı kimi istifadə edilmir və bazar açıldıqdan sonra təkrar aparılacaq.

## Yekun qərar

Hadisə gizlədilmədən və sayğac silinmədən bağlanıb. Tarixi itki auditli şəkildə
təsdiqlənib, səbəbə qarşı texniki nəzarətlər əlavə edilib və sonrakı sınaqlarda
yeni rejection müşahidə edilməyib.

Phase 1 məlumat itkisi hesabatı tamamlanıb. Phase 1-in yekun qəbulu üçün 24
saatlıq canlı sınaq və release qeydləri hələ tamamlanmalıdır.
