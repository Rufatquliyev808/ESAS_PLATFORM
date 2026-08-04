# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Bağlanmış replay şamları üzərində yalnız-oxuma `EMA`, `RSI` və `ATR` indikator
paketinin ilk versiyasını qurmaq.

## Sərhədlər

- MT5/backend UTC normallaşdırması `1.6.1` ilə tamamlanıb; mövcud xam tick-lər
  dəyişdirilməməlidir.
- Deterministik `bar-builder 1.0.0` `M1`, `M5`, `M15` və `H1` şamları üçün hazırdır;
  indikatorlar yalnız onun tam bağlanmış şamlarını qəbul etməlidir.
- İlk analiz indikatorları versiyalanmış, deterministik və replay dataset-inə bağlı
  olmalıdır.
- Analiz çıxışı yalnız müşahidə və hesabat olmalı, ticarət qərarı verməməlidir.

## Tamamlanma meyarları

- EMA, RSI və ATR yalnız cari və əvvəlki bağlanmış şamlardan hesablanır.
- Warm-up tamamlanmayan göstəricilər `insufficient_data` kimi təqdim edilir.
- Eyni bar fingerprint-i üçün indikator nəticəsi təkrar icrada eyni fingerprint verir.
- Replay və analiz xam tick cədvəlini dəyişmir.
- Tam backend və frontend regressiyası yaşıl qalır.

## Sonrakı addım

İlk indikator paketindən sonra yalnız-oxuma analiz API-si və sadə izahlı müasir
dashboard kartları əlavə ediləcək; strategiya, ticarət qərarı və order icrası bağlı
qalacaq.
