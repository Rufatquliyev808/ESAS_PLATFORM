# ESAS Platform — Phase 10 Məhdud İcra Müqaviləsi

Versiya: 1.0  
Status: DESIGN READY — NOT IMPLEMENTED  
Asılılıqlar: Phase 1–9 qəbul edilib, SHADOW nəticəsi ayrıca təsdiqlənib

## 1. Məqsəd

Phase 10 statistik olaraq qəbul edilmiş SHADOW namizədini ən kiçik təhlükəsiz real
icra sərhədində yoxlamaq üçündür. Bu mərhələ tam avtomatik treyd, limitsiz kapital,
özbaşına model seçimi və ya gəlir zəmanəti deyil.

Məhdud icra yalnız əvvəlcədən təsdiqlənmiş simvol, istiqamət, vaxt, mövqe ölçüsü və
risk büdcəsi daxilində işləyir. Default vəziyyət `EXECUTION_DISABLED`-dır.

## 2. Dəyişməz təhlükəsizlik prinsipləri

- İcra ayrıca feature flag və server-side permission olmadan açıla bilməz.
- Frontend təkbaşına icranı aktivləşdirə, riski artıra və kill switch-i aça bilməz.
- Model, Decision Layer və MT5 Bridge özünə icra icazəsi verə bilməz.
- Bütün limitlər server tərəfində, order göndərilməzdən dərhal əvvəl yenidən yoxlanır.
- Natamam, köhnə, uyğunsuz və ya təkrar əmr fail-closed bloklanır.
- Risk limiti artırılması yeni təsdiq və yeni icra manifesti tələb edir.
- Açıq mövqenin mövcudluğu bilinmirsə yeni mövqe açılmır.
- Kill switch işə düşdükdə yeni orderlər dayanır; açıq mövqelər əvvəlcədən təsdiqlənmiş
  fövqəladə siyasətlə idarə olunur.
- Secret, broker parolu və token event, log, frontend və sübut paketinə yazılmır.

## 3. İcraya qəbul qapısı

Order namizədi yalnız bütün şərtlər eyni anda doğrudursa qəbul edilə bilər:

1. Phase 9 nəticəsi `RECOMMENDED_FOR_LIMITED_EXECUTION_REVIEW`-dur;
2. müstəqil insan baxışı namizəd versiyanı və risk büdcəsini təsdiqləyib;
3. kod commit-i, model, qərar, risk və konfiqurasiya versiyaları manifestlə eynidir;
4. bazar məlumatı təzə, saatlar sinxron və broker sessiyası sağlamdır;
5. global, hesab, gün, simvol, istiqamət və strategiya limitləri keçilməyib;
6. kill switch bağlı deyil və execution lease etibarlıdır;
7. manual təsdiq tələb olunursa təzə, birdəfəlik təsdiq mövcuddur;
8. brokerdəki real order/mövqe snapshot-ı platforma ilə uzlaşdırılıb;
9. idempotency açarı və correlation zənciri tamdır;
10. order brokerin minimum/maximum lot, step, stop-distance və sessiya qaydalarına uyğundur.

Bir şərt ödənmirsə order yaradılmır və səbəb immutable audit event-i kimi saxlanır.

## 4. İcra manifesti və limitlər

Hər məhdud icra run-ı başlamazdan əvvəl dəyişməz manifest yaradılır:

- `execution_run_id`, təsdiq edənlər, başlanma və avtomatik bitmə vaxtı;
- SHADOW sübut paketi və acceptance identifikatoru;
- icazəli modul/model/decision/risk versiyaları və commit hash-i;
- hesab aliası, broker environment-i və yalnız icazəli simvollar;
- icazəli order və time-in-force növləri;
- bir order, bir mövqe, simvol, strategiya, gün və run üzrə maksimum risk;
- maksimum nominal exposure, leverage, açıq mövqe və pending order sayı;
- maksimum gündəlik itki, drawdown, ardıcıl itki və slippage;
- icazəli sessiyalar, xəbər/rollover blok intervalları;
- manual təsdiqin müddəti və kimlərin təsdiq edə biləcəyi;
- kill switch, flatten/hold siyasəti və rollback proseduru.

