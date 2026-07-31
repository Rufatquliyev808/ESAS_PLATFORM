# ESAS Platform — Phase 2 müşahidə və xəbərdarlıq müqaviləsi

Versiya: 1.0
Status: DESIGN READY — NOT IMPLEMENTED
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

## Məqsəd

Bu müqavilə replay, məlumat keyfiyyəti, worker, SQLite, API və təhlükəsizlik
hadisələrinin necə ölçüləcəyini, təsnif ediləcəyini və istifadəçiyə necə
göstəriləcəyini müəyyən edir.

Müşahidə sistemi:

- xam tick məlumatını dəyişmir;
- məlumat keyfiyyəti tapıntısını avtomatik platforma nasazlığı saymır;
- xəbərdarlığın təsdiqini problemin həlli kimi göstərmir;
- məxfi məlumatı metric, log, xəta cavabı və frontend-ə çıxarmır;
- siqnal, order və ticarət qərarı yaratmır.

Əlaqəli müqavilələr:

- `docs/architecture/PHASE_2_REPLAY_SESSION_CONTRACT.md`
- `docs/architecture/PHASE_2_DATA_QUALITY_CONTRACT.md`
- `docs/architecture/PHASE_2_ACCESS_CONTROL_CONTRACT.md`
- `docs/architecture/PHASE_2_PERFORMANCE_TEST_CONTRACT.md`

## Üç ayrı vəziyyət sahəsi

Platforma aşağıdakı vəziyyətləri bir-birinə qarışdırmır.

### 1. Platforma sağlamlığı

- `healthy`: tələb olunan komponentlər işləyir;
- `degraded`: iş davam edir, amma gecikmə, retry və ya qismən funksiya itkisi var;
- `critical`: bütövlük, audit və ya təhlükəsizlik riski var;
- `unavailable`: tələb olunan servis cavab vermir.

### 2. Replay sessiyası

`created`, `running`, `paused`, `interrupted`, `completed`, `cancelled`,
`failed` vəziyyətləri replay həyat dövrü müqaviləsindən gəlir.

`paused`, `completed` və istifadəçi tərəfindən `cancelled` platforma nasazlığı
deyil. `interrupted` səbəbindən asılı olaraq xəbərdarlıq yarada bilər.

### 3. Məlumat keyfiyyəti

`pass`, `review`, `fail` yalnız tətbiq olunan keyfiyyət qaydalarının nəticəsidir.

- `review` platformanın işləməməsi demək deyil;
- `fail` məlumat aralığının etibarlılığına təsir edir, backend-in çökməsi demək
  deyil;
- bazar sessiyası məlum olmadan gap namizədi avtomatik məlumat itkisi və ya
  platforma nasazlığı sayılmır.

## Siqnal mənbələri

### API

- sorğu sayı və nəticə statusu;
- server xətası və latency;
- `401`, `403`, `409`, `422`, `429`, `503` sayları;
- correlation ID ilə təhlükəsiz xəta kateqoriyası.

### Replay worker

- aktiv worker sayı;
- son heartbeat;
- emal edilmiş event və batch sayı;
- batch müddəti və throughput;
- retry və interruption sayı;
- checkpoint-in son uğurlu vaxtı.

### SQLite

- yazma və oxuma latency-si;
- `SQLITE_BUSY` retry sayı;
- həll edilməmiş busy və transaction rollback sayı;
- database fayl ölçüsü;
- son `quick_check` nəticəsi;
- migration və backup vəziyyəti.

### Məlumat keyfiyyəti

- işləyən və tamamlanan analiz sayı;
- qayda versiyası;
- analiz müddəti;
- `info`, `warning`, `critical` tapıntı sayı;
- hesabat statusu və fingerprint.

### Təhlükəsizlik

- uğurlu və uğursuz giriş sayı;
- aktiv login bloklaması;
- permission rəddi;
- rol dəyişikliyi və sessiya revocation-u;
- yüksək riskli əməliyyat və təzə autentifikasiya nəticəsi;
- audit yazısının uğuru və ya uğursuzluğu.

