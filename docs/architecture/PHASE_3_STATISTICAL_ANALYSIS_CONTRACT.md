# ESAS Platform — Phase 3 statistik analiz nəticə müqaviləsi

Versiya: 1.0  
Status: **IMPLEMENTED — SA-001–SA-007 backend, frontend və asinxron job resursu tamamlanıb**  
Tətbiq şərti: Phase 1 və Phase 2 qəbul qapılarının uğurla bağlanması

Əlaqəli tədqiqat və validasiya qaydaları:
`docs/architecture/PHASE_3_RESEARCH_VALIDATION_CONTRACT.md`

## Məqsəd və sərhəd

Bu müqavilə sabit replay snapshot-u üzərində təsviri statistikanın necə
hesablanacağını, versiyalanacağını və təqdim ediləcəyini müəyyən edir.

Statistik analiz:

- xam tick məlumatını yalnız Phase 2 replay sərhədi ilə oxuyur;
- `tick_events` sətrlərini dəyişmir və silmir;
- məlumat keyfiyyəti tapıntılarını gizlətmir;
- siqnal, proqnoz, qərar, mövqe və order yaratmır;
- müşahidəni səbəb-nəticə və ya gələcək gəlir vədi kimi təqdim etmir.

## Giriş müqaviləsi

Hər analiz işi ən azı bunları daşıyır:

| Sahə | Qayda |
| --- | --- |
| `analysis_id` | Dəyişməz unikal identifikator |
| `symbol` | Bir analiz üçün bir simvol |
| `start_at` | UTC ISO-8601, aralığa daxildir |
| `end_at` | UTC ISO-8601, aralığa daxil deyil |
| `dataset_fingerprint` | Replay snapshot-un dəyişməz izi |
| `replay_contract_version` | İstifadə olunan oxuma müqaviləsi |
| `quality_report_id` | Eyni snapshot üçün keyfiyyət hesabatı |
| `analysis_contract_version` | Statistik qaydalar versiyası |
| `window_spec` | Pəncərə ölçüləri və sərhəd qaydası |
| `calendar_version` | Sessiya təqvimi varsa onun versiyası |

Kanonik oxuma sırası `event_timestamp ASC, event_id ASC` olur. Aralıq
`[start_at, end_at)` formasındadır. Eyni giriş, versiya və snapshot eyni maşın-
oxunaqlı nəticəni verməlidir.

## Qiymət seriyası

Əsas qiymət yalnız `bid > 0`, `ask > 0` və `ask >= bid` olduqda hesablanan
mid-price-dır:

```text
mid = (bid + ask) / 2
```

- sıfır və ya natamam bid/ask cütü mid-price seriyasına salınmır;
- `last` avtomatik mid-price əvəzi deyil və ayrıca seriya kimi etiketlənir;
- forward-fill ilkin qayda deyil;
- pəncərədə etibarlı qiymət yoxdursa nəticə `insufficient_data` olur;
- qiymət vahidi və simvolun point/digit metadatası bilinmirsə nəticə yalnız xam
  qiymət və nisbi ölçü ilə verilir.

## Zaman pəncərəsi və resampling

İlkin dəstəklənən sabit UTC pəncərələri: `1s`, `10s`, `1m`, `5m`, `15m`, `1h`.
Hər pəncərə yarıaçıq `[window_start, window_end)` olur və UTC epoch sərhədinə
bağlanır.

Hər pəncərədə ən azı bunlar saxlanır:

- ilk və son kanonik event açarı;
- ümumi və etibarlı tick sayı;
- ilk/son mid-price və varsa `last`;
- minimum/maksimum mid-price;
- məlumat əhatəsi və quality statusu;
- boş pəncərə və qismən pəncərə işarəsi.

Boş pəncərə qiymətlə doldurulmur. Sessiya təqvimi olmadan onun bazar bağlanması və
ya məlumat boşluğu olduğu iddia edilmir.

## SA-001 — Gəlir seriyası

Ardıcıl müsbət mid-price-lar üçün log-return hesablanır:

```text
r_t = ln(mid_t / mid_(t-1))
```

Return heç vaxt gələcək tick-dən əvvəlki timestamp-a yazılmır. Pəncərə return-u
ilk və son etibarlı mid ilə hesablanır; bir qiymətli pəncərə return yaratmır.

Nəticə ən azı say, orta, median, standart sapma, minimum, maksimum, p05, p25, p75
və p95-i verir. Percentile üsulu müqavilə versiyasına bağlıdır.

## SA-002 — Volatilite

İlkin versiya aşağıdakı təsviri ölçüləri ayırır:

- tick-return standart sapması;
- pəncərə log-return-un mütləq dəyəri;
- pəncərə daxilində mid-price range-i və nisbi range;
- kifayət qədər nümunədə robust median absolute deviation.

