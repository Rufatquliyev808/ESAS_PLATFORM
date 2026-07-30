# ESAS Platform — Növbəti Tapşırıq

Status: READY  
Prioritet: HIGH  
Mərhələ: Phase 1

## Tapşırıq

Disk növbəsi limitə çatdıqda qəbul edilməyən event-ləri ölçmək və bu vəziyyəti
backend monitorinqində görünən etmək.

## Problem

Canlı davamlılıq sınağında backend uzun müddət bağlı qaldığı üçün disk növbəsi
konfiqurasiya edilmiş `1000` event limitinə çatdı. Növbədəki mövcud event-lər
qorundu, lakin limitdən sonra gələn yeni event-lər saxlanıla bilmədi.

Bridge hazırda uğursuz `Enqueue` nəticəsini loglayır, amma:

- sessiya üzrə qəbul edilməyən event sayını saxlamır;
- son növbə xətasının səbəbini ayrıca göstərmir;
- backend operational endpoint bu problemi göstərmir;
- frontend üçün hazır monitorinq göstəricisi yoxdur.

## Məqsəd

Səssiz məlumat itkisini aradan qaldırmaq və resurs limiti səbəbindən qəbul
edilməyən hər event-i ölçülə bilən operational problemə çevirmək.

## Plan

1. Queue əməliyyat nəticələri üçün aydın xəta kodları müəyyən etmək.
2. `queue_full`, `disk_write_failed` və `corrupt_queue` hallarını ayırmaq.
3. Bridge daxilində sessiya üzrə qəbul edilməyən event sayğacı yaratmaq.
4. Operational vəziyyəti backend-ə ötürmək üçün minimal status müqaviləsi
   hazırlamaq.
5. Backend status endpoint-inə queue vəziyyəti və itki sayğaclarını əlavə etmək.
6. Limit sınağı və backend testləri əlavə etmək.

## Təhlükəsizlik qaydaları

- Köhnə event növbədən avtomatik silinməməlidir.
- Növbə dolduqda köhnə məlumatın üzərinə yazılmamalıdır.
- Sayğac sıfırlanması məlumat itkisini gizlətməməlidir.
- Event müqaviləsi dəyişdirilməməlidir.
- Real ticarət funksiyası əlavə edilməməlidir.

## Tamamlanma meyarları

- Növbə dolması ayrıca səbəb kimi müəyyən edilir.
- Qəbul edilməyən event sayı hesablanır.
- Operational API problemi göstərir.
- Limitə çatma testi mövcuddur.
- Mövcud tick axını və idempotency testləri keçir.
- MT5 kompilyasiyası `0 errors, 0 warnings` nəticəsi verir.

## Planlaşdırılan ilk commit

```text
Expose persistent queue health metrics
```
