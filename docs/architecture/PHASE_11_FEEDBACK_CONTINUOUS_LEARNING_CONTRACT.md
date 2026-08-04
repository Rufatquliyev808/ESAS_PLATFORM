# ESAS Platform — Phase 11 Feedback və Davamlı Öyrənmə Müqaviləsi

Versiya: 1.0  
Status: DESIGN READY — NOT IMPLEMENTED  
Asılılıqlar: müvafiq Phase 1–10 qəbul qapıları və tam audit zənciri

## 1. Məqsəd

Feedback Layer qərar, risk, SHADOW və məhdud icra nəticələrini dəyişməz sübut kimi
analizə qaytarır. Məqsəd modelin real davranışını ölçmək, zəifləməni vaxtında aşkar
etmək, Knowledge Base-i versiyalı sübutla yeniləmək və yeni namizədləri təhlükəsiz
həyat dövrünə yönəltməkdir.

Davamlı öyrənmə canlı modelin öz kodunu və çəkilərini avtomatik dəyişdirməsi deyil.
Heç bir feedback nəticəsi özbaşına ACTIVE statusu, risk artımı və order icazəsi vermir.

## 2. Dəyişməz təhlükəsizlik sərhədi

- ACTIVE model in-place yenilənmir; hər dəyişiklik yeni immutable versiyadır.
- Təlim, rekalibrasiya və threshold dəyişikliyi real icra prosesindən ayrıdır.
- Yeni versiya birbaşa ACTIVE edilmir; `EXPERIMENTAL -> SHADOW` qapılarından keçir.
- Feedback Layer order, mövqe, stop, risk limiti və broker hesabını dəyişmir.
- Zəiflik aşkarlandıqda sistem riski artırmır; exposure azaldılır və ya modul halt/review olur.
- Natamam lineage, gecikmiş label və məlumat boşluğu əsasında avtomatik nəticə çıxarılmır.
- Holdout və gələcək məlumat təlimə sızmır.
- Audit və model registry yazıla bilmirsə promotion dayandırılır.
- Secret, şəxsi hesab və broker credential-ları dataset-ə və artefakta daxil edilmir.

## 3. Feedback vahidi və tam lineage

Hər feedback nümunəsi aşağıdakı zənciri saxlayır:

`market_event -> feature_snapshot -> knowledge_claim -> model_output -> decision -> risk
-> shadow/execution outcome -> label -> evaluation`

Minimum sahələr:

- feedback və correlation/causation identifikatorları;
- source event, dataset və snapshot fingerprint-i;
- feature, model, decision, risk, SHADOW və execution versiyaları;
- simvol, timeframe, sessiya, rejim və qərar vaxtı;
- proposal, abstain, risk block və manual approval nəticəsi;
- nəzəri və ya real entry/exit, xərclər, latency və slippage;
- label qaydası, horizon, maturity vaxtı və uncertainty;
- məlumat keyfiyyəti, incident və exclusion səbəbi.

Nəticə sonradan dəyişərsə köhnə sətir redaktə edilmir; revision event-i yaradılır.

## 4. Əhatə və seçim qərəzi

Yalnız fill olmuş treydləri öyrənmək qadağandır. Aşağıdakılar ayrıca qorunur:

- açılmış və açılmamış nəzəri mövqelər;
- real fill, partial fill, rejection, cancellation və unknown nəticələr;
- abstain edilmiş qərarlar;
- risk və manual approval tərəfindən bloklanan qərarlar;
- vaxtı bitmiş və invalidated qərarlar;
- əlaqəsiz baseline və bazar nəzarət nümunələri.

Bloklanan qərar üçün mümkün nəticə yalnız əvvəlcədən qeydiyyatlı counterfactual qayda ilə
hesablana bilər və real PnL kimi təqdim edilmir. Fill seçimi, manual müdaxilə, broker
rejection və latency selection-bias metadatası kimi qiymətləndirilir.

## 5. Label və nəticənin yetişməsi

