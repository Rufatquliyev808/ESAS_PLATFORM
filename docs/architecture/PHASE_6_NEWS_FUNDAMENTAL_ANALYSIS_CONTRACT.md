# ESAS Platform — Phase 6 xəbər və fundamental analiz müqaviləsi

Versiya: 1.0  
Status: **DESIGN READY — NOT IMPLEMENTED**  
Tətbiq şərti: Phase 1–5 qəbul qapılarının uğurla bağlanması

Əlaqəli müqavilələr:

- `docs/constitution/EVENT_CONTRACT.md`
- `docs/architecture/PHASE_3_RESEARCH_VALIDATION_CONTRACT.md`
- `docs/architecture/PHASE_3_STATISTICAL_ANALYSIS_CONTRACT.md`
- `docs/architecture/PHASE_4_PATTERN_TECHNICAL_ANALYSIS_CONTRACT.md`

## Məqsəd və sərhəd

Bu müqavilə xəbərlərin, iqtisadi təqvim hadisələrinin və fundamental göstəricilərin
necə toplanacağını, zamanla uyğunlaşdırılacağını, dəyişməz saxlanacağını və bazar
təsirinin qərəzsiz ölçüləcəyini müəyyən edir.

Phase 6:

- xəbər mətnini həqiqət və ya ticarət əmri kimi qəbul etmir;
- sentiment nəticəsini `buy`, `sell`, `long` və ya `short` adlandırmır;
- xam mənbə məlumatını səssiz dəyişmir və silmir;
- sonradan düzəldilən məlumatı ilkin buraxılışın üzərinə yazmır;
- yalnız həmin anda real məlum olan məlumatla causal tədqiqat aparır;
- MT5-ə, brokerə və Decision Layer-ə order göndərmir;
- ən çox sonrakı Knowledge Base və SHADOW qiymətləndirməsinə namizəd sübut yaradır.

## Mənbə reyestri

Hər məlumat mənbəyi istifadədən əvvəl reyestrə daxil edilir:

- `source_id`, sahibi, növü və rəsmi ünvanı;
- autentifikasiya üsulu və secret sərhədi;
- lisenziya, istifadə, saxlama və yenidən yayım hüquqları;
- dil, region, timezone və gözlənilən coverage;
- rate limit, gecikmə və əlçatanlıq öhdəliyi;
- düzəliş/revision davranışı;
- schema və connector versiyası;
- etibar və keyfiyyət məhdudiyyətləri;
- dayandırma və mənbə dəyişmə proseduru.

Lisenziyası və retention icazəsi aydın olmayan tam mətn saxlanmır. Bu halda yalnız
icazəli metadata, checksum və mənbə istinadı qorunur.

## Xam xəbər event-i

`NEWS_RECEIVED` event-i ən azı aşağıdakı sahələri daşıyır:

```text
event_id
event_type = NEWS_RECEIVED
timestamp = received_at UTC
source
version
source_item_id
published_at
received_at
first_seen_at
language
headline
body_reference
content_checksum
revision
symbols / entities
metadata
```

`published_at` mənbənin bildirdiyi dərc vaxtıdır; `received_at` platformanın məlumatı
ilk dəfə aldığı vaxtdır. İkisi eyni qəbul edilmir. Mənbə vaxtı etibarsızdırsa bu ayrıca
quality flag ilə göstərilir.

## Dəyişməzlik, təkrar və düzəliş

- source item ID və content checksum təkrar aşkarlanmasına birlikdə xidmət edir;
- eyni məzmunun sindikasiya olunması ayrıca source lineage ilə qeyd edilir;
- URL tək unikal açar deyil;
- yenilənmiş başlıq və ya mətn yeni revision event-i yaradır;
- silinmiş mənbə yazısı platformada tombstone event-i yaradır, köhnə sübutu silmir;
- ən erkən görülmə vaxtı sonradan gələn mənbə timestamp-ı ilə geri çəkilmir;
- dublikat sayğacı və qərarın səbəbi auditdə saxlanır;
- canonical xəbər klasteri bütün üzv source item-lərə istinad edir.

## Zaman uyğunlaşdırılması

Analiz üçün əsas əlçatanlıq vaxtı `received_at` olur. Tədqiqat yalnız platformanın
həmin anda görə bildiyi revision-dan istifadə edə bilər.

- gələcək revision keçmiş nümunəyə əlavə edilmir;
- xəbərdən əvvəlki bazar pəncərəsi və sonrakı horizon əvvəlcədən dondurulur;
- bazar sessiyası təqvimi versiyalanır;
- daylight-saving və timezone çevrilməsi audit olunur;
- planlı iqtisadi hadisə üçün `scheduled_at`, `released_at` və `received_at` ayrıdır;
- gecikmiş xəbər ayrıca latency bucket-də qiymətləndirilir;
- bazar bağlıdırsa ilk əlçatan açıq sessiya ayrıca qayda ilə qeyd edilir;
- eyni vaxtda çoxsaylı hadisə varsa qarışdırıcı təsir gizlədilmir.

