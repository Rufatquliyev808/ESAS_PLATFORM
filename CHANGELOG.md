# ESAS Platform — Dəyişiklik Tarixçəsi

Bu fayl ESAS Platform-da edilən əsas dəyişiklikləri izləyir.

Format Semantic Versioning prinsipinə əsaslanır:

`MAJOR.MINOR.PATCH`

## Unreleased

### Added

- MT5 Bridge `1.5.0` üçün davamlı rejected-event sayğacı.
- `queue_full`, serializasiya, disk və corruption xəta kateqoriyaları.
- `POST /status/bridge` operational status qəbulu.
- `GET /status/operational` daxilində `bridge_delivery` göstəriciləri.
- Bridge queue statusu üçün backend validation və API testləri.
- Backend testləri üçün hər testə məxsus müvəqqəti SQLite bazası.
- Test bazasının canlı `ESAS_PLATFORM.sqlite` faylından tam ayrılması.
- Push və pull request-lər üçün GitHub Actions backend test workflow-u.
- CI daxilində module manifest və Python source validation.
- MT5 Bridge `1.4.0` üçün disk əsaslı davamlı FIFO event növbəsi.
- Restart zamanı pending event-lərin bərpası.
- Uzunluq prefiksli ikili jurnal və davamlı acknowledgement checkpoint-i.
- Queue dizaynı üçün `ADR-0001`.
- Canlı backend outage, EA restart və recovery sınağı.
- Layihənin davamlı yaddaş sistemi.
- Codex üçün daimi `AGENTS.md` iş qaydaları.
- Cari vəziyyət üçün `docs/status/CURRENT_STATE.md`.
- Növbəti tapşırıq üçün `docs/status/NEXT_TASK.md`.
- Layihə dəyişikliklərini izləmək üçün `CHANGELOG.md`.
- MT5 Bridge üçün timer əsaslı FIFO retry mexanizmi.
- Konfiqurasiya olunan retry intervalı.
- Konfiqurasiya olunan batch göndəriş ölçüsü.
- Backend bərpa olduqda buferin avtomatik boşaldılması.
- Retry və batch nəticələri üçün operational log mesajları.

### Planned

- `PROJECT_ROADMAP.md` yol xəritəsinin hazırlanması.
- Azərbaycan dilindəki sənədlərin kodlaşdırmasının düzəldilməsi.
- MT5 buferindəki event-lərin avtomatik təkrar göndərilməsi.
- Disk əsaslı davamlı event növbəsi.
- Backend monitorinq göstəricilərinin genişləndirilməsi.
- Phase 1 frontend monitorinq paneli.
- Uzunmüddətli sabitlik sınağı.

## Backend 0.1.0 — 2026-07-27

### Added

- FastAPI tətbiqinin ilkin versiyası.
- `GET /health` endpoint-i.
- `POST /events/ticks` endpoint-i.
- `GET /statistics/ticks` endpoint-i.
- `GET /status/operational` endpoint-i.
- Pydantic vasitəsilə `TICK_RECEIVED` event yoxlaması.
- SQLite verilənlər bazasının avtomatik yaradılması.
- Tick event-lərinin saxlanması.
- Eyni `event_id` üçün idempotent yazma.
- Tick statistikalarının hesablanması.
- `waiting`, `active` və `stale` operational statusları.
- Backend API testləri.

### Validated

- Canlı MT5 tick-lərinin backend-ə çatması.
- Tick-lərin SQLite bazasında saxlanması.
- `active` axın vəziyyəti.
- 30 saniyədən sonra `stale` axın vəziyyəti.
- Sınaq zamanı 172 saxlanmış tick.

## ESAS MT5 Bridge 0.2.0 — 2026-07-27

### Added

- MT5-dən canlı tick məlumatının oxunması.
- Standart `TICK_RECEIVED` event yaradılması.
- Event ID yaradılması.
- UTC timestamp yaradılması.
- JSON serializasiyası.
- HTTP POST transportu.
- Backend endpoint konfiqurasiyası.
- Strategy Tester daxilində HTTP məhdudiyyəti xəbərdarlığı.
- Uğursuz event-lər üçün ilkin FIFO yaddaş buferi.

### Known limitations

- HTTP göndərişi hər tick üçün sinxron icra olunur.
- Buferdə saxlanmış event-lər avtomatik təkrar göndərilmir.
- RAM buferi MT5 bağlandıqda itir.
- Bufer dolması siyasəti tam müəyyən edilməyib.
- Modul versiyası bütün fayllarda uyğunlaşdırılmayıb.
