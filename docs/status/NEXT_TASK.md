# ESAS Platform — Növbəti tapşırıq

Status: READY  
Prioritet: HIGH  
Mərhələ: Phase 1

## Tapşırıq

1 saatlıq fasiləsiz canlı sabitlik sınağını aparmaq və nəticəni qəbul sübutu kimi
qeyd etmək.

## Başlanğıc göstəriciləri

Sınağın başlanğıcında aşağıdakılar qeyd edilməlidir:

- backend `/health` vəziyyəti;
- operational ümumi status;
- ümumi tick sayı;
- disk növbəsinin sayı və tutumu;
- rədd edilmiş event sayı;
- məlumat itkisi təsdiqinin vəziyyəti;
- SQLite `quick_check` nəticəsi.

## Sınaq zamanı

- MT5 və Algo Trading aktiv qalmalıdır.
- Backend və frontend işləməlidir.
- Sistem bilərəkdən dayandırılmamalıdır.
- Paneldə yeni qırmızı xəbərdarlıq yaranarsa vaxtı qeyd edilməlidir.

## Tamamlanma meyarları

- Tick sayı artmalıdır.
- Tick axını `active` qalmalıdır.
- Disk növbəsi sınağın sonunda `0 / 1000` olmalıdır.
- Rədd edilmiş event sayı `7343`-dən yuxarı qalxmamalıdır.
- Audit təsdiqi qorunmalıdır.
- Backend `/health=ok` və SQLite `quick_check=ok` olmalıdır.
- Backend və frontend testləri keçməlidir.

## Sonrakı addım

1 saatlıq sınaq keçərsə 8–12 saatlıq sabitlik sınağı planlaşdırılacaq.
