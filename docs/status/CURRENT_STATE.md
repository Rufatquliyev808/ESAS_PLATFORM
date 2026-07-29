# ESAS Platform — Cari Vəziyyət

Son yenilənmə: 2026-07-29  
Cari mərhələ: Phase 1  
Status: IN PROGRESS  
Əsas budaq: `main`

## Layihənin məqsədi

ESAS Platform bazar məlumatlarını toplayan, qoruyan, analiz edən və statistik olaraq sübut edilmiş nəticələr əsasında gələcəkdə qərar verə bilən modul platformadır.

Platforma əvvəlcədən seçilmiş strategiyanı sübut etməyə çalışmır. Strategiyalar müşahidə, toplanmış məlumat və statistik yoxlama nəticəsində yaranmalıdır.

## Cari Phase 1 məqsədi

Etibarlı və yoxlanıla bilən tick məlumatı axını yaratmaq:

```text
MT5 Tick
→ ESAS MT5 Bridge
→ TICK_RECEIVED Event
→ HTTP
→ FastAPI Validation
→ SQLite Storage
→ Tick Statistics
→ Operational Monitoring
```

## Tamamlanmış işlər

- Platformanın konstitusiya sənədləri yaradılıb.
- Ümumi arxitektura hazırlanıb.
- Standart event müqaviləsi müəyyən edilib.
- MT5 Bridge canlı tick qəbul edir.
- Tick məlumatı `TICK_RECEIVED` event-inə çevrilir.
- Event JSON formatında serializasiya edilir.
- Event HTTP vasitəsilə backend-ə göndərilir.
- FastAPI event strukturunu yoxlayır.
- Tick-lər SQLite bazasında saxlanılır.
- Eyni `event_id` ikinci dəfə bazaya yazılmır.
- Tick statistikası endpoint-i yaradılıb.
- Operational status endpoint-i yaradılıb.
- `waiting`, `active` və `stale` axın vəziyyətləri nəzərdə tutulub.
- Real MT5 axını ilə `active` və `stale` vəziyyətləri yoxlanılıb.
- Sınaq zamanı 172 tick-in saxlanması müşahidə edilib.
- Uğursuz HTTP göndərişləri üçün ilkin yaddaş FIFO buferi yaradılıb.
- Layihə GitHub-a yüklənib.

## Mövcud API endpoint-ləri

- `GET /health`
- `POST /events/ticks`
- `GET /statistics/ticks`
- `GET /status/operational`

## Cari modul vəziyyəti

### Backend

- Texnologiya: FastAPI
- Verilənlər bazası: SQLite
- Versiya: `0.1.0`
- Tick doğrulaması və saxlanması işləyir.
- Operational monitoring işləyir.

### MT5 Bridge

- Status: `EXPERIMENTAL`
- Sənədləşdirilmiş versiya: `0.2.0`
- Canlı tick oxunması işləyir.
- Event yaradılması işləyir.
- HTTP göndərişi işləyir.
- Uğursuz event-in RAM buferinə əlavə edilməsi işləyir.
- Buferdəki event-lərin avtomatik təkrar göndərilməsi hələ yoxdur.

### Frontend

- `frontend` qovluğu mövcuddur.
- Hazır frontend tətbiqi yoxdur.
- İlk frontend Phase 1 monitorinq paneli olmalıdır.
- Frontend yalnız backend API vasitəsilə məlumat almalıdır.

## Məlum problemlər

1. `PROJECT_ROADMAP.md` boşdur.
2. Azərbaycan hərfləri bəzi sənədlərdə pozulmuş görünür.
3. Phase 1 status sənədinin Markdown quruluşunda problem var.
4. MT5 buferi event-i saxlayır, amma yenidən göndərmir.
5. RAM buferindəki məlumat MT5 bağlandıqda itir.
6. Bufer dolması və məlumat itkisi siyasəti müəyyən edilməyib.
7. MT5 Bridge versiyası bütün fayllarda uyğun deyil.
8. README yeni bufer funksiyasını əks etdirmir.
9. MT5 buferi üçün avtomatlaşdırılmış test yoxdur.
10. Frontend spesifikasiyası hazırlanmayıb.

## Son tamamlanan texniki dəyişiklik

MT5 Bridge-ə uğursuz tick event-lərini saxlayan FIFO yaddaş buferi əlavə edilib.

Commit:

```text
9f58096 Add MT5 tick buffering
```

## Növbəti əsas texniki prioritet

Backend əlçatan olmadıqda buferə yazılmış event-lərin backend bərpa olduqdan sonra zaman ardıcıllığı ilə avtomatik göndərilməsi.

## Phase 1-in tamamlanması üçün qalan əsas işlər

1. Layihə yaddaşı və yol xəritəsini tamamlamaq.
2. Sənədlərin kodlaşdırmasını düzəltmək.
3. MT5 buferinin retry mexanizmini yaratmaq.
4. Disk əsaslı davamlı event növbəsini layihələndirmək.
5. Backend monitorinq göstəricilərini genişləndirmək.
6. Avtomatlaşdırılmış testləri artırmaq.
7. İlk frontend monitorinq panelini yaratmaq.
8. Uzunmüddətli sabitlik testi aparmaq.
9. Phase 1 nəticələrini sənədləşdirmək.
10. Phase 1-i rəsmi şəkildə bağlamaq.