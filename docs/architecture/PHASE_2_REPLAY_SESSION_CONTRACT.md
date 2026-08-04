# Phase 2 — Replay sessiyası və həyat dövrü müqaviləsi

Status: IMPLEMENTATION IN PROGRESS — STEP MODE READY
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

Worker claim, lease, fencing və scheduler qaydaları:
`docs/architecture/PHASE_2_WORKER_SCHEDULER_CONTRACT.md`

## Məqsəd və sərhəd

Bu müqavilə sabit tick aralığını idarə olunan sessiya daxilində deterministik replay
etmək üçün vəziyyətləri, əmrləri və qorunan API-ni müəyyən edir.

Replay sessiyası:

- xam tick məlumatını yalnız replay oxuma müqaviləsi ilə oxuyur;
- yaradıldıqdan sonra giriş parametrlərini dəyişmir;
- heç bir siqnal, qərar, order və broker əməliyyatı yaratmır;
- yalnız törəmə sessiya vəziyyəti və audit qeydləri yaza bilər;
- `tick_events` cədvəlini dəyişmir və silmir.

Əlaqəli müqavilələr:

- `docs/architecture/PHASE_2_REPLAY_CONTRACT.md`
- `docs/architecture/PHASE_2_DATA_QUALITY_CONTRACT.md`
- `docs/architecture/PHASE_2_ACCESS_CONTROL_CONTRACT.md`
- `docs/architecture/PHASE_2_OBSERVABILITY_CONTRACT.md`

## Dəyişməz sessiya girişi

Sessiya yaradılarkən aşağıdakı parametrlər sabitlənir:

| Sahə | Qayda |
| --- | --- |
| `symbol` | Məcburidir; bir sessiya üçün bir simvol |
| `start_at` | UTC ISO-8601; aralığa daxildir |
| `end_at` | UTC ISO-8601; aralığa daxil deyil |
| `mode` | `step` və ya `max_speed` |
| `replay_contract_version` | İlkin versiya `1.0` |
| `quality_rule_version` | Könüllü analiz üçün ilkin versiya `1.0` |

Vaxt aralığı `[start_at, end_at)` formasındadır. Sessiya yaradıldıqdan sonra simvol,
vaxt aralığı, rejim və müqavilə versiyaları dəyişdirilə bilməz. Fərqli giriş yeni
sessiya tələb edir.

## Verilənlər toplusunun izi

Sessiya başlamazdan əvvəl seçilmiş aralıq üçün aşağıdakılar saxlanılır:

- `tick_count`;
- ilk və son kanonik `(event_timestamp, event_id)` açarı;
- kanonik sıradakı `event_id` dəyərlərindən axın şəklində hesablanan SHA-256
  `dataset_fingerprint`.

Fingerprint bütün payload-ın əvəzi deyil. O, eyni sessiyanın sonradan fərqli event
toplusu üzərində səssiz işləməsini aşkarlayan təkrar istehsal izidir.

`tick_count == 0` sessiya yaradılmasını rədd etmir. Sessiya `completed` vəziyyətinə
keçir və boş nəticə audit olunur.

## İcra rejimləri

### `step`

Sessiya yalnız istifadəçi əmri ilə irəliləyir. Hər addım əmri `1..1000` tick tələb
edə bilər. Backend tələb olunan saydan çox tick emal etmir.

Addımın cavabı emal edilən faktiki tick sayını və yeni checkpoint-i qaytarır.
Aralığın sonuna çatdıqda sessiya avtomatik `completed` olur.

### `max_speed`

Sessiya tick-ləri real vaxt gecikməsini təqlid etmədən, kanonik sırada və limitli
batch-lərlə emal edir. İlkin daxili batch limiti `1000` tick-dir.

Maksimum sürət “bütün məlumatı yaddaşa yüklə” demək deyil. İcra cursor ilə davam
edir və hər uğurlu batch-dən sonra checkpoint saxlayır.

## Sessiya vəziyyətləri

```text
created
  ├─ start ─> running
  ├─ cancel ─> cancelled
  └─ empty range ─> completed

running
  ├─ pause ─> paused
  ├─ end reached ─> completed
  ├─ cancel ─> cancelled
  ├─ recoverable interruption ─> interrupted
  └─ terminal error ─> failed

paused
  ├─ resume ─> running
  └─ cancel ─> cancelled

interrupted
  ├─ resume ─> running
  └─ cancel ─> cancelled
```

