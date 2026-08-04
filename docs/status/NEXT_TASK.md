# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Yalnız müvəqqəti test bazalarında işləyən, versiyalanmış və checksum ilə yoxlanan
migration runner-i yaratmaq; replay oxuması üçün
`(symbol, event_timestamp, event_id)` indeksini migration vasitəsilə əlavə etmək.

## Sərhədlər

- Migration canlı `database/ESAS_PLATFORM.sqlite` üzərində icra edilməməlidir.
- Testlər yalnız ayrıca müvəqqəti SQLite bazası istifadə etməlidir.
- Hər migration versiya, ad və dəyişməz checksum ilə qeydə alınmalıdır.
- Eyni migration ikinci dəfə təhlükəsiz no-op olmalıdır.
- Checksum uyğunsuzluğu fail-closed xəta verməlidir.
- Xam `tick_events` sətirləri dəyişdirilə və silinə bilməz.
- Phase 1 canlı tick qəbulu və mövcud API davranışı dəyişməməlidir.

## Tamamlanma meyarları

- Təmiz müvəqqəti bazada migration uğurla tətbiq olunmalıdır.
- Təkrar icra sxemi və məlumatı dəyişməməlidir.
- Dəyişdirilmiş migration checksum xətası ilə dayandırılmalıdır.
- Replay indeksi SQLite metadata-sında təsdiqlənməlidir.
- Migration zamanı sintetik tick sətirlərinin sayı və məzmunu qorunmalıdır.
- Mövcud backend testləri keçməlidir.

## Sonrakı addım

Migration və indeks qəbul edildikdən sonra deterministik replay sessiyasının
skeleti yaradılacaq.
