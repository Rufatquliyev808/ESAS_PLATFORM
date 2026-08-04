# ESAS Platform — Phase 4 pattern və texniki analiz müqaviləsi

Versiya: 1.0  
Status: **PARTIALLY IMPLEMENTED — RESEARCH ONLY**
Tətbiq şərti: Phase 1–3 qəbul qapılarının uğurla bağlanması

Əlaqəli müqavilələr:

- `docs/architecture/PHASE_3_RESEARCH_VALIDATION_CONTRACT.md`
- `docs/architecture/PHASE_3_STATISTICAL_ANALYSIS_CONTRACT.md`

## Məqsəd və sərhəd

Bu müqavilə xam tick snapshot-dan deterministik barların, texniki feature-ların və
pattern namizədlərinin necə yaradılacağını, backtest ediləcəyini və audit
olunacağını müəyyən edir.

Phase 4:

- əvvəlcədən seçilmiş pattern-i sübut etməyə çalışmır;
- yalnız replay snapshot-u oxuyur və xam tick-i dəyişmir;
- pattern namizədini ticarət siqnalı adlandırmır;
- brokerə order göndərmir və real mövqe açmır;
- EXPERIMENTAL nəticəni birbaşa ACTIVE etmir;
- yalnız sonrakı SHADOW sınağına namizəd sübut paketi yarada bilər.

## Giriş qeydiyyatı

Hər iş başlamazdan əvvəl bunlar dəyişməz qeyd olunur:

- `experiment_id`, `analysis_id` və `candidate_id`;
- symbol, UTC `[start_at, end_at)` sərhədi və dataset fingerprint;
- quality report və statistik analiz versiyası;
- bar, feature, pattern və backtest müqavilə versiyaları;
- timeframe, qiymət mənbəyi və pəncərə sərhədi;
- indikator/pattern parametrləri və warm-up qaydası;
- label, horizon, entry/exit və icra fərziyyələri;
- train, validation, holdout və walk-forward sərhədləri;
- komissiya, spread, slippage, gecikmə və risk büdcəsi;
- primary metric, baseline və əvvəlcədən müəyyən edilmiş qəbul hədləri;
- Git commit, asılılıq hash-i, konfiqurasiya və seed.

İş başladıqdan sonra dəyişiklik yeni versiya və yeni namizəd yaradır.

## Deterministik bar müqaviləsi

Barlar yalnız Phase 3-də müəyyən edilmiş etibarlı mid-price tick-lərindən yaradılır.
İlkin timeframe-lər: `1s`, `10s`, `1m`, `5m`, `15m`, `1h`.

Hər bar UTC epoch sərhədinə bağlı yarıaçıq pəncərədir:

```text
[bar_start, bar_end)
```

Sabit kanonik sıra `event_timestamp ASC, event_id ASC` olur:

- `open`: ilk etibarlı mid;
- `high`: maksimum etibarlı mid;
- `low`: minimum etibarlı mid;
- `close`: son etibarlı mid;
- `tick_count`: pəncərədəki etibarlı mid sayı;
- `tick_volume`: MT5 tick-volume cəmi, real birja həcmi deyil;
- `spread_*`: yalnız etibarlı bid/ask cütlərindən təsviri göstəricilər;
- `first_event_id` və `last_event_id`: lineage sərhədi;
- quality və coverage işarələri.

Bar yalnız `bar_end` keçdikdən sonra bağlanmış sayılır. Açıq bar pattern və backtest
qərarında istifadə edilmir. Boş bar yaradılmır, forward-fill edilmir və sıfır
volatilite kimi qəbul olunmur. Təqvim yoxdursa boşluğun bazar bağlanması olduğu
iddia edilmir.

Bar-lar xam məlumat deyil, versiyalanmış derived artefaktdır. Mənbə fingerprint və
qurucu versiyası olmadan etibarlı sayılmır.

## Texniki feature kataloqu

Hər feature ayrıca `feature_id`, semantik versiya, parametr schema-sı, input
timeframe-i, warm-up uzunluğu və çıxış vahidi daşıyır.

İlkin namizəd ailələri:

- return və rolling volatility;
- rolling spread və tick sürəti;
- sadə/eksponensial hərəkətli orta;
- range, true range və ATR tipli ölçülər;
- momentum və rate-of-change;
- RSI tipli bounded oscillator;
- rolling high/low məsafəsi;
- yalnız tick-volume kimi etiketlənmiş həcm feature-ları.

Kataloq hazır strategiya siyahısı deyil. Hər feature ayrıca hipotez və ablation
testindən keçir.

