# ESAS Platform — Phase 8 Decision və Risk Layer müqaviləsi

Versiya: 1.0  
Status: **DESIGN READY — NOT IMPLEMENTED**  
Tətbiq şərti: Phase 1–7 qəbul qapılarının uğurla bağlanması

Əlaqəli müqavilələr:

- `docs/constitution/MODULE_LIFECYCLE.md`
- `docs/architecture/PHASE_3_RESEARCH_VALIDATION_CONTRACT.md`
- `docs/architecture/PHASE_7_KNOWLEDGE_BASE_CONTRACT.md`

## Məqsəd və sərhəd

Bu müqavilə qəbul edilmiş bilik və cari bazar kontekstinin necə birləşdiriləcəyini,
izahlı nəzəri qərarın necə yaradılacağını və müstəqil Risk Layer-in onu necə
məhdudlaşdıracağını müəyyən edir.

Phase 8:

- yalnız Phase 7-də uyğun və `accepted` olan bilikləri oxuyur;
- risk yoxlamasını model confidence-i ilə əvəz etmir;
- nəticəni broker orderinə çevirmir;
- MT5 order interfeysi, fill, mövqe və balans dəyişiklikləri yaratmır;
- yalnız Phase 9 SHADOW üçün order göndərməyən `decision_intent` yaradır;
- qeyri-müəyyən, natamam və audit olunmayan halda fail-closed `abstain/blocked` olur.

## Qatların ayrılığı

Decision və Risk ayrı modullardır:

```text
Accepted Knowledge + Current Context
→ Decision Proposal
→ Independent Risk Evaluation
→ Shadow Eligibility
```

Decision Layer istiqamət, confidence, horizon və səbəb təklif edə bilər. Risk Layer
onu yalnız daralda və ya bloklaya bilər; risk modulu bloklanmış təklifi icazəli edə
bilməz. Execution Layer Phase 8 daxilində yoxdur.

## Giriş snapshot-u

Hər qiymətləndirmə dəyişməz input snapshot-u dondurur:

- `decision_id`, `evaluation_at` və correlation ID;
- symbol/entity, timeframe və horizon;
- son bağlanmış bar/tick və onların yaş göstəricisi;
- spread, volatility, liquidity proxy və sessiya;
- bazar rejimi və detector confidence/version;
- uyğun Knowledge Base claim ID və versiyaları;
- conflict, limitation və review statusları;
- data-quality və operational-health snapshot-u;
- theoretical portfolio/exposure snapshot-u;
- decision, risk və config versiyaları;
- input checksum və `as_of` vaxtı.

Input sonradan dəyişmir. Yeni məlumat yeni decision evaluation yaradır.

## Giriş qapıları

Qiymətləndirmə başlamazdan əvvəl:

- bazar məlumatı freshness həddində olmalıdır;
- tick/bar lineage və quality qəbul həddində olmalıdır;
- yalnız bağlanmış məlumat istifadə edilməlidir;
- Knowledge Base claim `accepted`, compatible və review vaxtı keçməmiş olmalıdır;
- unresolved conflict və quarantine olmamalıdır;
- model/feature/event versiyaları uyğun olmalıdır;
- platforma operational health qərar hesablamasına imkan verməlidir;
- saat və timezone etibarlı olmalıdır;
- audit storage yazıla bilməlidir.

Bir qapı keçmirsə nəticə `blocked` və səbəb kodu olur.

## Decision proposal

Nəzəri təklif ən azı bunları daşıyır:

```text
proposal_id
decision_id
action = long_candidate | short_candidate | neutral | abstain
symbol
horizon
valid_from / expires_at
score_components
confidence / uncertainty
supporting_claims
opposing_claims
assumptions
limitations
invalidation_conditions
explanation
```

`long_candidate` və `short_candidate` order deyil. Onlar yalnız SHADOW qiymətləndirmə
istiqamətidir.

## Analiz nəticələrinin birləşdirilməsi

Aggregator əvvəlcədən versiyalanmış deterministik qayda istifadə edir:

- hər input claim-in uyğunluğu və sübut vəziyyəti ayrıca yoxlanır;
- eyni datasetdən törəyən korrelyasiyalı modellər müstəqil səs sayılmır;
- statistik, pattern, Visual AI və xəbər nəticələri sadəcə toplanmır;
- weight yalnız train/validation prosesində dondurulur, canlı nəticəyə görə dəyişmir;
- opposing evidence və abstain gizlədilmir;
- missing modul sıfır score kimi deyil, `missing_input` kimi saxlanır;
- rejimə uyğun olmayan bilik daxil edilmir;
- eyni input snapshot və config eyni proposal checksum-u verir.

## Konflikt və abstain

`abstain` normal və təhlükəsiz nəticədir. Aşağıdakılar abstain və ya block yaradır:

