# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 1

## Tapşırıq

24 saatlıq fasiləsiz canlı sabitlik sınağını aparmaq və nəticəni qəbul sübutu
kimi qeyd etmək.

## Başlanğıc göstəriciləri

Sınağın başlanğıcında aşağıdakılar qeyd edilməlidir:

- backend `/health` vəziyyəti;
- operational ümumi status;
- ümumi tick sayı;
- disk növbəsinin sayı və tutumu;
- rədd edilmiş event sayı;
- məlumat itkisi təsdiqinin vəziyyəti;
- SQLite `quick_check` nəticəsi.

## Tamamlanma meyarları

- Tick sayı artmalıdır.
- Tick axını `active` qalmalıdır.
- Disk növbəsi sınağın sonunda `0 / 1000` olmalıdır.
- Rədd edilmiş event sayı `7343`-dən yuxarı qalxmamalıdır.
- Audit təsdiqi qorunmalıdır.
- Backend `/health=ok` və SQLite `quick_check=ok` olmalıdır.
- Backend və frontend testləri keçməlidir.

## Sonrakı addım

24 saatlıq sınaq keçərsə yekun məlumat itkisi hesabatı hazırlanacaq.
