# ESAS Platform — Phase 2 saxlama və ehtiyat nüsxə müqaviləsi

Status: **DESIGN READY — NOT IMPLEMENTED**

Bu müqavilə Phase 2 məlumatlarının saxlanması, ehtiyatlanması, yoxlanması,
bərpası və təhlükəsiz təmizlənməsi qaydalarını müəyyən edir. Phase 1 qəbulu
tamamlanmadan icraya icazə vermir.

Konfiqurasiya, açar və startup sərhədləri:
`docs/architecture/PHASE_2_CONFIGURATION_STARTUP_CONTRACT.md`

Audit və qəbul sübutu paketinin formatı və saxlanması:
`docs/architecture/PHASE_2_AUDIT_EVIDENCE_EXPORT_CONTRACT.md`

## Əsas prinsiplər

1. Xam bazar məlumatı əsas aktivdir və standart olaraq qorunur.
2. Audit tarixçəsi və qəbul sübutları append-only qeydlərdir.
3. Təmizləmə canlı tick qəbuluna mane olmamalıdır.
4. Ehtiyat nüsxə yalnız bütövlüyü və bərpası yoxlandıqdan sonra etibarlıdır.
5. Heç bir avtomatika qorunan məlumatı səssiz silə bilməz.
6. Saxlama müddəti avtomatik silinmə tarixi deyil.

## Məlumat sinifləri və ilkin saxlama

| Sinif | Nümunə | İlkin müddət | Avtomatik silinmə |
| --- | --- | --- | --- |
| Xam bazar məlumatı | `tick_events`, dataset fingerprint | Müddətsiz | Qadağandır |
| İtki və bütövlük qeydləri | `loss_acknowledgements`, rədd edilən eventlər | Müddətsiz | Qadağandır |
| Təhlükəsizlik və əməliyyat auditi | giriş, rol, replay idarəsi, təsdiqləmə | Müddətsiz | Qadağandır |
| Qəbul sübutları | Phase 1/2, performans və bərpa hesabatları | Müddətsiz | Qadağandır |
| Replay nəticələri | sessiya, checkpoint, tapıntı, keyfiyyət hesabatı | İlkin versiyada müddətsiz | İlkin versiyada qadağandır |
| Idempotency qeydləri | hash edilmiş sorğu açarları | Ən az 24 saat | Kiçik paketlərlə mümkündür |
| Əməliyyat metrikləri | sağlamlıq və həcm zaman sıraları | 90 gün | Aqreqasiyadan sonra mümkündür |
| Əməliyyat logları | strukturlaşdırılmış API və worker logları | 30 gün | Təhlükəsiz rotasiya ilə mümkündür |
| Müvəqqəti diaqnostika | əl ilə yaradılmış debug paketi | 7 gün | Hold yoxdursa mümkündür |

Şifrə, token, sessiya sirri və şifrələmə açarı logda, audit payload-da,
ixrac hesabatında və Git-də saxlanmır.

## Qorunan qeydlər və hold

Xam tick-lər, itki təsdiqləri, təhlükəsizlik auditi, migration tarixçəsi,
qəbul sübutları və açıq insidentə bağlı məlumat adi təmizləmədən qorunur.
Insident/audit hold-u bütün müddət qaydalarını üstələyir. Hold-un götürülməsi
administrator, təzə autentifikasiya, səbəb və append-only audit tələb edir.

## Ehtiyat nüsxə və bərpa hədəfləri

Phase 2 icra hədəfi:

- hər 6 saatda SQLite-aware online backup, 7 gün saxlanılır;
- gündəlik yoxlanmış backup, 30 gün saxlanılır;
- aylıq yoxlanmış backup, 12 ay saxlanılır;
- istehsal bazasından ayrı yerdə ən az bir şifrələnmiş nüsxə;
- RPO ən çox 6 saat, RTO ən çox 4 saat.

Bunlar hazırkı təminat deyil, dizayn hədəfidir. Planlı backup və bərpa sınağı
keçmədən production hazırlığı kimi göstərilə bilməz.

WAL rejimində yalnız database faylını köçürmək qəbul edilmir. SQLite online
backup API və ya SQLite-aware üsul istifadə olunur. Şifrələmə açarı backup-la
eyni yerdə saxlanmır.

## Backup manifesti

Hər backup aşağıdakı maşın-oxunan manifestə malikdir:

- backup və sxem versiyası, UTC yaranma vaxtı;
- məxfi olmayan database identifikatoru və tətbiq versiyaları;
- ölçü və SHA-256 checksum;
- SQLite `quick_check` nəticəsi;
- tick sayı, ilk/son tick vaxtı və dataset fingerprint;
- itki təsdiqi və audit sayları;
- şifrələmə vəziyyəti və açarın özü deyil, identifikatoru;
- son yoxlama və bərpa sınağı vaxtı.

Tam manifesti olmayan backup təsdiqlənməmiş sayılır və köhnə təsdiqlənmiş
backup-ın silinməsinə əsas ola bilməz.

## Bərpa qaydası

Bərpa sınağı həmişə ayrı müvəqqəti yerdə aparılır:

1. manifest və checksum yoxlanır;
2. icazəli açarla deşifrə edilir;
3. `quick_check` və `foreign_key_check` işlədilir;
4. saylar, vaxt sərhədləri və fingerprint müqayisə olunur;
5. tətbiq təcrid olunmuş rejimdə bərpa bazası ilə açılır;
6. siqnal və order yaratmadan nümunə replay oxusu edilir;
7. nəticə dəyişməz bərpa sübutu kimi qeyd olunur.

Production bərpasında servis dayandırılır, cari bazanın backup-ı alınır,
dəqiq hədəf yoxlanır və administrator təsdiqi tələb olunur. Cari baza kor-koranə
üzərinə yazılmır. Rübdə ən az bir dəfə və ciddi sxem/backup dəyişikliyindən
sonra bərpa sınağı aparılır.

## Təmizləmə nəzarəti

Təmizləmə iki mərhələlidir:

1. heç nə silmədən dəqiq uyğunluq hesabatı;
2. yalnız yoxlanmış identifikatorların kiçik, davam etdirilə bilən paketlərlə silinməsi.

Geniş recursive yol, həll olunmamış dəyişən və wildcard hədəf qadağandır.
Actor, policy versiyası, identifikatorlar, səbəb, vaxt və nəticə audit edilir.

Replay nəticələrinin gələcəkdə silinməsi yeni müqavilə versiyası, təsir önizləməsi,
yoxlanmış backup, administrator təsdiqi, auditor görünürlüğü və təzə giriş
tələb edir. Aktiv, yarımçıq, hold altında və ya istinad edilən sessiya silinmir.

## Disk dolması davranışı

- 70%: xəbərdarlıq və qalan müddət proqnozu;
- 85%: kritik, yeni replay və törəmə işlər dayandırılır;
- 95%: fövqəladə, yalnız canlı qəbul və bütövlük xəbərdarlığı prioritet qalır.

Disk dolması xam tick, itki, audit və qəbul sübutlarını avtomatik silmir.
Operator müdaxiləsi tələb olunur.

## Məxfilik və Git sərhədi

IP ünvanlarının daimi saxlanması bu müqavilə ilə aktiv deyil. Bunun üçün ayrıca
məxfilik qərarı lazımdır. Auditdə istifadəçi kodu ola bilər, ixracda isə yalnız
zəruri identifikasiya qalır.

Canlı baza, backup, xam log və sanitizasiya edilməmiş sübut Git-ə əlavə edilmir.
Yalnız məxfi olmayan xülasə və sintetik fixture repository-yə daxildir.

## Məcburi testlər

Bütün avtomatik testlər sintetik məlumat və müvəqqəti yol istifadə edir:

- WAL yazıları davam edərkən online backup;
- checksum, korlanma və natamam manifest xətası;
- bərpadan sonra say və fingerprint bərabərliyi;
- retention sərhədləri və hold-un silinməni bloklaması;
- yarımçıq təmizləmənin təhlükəsiz davamı;
- şifrələmə açarı olmadıqda fail-closed davranış;
- 70/85/95 faiz disk vəziyyətləri;
- xam tick və auditin avtomatik silinə bilmədiyinin sübutu.

Heç bir backup və retention testi canlı database-i hədəfləmir.

## Monitorinq

Panel backup yaşı, yoxlama vəziyyəti, son bərpa sınağı, disk istifadəsi,
tutum proqnozu və təmizləmə xətalarını ayrıca göstərir. Backup, retention və
database sağlamlığı ayrı statuslardır və biri digərini gizlətmir.