- confidence/uncertainty həddi keçmir;
- dəstəkləyən və əks bilik arasında həll olunmamış konflikt var;
- input paylanmadan kənardır;
- knowledge coverage kifayət deyil;
- source/model/data quality aşağıdır;
- horizon və qərar müddəti uyğun deyil;
- risk hesabı üçün məlumat natamamdır;
- eyni anda bir neçə rejim qeyri-müəyyəndir;
- decision expiry keçib.

Sistem “hər halda mövqe seçmək” məcburiyyətində deyil.

## İzah edilə bilən qərar

Hər proposal insan və maşın üçün yoxlanıla bilən izah verir:

- hansı claim-lər dəstəklədi və qarşı çıxdı;
- hansı input və zaman snapshot-u istifadə edildi;
- hər component score və çəkisinin mənası;
- hansı qapı və limitlərin keçdiyi;
- uncertainty, conflict və missing input;
- hansı şərtdə proposal etibarsız olacaq;
- niyə neutral/abstain/blocked nəticəsi yarandı;
- decision və risk mühərrikinin versiyası.

Generativ mətn kanonik səbəb deyil; kanonik səbəb struktur kod və istinadlardır.

## Risk siyasəti

Risk siyasəti versiyalanmış və dəyişməz config-dir. İlkin ailələr:

- per-decision risk budget;
- symbol və asset-class exposure;
- ümumi gross və net exposure;
- eyni faktor/correlation concentration;
- gündəlik və rolling loss həddi;
- maksimum drawdown və tail-risk həddi;
- maksimum eyni vaxtlı theoretical mövqe;
- spread, volatility və latency həddi;
- event/news blackout və market-session qaydası;
- model/knowledge concentration həddi;
- minimum free-risk-budget və cooldown.

Rəqəmsal hədlər ayrıca risk policy versiyasında təsdiqlənir; kod daxilində gizli
hardcode edilmir.

## Nəzəri mövqe ölçüsü

Phase 8 yalnız `theoretical_size` hesablayır:

- risk budget və stop/invalidation məsafəsi;
- instrument contract metadata-sı;
- qiymət, tick size/value və valyuta conversion;
- volatility və likvidlik məhdudiyyəti;
- mövcud theoretical exposure və correlation;
- maksimum/minimum ölçü və rounding;
- commission, spread, slippage və stress buffer.

Məlumatın biri bilinmirsə ölçü sıfır və status `size_unavailable` olur. Minimum lota
yuxarı yuvarlaqlaşdırmaq risk büdcəsini aşırsa proposal bloklanır.

## Risk qiymətləndirmə nəticəsi

```text
risk_evaluation_id
decision_id / proposal_id
result = eligible_for_shadow | reduced_for_shadow | blocked
theoretical_size
risk_budget_requested / allowed
limits_checked
limits_triggered
stress_results
policy_version
expires_at
checksum
```

`eligible_for_shadow` və `reduced_for_shadow` real icra icazəsi deyil.

## Hard və soft limitlər

- hard limit keçilirsə həmişə `blocked` olur;
- soft limit yalnız ölçünü azalda və ya review tələb edə bilər;
- soft limit heç vaxt hard limit-i bypass etmir;
- config parse edilmirsə bütün riskli proposal-lar bloklanır;
- limit yoxlaması timeout olarsa bloklanır;
- negative/NaN/infinite ölçü qəbul edilmir;
- bütün limitlər stress qiymətində də yoxlanır;
- risk policy köhnədirsə proposal qəbul edilmir.

## Kill switch və fövqəladə vəziyyət

Phase 8 broker orderi göndərməsə də gələcək mərhələlər üçün ümumi blok vəziyyətini
modelləşdirir:

- `global_halt`, `symbol_halt`, `strategy_halt` və `source_halt`;
- halt aktivdirsə yeni proposal ən çox `blocked` olur;
- halt səbəbi, actor, vaxt və expiry audit olunur;
- halt-ı silmək təzə autentifikasiya və iki mərhələli təsdiq tələb edir;
- restart halt vəziyyətini silmir;
- monitorinq əlçatan olmasa halt fail-closed qalır.

Real kill switch icrası Phase 10 müqaviləsinə aiddir.

## Manual müdaxilə

- insan proposal-u rədd edə və əlavə məhdudlaşdıra bilər;
- insan hard-risk blokunu bypass edə bilməz;
- blocked proposal manual olaraq eligible edilmir;
- weight, score və input tarixçəsi sonradan dəyişdirilmir;
- override ayrıca yeni event, səbəb və actor yaradır;
- yüksək riskli əməl təzə autentifikasiya və permission tələb edir;
- frontend gizli “force trade” funksiyası daşımır.

## Vaxt, expiry və idempotency

