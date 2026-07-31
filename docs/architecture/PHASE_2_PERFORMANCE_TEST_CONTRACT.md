# ESAS Platform — Phase 2 performans və yaddaş sınağı müqaviləsi

Status: DESIGN READY — NOT IMPLEMENTED  
Başlama şərti: Phase 1 qəbul qapılarının tamamlanması

## Məqsəd

Replay, məlumat keyfiyyəti, SQLite və frontend işlərinin sürətini, yaddaş
istifadəsini və sabitliyini təkrarlana bilən üsulla ölçmək.

Bu müqavilə performans naminə məlumat bütövlüyünün, deterministik nəticənin,
audit izinin və təhlükəsizliyin zəiflədilməsinə icazə vermir.

## Dəyişməz təhlükəsizlik sərhədi

- Canlı `database/ESAS_PLATFORM.sqlite` üzərində yük, stress, migration və ya
  dağıdıcı sınaq aparılmır.
- Hər sınaq ayrıca müvəqqəti SQLite bazası və ayrıca nəticə qovluğu istifadə edir.
- Sintetik məlumat generatoru sabit seed, event müqaviləsi versiyası və generator
  versiyası ilə işləyir.
- Sınaq nəticələrində məxfi açar, parol, cookie, token və istifadəçinin həssas
  lokal yolları saxlanmır.
- Ölçmədən əvvəl və sonra event sayı, deterministik sıra və dataset fingerprint-i
  müqayisə edilir.
- Sürət qapısını keçib bütövlük qapısını keçməyən nəticə uğursuz sayılır.

## Referans məlumat dəstləri

| Səviyyə | Event sayı | İstifadə yeri |
| --- | ---: | --- |
| Kiçik | 10 000 | hər pull request üçün smoke sınağı |
| Orta | 100 000 | planlı və manual inteqrasiya sınağı |
| Böyük | 1 000 000 | release və performans qəbul qapısı |
| Stress | 5 000 000 | yalnız manual tutum araşdırması |

Generator ən azı üç simvol, eyni timestamp-li event-lər, müxtəlif tick
sürətləri və ayrıca işarələnmiş keyfiyyət pozuntusu fixture-ləri yaradır.
Etibarlı dataset və pozuntu dataset-i qarışdırılmır.

Hər nəticə ilə bunlar qeyd olunur:

- Git commit və müqavilə versiyası;
- əməliyyat sistemi, CPU, RAM, Python, Node və SQLite versiyası;
- dataset səviyyəsi, seed, event sayı və fingerprint;
- cold və warm run işarəsi;
- icra sayı və tamamlanma vaxtı.

## Ölçmə qaydası

- Hər əsas workload ən azı 5 dəfə icra edilir.
- İlk cold run ayrıca, sonrakı warm run-lar ayrıca göstərilir.
- Latency üçün `p50`, `p95`, `p99` və maksimum dəyər saxlanır.
- Throughput saniyədə tam işlənmiş event sayı ilə ölçülür.
- Yaddaş üçün idle səviyyəsi və prosesin peak RSS artımı saxlanır.
- Uğursuz və kənar nəticələr silinmir; səbəbi ilə birlikdə hesabatda qalır.
- Baseline eyni maşında, eyni dataset və eyni konfiqurasiya ilə yaradılır.

## Workload-lar

### PF-01 — Replay səhifə oxuması

- `250` və `1000` event səhifə ölçüləri;
- intervalın ilk, orta və son cursor-u;
- cold və warm sorğular;
- `(symbol, event_timestamp, event_id)` indeksli və nəzarət müqayisəsi.

Qəbul:

- hər səhifədə sıra və fingerprint dəyişməzdir;
- 1 milyon eventlik referans bazada warm `1000`-lik səhifə `p95 <= 500 ms`;
- səhifələmə zamanı peak RSS artımı dataset ölçüsü ilə xətti böyümür.

### PF-02 — Dataset fingerprint

- fingerprint bütün payload-ı RAM-a yükləmədən streaming üsulla hesablanır;
- iki eyni dataset eyni, bir event dəyişmiş dataset fərqli nəticə verir.

Qəbul:

- 1 milyon event üçün peak RSS artımı `<= 128 MiB`;
- nəticə səhifə ölçüsündən asılı deyil.

### PF-03 — Addım replay

`1`, `10`, `100` və `1000` event addımları ayrıca ölçülür.

Qəbul:

- checkpoint və audit hər addımdan sonra düzgündür;
- warm `1000` event addımı `p95 <= 750 ms`;
- təkrar idempotency əmri əlavə event işlətmir.

### PF-04 — Maksimum sürətli replay

- daxili batch ölçüsü maksimum `1000`;
- bütün event-lər deterministik ardıcıllıqla işlənir;
- 30 dəqiqəlik sintetik endurance run ayrıca aparılır.

Qəbul:

- referans maşında ilkin minimum throughput `5 000 event/s`;
- itən, təkrarlanan və ya sırası dəyişən event sayı `0`;
- böyük/orta dataset peak RSS nisbəti `<= 1.5`;
- restart və resume son fingerprint-i dəyişmir.

