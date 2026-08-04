# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

İlk streaming məlumat keyfiyyəti tapıntılarını replay sessiyası ilə bağlı yekun
hesabata çevirmək və `pass`, `review`, `fail` keyfiyyət statusunu hesablamaq.

## Sərhədlər

- Hesabat yalnız tamamlanmış və dataset-i yenidən təsdiqlənmiş replay sessiyasından
  yaradılmalıdır.
- `critical` tapıntı `fail`, yalnız `warning` tapıntı `review`, qalan hal `pass`
  statusu verməlidir.
- Hesabat replay manifesti, qayda versiyası, ümumi tick və səviyyə saylarını daşımalıdır.
- Eyni sessiya və qaydalar üçün deterministik məzmun fingerprint-i yaranmalıdır.
- Tapıntı nümunələri məhdud qalmalı və bütün dataset yaddaşa yüklənməməlidir.
- Xam tick-lər dəyişdirilməməli; API, frontend və canlı migration hələ əlavə edilməməlidir.

## Tamamlanma meyarları

- `pass`, `review` və `fail` statusları ayrıca test edilir.
- Natamam və sonradan dəyişmiş datasetli sessiya fail-closed rədd edilir.
- Fərqli batch ölçüləri eyni hesabat fingerprint-i verir.
- Replay manifesti və keyfiyyət xülasəsi bir nəticədə bağlanır.
- Mövcud backend testləri keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

Hesabat qatı qəbul edildikdən sonra qalan `DQ-003`, `DQ-005..010` qaydaları mərhələli
şəkildə analizatora əlavə ediləcək.
