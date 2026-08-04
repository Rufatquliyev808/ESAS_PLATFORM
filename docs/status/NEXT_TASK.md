# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Replay sessiyasının lifecycle əmrləri üçün qorunan
`POST /api/v2/replay-sessions/{session_id}/commands` endpoint-ini hazırlamaq.

## Sərhədlər

- Sorğu `start`, `step`, `pause`, `resume` və `cancel` əmrlərini yalnız sessiyanın
  qanuni cari vəziyyətində qəbul etməlidir.
- Mövcud dashboard autentifikasiyası qorunmalı və dəyişdirici əməliyyat yalnız
  sessiyanı yaradan istifadəçiyə aid olmalıdır.
- `Idempotency-Key` və `expected_state_version` tələb olunmalı; təkrar eyni əmr
  əvvəlki nəticəni qaytarmalı, fərqli payload və köhnə state fail-closed `409`
  almalıdır.
- Sessiya vəziyyəti, progress/checkpoint, idempotency qeydi və append-only audit
  mövcud repository transaction sərhədində atomik saxlanmalıdır.
- Xam tick-lər dəyişdirilməməli və canlı bazada test məlumatı yaradılmamalıdır.

## Tamamlanma meyarları

- Uğurlu əmr yeni state, progress və checkpoint metadatasını qaytarır.
- Ownership, authentication, idempotency və optimistic conflict sərhədləri API
  testləri ilə təsdiqlənir.
- Qanunsuz keçid, mövcud olmayan sessiya, naməlum əmr və sahələr təhlükəsiz rədd
  edilir; qismən yazı yaranmır.
- API testi session/audit/idempotency atomikliyini və xam məlumat dəyişməzliyini
  təsdiqləyir.
- Tam backend regressiyası keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

Lifecycle command endpoint-indən sonra replay event axını imzalanmış cursor və
snapshot sərhədi ilə yalnız oxuma üçün API-yə çıxarılacaq.
