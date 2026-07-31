# ESAS Platform — Phase 5 Visual AI müqaviləsi

Versiya: 1.0  
Status: **DESIGN READY — NOT IMPLEMENTED**  
Tətbiq şərti: Phase 1–4 qəbul qapılarının uğurla bağlanması

Əlaqəli müqavilələr:

- `docs/architecture/PHASE_3_RESEARCH_VALIDATION_CONTRACT.md`
- `docs/architecture/PHASE_3_STATISTICAL_ANALYSIS_CONTRACT.md`
- `docs/architecture/PHASE_4_PATTERN_TECHNICAL_ANALYSIS_CONTRACT.md`

## Məqsəd və sərhəd

Bu müqavilə bazar məlumatından deterministik qrafik görüntülərinin, Visual AI məlumat
dəstinin, eksperiment və müqayisə sübutunun necə yaradılacağını müəyyən edir.

Phase 5:

- insanın qrafikdə gördüyü formanın həqiqət olduğunu əvvəlcədən qəbul etmir;
- yalnız Phase 4-ün bağlanmış və versiyalanmış bar artefaktını oxuyur;
- şəkil üzrə nəticəni `buy`, `sell` və ya order əmri saymır;
- MT5-ə və brokerə heç bir əmr göndərmir;
- xam tick, derived bar və əvvəlki tədqiqat nəticəsini dəyişmir;
- statistik baseline-dan zəif modeli yalnız vizual cəlbediciliyinə görə qəbul etmir;
- ən çox sonrakı SHADOW sınağı üçün namizəd sübut paketi yaradır.

## Eksperiment qeydiyyatı

Render və təlim başlamazdan əvvəl bunlar dəyişməz qeyd olunur:

- `experiment_id`, `dataset_id`, `render_spec_id` və `model_id`;
- mənbə dataset və bar fingerprint-ləri;
- symbol, UTC `[start_at, end_at)` sərhədi və timeframe;
- müşahidə pəncərəsi, horizon, label və dead-zone qaydası;
- train, validation, holdout və walk-forward sərhədləri;
- render ölçüsü, rəng palitrası, şkalalama, layer və boşluq qaydaları;
- augmentasiya, preprocessing və normalization versiyası;
- model arxitekturası, loss, optimizer, seed və resurs limiti;
- primary metric, baseline-lar və qəbul hədləri;
- kod commit-i, asılılıq hash-i və konfiqurasiya checksum-u.

İş başladıqdan sonra hər dəyişiklik yeni render, dataset və ya model versiyası yaradır.

## Kanonik görüntü müqaviləsi

Görüntü yalnız Phase 4-də bağlanmış barlardan deterministik yaradılır. Eyni input,
render spesifikasiyası və proqram versiyası eyni piksel checksum-u verməlidir.

Kanonik görüntü ən azı bunları qeyd edir:

- input barlarının `first_event_id` və `last_event_id` lineage-i;
- müşahidə pəncərəsinin ilk və son bağlanmış barı;
- renderin real məlum olduğu ən erkən UTC vaxtı;
- width, height, kanal sayı və rəng məkanı;
- qiymət şkalası və padding qaydası;
- candle/OHLC və icazəli indikator layer-ləri;
- missing-data maskası və quality flag-ləri;
- renderer adı, semantik versiyası və checksum-u.

İlkin format itkisiz `PNG` və ya deterministik tensor artefaktıdır. JPEG kimi itgili
format əsas dataset mənbəyi olmur. Ekran görüntüsü, brauzer, MT5 pəncərəsi, siçan,
hesab nömrəsi və əməliyyat elementləri datasetə daxil edilmir.

## Zaman və səbəbiyyət sərhədi

`t` anında yaradılan görüntü yalnız `t`-də və əvvəl bağlanmış barları göstərə bilər.

- gələcək bar və label sahəsi kəsilir;
- açıq bar istifadə edilmir;
- centered smoothing və gələcəkdən backfill qadağandır;
- şəkil yaradıldıqdan sonra məlum olan annotation inputa çəkilmir;
- horizon və nəticə görüntünün pikselinə, metadata-sına və fayl adına yazılmır;
- snapshot vaxtı modelin real işləyə biləcəyi ən erkən vaxtdan əvvəl göstərilmir;
- missing interval vizual olaraq gizli şəkildə doldurulmur.

## Vizual sızma qoruması

Model bazarı deyil, dataset quruluşunu öyrənməməlidir. Buna görə aşağıdakılar inputdan
çıxarılır və avtomatik yoxlanır:

- label, gələcək gəlir, entry/exit işarəsi və nəticə rəngi;
- fayl və qovluq adında class, tarix bölgüsü və nəticə kodu;
- train/test-ə xas watermark, sıxılma, ölçü və palitra;
- platforma saatı, broker adı, hesab və terminal məlumatı;
- gələcək barın chart boşluğu və horizon uzunluğunu bildirən padding;
- yalnız uğurlu nümunələrə tətbiq olunan annotation və augmentasiya;
- label ilə korrelyasiyalı sıra nömrəsi və metadata.

