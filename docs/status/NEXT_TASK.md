# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca istifadəçi təsdiqi gözləyir
Prioritet: HIGH
Mərhələ: Causal FVG detektoru 1.0.0

## Məqsəd

Bağlanmış barlardan yaranan bullish və bearish fair value gap sahələrini yalnız məlum olduqları andan sonra izləmək. Doldurulma, qismən doldurulma, etibarsızlaşma və yetərsiz məlumat halları ayrıca göstərilməlidir.

## Sərhədlər

- Yalnız tamamlanmış replay və bağlanmış barlar.
- Bullish və bearish nəticələr ayrıdır.
- No-lookahead və deterministik fingerprint məcburidir.
- Frontend sadə Azərbaycan dilində ayrıca kartlar göstərir.
- Order-block birləşməsi, strategiya, siqnal, giriş, stop, hədəf, risk ölçüsü və avtomatik order daxil deyil.

## Başlama şərti

Bu yeni mərhələ istifadəçinin ayrıca təsdiqindən sonra başlanacaq.

## 2026-08-05 frontend mərhələsinin vəziyyəti

Sol menyulu, bölmə əsaslı frontend iş sahəsi tamamlanıb və `8/8` frontend testi ilə yoxlanıb.
Aktiv növbəti müstəqil iş yuxarıda göstərilən `Causal FVG detektoru 1.0.0` mərhələsidir.
Bu mərhələ yalnız istifadəçinin ayrıca təsdiqindən sonra başlanmalıdır.

## 2026-08-05 frontend fokus düzəlişi

Replay idarəetməsi yalnız öz menyusunda saxlanılıb. Digər analiz bölmələri qısa replay
konteksti, aid nəticə, `Sessiyanı dəyiş` keçidi və üç addımlı istifadə təlimatı göstərir.
Frontend production build və `9/9` test uğurla keçib. Növbəti müstəqil iş dəyişməyib:
`Causal FVG detektoru 1.0.0`; başlamazdan əvvəl ayrıca istifadəçi təsdiqi tələb olunur.