`completed`, `cancelled` və `failed` terminal vəziyyətlərdir. Terminal sessiya
yenidən başladılmır; eyni girişlə yeni sessiya yaratmaq olar.

`step` sessiyası start edildikdən sonra növbəti addımı gözləyərkən `paused`
vəziyyətində saxlanılır.

## Checkpoint və restart davranışı

Checkpoint ən son tam emal edilmiş `(event_timestamp, event_id)` açarını,
`processed_ticks` sayını və son uğurlu batch vaxtını saxlayır.

- Batch tam uğurlu olmadan checkpoint irəli çəkilmir.
- Eyni batch təkrar icra olunarsa törəmə nəticə idempotent olmalıdır.
- Backend restartında `running` sessiyalar `interrupted` kimi işarələnir.
- Avtomatik səssiz davam yoxdur; istifadəçi `resume` əmri verir.
- Resume-dan əvvəl dataset fingerprint yenidən yoxlanılır.
- Fingerprint dəyişibsə sessiya `failed` olur və yeni sessiya tələb edilir.

Bu davranış yarımçıq sessiyanı uğurla tamamlanmış kimi göstərməyin qarşısını alır.

## Audit hadisələri

Hər idarəetmə əməliyyatı append-only audit hadisəsi yaradır:

- sessiyanı yaradan və əmri verən istifadəçi kodu;
- `session_id`, əvvəlki və yeni vəziyyət;
- əmrin adı və UTC vaxtı;
- checkpoint və `processed_ticks`;
- təhlükəsiz xəta kateqoriyası.

Audit qeydi parol, bearer nişanı, Bridge açarı, xam SQL, lokal yol və traceback
saxlamır.

## Qorunan API müqaviləsi

### Sessiya yaratmaq

```text
POST /replay/sessions
```

Sorğu:

```json
{
  "symbol": "GOLD",
  "start_at": "2026-07-30T00:00:00.000Z",
  "end_at": "2026-07-31T00:00:00.000Z",
  "mode": "step"
}
```

Cavab `201 Created` və qeyri-şəffaf `session_id` qaytarır.

### Sessiyanı və siyahını oxumaq

```text
GET /replay/sessions/{session_id}
GET /replay/sessions?cursor=...&page_size=...
```

Siyahı `created_at DESC, session_id DESC` sırası və cursor səhifələmə istifadə edir.
İlkin `page_size` `50`, maksimum `200`-dür.

### İdarəetmə əmrləri

```text
POST /replay/sessions/{session_id}/start
POST /replay/sessions/{session_id}/pause
POST /replay/sessions/{session_id}/resume
POST /replay/sessions/{session_id}/advance
POST /replay/sessions/{session_id}/cancel
```

`advance` yalnız `step` rejimində qəbul edilir:

```json
{
  "tick_count": 1
}
```

Eyni idarəetmə sorğusunun şəbəkə retry-si iki dəfə icra olunmaması üçün dəyişdirici
əmrlər məcburi `Idempotency-Key` başlığı qəbul edir. Eyni açar və eyni body əvvəlki
cavabı qaytarır; eyni açar fərqli body ilə `409` alır.

## Sessiya cavabı

```json
{
  "session_id": "opaque-id",
  "state": "paused",
  "mode": "step",
  "query": {
    "symbol": "GOLD",
    "start_at": "2026-07-30T00:00:00.000Z",
    "end_at": "2026-07-31T00:00:00.000Z"
  },
  "contracts": {
    "replay": "1.0",
    "quality": "1.0"
  },
  "dataset": {
    "tick_count": 1000,
    "fingerprint": "sha256:..."
  },
  "progress": {
    "processed_ticks": 10,
    "percent": 1.0,
    "last_event_id": "..."
  },
  "created_by": "RUFAT-091084",
  "created_at": "2026-07-31T10:00:00.000Z",
  "updated_at": "2026-07-31T10:00:10.000Z",
  "error": null
}
```

`percent` boş dataset üçün `100`, digər hallarda
`processed_ticks / tick_count * 100` kimi hesablanır və `0..100` aralığında
məhdudlaşdırılır.

## İcazə və təhlükəsizlik

