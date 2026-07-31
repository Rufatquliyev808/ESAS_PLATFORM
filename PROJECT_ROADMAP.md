# ESAS Platform — Project Roadmap

Son yenilənmə: 2026-07-31
Cari mərhələ: Phase 1  
Ümumi status: IN PROGRESS

## Missiya

ESAS Platform bazarı qərəzsiz müşahidə edən, xam məlumatı qoruyan, statistik qanunauyğunluqları araşdıran və yalnız sübut edilmiş nəticələr əsasında gələcəkdə qərar verən modul platformadır.

Platformanın əsas məqsədi əvvəlcədən hazırlanmış strategiyanı sübut etmək deyil. Məqsəd bazarın davranışını öyrənmək və strategiyaların məlumatdan yaranmasını təmin etməkdir.

## Ümumi inkişaf axını

```text
Market Data
→ Collection
→ Event Bus
→ Raw Storage
→ Monitoring
→ Replay
→ Statistical Analysis
→ Pattern Discovery
→ Knowledge Base
→ Decision
→ Risk Management
→ Execution
→ Feedback
→ Learning
```

# Phase 1 — Etibarlı məlumat toplama təməli

Status: IN PROGRESS

## Məqsəd

MT5-dən gələn tick məlumatını itkisiz, yoxlanıla bilən və monitorinq olunan şəkildə backend-ə çatdırmaq və xam formada saxlamaq.

## Tamamlanmış işlər

- [x] Platforma konstitusiyasının ilkin versiyası
- [x] Platforma arxitekturasının ilkin versiyası
- [x] Event müqaviləsi
- [x] Modul həyat dövrü qaydaları
- [x] Versiyalandırma qaydaları
- [x] MT5-dən canlı tick oxunması
- [x] `TICK_RECEIVED` event yaradılması
- [x] JSON serializasiyası
- [x] HTTP transportu
- [x] FastAPI event validation
- [x] SQLite saxlanması
- [x] Təkrar event qoruması
- [x] Tick statistikası endpoint-i
- [x] Operational status endpoint-i
- [x] `active` və `stale` vəziyyətlərinin real yoxlanması
- [x] İlkin FIFO yaddaş buferi
- [x] GitHub repozitoriyası
- [x] Layihənin davamlı yaddaş sənədləri

## Qalan işlər

- [x] Azərbaycan dilindəki sənədlərin UTF-8 kodlaşdırmasını düzəltmək
- [x] Phase 1 status sənədini düzəltmək
- [x] MT5 Bridge versiyalarını uyğunlaşdırmaq
- [x] README sənədini yeniləmək
- [x] Buferdəki event-lərin avtomatik retry göndərişi
- [x] Bufer dolması siyasəti
- [x] İtirilmiş event sayğacı
- [x] Disk əsaslı davamlı event növbəsi
- [x] Backend monitorinq göstəricilərini genişləndirmək
- [x] Test verilənlər bazasını əsas bazadan ayırmaq
- [x] Bufer və retry testləri
- [x] GitHub Actions test axını
- [x] Phase 1 frontend monitorinq paneli
- [x] 30 dəqiqəlik sabitlik sınağı
- [x] 1 saatlıq sabitlik testi
- [x] 8–12 saatlıq sabitlik testi
- [ ] 24 saatlıq sabitlik testi
- [x] Məlumat itkisi hesabatı
- [x] Phase 1 release qeydləri

## Phase 1 qəbul meyarları

- Gözlənilməz event itkisi olmamalıdır.
- Təkrar event bazaya ikinci dəfə yazılmamalıdır.
- Backend kəsildikdə event-lər qorunmalıdır.
- Backend bərpa olduqda növbə avtomatik göndərilməlidir.
- Operational status real vəziyyəti göstərməlidir.
- Frontend əsas monitorinq göstəricilərini göstərməlidir.
- Sistem 24 saatlıq sınaqda sabit işləməlidir.
- Bütün əsas testlər keçməlidir.
- Sənədlər cari vəziyyətlə uyğun olmalıdır.

# Phase 2 — Replay və məlumat keyfiyyəti

Status: PLANNED

- [ ] Tarixi tick məlumatının oxunması
- [ ] Müəyyən zaman aralığının replay edilməsi
- [ ] Məlumat boşluqlarının aşkarlanması
- [ ] Tick ardıcıllığının yoxlanması
- [ ] Spread və tick sürəti statistikası
- [ ] Simvollar üzrə məlumat keyfiyyəti hesabatı
- [ ] Replay nəticələrinin təkrar istehsal edilə bilməsi

# Phase 3 — Statistik analiz

Status: PLANNED

Tədqiqat qeydiyyatı, məlumat sızması, zaman bölgüsü, holdout, walk-forward,
multiple-testing, xərclər və qəbul qapıları:
`docs/architecture/PHASE_3_RESEARCH_VALIDATION_CONTRACT.md`

Volatilite, spread, tick sürəti, sessiya və bazar rejimi nəticə müqaviləsi:
`docs/architecture/PHASE_3_STATISTICAL_ANALYSIS_CONTRACT.md`

- [ ] Volatilite analizi
- [ ] Spread davranışı
- [ ] Həcm analizi
- [ ] Sessiya müqayisələri
- [ ] Bazar rejimlərinin aşkarlanması
- [ ] Statistik hipotezlərin yoxlanması
- [ ] Nəticələrin etibarlılıq göstəriciləri

