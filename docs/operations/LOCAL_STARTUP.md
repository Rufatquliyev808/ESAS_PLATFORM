# Lokal başlatma və dayandırma

ESAS Platform-un backend və frontend hissələrini bir əmrlə təhlükəsiz başlatmaq
üçün layihənin kök qovluğunda PowerShell açın:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\start-local-platform.ps1
```

Skript:

- `.env` və Python virtual mühitinin mövcudluğunu yoxlayır;
- artıq işləyən backend və frontend üçün ikinci proses yaratmır;
- backend-i lokal `127.0.0.1:8000` ünvanında başladır;
- verilənlər bazasının yazıla bildiyini `/health` vasitəsilə təsdiqləyir;
- frontend-i lokal `127.0.0.1:3000` ünvanında başladır;
- prosesləri gizli pəncərədə saxlayır;
- lokal proses qeydlərini və logları Git-ə düşməyən `.runtime` qovluğunda saxlayır.

Platformanı bu skriptlə başladılmış proseslər üzrə dayandırmaq üçün:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\stop-local-platform.ps1
```

Dayandırma skripti yalnız özü tərəfindən qeydə alınmış prosesləri dayandırır. PID
başqa prosesə aid olarsa, təhlükəsizlik üçün həmin prosesə toxunmur.
