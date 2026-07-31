# ESAS Platform — Phase 2 konfiqurasiya və təhlükəsiz işə salınma müqaviləsi

Versiya: 1.0
Status: **DESIGN READY — NOT IMPLEMENTED**
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

## Məqsəd

Bu müqavilə Phase 2 servislərinin hansı konfiqurasiya ilə, hansı yoxlamalardan
sonra və hansı təhlükəsizlik məhdudiyyətləri daxilində işə düşəcəyini müəyyən
edir.

Phase 2 başlanğıcı:

- xam tick qəbulunun bütövlüyünü riskə atmır;
- səhv və ya natamam konfiqurasiyada fail-closed dayanır;
- məxfi dəyərləri Git, log, audit və frontend-ə çıxarmır;
- migration, replay worker və təmizləmə işlərini səssiz aktivləşdirmir;
- siqnal, order və real ticarət funksiyası açmır.

## Konfiqurasiya mənbələrinin prioriteti

Etibarlı mənbələr aşağıdakı ardıcıllıqla oxunur:

1. prosesə təhlükəsiz şəkildə verilmiş mühit dəyişənləri;
2. Git-dən kənar lokal secret/config faylı;
3. versiyalanmış, məxfi olmayan standart dəyərlər.

Frontend sorğusu, URL parametri, cookie, database-dəki xam tick payload-ı və
istifadəçinin brauzerdə dəyişdirdiyi dəyər backend konfiqurasiyası sayılmır.

Eyni parametr iki etibarlı mənbədə fərqli verilərsə startup dayanır və yalnız
parametrin adı göstərilir. Məxfi dəyər və onun hissəsi göstərilmir.

## Mühit profilləri

Yalnız bu profillər qəbul edilir:

- `development`: lokal inkişaf, sintetik test və debug;
- `test`: yalnız müvəqqəti baza və sintetik fixture;
- `acceptance`: qəbul sübutu yaradan nəzarətli sınaq;
- `production`: real platforma məlumatı və sərt təhlükəsizlik qaydaları.

Naməlum profil qəbul edilmir. Profil startup-dan sonra dəyişdirilə bilməz.
`test` profilinin production database yoluna, production backup yerinə və canlı
Bridge açarına bağlanması qadağandır.

`development` və `test` rahatlıqları `acceptance` və `production` profilinə
avtomatik keçmir.

## Məcburi və məxfi parametrlər

Phase 2 implementasiyası aşağıdakı parametr qruplarını ayrıca təsnif edir:

### Məcburi, məxfi olmayan

- mühit profili;
- database identifikatoru və icazəli kök yolu;
- API bind ünvanı və portu;
- replay worker sayı və təhlükəsiz maksimumu;
- replay səhifə/batch ölçüsü;
- heartbeat və timeout hədləri;
- metric və log saxlama müddətləri;
- backup cədvəli və məxfi olmayan backup identifikatoru;
- konfiqurasiya sxeminin versiyası.

### Məcburi, məxfi

- Bridge API açarı;
- sessiya imzalama açarı;
- backup şifrələmə açarının identifikatoruna çıxış;
- ilk administrator bootstrap nişanı, yalnız bootstrap zamanı.

### Qadağan edilmiş

- kodda və ya versiyalanmış sənəddə real parol/token;
- `NEXT_PUBLIC_*` vasitəsilə backend sirri;
- məxfi dəyərin command-line arqumenti kimi ötürülməsi;
- production üçün standart və ya nümunə parol;
- eyni açarın Bridge, sessiya və backup üçün təkrar istifadəsi.

Məxfi açar minimum 32 təsadüfi bayt ekvivalentində olmalı və məqsədinə görə
ayrılmalıdır. `.env.example` yalnız dəyişən adlarını və təhlükəsiz placeholder
dəyərləri göstərir.

## Startup yoxlamalarının ardıcıllığı

Servis trafik qəbul etməzdən əvvəl:

