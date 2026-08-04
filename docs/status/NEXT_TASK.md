# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

MT5/backend vaxt normallaşdırmasını düzəltmək və yalnız-oxuma texniki analiz
göstəricilərinin ilk versiyasını qurmaq.

## Sərhədlər

- `DQ-009` xəbərdarlığının kök səbəbi saat zonası və qəbul vaxtı müqaviləsi üzrə
  müəyyən edilməlidir.
- Mövcud xam tick-lər dəyişdirilməməli; düzəliş yeni qəbul olunan event-lər və ya
  yalnız-oxuma normallaşdırma qatında edilməlidir.
- İlk analiz indikatorları versiyalanmış, deterministik və replay dataset-inə bağlı
  olmalıdır.
- Analiz çıxışı yalnız müşahidə və hesabat olmalı, ticarət qərarı verməməlidir.

## Tamamlanma meyarları

- Yeni real intervalda yanlış `received_at < event_timestamp` xəbərdarlığı yaranmır.
- Eyni replay dataset-i üçün indikator nəticəsi təkrar icrada eyni fingerprint verir.
- Replay və analiz xam tick cədvəlini dəyişmir.
- Tam backend və frontend regressiyası yaşıl qalır.

## Sonrakı addım

İlk indikator paketindən sonra yalnız-oxuma analiz API-si və dashboard kartları
əlavə ediləcək; ticarət qərarı və order icrası hələ bağlı qalacaq.