Manifest vaxtı bitdikdə execution lease avtomatik ləğv edilir. Davam üçün yeni manual
təsdiq tələb olunur. Limitlər run zamanı yalnız azaldıla bilər; artırmaq yeni run tələb edir.

## 5. Manual təsdiq və səlahiyyət ayrılığı

- Operator namizədi görə və təsdiq sorğusu yarada bilər.
- Təsdiqləyən şəxs qərar, risk, cari qiymət, spread, mümkün zərər və expiry-ni görür.
- Təsdiq konkret `decision_id + order_intent_hash` üçün birdəfəlikdir.
- Təsdiqin qısa müddəti olur; qiymət/risk material dəyişərsə avtomatik etibarsızlaşır.
- Təsdiq verən şəxs limiti və order payload-ını təsdiqdən sonra dəyişə bilməz.
- Yüksək riskli dəyişiklik üçün iki nəfər prinsipi tətbiq oluna bilər.
- Login sessiyası, frontend düyməsi və ya əvvəlki təsdiq gələcək orderlərə ümumi icazə deyil.

## 6. Order niyyəti və idempotency

Decision Layer broker payload-ı deyil, dəyişməz `order_intent` yaradır. Execution Layer
onu brokerə uyğunlaşdırmazdan əvvəl risk qapısını yenidən işlədir.

Minimum order intent sahələri:

- `order_intent_id`, `decision_id`, `execution_run_id`;
- correlation və causation identifikatorları;
- simvol, istiqamət, order növü, həcm, expiry;
- nəzərdə tutulan entry, stop, take-profit və maksimum slippage;
- qərar/risk/model/manifest versiyaları;
- manual approval identifikatoru;
- idempotency açarı və payload hash-i.

Eyni idempotency açarı ikinci broker orderi yarada bilməz. Cavab gecikdikdə kor-koranə
retry qadağandır: əvvəl broker state-i order identifikatoru, client ID və zaman aralığı
ilə uzlaşdırılır.

## 7. Order həyat dövrü

İcazəli vəziyyətlər:

`INTENT_CREATED -> RISK_APPROVED -> MANUALLY_APPROVED -> SUBMITTING -> ACKNOWLEDGED`

Sonrakı vəziyyətlər:

- `PARTIALLY_FILLED`
- `FILLED`
- `CANCEL_REQUESTED -> CANCELLED`
- `REJECTED`
- `EXPIRED`
- `UNKNOWN_RECONCILIATION_REQUIRED`

Hər keçid yeni immutable event yaradır. Broker cavabı gəlmədən `FILLED` qəbul edilmir.
`UNKNOWN_RECONCILIATION_REQUIRED` vəziyyətində yeni orderlər bloklanır.

## 8. Broker və MT5 adapter sərhədi

- Adapter yalnız versiyalanmış Execution interface-i qəbul edir.
- Broker simvolu, digits, volume step, tick size/value və trading mode başlanğıcda yoxlanır.
- Demo, paper və real hesab qarışdırılmır; environment manifestdə açıq göstərilir.
- Account number log və frontenddə maskalanır.
- Trade icazəsi olmayan terminal, market closed, requote, off-quotes, invalid stops,
  margin və connectivity cavabları ayrıca kateqoriyalaşdırılır.
- Broker server vaxtı və platforma UTC vaxtı birlikdə saxlanır.
- Adapter məlumat toplama Bridge-indən məntiqi ayrılır; icra nasazlığı tick qəbulunu saxlamır.

## 9. Pre-trade risk qapısı

Order göndərilməzdən dərhal əvvəl atomik şəkildə yoxlanır:

