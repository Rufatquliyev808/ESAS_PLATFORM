# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Replay sessiyası və append-only audit sxemini `0002` migration-u ilə yaratmaq və
yalnız müvəqqəti test bazasında constraint/trigger davranışını təsdiqləmək.

## Sərhədlər

- `replay_sessions` müqavilədəki vəziyyət, interval, progress və checkpoint
  constraint-lərini tətbiq etməlidir.
- `replay_session_audit` sessiyaya foreign key ilə bağlanmalıdır.
- Audit `UPDATE` və `DELETE` əməliyyatları trigger ilə bloklanmalıdır.
- Migration transaction, checksum və təkrar icra qaydalarını qorumalıdır.
- Testlər yalnız müvəqqəti SQLite bazası istifadə etməlidir.
- Xam tick və loss acknowledgement məlumatına toxunulmamalıdır.
- Hələ repository yazıları, worker, API, frontend və canlı migration olmamalıdır.

## Tamamlanma meyarları

- Təzə test bazasında `0001` və `0002` ardıcıllıqla tətbiq olunmalıdır.
- Sessiya vəziyyəti, rejim, vaxt və progress constraint-ləri yanlış sətri rədd etməlidir.
- Audit sətri əlavə edilə, lakin yenilənə və silinə bilməməlidir.
- Foreign key mövcud olmayan sessiya auditini rədd etməlidir.
- Təkrar migration icrası no-op olmalı və checksum qorunmalıdır.
- Mövcud backend testləri keçməlidir.

## Sonrakı addım

Sxem qəbul edildikdən sonra replay sessiyası yaratma repository-si və atomik ilkin
audit yazısı hazırlanacaq.
