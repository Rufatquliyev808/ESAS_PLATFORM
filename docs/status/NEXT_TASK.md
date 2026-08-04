# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Hazır deterministik tick batch sərhədi üzərində `max_speed` replay orchestrator-u,
təhlükəsiz dayandırmanı və qəza sonrası davametməni hazırlamaq.

## Sərhədlər

- Yalnız `running` vəziyyətində və `mode=max_speed` sessiya avtomatik irəliləyə bilər.
- Hər daxili batch maksimum `1000` tick olmalıdır.
- Orchestrator bütün dataset-i yaddaşa yükləməməlidir.
- Hər uğurlu batch-dən sonra progress, checkpoint və audit atomik saxlanmalıdır.
- Pause, cancel və interrupt siqnalları növbəti batch sərhədində təhlükəsiz dayanmalıdır.
- Restart checkpoint-dən sonrakı tick-dən davam etməli, təkrar emal yaratmamalıdır.
- Dataset dəyişməsi və ya natamam batch fail-closed nəticə verməlidir.
- Xam tick-lər dəyişdirilməməli; API, frontend və canlı migration hələ əlavə edilməməlidir.

## Tamamlanma meyarları

- `max_speed` sessiyası çoxsaylı batch ilə boşluqsuz və dublikatsız tamamlanır.
- Böyük dataset sabit yaddaş sərhədi ilə emal olunur.
- Pause/interruption sonrası resume düzgün checkpoint-dən davam edir.
- Batch xətasında son uğurlu checkpoint qorunur.
- Terminal sessiya yenidən işə düşmür.
- Mövcud backend testləri keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

Orchestrator qəbul edildikdən sonra replay nəticəsinin təkrar istehsal sübutu və
məlumat keyfiyyəti analiz qatının ilk qaydaları hazırlanacaq.