## İqtisadi təqvim və fundamental release

Planlı göstərici üçün dəyişməz buraxılış vahidi:

```text
release_id
indicator_id
country / region
period
scheduled_at
released_at
received_at
actual
consensus
previous_reported
previous_revised
unit
seasonal_adjustment
revision
source_id
```

Surprise yalnız əvvəlcədən məlum consensus-a qarşı hesablanır. Sonradan yenilənmiş
consensus və revised previous rəqəmi tarixi nəticəyə geriyə tətbiq edilmir.

## Fundamental vintage məlumatı

Makro və şirkət göstəricilərində hər buraxılışın həmin tarixdə məlum olan variantı
— vintage — ayrıca saxlanır.

- period vaxtı ilə publication vaxtı qarışdırılmır;
- ilkin rəqəm və bütün revisions append-only saxlanır;
- point-in-time sorğu yalnız seçilmiş anda məlum olan vintage-i qaytarır;
- korporativ action, ticker və entity dəyişiklikləri zamanlı mapping daşıyır;
- survivorship bias yaratmamaq üçün ləğv edilmiş/delist olmuş entity-lər itirilmir;
- vahid, valyuta, nominal/real və seasonal adjustment metadata-sı məcburidir;
- müqayisə olunan göstəricilər schema versiyası ilə uyğunlaşdırılır.

## Entity və simvol uyğunlaşdırılması

Xəbərin alətə aidliyi ayrıca versiyalanmış mapping nəticəsidir:

- təşkilat, ölkə, sektor, commodity, valyuta və indeks ID-ləri sabitdir;
- broker symbol-u iqtisadi entity ID-si kimi istifadə edilmir;
- alias və ticker tarixi qüvvədəolma intervalı daşıyır;
- qeyri-müəyyən uyğunlaşdırma confidence və alternativ namizədlərlə saxlanır;
- aşağı confidence halında sistem `unresolved_entity` qaytarır;
- insan düzəlişi köhnə nəticəni dəyişmir, yeni review event-i yaradır;
- eyni xəbər bir neçə alətə təsir edə bilər və hər mapping ayrıca audit olunur.

## Mətn emalı və sentiment

Dil aşkarlanması, təmizləmə, tərcümə, entity extraction, topic və sentiment hər biri
ayrıca versiyalanmış derived artefaktdır.

- xam mətn dəyişdirilmir;
- tərcümə mənbə mətnin əvəzi sayılmır;
- model/provider, prompt, tokenizer və preprocessing versiyası saxlanır;
- confidence aşağıdırsa `abstain` edilir;
- sarcasm, negation, quoted speech və çoxdilli mətn məhdudiyyət kimi qeyd olunur;
- headline-only nəticə full-text nəticə ilə qarışdırılmır;
- müsbət sentiment avtomatik qiymət artımı fərziyyəsi deyil;
- model çıxışı label və gələcək bazar məlumatı ilə zənginləşdirilmir.

## Xəbər təsirinin ölçülməsi

Təsir əvvəlcədən qeydiyyatdan keçmiş event-study qaydası ilə ölçülür:

- estimation, pre-event və post-event pəncərələri;
- return, volatility, spread və tick-rate göstəriciləri;
- bazar/sector benchmark və normal nəticə modeli;
- abnormal return və uncertainty;
- komissiya, spread, slippage və latency;
- eyni vaxtlı xəbər və rejim control-ları;
- symbol, sessiya, topic, source və latency üzrə stabillik;
- multiple-testing düzəlişi və minimum nümunə sayı;
- placebo vaxtları və no-news baseline.

Korrelyasiya causal təsir kimi təqdim edilmir. Hadisələr üst-üstə düşürsə attribution
`ambiguous` və ya `confounded` ola bilər.

## Leakage və hindsight qoruması

- split-lər publication deyil, real `received_at` və horizon üzrə purge/embargo alır;
- son headline/revision köhnə train nümunəsinə yazılmır;
- sonradan məlum actual və revised göstərici forecast feature-a daxil edilmir;
- gələcək entity mapping və taxonomy keçmiş inputu səssiz dəyişmir;
- bütün dövr üzrə fit edilmiş vocabulary/normalizer qadağandır;
- xəbərin bazar reaksiyası sentiment inputuna daxil edilmir;
- holdout model və threshold seçmək üçün istifadə olunmur;
- uğursuz source, topic və model eksperimentləri reyestrdə qalır.

## Məlumat keyfiyyəti

Hər source və dataset üçün ən azı bunlar ölçülür:

- coverage və gözlənilənə qarşı boşluq;
- source və end-to-end latency;
- parse, schema və language failure;
- duplicate və revision sayı;
- unresolved entity faizi;
- timestamp etibarlılığı;
- lisenziya/retention vəziyyəti;
- checksum və lineage bütövlüyü;
- source outage və rate-limit intervalı.

Keyfiyyət həddi keçmirsə analiz `blocked_by_data_quality` olur; boşluq “xəbər yox idi”
kimi şərh edilmir.

