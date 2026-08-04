# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca təsdiq gözləyir
Prioritet: HIGH
Mərhələ: Phase 4 nəticə ölçmə və müqayisə infrastrukturu

## Tapşırıq

EMA və RSI müşahidələrinin gələcək qapalı bar nəticələri ilə yalnız tədqiqat məqsədli,
no-lookahead qaydasını qoruyan qiymətləndirilməsini qurmaq.

## Sərhədlər

- Gələcək nəticə üfüqləri versiyalanacaq və yalnız müşahidədən sonrakı qapalı barlardan qurulacaq.
- Gələcək qiymət müşahidənin yaradılmasına və ya əvvəlki hesablamaya daxil olmayacaq.
- Gəlir istiqaməti, əhatə və yetkinləşməmiş nəticə metrikləri ayrıca göstəriləcək.
- EMA və RSI modulları müstəqil qalacaq və frontend-də ayrı görünəcək.
- Walk-forward təməli hazırlanacaq; order və canlı ticarət daxil deyil.

## Tamamlanma meyarları

- Determinizm, sərhəd, yetkinləşməmiş nəticə və no-lookahead testləri keçir.
- Nəticə lineage və fingerprint ilə mənbə məlumatına bağlanır.
- Panel metrikləri sadə Azərbaycan dilində izah edir.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Sonrakı addım

Bu mərhələ istifadəçinin ayrıca təsdiqindən sonra başlayacaq. Müsbət keçmiş nəticə canlı
ticarət icazəsi sayılmır.