Görüntünün özündən əlavə tensor, metadata və fayl sistemi yolu da leakage auditindən
keçir.

## Dataset vahidi və lineage

Hər nümunə aşağıdakı dəyişməz əlaqəni daşıyır:

```text
sample_id
→ source_bar_fingerprint
→ render_spec_id
→ image_checksum
→ observation_end_at
→ label_spec_id
→ label_available_at
→ split_id
```

Eyni və ya üst-üstə düşən müşahidə/horizon intervalından törəyən görüntülər müxtəlif
train, validation və holdout hissələrinə düşə bilməz. Purge/embargo qaydası Phase 3
müqaviləsinə uyğun tətbiq edilir.

Dataset manifesti nümunə sayını symbol, timeframe, sessiya, rejim, label və quality
üzrə göstərir. Uğursuz, neutral və `insufficient_data` nümunələri səssiz silinmir.

## Label və class balansı

Label Phase 4 qaydasına uyğun ayrıca hesablanır və şəkil yaradılmasına təsir etmir.

- label spesifikasiyası train-dən əvvəl dondurulur;
- class həddi bütün datasetə baxılaraq optimallaşdırılmır;
- horizon tamamlanmayan nümunə təlimə daxil edilmir;
- oversampling yalnız train hissəsində edilir;
- validation və holdout real yayılmanı qoruyur;
- class weight və sampling siyasəti nəticə ilə birlikdə açıqlanır;
- accuracy tək qəbul göstəricisi deyil.

## Augmentasiya qaydaları

Augmentasiya yalnız bazar semantikasını qoruyursa istifadə olunur.

İcazəli ola bilən dəyişikliklər əvvəlcədən sınaqdan keçirilir: kiçik piksel səs-küyü,
render rezolyusiyasının kontrollu dəyişməsi və label-i dəyişməyən maskalama.

Aşağıdakılar ilkin olaraq qadağandır:

- zaman oxunu tərsinə çevirmək;
- qiyməti şaquli çevirmək;
- gələcək hissəni crop ilə açmaq;
- yalnız bir class-a augmentasiya tətbiq etmək;
- iqtisadi mənanı dəyişən candle silmək və ya əlavə etmək;
- holdout görüntüsündən train variantı yaratmaq.

Hər augmentasiya ayrıca ablation testində faydasını və zərərsizliyini göstərməlidir.

## Model çıxışı və abstain

Model çıxışı ən azı bunları daşıyır:

- `prediction_id`, model və dataset versiyası;
- nümunə və görüntü checksum-u;
- class/score və onun kalibrasiya mənası;
- uncertainty və out-of-distribution göstəricisi;
- `abstain`, `insufficient_data` və quality səbəbləri;
- inference başlanma/bitmə vaxtı və latency;
- izah artefaktının identifikatoru.

Confidence ticarət ehtimalı deyil. Kalibrasiya zəifdirsə, input train paylanmasından
kənardadırsa və ya quality qapısı keçmirsə model `abstain` etməlidir.

## İzah və vizual audit

Saliency/attention xəritəsi səbəb sübutu sayılmır, yalnız diaqnostik artefaktdır.

- izah üsulu və versiyası saxlanır;
- heatmap mənbə görüntüdən ayrı artefaktdır;
- modelin fayl kənarı, watermark və boş sahəyə baxması leakage siqnalıdır;
- seçilmiş yaxşı nümunələrlə yanaşı səhv və neutral nümunələr də göstərilir;
- insan şərhi model nəticəsini sonradan dəyişmir, ayrıca review qeydi yaradır.

## Statistik baseline ilə ədalətli müqayisə

Visual AI eyni zaman bölgüsü, label, xərc, risk və nümunə sərhədində ən azı bunlarla
müqayisə edilir:

- no-skill və class-prior baseline;
- sadə qiymət/return baseline-ı;
- Phase 4-ün uyğun texniki feature namizədi;
- eyni parametr büdcəli sadə model;
- varsa əvvəlki təsdiqlənmiş visual model.

Müqayisə yalnız predictive metric deyil, net nəticə, uncertainty, calibration,
drawdown, inference latency, model ölçüsü və hesablama xərcini də əhatə edir. Visual
model statistik baseline-dan praktik və sabit üstünlük göstərmirsə qəbul edilmir.

## Təlim, holdout və walk-forward