## Xarici xidmət və təhlükəsizlik

- API açarı yalnız secret store/mühit sərhədində saxlanır;
- log, frontend, event payload və export paketində secret olmur;
- xarici URL və redirect allowlist ilə məhdudlaşdırılır;
- response ölçüsü, timeout, retry və rate limit tətbiq edilir;
- HTML/script aktiv məzmun kimi icra edilmir;
- prompt injection və mətn daxilindəki əmrlər data kimi qəbul edilir;
- üçüncü tərəfə xam mətn göndərilməsi ayrıca məxfilik və lisenziya icazəsi tələb edir;
- provider outage bazar məlumatı pipeline-ını dayandırmır.

## Standart event əlaqəsi

Konseptual event ailələri ayrıca versiyalanır:

- `NEWS_RECEIVED` — xam və ya icazəli mənbə metadata-sı;
- `NEWS_REVISED` — yeni revision və əvvəlki event istinadı;
- `ECONOMIC_RELEASE_RECEIVED` — point-in-time iqtisadi buraxılış;
- `FUNDAMENTAL_VINTAGE_RECEIVED` — fundamental vintage;
- `NEWS_ENTITY_RESOLVED` — derived entity mapping;
- `NEWS_ANALYSIS_COMPLETED` — derived tədqiqat nəticəsi.

Derived event mənbə event ID-lərini, model/spec versiyasını və checksum-u daşıyır.
Heç biri order event-i deyil.

## Konseptual API sərhədi

```text
GET  /api/v2/news/items
GET  /api/v2/news/items/{event_id}
GET  /api/v2/economic-releases
GET  /api/v2/fundamentals/vintages
POST /api/v2/news-studies
GET  /api/v2/news-studies/{study_id}
POST /api/v2/news-studies/{study_id}/archive
```

Siyahılar imzalanmış snapshot cursor ilə səhifələnir. Tam mətn yalnız rol və lisenziya
icazəsi daxilində qaytarılır. Archive xam event, revision və audit sübutunu silmir.

## Frontend təqdimatı

Panel:

- source, published/received vaxtı və gecikməni ayrı göstərir;
- düzəliş və revision tarixçəsini gizlətmir;
- original və tərcümə mətnini ayırır;
- entity confidence və unresolved halını göstərir;
- sentiment-i “al/sat” kimi təqdim etmir;
- event-study nəticəsində sample size, uncertainty və confounder göstərir;
- ilkin/revised fundamental rəqəmləri ayırır;
- source outage və məlumat boşluğunu “xəbər yoxdur” kimi göstərmir;
- order və real icra düyməsi təqdim etmir.

## Namizəd vəziyyətləri

`draft → registered → collecting → aligned → evaluated → accepted_for_knowledge | rejected → archived`

Əlavə vəziyyətlər: `blocked_by_license`, `blocked_by_data_quality`,
`unresolved_entity`, `invalid_leakage`, `confounded`, `insufficient_evidence`,
`failed`, `cancelled`.

`accepted_for_knowledge` avtomatik qərar və real ticarət icazəsi deyil.

## Audit və reproduksiya

Saxlanılan sübut:

- source registry və lisenziya snapshot-u;
- xam item/release checksum-u və bütün revisions;
- published, scheduled, released, received və first-seen vaxtları;
- entity/ticker mapping və taxonomy versiyası;
- preprocessing, tərcümə, model və prompt versiyası;
- dataset fingerprint və point-in-time split;
- primary metric, baseline, bütün eksperiment və failures;
- kod commit-i, dependency hash və seed;
- qəbul/rədd qərarı, actor və timestamp.

## Qəbul sınaqları

1. Eyni source item və checksum ikinci xam xəbər yaratmır.
2. Dəyişmiş məzmun köhnə event-i yeniləmədən yeni revision yaradır.
3. `published_at` və `received_at` ayrı saxlanır.
4. Gələcək revision keçmiş point-in-time sorğusunda görünmür.
5. Fundamental ilkin və revised rəqəmləri ayrıca vintage kimi qalır.
6. Sonradan məlum actual/consensus forecast feature-a sızmır.
7. Üst-üstə düşən event horizon-ları purge/embargo olmadan split edilmir.
8. Duplicate/sindication klasteri source lineage-i itirmir.
9. Aşağı entity confidence `unresolved_entity` yaradır.
10. Source outage “xəbər yoxdur” nəticəsi yaratmır.
11. Sentiment nəticəsi avtomatik al/sat siqnalı olmur.
12. Event-study placebo və no-news baseline ilə müqayisə edilir.
13. Lisenziya icazəsi olmayan tam mətn API/export-da görünmür.
14. Uğursuz eksperiment və source məlumatı səssiz silinmir.
15. Heç bir event, API və frontend elementi order yaratmır.

Bu sənəd xəbər və fundamental tədqiqatın elmi, hüquqi və təhlükəsiz sərhədidir;
strategiya, qərar və real ticarət icazəsi deyil.