## Metric qaydaları

Metric adları sabit, aşağı kardinal etiketlər istifadə edir. İlkin konseptual
adlar:

```text
esas_api_requests_total{route,method,status_class}
esas_api_request_duration_seconds{route,method}
esas_replay_sessions{state,mode}
esas_replay_events_processed_total{mode}
esas_replay_batch_duration_seconds{mode}
esas_replay_worker_heartbeat_age_seconds
esas_replay_interruptions_total{category}
esas_sqlite_operations_total{operation,result}
esas_sqlite_operation_duration_seconds{operation}
esas_sqlite_busy_retries_total{operation}
esas_quality_reports_total{status,rule_version}
esas_quality_findings_total{severity,rule_id,rule_version}
esas_auth_attempts_total{result}
esas_authorization_decisions_total{permission,result}
esas_security_audit_writes_total{result}
esas_alerts{severity,state,category}
```

Metric label-larında aşağıdakılar olmaz:

- tam `session_id`, `event_id`, user code və correlation ID;
- parol, token, cookie və Bridge açarı;
- xam SQL, lokal yol və traceback;
- sərbəst istifadəçi mətni;
- limitsiz simvol və ya xəta mesajı.

Sessiya və request səviyyəli araşdırma strukturlaşdırılmış log və audit izi ilə
aparılır, metric label-i ilə deyil.

## Strukturlaşdırılmış log

Phase 2 log sətri maşın tərəfindən oxunan strukturda ən azı bunları daşıyır:

- UTC timestamp;
- log level;
- komponent;
- hadisə adı;
- təhlükəsiz error category;
- correlation ID;
- varsa qısaldılmamış, amma məxfi olmayan qeyri-şəffaf resurs ID-si;
- müddət və say kimi təhlükəsiz ölçülər;
- nəticə.

İstifadəçiyə göstərilən mətn Azərbaycan dilində ola bilər, lakin daxili
`event_name` və `error_category` sabit maşın kodudur.

Log parol, token, cookie, Bridge açarı, xam tick payload-ı, xam SQL, tam lokal yol
və idarə olunmamış traceback saxlamır. Daxili exception təhlükəsiz kateqoriyaya
çevrilir; detallı araşdırma yalnız məhdud lokal debug sübutunda və açıq
administrator qərarı ilə aparılır.

## Correlation ID

- Hər API sorğusuna backend tərəfindən correlation ID verilir.
- Müştərinin göndərdiyi ID yalnız format və uzunluq yoxlamasından sonra qəbul
  edilə bilər; əks halda yenisi yaradılır.
- Cavab təhlükəsiz correlation ID-ni başlıqda qaytarır.
- Eyni əməliyyatın API logu, worker əmri və audit sətri bu ID ilə əlaqələndirilir.
- Correlation ID autentifikasiya nişanı və idempotency açarı deyil.

## Xəta kateqoriyaları

Kateqoriya kodu təhlükəsiz və sabitdir; exception mətni API müqaviləsi deyil.

### Replay

| Kod | Mənası | İlkin təsir |
| --- | --- | --- |
| `REPLAY_INVALID_INPUT` | giriş müqaviləsi pozulub | sorğu rədd edilir |
| `REPLAY_CURSOR_INVALID` | cursor pozulub və ya uyğun deyil | sorğu rədd edilir |
| `REPLAY_STATE_CONFLICT` | vəziyyət keçidi qanunsuzdur | əməliyyat rədd edilir |
| `REPLAY_IDEMPOTENCY_CONFLICT` | açar fərqli body ilə təkrar istifadə edilib | əməliyyat rədd edilir |
| `REPLAY_DATASET_CHANGED` | fingerprint əvvəlki dataset-lə uyğun deyil | sessiya dayandırılır |
| `REPLAY_CHECKPOINT_FAILED` | checkpoint atomik yazılmayıb | batch qəbul edilmir |
| `REPLAY_WORKER_INTERRUPTED` | worker işi yarımçıq qalıb | sessiya interrupted olur |
| `REPLAY_WORKER_STALLED` | running sessiyada progress dayanıb | araşdırma tələb olunur |

