# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca istifadəçi təsdiqi gözləyir
Prioritet: HIGH
Mərhələ: Causal bazar strukturu detektoru 1.0.0

## Məqsəd

Tamamlanmış hipotez reyestrindəki ilk ailəni ölçülə bilən müşahidəyə çevirmək:
yalnız bağlanmış barlarla HH/HL və LH/LL bazar strukturu vəziyyətlərini hesablamaq.

## Sərhədlər

- LONG və SHORT müşahidələri ayrı qalır.
- Açıq bar və gələcək məlumat hesaba daxil edilmir.
- Pivot qaydası, bərabərlik toleransı, warm-up və invalidasiya əvvəlcədən versiyalanır.
- Yetərsiz və ziddiyyətli məlumat açıq statusla göstərilir.
- Nəticə yalnız tədqiqat müşahidəsidir; siqnal, giriş, risk ölçüsü və order deyil.
- Sosial-media şəkilləri yalnız anlayış mənbəyidir, detector üçün sübut deyil.

## Tamamlanma meyarları

- Deterministik HH/HL və LH/LL detector müqaviləsi və testləri.
- Eyni bağlanmış bar snapshot-u eyni nəticə və fingerprint yaradır.
- Future-leakage və açıq-bar istifadəsi testlə bloklanır.
- Replay üzərində müşahidələrin sadə Azərbaycan dilində ayrıca frontend görünüşü.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Başlama şərti

Bu yeni mərhələ istifadəçinin ayrıca təsdiqindən sonra başlanacaq.
