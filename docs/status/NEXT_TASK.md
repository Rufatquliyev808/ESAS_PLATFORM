# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Phase 2 qəbul sübutlarını və yalnız-oxuma analiz iş axınını yekunlaşdırmaq.

## Sərhədlər

- Real interval üzrə həm `step`, həm `max_speed` replay sübutu alınmalıdır.
- Tamamlanmış sessiyaların keyfiyyət hesabatı və event səhifələri yoxlanmalıdır.
- Eyni dataset üzrə deterministik nəticə sübutu saxlanmalıdır.
- Analiz çıxışı yalnız müşahidə və hesabat olmalı, ticarət qərarı verməməlidir.

## Tamamlanma meyarları

- Qəbul sübutları tarix, session ID, fingerprint və nəticə ilə sənədləşdirilir.
- Replay xam tick cədvəlini dəyişmir.
- Determinizm və keyfiyyət qapısı testləri keçir.
- Tam backend və frontend regressiyası yaşıl qalır.

## Sonrakı addım

Qəbul sübutlarından sonra texniki analiz göstəricilərinin yalnız-oxuma ilk
versiyasına keçiləcək.
