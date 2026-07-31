# Phase 2 — Tick məlumat keyfiyyəti müqaviləsi

Status: DESIGN READY — NOT IMPLEMENTED  
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

## Məqsəd və sərhəd

Bu müqavilə sabit replay aralığındakı xam tick-lərin keyfiyyətini ölçmək, nəticəni
təkrar istehsal etmək və hər tapıntını qayda versiyası ilə audit etmək üçündür.

Məlumat keyfiyyəti modulu:

- yalnız replay müqaviləsi ilə oxunan məlumatı analiz edir;
- xam `tick_events` sətrlərini dəyişmir və silmir;
- avtomatik olaraq “məlumat itkisi” hökmü vermir;
- siqnal, proqnoz, ticarət qərarı və order yaratmır.

Əlaqəli oxuma müqaviləsi:
`docs/architecture/PHASE_2_REPLAY_CONTRACT.md`

## Analiz girişi

Hər hesabat aşağıdakı sabit identifikatorlarla yaradılır:

| Sahə | Qayda |
| --- | --- |
| `symbol` | Bir hesabat üçün bir simvol |
| `start_at` | UTC ISO-8601; aralığa daxildir |
| `end_at` | UTC ISO-8601; aralığa daxil deyil |
| `replay_contract_version` | İstifadə olunan replay müqaviləsi |
| `quality_rule_version` | Bütün tətbiq olunan qaydaların versiyası |

Analiz `[start_at, end_at)` aralığına və
`event_timestamp ASC, event_id ASC` kanonik sırasına əsaslanır. Eyni xam məlumat,
eyni aralıq və eyni qayda versiyası eyni nəticəni verməlidir.

## Tapıntı səviyyələri

- `info`: müşahidədir, nasazlıq hökmü deyil;
- `warning`: araşdırılmalı uyğunsuzluqdur;
- `critical`: müqaviləni birbaşa pozan və nəticəyə etibarı azaldan haldır.

Hər tapıntıda `rule_id`, `rule_version`, səviyyə, say, ilk/son nümunə vaxtı və
məhdud sayda nümunə `event_id` saxlanılır. Bütün uyğun sətrlər cavaba yüklənmir.

## Qayda kataloqu — versiya 1.0

### DQ-001 — Event identifikatoru dublikatı

Eyni `event_id` bir neçə dəfə görünürsə `critical` tapıntıdır.

Hazırkı SQLite primary key bu halın saxlanmasına mane olur. Buna görə nəticənin sıfır
olması gözlənilir, lakin qayda storage müqaviləsinin pozulmasını ayrıca yoxlayır.

### DQ-002 — Mənbə vaxtının geriyə getməsi

Kanonik ardıcıllıqda cari `source_time_msc` əvvəlki tick-dən kiçikdirsə `warning`
tapıntıdır.

Bu qayda yalnız eyni `symbol`, `source` və `module_version` ardıcıllığında tətbiq
olunur. Modul versiyası dəyişəndə müqayisə yeni seqmentdən başlayır.

### DQ-003 — Event vaxtı ilə mənbə vaxtının uyğunsuzluğu

`event_timestamp` və `source_time_msc` arasındakı mütləq fərq hesablanır:

- `> 2 saniyə`: `warning`;
- `> 30 saniyə`: `critical`.

Hədlər qayda versiyasının hissəsidir və sonradan səssiz dəyişdirilə bilməz.

### DQ-004 — Ardıcıl tick zaman boşluğu

Eyni simvolun iki ardıcıl tick-i arasındakı zaman fərqi hesablanır.

- `> 30 saniyə`: `info` səviyyəli boşluq namizədi;
- `> 5 dəqiqə`: `warning` səviyyəli uzun boşluq namizədi.

Bu tapıntı öz-özlüyündə məlumat itkisi demək deyil. Bazar sessiyası, həftəsonu,
bayram və alətin ticarət fasiləsi ayrıca sessiya təqvimi olmadan fərqləndirilə
bilməz. Gələcək sessiya təqvimi boşluğu `expected_closed` və `unexpected_gap`
kateqoriyalarına ayıra bilər.

### DQ-005 — Mənfi spread

Həm `bid > 0`, həm də `ask > 0` olduğu halda `ask < bid` olarsa `critical`
tapıntıdır.

`bid == 0` və ya `ask == 0` avtomatik xəta sayılmır; bu hallar DQ-006 ilə ayrıca
ölçülür.

### DQ-006 — Natamam qiymət cütü

Yalnız biri sıfır olduqda:

```text
(bid == 0 və ask > 0) və ya (ask == 0 və bid > 0)
```

`info` tapıntısı yaradılır. Həm `bid`, həm `ask` sıfırdırsa ayrıca sayılır. Bu
hallar MT5 tick tipindən asılı ola bildiyi üçün ilkin versiyada nasazlıq hökmü
verilmir.

### DQ-007 — Qeyri-sonlu və mənfi ədədi dəyər

`bid`, `ask`, `last` sahəsində `NaN`, müsbət/mənfi sonsuzluq və ya mənfi dəyər;
`volume`, `flags` sahəsində mənfi dəyər `critical` tapıntıdır.