### Database

| Kod | Mənası | İlkin təsir |
| --- | --- | --- |
| `DB_UNAVAILABLE` | database əlçatan deyil | əməliyyat müvəqqəti rədd edilir |
| `DB_BUSY_RETRYING` | təhlükəsiz retry davam edir | degraded ola bilər |
| `DB_BUSY_EXHAUSTED` | retry limiti bitib | əməliyyat `503` alır |
| `DB_TRANSACTION_ROLLBACK` | transaction tam rollback olunub | qismən nəticə qəbul edilmir |
| `DB_INTEGRITY_FAILED` | quick check və ya fingerprint keçməyib | kritik bloklama |
| `DB_MIGRATION_FAILED` | migration tamamlanmayıb | rollback/restore tələb olunur |
| `DB_BACKUP_FAILED` | məcburi backup sübutu yaranmayıb | migration başlamır |

### Məlumat keyfiyyəti

| Kod | Mənası | İlkin təsir |
| --- | --- | --- |
| `QUALITY_REPORT_FAILED` | analiz terminal nəticə yarada bilməyib | hesabat failed olur |
| `QUALITY_RULE_UNSUPPORTED` | tələb olunan qayda versiyası yoxdur | analiz başlamır |
| `QUALITY_DATASET_CHANGED` | hesabat dataset izi dəyişib | nəticə qəbul edilmir |

DQ-001–DQ-010 tapıntıları xəta kateqoriyası deyil; onlar ayrıca versiyalanmış
məlumat keyfiyyəti nəticələridir.

### Təhlükəsizlik və audit

| Kod | Mənası | İlkin təsir |
| --- | --- | --- |
| `AUTH_INVALID_SESSION` | sessiya yoxdur, səhvdir və ya bitib | `401` |
| `AUTH_PERMISSION_DENIED` | permission kifayət deyil | `403` |
| `AUTH_RATE_LIMITED` | giriş limiti aşılıb | `429` |
| `AUTH_REAUTH_REQUIRED` | yüksək riskli əməl üçün təzə giriş yoxdur | əməliyyat rədd edilir |
| `AUDIT_WRITE_FAILED` | məcburi audit sətri yazılmayıb | əməliyyat fail-closed dayanır |

## Heartbeat və stall qaydası

- `running` replay worker ən gec 10 saniyədə bir heartbeat yeniləyir.
- Uğurlu heartbeat olub progress-in qısa müddət dəyişməməsi dərhal xəta deyil;
  uzun database əməliyyatı ayrıca ölçülür.
- Heartbeat yaşı `> 30 saniyə` iki ardıcıl yoxlamada qalarsa `degraded` olur.
- Heartbeat yaşı `> 60 saniyə` olarsa `REPLAY_WORKER_STALLED` xəbərdarlığı açılır
  və sessiya avtomatik uğurlu sayılmır.
- Backend restartında əvvəlki `running` sessiya müqaviləyə uyğun `interrupted`
  olur; səssiz resume edilmir.

## Xəbərdarlıq səviyyələri

### `info`

İstifadəçinin bilməli olduğu, amma müdaxilə tələb etməyən vəziyyət:

- replay tamamlandı;
- keyfiyyət hesabatı `review` oldu;
- planlı worker restartı sessiyanı `interrupted` etdi.

### `warning`

İş davam edir, lakin araşdırma tələb olunur:

- worker heartbeat 30 saniyədən çox gecikir;
- 5 dəqiqədə 5-dən çox SQLite busy retry yaranır;
- API `p95` latency performans müqaviləsi həddini iki ölçü pəncərəsində keçir;
- keyfiyyət analizi gözlənilən müddəti keçir;
- permission rəddlərinin sayı baseline-dan aydın yüksəlir.

### `critical`

Bütövlük, audit və ya təhlükəsizlik riski:

- `REPLAY_DATASET_CHANGED`;
- `DB_INTEGRITY_FAILED`;
- `DB_MIGRATION_FAILED` və təhlükəsiz rollback sübutu yoxdur;
- `AUDIT_WRITE_FAILED`;
- checkpoint və audit atomikliyi pozulur;
- xam tick dəyişiklik qadağası pozulmağa cəhd edilir;
- davam edən həll edilməmiş database yazma xətası məlumat qəbuluna təsir edir.

Keyfiyyət hesabatındakı `critical` tapıntı platforma səviyyəli `critical`
nasazlıqla eyni deyil. Frontend bunları “Məlumat keyfiyyəti” və “Platforma
sağlamlığı” sahələrində ayrı göstərir.

## Xəbərdarlığın həyat dövrü

```text
open -> acknowledged -> resolved
  \--------------------> resolved
```

- `open`: şərt hazırda mövcuddur;
- `acknowledged`: səlahiyyətli istifadəçi hadisəni gördüyünü təsdiqləyib;
- `resolved`: ölçülən şərt artıq yoxdur və bərpa meyarı keçib.

Təsdiq:

- sayğacı sıfırlamır;
- hadisəni silmir;
- severity-ni dəyişmir;
- problemi həll olunmuş göstərmir;
- istifadəçi, rol, UTC vaxtı və şərhlə audit olunur.

Eyni səbəb və resurs üçün mövcud açıq xəbərdarlıq yenilənir; hər polling dövrü yeni
xəbərdarlıq yaratmır. Problem həll olunub sonra təkrar yaranarsa yeni occurrence
açılır və əvvəlki tarixçə qorunur.

## Açılma və bağlanma sabitliyi

- Ani, bərpa olunan warning üçün iki ardıcıl pozuntu tələb olunur.
- Kritik bütövlük və audit xətası ilk hadisədə dərhal açılır.
- Warning yalnız üç ardıcıl sağlam yoxlamadan sonra avtomatik `resolved` olur.
- Kritik xəbərdarlıq yalnız səbəb aradan qalxdıqdan və uyğun bütövlük yoxlaması
  keçdikdən sonra `resolved` olur.
- Manual təsdiq avtomatik resolution meyarını əvəz etmir.

Bu qayda statusun yaşıl-qırmızı arasında tez-tez dəyişməsinin qarşısını alır.

## Operational API

Phase 2 detalı yalnız qorunan endpoint-dən alınır:

```text
GET /status/phase2
GET /alerts?state=open&cursor=...&page_size=...
GET /alerts/{alert_id}
POST /alerts/{alert_id}/acknowledge
```

`/health` minimum servis və database hazırlığını göstərməyə davam edir və məxfi
detal qaytarmır. `/status/operational` mövcud Phase 1 axınını qoruyur.

`/status/phase2` konseptual olaraq qaytarır:

- ümumi platforma sağlamlığı;
- replay sessiyalarının vəziyyət üzrə sayı;
- worker heartbeat və son progress;
- SQLite vəziyyəti və son integrity check;
- keyfiyyət analizlərinin xülasəsi;
- açıq warning və critical sayı;
- ölçülərin `observed_at` UTC vaxtı.

Alert siyahısı cursor ilə səhifələnir. Frontend severity hesablamır və backend
statusunu yenidən şərh etmir.

## Frontend davranışı

- Platforma sağlamlığı, replay vəziyyəti və məlumat keyfiyyəti ayrı kartlarda
  göstərilir.
- Rəng heç vaxt yeganə göstərici deyil; mətn və ikon birlikdə istifadə olunur.
- “Canlı deyil” vəziyyəti son uğurlu məlumatı saxlayır, amma onu cari göstərmir.
- Hər xəbərdarlıq səbəb, ilk/son görülmə vaxtı, təsir və təhlükəsiz növbəti addımı
  göstərir.
