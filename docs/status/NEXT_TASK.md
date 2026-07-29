# ESAS Platform — Növbəti Tapşırıq

Status: READY  
Prioritet: HIGH  
Mərhələ: Phase 1

## Tapşırıq

MT5 yaddaş buferində saxlanmış tick event-lərinin backend yenidən əlçatan olduqda avtomatik göndərilməsi.

## Problem

Hazırda HTTP göndərişi uğursuz olduqda tick event-i `EsasTickBuffer` daxilində saxlanılır.

Lakin sistem:

- buferdəki event-i yenidən göndərmir;
- backend-in bərpa olunduğunu istifadə etmir;
- uğurla göndərilmiş event-i buferdən silmir;
- köhnə və yeni event-lərin ardıcıllığını idarə etmir.

Bu səbəbdən hazırkı bufer məlumatı yalnız müvəqqəti saxlayır, lakin çatdırılmanı təmin etmir.

## Məqsəd

Backend müvəqqəti dayandıqda event-ləri yaddaş buferində toplamaq və backend bərpa olunduqda onları FIFO ardıcıllığı ilə göndərmək.

## Təsir edəcək əsas fayllar

- `mt5/bridge/include/EsasTickBuffer.mqh`
- `mt5/bridge/include/EsasHttpTransport.mqh`
- `mt5/bridge/src/ESAS_MT5_Bridge.mq5`
- `mt5/bridge/README.md`
- `mt5/bridge/module.json`
- `docs/status/CURRENT_STATE.md`
- `CHANGELOG.md`

## Funksional tələblər

1. Bufer boş deyilsə ən köhnə event əvvəl göndərilməlidir.
2. Event yalnız uğurlu HTTP cavabından sonra buferdən silinməlidir.
3. Göndəriş uğursuz olarsa event buferdə qalmalıdır.
4. Retry prosesi sonsuz və sürətli dövrə yaratmamalıdır.
5. Köhnə event-lərin zaman ardıcıllığı qorunmalıdır.
6. Bufer sayı və göndəriş nəticəsi loglanmalıdır.
7. Bufer dolduqda məlumat itkisi açıq şəkildə loglanmalıdır.
8. Yeni tick-lərin işlənməsi tam bloklanmamalıdır.
9. Event müqaviləsi dəyişdirilməməlidir.
10. Backend-də təkrar event qoruması saxlanmalıdır.

## Təhlükəsizlik qaydaları

- Real ticarət funksiyası əlavə edilməməlidir.
- Event məlumatı dəyişdirilməməlidir.
- Uğursuz event səssiz şəkildə silinməməlidir.
- Mövcud istifadəçi dəyişiklikləri qorunmalıdır.
- Dəyişiklikdən əvvəl Git statusu yoxlanmalıdır.

## Yoxlama ssenarisi

1. Backend-i işə sal.
2. MT5 tick göndərişini aktiv et.
3. Tick-lərin bazaya çatdığını təsdiqlə.
4. Backend-i dayandır.
5. Tick-lərin buferə əlavə olunduğunu təsdiqlə.
6. Backend-i yenidən işə sal.
7. Buferdəki event-lərin ardıcıllıqla göndərildiyini təsdiqlə.
8. Bufer sayının sıfıra düşdüyünü təsdiqlə.
9. Bazada təkrar `event_id` yaranmadığını yoxla.
10. Yeni tick-lərin göndərilməyə davam etdiyini yoxla.

## Tamamlanma meyarları

Tapşırıq yalnız aşağıdakı hallarda tamamlanmış hesab ediləcək:

- backend kəsilməsi zamanı event-lər buferdə qalır;
- backend bərpa olduqda event-lər avtomatik göndərilir;
- uğurlu event buferdən silinir;
- uğursuz event buferdə saxlanılır;
- FIFO ardıcıllığı qorunur;
- məlumat itkisi səssiz baş vermir;
- mövcud backend testləri keçir;
- MT5 Bridge uğurla kompilyasiya olunur;
- README və status sənədləri yenilənir.

## Planlaşdırılan commit

```text
Implement buffered tick retry delivery
```