- hesab equity/balance və free margin snapshot-ı;
- real açıq mövqe və pending orderlər;
- cari bid/ask, spread, məlumat yaşı və bazar sessiyası;
- stop məsafəsi, nəzəri maksimum zərər və valyuta çevrilməsi;
- bütün exposure, leverage, gündəlik itki və drawdown limitləri;
- dublikat və zidd istiqamətli order;
- xəbər, rollover, gap, yüksək spread və qeyri-normal volatility bloku;
- kill switch, lease, model statusu və manual approval.

Risk hesabı mümkün zərəri konservativ yuvarlaqlaşdırır. Hesab və ya qiymət məlumatı
çatışmırsa `RISK_BLOCKED` qaytarılır.

## 10. Kill switch və fövqəladə dayandırma

Kill switch səviyyələri:

- `STRATEGY_HALT`
- `SYMBOL_HALT`
- `ACCOUNT_HALT`
- `GLOBAL_HALT`

Trigger-lər:

- manual fövqəladə dayandırma;
- gündəlik itki/drawdown və exposure həddi;
- gözlənilməz order, dublikat və ya state uyğunsuzluğu;
- broker bağlantısı və ya məlumat köhnəlməsi;
- slippage/rejection/latency həddinin aşılması;
- model, konfiqurasiya və ya manifest uyğunsuzluğu;
- audit və storage yazısının mümkün olmaması.

Kill switch lokal UI-dan asılı deyil və restartdan sonra bağlı vəziyyətini qoruyur.
Onu açmaq kök səbəb hesabatı, broker reconciliation, təzə autentifikasiya və ayrıca
manual təsdiq tələb edir. “Halt” avtomatik “bütün mövqeləri bazardan bağla” demək deyil;
flatten qərarı əvvəlcədən təsdiqlənmiş fövqəladə siyasətlə verilir.

## 11. Restart və reconciliation

- Startup zamanı yeni orderlər default olaraq bağlıdır.
- Platforma əvvəl immutable event-ləri, sonra broker order/mövqe tarixçəsini oxuyur.
- Açıq mövqe, pending order, partial fill və naməlum submission uzlaşdırılmadan lease verilmir.
- Platforma crash-dən sonra keçmiş intent-i avtomatik yenidən göndərmir.
- Brokerdə olub platformada olmayan order kritik incident yaradır.
- Platformada olub brokerdə görünməyən submission `UNKNOWN` qalır və manual araşdırılır.
- Reconciliation nəticəsi checksum və snapshot vaxtı ilə audit edilir.

## 12. İcra xərcləri və nəticə ölçümü

Hər fill üçün qərar qiyməti, submit qiyməti, broker fill-i, spread, komissiya, slippage,
swap, latency və partial fill ölçülür. SHADOW nəzəri nəticəsi real nəticə ilə eyni
horizon və risk vahidində müqayisə edilir.

Müsbət PnL təhlükəsizlik pozuntusunu kompensasiya etmir. Təhlükəsizlik, bütövlük,
reconciliation və limit pozuntuları ayrıca məcburi qapılardır.

## 13. Event ailələri və audit

Minimum event-lər:

- `EXECUTION_RUN_AUTHORIZED`
- `ORDER_INTENT_CREATED`
- `ORDER_RISK_APPROVED`
- `ORDER_RISK_BLOCKED`
- `ORDER_MANUALLY_APPROVED`
- `ORDER_SUBMISSION_REQUESTED`
- `ORDER_ACKNOWLEDGED`
- `ORDER_PARTIALLY_FILLED`
- `ORDER_FILLED`
- `ORDER_REJECTED`
- `ORDER_CANCEL_REQUESTED`
- `ORDER_CANCELLED`
- `EXECUTION_STATE_UNKNOWN`
- `EXECUTION_RECONCILED`
- `EXECUTION_HALT_TRIGGERED`
- `EXECUTION_HALT_RELEASED`
- `EXECUTION_RUN_COMPLETED`

