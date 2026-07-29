# ESAS Platform — Codex İş Qaydaları

## İşə başlama qaydası

Hər yeni iş sessiyasında əvvəlcə bu faylları oxu:

1. `AGENTS.md`
2. `docs/constitution/PLATFORM_RULES.md`
3. `docs/constitution/EVENT_CONTRACT.md`
4. `docs/constitution/MODULE_LIFECYCLE.md`
5. `docs/constitution/VERSION_POLICY.md`
6. `docs/architecture/PLATFORM_ARCHITECTURE.md`
7. `PROJECT_ROADMAP.md`
8. `docs/status/CURRENT_STATE.md`
9. `docs/status/NEXT_TASK.md`
10. `CHANGELOG.md`

Sonra Git statusunu və son commit tarixçəsini yoxla. Cari vəziyyəti anlamadan kod dəyişdirmə.

## Əsas məqsəd

ESAS Platform bazarı qərəzsiz müşahidə edən, xam məlumat toplayan, statistik qanunauyğunluqları araşdıran və yalnız sübut edilmiş nəticələr əsasında qərar verən modul platformadır.

Platforma əvvəlcədən seçilmiş strategiyanı sübut etməyə çalışmamalıdır. Strategiyalar məlumatdan və yoxlanmış nəticələrdən yaranmalıdır.

## Məcburi prinsiplər

- Məlumatın bütövlüyü performansdan üstündür.
- Xam məlumat dəyişdirilməməli və səbəbsiz silinməməlidir.
- Modullar bir-birinin daxili koduna müdaxilə etməməlidir.
- Modullar yalnız standart interfeys və event-lərlə əlaqə saxlamalıdır.
- Event-lər yaradıldıqdan sonra dəyişdirilməməlidir.
- Event müqaviləsindəki dəyişikliklər versiyalandırılmalıdır.
- Sübut edilməmiş modul real qərar və ticarətə təsir etməməlidir.
- Hər yeni modul həyat dövrü qaydalarına uyğun inkişaf etdirilməlidir.
- Frontend birbaşa verilənlər bazasına qoşulmamalıdır; backend API-dən istifadə etməlidir.
- Frontend ticarət qərarı verməməlidir.

## Dəyişiklik qaydası

Kod dəyişdirilməzdən əvvəl:

1. Tapşırığın məqsədini müəyyən et.
2. Təsir edəcək faylları müəyyən et.
3. Konstitusiya və arxitektura ilə uyğunluğu yoxla.
4. Məlumat itkisi və geriyə uyğunluq risklərini qiymətləndir.
5. Lazımi testləri müəyyən et.

Kod dəyişdirildikdən sonra:

1. Müvafiq testləri icra et.
2. Nəticəni yoxla.
3. Sənədləri yenilə.
4. `docs/status/CURRENT_STATE.md` faylını yenilə.
5. `docs/status/NEXT_TASK.md` faylını növbəti işə uyğunlaşdır.
6. Lazım olduqda `PROJECT_ROADMAP.md` və `CHANGELOG.md` fayllarını yenilə.
7. Yalnız məqsədli faylları commit et.

## Təhlükəsizlik

- `.env`, şifrələr, tokenlər, SSH açarları və digər məxfi məlumatları Git-ə əlavə etmə.
- `.venv`, loglar, yaradılmış verilənlər bazaları və build fayllarını commit etmə.
- İstifadəçinin mövcud dəyişikliklərini icazəsiz silmə və ya üzərinə yazma.
- Məlumat bazasında dağıdıcı əməliyyatdan əvvəl ehtiyat nüsxə və bərpa yolunu müəyyən et.
- Real ticarət funksiyasını açıq istifadəçi təsdiqi olmadan aktivləşdirmə.

## Phase 1 prioriteti

Phase 1 tamamlanana qədər əsas prioritet etibarlı tick məlumatı axınıdır:

`MT5 → Bridge → Event → HTTP → FastAPI → SQLite → Monitoring`

AI, avtomatik qərar və real ticarət funksiyaları Phase 1 qəbul meyarları tamamlanmadan əsas prioritet olmamalıdır.

## Sessiyanın tamamlanması

Hər sessiyanın sonunda aşağıdakılar aydın olmalıdır:

- nə edildi;
- hansı fayllar dəyişdi;
- hansı testlər keçirildi;
- hansı problemlər qaldı;
- növbəti konkret tapşırıq nədir;
- dəyişikliklər commit və push edilibmi.

Yeni sessiya yalnız layihə sənədlərini və Git tarixçəsini oxumaqla qaldığı yerdən davam edə bilməlidir.