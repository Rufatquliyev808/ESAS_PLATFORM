# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca təsdiq gözləyir
Prioritet: HIGH
Mərhələ: Phase 4 strategiya layihələndirməsi

## Tapşırıq

Texniki analiz indikatorlarının üzərində versiyalanmış, bir-birindən müstəqil və
yalnız araşdırma məqsədli strategiya modullarının müqaviləsini layihələndirmək.

## Sərhədlər

- İlk mərhələdə yalnız strategiya müqaviləsi, versiya, parametr, giriş indikatorları və
  deterministik replay nəticə modeli hazırlanmalıdır.
- Hər strategiya ayrıca modul olmalı, digər strategiyadan müstəqil test və düzəliş
  edilə bilməlidir.
- Gələcək məlumatın keçmiş nəticəyə sızması qadağandır; yalnız bağlanmış bar istifadə
  edilməlidir.
- Strategiya nəticəsi mənbə dataset/bar/indikator fingerprint-lərinə bağlanmalıdır.
- Nəticələr ilk mərhələdə yalnız araşdırma və müqayisə üçündür.
- Canlı order, broker əmri, avtomatik kapital riski və ticarət icrası daxil deyil.

## Tamamlanma meyarları

- Strategiya kontraktı və modul sərhədləri konstitusiyaya uyğun sənədləşdirilir.
- Ən azı bir sadə istinad strategiyası ayrıca versiyalanmış modul kimi qurulur.
- Determinizm, warm-up, no-lookahead və boş məlumat sınaqları avtomatlaşdırılır.
- Eyni replay və parametrlər eyni nəticə fingerprint-i yaradır.
- Tam backend regressiyası və frontend yoxlamaları yaşıl qalır.

## Sonrakı addım

Bu mərhələ istifadəçinin ayrıca təsdiqindən sonra başlayacaq. Strategiya araşdırması
tamamlandıqdan sonra nəticələrin frontend müqayisə görünüşü ayrıca planlaşdırılacaq;
canlı əməliyyat yenə ayrıca təhlükəsizlik qapısından keçəcək.
