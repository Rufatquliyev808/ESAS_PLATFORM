# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca təsdiq gözləyir
Prioritet: HIGH
Mərhələ: Phase 4 strategiya nəticəsi API-si və müqayisə görünüşü

## Tapşırıq

Tamamlanmış replay sessiyası üzərində seçilmiş, versiyalanmış strategiya modulunu
işlədən qorunan read-only API və nəticələri müqayisə edən frontend görünüşü hazırlamaq.

## Sərhədlər

- Yalnız sessiya sahibinin tamamlanmış replay məlumatı istifadə ediləcək.
- Strategiya ayrıca seçiləcək; parametrlər və lineage fingerprint-ləri görünəcək.
- Nəticələr tədqiqat müşahidəsi kimi təqdim ediləcək, BUY/SELL siqnalı kimi yox.
- Warm-up, boş məlumat, dataset drift və köhnə versiya halları açıq göstəriləcək.
- Canlı order, broker əmri, avtomatik risk və ticarət icrası daxil deyil.

## Tamamlanma meyarları

- Qorunan API strategiya nəticəsini deterministik qaytarır.
- Frontend strategiyaları ayrı kartlarda seçməyə və müqayisə etməyə imkan verir.
- Strategiya versiyası, parametrlər, sayımlar və lineage aydın görünür.
- İcazə, drift, determinizm və frontend vəziyyət testləri keçir.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Sonrakı addım

Bu mərhələ istifadəçinin ayrıca təsdiqindən sonra başlayacaq. Canlı ticarət ayrıca
təhlükəsizlik və sübut qapısından keçmədən aktiv edilməyəcək.
