# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Replay sessiyası yaratmaq üçün qorunan `POST /api/v2/replay-sessions` endpoint-ini
hazırlamaq.

## Sərhədlər

- Sorğu `symbol`, `[start_at, end_at)` intervalı və `step|max_speed` rejimini qəbul
  etməlidir.
- Mövcud dashboard autentifikasiyası qorunmalı, yaradıcı istifadəçi auditə
  yazılmalı və etibarsız giriş fail-closed rədd edilməlidir.
- Snapshot, sessiya və ilkin append-only audit mövcud repository transaction-u ilə
  atomik yaradılmalıdır.
- Xam tick-lər dəyişdirilməməli və canlı bazada test məlumatı yaradılmamalıdır.

## Tamamlanma meyarları

- Uğurlu sorğu yeni sessiya ID-si, state və snapshot metadatasını qaytarır.
- Boş dataset təhlükəsiz `completed`, məlumatlı dataset `created` olur.
- Yanlış interval, rejim və sahələr təhlükəsiz rədd edilir.
- API testi sessiya/audit atomikliyini və xam məlumat dəyişməzliyini təsdiqləyir.
- Tam backend regressiyası keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

Yaratma endpoint-indən sonra replay lifecycle command API-si ownership,
idempotency və optimistic state nəzarəti ilə əlavə ediləcək.
