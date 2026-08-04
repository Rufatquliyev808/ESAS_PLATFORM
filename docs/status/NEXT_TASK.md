# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca təsdiq gözləyir
Prioritet: HIGH
Mərhələ: Phase 4 çoxpəncərəli walk-forward sabitlik ölçümü

## Tapşırıq

Tamamlanmış tək xronoloji bölgünü ardıcıl, üst-üstə düşməyən yoxlama pəncərələrinə
genişləndirmək və EMA/RSI nəticəsinin müxtəlif zaman hissələrində sabit qalıb-qalmadığını
ayrıca ölçmək.

## Sərhədlər

- Hər pəncərə yalnız özündən əvvəlki inkişaf məlumatından istifadə edəcək.
- Təsadüfi qarışdırma və gələcək pəncərədən parametr seçimi olmayacaq.
- EMA və RSI müstəqil eksperimentlər kimi saxlanacaq.
- Pəncərə əhatəsi, yetkinləşməmiş nəticə və xərcsiz tarixi dəyişiklik ayrıca göstəriləcək.
- Keçmiş nəticə gəlir vəd etməyəcək; order, canlı siqnal və kapital riski daxil deyil.

## Tamamlanma meyarları

- Ən azı iki ardıcıl yoxlama pəncərəsi deterministik hesablanır.
- Pəncərələr arasında overlap, data leakage, sərhəd və kiçik dataset testləri keçir.
- Hər pəncərə manifest və upstream fingerprint izini saxlayır.
- Frontend ümumi rəqəmi gizlətmədən pəncərə sabitliyini sadə Azərbaycan dilində göstərir.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Sonrakı addım

Bu mərhələ yalnız istifadəçinin ayrıca təsdiqindən sonra başlayacaq. Tamamlanmış tək
bölgü və gələcək çoxpəncərəli ölçüm ticarət icazəsi deyil.
