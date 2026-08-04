# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Tamamlanmış replay keyfiyyət hesabatını və `DQ-010` statistikalarını daxili,
yalnız oxuma üçün nəzərdə tutulmuş API repository qatına çıxarmaq.

## Sərhədlər

- Endpoint yalnız tamamlanmış replay sessiyasını qəbul etməlidir.
- Cavab manifest, yekun status, tapıntılar və statistikaları dəyişmədən qaytarmalıdır.
- Mövcud autentifikasiya sərhədi qorunmalı və xəta cavabları təhlükəsiz olmalıdır.
- Xam tick-lər dəyişdirilməməli; API, frontend və canlı migration hələ əlavə edilməməlidir.

## Tamamlanma meyarları

- API repository testi tam hesabatı və deterministik fingerprint-i yoxlayır.
- Mövcud olmayan və tamamlanmamış sessiyalar təhlükəsiz rədd edilir.
- Tam backend regressiyası keçir və canlı baza toxunulmaz qalır.
- Mövcud backend testləri keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

Statistika qatı qəbul edildikdən sonra qorunan Phase 2 replay/keyfiyyət API-sinin
repository sərhədi hazırlanacaq.
