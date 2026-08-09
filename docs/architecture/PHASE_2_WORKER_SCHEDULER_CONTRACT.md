# ESAS Platform — Phase 2 worker və scheduler müqaviləsi

Versiya: 1.0  
Status: **IMPLEMENTED — job növbəsi, worker, claim/lease/fencing/retry və frontend job-queue səthi tamamlanıb**  
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

## Məqsəd

Bu müqavilə replay, məlumat keyfiyyəti, sübut ixracı və texniki xidmət işlərinin
necə növbəyə alınacağını, yalnız bir worker tərəfindən icra ediləcəyini, xəta və
restart zamanı necə bərpa olunacağını müəyyən edir.

Phase 2 scheduler-i:

- Phase 1 tick qəbulunu və SQLite yazmasını həmişə üstün tutur;
- MT5 Bridge-in davamlı disk növbəsindən tamamilə ayrıdır;
- heç bir siqnal, qərar, order və broker əməliyyatı yaratmır;
- səssiz məlumat itkisinə və eyni checkpoint-in paralel yazılmasına icazə vermir;
- Phase 1 rəsmi qəbulundan əvvəl işə salınmır.

## Ayrı növbələr

MT5 Bridge disk növbəsi çatdırılmamış canlı tick hadisələrinin FIFO növbəsidir.
Phase 2 job növbəsi isə idarə olunan analiz və texniki xidmət tapşırıqları üçündür.
Onlar eyni faylı, tutumu, sayğacı və ya bərpa mexanizmini paylaşmır.

Phase 2 növbəsinin dolması canlı tick qəbulunu dayandıra bilməz. Yeni Phase 2 işi
qəbul edilə bilmədikdə API sabit `429` və ya `503` cavabı verir; iş səssiz atılmır.

## Dəstəklənən iş növləri

- `replay_session`: sabit snapshot üzərində replay sessiyasının icrası;
- `quality_scan`: məlumat keyfiyyəti qaydalarının paketlə yoxlanması;
- `evidence_export`: audit və qəbul sübutlarının dəyişdirilməz ixracı;
- `backup_verify`: backup manifesti və bərpa sübutunun yoxlanması;
- `retention_cleanup`: yalnız ayrıca açar və təsdiqdən sonra təhlükəsiz təmizləmə.

Restore əməliyyatı scheduler tərəfindən avtomatik başladılmır.

## Davamlı job yazısı

Hər iş verilənlər bazasında ən azı bu sahələrlə saxlanır:

- dəyişməz `job_id`, `job_type`, sahib istifadəçi və yaradılma vaxtı;
- prioritet, payload hash-i, idempotency hash-i və əlaqəli resurs ID-si;
- cari vəziyyət, cəhd sayı, maksimum cəhd və növbəti uyğun icra vaxtı;
- lease sahibi, lease sonu, fencing token və optimistic-lock versiyası;
- başlanma, heartbeat, bitmə vaxtları və sabit xəta kodu;
- correlation ID və append-only audit bağlantısı.

Payload daxilində secret, parol, token və ya şəxsi açar saxlanmır.

## Vəziyyət maşını

İcazəli vəziyyətlər:

`queued → claimed → running → completed`

Əlavə idarə olunan keçidlər:

- `running → pausing → paused → queued`;
- `running → retry_wait → queued`;
- `queued|claimed|running|paused → cancelled`;
- `claimed|running → interrupted → queued|failed`;
- `running|retry_wait → failed`.

Hər keçid atomik yazılır və audit olunur. Naməlum və ya icazəsiz keçid fail-closed
dayanır.

## Claim, lease və tək icraçı zəmanəti

Worker işi qısa atomik tranzaksiyada claim edir. Claim zamanı yeni monoton fencing
token yaradılır. Yalnız aktiv lease sahibi və ən son fencing token checkpoint,
progress və nəticə yaza bilər.

- heartbeat intervalı ən çox 10 saniyədir;
- 30 saniyə heartbeat olmadıqda worker degraded sayılır;
- 60 saniyə sonra lease bərpaya uyğun olur;
- köhnə worker sonradan qayıtsa belə stale fencing token ilə yaza bilməz;
- bir replay sessiyasının checkpoint-i eyni vaxtda yalnız bir worker tərəfindən
  dəyişdirilə bilər.

Lease vaxtı UTC ilə saxlanır, müddət hesabı üçün monoton saat istifadə olunur.

## Prioritet və ədalət

İşlər təhlükəsizlik və istifadəçi təsirinə görə növbələnir:

1. bütövlük və backup yoxlaması;
2. operatorun interaktiv replay əmri;
3. replay və məlumat keyfiyyəti işləri;
4. sübut ixracı;
5. retention və digər texniki xidmət.