## Səbəbiyyət və warm-up

Bar `t` üçün feature yalnız `t` və ondan əvvəl bağlanmış barlardan hesablana bilər.

- centered rolling window qadağandır;
- gələcək bar ilə interpolation və smoothing qadağandır;
- backfill qadağandır;
- normalizer və parametr yalnız train hissəsində fit edilir;
- warm-up tamamlanmayan dəyər `null/warmup_incomplete` olur;
- missing bar səssiz doldurulmur;
- label və gələcək nəticə feature cədvəlinə qarışdırılmır;
- feature timestamp onun real məlum olduğu ən erkən vaxtdır.

## Pattern namizədi

Pattern namizədi müşahidə olunan şərtin dəyişməz təsviridir:

- versiyalanmış qayda/model və parametrlər;
- istifadə olunan feature və timeframe-lər;
- səbəbiyyət üçün lazım olan son bağlanmış bar;
- başlanma və bitmə vaxtı;
- confidence və ya score-un dəqiq mənası;
- trigger səbəbləri və audit lineage-i;
- `insufficient_data` və `abstain` imkanı.

Pattern tapıntısı `buy`, `sell`, `long`, `short` və ya order əmri deyil. Pattern
hadisəsi lazım olduqda `PATTERN_FOUND` event müqaviləsinin ayrıca yeni versiyası ilə
yayına bilər, lakin ilkin EXPERIMENTAL mərhələdə yalnız tədqiqat bazasında saxlanır.

## Pattern ailələri və discovery

İlkin tədqiqat aşağıdakı neytral ailələri yoxlaya bilər:

- trend/momentum namizədi;
- mean-reversion namizədi;
- volatility expansion/contraction namizədi;
- spread/tick-rate vəziyyəti;
- çox-timeframe uyğunluq namizədi;
- bazar rejiminə şərtlənmiş namizəd.

Ad iqtisadi həqiqət deyil. Məsələn, `trend_candidate_v1` yalnız qeyd edilmiş qaydanın
adı olur. Eyni məlumatda çox sayda pattern axtarışı multiple-testing reyestrinə
daxil edilir; yalnız uğurluların saxlanması qadağandır.

## Label və horizon

Pattern-in gələcək nəticəsi əvvəlcədən versiyalanmış label ilə ölçülür:

- horizon vaxt və ya bağlanmış bar sayı ilə sabitdir;
- label qiymət mənbəyi əvvəlcədən seçilir;
- neutral/dead-zone sərhədi varsa əvvəlcədən qeyd olunur;
- üst-üstə düşən horizon-lar effective sample size və purge/embargo tələb edir;
- horizon tamamlanmayıbsa nümunə nəticəyə daxil edilmir;
- ən əlverişli gələcək high/low entry qiyməti kimi istifadə edilmir.

Label yalnız qiymətləndirmə üçündür və trigger vaxtında feature deyil.

## Backtest icra modeli

Backtest pattern-i real icra kimi şişirtməməlidir:

- namizəd yalnız bağlanmış bar bitəndə məlum sayılır;
- ən erkən nəzəri entry növbəti əlçatan tick/bar-dadır;
- side, entry, exit və invalidation qaydası əvvəlcədən qeyd olunur;
- bid/ask istiqamətə uyğun istifadə edilir; mid ilə pulsuz icra edilmir;
- spread, komissiya, slippage və gecikmə normal/pis/stress ssenarisində çıxılır;
- eyni anda açıq namizədlər kapital və risk büdcəsini paylaşır;
- likvidlik məlumatı yoxdursa fill zəmanəti verilmir;
- stop/limit bar daxilində hansı ardıcıllıqla dəyib bilinmirsə konservativ nəticə
  və ya `ambiguous_fill` tətbiq olunur;
- gap və missing data olan interval ayrıca məhdudiyyət daşıyır;
- rollover, swap və digər broker xərci məlum deyilsə nəticə məhdud sayılır.

Bu backtest order göndərmir; yalnız dəyişməz simulyasiya artefaktı yaradır.

## Baseline və müqayisə

Hər namizəd ən azı bunlarla eyni xərc/risk sərhədində müqayisə edilir:

- no-signal baseline;
- eyni tezlikli təsadüfi zaman baseline-ı;
- sadə tək-feature qaydası;
- varsa əvvəlki təsdiqlənmiş namizəd.

Nəticə train, validation, holdout və walk-forward üzrə ayrı verilir. Parameter
sweep-in yalnız ən yaxşı nöqtəsi deyil, tam səthi və sınaq sayı saxlanır.

