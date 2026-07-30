# ESAS Platform — Növbəti Tapşırıq

Status: READY  
Prioritet: HIGH  
Mərhələ: Phase 1

## Tapşırıq

Phase 1 frontend monitorinq panelinin API və UI spesifikasiyasını hazırlamaq.

## Problem

`frontend` qovluğu mövcuddur, lakin panelin göstərəcəyi məlumatlar, ekran
quruluşu və operational statusların istifadəçiyə necə izah ediləcəyi
sənədləşdirilməyib.

## Məqsəd

Kod yazmazdan əvvəl sadə, Azərbaycan dilində və texniki olmayan Phase 1
monitorinq panelinin dəqiq spesifikasiyasını hazırlamaq.

## Plan

1. İstifadəçinin ilk baxışda cavab almalı olduğu sualları müəyyən etmək.
2. `GET /status/operational` və `GET /statistics/ticks` məlumatlarını xəritələmək.
3. `active`, `stale`, `waiting`, `healthy`, `degraded` və `full` vəziyyətləri
   üçün Azərbaycan dilində izah və rəng qaydaları yazmaq.
4. Desktop əsaslı sadə ekran quruluşunu müəyyən etmək.
5. API əlçatmaz olduqda göstəriləcək vəziyyəti müəyyən etmək.
6. Yenilənmə intervalı və son yenilənmə vaxtını müəyyən etmək.
7. Spesifikasiyanı `docs/frontend/` daxilində saxlamaq.

## Təhlükəsizlik qaydaları

- Frontend birbaşa SQLite bazasına qoşulmamalıdır.
- Frontend yalnız backend API istifadə etməlidir.
- Panel ticarət qərarı və ya siqnal verməməlidir.
- Texniki xəta kodları istifadəçiyə izahsız göstərilməməlidir.
- Məlumat itkisi və degraded vəziyyət yaşıl göstərilməməlidir.

## Tamamlanma meyarları

- Panelin bütün bölmələri və məlumat mənbələri sənədləşdirilir.
- Status rəngləri və Azərbaycan dilində mətnlər müəyyən edilir.
- API xətası və stale vəziyyəti fərqli göstərilir.
- Responsive desktop/tablet quruluşu təsvir edilir.
- Kodlaşdırmaya başlamaq üçün qəbul meyarları aydın olur.

## Planlaşdırılan ilk commit

```text
Document Phase 1 monitoring dashboard
```
