# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Replay sessiyasının `step` rejimi üçün bir əmrdə `1..1000` tick həddində
deterministik batch emalını və idempotency sərhədini hazırlamaq.

## Sərhədlər

- Yalnız `running` vəziyyətində olan və `mode=step` sessiya irəliləyə bilər.
- Tick-lər sessiyanın immutable intervalı daxilində kanonik
  `(event_timestamp, event_id)` sırası ilə oxunmalıdır.
- Bir addım tələb olunan saydan və `1000` tick-dən çox emal etməməlidir.
- Təkrar göndərilən eyni idempotency açarı ikinci dəfə progress yaratmamalıdır.
- Batch tam uğurlu olmadan checkpoint, progress və audit irəli getməməlidir.
- Dataset sonuna çatdıqda sessiya atomik olaraq `completed` olmalıdır.
- Xam `tick_events` cədvəli dəyişdirilməməlidir.
- Hələ API, frontend, worker və canlı migration əlavə edilməməlidir.

## Tamamlanma meyarları

- İlk addım checkpoint-dən sonrakı düzgün tick-ləri qaytarır.
- Ardıcıl addımlar arasında boşluq və dublikat yaranmır.
- Eyni idempotency açarı eyni nəticəni qaytarır və audit/progress təkrarlanmır.
- Səhv batch emalı tam rollback verir.
- Son batch faktiki sayla tamamlanır və sessiyanı `completed` edir.
- Mövcud backend testləri keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

`step` rejimi qəbul edildikdən sonra eyni batch sərhədi üzərində `max_speed`
orchestrator və qəza sonrası davametmə hazırlanacaq.
