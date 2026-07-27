# ESAS Platform — Phase 1 Status

Version: 1.0

Status: IN PROGRESS

Last Updated: 2026-07-27

---

## Main Objective

ESAS Platform-un əsas məqsədi bazarın statistik davranışını öyrənmək və toplanmış məlumatlardan sübut edilmiş strategiyalar yaratmaqdır.

Gələcəkdə platforma müstəqil şəkildə işləyən aşağıdakı mənbələri birləşdirəcək:

- statistik analiz;
- texniki analiz;
- Visual AI;
- fundamental və xəbər analizi;
- risk idarəetməsi;
- qərar və icra modulları.

Heç bir modul digər modulun koduna qarışmamalı və ya onu bloklamamalıdır.

---

## Phase 1 Objective

Phase 1-in məqsədi etibarlı və yoxlanılan bazar məlumatı axını yaratmaqdır.

Hazırkı axın:

```text
MT5 Tick
    ↓
ESAS MT5 Bridge
    ↓
TICK_RECEIVED Event
    ↓
HTTP
    ↓
FastAPI Validation
    ↓
SQLite Storage
    ↓
Tick Statistics

## Operational Monitoring Validation

Date: 2026-07-27

Operational status endpoint successfully detected both states:

- ACTIVE: live MT5 ticks were reaching the backend.
- STALE: tick transmission was stopped and the 30-second threshold was exceeded.

Validated endpoint:

`GET /status/operational`

Observed stored tick count during validation: 172.

Result: PASSED