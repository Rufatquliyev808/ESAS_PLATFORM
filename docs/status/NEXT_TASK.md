# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca təsdiq gözləyir
Prioritet: HIGH
Mərhələ: Phase 4 ikinci müstəqil strategiya müşahidə modulu

## Tapşırıq

RSI əsasında bazar momentum rejimini təsnif edən ikinci, müstəqil və versiyalanmış
araşdırma modulunu hazırlamaq və mövcud müqayisə laboratoriyasında ayrıca kart kimi
göstərmək.

## Sərhədlər

- Modul `rsi_regime_observation` kimi ayrıca paket və versiya daşıyacaq.
- RSI aşağı/neytral/yüksək rejimləri konfiqurasiya olunan hədlərlə təsnif ediləcək.
- Warm-up, sərhəd qiymətləri, determinizm və no-lookahead ayrıca test olunacaq.
- EMA və RSI modulları bir-birindən asılı olmadan müqayisə kartlarında görünəcək.
- Nəticələr tədqiqat müşahidəsi olacaq; canlı order və ticarət icrası daxil deyil.

## Tamamlanma meyarları

- İkinci modul ümumi strategiya müqaviləsinə dəyişiklik etmədən qoşulur.
- Eyni girişlər eyni fingerprint və sayımları qaytarır.
- Frontend hər iki modulu ayrıca, aydın kartlarda göstərir.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Sonrakı addım

Bu yeni mərhələ istifadəçinin ayrıca təsdiqindən sonra başlayacaq. Canlı ticarət ayrıca
təhlükəsizlik və sübut qapısından keçmədən aktiv edilməyəcək.