Annualized volatility yalnız sessiya təqvimi və illikləşdirmə faktoru əvvəlcədən
verildikdə hesablanır. Kripto, FX və digər bazarlara eyni faktor səssiz tətbiq
olunmur.

## SA-003 — Spread davranışı

Yalnız etibarlı müsbət bid/ask cütləri üçün:

```text
spread_raw = ask - bid
spread_relative = spread_raw / mid
```

Hər pəncərə və ümumi aralıq üzrə say, minimum, orta, median, p05, p25, p75, p95,
p99 və maksimum verilir. Point ölçüsü təsdiqlənibsə `spread_points` ayrıca əlavə
olunur; yoxdursa uydurulmur.

Spread sıçrayışı sabit universal hədlə “pis” adlandırılmır. O, əvvəlcədən
versiyalanmış baseline-a nisbətən descriptive outlier kimi işarələnə bilər.

## SA-004 — Tick sürəti və interval

Hər pəncərə üçün:

- tick sayı və saniyə başına tick;
- ardıcıl event timestamp intervalının median, p95, p99 və maksimumu;
- eyni timestamp-li tick sayı;
- boş və qismən pəncərə sayı.

Tick sürəti likvidlik və ya real ticarət həcmi ilə eyniləşdirilmir.

## SA-005 — Tick volume və flags

Hazırkı `volume` sahəsi **MT5 tick-volume məlumatı** kimi etiketlənir. Müqavilə onu
real birja həcmi, order-book dərinliyi və ya icra edilə bilən likvidlik hesab etmir.

Hesabat:

- volume sıfır/müsbət sayını və paylanmasını;
- pəncərə üzrə cəm, median, p95 və maksimumu;
- `flags` dəyərlərinin sayını və məlum bit kombinasiyalarını;
- modul və event versiyası üzrə seqmentləri göstərir.

Flags semantikası ayrıca versiyalanmış MT5 mapping olmadan şərh edilmir.

## SA-006 — Sessiya müqayisəsi

Sessiya müqayisəsi yalnız versiyalanmış təqvim olduqda rəsmi nəticə yaradır. Təqvim:

- simvol/broker timezone-u və UTC çevrilməsini;
- yay/qış vaxtı qaydasını;
- həftəsonu, bayram və xüsusi bağlanmanı;
- üst-üstə düşən sessiyalar üçün prioriteti daşıyır.

Təqvim yoxdursa yalnız UTC saat dilimləri göstərilir və `calendar_unavailable`
məhdudiyyəti yazılır. UTC saat statistikası “London”, “New York” və ya başqa bazar
sessiyası adlandırılmır.

Sessiyalar eyni metric dəsti, nümunə sayı və confidence interval ilə müqayisə
olunur. Fərq avtomatik olaraq ticarət üstünlüyü sayılmır.

## SA-007 — Bazar rejimi namizədləri

Rejim aşkarlanması ilkin mərhələdə təsviri və müşahidə xarakterlidir. Feature-lar
yalnız keçmiş və cari pəncərələrdən yarana bilər:

- volatilite səviyyəsi;
- spread səviyyəsi;
- tick sürəti;
- return istiqaməti və range;
- data-quality statusu.

Hər rejim nəticəsi:

- model/qayda versiyası və parametrləri;
- feature schema və normalization versiyası;
- başlanğıc/son vaxt, müşahidə sayı və confidence;
- `unknown`/`insufficient_data` imkanı;
- əvvəlki versiya ilə mapping məhdudiyyətini saxlayır.

Rejim adı “trend”, “range” və ya “riskli” kimi iqtisadi məna daşımır, bu məna ayrıca
validasiya olunmayıbsa neytral `regime_1`, `regime_2` formasında verilir. Rejim
dəyişikliyi order siqnalı deyil.

## Keyfiyyət qapısı

Analiz eyni snapshot-un Phase 2 quality hesabatını tələb edir:

- `fail`: rəsmi statistik nəticə yayımlanmır, iş `blocked_by_data_quality` olur;
- `review`: nəticə məhdudiyyət və tapıntılarla birlikdə yayımlana bilər, SHADOW
  namizədliyi bloklanır;
- `pass`: statistik hesablama davam edir, lakin bu ticarət hazırlığı demək deyil.

Hər metric istifadə etdiyi və kənarlaşdırdığı müşahidə sayını ayrıca göstərir.

## Nümunə ölçüsü və uncertainty

Hər nəticə `n_total`, `n_valid`, `n_excluded` və exclusion səbəblərini daşıyır.
Konfiqurasiya olunan minimumdan az müşahidədə:

