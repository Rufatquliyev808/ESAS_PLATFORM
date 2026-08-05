# ESAS Platform — Codex iş qaydaları

## Hər sessiyanın başlanğıcı

Bu faylları ardıcıllıqla oxu: `AGENTS.md`, konstitusiya faylları, arxitektura, `PROJECT_ROADMAP.md`, `docs/status/CURRENT_STATE.md`, `docs/status/NEXT_TASK.md`, `docs/status/SESSION_HANDOFF.md`, `CHANGELOG.md`. Sonra Git statusu, branch və son commitləri yoxla. Cari vəziyyəti anlamadan kodu dəyişmə və əvvəlki işi təkrarlama.

## Əsas prinsiplər

- Məlumat bütövlüyü performansdan üstündür; xam məlumat dəyişdirilməməli və səbəbsiz silinməməlidir.
- Modullar yalnız standart interfeys və versiyalanmış event müqavilələri ilə əlaqə saxlamalıdır.
- Sübut edilməmiş modul real qərara və ticarətə təsir etməməlidir.
- Frontend yalnız backend API istifadə etməli və ticarət qərarı verməməlidir.
- Mövcud istifadəçi dəyişikliklərini icazəsiz silmə və üzərinə yazma.
- Məxfi məlumatları, `.env`, parol, token və açarları Git-ə və sənədlərə əlavə etmə.
- Real ticarəti yalnız açıq istifadəçi təsdiqi ilə aktivləşdir.

## Dəyişiklik qaydası

Əvvəl məqsədi, təsir edilən faylları, konstitusiya uyğunluğunu, məlumat/geriyə uyğunluq riskini və testləri müəyyən et. Sonra kodu dəyiş, uyğun testləri və mümkün olduqda tam regressiyanı işlə, nəticəni yoxla, sənədləri yenilə və yalnız məqsədli faylları commit et. Push yalnız istifadəçi tapşırığı olduqda edilir.

## Məcburi davamlılıq qeydiyyatı

Hər ayrıca iş tamamlanan kimi, növbəti işə keçməzdən əvvəl bunları yenilə:

1. `docs/status/CURRENT_STATE.md` — bitən iş, dəyişən fayllar, test nəticələri, commit/push vəziyyəti və məlum problemlər.
2. `docs/status/NEXT_TASK.md` — yalnız növbəti konkret mərhələ, sərhədlər, tamamlanma meyarları və təsdiq şərti.
3. `CHANGELOG.md` — sistem davranışına təsir edən dəyişikliklər.
4. `docs/status/SESSION_HANDOFF.md` — yeni söhbətin tarixçəsiz davam edə bilməsi üçün aktual xülasə.

Bu qeydiyyat edilməyibsə iş tamamlanmış sayılmır. Məxfi məlumatı handoff-a yazma. Yeni sessiya əvvəl real faylları, Git-i, testləri və verilənlər bazasını yoxlamalı; sənəddəki məlumatı kor-koranə qəbul etməməlidir.

## Sessiya sonunda mütləq aydın olmalıdır

- nə edildi və hansı fayllar dəyişdi;
- hansı testlər keçdi və hansı yoxlama bloklandı;
- hansı problem və risk qaldı;
- növbəti konkret tapşırıq nədir;
- commit və push vəziyyəti nədir.