Event-lər secret saxlamır, dəyişdirilmir və decision-dan broker cavabına qədər tam
causation zənciri yaradır. Audit storage yazıla bilmirsə yeni order göndərilmir.

## 14. Monitorinq və frontend

Monitorinq aşağıdakıları göstərir:

- execution statusu, lease expiry və manifest versiyası;
- açıq mövqe/pending order, exposure, gündəlik PnL və drawdown;
- risk limitlərinin cari istifadəsi;
- latency, slippage, rejection və reconciliation vəziyyəti;
- kill switch səviyyəsi və səbəbi;
- son manual approval və audit correlation-u.

Frontenddə real icra aktivdirsə daimi və aydın **“REAL MƏHDUD İCRA”** banner-i olur.
Order öncəsi maksimum mümkün zərər göstərilir. Limit artırmaq, halt açmaq və fövqəladə
əməliyyatlar təzə autentifikasiya tələb edir. UI backend təsdiqi olmadan uğur göstərmir.

## 15. Məhdud icranın qəbul meyarları

Phase 10 run-ı yalnız aşağıdakılarla `PASS` ola bilər:

1. bütün orderlər təsdiqlənmiş manifest və risk daxilindədir;
2. icazəsiz, dublikat və gözlənilməz order sayı `0`-dır;
3. bütün broker state-i event tarixçəsi ilə uzlaşdırılıb;
4. risk, daily loss və drawdown limit pozuntusu yoxdur;
5. kill switch sınaqları və restart recovery keçib;
6. real xərclər və slippage əvvəlcədən seçilmiş hədlərdədir;
7. hər orderin qərar, approval, risk və broker audit zənciri tamdır;
8. məlumat itkisi və audit boşluğu yoxdur;
9. manual operator proseduru və rollback real məşqlə yoxlanıb;
10. nəticə SHADOW fərqini və qeyri-müəyyənliyi açıq göstərir.

Bir kritik təhlükəsizlik pozuntusu run-ı `FAIL` edir. Sübut çatmırsa `INCONCLUSIVE` olur.
Heç bir nəticə limitsiz və nəzarətsiz ticarəti avtomatik aktivləşdirmir.

## 16. Məcburi qəbul sınaqları

1. Feature flag bağlı olduqda order adapterinə çağırış edilmir.
2. Vaxtı bitmiş lease və approval orderi bloklayır.
3. Dəyişmiş payload əvvəlki approval ilə qəbul edilmir.
4. Eyni idempotency açarı yalnız bir broker orderi yaradır.
5. Timeout sonrası kor retry edilmir, reconciliation başlayır.
6. Köhnə qiymət və natamam hesab snapshot-ı orderi bloklayır.
7. Bütün risk limitləri broker submission-dan əvvəl yenidən yoxlanır.
8. Daily loss həddi kill switch-i işə salır.
9. Kill switch restartdan sonra aktiv qalır.
10. Audit storage nasazlığı yeni orderi bloklayır.
11. Partial fill düzgün exposure və qalan həcmi hesablayır.
12. Broker rejection və unknown state düzgün event-ləşdirilir.
13. Platforma/broker fərqi yeni orderləri bloklayır.
14. Secret və tam hesab nömrəsi log, event və frontenddə görünmür.
15. Frontend real icranı aydın göstərir və backend təsdiqi olmadan uğur bildirmir.
16. Məlumat toplama axını execution nasazlığından təsirlənmir.

## 17. Hazırkı təsir

Bu sənəd gələcək Phase 10 tətbiqi üçün təhlükəsizlik müqaviləsidir. Hazırda MT5 order
interfeysi yaradılmır, broker icazəsi verilmir, real ticarət aktivləşdirilmir və Phase 1
üçün rəsmi 24 saatlıq sabitlik sınağı əvəz edilmir.