- Label qaydası təlim və qiymətləndirmədən əvvəl versiyalanır.
- Nəticə horizon bitmədən `MATURED` sayılmır.
- Gecikmiş broker düzəlişi və korporativ/xəbər revision-u yeni event yaradır.
- Eyni qərarın bir neçə horizon-u ayrı label kimi saxlanır.
- Exit siyasəti dəyişərsə köhnə nəticə yeni siyasətlə geriyə yazılmır.
- Məlumat keyfiyyəti zəifdirsə label `INCONCLUSIVE` olur.
- Realized, mark-to-market və counterfactual nəticələr qarışdırılmır.

## 6. Performans ölçüləri

Qiymətləndirmə həm ümumi, həm simvol, timeframe, sessiya və rejim üzrə aparılır:

- coverage, abstain, risk-block və fill nisbəti;
- calibration, discrimination və forecast error;
- gross/net nəticə, spread, komissiya, slippage, swap və latency;
- win/loss deyil, gözlənilən dəyər və uncertainty intervalı;
- drawdown, tail loss, exposure və risk-adjusted nəticə;
- SHADOW ilə real icra arasındakı fərq;
- rejection, partial fill və operational incident nisbəti;
- baseline, champion və challenger fərqi;
- data, feature, prediction, calibration və outcome drift-i.

Tək PnL model keyfiyyətinin sübutu deyil. Təhlükəsizlik və bütövlük göstəriciləri ayrıca
məcburi qapıdır.

## 7. Drift və degradation monitorinqi

Əvvəlcədən qeydiyyatlı pəncərələr istifadə olunur:

- qısa operativ pəncərə;
- orta trend pəncərəsi;
- uzunmüddətli referens pəncərə.

Minimum trigger-lər:

- input/feature paylanmasının referensdən uzaqlaşması;
- bazar rejimi və coverage dəyişməsi;
- calibration və nəticə keyfiyyətinin həddən aşağı düşməsi;
- xərclərin və slippage-in gözləniləndən artması;
- drawdown/tail loss və ardıcıl uğursuzluq həddi;
- SHADOW-real fərqinin böyüməsi;
- məlumat keyfiyyəti, latency və broker davranışı dəyişməsi;
- istifadə edilən Knowledge Base claim-inin köhnəlməsi və ya zidd sübut.

Multiple-testing və təkrarlanan baxışlar üçün false-alert nəzarəti tətbiq edilir.
Metrik yalnız nümunə sayı və uncertainty kifayət olduqda degradation sübutu sayılır.

## 8. Təhlükəsiz cavab matrisi

| Səviyyə | Vəziyyət | Məcburi cavab |
|---|---|---|
| INFO | Erkən zəif siqnal | Müşahidəni artır, audit et |
| WARNING | Davamlı, lakin kritik olmayan drift | Yeni exposure azalt, SHADOW müqayisəsi aç |
| CRITICAL | Risk/performance həddi və ya lineage problemi | Yeni qərar/order halt, modul `REVIEW` |
| INCIDENT | İcazəsiz davranış, audit boşluğu, təhlükəsizlik pozuntusu | Global/account halt və manual araşdırma |

Avtomatik cavab yalnız daha təhlükəsiz istiqamətdə ola bilər: risk azaltmaq, orderi
bloklamaq, modeli REVIEW/SHADOW-a çəkmək. Avtomatik risk artırmaq qadağandır.

## 9. Modul həyat dövrü

Feedback qərarları:

- `ACTIVE_RETAINED`
- `ACTIVE_WITH_REDUCED_LIMITS`
- `REVIEW_REQUIRED`
- `RETURN_TO_SHADOW`
- `ARCHIVE_RECOMMENDED`
- `MORE_EVIDENCE_REQUIRED`

`REVIEW_REQUIRED` olduqda yeni exposure siyasətə uyğun bloklanır və ya azaldılır.
Mövcud açıq mövqelərin taleyi Phase 10 fövqəladə siyasəti ilə idarə olunur; Feedback
Layer özü order göndərmir.

