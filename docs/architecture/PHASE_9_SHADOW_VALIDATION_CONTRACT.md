# ESAS Platform — Phase 9 SHADOW Validasiya Müqaviləsi

Versiya: 1.0  
Status: DESIGN READY — NOT IMPLEMENTED  
Asılılıqlar: Phase 1–8 qəbul edilib və istifadə olunan konfiqurasiya dondurulub

## 1. Məqsəd

SHADOW rejimi qərar və risk sistemini real bazar axınında müşahidə edir, lakin brokerə
heç bir əmr göndərmir. Məqsəd nəzəri giriş/çıxışları səbəb-nəticə ardıcıllığını
pozmadan hesablamaq, alternativləri eyni şərtlərlə müqayisə etmək və yalnız kifayət
qədər sübut olduqda məhdud icra baxışını tövsiyə etməkdir.

SHADOW uğuru gəlirlilik zəmanəti, ACTIVE statusu və ya real əməliyyat icazəsi deyil.

## 2. Dəyişməz təhlükəsizlik sərhədi

- `execution_allowed=false` bütün SHADOW qərarlarında məcburidir.
- Order, mövqe dəyişməsi, broker hesabı yazısı və MT5 trade funksiyası qadağandır.
- SHADOW komponentində broker order səlahiyyəti və icra açarı saxlanmır.
- İcra endpoint-i, adapteri və növbəsi SHADOW prosesinə qoşulmur.
- Order cəhdi kritik təhlükəsizlik hadisəsidir: run dərhal `FAILED`, modul `HALTED`
  olur və manual araşdırma tələb edilir.
- SHADOW Phase 1 məlumat qəbuluna backpressure və ya gecikmə yarada bilməz.
- Nasazlıq zamanı sistem fail-closed işləyir: nəzəri qərar dayanar, real order yaranmaz.

## 3. Run-ın əvvəlcədən qeydiyyatı

Hər sınaq başlamazdan əvvəl dəyişməz manifest yaradılır:

- `shadow_run_id`, başlanma və planlaşdırılan bitmə vaxtı;
- sınaq edilən modul/model və versiyalar, champion və challenger rolları;
- kod commit-i, konfiqurasiya hash-i, feature/claim versiyaları;
- simvollar, timeframe-lər, sessiyalar və qəbul edilən bazar rejimləri;
- minimum bazar-açıq müşahidə müddəti və minimum uyğun qərar sayı;
- əsas və ikinci dərəcəli metriklər, hədlər və uğursuzluq qaydaları;
- nəzəri fill, spread, komissiya, slippage, latency və swap modeli;
- risk büdcəsi, eyni vaxtda mövqe və drawdown limitləri;
- məlumat keyfiyyəti, kəsinti və qeyri-müəyyən nəticələrin idarəsi;
- təsdiqləyən şəxs və rollback planı.

Run başladıqdan sonra hədəf, metrik və hədlər dəyişdirilmir. Yeni fərziyyə yeni
`shadow_run_id` tələb edir. Təqvim vaxtı deyil, yalnız bazarın açıq və giriş
məlumatının sağlam olduğu intervallar qəbul müddətinə daxil edilir.

## 4. Qəbul edilən giriş

Yalnız Phase 8 risk qapısından keçmiş, tam lineage-li və SHADOW üçün uyğun qərar
namizədi qəbul edilir. Hər giriş aşağıdakıları daşıyır:

- qərar, event və correlation identifikatorları;
- qərarın yaradıldığı bazar vaxtı və sistemə çatdığı vaxt;
- simvol, timeframe, istiqamət, nəzəri ölçü, expiry və invalidation;
- istifadə edilən snapshot, feature, model, bilik claim-i və risk versiyaları;
- izah, uncertainty, abstain və risk nəticəsi;
- `execution_allowed=false`.

Natamam lineage, gələcək məlumat, uyğun olmayan claim və ya köhnəlmiş snapshot
qərarı bloklayır və səbəb ayrıca audit olunur.

## 5. Səbəbiyyət və nəzəri fill

