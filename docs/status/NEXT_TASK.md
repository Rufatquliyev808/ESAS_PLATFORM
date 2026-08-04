# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Replay keyfiyyət hesabatını qorunan public v2 contract-a çıxarmaq:
`GET /api/v2/replay-sessions/{session_id}/quality-report`.

## Sərhədlər

- Yalnız sessiyanın sahibi hesabatı oxuya bilməlidir.
- Hesabat yalnız tamamlanmış replay üçün təqdim edilməlidir.
- Mövcud deterministik report ID və fingerprint dəyişdirilməməlidir.
- Daxili endpoint geriyə uyğun saxlanmalı, public cavab versiyalanmalıdır.
- Xam tick-lər dəyişdirilməməli və testlər yalnız müvəqqəti bazada işləməlidir.

## Tamamlanma meyarları

- Authentication, ownership, incomplete state və not-found sərhədləri test olunur.
- Public cavab stabil `data` və `meta.api_version=2` contract-ı qaytarır.
- Eyni replay üçün hesabat reproduksiya olunur.
- Tam backend regressiyası keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

Public keyfiyyət hesabatından sonra Phase 2 replay idarəetmə frontend-i hazırlanacaq.