- proposal müəyyən `valid_from` və `expires_at` aralığında yaşayır;
- expiry-dən sonra yenidən qiymətləndirmə məcburidir;
- eyni input/config/idempotency key ikinci proposal yaratmır;
- gecikmiş risk cavabı yeni bazar snapshot-una tətbiq edilmir;
- saat geriyə gedərsə və ya clock etibarsızdırsa block edilir;
- retry eyni audit nəticəsini dublikatlaşdırmır.

## Portfolio və correlation sərhədi

Risk tək proposal-a yox, bütün theoretical portfolio-ya baxır:

- eyni symbol üzrə birləşdirilmiş exposure;
- valyuta və commodity faktor exposure-u;
- eyni xəbərə/modelə bağlı concentration;
- rolling correlation və uncertainty;
- hedge iddiası üçün stress ssenarisi;
- stale theoretical position və orphan vəziyyəti;
- ümumi risk budget reservation.

Correlation məlumatı yoxdursa müstəqillik fərz edilmir; konservativ bucket tətbiq edilir.

## SHADOW sərhədi

Phase 8 nəticələri Phase 9-a yalnız aşağıdakı formada keçir:

- immutable decision və risk event-ləri;
- nəzəri entry vaxtı və theoretical size;
- expiry və invalidation;
- tam izah və limit snapshot-u;
- real order göndərilməsinə açıq `execution_allowed=false` bayrağı.

Phase 9 nəticəni real bazarda izləyəcək, amma order açmayacaq.

## Konseptual event ailələri

- `DECISION_PROPOSED`;
- `DECISION_ABSTAINED`;
- `DECISION_BLOCKED`;
- `RISK_EVALUATED`;
- `RISK_LIMIT_REACHED`;
- `SHADOW_ELIGIBILITY_GRANTED`;
- `SHADOW_ELIGIBILITY_EXPIRED`;
- `RISK_HALT_ACTIVATED`;
- `RISK_HALT_RELEASED`.

Bu event-lər `ORDER_SENT` və `TRADE_OPENED` deyil.

## Konseptual API sərhədi

```text
POST /api/v2/decisions/evaluate
GET  /api/v2/decisions/{decision_id}
GET  /api/v2/decisions/{decision_id}/explanation
GET  /api/v2/decisions/{decision_id}/risk
GET  /api/v2/risk/policies/{version}
GET  /api/v2/risk/halts
POST /api/v2/risk/halts
POST /api/v2/risk/halts/{halt_id}/release
```

Yazma endpoint-ləri idempotency, role permission, təzə autentifikasiya və audit tələb
edir. Phase 8 API-də order endpoint-i yoxdur.

## Frontend təqdimatı

Panel:

- “SHADOW namizədi — real order deyil” nişanı göstərir;
- proposal, risk nəticəsi və theoretical size-i ayırır;
- supporting/opposing evidence və uncertainty göstərir;
- hər risk limitinin pass/reduced/blocked nəticəsini göstərir;
- stale, expired və blocked qərarı yaşıl təqdim etmir;
- risk halt vəziyyətini görünən saxlayır;
- manual rədd və halt üçün səbəb/təsdiq tələb edir;
- al/sat və broker order düyməsi göstərmir.

## Audit

Hər qiymətləndirmə üçün saxlanır:

- input snapshot və checksum;
- claim ID/versiyaları və `as_of` sorğusu;
- decision/risk config və kod versiyası;
- component score, weight, conflict və missing input;
- proposal, theoretical size və bütün risk hesabları;
- keçən və bloklayan limitlər;
- manual action, actor, permission və timestamp;
- expiry, retry və idempotency nəticəsi;
- heç bir order yaradılmadığının phase marker-i.

Audit yazılmırsa qərar yayımlanmır.

## Qəbul sınaqları

1. Eyni input/config eyni decision və risk checksum-u yaradır.
2. Stale və açıq bazar məlumatı proposal-u bloklayır.
3. Review vaxtı keçmiş/quarantined claim istifadə edilmir.
4. Missing input sıfır score kimi gizlədilmir.
5. Korrelyasiyalı modellər müstəqil səslər kimi sayılmır.
6. Həll olunmamış konflikt abstain və ya blocked yaradır.
7. Hard limit manual override ilə keçilmir.
8. NaN, negative və hesablanmayan size sıfır/blocked olur.
9. Minimum lot risk büdcəsini aşırsa yuxarı yuvarlaqlaşdırılmır.
10. Global halt restartdan sonra aktiv qalır.
11. Expired proposal yeni snapshot olmadan yenilənmir.
12. Audit yazma xətası qərarı fail-closed bloklayır.
13. Eyni idempotency key dublikat proposal yaratmır.
14. Frontend opposing evidence və risk blokunu gizlətmir.
15. API, event və frontend brokerə order göndərmir.

Bu sənəd qərar və risk hesablamasının SHADOW-a qədər olan təhlükəsiz sərhədidir;
real ticarət və icra icazəsi deyil.
