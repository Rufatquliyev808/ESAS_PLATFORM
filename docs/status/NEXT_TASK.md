# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Məlumat keyfiyyəti kataloqunun qalan əsas qaydalarını streaming analizatora əlavə
etmək: event/source vaxt uyğunsuzluğu, natamam qiymət cütü, qeyri-sonlu və mənfi
ədədlər, event müqaviləsi və qəbul gecikməsi.

## Sərhədlər

- `DQ-003`, `DQ-006`, `DQ-007`, `DQ-008` və `DQ-009` müqavilədəki dəqiq hədlərlə
  tətbiq edilməlidir.
- Hər qayda digər qaydanın mənasını qarışdırmadan ayrıca tapıntı qaytarmalıdır.
- Timestamp və qeyri-sonlu ədəd xətaları təhlükəsiz və deterministik işlənməlidir.
- Tapıntılar mövcud yekun hesabat statusuna avtomatik daxil olmalıdır.
- Streaming və məhdud nümunə sərhədi qorunmalıdır.
- Xam tick-lər dəyişdirilməməli; API, frontend və canlı migration hələ əlavə edilməməlidir.

## Tamamlanma meyarları

- Hər yeni qayda üçün minimal sintetik sərhəd testi mövcuddur.
- Warning və critical hədlərinin tam sərhədi ayrıca yoxlanılır.
- Sıfır qiymət, retry gecikməsi və modul/source sərhədləri səhv təsnif edilmir.
- Tam backend regressiyası keçir və canlı baza toxunulmaz qalır.
- Mövcud backend testləri keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

Qayda kataloqu tamamlandıqdan sonra `DQ-010` təsviri spread və tick sürəti
statistikaları streaming üsulla əlavə ediləcək.
