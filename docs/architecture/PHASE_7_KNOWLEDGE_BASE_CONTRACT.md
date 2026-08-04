# ESAS Platform — Phase 7 Knowledge Base müqaviləsi

Versiya: 1.0  
Status: **DESIGN READY — NOT IMPLEMENTED**  
Tətbiq şərti: Phase 1–6 qəbul qapılarının uğurla bağlanması

Əlaqəli müqavilələr:

- `docs/constitution/MODULE_LIFECYCLE.md`
- `docs/architecture/PHASE_2_AUDIT_EVIDENCE_EXPORT_CONTRACT.md`
- `docs/architecture/PHASE_3_RESEARCH_VALIDATION_CONTRACT.md`
- `docs/architecture/PHASE_4_PATTERN_TECHNICAL_ANALYSIS_CONTRACT.md`
- `docs/architecture/PHASE_5_VISUAL_AI_CONTRACT.md`
- `docs/architecture/PHASE_6_NEWS_FUNDAMENTAL_ANALYSIS_CONTRACT.md`

## Məqsəd və sərhəd

Knowledge Base platformanın audit edilə bilən elmi yaddaşıdır. O, tədqiqat nəticəsini
mənbə məlumatı, metod, sübut, məhdudiyyət, bazar rejimi və həyat dövrü ilə birlikdə
saxlayır.

Knowledge Base:

- yalnız qalib nəticələri seçib uğursuzluqları gizlətmir;
- tədqiqat nəticəsini dəyişməz həqiqət kimi təqdim etmir;
- xam tick, xəbər, bar, görüntü və model artefaktını özündə yenidən yazmır;
- mənbə artefaktlara checksum və lineage ilə istinad edir;
- zidd sübutu əvvəlki biliyin üzərinə yazmır;
- avtomatik al/sat qərarı, risk limiti və order yaratmır;
- yalnız Decision Layer-in sonradan qiymətləndirə biləcəyi versiyalı bilik verir.

## Bilik vahidi

Hər bilik dəyişməz, versiyalanmış `knowledge_claim` vahididir:

```text
knowledge_id
knowledge_version
claim_type
statement
scope
applicability
evidence_bundle_ids
dataset_fingerprints
method_versions
effect_and_uncertainty
limitations
valid_from
review_due_at
status
created_at
created_by
supersedes / conflicts_with
checksum
```

`statement` insan üçün qısa iddiadır; maşın tərəfindən istifadə olunan məna ayrıca
versiyalanmış struktur sahələrdə saxlanır. Mətn tək icra müqaviləsi deyil.

## İcazəli bilik növləri

İlkin claim ailələri:

- `descriptive_fact` — dataset daxilində müşahidə olunan təsviri nəticə;
- `statistical_relation` — uncertainty ilə statistik əlaqə;
- `regime_observation` — müəyyən bazar rejiminə aid nəticə;
- `pattern_candidate` — Phase 4 sübutuna bağlı namizəd;
- `visual_model_finding` — Phase 5 model nəticəsi;
- `news_impact_finding` — Phase 6 event-study nəticəsi;
- `data_quality_limitation` — istifadəyə təsir edən keyfiyyət məhdudiyyəti;
- `negative_result` — keçməyən hipotez və ya model;
- `operational_constraint` — latency, xərc və ya resurs sərhədi.

Heç bir claim növü öz-özünə `trade_signal` və ya order deyil.

## Qəbul qapısı

Knowledge Base-ə giriş iki səviyyəlidir:

### `candidate`

Eksperiment tamamlanıb, nəticə və sübut saxlanıb, lakin müstəqil review və ya tələb
olunan qəbul qapıları tam keçməyib. Decision Layer bunu istifadə edə bilməz.

### `accepted`

Yalnız aşağıdakılar birlikdə olduqda mümkündür:

- mənbə dataset fingerprint və quality report mövcuddur;
- əvvəlcədən qeydiyyat və primary metric saxlanıb;
- leakage və multiple-testing yoxlamaları keçib;
- holdout və walk-forward nəticələri qəbul həddindədir;
- baseline müqayisəsi və uncertainty verilib;
- xərc, latency, risk və məhdudiyyətlər göstərilib;
- reproduksiya nəticəsi və imzalanmış sübut paketi mövcuddur;
- səlahiyyətli review qərarı append-only auditdədir.

Çatışmayan sübut fail-closed olaraq qəbulun qarşısını alır.

## Sübut qrafı və lineage

Hər claim aşağıdakı əlaqəni geriyə izləməyə imkan verməlidir:

```text
knowledge claim
→ review decision
→ experiment result
→ method/model/config version
→ derived artefact
→ dataset snapshot
→ raw event lineage
```

Qraf düyünləri checksum daşıyır. İstinad edilən artefakt dəyişibsə claim bütövlük
yoxlamasından keçmir və `quarantined` olur.

## Dəyişməzlik və versiyalandırma

