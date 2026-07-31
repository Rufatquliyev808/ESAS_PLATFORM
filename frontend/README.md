# ESAS Platform Frontend

Phase 1 üçün read-only canlı monitorinq panelidir.

## Lokal işə salma

Backend əvvəlcə `127.0.0.1:8000` ünvanında işləməlidir.

```powershell
npm ci
npm run dev
```

Panel standart olaraq `http://localhost:3000` ünvanında açılır.

## Yoxlama

```powershell
npm run lint
npm test
```

`npm test` production build və server-render testini birlikdə icra edir.

## API ünvanı

Standart backend ünvanı `http://127.0.0.1:8000`-dir. Başqa mühit üçün
`NEXT_PUBLIC_ESAS_API_URL` dəyişəni istifadə oluna bilər.

Frontend yalnız backend API-lərini oxuyur. SQLite bazasına və MT5 order
əməliyyatlarına birbaşa çıxışı yoxdur.

Panel görünən brauzer səhifəsində məlumatı 5 saniyədə bir yeniləyir. Səhifə
arxa plana keçdikdə lazımsız backend sorğuları dayandırılır; səhifəyə qayıdanda
və internet bağlantısı bərpa olunanda vəziyyət dərhal yenidən yoxlanılır. Başlıq
hissəsində əl ilə `Yenilə` düyməsi də mövcuddur.

## Giriş qoruması

Lokal `.env` faylında aşağıdakı dəyişənlər təyin edilməlidir:

- `ESAS_USER_CODE`
- `ESAS_USER_PASSWORD`
- `ESAS_SESSION_SECRET`

`.env` Git-ə daxil edilmir. Monitorinq API-ləri etibarlı 8 saatlıq sessiya
nişanı olmadan `401 Unauthorized` qaytarır.