1. profil və konfiqurasiya sxemi doğrulanır;
2. bütün məcburi parametr və sərhədlər yoxlanır;
3. məxfi açarların mövcudluğu, minimum gücü və bir-birindən fərqli olması
   yoxlanır;
4. database və backup yolları canonical formaya çevrilib icazəli kök daxilində
   olduğu təsdiqlənir;
5. `test` profilinin production resurslarına toxunmadığı sübut olunur;
6. database açılır, `quick_check`, schema versiyası və migration checksum-u
   yoxlanır;
7. yazma tələb olunan profildə təhlükəsiz transaction daxilində geri qaytarılan
   real yazma yoxlaması edilir;
8. append-only audit yazısının mümkün olduğu yoxlanır;
9. disk və backup vəziyyəti qiymətləndirilir;
10. yalnız bundan sonra API `ready` olur və worker-lər başlaya bilir.

Startup yoxlaması uğursuz olduqda proses aydın kateqoriya ilə dayanır. Logda
parol, token, tam lokal yol, database payload-ı və traceback göstərilmir.

## Phase 1 və Phase 2 proses sərhədi

Phase 2 replay və analiz yükü Phase 1 tick qəbulundan ayrılır. Replay worker
başlamasa belə Phase 1 qəbul prosesi sağlam qala bilməlidir.

Phase 2-nin səhv konfiqurasiyası:

- tick endpoint-in mövcud məlumatını dəyişmir;
- xam cədvəldə migration etmir;
- Bridge açarını rotasiya etmir;
- növbəni silmir;
- qəbul sübutunu etibarsızlaşdırmır.

Phase 2 API hazır deyilsə frontend son uğurlu məlumatı Phase 2 nəticəsi kimi
yeniləmir və səbəbi ayrıca göstərir.

## Funksiya açarları

Funksiya açarı təhlükəsizlik sərhədi deyil; backend permission yoxlamasını
əvəz etmir.

İlkin Phase 2 açarları standart olaraq bağlıdır:

- `replay_read_enabled`;
- `replay_worker_enabled`;
- `quality_analysis_enabled`;
- `phase2_ui_enabled`;
- `scheduled_backup_enabled`;
- `retention_cleanup_enabled`.

Aktivləşmə ardıcıllığı:

1. schema və yalnız-oxuma repository;
2. replay oxusu;
3. keyfiyyət analizi;
4. qorunan API;
5. frontend görünüşü;
6. worker və planlı backup;
7. ayrıca qəbuldan sonra retention cleanup.

`retention_cleanup_enabled` heç vaxt migration və ya sadə restart nəticəsində
öz-özünə aktiv olmur.

## Konfiqurasiya dəyişikliyi

Təhlükəsizlik, database, backup, retention, worker sayı və timeout parametrləri
yalnız restart ilə tətbiq olunur. İsti dəyişiklik ilkin versiyada yoxdur.

Dəyişiklik prosesi:

1. məxfi dəyəri göstərməyən fərq önizləməsi;
2. sxem və sərhəd yoxlaması;
3. administrator təsdiqi və təzə autentifikasiya;
4. append-only audit;
5. nəzarətli restart;
6. health/readiness və əsas replay smoke testi;
7. uğursuzluqda əvvəlki təsdiqlənmiş konfiqurasiyaya rollback.

Rollback database migration-ını kor-koranə geri çevirmir. Database bərpası
ayrıca migration və backup müqavilələrinə tabedir.

## Açar rotasiyası

- Bridge və sessiya açarları ən azı 90 gündə bir və şübhə olduqda dərhal
  rotasiya edilir.
- Backup açarı ayrıca idarə olunur; köhnə backup-ların oxunması üçün əvvəlki
  açar identifikatorları qorunur.
- Sessiya açarı dəyişəndə bütün aktiv sessiyalar ləğv edilir.
- Bridge rotasiyası qısa, audit olunan keçid pəncərəsində əvvəlki və yeni açarı
  qəbul edə bilər; pəncərə bitdikdən sonra köhnə açar rədd edilir.