- qəbul edilmiş claim yerində redaktə edilmir;
- mətn, scope, sübut və hədd dəyişirsə yeni `knowledge_version` yaranır;
- yeni versiya əvvəlkini `supersedes`, `refines` və ya `contradicts` əlaqəsi ilə bağlayır;
- köhnə versiya tarixdən silinmir;
- yanlış metadata düzəlişi ayrıca correction event-i və audit tələb edir;
- semantikası dəyişən schema MAJOR versiya yaradır;
- eyni idempotency key eyni nəticəni qaytarır, yeni claim yaratmır.

## Scope və tətbiq sərhədi

Hər claim ən azı bunlarla məhdudlaşdırılır:

- symbol/entity və asset class;
- məlumat mənbəyi və broker/mənbə xüsusiyyəti;
- timeframe və horizon;
- UTC vaxt intervalı və sessiya;
- bazar rejimi və onun detector versiyası;
- minimum data quality;
- spread, latency və xərc ssenarisi;
- model/feature və event contract versiyası;
- məlum olmayan və qadağan olunmuş istifadə sahəsi.

Scope-dan kənar sorğu `not_applicable` qaytarır; ən yaxın claim səssiz seçilmir.

## Bazar rejiminə görə seçim

Rejim etiketi yalnız Phase 3-də versiyalanmış detector və bağlanmış məlumatla yaranır.

- rejim confidence aşağıdırsa regime-specific claim seçilmir;
- eyni anda bir neçə rejim mümkündürsə ambiguity saxlanır;
- gələcək məlumatla sonradan düzəldilmiş rejim canlı seçimə tətbiq edilmir;
- detector versiyası dəyişəndə əvvəlki claim avtomatik yeni rejimə köçürülmür;
- global claim və regime-specific claim ayrı müqayisə olunur;
- bazar bağlı, missing data və source outage ayrıca vəziyyətdir, rejim deyil.

## Etibarlılıq və istifadə müddəti

Knowledge Base “əbədi doğru” bilik saxlamır. Hər accepted claim üçün:

- `accepted_at` və `last_validated_at`;
- `review_due_at`;
- minimum yeni nümunə və observation coverage;
- gözlənilən effect intervalı;
- drift və degradation hədləri;
- istifadə sayı və son istifadə vaxtı;
- dependency və contract compatibility

qeyd olunur.

Vaxt həddi çatdıqda claim silinmir. Status `review_due` olur və Decision Layer üçün
fail-closed siyasətə uyğun ya bloklanır, ya yalnız müşahidə məqsədli göstərilir.

## REVIEW trigger-ləri

Review aşağıdakılardan biri baş verdikdə açılır:

- planlı `review_due_at` çatıb;
- yeni məlumatda effect qəbul intervalından çıxıb;
- calibration, hit rate və ya net nəticə zəifləyib;
- bazar rejimi və ya source coverage dəyişib;
- data quality həddi pozulub;
- yeni zidd sübut və ya daha güclü alternativ yaranıb;
- dependency, event, feature, model və ya taxonomy uyğunluğu pozulub;
- leakage, incident və ya audit bütövlüyü problemi aşkarlanıb;
- xərc, spread, latency və broker şərtləri dəyişib.

Review açılması köhnə sübutu dəyişmir və avtomatik yeni nəticə yaratmır.

## Zidd bilik və mübahisə

Zidd nəticələr ayrıca claim kimi saxlanır.

- conflict scope, data dövrü, metod və uncertainty ilə göstərilir;
- son yaradılan claim avtomatik qalib sayılmır;
- daha yüksək train nəticəsi üstünlük vermir;
- review `confirmed`, `refined`, `superseded`, `restricted`, `rejected` və ya
  `inconclusive` qərarı verə bilər;
- həll olunmamış konflikt Decision Layer-ə açıq şəkildə ötürülür;
- negative result və uğursuz reproduksiya axtarışdan gizlədilmir.

## Etibarlılıq göstəricisi

Vahid, sirli “AI score” qadağandır. Etibarlılıq komponentləri ayrıca göstərilir:

- evidence completeness;
- reproduksiya vəziyyəti;
- sample size və coverage;
- effect size və uncertainty;
- holdout/walk-forward stabilliyi;
- multiple-testing yükü;
- data quality;
- recency və drift;
- xərc/latency həssaslığı;
- conflict və limitation sayı.

Əgər ümumi kateqoriya verilirsə, onun formulu və hədləri versiyalanır və komponentləri
gizlətmir.

## Axtarış və retrieval

Sorğu dəyişməz `as_of` vaxtı və kontekst tələb edir:

```text
as_of
symbol/entity
timeframe/horizon
regime context
minimum status
contract compatibility
quality context
```

Nəticə yalnız həmin `as_of` vaxtında mövcud olan claim versiyalarını qaytarır. Default
sıralama “ən çox gəlir” deyil; tətbiq uyğunluğu, status, sübut bütövlüyü və review
vəziyyətidir.

## Decision Layer sərhədi

Knowledge Base yalnız oxuna bilən kontekst verir:

- `candidate`, `review_due`, `quarantined`, `rejected` claim qərar üçün yararlı deyil;
- accepted claim belə təkbaşına qərar yaratmır;
- Decision Layer ayrıca Phase 8 müqaviləsi ilə konflikt, risk və abstain tətbiq edir;
- Knowledge Base order ölçüsü, stop, entry və broker əmri qaytarmır;
- sorğu nəticəsi ilə yanaşı limitation və conflict məcburi qaytarılır;
- uyğun bilik yoxdursa `no_applicable_knowledge` cavabı verilir.

## İcazə və governance

- observer yalnız icazəli claim və sanitizasiya edilmiş sübutu oxuyur;
- researcher candidate yarada bilər, qəbul edə bilməz;
- reviewer qəbul/rədd qərarı verə bilər, öz eksperimenti üçün təkbaşına qərar verə bilməz;
- administrator schema və access idarə edir, elmi qəbul qərarını dəyişmir;
- yüksək riskli status dəyişikliyi təzə autentifikasiya və audit tələb edir;
- bulk import yalnız schema, checksum və provenance yoxlamasından sonra mümkündür.

## Saxlama və bərpa

- claim, review, conflict və audit append-only qorunur;
- artefaktların özləri uyğun mənbə storage-da qalır;
- backup manifesti claim və evidence graph checksum-larını əhatə edir;
- bərpa testi relation və signature bütövlüyünü yoxlayır;
- disk təzyiqi accepted/rejected bilik və audit tarixçəsini avtomatik silmir;
- cache itə bilər, kanonik claim və lineage itə bilməz;
- Git repozitoriyasına canlı Knowledge Base və məxfi payload əlavə edilmir.

## Konseptual event ailələri

- `KNOWLEDGE_CANDIDATE_CREATED`;
- `KNOWLEDGE_ACCEPTED`;
- `KNOWLEDGE_REJECTED`;
- `KNOWLEDGE_REVIEW_REQUESTED`;
- `KNOWLEDGE_REVIEW_COMPLETED`;
- `KNOWLEDGE_CONFLICT_DETECTED`;
- `KNOWLEDGE_QUARANTINED`;
- `KNOWLEDGE_ARCHIVED`.

Event-lər immutable və versiyalanmışdır. Heç biri ticarət siqnalı və order deyil.

## Konseptual API sərhədi

```text
POST /api/v2/knowledge/candidates
GET  /api/v2/knowledge/claims
GET  /api/v2/knowledge/claims/{knowledge_id}/versions
GET  /api/v2/knowledge/claims/{knowledge_id}/evidence
POST /api/v2/knowledge/claims/{knowledge_id}/reviews
GET  /api/v2/knowledge/conflicts
POST /api/v2/knowledge/claims/{knowledge_id}/archive
```

Yazma idempotency key və optimistic locking tələb edir. Siyahılar imzalanmış snapshot
cursor ilə səhifələnir. Archive claim, evidence və audit tarixçəsini silmir.

## Frontend təqdimatı

Panel:

- claim statusu, versiyası, scope-u və `as_of` vaxtını göstərir;
- nəticə ilə birlikdə uncertainty, limitation və conflict göstərir;
- candidate və accepted biliyi vizual olaraq ayırır;
- review vaxtı keçmiş və quarantined biliyi yaşıl göstərmir;
- sübut qrafına və reproduksiya nəticəsinə keçid verir;
- negative result və superseded versiyaları axtarışda saxlayır;
- etibarlılıq komponentlərini vahid gizli score arxasında gizlətmir;
- “ən yaxşı strategiya”, al/sat və order düyməsi göstərmir.

## Vəziyyətlər

```text
candidate → under_review → accepted → review_due → under_review
                         ↘ rejected
accepted → restricted | superseded | quarantined | archived
```

`archived` silinmiş demək deyil. `accepted` də ACTIVE ticarət modulu demək deyil.

## Qəbul sınaqları

1. Sübut paketi çatışmayan candidate accepted ola bilmir.
2. Accepted claim yerində dəyişdirilmir; dəyişiklik yeni versiya yaradır.
3. Evidence checksum dəyişəndə claim quarantined olur.
4. `as_of` sorğusu gələcək claim versiyasını qaytarmır.
5. Scope-dan kənar sorğu `not_applicable` verir.
6. Aşağı regime confidence regime-specific claim seçmir.
7. Review vaxtı çatan claim səssiz accepted istifadədə qalmır.
8. Zidd sübut əvvəlki claim-i silmir və conflict yaradır.
9. Negative və rejected nəticə axtarışdan itmir.
10. Eyni idempotency key ikinci claim yaratmır.
11. Reviewer öz eksperimenti üçün təkbaşına qəbul verə bilmir.
12. Backup restore evidence graph və checksum-u qoruyur.
13. Uyğun bilik yoxdursa sistem `no_applicable_knowledge` qaytarır.
14. Frontend status, uncertainty və limitations-u gizlətmir.
15. Knowledge Base event, API və frontend vasitəsilə order yaratmır.

Bu sənəd platformanın elmi yaddaş sərhədidir; qərar, risk və real ticarət icazəsi deyil.
