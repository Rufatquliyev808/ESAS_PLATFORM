# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Phase 2 məlumat keyfiyyəti qatının ilk deterministik qaydalarını hazırlamaq:
zaman boşluğu, geriyə gedən timestamp və dublikat aşkarlanması.

## Sərhədlər

- Qaydalar versiyalanmış olmalı və eyni dataset üçün eyni nəticəni verməlidir.
- Zaman boşluğu həddi simvol və müşahidə kontekstinə açıq parametr kimi bağlanmalıdır.
- Geriyə gedən timestamp mənbə vaxtı ilə qəbul vaxtını qarışdırmadan aşkarlanmalıdır.
- Dublikat anlayışı `event_id` dublikatından və eyni payload namizədindən ayrılmalıdır.
- Hər tapıntı səbəb, mövqe və qayda versiyası ilə izah edilə bilməlidir.
- Hesablama bütün dataset-i yaddaşa yükləməməlidir.
- Xam tick-lər dəyişdirilməməli; API, frontend və canlı migration hələ əlavə edilməməlidir.

## Tamamlanma meyarları

- Boşluq, geriyə timestamp və dublikat üçün sərhəd testləri keçir.
- Eyni timestamp-li qanuni tick-lər səhvən problem sayılmır.
- Fərqli batch ölçüləri eyni keyfiyyət tapıntılarını verir.
- Tapıntılar deterministik sıra və stabil identifikatorla qaytarılır.
- Analiz bütün dataset-i yaddaşa yükləmir.
- Mövcud backend testləri keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

İlk keyfiyyət qaydaları qəbul edildikdən sonra nəticə hesabatı replay sessiyası ilə
əlaqələndiriləcək və keyfiyyət qapısının ilkin status modeli hazırlanacaq.