Backend modeli bu dəyərlərin çoxunu qəbul zamanı rədd edir. Qayda bazadakı tarixi
və ya xarici yolla daxil olmuş məlumatı yenə də yoxlayır.

### DQ-008 — Event müqaviləsi uyğunsuzluğu

Aşağıdakılardan biri baş verərsə `critical` tapıntıdır:

- `event_type != TICK_RECEIVED`;
- `source != esas.mt5.bridge`;
- `event_version != 1.0`;
- boş `symbol`, `module_version` və ya `event_id`;
- analiz edilən simvol ilə sətrin simvolu fərqlidir.

### DQ-009 — Qəbul gecikməsi

`received_at - event_timestamp` paylanması hesablanır:

- mənfi gecikmə ayrıca `warning` sayılır;
- `> 5 saniyə` gecikmə `info`;
- `> 60 saniyə` gecikmə `warning`.

Bu qayda retry zamanı gecikmiş, amma düzgün saxlanmış event-ləri məlumat itkisi
kimi qiymətləndirmir.

### DQ-010 — Sürət və spread statistikası

Hesabat hökm vermədən aşağıdakı təsviri göstəriciləri qaytarır:

- ümumi tick və saniyə/dəqiqə üzrə tick sayı;
- ardıcıl tick intervalının minimum, median, p95 və maksimumu;
- yalnız müsbət bid/ask cütləri üçün spread minimum, median, p95 və maksimumu;
- sıfır qiymət cütlərinin və natamam cütlərin sayı.

Statistikaların hesab üsulu və yuvarlaqlaşdırma qaydası müqavilə versiyasına
bağlanır.

## Hesabat müqaviləsi

İlkin qorunan endpoint:

```text
GET /quality/ticks/report
```

Sorğu parametrləri replay sorğusundakı `symbol`, `start_at`, `end_at` ilə eynidir.
Hesabat böyük aralığı yaddaşa bütöv yükləmədən səhifə-səhifə hesablanmalıdır.

Konseptual cavab:

```json
{
  "report_id": "opaque-id",
  "generated_at": "2026-07-31T10:00:00.000Z",
  "replay_contract_version": "1.0",
  "quality_rule_version": "1.0",
  "query": {
    "symbol": "GOLD",
    "start_at": "2026-07-30T00:00:00.000Z",
    "end_at": "2026-07-31T00:00:00.000Z"
  },
  "summary": {
    "status": "pass",
    "tick_count": 0,
    "critical_count": 0,
    "warning_count": 0,
    "info_count": 0
  },
  "findings": [],
  "metrics": {}
}
```

`summary.status`:

- `pass`: critical və warning yoxdur;
- `review`: warning var, critical yoxdur;
- `fail`: ən azı bir critical tapıntı var.

`pass` ticarət üçün hazır olmaq demək deyil; yalnız bu qaydalar üzrə keyfiyyət
tapıntısının olmadığını bildirir.

## Audit və dəyişməzlik

- Hesabat giriş aralığını və hər iki müqavilə versiyasını saxlayır.
- Qayda həddi dəyişəndə `quality_rule_version` artırılır.
- Köhnə hesabat yeni qayda ilə səssiz yenidən şərh edilmir.
- Nümunə payload-larda məxfi açar, lokal fayl yolu və xam daxili xəta olmur.
- Analizdən əvvəl və sonra xam tick sətir sayı və nəzarət cəmi dəyişməməlidir.

## Qəbul testləri

1. Eyni fixture və qayda versiyası iki icrada eyni hesabat məzmununu verir
   (`report_id` və `generated_at` istisna olmaqla).
2. Hər qayda üçün ayrıca minimal sintetik fixture mövcuddur.
3. Eyni timestamp və səhifə sərhədi nəticəni dəyişmir.
4. Həftəsonu fasiləsi avtomatik məlumat itkisi kimi göstərilmir.
5. Sıfır bid/ask mənfi spread yaratmır.
6. Mənfi spread yalnız hər iki qiymət müsbət olduqda qeydə alınır.
7. Retry gecikməsi itki kimi deyil, qəbul gecikməsi kimi ölçülür.
8. Hesabatdan əvvəl və sonra `tick_events` dəyişməz qalır.
9. Böyük aralıq limitli yaddaşla işlənir.
10. Sessiyasız API sorğusu `401` qaytarır.
11. Yanlış vaxt aralığı `422`, verilənlər bazası xətası təhlükəsiz `503` qaytarır.
12. Frontend yalnız qorunan API nəticəsini göstərir və özü qayda hesablamır.

## Phase 1-dən sonra icra ardıcıllığı

1. Versiyalanmış qayda kataloqu və sintetik fixture-lər.
2. Axın şəklində işləyən keyfiyyət analizatoru.
3. Determinizm və xam məlumat dəyişməzliyi testləri.
4. Qorunan hesabat API-si.
5. Frontend keyfiyyət kartları və tapıntı detalları.
6. Sessiya təqvimi əlavə edilərsə boşluq qaydasının yeni versiyası.

Bu sənədin hazırlanması Phase 2 istehsal kodunun başladılması demək deyil.