## 10. Yeni model və rekalibrasiya

Yeni təlim run-ı dəyişməz manifest daşıyır:

- məqsəd, fərziyyə, əvvəlcədən qeydiyyatlı metrik və hədlər;
- dataset/time cutoff, nümunə seçimi və lineage;
- train/validation/holdout və embargo sərhədləri;
- kod, dependency, feature, label və hyperparameter versiyaları;
- random seed və reproduksiya mühiti;
- baseline/champion və xərc modeli;
- fairness, təhlükəsizlik və rollback planı.

Yeni artefakt yeni model versiyası və checksum alır. Rekalibrasiya da model
dəyişikliyidir; in-place threshold dəyişikliyi kimi gizlədilə bilməz.

## 11. Promotion qapısı

Yeni namizəd yalnız aşağıdakı ardıcıllıqla irəliləyir:

`EXPERIMENTAL -> offline validation -> SHADOW -> limited execution review`

Promotion üçün:

1. holdout toxunulmaz və bütün lineage tamdır;
2. baseline/champion müqayisəsi əvvəlcədən qeydiyyatlı hədləri keçir;
3. nəticə xərclərdən sonra və uncertainty ilə verilir;
4. fərqli rejim, sessiya və simvollarda dayanıqlıq göstərilir;
5. risk, tail və operational meyarları keçilir;
6. təhlükəsizlik sınaqları və rollback məşqi uğurludur;
7. müstəqil insan review-u və imzalanmış acceptance mövcuddur.

Promotion əvvəlki ACTIVE versiyanı silmir. Canary/məhdud icra və dərhal rollback yolu
qorunur.

## 12. Knowledge Base yenilənməsi

Feedback birbaşa “həqiqət” yazmır. O, sübut paketi ilə yeni claim və ya mövcud claim
üçün dəstək/ziddiyyət namizədi yaradır:

- claim scope-u, rejim və etibarlılıq müddəti;
- istifadə edilən dataset və model versiyası;
- statistik effekt, uncertainty və practical significance;
- əks sübut, məhdudiyyət və məlum qərəzlər;
- review/expiry trigger-ləri.

Knowledge Base governance qəbulundan sonra yeni versiya aktiv olur. Köhnə claim
silinmir; superseded/review/archived statusu və səbəbi qorunur.

## 13. Reproduksiya və registry

Hər model artefaktı üçün saxlanır:

- model ID və semantik versiya;
- manifest, checksum və digital signature;
- kod commit-i və dependency lock;
- dataset fingerprint və cutoff;
- training/evaluation hesabatı;
- lifecycle statusu və approval tarixçəsi;
- istifadə edən qərar və icra run-ları;
- rollback olunan əvvəlki stabil versiya.

Artefakt, manifest və metriklərdən eyni nəticə yenidən hesablana bilmirsə promotion
`INCONCLUSIVE` olur.

## 14. Event ailələri

Minimum event-lər:

- `FEEDBACK_SAMPLE_RECORDED`
- `OUTCOME_LABEL_MATURED`
- `OUTCOME_LABEL_REVISED`
- `MODEL_EVALUATION_COMPLETED`
- `MODEL_DRIFT_DETECTED`
- `MODEL_DEGRADATION_CONFIRMED`
- `MODEL_REVIEW_REQUESTED`
- `MODEL_RETURNED_TO_SHADOW`
- `TRAINING_RUN_REGISTERED`
- `MODEL_CANDIDATE_CREATED`
- `MODEL_PROMOTION_RECOMMENDED`
- `MODEL_PROMOTION_REJECTED`
- `MODEL_ROLLBACK_REQUESTED`
- `KNOWLEDGE_UPDATE_PROPOSED`

Event-lər immutable, versiyalanmış və causation zəncirli olur. Heç biri order event-i
və ya avtomatik ACTIVE icazəsi deyil.

## 15. Worker, restart və idempotency