- preprocessing yalnız train hissəsində fit edilir;
- early stopping yalnız validation-a baxır;
- holdout model və threshold seçimi üçün istifadə edilmir;
- hyperparameter və arxitektura sınaqlarının tam sayı multiple-testing reyestrindədir;
- random image split qadağandır; zaman əsaslı bölgü məcburidir;
- walk-forward nəticələri ayrı-ayrı dövrlər üzrə göstərilir;
- təkrar holdout baxışı audit olunur və nəticənin statusunu endirir;
- ən yaxşı checkpoint seçmə qaydası əvvəlcədən qeyd olunur.

## Reproduksiya və model artefaktı

Saxlanılan paketə daxildir:

- dataset manifesti və fingerprint;
- render, preprocessing və augmentasiya spesifikasiyası;
- kod commit-i, dependency lock və seed;
- model arxitekturası, çəkilər, checksum və imza;
- train log-u, bütün checkpoint seçimi və resurs istifadəsi;
- validation, holdout və walk-forward nəticələri;
- baseline və ablation müqayisələri;
- məlum məhdudiyyətlər və istifadə sərhədi.

GPU əməliyyatı tam deterministik deyilsə bu məhdudiyyət ölçülür, qeyd olunur və nəticə
fərqinin toleransı əvvəlcədən müəyyən edilir.

## Namizəd vəziyyətləri

İcazəli axın:

`draft → registered → rendering → training → evaluated → accepted_for_shadow | rejected → archived`

Əlavə vəziyyətlər: `blocked_by_data_quality`, `invalid_leakage`,
`non_reproducible`, `out_of_distribution`, `insufficient_evidence`, `failed`,
`cancelled`.

`accepted_for_shadow` real ticarət icazəsi deyil. Model Phase 9-da order açmadan canlı
görüntü üzərində müşahidə oluna bilər.

## Konseptual API sərhədi

Phase 2 scheduler və `/api/v2` sərhədində:

```text
POST /api/v2/visual-datasets
GET  /api/v2/visual-datasets/{dataset_id}
POST /api/v2/visual-experiments
GET  /api/v2/visual-experiments/{experiment_id}
GET  /api/v2/visual-experiments/{experiment_id}/comparison
POST /api/v2/visual-experiments/{experiment_id}/archive
```

Yaratma idempotency key tələb edir. Böyük manifest və nəticə snapshot cursor ilə
səhifələnir. Archive xam məlumatı, görüntünü, modeli və audit sübutunu silmir.

## Frontend təqdimatı

Panel:

- “Visual AI tədqiqatıdır — ticarət siqnalı deyil” nişanı göstərir;
- mənbə pəncərəsini, render/model versiyasını və checksum-u göstərir;
- train, validation, holdout və walk-forward nəticələrini ayırır;
- baseline müqayisəsini və uncertainty-ni gizlətmir;
- düzgün nümunələrlə yanaşı səhvləri və abstain hallarını göstərir;
- heatmap-i səbəb sübutu kimi təqdim etmir;
- latency, model ölçüsü və resurs xərcini göstərir;
- order, al/sat və real icra düyməsi göstərmir.

## Məxfilik və xarici model

Xam bazar görüntüsü üçüncü tərəfə standart olaraq göndərilmir. Xarici model və ya
servis yalnız ayrıca təsdiqdən sonra istifadə oluna bilər və bu zaman:

- göndərilən məlumat sərhədi və retention siyasəti;
- model/provider versiyası;
- determinism və xidmət əlçatanlığı;
- məxfilik, lisenziya və xərc;
- nəticənin lokal reproduksiya məhdudiyyəti

auditdə qeyd olunur. Məxfi açar kodda, datasetdə və model paketində saxlanmır.

## Qəbul sınaqları

1. Eyni bar snapshot-u və render spesifikasiyası eyni piksel checksum-u yaradır.
2. Açıq və gələcək bar görüntüyə daxil olmur.
3. Label və nəticə piksel, metadata, fayl və qovluq adından tapılmır.
4. Üst-üstə düşən zaman/horizon nümunələri müxtəlif split-lərə keçmir.
5. Random image split bloklanır.
6. Holdout-dan train augmentasiyası yaradılmır.
7. Missing interval səssiz doldurulmur.
8. Eyni class üçün render formatı digər class-lardan fərqlənmir.
9. Preprocessing yalnız train hissəsində fit edilir.
10. Aşağı confidence və OOD input `abstain` yaradır.
11. Statistik baseline eyni dataset, label və xərc sərhədində hesablanır.
12. Multiple-testing reyestri olmadan ən yaxşı model qəbul edilmir.
13. Model checksum-u dəyişəndə audit yoxlaması uğursuz olur.
14. Uğursuz model, nümunə və nəticə silinmir.
15. Frontend və API nəticəsi order və broker əməliyyatı yaratmır.

Bu sənəd Visual AI tədqiqatının elmi və təhlükəsiz sərhədidir; strategiya, qərar və
real ticarət icazəsi deyil.
