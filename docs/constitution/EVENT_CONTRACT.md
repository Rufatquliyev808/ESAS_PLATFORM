# Event Contract

Version: 1.0

Status: Draft

---

# Purpose

Bu sənəd ESAS Platform-da modullar arasında məlumat mübadiləsinin standartını müəyyən edir.

Heç bir modul digər modulun daxili dəyişənlərinə birbaşa müraciət etməməlidir.

Bütün məlumat mübadiləsi standart hadisələr (Events) vasitəsilə həyata keçirilir.

Bu yanaşma modulların müstəqilliyini qoruyur və platformanın genişlənməsini asanlaşdırır.

---# Event Principles

## Rule 1

Hər hadisənin (Event) bir sahibi olur.

Event yaradan modul onun mənbəyi hesab olunur.

Digər modullar həmin hadisəni yalnız oxuya bilər.

Onu dəyişdirə bilməz.

---

## Rule 2

Event dəyişdirilməzdir (Immutable).

Yaradıldıqdan sonra event-in məzmunu dəyişdirilə bilməz.

Əgər yeni məlumat yaranırsa, yeni event yaradılır.

---

## Rule 3

Event-lər zaman ardıcıllığı ilə saxlanılır.

Hər event:

- Timestamp
- Source
- Event Type
- Payload

məlumatlarını daşımalıdır.

---# Standard Event Structure

Hər Event aşağıdakı standart struktura uyğun olmalıdır.

| Field | Description |
|--------|-------------|
| event_id | Unikal Event ID |
| event_type | Hadisənin növü |
| timestamp | UTC vaxtı |
| source | Event-i yaradan modul |
| version | Event formatının versiyası |
| symbol | Maliyyə aləti |
| payload | Əsas məlumat |
| metadata | Əlavə məlumat |

---

Bu struktur platformadakı bütün event-lər üçün ortaq standartdır.

# Event Naming Convention

Event adları aşağıdakı qaydaya uyğun olmalıdır.

OBJECT_ACTION

Nümunələr:

PRICE_UPDATED

TICK_RECEIVED

BAR_CLOSED

TRADE_OPENED

TRADE_CLOSED

ORDER_SENT

ORDER_REJECTED

MODEL_UPDATED

PATTERN_FOUND

NEWS_RECEIVED

RISK_LIMIT_REACHED

SYSTEM_STARTED

SYSTEM_STOPPED

LOGGER_ERROR

DATABASE_UPDATED

# Event Versioning

Event strukturu dəyişdirildikdə yeni versiya yaradılır.

Köhnə modullar mümkün olduğu qədər əvvəlki versiyanı dəstəkləməyə davam etməlidir.

Bu yanaşma platformanın geriyə uyğunluğunu (Backward Compatibility) qoruyur.

Nümunə:

PRICE_UPDATED v1

PRICE_UPDATED v2

