# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Dashboard-da Phase 2 replay idarəetmə görünüşünü hazırlamaq.

## Sərhədlər

- Sessiya yaratma formu simvol, interval və `step/max_speed` rejimini qəbul etməlidir.
- Sessiya siyahısı və detalı mövcud v2 API-lərdən oxunmalıdır.
- Qanuni lifecycle əmrləri `Idempotency-Key` və cari `state_version` ilə göndərilməlidir.
- Event səhifələri cursor ilə, keyfiyyət hesabatı yalnız tamamlandıqda göstərilməlidir.
- Frontend qərar və ticarət əməliyyatı verməməlidir; yalnız replay idarəetməsi və
  müşahidə təmin etməlidir.

## Tamamlanma meyarları

- Loading, empty, error, conflict və unauthorized vəziyyətləri aydın göstərilir.
- Köhnə və təkrar command cavabları təhlükəsiz idarə olunur.
- Klaviatura istifadəsi və mobil görünüş qorunur.
- Frontend lint, build və render yoxlamaları, tam backend regressiyası keçir.

## Sonrakı addım

Replay frontend-dən sonra Phase 2 qəbul sübutları və read-only analiz iş axını
yekunlaşdırılacaq.