- Təsdiq düyməsi yalnız access-control müqaviləsində icazəli rola görünür.
- Kritik xəbərdarlıq təsdiqlənsə də kritik olaraq görünməyə davam edir, yalnız
  “Təsdiqlənib” əlavəsi alır.
- Ekranda xam exception, SQL, lokal yol, token və traceback göstərilmir.

İlkin versiya yalnız panel daxili xəbərdarlıq yaradır. E-poçt, SMS, Slack və başqa
xarici kanal ayrıca konfiqurasiya, rate-limit, məxfilik və çatdırılma müqaviləsi
olmadan avtomatik aktiv edilmir.

## Saxlama

- Metric retention deploy mühitinə görə konfiqurasiya edilir və sənədləşdirilir.
- Alert occurrence və təsdiq auditi avtomatik silinmir.
- Operational log üçün ilkin hədəf 30 gündür; disk limiti və təhlükəsiz rotasiya
  implementasiyadan əvvəl ölçülür.
- Təhlükəsizlik auditi, replay auditi və qəbul sübutu adi debug log retention-u
  ilə silinmir.
- Retention xam tick qoruma siyasətini dəyişmir.

## Fail-closed qaydaları

Aşağıdakı hallarda dəyişdirici Phase 2 əməliyyatı uğurlu qaytarılmır:

- məcburi audit sətri yazılmır;
- checkpoint və audit eyni transaction-da bağlanmır;
- dataset fingerprint uyğun gəlmir;
- database integrity yoxlaması uğursuzdur;
- permission qərarı müəyyən edilə bilmir.

Monitorinq sisteminin öz metric ixracının müvəqqəti dayanması xam tick qəbulunu
avtomatik dayandırmır. Lakin bu hal `degraded` kimi görünür və audit tələb edən
əməliyyatların fail-closed qaydasını zəiflətmir.

## Qəbul testləri

1. Platforma, replay və məlumat keyfiyyəti statusları ayrı hesablanır.
2. `paused`, `completed` və user-cancelled sessiya nasazlıq yaratmır.
3. DQ gap namizədi avtomatik platforma xətası və məlumat itkisi olmur.
4. Running worker heartbeat qaydaları 30 və 60 saniyə hədlərində deterministikdir.
5. Eyni davam edən səbəb hər polling dövründə yeni alert yaratmır.
6. Warning üç sağlam yoxlamadan əvvəl avtomatik bağlanmır.
7. Audit və integrity xətası ilk hadisədə critical açır.
8. Alert təsdiqi sayğacı və severity-ni dəyişmir.
9. Problem təkrar yarananda yeni occurrence yaranır, əvvəlki audit qorunur.
10. Metric label-larında yüksək kardinal və məxfi məlumat yoxdur.
11. Log və API cavabında parol, token, cookie, Bridge açarı, xam SQL və traceback
    görünmür.
12. Correlation ID API, worker və audit hadisəsini əlaqələndirir, amma
    autentifikasiya kimi istifadə edilmir.
13. Audit yazısı uğursuz olarsa dəyişdirici əməliyyat uğurlu sayılmır.
14. Frontend backend severity-sini yenidən hesablamır.
15. İcazəsiz alert detalı və təsdiqi access-control müqaviləsinə uyğun rədd olunur.
16. Backend əlçatan olmadıqda son məlumat “canlı” kimi göstərilmir.
17. Bütün testlər sintetik müvəqqəti bazada işləyir və production bazasına
    toxunmur.

## Phase 2 icra ardıcıllığındakı yeri

1. Sabit metric, log event və error category kataloqu.
2. Correlation ID middleware-i və təhlükəsiz strukturlaşdırılmış log.
3. Worker heartbeat və progress ölçüləri.
4. SQLite, replay, quality və auth metric-ləri.
5. Alert qiymətləndiricisi və occurrence həyat dövrü.
6. Qorunan operational və alert API-ləri.
7. Frontend sağlamlıq və xəbərdarlıq görünüşü.
8. Sintetik failure-injection və qəbul testləri.

Bu sənədin hazırlanması Phase 2 istehsal kodunun başladılması demək deyil.
