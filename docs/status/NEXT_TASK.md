# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Yalnız-oxuma texniki analiz göstəricilərinin ilk versiyasını replay dataset-i üzərində
qurmaq.

## Sərhədlər

- MT5/backend UTC normallaşdırması `1.6.1` ilə tamamlanıb; mövcud xam tick-lər
  dəyişdirilməməlidir.
- İlk analiz indikatorları versiyalanmış, deterministik və replay dataset-inə bağlı
  olmalıdır.
- Analiz çıxışı yalnız müşahidə və hesabat olmalı, ticarət qərarı verməməlidir.

## Tamamlanma meyarları

- Yeni `1.6.1` real intervalında yanlış `received_at < event_timestamp` xəbərdarlığı
  yaranmır.
- Eyni replay dataset-i üçün indikator nəticəsi təkrar icrada eyni fingerprint verir.
- Replay və analiz xam tick cədvəlini dəyişmir.
- Tam backend və frontend regressiyası yaşıl qalır.

## Sonrakı addım

İlk indikator paketindən sonra yalnız-oxuma analiz API-si və dashboard kartları
əlavə ediləcək; ticarət qərarı və order icrası hələ bağlı qalacaq.
