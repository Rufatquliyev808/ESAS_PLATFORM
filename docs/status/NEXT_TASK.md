# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Xam tick məlumatını dəyişdirmədən oxuyan repository interfeysini və deterministik
`event_timestamp + event_id` sıralama testlərini yaratmaq.

## Sərhədlər

- Repository yalnız oxuma əməliyyatları təqdim etməlidir.
- Xam `tick_events` sətirləri dəyişdirilə və silinə bilməz.
- Zaman aralığı `[start_at, end_at)` formasında sabit olmalıdır.
- Sıralama `event_timestamp`, sonra `event_id` ilə deterministik olmalıdır.
- Böyük nəticələr cursor və limit ilə səhifələnməlidir.
- Phase 1 canlı tick qəbulu və mövcud API davranışı dəyişməməlidir.

## Tamamlanma meyarları

- Eyni giriş iki icrada eyni event ardıcıllığını qaytarmalıdır.
- Eyni timestamp-li event-lər `event_id` ilə sabit sıralanmalıdır.
- Boş aralıq təhlükəsiz boş nəticə qaytarmalıdır.
- Yanlış zaman aralığı və limitlər aydın validation xətası verməlidir.
- Test xam tick sətirlərinin və sayının dəyişmədiyini təsdiqləməlidir.
- Mövcud backend testləri keçməlidir.

## Sonrakı addım

Repository sərhədi qəbul edildikdən sonra deterministik replay sessiyasının
skeleti yaradılacaq.