- Feedback işi Phase 1 məlumat qəbulundan və Phase 10 execution-dan ayrıdır.
- Job identifikatoru dataset cutoff + model + evaluator + config hash-dən yaranır.
- Eyni job restartdan sonra ikinci nəticə və ya model versiyası yaratmır.
- Checkpoint yalnız tam emal edilmiş partition-dan sonra irəliləyir.
- Gecikmiş event yeni evaluation revision-u yaradır, köhnəni dəyişmir.
- Queue təzyiqi order və tick axınına ötürülmür.
- Natamam run promotion üçün istifadə edilmir.

## 16. Monitorinq və frontend

Frontend aşağıdakıları göstərir:

- ACTIVE/SHADOW/REVIEW model və versiya;
- referens, cari pəncərə, nümunə sayı və uncertainty;
- performans, risk, drift və operational göstəricilər;
- degradation səbəbi və avtomatik təhlükəsizlik cavabı;
- champion/challenger müqayisəsi;
- Knowledge Base update namizədləri və approval statusu;
- training run və promotion audit izi.

UI “model öyrəndi” ifadəsini yalnız yeni versiya yaradılıb təsdiqləndikdə göstərir.
Frontend model aktivləşdirmir, riski artırmır və order göndərmir.

## 17. Davamlı öyrənmə qəbul meyarları

1. qərardan nəticəyə tam lineage mövcuddur;
2. abstain, risk-block, rejection və fill olmayan nümunələr itirilmir;
3. label maturity və revision qaydaları deterministikdir;
4. selection bias və counterfactual nəticə real PnL-dən ayrıdır;
5. drift trigger-ləri əvvəlcədən qeydiyyatlı və uncertainty-lidir;
6. kritik degradation yeni exposure-u təhlükəsiz dayandırır;
7. ACTIVE model in-place dəyişmir;
8. hər yeni model ayrıca versiya və reproduksiya manifesti alır;
9. holdout/leakage/multiple-testing qapıları keçilir;
10. promotion yalnız həyat dövrü və insan təsdiqi ilə baş verir;
11. rollback əvvəlki stabil versiyaya deterministikdir;
12. Knowledge Base update-i versiyalı governance-dan keçir;
13. restart dublikat evaluation və model yaratmır;
14. Feedback nasazlığı tick qəbuluna və execution təhlükəsizliyinə təsir etmir;
15. secret və şəxsi məlumat artefaktlara sızmır.

## 18. Məcburi qəbul sınaqları

1. Fill olmayan və risk-block qərarlar feedback dataset-də qalır.
2. Horizon bitməmiş label `MATURED` olmur.
3. Gecikmiş düzəliş köhnə label-i dəyişmir, revision yaradır.
4. Real və counterfactual nəticələr qarışdırılmır.
5. Natamam lineage promotion-u bloklayır.
6. Eyni job restartdan sonra dublikat nəticə yaratmır.
7. Drift trigger-i kifayət nümunə olmadan kritik qərar vermir.
8. Kritik degradation yeni exposure-u bloklayır.
9. Feedback Layer broker/order adapterinə çağırış etmir.
10. Risk limiti avtomatik artırılmır.
11. Rekalibrasiya yeni model versiyası yaradır.
12. Yeni model birbaşa ACTIVE edilmir.
13. Rollback model, feature və config versiyalarını birlikdə qaytarır.
14. Holdout məlumatı training input-una daxil edilmir.
15. Knowledge claim köhnə tarixçəni silmədən versiyalanır.
16. Frontend approval olmadan promotion göstərə bilmir.

## 19. Hazırkı təsir

Bu sənəd gələcək Phase 11 tətbiqi üçün müqavilədir. Hazırda təlim job-u, model
yenilənməsi, Knowledge Base mutation-u və real ticarət funksiyası yaradılmır. Phase 1
üçün rəsmi 24 saatlıq sabitlik sınağı əsas növbəti qəbul tapşırığı olaraq qalır.
