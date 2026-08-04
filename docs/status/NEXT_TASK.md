# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Replay sessiyası üçün qanuni vəziyyət keçidlərini modelləşdirmək və hər keçidi
uyğun checkpoint/progress məlumatı ilə append-only auditə atomik yazmaq.

## Sərhədlər

- Yalnız müqavilədə icazə verilən state keçidləri qəbul edilməlidir.
- Terminal `completed|cancelled|failed` vəziyyətindən keçid rədd edilməlidir.
- Progress geriyə gedə və dataset tick sayını keçə bilməz.
- Checkpoint və `processed_ticks` uyğun audit sətri ilə eyni transaction-da yazılmalıdır.
- Gözlənilməyən cari vəziyyət optimistic conflict kimi rədd edilməlidir.
- Audit və ya session update xətasında bütün keçid rollback edilməlidir.
- Hələ worker, API, frontend və canlı migration əlavə edilməməlidir.

## Tamamlanma meyarları

- Bütün qanuni və qanunsuz vəziyyət keçidləri unit testlərlə örtülməlidir.
- Hər uğurlu keçid dəqiq bir audit sətri yaratmalıdır.
- Qanunsuz keçid sessiya və audit sayını dəyişməməlidir.
- Checkpoint yalnız tam uğurlu transaction-dan sonra irəliləməlidir.
- Eyni expected state ilə yarışan ikinci yazı conflict almalıdır.
- Immutable sessiya giriş və snapshot sahələri dəyişməməlidir.
- Mövcud backend testləri keçməlidir.

## Sonrakı addım

Vəziyyət keçidləri qəbul edildikdən sonra `step` rejiminin limitli tick batch emalı
və idempotency sərhədi hazırlanacaq.