- Yalnız qərar vaxtında məlum olan məlumat istifadə edilir.
- Bar əsaslı qərar yalnız bağlanmış barla hesablanır.
- Nəzəri giriş qərardan sonra əldə edilə bilən ilk uyğun bid/ask və qeydiyyata alınmış
  latency ilə hesablanır; qərar barının əlverişli keçmiş qiymətinə giriş qadağandır.
- Long giriş ask, çıxış bid; short giriş bid, çıxış ask tərəfi ilə qiymətləndirilir.
- Spread, komissiya, konservativ slippage, swap və gap nəticədən çıxılır.
- Likvidlik və ya qiymət sübutu çatmırsa fill uydurulmur; nəticə `UNFILLED` və ya
  `INCONCLUSIVE` olur.
- Expiry və invalidation keçdikdən sonra geriyə dönüb mövqe açılmır.

Nəzəri həyat dövrü:

`PROPOSED -> ELIGIBLE -> THEORETICALLY_OPEN -> THEORETICALLY_CLOSED`

Alternativ sonluqlar: `ABSTAINED`, `RISK_BLOCKED`, `EXPIRED`, `UNFILLED`,
`INVALIDATED`, `INCONCLUSIVE`.

## 6. Nəzəri portfolio və risk

SHADOW ayrıca nəzəri hesab saxlayır. O, real hesab balansına toxunmur. Qərar açıldıqda
nəzəri risk rezerv edilir; bağlandıqda azad edilir. Eyni vaxtda mövqe, simvol və
istiqamət konsentrasiyası, gündəlik itki, ümumi risk və drawdown limitləri Phase 8
qaydaları ilə eyni tətbiq olunur. Limitə görə açılmayan qərar nəticədən silinmir,
`RISK_BLOCKED` kimi saxlanır.

## 7. Champion/challenger müqayisəsi

- Namizədlər eyni dəyişməz input snapshot-larını alır.
- Eyni qərar vaxtı, risk büdcəsi, fill/xərc modeli və qiymətləndirmə horizon-u tətbiq edilir.
- Baseline əvvəlcədən seçilir; run bitəndən sonra əlverişli baseline seçmək qadağandır.
- Abstain, blok, fill olmayan və zidd qərarlar ayrıca ölçülür.
- Modellər bir-birinin nəticəsini giriş kimi istifadə etmir.
- Müqayisə ümumi nəticə ilə yanaşı simvol, sessiya və bazar rejimi üzrə göstərilir.

## 8. Kəsinti, restart və təkrar emal

- Checkpoint son işlənmiş event və açıq nəzəri mövqeləri saxlayır.
- Event və qərar identifikatorları idempotentdir; restart dublikat mövqe yaratmır.
- Kəsinti intervalı ayrıca qeyd edilir və canlı müşahidə kimi sayılmır.
- Sonradan replay edilən məlumat canlı SHADOW nəticəsinə qarışdırılmır.
- Restart keçmiş qiymətə baxaraq yeni qərar və ya əlverişli fill yarada bilməz.
- Giriş köhnədirsə sistem `DEGRADED` olur, qərar yaratmağı dayandırır və no-order
  invariantını qoruyur.

## 9. Saxlama və audit event-ləri

Minimum event ailələri:

- `SHADOW_RUN_STARTED`
- `SHADOW_DECISION_RECORDED`
- `SHADOW_RISK_BLOCKED`
- `SHADOW_THEORETICAL_POSITION_OPENED`
- `SHADOW_THEORETICAL_POSITION_CLOSED`
- `SHADOW_DATA_GAP_RECORDED`
- `SHADOW_RUN_COMPLETED`
- `SHADOW_PROMOTION_RECOMMENDED`
- `SHADOW_PROMOTION_REJECTED`

Event-lər append-only saxlanır; source event, qərar, risk, xərc modeli və run
manifestinə istinad edir. Heç biri `ORDER_*`, broker ticket-i və ya real mövqe
identifikatoru yarada bilməz.

## 10. Monitorinq və frontend