# Phase 4 — Pattern və texniki analiz

Status: PLANNED

Deterministik bar, causal indikator, pattern namizədi, realist backtest və SHADOW
hazırlığı müqaviləsi:
`docs/architecture/PHASE_4_PATTERN_TECHNICAL_ANALYSIS_CONTRACT.md`

- [ ] Pattern namizədlərinin yaradılması
- [ ] Texniki analiz modulları
- [ ] Backtesting
- [ ] Nəticələrin statistik müqayisəsi
- [ ] Uğursuz eksperimentlərin arxivləşdirilməsi
- [ ] SHADOW mərhələsi üçün hazırlıq

# Phase 5 — Visual AI

Status: PLANNED

Deterministik qrafik renderi, visual dataset lineage-i, leakage qoruması, zaman əsaslı
bölgü, model audit və statistik baseline müqayisəsi müqaviləsi:
`docs/architecture/PHASE_5_VISUAL_AI_CONTRACT.md`

- [ ] Qrafik görüntülərinin standartlaşdırılması
- [ ] Visual pattern məlumat dəsti
- [ ] Visual AI eksperimentləri
- [ ] Statistik analizlə müqayisə
- [ ] SHADOW rejimində yoxlama

# Phase 6 — Xəbər və fundamental analiz

Status: PLANNED

Mənbə və lisenziya reyestri, point-in-time xəbər/revision, iqtisadi buraxılış,
fundamental vintage, entity mapping və causal təsir ölçümü müqaviləsi:
`docs/architecture/PHASE_6_NEWS_FUNDAMENTAL_ANALYSIS_CONTRACT.md`

- [ ] Xəbər məlumatlarının toplanması
- [ ] Hadisələrin zaman uyğunlaşdırılması
- [ ] Xəbər təsirinin ölçülməsi
- [ ] Fundamental göstəricilərin saxlanması
- [ ] Digər analiz modulları ilə standart event əlaqəsi

# Phase 7 — Knowledge Base

Status: PLANNED

Versiyalanmış bilik claim-i, sübut qrafı, scope və rejim uyğunluğu, etibarlılıq
müddəti, conflict, REVIEW və təhlükəsiz retrieval müqaviləsi:
`docs/architecture/PHASE_7_KNOWLEDGE_BASE_CONTRACT.md`

- [ ] Sübut edilmiş nəticələrin saxlanması
- [ ] Model və pattern versiyalandırması
- [ ] Etibarlılıq və istifadə müddəti göstəriciləri
- [ ] Bazar rejiminə görə bilik seçimi
- [ ] Köhnəlmiş biliklərin REVIEW mərhələsi

# Phase 8 — Decision və Risk Layer

Status: PLANNED

Deterministik analiz birləşdirməsi, izahlı proposal, abstain, müstəqil risk qapısı,
nəzəri mövqe ölçüsü, limit/halt və SHADOW eligibility müqaviləsi:
`docs/architecture/PHASE_8_DECISION_RISK_CONTRACT.md`

- [ ] Analiz nəticələrinin birləşdirilməsi
- [ ] Qərarın izah edilə bilməsi
- [ ] Risk limitləri
- [ ] Mövqe ölçüsünün hesablanması
- [ ] Əməliyyat icazəsi və bloklama qaydaları
- [ ] Bütün qərarların audit tarixçəsi

# Phase 9 — SHADOW rejimi

Status: PLANNED

Real bazar axınında order-siz qərar izlənməsi, səbəbiyyətə uyğun nəzəri fill,
champion/challenger müqayisəsi, restart təhlükəsizliyi, statistik qəbul qapısı və
məhdud icra baxışına keçid müqaviləsi:
`docs/architecture/PHASE_9_SHADOW_VALIDATION_CONTRACT.md`

- [ ] Real bazarda qərarların hesablanması
- [ ] Real əməliyyat açmadan nəticələrin saxlanması
- [ ] Alternativ modulların müqayisəsi
- [ ] Statistik qəbul meyarları
- [ ] ACTIVE mərhələsinə keçid qərarı

# Phase 10 — Məhdud icra

Status: PLANNED

- [ ] MT5 order interfeysi
- [ ] Məhdud risklə ilkin əməliyyatlar
- [ ] Fövqəladə dayandırma mexanizmi
- [ ] Order və broker cavablarının event-ləşdirilməsi
- [ ] İcra nəticələrinin monitorinqi
- [ ] Manual təsdiq və nəzarət imkanları

# Phase 11 — Feedback və davamlı öyrənmə

Status: PLANNED

- [ ] Əməliyyat nəticələrinin analizə qaytarılması
- [ ] Model performansının davamlı ölçülməsi
- [ ] Performansı zəifləyən modulların REVIEW statusuna keçirilməsi
- [ ] Yeni və köhnə modellərin SHADOW müqayisəsi
- [ ] Knowledge Base yenilənməsi
- [ ] Davamlı öyrənmə dövrəsi

## Cari növbəti tapşırıq

Bazar açıldıqda 24 saatlıq fasiləsiz canlı sabitlik sınağını yenidən başlatmaq.

Ətraflı tapşırıq:

`docs/status/NEXT_TASK.md`
