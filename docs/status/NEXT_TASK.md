# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 4 təqdimat qatı

## Tapşırıq

Qorunan texniki analiz API-sinin EMA, RSI və ATR nəticələrini müasir, sadə və rahat
anlaşılan frontend ekranında göstərmək.

## Sərhədlər

- Hər indikator ayrıca modul/kart kimi qurulmalıdır ki, sonrakı düzəlişlər bir-birindən
  asılı olmasın.
- Qrafik yalnız qapalı replay şamlarını göstərməlidir.
- İstifadəçi timeframe, EMA, RSI, ATR periodlarını və görünən şam sayını seçə bilməlidir.
- Warm-up (`insufficient_data`) vəziyyəti gizlədilməməlidir.
- Dataset, bar və indikator lineage məlumatı sadə “Məlumat mənbəyi” bölməsində görünməlidir.
- Ekran mobil və masaüstü ölçülərdə rahat işləməlidir.
- Strategiya, al/sat siqnalı, avtomatik qərar və order icrası bu mərhələyə daxil deyil.

## Tamamlanma meyarları

- İcazəsiz istifadəçi analiz ekranını görə bilmir.
- Sessiya və timeframe dəyişəndə nəticə aydın yüklənmə/xəta vəziyyəti ilə yenilənir.
- EMA qiymət qrafikində, RSI və ATR ayrıca oxunaqlı panellərdə göstərilir.
- Boş dataset və warm-up halları istifadəçiyə aydın Azərbaycan dilində izah edilir.
- Frontend lint/build və tam backend regressiyası yaşıl qalır.

## Sonrakı addım

Frontend analiz ekranından sonra indikatorların üzərində ayrıca, versiyalanmış strategiya
modulları layihələndiriləcək. Strategiya mərhələsi ayrıca təsdiqdən sonra başlayacaq.