Throughput həddi ilk real implementasiya nəticəsində ölçülüb əsaslandırıldıqdan
sonra sərtləşdirilə bilər; bütövlük meyarları dəyişdirilə bilməz.

### PF-05 — Məlumat keyfiyyəti analizi

- bütün versiyalanmış keyfiyyət qaydaları birlikdə işlədilir;
- etibarlı və pozuntulu fixture-lərin gözlənilən sayları əvvəlcədən məlumdur.

Qəbul:

- qayda nəticələrinin səhv müsbət və səhv mənfi sayı `0`;
- 1 milyon event `<= 120 s`;
- peak RSS artımı `<= 256 MiB`;
- hesabat fingerprint-i təkrar icrada eynidir.

### PF-06 — Paralel yazma və replay oxuması

Canlı axına bənzər yazma yalnız sintetik müvəqqəti bazada replay oxuması ilə
paralel simulyasiya edilir.

Qəbul:

- yazılmış və oxunmuş event itkisi `0`;
- retry-lərdən sonra həll edilməmiş `SQLITE_BUSY` və API `503` sayı `0`;
- yazma `p95` latency-si eyni maşındakı yazma-only baseline-dan 2 dəfədən çox
  pisləşmir;
- replay oxuması xam event-ləri dəyişdirmir.

### PF-07 — Migration və indeks

- online backup, migration, indeks qurulması və rollback yalnız sintetik bazada;
- migration-dan əvvəl və sonra event sayı və fingerprint müqayisə edilir.

Qəbul:

- məlumat itkisi və dəyişmiş xam payload sayı `0`;
- uğurlu migration gözlənilən schema versiyasını yazır;
- qəsdən yaradılmış uğursuzluq təhlükəsiz rollback və ya sənədləşdirilmiş
  backup restore ilə bərpa olunur;
- indeksin disk ölçüsü, qurulma vaxtı və replay latency təsiri hesabatlanır.

### PF-08 — Qorunan API

- login, sessiya yoxlaması, replay list/detail/control və keyfiyyət hesabatı;
- icazəsiz və vaxtı bitmiş sessiya sınaqları performans nəticəsinə qarışdırılmır.

Qəbul:

- icazəsiz sorğular məlumat qaytarmır;
- list endpoint-i tick payload-larını daxil etmir;
- böyük cavablar cursor ilə səhifələnir;
- warm read endpoint-ləri üçün `p95 <= 750 ms`.

### PF-09 — Frontend

- production build ölçüsü;
- login, sessiya siyahısı, sessiya detalı və keyfiyyət hesabatının render-i;
- running sessiya üçün 2 saniyəlik, paused/interrupted sessiya üçün 10 saniyəlik
  polling;
- gizli brauzer tabında sorğuların dayanması.

Qəbul:

- route JavaScript ölçüsü təsdiqlənmiş baseline-dan `20%` çox artmır;
- siyahı bütün tick payload-larını brauzerə yükləmir;
- böyük hesabat bölmələri lazy açılır;
- eyni refresh dövründə üst-üstə düşən status sorğusu yaradılmır;
- frontend lint, production build və render testləri keçir.

## Avtomatlaşdırma pillələri

### Pull request

- 10 000 event smoke dataset;
- deterministik sıra və fingerprint;
- bir replay səhifəsi və addım sınağı;
- kiçik keyfiyyət fixture-i;
- backend testləri, frontend lint/build/render.

### Planlı və manual

- 100 000 event inteqrasiya dəsti;
- paralel yazma/oxuma;
- restart/resume;
- migration və rollback.

### Release qəbul qapısı

- 1 000 000 eventlik bütün workload-lar;
- 30 dəqiqəlik endurance;
- baseline müqayisəsi və ölçü hesabatı;
- bütün bütövlük və təhlükəsizlik qapıları.

5 milyon eventlik stress sınağı release qapısı deyil; tutum planlaması üçün
ayrıca manual sübutdur.

## Sübut formatı

Nəticə maşın tərəfindən oxunan JSON və insan üçün qısa Markdown xülasəsi kimi
saxlanır. JSON ən azı bunları daşıyır:

- `contract_version`;
- `commit_sha`;
- `dataset`;
- `environment`;
- `workload`;
- `runs`;
- `latency_ms`;
- `throughput_events_per_second`;
- `peak_rss_bytes`;
- `integrity`;
- `result`;
- `failures`.

Sübut faylları istehsal bazasını, xam məxfi payload-ları və autentifikasiya
məlumatını daşımır.

## Phase 2 performans qapısının tamamlanma meyarı

- PF-01–PF-09 üçün tələb olunan pillələr keçir.
- Bütün integrity nəticələri sıfır itki, sıfır dublikat və deterministik
  fingerprint göstərir.
- Performans hədləri referans mühit məlumatı ilə audit edilə bilir.
- Heç bir test canlı bazada aparılmayıb.
- Qəbul sübutu commit SHA və müqavilə versiyası ilə saxlanıb.
- Aşkarlanmış regressiya aradan qaldırılmadan release qapısı bağlanmır.

