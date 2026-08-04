# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca istifadəçi təsdiqi gözləyir
Prioritet: HIGH
Mərhələ: Causal BOS/CHoCH detektoru 1.0.0

## Məqsəd

Təsdiqlənmiş bazar strukturu pivotları və yalnız bağlanmış barlarla strukturun davamını (BOS)
və mümkün istiqamət dəyişməsini (CHoCH) səbəbiyyət qaydasında müşahidə etmək.

## Sərhədlər

- Bullish və bearish müşahidələr ayrıca qalır.
- Qırılma yalnız pivot əvvəlcədən təsdiqləndikdən və bar bağlandıqdan sonra qiymətləndirilir.
- BOS və CHoCH anlayışları, bağlanma məsafəsi, köhnəlmə və ziddiyyət qaydaları versiyalanır.
- Yetərsiz, qırılma olmayan və ziddiyyətli hallar açıq statusla göstərilir.
- Nəticə yalnız tədqiqat müşahidəsidir; siqnal, giriş, risk ölçüsü və order deyil.
- Retest, FVG, order-block və avtomatik əməliyyat bu mərhələyə daxil deyil.

## Tamamlanma meyarları

- Deterministik BOS/CHoCH müqaviləsi və no-lookahead testləri.
- Gələcək bar əvvəlki müşahidəni dəyişmir.
- Bullish/bearish nəticələr frontend-də sadə Azərbaycan dilində ayrılıqda görünür.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Başlama şərti

Bu yeni mərhələ istifadəçinin ayrıca təsdiqindən sonra başlanacaq.