Scheduler weighted-fair seçim və gözləmə yaşlanması tətbiq edir. Aşağı prioritetli
iş sonsuz gözləyə bilməz, bir istifadəçi bütün worker-ləri tuta bilməz. API
müqaviləsindəki bir istifadəçi üçün maksimum üç aktiv replay/keyfiyyət işi qorunur.

## Phase 1 resurs qoruması

SQLite tək-yazıcı məhdudiyyəti nəzərə alınır:

- hesablama tranzaksiyadan kənarda aparılır;
- yazma tranzaksiyası qısa və məhdud paketlə olur;
- checkpoint, nəticə xülasəsi və audit eyni atomik sərhəddə yazılır;
- database busy, tick gecikməsi, rədd sayı və disk təzyiqi artdıqda Phase 2
  avtomatik throttling və ya pause rejiminə keçir;
- disk təhlükə həddində retention istisna olmaqla yeni ağır iş claim edilmir;
- worker sayı yalnız təsdiqlənmiş konfiqurasiya həddində artırılır.

Phase 2 performansı naminə Phase 1-in durability və qəbul davranışı zəiflədilə
bilməz.

## Retry və zəhərli işlər

Yalnız müvəqqəti xətalar retry edilir. İlkin standart siyasət:

- maksimum 5 cəhd;
- 1 saniyədən başlayan eksponensial backoff və jitter;
- ən çox 60 saniyə gözləmə;
- validation, permission, fingerprint və dəyişməzlik xətalarında retry yoxdur.

Qeyri-müəyyən commit nəticəsində worker əvvəlcə idempotency yazısını və checkpoint-i
yoxlayır, sonra retry qərarı verir. Maksimum cəhdi keçən iş `failed` vəziyyətində
qorunur; payload və audit silinmir.

## Pause, cancel və təhlükəsiz shutdown

Pause və cancel kooperativdir. Worker aktiv tranzaksiyanın ortasında öldürülmür;
paket sərhədinə çatır, checkpoint və audit yazır, sonra dayanır.

Planlı shutdown zamanı scheduler:

1. yeni claim-ləri dayandırır və `draining` vəziyyətinə keçir;
2. aktiv paketi tamamlayır və ya təhlükəsiz rollback edir;
3. son heartbeat və audit yazır;
4. lease-i buraxır və ya işi `interrupted` edir.

## Restart və bərpa

Startup preflight-dan sonra yalnız lease-i bitmiş işlər bərpa edilir. Worker:

- snapshot fingerprint və dəyişməz parametrləri yenidən yoxlayır;
- son uğurlu checkpoint-dən davam edir;
- tamamlanmış paketi yenidən yazmır;
- bərpası təhlükəsiz olmayan işi avtomatik davam etdirmir, `failed` və ya manual
  review vəziyyətinə keçirir.

Checkpoint yalnız bütün paket uğurla bitdikdən sonra irəliləyir.

## Təhlükəsizlik

Job yaradılarkən və claim edilərkən istifadəçinin aktivliyi, rol və resurs icazəsi
yenidən yoxlanır. Yaradılma anındakı rol snapshot-u icra icazəsi hesab edilmir.
Worker yalnız öz iş növünə lazım olan minimal database və fayl icazəsi ilə işləyir.

## Müşahidə göstəriciləri

Ən azı bunlar ölçülür:

- növ, vəziyyət və prioritet üzrə queue depth;
- ən köhnə işin yaşı və claim gecikməsi;
- aktiv worker, lease yaşı və heartbeat gecikməsi;
- icra müddəti, paket sürəti, retry və failure sayı;
- stale fencing yazma cəhdi və recovery sayı;
- Phase 1 tick yazma gecikməsi, SQLite busy və disk təzyiqi;
- queue tutumu və rədd edilmiş yeni job sayı.

## Qəbul sınaqları

Tətbiq yalnız sintetik müvəqqəti baza üzərində bu sınaqlardan keçdikdən sonra hazır
sayılır:

1. iki worker eyni işi claim edə bilmir;
2. vaxtı keçmiş worker stale fencing token ilə yaza bilmir;
3. checkpoint-dən əvvəl və sonra qəza məlumatı nə itirir, nə də iki dəfə yazır;
4. retry yalnız müvəqqəti xətalarda və limit daxilində işləyir;
5. pause, cancel və graceful shutdown paket sərhədini qoruyur;
6. prioritet, istifadəçi ədaləti və starvation qoruması işləyir;
7. dolu Phase 2 növbəsi işi rədd edir, Phase 1 tick qəbuluna toxunmur;
8. paralel yük altında Phase 1 sağlamlıq və durability qapıları yaşıl qalır;
9. restart yalnız fingerprint-i uyğun təhlükəsiz işi checkpoint-dən davam etdirir;
10. log, metric və audit daxilində secret yoxdur.

Bu sənəd icra icazəsi deyil. Worker və scheduler yalnız Phase 1 rəsmi qəbulundan,
migration preflight-dan və ayrıca feature flag təsdiqindən sonra aktivləşdirilə bilər.