- Açarın özü auditə yazılmır; yalnız məqsəd, qeyri-həssas key ID, actor, vaxt və
  nəticə saxlanır.

## Şəbəkə və uzaq giriş

Lokal profil standart olaraq yalnız `127.0.0.1` üzərində dinləyir və yalnız həmin
kompüterdən açılır.

Başqa kompüterdən giriş üçün ayrıca production yerləşdirməsi tələb olunur:

- explicit bind ünvanı;
- firewall allowlist;
- HTTPS reverse proxy;
- təhlükəsiz cookie və CSRF müdafiəsi;
- etibarlı sertifikat;
- ayrıca backup və monitorinq;
- uzaq giriş üçün təhlükəsizlik qəbulu.

Sadəcə `0.0.0.0` yazmaq təhlükəsiz yerləşdirmə sayılmır və lokal start aləti bunu
avtomatik etmir.

## Xəta kateqoriyaları

Startup ən azı bu təhlükəsiz kateqoriyaları qaytarır:

- `CONFIG_SCHEMA_INVALID`;
- `CONFIG_REQUIRED_VALUE_MISSING`;
- `CONFIG_SOURCE_CONFLICT`;
- `SECRET_MISSING_OR_WEAK`;
- `SECRET_PURPOSE_REUSE`;
- `PATH_OUTSIDE_ALLOWED_ROOT`;
- `TEST_PRODUCTION_BOUNDARY_VIOLATION`;
- `DATABASE_INTEGRITY_FAILED`;
- `MIGRATION_CHECKSUM_MISMATCH`;
- `AUDIT_WRITE_FAILED`;
- `BACKUP_NOT_READY`;
- `DISK_CAPACITY_CRITICAL`.

Xəta cavabı düzəliş istiqaməti verir, lakin məxfi dəyəri və sistemin həssas
daxili quruluşunu açıqlamır.

## Məcburi testlər

1. Hər profil yalnız öz icazəli resursları ilə başlayır.
2. Naməlum profil və konfiqurasiya versiyası fail-closed dayanır.
3. Məcburi parametr olmadıqda servis `ready` olmur.
4. Zəif, eyni və ya placeholder açarlar acceptance/production-da rədd edilir.
5. Məxfi dəyər log, audit, API cavabı, frontend bundle və test çıxışında görünmür.
6. Relative traversal, symlink/junction və icazəli kökdən kənar yol rədd edilir.
7. `test` profili production database və backup yerinə toxuna bilmir.
8. Səhv migration checksum-u worker başlamazdan əvvəl startup-ı dayandırır.
9. Audit yazıla bilmirsə dəyişdirici Phase 2 funksiyalar açılmır.
10. Phase 2 startup xətası Phase 1 xam tick tarixçəsini dəyişmir.
11. Funksiya açarı bağlı olduqda endpoint və worker həqiqətən bağlıdır.
12. Cleanup restart və migration-dan sonra standart olaraq bağlı qalır.
13. Sessiya açarı rotasiyası mövcud sessiyaları ləğv edir.
14. Konfiqurasiya rollback-i canlı bazanı üzərinə yazmır.
15. Bütün testlər sintetik müvəqqəti resurslarda işləyir.

## İcra ardıcıllığındakı yeri

Phase 1 qəbulundan sonra:

1. typed konfiqurasiya sxemi və profil validatoru;
2. secret provider interfeysi və redaction;
3. canonical yol və test/production sərhəd yoxlaması;
4. startup preflight və readiness;
5. funksiya açarları;
6. audit olunan konfiqurasiya dəyişiklik prosesi;
7. açar rotasiyası;
8. backend, frontend və startup qəbul testləri.

Bu sənəd Phase 2 istehsal kodunun başladılması və ya rəsmi START verilməsi
demək deyil.