- Bütün replay endpoint-ləri etibarlı monitorinq sessiyası tələb edir.
- Rollar, permission-lar və ownership
  `docs/architecture/PHASE_2_ACCESS_CONTROL_CONTRACT.md` müqaviləsinə əsaslanır.
- Operator yalnız öz sessiyasını idarə edir; administratorun başqa istifadəçinin
  sessiyasına müdaxiləsi məcburi səbəb və audit tələb edir.
- Sessiya identifikatoru ardıcıl rəqəm kimi təxmin edilə bilməz.
- Mövcud olmayan və istifadəçiyə aid olmayan sessiya eyni `404` cavabını verir.
- İdarəetmə əmri gözlənilməyən vəziyyətdədirsə `409` qaytarılır.
- İşləmə xətası təhlükəsiz kateqoriya ilə saxlanılır, daxili məlumat cavaba çıxmır.
- Eyni anda bir sessiya üçün yalnız bir worker checkpoint yaza bilər.

## Xəta davranışı

- `400`: pozulmuş cursor və ya Idempotency-Key istifadəsi;
- `401`: etibarlı monitorinq sessiyası yoxdur;
- `404`: sessiya tapılmır və ya görünmür;
- `409`: vəziyyət keçidi, dataset fingerprint və ya idempotency münaqişəsi;
- `422`: giriş və ya `tick_count` doğrulaması uğursuzdur;
- `503`: verilənlər bazası və ya worker müvəqqəti əlçatan deyil.

## Saxlama və təmizləmə

Sessiya, checkpoint və audit qeydləri xam tick cədvəlindən ayrı saxlanılır.
Avtomatik silmə ilkin versiyaya daxil deyil. Gələcək retention siyasəti:

- terminal sessiyanın nəticəsini silməzdən əvvəl audit qeydini qoruyur;
- aktiv və ya interrupted sessiyanı silmir;
- istifadəçi təsdiqi və ayrıca sənədləşdirilmiş müddət tələb edir.

## Qəbul testləri

1. Eyni giriş iki sessiyada eyni dataset fingerprint və event ardıcıllığı verir.
2. Sessiya yaradıldıqdan sonra giriş parametrləri dəyişdirilə bilmir.
3. `step` əmri tələb edilən saydan artıq tick emal etmir.
4. `max_speed` böyük aralığı limitli yaddaş və batch-lərlə tamamlayır.
5. Eyni timestamp-a malik tick-lər səhifə sərhədində itmir və təkrarlanmır.
6. Batch xətasında checkpoint irəli getmir.
7. Eyni batch-in təkrar icrası törəmə nəticəni dublikat etmir.
8. Backend restartı `running` sessiyanı `interrupted` edir.
9. Dəyişmiş fingerprint ilə resume `409` verir və sessiyanı `failed` edir.
10. Terminal vəziyyətdən qanunsuz keçid `409` qaytarır.
11. Eyni Idempotency-Key və body iki əməliyyat yaratmır.
12. Sessiyasız endpoint sorğusu `401` qaytarır.
13. Xam `tick_events` sətir sayı və nəzarət cəmi replay-dən sonra dəyişmir.
14. Audit bütün vəziyyət keçidlərini istifadəçi və UTC vaxtı ilə saxlayır.
15. Xəta və audit cavablarında məxfi məlumat görünmür.

## Phase 1-dən sonra icra ardıcıllığı

1. Sessiya və append-only audit schema migration-u.
2. Vəziyyət keçidi modeli və unit testlər.
3. Dataset fingerprint və checkpoint mexanizmi.
4. `step` rejimi və idempotency testləri.
5. `max_speed` worker-i və restart bərpası.
6. Qorunan API və frontend sessiya monitorinqi.
7. Məlumat keyfiyyəti hesabatının sessiya nəticəsinə bağlanması.

Dataset snapshot skeleti tətbiq edilib: tick sayı, ilk/son kanonik mövqe və
uzunluq-prefiksli UTF-8 `event_id` axınından `sha256-event-id-v1` fingerprint
hesablanır. Sessiya və append-only audit sxemi müvəqqəti bazada tətbiq və test edilib.
Sessiya yaratma repository-si snapshot sahələrini və ilkin audit qeydini atomik yazır;
boş dataset birbaşa `completed` olur. Vəziyyət keçidləri, worker və API hələ tətbiq
edilməyib.
