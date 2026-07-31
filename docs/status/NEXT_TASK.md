# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 1

## Tapşırıq

Bazar açıldıqda Phase 1 üçün 24 saatlıq fasiləsiz canlı sabitlik sınağını yenidən
başlatmaq və yekun qəbul sübutunu toplamaq.

## Başlanğıc göstəriciləri

- `tools/phase1-acceptance-snapshot.ps1` ilə başlanğıc JSON sübutu;
- backend `/health` və operational status;
- ümumi tick sayı və tick axınının vəziyyəti;
- disk növbəsinin sayı və tutumu;
- rejection sayı və məlumat itkisi təsdiqi;
- SQLite `quick_check` və audit sətri;
- bazarın açıq olduğunun təsdiqi.

## Tamamlanma meyarları

- Avtomatik müqayisə minimum `24` saat keçdiyini təsdiqləməlidir.
- Tick sayı 24 saat ərzində artmalıdır və axın `active` qalmalıdır.
- Disk növbəsi sonda `0 / 1000` olmalıdır.
- Rejection sayı `7343`-dən yuxarı qalxmamalıdır.
- SQLite `quick_check=ok` və audit təsdiqi qorunmalıdır.
- Backend, frontend və MQL5 qəbul yoxlamaları yenidən keçməlidir.

## Sonrakı addım

24 saatlıq sınaq keçərsə Phase 1 statusu yekun review üçün hazırlanacaq.
