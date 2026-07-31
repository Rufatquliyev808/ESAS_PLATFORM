# ESAS Platform — Phase 2 API müqaviləsi

Versiya: 1.0
Status: **DESIGN READY — NOT IMPLEMENTED**
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

## Məqsəd və sərhəd

Bu müqavilə Phase 2 replay, məlumat keyfiyyəti, audit və əməliyyat
funksiyalarının frontend-ə necə təqdim ediləcəyini müəyyən edir.

API frontend-i database-dən ayırır, böyük məlumatı bir cavabda yaddaşa
yükləmir, permission qərarını backend-də verir və xam tick-i dəyişdirən,
siqnal, order və real ticarət endpoint-i yaratmır.

## Versiyalanma

Phase 2 public backend sərhədi `/api/v2` prefiksindən istifadə edir.

Mövcud sahə silindikdə, mənası dəyişdikdə və ya status, permission, cursor,
idempotency və xəta davranışı geriyə uyğunsuz dəyişdikdə yeni API major
versiyası tələb olunur. Yeni optional response sahəsi major versiya tələb
etmir; müştəri tanımadığı optional sahəni nəzərə almamalıdır.

API, event, replay qaydası və məlumat keyfiyyəti qaydası ayrı versiyalardır.

## Ümumi cavab qaydası

- JSON `application/json; charset=utf-8` formatındadır.
- Vaxt UTC, ISO 8601 və `Z` sonluğu ilə qaytarılır.
- Hər cavabda qeyri-həssas `request_id` olur.
- Qorunan cavablar `Cache-Control: no-store` qaytarır.
- Sessiya və secret URL, body və loga yazılmır.

```json
{
  "data": {},
  "meta": {
    "api_version": "2",
    "request_id": "opaque-id",
    "generated_at": "2026-01-01T00:00:00.000Z"
  }
}
```

## İlkin endpoint səthi

| Metod və yol | Məqsəd |
| --- | --- |
| `POST /api/v2/replay-sessions` | Replay sessiyası yaratmaq |
| `GET /api/v2/replay-sessions` | Sessiyaları səhifələmək |
| `GET /api/v2/replay-sessions/{id}` | Sessiya və checkpoint detalı |
| `POST /api/v2/replay-sessions/{id}/commands` | Start, step, pause, resume, cancel |
| `GET /api/v2/replay-sessions/{id}/events` | Eventləri cursor ilə oxumaq |
| `POST /api/v2/quality-reports` | Keyfiyyət analizini başlatmaq |
| `GET /api/v2/quality-reports` | Hesabatları səhifələmək |
| `GET /api/v2/quality-reports/{id}` | Hesabat xülasəsi |
| `GET /api/v2/quality-reports/{id}/findings` | Tapıntıları səhifələmək |
| `GET /api/v2/audit-events` | Sanitizasiya edilmiş audit |
| `GET /api/v2/operational-status` | Phase 2 sağlamlıq detalları |

`/health` minimal servis hazırlığını göstərə bilər, amma qorunan Phase 2
detallarını açıqlamır.

## Sorğu modeli

Replay yaratma sorğusu ən azı `symbol`, `start_time`, `end_time`, `mode`,
snapshot/fingerprint seçimi və replay müqaviləsi versiyasını daşıyır.
Naməlum request sahəsi səssiz qəbul edilmir və `422` qaytarır.

Komanda modeli:

```json
{
  "command": "step",
  "expected_state_version": 4,
  "reason": null
}
```

Uyğun olmayan vəziyyət keçidi `409` qaytarır və qismən icra edilmir.

## Asinxron işlər

Replay və keyfiyyət analizi HTTP request daxilində tam icra edilmir.

- Yaratma `202 Accepted` və resurs ID-si qaytarır.
- Vəziyyət `queued`, `running`, `paused`, `completed`, `failed` və ya
  `cancelled` olur.
- Müştəri statusu təhlükəsiz interval ilə yoxlayır.
- Server `Retry-After` verə bilər.
- İlkin versiyada WebSocket və SSE məcburi deyil.

## Cursor səhifələmə

Xam tick, replay event, finding və audit üçün offset istifadə edilmir. Cursor:

- opaque, imzalanmış və təxmin edilə bilməyən dəyərdir;
- resurs tipi, filter hash-i, snapshot fingerprint-i, sıralama versiyası,
  son sort açarı, istifadəçi sərhədi və bitmə vaxtını bağlayır;
- frontend tərəfindən parse və redaktə edilmir.

Standart `limit` 100, minimum 1, maksimum 500-dür.

```json
{
  "data": [],
  "page": {
    "limit": 100,
    "next_cursor": null,
    "has_more": false
  },
  "meta": {
    "api_version": "2",
    "request_id": "opaque-id",
    "snapshot_fingerprint": "sha256:...",
    "generated_at": "2026-01-01T00:00:00.000Z"
  }
}
```

Yeni tick-lər açıq snapshot-a qarışmır. Cursor başqa filter, istifadəçi və
dataset üçün işləmirsə `409 CURSOR_CONTEXT_CHANGED`; səhv və ya vaxtı bitibsə
`400 CURSOR_INVALID_OR_EXPIRED` qaytarılır. Səhifələr arasında dublikat və
boşluq yaranmamalıdır.

## Filter və ölçü limitləri

