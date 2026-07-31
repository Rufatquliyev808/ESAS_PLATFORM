# ESAS Platform Phase 1 RC1 buraxılış qeydləri

Version: `Phase 1 RC1`

Tarix: `2026-07-31`

Status: RELEASE CANDIDATE — 24-HOUR ACCEPTANCE PENDING

Müəllif: ESAS Platform

## Xülasə

Phase 1 RC1 MT5-dən gələn tick məlumatının standart eventə çevrilməsi, backend-ə
çatdırılması, SQLite bazasında xam saxlanması və canlı monitorinqi üçün qəbul
namizədidir.

Bu buraxılış `Stable` deyil. Bazar açıq olduqda aparılacaq 24 saatlıq fasiləsiz
canlı qəbul sınağı keçmədən Phase 1 tamamlanmış və ya stabil elan edilə bilməz.

## Komponent versiyaları

| Komponent | Versiya | Vəziyyət |
|---|---|---|
| Backend API | `0.2.0` | Release Candidate |
| ESAS MT5 Bridge | `1.5.0` | `EXPERIMENTAL` |
| Frontend monitorinq paneli | `0.1.0` | Release Candidate |
| Event Contract | `1.0` | Draft |

## Dəyişən modullar

### Backend

- `TICK_RECEIVED` event validation və idempotent SQLite saxlanması;
- tick statistikası və operational status endpoint-ləri;
- Bridge queue health hesabatlarının qəbulu;
- SQLite yazma qabiliyyətinin startup və `/health` zamanı yoxlanması;
- runtime SQLite yazma xətası üçün `503` cavabı;
- istifadəçi kodu və parol ilə qorunan monitorinq sessiyası;
- məlumat itkisi təsdiqi və dəyişdirilməz audit izi.

### ESAS MT5 Bridge

- canlı tick oxunması və Event Contract `1.0` serializasiyası;
- HTTP transportu;
- disk əsaslı, uzunluq prefiksli FIFO jurnal;
- checkpoint ilə at-least-once acknowledgement;
- EA/MT5 restartından sonra pending event bərpası;
- batch retry;
- davamlı rejection metriyi və queue xəta kateqoriyaları;
- backend-ə periodik queue health hesabatı;
- avtomatlaşdırılmış queue/retry qəbul testi.

### Frontend

- Azərbaycan dilində canlı monitorinq paneli;
- tick axını, Bridge, disk növbəsi və məlumat itkisi göstəriciləri;
- istifadəçi kodu və parol ilə giriş;
- səkkiz saatlıq sessiya və çıxış;
- backend əlçatmaz olduqda son uğurlu məlumatın qorunması;
- auditli məlumat itkisi təsdiqi.

### Əməliyyat və sənədlər

- bir əmrlə lokal backend/frontend başlatma və təhlükəsiz dayandırma skriptləri;
- GitHub Actions backend və frontend test axınları;
- Phase 1 statusu, sabitlik jurnalı və Phase 2 planı;
- məlumat itkisi üzrə yekun hesabat;
- UTF-8 audit və repo səviyyəli `.editorconfig`.

## Geriyə uyğunluq

- Event Contract versiyası `1.0` olaraq qalır.
- Backend tick endpoint-i mövcud `TICK_RECEIVED` strukturunu qoruyur.
- MT5 Bridge dəyişiklikləri event payload-ını dəyişmir.
- Frontend verilənlər bazasına birbaşa qoşulmur və yalnız backend API istifadə edir.

Breaking change: yoxdur.

## Qəbul sübutları

- Backend regressiya testləri: `12 passed`.
- Frontend lint: passed.
- Frontend production build: passed.
- Frontend render testi: `1 passed`.
- MQL5 Bridge kompilyasiyası: `0 errors, 0 warnings`.
- MQL5 queue/retry qəbul testi: `44 / 44`, uğursuzluq `0`.
- 30 dəqiqəlik canlı sınaq: `31844` yeni tick, yeni rejection `0`.
- 1 saatlıq canlı sınaq: `36506` yeni tick, yeni rejection `0`.
- 12.62 saatlıq canlı sınaq: `210168` yeni tick, yeni rejection `0`.
- SQLite `quick_check`: `ok`.

## Məlum tarixi məlumat itkisi

2026-07-30 hadisəsində disk növbəsi dolduqdan sonra `7343` event rədd edilib.
Payload-lar saxlanmadığı üçün həmin eventlər bərpa edilə bilməz. Hadisə auditli
şəkildə təsdiqlənib, sayğac silinməyib və sonrakı qəbul sınaqlarında yeni
rejection qeydə alınmayıb.

Ətraflı hesabat: `docs/status/DATA_LOSS_REPORT.md`.

## Məlum məhdudiyyətlər və qalıq risklər

- 24 saatlıq fasiləsiz canlı qəbul sınağı hələ keçməyib.
- 2026-07-31 sınağı cümə bazar bağlanmasına görə qəbul sübutu sayılmır.
- Bridge sinxron HTTP transportundan istifadə edir.
- Disk növbəsi sərhədlidir; yenidən dolarsa əlavə event itkisi mümkündür.
- Çox yüksək tick sürətində uzunmüddətli retry batch davranışı 24 saatlıq sınaqda
  yenidən izlənməlidir.
- Backend testlərində Starlette/httpx deprecation xəbərdarlığı mövcuddur.
- Production hostinq və HTTPS konfiqurasiyası bu buraxılışa daxil deyil.

## Stable keçid şərti

Phase 1 RC1 yalnız aşağıdakılar tamamlandıqdan sonra Stable namizədi ola bilər:

1. bazar açıq olduqda 24 saatlıq fasiləsiz canlı sınaq;
2. sınağın sonunda disk növbəsinin `0 / 1000` olması;
3. rejection sayının `7343`-dən yuxarı qalxmaması;
4. SQLite `quick_check=ok`;
5. bütün backend, frontend və MQL5 yoxlamalarının yenidən keçməsi;
6. qəbul nəticəsinin status sənədlərinə və bu release qeydlərinə əlavə edilməsi.