- statistic mümkün olsa belə `insufficient_data` işarəsi alır;
- confidence interval və müqayisə qərarı verilməyə bilər;
- boş nəticə sıfır effekt kimi göstərilmir.

Serial asılılıq nəzərə alınmadan tick-lər müstəqil müşahidə kimi təqdim edilmir.
Confidence interval üçün block bootstrap və ya time-series-ə uyğun üsul və onun
seed-i versiyalanır.

## Nəticə müqaviləsi

Konseptual maşın-oxunaqlı cavab:

```json
{
  "analysis_id": "opaque-id",
  "analysis_contract_version": "1.0",
  "generated_at": "2026-08-01T00:00:00.000Z",
  "dataset": {
    "symbol": "GOLD",
    "start_at": "2026-07-01T00:00:00.000Z",
    "end_at": "2026-08-01T00:00:00.000Z",
    "fingerprint": "sha256:...",
    "quality_report_id": "opaque-id",
    "quality_status": "pass"
  },
  "status": "completed",
  "limitations": [],
  "coverage": {},
  "price_returns": {},
  "volatility": {},
  "spread": {},
  "tick_rate": {},
  "tick_volume": {},
  "sessions": {},
  "regimes": {}
}
```

İcazəli yekun statuslar:

- `completed`;
- `completed_with_limitations`;
- `insufficient_data`;
- `blocked_by_data_quality`;
- `failed`.

Nəticə payload-u NaN və infinity daşımır; hesablanmayan dəyər `null` və səbəb kodu
ilə verilir. Rəqəmlərin saxlanma dəqiqliyi ilə frontend göstərmə yuvarlaqlaşdırması
ayrıdır.

## API və icra modeli

Analiz Phase 2 job/scheduler və `/api/v2` müqavilələri ilə asinxron iş kimi icra
olunur. Konseptual resurslar:

```text
POST /api/v2/statistical-analyses
GET  /api/v2/statistical-analyses/{analysis_id}
GET  /api/v2/statistical-analyses/{analysis_id}/results
```

Yaratma idempotency key tələb edir. Böyük pəncərə nəticələri imzalanmış snapshot
cursor-u ilə səhifələnir. Frontend SQLite-a qoşulmur və statistic hesablamır.

## Audit və dəyişməzlik

- giriş qeydiyyatı iş başlamazdan əvvəl append-only auditə yazılır;
- qayda, percentile, timezone və minimum nümunə həddi səssiz dəyişmir;
- köhnə nəticə yeni versiya ilə yenidən şərh edilmir;
- nəticə dataset fingerprint, Git commit, konfiqurasiya və asılılıq hash-i daşıyır;
- analizdən əvvəl və sonra xam tick sayı və checksum dəyişməməlidir;
- uğursuz və `insufficient_data` nəticələri silinmir.

## Frontend təqdimatı

Panel ən azı bunları aydın ayırır:

- “Təsviri statistika — ticarət siqnalı deyil” nişanı;
- simvol, UTC aralığı, snapshot və qayda versiyası;
- data-quality statusu və exclusion sayı;
- volatilite, spread, tick sürəti və tick-volume kartları;
- sessiya təqvimi yoxdursa açıq məhdudiyyət;
- uncertainty, nümunə sayı və `insufficient_data` vəziyyəti;
- rejim namizədlərinin neytral adı və confidence-i;
- tam audit/sübut paketinə qorunan keçid.

Rəng tək informasiya kanalı olmur və “al/sat”, gəlir və order dili istifadə edilmir.

## Qəbul sınaqları

1. Eyni snapshot və versiya iki icrada eyni nəticəni verir.
2. Pəncərə sərhədində tick itmir və iki dəfə sayılmır.
3. Sıfır/natamam qiymət mid və spread hesabına daxil edilmir.
4. Gələcək tick əvvəlki return və rejim feature-ına sızmır.
5. Boş pəncərə forward-fill olunmur və sıfır volatilite sayılmır.
6. Point metadata olmadan `spread_points` yaradılmır.
7. Tick volume real birja həcmi kimi etiketlənmir.
8. Təqvimsiz UTC saatı bazar sessiyası adı almır.
9. `fail` quality hesabatı rəsmi nəticəni bloklayır.
10. Az nümunə `insufficient_data` verir, saxta sıfır effekt yaratmır.
11. NaN/infinity API cavabına çıxmır.
12. Xam tick sətirləri və checksum analizdən sonra dəyişmir.
13. Frontend yalnız qorunan API nəticəsini göstərir.
14. Heç bir analiz siqnal, qərar və order yaratmır.

Bu müqavilə statistik müşahidənin formatıdır; strategiya, gəlir və ya real ticarət
icazəsi deyil.