Monitorinq ən azı heartbeat, input age, qərar latency-si, abstain/risk-block nisbəti,
nəzəri açıq mövqelər, net PnL, drawdown, queue, məlumat boşluğu, drift və model
versiyasını göstərir.

Frontend bütün SHADOW ekranlarında aydın **“NƏZƏRİDİR — REAL ƏMƏLİYYAT YOXDUR”**
banner-i göstərir. Champion/challenger nəticələri və qeyri-müəyyənlik görünür. Order
açmaq, mövqe bağlamaq və ya icranı aktivləşdirmək düyməsi olmur.

## 11. Statistik qəbul qapısı

Run yalnız əvvəlcədən qeydiyyata alınmış bütün şərtlərlə qiymətləndirilir:

1. minimum bazar-açıq müddəti və minimum uyğun nümunə sayı tamamlanıb;
2. tələb olunan sessiya və bazar rejimləri üzrə əhatə kifayətdir;
3. net nəticə bütün qeydiyyatlı xərclərdən sonradır;
4. əsas metrik baseline-dan əvvəlcədən müəyyən edilmiş həddlə üstündür və uncertainty
   intervalı təqdim edilir;
5. maksimum drawdown, tail loss, konsentrasiya və risk pozuntuları limit daxilindədir;
6. nəticə tək simvol, sessiya və ya qısa əlverişli intervaldan asılı deyil;
7. məlumat sızması, seçmə nəticə, retrospektiv parametr və ya holdout pozuntusu yoxdur;
8. restart/recovery, idempotency və lineage sübutu tamdır;
9. order cəhdi, broker yazısı və real hesab təsiri sayı dəqiq `0`-dır;
10. nəticə dəyişməz manifest və event-lərlə təkrar hesablana bilir.

Hər hansı məcburi qapı ödənmirsə nəticə `FAIL` və ya sübut çatmırsa `INCONCLUSIVE`
olur. Zəif nəticə müddəti uzatmaqla və ya post-hoc hədlə gizlədilmir.

## 12. Keçid qərarı

Phase 9 yalnız bu nəticələrdən birini verir:

- `REJECTED`
- `MORE_EVIDENCE_REQUIRED`
- `RECOMMENDED_FOR_LIMITED_EXECUTION_REVIEW`

Sonuncu nəticə real treydi aktivləşdirmir. Phase 10 məhdud icra müqaviləsi, ayrıca
insan təsdiqi, kiçik risk limiti, kill switch, broker təhlükəsizlik yoxlaması və
rollback sübutu olmadan ACTIVE və ya order icazəsi verilmir.

## 13. Məcburi qəbul sınaqları

1. SHADOW qərarında `execution_allowed=true` qəbul edilmir.
2. Order adapterinə istənilən çağırış run-ı kritik xəta ilə dayandırır.
3. Eyni event restartdan sonra ikinci nəzəri mövqe yaratmır.
4. Qərardan əvvəlki əlverişli qiymət fill kimi seçilmir.
5. Long/short bid-ask tərəfləri düzgün tətbiq edilir.
6. Spread, komissiya, slippage, latency və swap net nəticəyə daxil edilir.
7. Natamam lineage qərarı bloklayır.
8. Expired və invalidated qərar sonradan açılmır.
9. Risk limitini keçən qərar `RISK_BLOCKED` olur.
10. Champion və challenger eyni input snapshot-ı alır.
11. Kəsinti intervalı bazar-açıq müşahidə vaxtına daxil edilmir.
12. Replay canlı SHADOW nəticəsinə qarışmır.
13. Nəzəri portfolio real hesab və MT5 mövqelərini dəyişmir.
14. Frontend nəzəri rejimi aydın göstərir və order əməliyyatı təqdim etmir.
15. Qəbul hesabatı manifest, metrik, uncertainty, istisna və audit checksum-larını daşıyır.

## 14. Bu sənədin hazırkı təsiri

Bu, gələcək Phase 9 tətbiqi üçün müqavilədir. Hazırda SHADOW run başladılmır, rəsmi
24 saatlıq Phase 1 sınağı əvəz edilmir və platformaya real order imkanı əlavə olunmur.