## Nəticə və risk göstəriciləri

Hər backtest nəticəsi ən azı bunları verir:

- ümumi, etibarlı, kənarlaşdırılmış və ambiguous nümunə sayı;
- gross və bütün xərclərdən sonrakı net nəticə;
- hit rate, orta/median nəticə və payoff paylanması;
- maksimum drawdown və drawdown müddəti;
- turnover, exposure və namizəd tezliyi;
- tail loss və stress ssenarisi;
- effect size, confidence interval və multiple-testing düzəlişi;
- zaman, simvol, sessiya və rejim üzrə stabillik;
- baseline fərqi və uncertainty;
- data-quality və icra məhdudiyyətləri.

Az nümunə, böyük uncertainty və ya xərclərdən sonra itən effekt
`insufficient_evidence` sayılır.

## Namizəd vəziyyətləri

İcazəli vəziyyətlər:

`draft → registered → running → evaluated → accepted_for_shadow | rejected → archived`

Əlavə son vəziyyətlər: `blocked_by_data_quality`, `invalid_leakage`,
`insufficient_evidence`, `failed`, `cancelled`.

`accepted_for_shadow` real ticarət icazəsi deyil. O yalnız Phase 9 SHADOW sistemində
order açmadan canlı müşahidə namizədidir.

## API nəticə müqaviləsi

Phase 2 scheduler və `/api/v2` sərhədində konseptual resurslar:

```text
POST /api/v2/pattern-candidates
GET  /api/v2/pattern-candidates/{candidate_id}
GET  /api/v2/pattern-candidates/{candidate_id}/features
GET  /api/v2/pattern-candidates/{candidate_id}/backtest
POST /api/v2/pattern-candidates/{candidate_id}/archive
```

Yaratma idempotency key tələb edir. Böyük nəticələr imzalanmış snapshot cursor ilə
səhifələnir. Archive xam tick, audit və sübutu silmir.

## Frontend təqdimatı

Panel:

- “Tədqiqat namizədi — ticarət siqnalı deyil” nişanı göstərir;
- dataset, timeframe, qayda və feature versiyasını göstərir;
- train/validation/holdout/walk-forward nəticələrini qarışdırmır;
- gross və net nəticəni, xərcləri və uncertainty-ni yanaşı göstərir;
- leakage, insufficient data və quality blokunu gizlətmir;
- bütün parametr sweep-i və uğursuz eksperimentləri əlçatan edir;
- `accepted_for_shadow` statusunu “al/sat” kimi təqdim etmir;
- order düyməsi və real icra idarəsi göstərmir.

## Audit və artefaktlar

Saxlanılan sübut:

- dataset və derived bar checksum-u;
- bar, feature, pattern, label və backtest versiyaları;
- qeydiyyat, parametr və primary metric;
- kod commit-i, asılılıq hash-i və seed;
- bütün variantların nəticəsi və multiple-testing sayı;
- xərclər, fill fərziyyələri və məhdudiyyətlər;
- qəbul/rədd qərarı, actor və timestamp;
- uğursuz və arxivlənmiş namizədlər.

Xam tick və əvvəlki nəticə heç vaxt səssiz yenilənmir.

## Qəbul sınaqları

1. Eyni tick snapshot-u eyni checksum-lu barlar yaradır.
2. Eyni timestamp-li tick-lər `event_id` ilə deterministik OHLC yaradır.
3. Açıq bar feature və pattern qərarına daxil olmur.
4. Boş bar forward-fill edilmir.
5. Warm-up tamamlanmadan indikator dəyəri yaranmır.
6. Gələcək bar feature-a və trigger timestamp-a sızmır.
7. Label horizon feature cədvəlindən ayrıdır.
8. Entry pattern məlum olmamışdan əvvəl baş vermir.
9. Bid/ask, komissiya, slippage və gecikmə net nəticəyə daxil edilir.
10. Ambiguous intrabar fill optimist nəticə yaratmır.
11. Multiple-testing qeydiyyatı olmadan namizəd qəbul edilmir.
12. Holdout və walk-forward zəifdirsə train uğuru SHADOW statusu vermir.
13. Uğursuz namizəd və sübut silinmir.
14. Analizdən əvvəl/sonra xam tick checksum-u dəyişmir.
15. Heç bir endpoint və frontend elementi real order yaratmır.

Bu sənəd pattern və texniki analiz tədqiqatının sərhədidir; strategiya və real
ticarət icazəsi deyil.
