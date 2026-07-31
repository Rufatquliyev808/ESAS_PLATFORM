# ESAS Platform — Phase 3 tədqiqat və statistik validasiya müqaviləsi

Versiya: 1.0  
Status: **DESIGN READY — NOT IMPLEMENTED**  
Tətbiq şərti: Phase 1 və Phase 2 qəbul qapılarının uğurla bağlanması

## Məqsəd

Bu müqavilə statistik analiz, pattern, texniki analiz və gələcək AI modellərinin
necə araşdırılacağını və hansı sübutdan sonra növbəti mərhələyə keçə biləcəyini
müəyyən edir.

Məqsəd əvvəlcədən seçilmiş strategiyanı təsdiqləmək deyil. Məqsəd təsadüfi,
overfit və ya məlumat sızması ilə yaranan nəticələri erkən rədd etməkdir.

Bu mərhələ:

- siqnalı real orderə çevirmir;
- brokerə əmr göndərmir;
- xam tick məlumatını dəyişmir;
- gəlir və ya uğurlu treyd zəmanəti vermir;
- yalnız audit edilə bilən tədqiqat sübutu yaradır.

## Tədqiqat obyektləri

Eyni validasiya qaydaları bunlara tətbiq olunur:

- volatilite, spread, həcm və sessiya statistikası;
- bazar rejimi aşkarlanması;
- texniki indikator və pattern namizədləri;
- klassik maşın öyrənməsi və Visual AI modelləri;
- qayda, model və ansambl müqayisələri;
- gələcək qərar moduluna namizəd olan hər nəticə.

## Eksperiment qeydiyyatı

Hər eksperiment hesablamadan əvvəl dəyişməz qeydiyyat alır:

- unikal `experiment_id` və correlation ID;
- hipotez və onun iqtisadi/məntiqi izahı;
- əsas və ikinci dərəcəli metric-lər;
- dataset fingerprint-i, simvollar və UTC zaman sərhədləri;
- feature, label, horizon və qərar vaxtı;
- train, validation və toxunulmaz test bölgüsü;
- baseline və müqayisə ediləcək alternativlər;
- komissiya, spread, slippage və gecikmə fərziyyələri;
- statistik test, confidence interval və multiple-testing siyasəti;
- qəbul/rədd hədləri və dayandırma qaydası;
- kod, konfiqurasiya, seed və mühit versiyası;
- sahibi, modul həyat dövrü statusu və yaradılma vaxtı.

Hesablama başladıqdan sonra hipotez və əsas qəbul meyarı dəyişdirilmir. Dəyişiklik
yeni eksperiment versiyası yaradır.

## Məlumat sərhədi və sızmanın qarşısı

Məlumat həmişə zaman ardıcıllığı ilə bölünür. Təsadüfi shuffle time-series üçün
standart seçim deyil.

- feature yalnız qərar anında real mövcud olan məlumatdan yaranır;
- gələcək tick, gələcək bar, sessiyanın son nəticəsi və test statistikası feature-a
  daxil edilmir;
- scaler, normalization, feature selection və model yalnız train hissəsində fit
  edilir;
- validation model və parametr seçimi üçündür;
- toxunulmaz test hissəsi yalnız yekun namizəd üçün bir dəfə açılır;
- eyni hadisənin və ya üst-üstə düşən label horizon-un müxtəlif bölgülərə keçməsi
  purge/embargo ilə bloklanır;
- düzəldilmiş və ya sonradan məlum olmuş xarici məlumat point-in-time versiyası
  olmadan istifadə edilmir.

Sızma aşkarlanarsa nəticə avtomatik etibarsız sayılır və düzəliş yeni eksperiment
kimi başlanır.

## Dataset bölgüsü

Konkret tarixlər məlumat mövcudluğuna görə əvvəlcədən qeyd olunur. Minimum quruluş:

1. `train`: model və parametr öyrənməsi;
2. `validation`: seçim və kalibrasiya;
3. `holdout test`: yekun, toxunulmaz qiymətləndirmə;
4. `walk-forward`: müxtəlif bazar dövrlərində ardıcıl out-of-sample pəncərələr.

Tək dövrün nəticəsi kifayət deyil. Nəticə mümkün olduqda müxtəlif volatilite,
likvidlik, sessiya və bazar rejimlərində ayrıca göstərilir.

## Baseline və ablation

Hər namizəd ən azı bunlarla müqayisə edilir:

- fəaliyyətsiz/no-signal baseline;
- sadə və əvvəlcədən müəyyən edilmiş qayda;
- təsadüfi, lakin eyni tezlik və risk profilli baseline;
- mövcud ən sadə etibarlı model, əgər varsa.

Mürəkkəb model sadə baseline-ı xərclərdən sonra və out-of-sample məlumatda aydın
keçmirsə növbəti mərhələyə getmir. Feature və komponentlərin real töhfəsi ablation
testi ilə ölçülür.

## Metric müqaviləsi

Əsas metric hipotezdən əvvəl seçilir. Tək metric nəticəni qəbul etmək üçün kifayət
deyil. Uyğun olduqda aşağıdakılar birlikdə verilir:

- müşahidə sayı və effektiv müstəqil nümunə sayı;
- effect size və confidence interval;
- out-of-sample gəlir, drawdown və riskə uyğunlaşdırılmış nəticə;
- hit rate ilə yanaşı qazanc/zərər paylanması və tail risk;
- turnover, siqnal tezliyi və mövqe müddəti;
- spread, komissiya, slippage və gecikmədən sonrakı nəticə;
- stabillik: zaman, simvol, sessiya və rejim üzrə dispersiya;
- modeldirsə calibration, precision/recall və uyğun səhv metric-ləri.

