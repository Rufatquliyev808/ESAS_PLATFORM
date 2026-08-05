# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca istifadəçi təsdiqi gözləyir
Prioritet: HIGH
Mərhələ: Causal retest detektoru 1.0.0

## Məqsəd

Təsdiqlənmiş BOS/CHoCH müşahidəsindən sonra qırılmış struktur səviyyəsinə mümkün geri dönüşü
yalnız sonrakı bağlanmış barlarla, səbəbiyyət və no-lookahead qaydasında müşahidə etmək.

## Sərhədlər

- Bullish və bearish retest müşahidələri ayrı qalır.
- Retest yalnız əvvəlki BOS/CHoCH və onun qırılmış pivot səviyyəsi məlum olduqdan sonra axtarılır.
- Toxunma toleransı, qəbul edilən bağlanma, vaxt limiti və invalidasiya qaydaları versiyalanır.
- Yetərsiz, retest olmayan, təsdiqlənməyən və ziddiyyətli hallar açıq statusla göstərilir.
- Nəticə yalnız tədqiqat müşahidəsidir; siqnal, giriş, stop, hədəf, risk ölçüsü və order deyil.
- FVG, order-block, zona birləşdirməsi və avtomatik əməliyyat bu mərhələyə daxil deyil.

## Tamamlanma meyarları

- Deterministik retest müqaviləsi və no-lookahead testləri.
- Gələcək bar əvvəlki müşahidəni dəyişmir.
- Bullish/bearish nəticələr frontend-də sadə Azərbaycan dilində ayrılıqda görünür.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Başlama şərti

Bu yeni mərhələ istifadəçinin ayrıca təsdiqindən sonra başlanacaq.
