# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Snapshot nəticəsindən replay sessiyasını və ilkin `create` audit sətrini eyni
transaction daxilində yaradan repository əməliyyatını hazırlamaq.

## Sərhədlər

- Giriş `symbol`, `[start_at,end_at)`, `step|max_speed`, yaradan istifadəçi və
  müqavilə versiyalarını qəbul etməlidir.
- `session_id` təxmin edilə bilməyən lokal identifikator olmalıdır.
- Snapshot sessiya yazısından əvvəl read-only sərhəddə hesablanmalıdır.
- Sessiya və ilkin audit sətri bir transaction-da yazılmalıdır; yarımçıq yazı olmaz.
- Boş dataset sessiyası birbaşa `completed`, digəri `created` olmalıdır.
- Xam tick və loss acknowledgement məlumatı dəyişməməlidir.
- Hələ worker, API, frontend və canlı migration əlavə edilməməlidir.

## Tamamlanma meyarları

- Yaradılan sessiyanın immutable giriş və snapshot sahələri düzgün saxlanmalıdır.
- Eyni transaction-da dəqiq bir `create` audit sətri yaranmalıdır.
- Audit insert xətası sessiya insert-ini də rollback etməlidir.
- Boş və dolu dataset üçün düzgün ilkin vəziyyət seçilməlidir.
- İki yaradılış unikal, təxmin edilə bilməyən session ID-lər verməlidir.
- Xam tick sətirləri əməliyyatdan əvvəl və sonra eyni qalmalıdır.
- Mövcud backend testləri keçməlidir.

## Sonrakı addım

Sessiya yaratma repository-si qəbul edildikdən sonra vəziyyət keçidi modeli və
atomik checkpoint/audit əməliyyatları hazırlanacaq.