Yalnız p-value əsasında qərar verilmir. Praktik əhəmiyyət və uncertainty açıq
göstərilir.

## Multiple testing və selection bias

Sınaqdan keçirilən bütün hipotez, feature, parametr və model variantları reyestrdə
sayılır. Yalnız uğurlu nəticələri saxlamaq qadağandır.

- əvvəlcədən təyin edilmiş primary hipotez ayrıca göstərilir;
- çoxsaylı müqayisələr üçün uyğun FDR və ya ailəvi xəta düzəlişi tətbiq olunur;
- parameter sweep nəticəsində ən yaxşı nöqtə ilə yanaşı bütün səth saxlanır;
- eyni holdout-a təkrar baxış onun statusunu validation-a endirir və yeni holdout
  tələb edir;
- dayandırılmış və uğursuz eksperimentlər də səbəbi ilə arxivləşdirilir.

## Backtest reallıq sərhədi

Backtest yalnız qərar anında əldə edilə bilən qiymət və məlumatla işləyir:

- order qiyməti gələcək barın əlverişli nöqtəsindən seçilmir;
- spread və komissiya heç vaxt sıfır fərz edilmir, yalnız sübut varsa dəyişir;
- slippage və gecikmə üçün normal, pis və stress ssenarisi göstərilir;
- likvidlik və həcm məlum deyilsə icra qabiliyyəti iddia edilmir;
- eyni anda açılan siqnallar kapital və risk məhdudiyyətini paylaşır;
- missing tick, bazar bağlanması və data-quality tapıntıları gizlədilmir;
- survivorship və symbol-selection bias ayrıca qiymətləndirilir.

## Reproducibility

Eyni eksperiment eyni fingerprint, kod, konfiqurasiya və seed ilə eyni nəticəni
verməlidir. Sübut paketində ən azı bunlar olur:

- input və output checksum-ları;
- dataset və qayda versiyaları;
- Git commit-i və asılılıq lock hash-i;
- seed və deterministik icra parametrləri;
- train/validation/test sərhədləri;
- metric-lərin maşın-oxunaqlı tam nəticəsi;
- xəbərdarlıq, rədd və istisnaların audit izi.

## Qəbul qapıları

Namizəd yalnız bütün qapıları keçərsə EXPERIMENTAL-dan SHADOW hazırlığına keçə
bilər:

1. dataset və kod təkrar istehsal edilə bilir;
2. data-quality və leakage yoxlamaları keçir;
3. əvvəlcədən seçilmiş primary metric holdout-da həddi keçir;
4. confidence interval praktik faydanı dəstəkləyir;
5. multiple-testing düzəlişindən sonra nəticə qalır;
6. xərclər və stress slippage-dan sonra sadə baseline-ı keçir;
7. walk-forward pəncərələrinin nəticəsi tək dövrdən asılı deyil;
8. risk, drawdown və tail göstəriciləri qəbul həddindədir;
9. nəticə ən azı uyğun rejimlər üzrə izah edilə bilir;
10. uğursuzluqlar, məhdudiyyətlər və istifadə sərhədi açıq yazılıb;
11. müstəqil təkrar icra eyni yekunu verir;
12. review qərarı və bütün sübutlar append-only auditdədir.

Bir qapının keçməməsi nəticəni gizlətmir: namizəd rədd edilir və eksperiment
ARCHIVED vəziyyətində öyrənmə sübutu kimi saxlanır.

## AI və Visual AI üçün əlavə qapılar

- dataset lineage və label yaratma prosesi tam versiyalanır;
- train/validation/test görüntüləri eyni zaman hadisəsindən törəyə bilməz;
- model ölçüsü, latency və resurs istifadəsi baseline ilə müqayisə olunur;
- feature importance və ya uyğun izah üsulu qərarın auditinə əlavə edilir;
- confidence aşağı və ya input paylanmadan kənardadırsa model abstain edir;
- model faylı checksum və imza ilə qorunur;
- prompt, xarici model və ya üçüncü tərəf servisi istifadə olunursa versiya,
  məxfilik və determinism məhdudiyyəti ayrıca qeyd edilir.

## Modul həyat dövrü

Bu müqavilənin keçilməsi birbaşa ACTIVE və real ticarət icazəsi deyil.

`IDEA → EXPERIMENTAL → SHADOW → ACTIVE → REVIEW → ARCHIVED`

Phase 3 nəticəsi ən çox SHADOW hazırlığına namizəd yaradır. Real order yalnız sonrakı
Decision, Risk, SHADOW və məhdud icra mərhələlərinin ayrıca qəbulundan sonra mümkün
ola bilər.

## Avtomatlaşdırılmış qəbul sınaqları

Tətbiq başlamazdan əvvəl sintetik məlumatla aşağıdakılar yoxlanır:

1. gələcək məlumat feature-a daxil ediləndə leakage testi işi rədd edir;
2. train-də fit edilməmiş preprocessing artefaktı qəbul edilmir;
3. üst-üstə düşən horizon purge/embargo olmadan bölgülərə keçmir;
4. holdout-un ikinci açılışı audit olunur və statusu endirir;
5. multiple-testing düzəlişi olmadan çoxsaylı namizəd qəbul edilmir;
6. komissiya və slippage çıxılmadan yekun nəticə yayımlanmır;
7. eyni seed və fingerprint eyni nəticəni verir;
8. uğursuz eksperiment reyestrdən silinmir;
9. zəif baseline müqayisəsi SHADOW namizədliyini bloklayır;
10. heç bir nəticə siqnal, order və broker əməliyyatı yaratmır.

Bu sənəd tədqiqatın təhlükəsiz elmi sərhədidir; model və ya strategiya seçimi deyil.
