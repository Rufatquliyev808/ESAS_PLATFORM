# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Deterministik replay sessiyasının ilkin skeletini yaratmaq: sabit giriş intervalından
dataset snapshot metadatasını hesablamaq və eyni giriş üçün eyni fingerprint vermək.

## Sərhədlər

- Snapshot yalnız repository-nin `[start_at, end_at)` sərhədindən oxunmalıdır.
- Dataset tick sayı, ilk və son kanonik mövqe hesablanmalıdır.
- Fingerprint kanonik `event_timestamp + event_id` ardıcıllığından alınmalıdır.
- Eyni dəyişməz dataset iki icrada eyni fingerprint qaytarmalıdır.
- Boş dataset təhlükəsiz və deterministik nəticə verməlidir.
- Xam tick sətrləri dəyişdirilə və silinə bilməz.
- Hələ worker, API, frontend və canlı bazada migration əlavə edilməməlidir.

## Tamamlanma meyarları

- Eyni interval iki icrada eyni tick sayı, sərhədlər və fingerprint verməlidir.
- Eyni timestamp-li event-lərin `event_id` sırası fingerprint-də qorunmalıdır.
- Boş dataset üçün say `0`, ilk/son mövqe `NULL` olmalıdır.
- Səhifələnmiş oxuma böyük intervalı yaddaşa tam yükləməməlidir.
- Snapshot hesablanması xam tick məlumatını dəyişməməlidir.
- Mövcud backend testləri keçməlidir.

## Sonrakı addım

Snapshot skeleti qəbul edildikdən sonra replay sessiyası cədvəlləri və append-only
audit mexanizmi növbəti migration-da, yenə yalnız müvəqqəti bazada yaradılacaq.
