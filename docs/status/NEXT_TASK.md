# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Tamamlanmış replay sessiyasının bağlanmış şam və indikator nəticələrini qorunan,
yalnız-oxuma analiz API-si ilə təqdim etmək.

## Sərhədlər

- Deterministik `bar-builder 1.0.0` `M1`, `M5`, `M15` və `H1` şamları üçün hazırdır;
  `indicator-package 1.0.0` EMA, RSI və ATR nəticələrini deterministik yaradır.
- API yalnız sessiyanın sahibinə və yalnız tamamlanmış replay sessiyasına xidmət etməlidir.
- Sorğu timeframe və indikator periodlarını açıq qəbul etməli, təhlükəsiz hədlərlə
  yoxlamalıdır.
- Xam tick, replay sessiyası və analiz nəticəsi dəyişdirilməməlidir.
- Cavabda dataset/bar/indicator lineage və versiyalar görünməlidir.

## Tamamlanma meyarları

- İcazəsiz və başqa istifadəçiyə aid sorğular təhlükəsiz rədd edilir.
- Açıq replay sessiyası üçün analiz nəticəsi verilmir.
- Eyni tamamlanmış sessiya və parametrlər eyni fingerprint-li cavab verir.
- Warm-up `insufficient_data` vəziyyəti API cavabında itirilmir.
- API strategiya, al/sat siqnalı və order əmri yaratmır.
- Tam backend və frontend regressiyası yaşıl qalır.

## Sonrakı addım

Analiz API-sindən sonra EMA, RSI və ATR-ni ayrı izah edən müasir, sadə dashboard
kartları və qrafik görünüşü əlavə ediləcək; strategiya, ticarət qərarı və order icrası
bağlı qalacaq.
