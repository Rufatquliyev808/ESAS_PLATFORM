# ESAS Platform — Növbəti tapşırıq

Status: READY  
Prioritet: HIGH  
Mərhələ: Phase 1

## Tapşırıq

Phase 1 monitorinq panelini real MT5 axını ilə qəbul sınağından keçirmək və
frontend-i GitHub Actions test axınına daxil etmək.

## Hazır vəziyyət

- Azərbaycan dilində monitorinq paneli yaradılıb.
- Panel yalnız backend API-lərindən məlumat alır.
- Tick, Bridge, disk növbəsi və rədd edilən event vəziyyətləri göstərilir.
- Məlumat hər 5 saniyədə yenilənir.
- Müvəqqəti API xətasında son uğurlu məlumat qorunur.
- Backend üçün lokal frontend CORS icazələri əlavə edilib.
- Frontend lint, build və render testi lokal olaraq keçir.

## Növbəti addımlar

1. Paneldə tarixi `7343` rədd edilmiş event hadisəsini istifadəçi təsdiqi ilə canlı
   qəbul sınağından keçirmək.
2. Təsdiqdən sonra ümumi statusun sağlam, itki kartının isə audit izi ilə
   `Təsdiqlənib` göstərildiyini yoxlamaq.
3. Uzunmüddətli sabitlik sınağı aparmaq.
4. GitHub Actions nəticələrini təsdiqləmək.

## Tamamlanma meyarları

- Panel real API məlumatlarını düzgün göstərir.
- Backend kəsilməsi zamanı son uğurlu göstəricilər itmir.
- Desktop və mobil ölçüdə ekran istifadəyə yararlıdır.
- Backend və frontend testləri GitHub-da keçir.

## Təhlükəsizlik sərhədi

Panel yalnız oxuma və monitorinq üçündür. Ticarət əməliyyatı, siqnal, proqnoz və
birbaşa verilənlər bazası bağlantısı daxil deyil.
