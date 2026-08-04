# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca təsdiq gözləyir
Prioritet: HIGH
Mərhələ: Phase 4 xronoloji walk-forward müqayisə təməli

## Tapşırıq

EMA və RSI tədqiqat nəticələrini xronoloji inkişaf və yoxlama intervallarına ayıran,
parametrləri gələcək məlumatdan qoruyan versiyalanmış walk-forward müqayisəsi qurmaq.

## Sərhədlər

- Bölünmə yalnız vaxt sırası ilə aparılacaq; təsadüfi qarışdırma olmayacaq.
- Parametrlər yalnız inkişaf intervalında seçiləcək, yoxlama intervalı toxunulmaz qalacaq.
- EMA və RSI müstəqil eksperimentlər kimi saxlanacaq.
- Əhatə, yetkinləşməmiş nəticə və xərcsiz tarixi dəyişiklik ayrıca göstəriləcək.
- Keçmiş nəticə gəlir vəd etməyəcək; order, canlı siqnal və kapital riski daxil deyil.

## Tamamlanma meyarları

- Xronoloji sərhəd, data leakage, determinizm və kiçik dataset testləri keçir.
- Eksperiment manifesti bütün parametrləri və upstream fingerprint-ləri saxlayır.
- Frontend inkişaf və yoxlama nəticələrini sadə Azərbaycan dilində ayırır.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Sonrakı addım

Bu mərhələ yalnız istifadəçinin ayrıca təsdiqindən sonra başlayacaq. Cari tarixi nəticə
ölçümü və gələcək walk-forward müqayisəsi ticarət icazəsi deyil.
