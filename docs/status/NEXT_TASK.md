# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca istifadəçi təsdiqi gözləyir
Prioritet: HIGH
Mərhələ: Causal likvidlik süpürməsi detektoru 1.0.0

## Məqsəd

Tamamlanmış causal pivotların üzərində bərabər zirvə/dib likvidlik hovuzlarını və yalnız
bağlanmış barla təsdiqlənən wick sweep + səviyyəyə geri bağlanma müşahidələrini hesablamaq.

## Sərhədlər

- Bullish və bearish süpürmə müşahidələri ayrı qalır.
- Açıq bar və gələcək məlumat hesaba daxil edilmir.
- Hovuz toleransı, minimum toxunuş sayı, sweep məsafəsi, geri bağlanma və köhnəlmə qaydası
  əvvəlcədən versiyalanır.
- Yetərsiz və ziddiyyətli məlumat açıq statusla göstərilir.
- Nəticə yalnız tədqiqat müşahidəsidir; siqnal, giriş, risk ölçüsü və order deyil.
- Sosial-media şəkilləri yalnız anlayış mənbəyidir, detector üçün sübut deyil.
- BOS/CHoCH, retest, FVG və order-block bu mərhələyə daxil deyil.

## Tamamlanma meyarları

- Deterministik equal-high/equal-low hovuzu və sweep detector müqaviləsi və testləri.
- Eyni bağlanmış bar snapshot-u eyni nəticə və fingerprint yaradır.
- Future-leakage və açıq-bar istifadəsi testlə bloklanır.
- Replay üzərində bullish və bearish müşahidələrin sadə Azərbaycan dilində ayrıca görünüşü.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Başlama şərti

Bu yeni mərhələ istifadəçinin ayrıca təsdiqindən sonra başlanacaq.
