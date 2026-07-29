# ESAS Platform — Növbəti Tapşırıq

Status: READY  
Prioritet: HIGH  
Mərhələ: Phase 1

## Tapşırıq

MT5 və ya Expert Advisor bağlandıqda gözləyən event-lərin itməməsi üçün disk əsaslı davamlı event növbəsini layihələndirmək.

## Problem

Hazırkı FIFO bufer RAM daxilində işləyir.

Bufer:

- müvəqqəti backend kəsilməsini idarə edir;
- backend bərpa olduqda event-ləri batch şəklində göndərir;
- MT5 və ya Expert Advisor bağlandıqda bütün gözləyən event-ləri itirir.

Bu, məlumat bütövlüyü prinsipinə uyğun deyil.

## Məqsəd

Göndərilməmiş event-ləri lokal diskdə qorumaq və MT5 yenidən başladıqda onları bərpa edərək FIFO ardıcıllığı ilə backend-ə göndərmək.

## İlkin araşdırma mövzuları

1. Fayl əsaslı növbə və SQLite əsaslı növbənin müqayisəsi.
2. MQL5 daxilində təhlükəsiz fayl yazma imkanları.
3. Yarımçıq yazılmış event-in aşkarlanması.
4. Event-in yalnız uğurlu HTTP cavabından sonra diskdən silinməsi.
5. MT5 yenidən başladıqda növbənin bərpası.
6. Maksimum disk istifadəsi və limit siyasəti.
7. Fayl korlanması zamanı bərpa qaydası.
8. FIFO ardıcıllığının qorunması.
9. Təkrar event riskinin backend idempotency ilə idarə olunması.
10. Disk yazma performansının tick axınına təsiri.

## Təhlükəsizlik qaydaları

- Event məlumatı dəyişdirilməməlidir.
- Uğursuz event səssiz şəkildə silinməməlidir.
- Disk faylı korlandıqda mövcud məlumat qorunmalıdır.
- Real ticarət funksiyası əlavə edilməməlidir.
- Event müqaviləsi dəyişdirilməməlidir.
- Koddan əvvəl ayrıca dizayn qərarı sənədi hazırlanmalıdır.

## İlk addım

`docs/decisions/` daxilində disk növbəsi üçün Architecture Decision Record hazırlamaq.

Qərar sənədində aşağıdakılar olmalıdır:

- problem;
- tələblər;
- alternativlər;
- fayl əsaslı həll;
- SQLite əsaslı həll;
- üstünlük və risklər;
- seçilən yanaşma;
- qəbul meyarları.

## Tamamlanma meyarları

- Disk növbəsinin dizaynı sənədləşdirilir.
- Seçilmiş yanaşmanın səbəbi izah edilir.
- Məlumat itkisi və bərpa ssenariləri müəyyən edilir.
- Kodlaşdırmaya başlamazdan əvvəl təhlükəsizlik riskləri qiymətləndirilir.
- Qərar konstitusiya və arxitektura prinsiplərinə uyğun olur.

## Planlaşdırılan ilk commit

```text
Document persistent event queue design
```
