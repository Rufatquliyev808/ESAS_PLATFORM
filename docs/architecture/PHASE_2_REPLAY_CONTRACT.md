# Phase 2 — Tick replay oxuma müqaviləsi

Status: DESIGN READY — NOT IMPLEMENTED  
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

## Məqsəd və sərhəd

Bu müqavilə saxlanmış xam tick məlumatını dəyişdirmədən, təkrarlana bilən ardıcıllıqla
oxumaq üçün Phase 2 sərhədini müəyyən edir.

Phase 2 replay:

- yalnız `SELECT` əməliyyatları aparır;
- siqnal, proqnoz, ticarət qərarı və order yaratmır;
- xam `tick_events` sətrlərini yeniləmir və silmir;
- frontend-i SQLite bazasına birbaşa qoşmur.

## Sorğu müqaviləsi

İlkin qorunan endpoint:

```text
GET /replay/ticks
```

Sorğu yalnız etibarlı monitorinq sessiyası ilə qəbul edilir.

| Parametr | Qayda |
| --- | --- |
| `symbol` | Məcburidir; boş ola bilməz |
| `start_at` | Məcburidir; UTC ISO-8601; aralığa daxildir |
| `end_at` | Məcburidir; UTC ISO-8601; aralığa daxil deyil |
| `page_size` | Könüllüdür; ilkin dəyər `250`, maksimum `1000` |
| `cursor` | Könüllüdür; backend tərəfindən verilən qeyri-şəffaf davam açarı |

Vaxt aralığı `[start_at, end_at)` formasındadır. `end_at > start_at` olmalıdır. Hər iki
sərhədin məcburi olması canlı bazaya yeni tick yazılarkən replay nəticəsinin dəyişməsinin
qarşısını alır.

## Deterministik sıralama

Kanonik sıra:

```text
event_timestamp ASC, event_id ASC
```

`event_timestamp` əsas zaman açarıdır. Unikal `event_id` eyni timestamp-a malik tick-lər
üçün sabit ikinci açardır. Eyni sorğu və eyni verilənlər bazası vəziyyəti həmişə eyni
ardıcıllığı verməlidir.

Offset səhifələmə istifadə edilmir. Cursor son qaytarılan
`(event_timestamp, event_id)` cütünü, sorğunun simvol və vaxt sərhədlərini özündə
bağlayan, dəyişdirilməyə qarşı qorunan qeyri-şəffaf nişandır.

Konseptual davam şərti:

```sql
AND (
  event_timestamp > :cursor_timestamp
  OR (event_timestamp = :cursor_timestamp AND event_id > :cursor_event_id)
)
ORDER BY event_timestamp ASC, event_id ASC
LIMIT :page_size_plus_one
```

Cursor başqa simvol, vaxt aralığı və ya səhifə ölçüsü ilə istifadə edilə bilməz.

## Cavab müqaviləsi

```json
{
  "contract_version": "1.0",
  "query": {
    "symbol": "GOLD",
    "start_at": "2026-07-30T00:00:00.000Z",
    "end_at": "2026-07-31T00:00:00.000Z",
    "page_size": 250
  },
  "items": [],
  "page": {
    "has_more": false,
    "next_cursor": null
  }
}
```

Hər tick ən azı bunları qaytarır:

- `event_id`, `event_timestamp`, `received_at`;
- `symbol`, `bid`, `ask`, `last`, `volume`, `flags`;
- `source_time_msc`, `source`, `event_version`, `module_version`.

`raw_event_json` ilkin API cavabına daxil edilmir; audit ehtiyacı ayrıca qorunan
endpoint və ya ixrac müqaviləsi ilə həll olunmalıdır.

## Xəta davranışı

- `401`: etibarlı monitorinq sessiyası yoxdur;
- `400`: cursor dəyişdirilib, pozulub və ya başqa sorğuya aiddir;
- `422`: parametr formatı, vaxt sırası və ya səhifə ölçüsü yanlışdır;
- `503`: verilənlər bazası müvəqqəti əlçatan deyil.

Xəta cavabı xam SQL, lokal fayl yolu, açar və ya daxili traceback göstərməməlidir.

## Verilənlər bazası tələbi

İcra zamanı aşağıdakı indeks ayrıca migration ilə əlavə ediləcək:

```sql
CREATE INDEX ... ON tick_events(symbol, event_timestamp, event_id);
```

Migration-dan əvvəl və sonra sətir sayı, minimum/maksimum vaxt və SQLite
`quick_check` müqayisə edilməlidir. İndeks əlavə edilməsi xam tick məlumatının
məzmununu dəyişməməlidir.

## Qəbul meyarları

İcra tamamlanmış sayılmaq üçün:

1. Eyni sorğu iki dəfə eyni `event_id` ardıcıllığını qaytarır.
2. Eyni timestamp-a malik event-lər `event_id` ilə sabit sıralanır.
3. Səhifə sərhədlərində boşluq və dublikat yaranmır.
4. `start_at` anındakı tick daxil, `end_at` anındakı tick xaric edilir.
5. Cursor başqa sorğuda və dəyişdirilmiş formada rədd edilir.
6. `page_size` həddi aşılmır və böyük nəticə yaddaşa bütöv yüklənmir.
7. Replay-dən əvvəl və sonra `tick_events` sətir sayı və məzmun nəzarət cəmi dəyişmir.
8. Frontend nəticəni yalnız qorunan API-dən alır.
9. Repository testində `UPDATE`, `DELETE` və `INSERT` yolu mövcud olmur.
10. Paralel yeni tick qəbulu sabit `[start_at, end_at)` nəticəsinin əvvəlki
    səhifələrini dəyişmir.

## Phase 1-dən sonra icra ardıcıllığı

1. Yalnız-oxuma repository və deterministik sıra testləri.
2. İndeks migration-u və məlumat bütövlüyü yoxlaması.
3. Cursor kodlayıcısı və sorğu doğrulaması.
4. Sessiya ilə qorunan API endpoint-i.
5. Böyük interval üçün yaddaş və performans testləri.
6. Replay sessiyası və məlumat keyfiyyəti modullarına keçid.

Bu sənədin hazırlanması Phase 2 istehsal kodunun başladılması demək deyil.
