# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 1

## Tapşırıq

MT5 disk növbəsi və retry davranışı üçün avtomatlaşdırılmış qəbul testini
hazırlamaq və nəticəni qəbul sübutu kimi qeyd etmək.

## Yoxlanacaq davranışlar

- FIFO sırası qorunmalıdır.
- Növbə faylı və checkpoint restart simulyasiyasından sonra bərpa olunmalıdır.
- Yalnız `Peek` edilmiş ilk event təsdiqlənib silinməlidir.
- Tutum həddi keçildikdə event qəbul edilməməli və rejection metriyi artmalıdır.
- Rejection metriyi yenidən initialize edildikdən sonra qorunmalıdır.
- Korlanmış növbə faylı aşkar edilməlidir.

## Tamamlanma meyarları

- MQL5 test mənbəyi `0 errors, 0 warnings` ilə kompilyasiya edilməlidir.
- Test real queue fayllarına toxunmamaq üçün unikal test açarı istifadə etməlidir.
- Bütün avtomatik assertion-lar keçməlidir.
- Test yaratdığı müvəqqəti queue, checkpoint və metrics fayllarını təmizləməlidir.

## Sonrakı addım

Avtomatlaşdırılmış queue testi keçərsə Azərbaycan dilindəki köhnə sənədlərin
UTF-8 kodlaşdırması düzəldiləcək. Rəsmi 24 saatlıq canlı sınaq bazar açıldıqdan
sonra yenidən başladılacaq.
