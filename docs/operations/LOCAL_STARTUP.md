# Lokal başlatma və dayandırma

ESAS Platform-un backend və frontend hissələrini bir əmrlə təhlükəsiz başlatmaq
üçün layihənin kök qovluğunda PowerShell açın:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\start-local-platform.ps1
```

Skript:

- `.env` və Python virtual mühitinin mövcudluğunu yoxlayır;
- `.env` daxilində minimum 32 simvolluq `ESAS_BRIDGE_API_KEY` olduğunu yoxlayır;
- artıq işləyən backend və frontend üçün ikinci proses yaratmır;
- backend-i lokal `127.0.0.1:8000` ünvanında başladır;
- verilənlər bazasının yazıla bildiyini `/health` vasitəsilə təsdiqləyir;
- frontend-i lokal `127.0.0.1:3000` ünvanında başladır;
- prosesləri gizli pəncərədə saxlayır;
- lokal proses qeydlərini və logları Git-ə düşməyən `.runtime` qovluğunda saxlayır.

Backend başlamazdan əvvəl `.env` faylında ayrıca məxfi Bridge açarı olmalıdır:

```dotenv
ESAS_BRIDGE_API_KEY=<minimum-32-simvolluq-məxfi-açar>
```

Eyni dəyər MT5 Bridge parametrlərində `InpBackendBridgeKey` sahəsinə daxil
edilməlidir. Açarı Git-ə, ekran görüntüsünə və loglara əlavə etməyin.

Platformanı bu skriptlə başladılmış proseslər üzrə dayandırmaq üçün:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\stop-local-platform.ps1
```

Dayandırma skripti yalnız özü tərəfindən qeydə alınmış prosesləri dayandırır. PID
başqa prosesə aid olarsa, təhlükəsizlik üçün həmin prosesə toxunmur.

## Giriş təhlükəsizliyi

Monitorinq paneli istifadəçi kodu və parol ilə qorunur. Eyni şəbəkə ünvanından
ardıcıl 5 səhv giriş cəhdi olduqda giriş 15 dəqiqəlik müvəqqəti bloklanır.
Uğurlu giriş əvvəlki səhv cəhd sayğacını sıfırlayır. Backend yenidən başladıldıqda
yaddaşdakı müvəqqəti bloklama vəziyyəti də sıfırlanır.

Hər uğurlu giriş serverdə ayrıca aktiv sessiya kimi qeydə alınır. Paneldə
`Çıxış` seçildikdə sessiya backend-də dərhal ləğv edilir. Backend restartı da
bütün aktiv sessiyaları təhlükəsizlik məqsədilə bağlayır.

Backend və frontend monitorinq cavabları brauzer keşinə yazılmır. Cavablarda
clickjacking, MIME sniffing, referrer sızması və kamera, mikrofon, məkan
icazələrini məhdudlaşdıran təhlükəsizlik başlıqları mövcuddur.

## Phase 1 qəbul göstəricilərinin avtomatik saxlanması

24 saatlıq sınağın əvvəlində cari göstəriciləri məxfi məlumatları göstərmədən
`.runtime/phase1-acceptance` qovluğunda saxlamaq üçün:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\phase1-acceptance-snapshot.ps1 `
  -Action Capture -Label phase1-24h-start
```

Sınağın sonunda başlanğıc JSON faylının yolunu göstərərək müqayisə aparmaq üçün:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\phase1-acceptance-snapshot.ps1 `
  -Action Compare `
  -BaselinePath ".\.runtime\phase1-acceptance\<başlanğıc-faylı>.json" `
  -Label phase1-24h-end
```

Alət backend health və operational statusunu, tick artımını, disk növbəsini,
rejection sayını, məlumat itkisi təsdiqini, SQLite `quick_check` nəticəsini və
audit sayını yoxlayır. Müqayisənin uğurlu sayılması üçün standart olaraq minimum
`24` saat keçməlidir. Sübut faylları lokal `.runtime` daxilində qalır və Git-ə
əlavə edilmir.