- Simvol sayı bir sorğuda maksimum 20-dir.
- Audit sorğusu standart ən çox 7 günlük intervaldır.
- Böyük audit ixracı ayrıca background job tələb edir.
- Sort sahəsi allowlist-dən seçilir.
- Regex, sərbəst SQL, filesystem yolu və sərbəst query expression qəbul edilmir.
- Request body standart maksimum 256 KiB-dir.
- Server yaddaş büdcəsini qorumaq üçün daha kiçik faktiki page qaytara bilər.
- Faktiki limit cavabın `page.limit` sahəsində göstərilir.

## Idempotency

Replay yaratma, replay command, keyfiyyət analizi və audit ixracı
`Idempotency-Key` tələb edir.

- Açarın özü deyil, kriptoqrafik hash saxlanır.
- Eyni user, endpoint, body hash və açar eyni nəticəni qaytarır.
- Eyni açar fərqli body ilə `409 IDEMPOTENCY_KEY_REUSED` qaytarır.
- Retry ikinci resurs və ya ikiqat komanda yaratmır.
- İlkin retention ən az 24 saatdır.

## Rate limit və resurs qoruması

| Sinif | İlkin təhlükəsiz tavan |
| --- | --- |
| Login | 5 uğursuz cəhd, sonra 15 dəqiqə blok |
| Adi read | 120 sorğu/dəqiqə/istifadəçi |
| Ağır read və event page | 30 sorğu/dəqiqə/istifadəçi |
| Replay/quality yaratma | 10 sorğu/dəqiqə, ən çox 3 aktiv iş |
| Replay command | 60 sorğu/dəqiqə/istifadəçi |
| Audit ixracı | 2 aktiv iş/auditor |

`429` təhlükəsiz `Retry-After` verir. Sistem təzyiq altında əvvəlcə Phase 2 ağır
sorğularını yavaşıdır və ya rədd edir; Phase 1 tick qəbulu ayrıca qorunur.

## Standart xəta envelope-u

```json
{
  "error": {
    "code": "REPLAY_STATE_CONFLICT",
    "message": "Əməliyyat cari vəziyyətdə mümkün deyil.",
    "retryable": false,
    "field_errors": []
  },
  "meta": {
    "api_version": "2",
    "request_id": "opaque-id"
  }
}
```

Frontend qərarı sabit `code` əsasında verir. Body traceback, SQL, tam lokal
yol, secret, başqa istifadəçinin kimliyi və xam payload göstərmir.

- `400`: cursor və sintaksis;
- `401`: sessiya yoxdur və ya vaxtı bitib;
- `403`: permission kifayət deyil;
- `404`: resurs yoxdur və ya görünmür;
- `409`: vəziyyət, snapshot və idempotency konflikti;
- `413`: body həddi keçib;
- `422`: sahə və biznes validasiyası;
- `429`: rate/concurrency limiti;
- `503`: database, audit, worker və ya bütövlük xətası.

Gözlənilməz xəta `500 INTERNAL_ERROR` və `request_id` qaytarır.

## Concurrency və optimistic locking

Replay sessiyası monoton `state_version` daşıyır. Komanda gözlənilən versiyanı
göndərir; versiya dəyişibsə `409` qaytarılır.

Permission və ownership yazı zamanı yenidən təsdiqlənir. Vəziyyət dəyişikliyi
və audit eyni uğur sərhədindədir. Audit yazılmasa əməliyyat uğurlu göstərilmir.

## Frontend davranışı

- Cursor opaque saxlanılır, offset yaradılmır.
- `401` təhlükəsiz login keçidi verir.
- `403` aydın icazə mesajı göstərir.
- `409` son vəziyyəti yenidən alır.
- `429` `Retry-After`-a hörmət edir.
- `503` son məlumatı “canlı” kimi göstərmir.
- Idempotency açarı yalnız eyni user niyyətinin retry-si üçün təkrar işlədilir.

## CORS və təhlükəsizlik

- Production CORS yalnız dəqiq allowlist origin qəbul edir.
- Credential ilə wildcard origin qadağandır.
- Cookie əsaslı dəyişdirici sorğu CSRF müdafiəsi tələb edir.
- MIME, frame, referrer və uyğun CSP başlıqları tətbiq olunur.
- Production API sənədi anonim şəkildə daxili endpoint detallarını açıqlamır.

## Məcburi testlər

1. Uğurlu və xəta envelope-u schema testindən keçir.
2. Naməlum request sahəsi `422` alır.
3. Cursor snapshot daxilində dublikat və boşluq yaratmır.
4. Cursor başqa filter, user və dataset üçün işləməz.
5. Yeni tick açıq snapshot-a qarışmır.
6. Limit sərhədləri və böyük body yoxlanır.
7. Eyni idempotency retry-si yalnız bir nəticə yaradır.
8. Eyni açar fərqli body ilə `409` alır.
9. Paralel komandada yalnız doğru `state_version` qalib gəlir.
10. Permission və ownership backend-də yoxlanır.
11. Audit yazılmadıqda əməliyyat fail-closed dayanır.
12. Xəta və log secret, SQL, yol və traceback sızdırmır.
13. `429` və `503` altında Phase 1 tick qəbulu sağlam qalır.
14. Frontend əsas xəta hallarını düzgün göstərir.
15. Bütün testlər sintetik müvəqqəti bazada işləyir.

## İcra ardıcıllığındakı yeri

1. `/api/v2` ümumi response və error modelləri.
2. Auth, permission və request ID middleware.
3. Cursor imzalama və snapshot repository-si.
4. Idempotency repository-si.
5. Replay və quality endpoint-ləri.
6. Rate, concurrency və body limitləri.
7. Frontend API client-i.
8. OpenAPI, backend, frontend və yük testləri.

Bu sənəd Phase 2 API kodunun başladılması və ya rəsmi START verilməsi demək deyil.
