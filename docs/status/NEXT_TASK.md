# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Replay sessiyasının event axınını qorunan, yalnız oxuma üçün
`GET /api/v2/replay-sessions/{session_id}/events` endpoint-i ilə təqdim etmək.

## Sərhədlər

- Yalnız sessiyanı yaradan istifadəçi event axınını oxuya bilməlidir.
- Sıralama `(event_timestamp, event_id)` üzrə deterministik olmalıdır.
- Cursor imzalanmış, istifadəçiyə və sessiyaya bağlı, vaxtı məhdud olmalıdır.
- Səhifələmə sessiyanın sabit snapshot sərhədini aşmamalı, təkrar və boşluq
  yaratmamalıdır.
- Xam tick-lər dəyişdirilməməli və canlı bazada test məlumatı yaradılmamalıdır.

## Tamamlanma meyarları

- Event səhifəsi deterministik sıra, limit və növbəti cursor qaytarır.
- Authentication, ownership, cursor saxtalaşdırılması və cursor expiry testlərlə
  təsdiqlənir.
- Səhifələr arasında dublikat və itki olmur.
- Tam backend regressiyası keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

Event API-dən sonra replay keyfiyyət hesabatı public v2 contract-a çıxarılacaq.
