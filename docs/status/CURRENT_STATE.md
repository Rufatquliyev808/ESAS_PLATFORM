# ESAS Platform — Cari Vəziyyət

## 2026-08-05 — Phase 2 worker/scheduler müqaviləsi hərfi tətbiq edildi (`pattern_candidate_backtest`)

- İstifadəçinin iki dəfə açıq təsdiqi ilə (`Tam həcmdə tiklə` → `Tam
  müqaviləni hərfi tiklə`) `PHASE_2_WORKER_SCHEDULER_CONTRACT.md`-dəki tam
  claim/lease/fencing/retry/audit/state-machine/observability modeli
  tətbiq edildi — yalnız `pattern_candidate_backtest` iş növü üçün (müqavilədə
  adı çəkilən 5 iş növünə bu, 6-cı olaraq əlavə edildi; digər 5-i hələ
  yoxdur, real ehtiyac yalnız backtest üçündür).
- Ayrıca worker prosesi qurulmadı — icra sürücüsü FastAPI `BackgroundTasks`-dır;
  claim/lease/fencing DB məntiqi isə düzgün və gələcək real worker tərəfindən
  təkrar istifadə edilə bilər şəkildə yazılıb.
- `0007_analysis_jobs.sql`: `analysis_jobs` (tam vəziyyət maşını —
  `queued/claimed/running/pausing/paused/retry_wait/completed/cancelled/
  interrupted/failed`, monoton `fencing_token`, lease, `state_version`
  optimistic lock, idempotency) + append-only `analysis_job_audit`.
- `backend/app/database/analysis_job_repository.py`: `enqueue_job`
  (idempotent, istifadəçi başına maksimum `3` aktiv iş), `claim_next_job`
  (prioritet+yaranma vaxtı üzrə, vaxtı keçmiş lease-ləri əvvəlcə `interrupted`
  kimi bərpa edir və fencing token-i artırır), `send_heartbeat`,
  `complete_job` (işləyərkən `cancel_requested` görsə `cancelled`-ə keçir,
  nəticəni saxlamır), `fail_job` (yalnız `retryable=True` olanlar exponential
  backoff+jitter ilə `max_attempts`-a qədər təkrarlanır), `request_cancel`
  (queued/retry_wait dərhal, running yalnız kooperativ — tək batch sərhədində
  `complete_job` tərəfindən icra olunur), `queue_metrics`.
- **Real bug tapıldı və düzəldildi:** `enqueue_job`-da idempotency key hash-i
  `created_by` ilə birlikdə hesablanırdı, ona görə fərqli istifadəçilər eyni
  key ilə heç vaxt DB sətrində toqquşmurdu — nəzəri `AnalysisJobOwnershipError`
  qoruması faktiki heç vaxt işə düşə bilməzdi (dead code). Düzəliş: hash indi
  yalnız `job_type:key` üzrədir, ownership yoxlanışı tapılan sətirdə real
  aparılır. Reqressiya testi: `test_enqueue_rejects_key_reused_by_another_user`.
- `backend/app/workers/analysis_job_worker.py`: `run_worker_once` (bir işi
  claim edib tam icra edir — uğur/retry/fail bütün yolları), `drain_queue`
  (bir çağırışda ən çox `max_jobs` iş, sonsuz dövr riski yoxdur). Xəta
  təsnifatı: bilinən domain xətaları (`PatternCandidateNotFoundError` və s.)
  → `retryable=False`; `sqlite3.OperationalError` → `retryable=True`; digər
  gözlənilməz xətalar → `retryable=False` (worker sərhədində şüurlu geniş
  `except`, iş növbəsini bir pis işin çökdürməməsi üçün).
- Yeni API-lər: `POST .../pattern-candidates/{id}/backtest-jobs` (202,
  enqueue + arxa planda dərhal icra), `GET .../backtest-jobs/{job_id}`,
  `POST .../backtest-jobs/{job_id}/cancel`, `GET
  /api/v2/analysis-jobs/metrics`. Mövcud sinxron `POST .../backtest`
  endpoint-i dəyişməz saxlanıldı — job-əsaslı yol əlavədir, əvəzləmə deyil.
- **Frontend hələ toxunulmayıb** — yeni async job endpoint-ləri üçün UI
  yoxdur, mövcud "Backtest et" düyməsi sinxron endpoint-dən istifadə etməyə
  davam edir. Bu, istifadəçi ilə ayrıca müzakirə tələb edən açıq qərardır.
- Yoxlama: yeni `test_analysis_job_repository.py` (`17` test),
  `test_analysis_job_worker.py` (`4` test, real replay session + tick
  data ilə tam uğurlu backtest icrası daxil), `test_analysis_jobs_api.py`
  (`7` test). `test_migration_runner.py` sayğacları `0007`-ə uyğunlaşdırıldı.
  Tam backend regressiyası: `321 passed`. Frontend toxunulmadığı üçün
  ayrıca frontend sınağı aparılmadı.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; iş növbəsi yalnız
  mövcud sinxron backtest hesablamasını asinxron şəkildə işə salır.

## 2026-08-05 — Pattern namizədi UI-si canlı brauzerdə vizual təsdiqləndi

- Real `database/ESAS_PLATFORM.sqlite`-a **toxunulmadı**. Ayrıca, birdəfəlik
  test bazası (`.venv` ilə yeni SQLite fayl, `0001-0006` migrasiyaları
  tətbiq edilmiş) yaradıldı, sintetik GOLD tick zigzag-ı (67 tick) əlavə
  edildi və tam bir replay sessiyası (`max_speed`, `completed`) quruldu.
- Backend `127.0.0.1:8001`-də, frontend `127.0.0.1:5173`-də (hər ikisi
  müvəqqəti, yalnız bu yoxlama üçün) işə salındı; CORS artıq `5173`-ə
  icazə verdiyi üçün əlavə konfiqurasiya lazım olmadı.
- Brauzerdə tam giriş edildi və **Pattern namizədləri** bölməsinin bütün
  dövrü uğurla yoxlanıldı: draft hesablama (M1 vaxt çərçivəsində
  `market_structure_short` real olaraq `candidate_confirmed` göstərdi,
  Python-da əvvəlcədən yoxlanmış nəticə ilə tam üst-üstə düşdü) → "Draft
  kimi qeydə al" → "Backtest et" (n=1, 3 ssenari, "Sübut yetərli deyil") →
  "Nəticələndir" (→ `insufficient_evidence`) → "Arxivləşdir" (→
  `Arxivləşdirilib`). Bütün addımlarda UI mətnləri gözlənilən nəticələri
  göstərdi, brauzer konsolunda **heç bir xəta olmadı**.
- "Bazar strukturu" bölməsi də ayrıca yoxlanıldı — düzgün render olundu.
- Yoxlamadan sonra bütün müvəqqəti proseslər dayandırıldı, `frontend/.env.local`
  silindi, test bazası scratchpad-də qaldı (layihəyə heç nə commit edilmədi).
- Bu, sessiya boyu qeyd edilən "canlı brauzerdə yoxlanmayıb" qeydini
  bağlayır.

## 2026-08-05 — Backtest verdiktindən avtomatik nəticələndirmə (Phase 4)

- Vəziyyət maşınının növbəti addımı: `evaluated → accepted_for_shadow |
  rejected | insufficient_evidence` keçidi əlavə edildi
  (`classify_backtest_verdict`, `POST /api/v2/pattern-candidates/{id}/classify`).
- Verdikt yalnız son backtest-in **"normal" xərc ssenarisindən** deterministik
  hesablanır, yeni statistika yoxdur:
  - `supportive_evidence` → `accepted_for_shadow` (Phase 9 SHADOW hələ
    yoxdur — bu, real ticarət icazəsi vermir, yalnız tarixi sübutun
    əvvəlcədən müəyyən edilmiş həddi keçdiyini qeyd edir);
  - `insufficient_evidence` + səbəb `effective_sample_below_30` →
    `insufficient_evidence` (bəlkə də sadəcə daha çox məlumat lazımdır);
  - `insufficient_evidence` + digər səbəb (kifayət qədər nümunə var, amma
    etibar intervalı sıfırı keçir) → `rejected` (bu, əskik məlumat deyil,
    əksinə sübut).
- `archive_pattern_candidate` genişləndirildi: əvvəllər yalnız `registered`
  vəziyyətindən arxivləşdirmək mümkün idi, indi `evaluated`,
  `accepted_for_shadow`, `rejected`, `insufficient_evidence`-dən də mümkündür.
- Frontend: "Nəticələndir" düyməsi və LIFECYCLE_LABELS ilə aydın vəziyyət
  mətnləri, "real ticarət icazəsi deyil" xəbərdarlığı.
- Yoxlama: backend `293 passed`; frontend production build və `10/10`
  test, lint təmiz.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; `accepted_for_shadow`
  real ticarət icazəsi deyil.

## 2026-08-05 — Backtest v1 bütün 6 hipotezi əhatə edir (Phase 4)

- `market_structure.py`-a tarixi `observations` sahəsi əlavə edildi.
  Dizayn qərarı: hər istiqamət üçün yalnız **rejimin təsdiqlənməyə
  keçdiyi an** (transition into `confirmed_structure`) bir hadisə kimi
  qeyd olunur — davam edən eyni rejimin sonrakı hər pivotu YENİDƏN hadisə
  yaratmır. Səbəb: əks halda uzun bir trend onlarla üst-üstə düşən,
  yüksək korrelyasiyalı "nümunə" yaradardı və effektiv nümunə sayını
  süni artırardı (purged-validation prinsipinə zidd).
- Backtest v1 indi `market_structure_long/short`-u da dəstəkləyir —
  bütün 6 hipotez əhatə olunub.
- Yoxlama: backend `286 passed` (yeni market_structure tarixi hadisə
  testləri, backtest-ə market_structure inteqrasiya testləri); frontend
  production build və `10/10` test, lint təmiz.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır.

## 2026-08-05 — Backtest v1 genişləndirilməsi və istiqamət bug-ı düzəldildi (Phase 4)

- **Vacib düzəliş:** `run_pattern_candidate_backtest` səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, amma real qeydə alınmış
  namizədin `direction` sahəsi hipotez reyestrindən `"long"/"short"` gəlir.
  Bu, real axında backtest-i həmişə `ValueError` ilə uğursuz edərdi (əvvəlki
  testlərdə fixture-larda əl ilə "bullish" yazıldığı üçün gizlənmişdi).
  Düzəliş: funksiya artıq `direction` parametrini qəbul etmir, istiqaməti
  yalnız `hypothesis_id`-dən (`HYPOTHESIS_EVENT_DIRECTION` xəritəsi) təyin
  edir.
- `liquidity_sweep.py`-a `observations: tuple[...]` sahəsi əlavə edildi —
  əvvəllər yalnız son süpürmə saxlanılırdı, indi hər hovuzun tarixi
  süpürmə hadisəsi (varsa) qorunur. Geriyə uyğun, əlavəedici dəyişiklik.
- Backtest v1 indi `liquidity_sweep_reclaim_long/short`-u da dəstəkləyir
  (əvvəllər yalnız `structure_break_long/short`). `market_structure`
  hələ kənarda qalır — o, davamlı rejim konsepsiyasıdır (diskret hadisə
  deyil), tarixi hadisə semantikası üçün ayrıca dizayn qərarı tələb edir.
- Yoxlama: backend `281 passed` (yeni liquidity_sweep tarixi hadisə testi,
  yenilənmiş backtest testləri — istiqamət bug-ının reqressiya testi
  daxil); frontend production build və `10/10` test, lint təmiz.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır.

## 2026-08-05 — Pattern namizədi backtest v1 (Phase 4)

- Backtest v1 **yalnız** `structure_break_long`/`structure_break_short`
  hipotezlərini dəstəkləyir — səbəb: yalnız bu ikisinin arxasındakı
  detektorlar (`bos_choch.observations`, `retest.observations`) **bütün
  tarixi təkrarları** saxlayır. `market_structure` və `liquidity_sweep`
  hazırda yalnız son müşahidəni saxlayır; onları backtest etmək statistik
  cəhətdən mənasız (1 nümunə) olardı, ona görə v1-ə şüurlu şəkildə
  daxil edilmədi.
- `run_pattern_candidate_backtest` (`pattern_candidate_backtest.py`):
  hipotezin bütün tarixi `confirmed_retest` hadisələrini tapır, hər biri
  üçün giriş = təsdiq barının öz bağlanışı (mövcud `forward_closed_bar_outcome`
  konvensiyası ilə eyni), çıxış = horizon bar sonrakı bağlanış. Normal/pis/stress
  xərc ssenariləri, effektiv nümunə sayı, hit rate, 95% etibar intervalı
  (`statistical_reliability.py` ilə eyni düstur və `n≥30` həddi) hesablanır.
- `0006_pattern_candidate_backtests.sql`: append-only backtest nəticələri
  cədvəli. `0005` migrasiyası (bu sessiyada yaradılıb, heç bir real bazaya
  tətbiq edilməyib) `lifecycle_state` CHECK-i müqavilədəki tam vəziyyət
  lüğəti ilə (`evaluated` daxil) əvvəlcədən genişləndirilərək düzəldildi —
  DROP-based rebuild lazım olmasın deyə.
- Yeni endpoint-lər: `POST/GET /api/v2/pattern-candidates/{id}/backtest`.
  İlk uğurlu backtest namizədi `registered → evaluated`-ə keçirir; təkrar
  işlətmə `evaluated`-də qalır, amma yeni backtest sətri və audit qeydi
  əlavə edir (heç bir əvvəlki nəticə silinmir/üzərinə yazılmır).
- Frontend: qeydə alınmış namizədlər cədvəlində "Backtest et" düyməsi və
  ssenari nəticələri (n, net %, sübut statusu).
- Yoxlama: backend `277 passed` (yeni backtest pure `7` + repository `5` +
  API `3` test); frontend production build və `10/10` test, lint təmiz.
- Bu qat strategiya, giriş, risk ölçüsü və order yaratmır; "evaluated" real
  ticarət icazəsi deyil, yalnız tarixi simulyasiyadır.

## 2026-08-05 — Pattern namizədi persistence/`registered` qatı (Phase 4)

- `0005_pattern_candidates.sql` migrasiyası: `pattern_candidates` (dəyişməz
  qeydiyyat, `lifecycle_state IN ('registered','archived')`, optimistic
  `state_version` lock) və append-only `pattern_candidate_audit` cədvəlləri
  əlavə edildi.
- `backend/app/database/pattern_candidate_repository.py`: `register_pattern_candidate`
  (yalnız `candidate_confirmed` slotlar, `candidate_id`-ə görə idempotent),
  `get_pattern_candidate`, `list_pattern_candidates` (owner-scoped keyset
  pagination), `archive_pattern_candidate` (ownership + optimistic lock).
- `replay_pattern_candidates.py`-a `register_replay_pattern_candidate`
  əlavə edildi: server HƏMİŞƏ sessiyanı yenidən hesablayır, klient heç vaxt
  evidence/condition_state göndərmir — yalnız real, hazırkı causal nəticə
  qeydə alına bilir.
- Yeni qorunan API-lər (müqavilədə göstərilən adlarla): `POST
  /api/v2/pattern-candidates`, `GET /api/v2/pattern-candidates`, `GET
  /api/v2/pattern-candidates/{id}`, `POST /api/v2/pattern-candidates/{id}/archive`.
  `features`/`backtest` alt-resursları hələ tətbiq edilməyib (backtest
  infrastrukturu yoxdur).
- Frontend: hər `candidate_confirmed` kartında "Draft kimi qeydə al" düyməsi,
  ayrıca "Qeydə alınmış namizədlər" cədvəli (bütün sessiyalar, owner-scoped)
  və "Arxivləşdir" əməliyyatı əlavə edildi.
- Şüurlu şəkildə kənarda: `running`, `evaluated`, `accepted_for_shadow`,
  `rejected` və digər backtest-asılı vəziyyətlər tətbiq edilməyib — bunlar
  backtest mühərriki olmadan mənasız/saxta olardı.
- Yoxlama: backend `262 passed` (yeni `test_pattern_candidate_repository.py`
  `7` test + `test_pattern_candidates_persistence_api.py` `4` test; mövcud
  `test_migration_runner.py` sayğacları `0005`-ə uyğunlaşdırıldı); frontend
  production build və `10/10` test, lint təmiz.
- Bu qat strategiya, siqnal, giriş, risk ölçüsü və order yaratmır; "registered"
  vəziyyəti real ticarət icazəsi deyil.

## 2026-08-05 — Phase 2 rəsmi bağlanışı (STABLE)

Phase 2 (Replay və məlumat keyfiyyəti) rəsmi olaraq bağlanıb. Qərar və rəsmi
qəbul sübutu: `docs/releases/PHASE_2_STABLE.md`.

- Bütün Phase 2 roadmap bəndləri (`PROJECT_ROADMAP.md`) tamamlanmış idi;
  bu addım yalnız Phase 1-dəki kimi rəsmi qəbul sənədini yazdı — yeni kod
  dəyişikliyi yoxdur.
- Əsas sübut mənbəyi: 2026-08-04 tarixli real `GOLD` intervalı üzərində
  aparılmış `step`/`max_speed` cross-mode qəbul sınağı
  (`.runtime/phase2-acceptance/phase2-replay-latest.json`), nəticə `PASSED`,
  kritik tapıntı `0`, xam tick sayı dəyişməz (`1,258,269`).
- Tarixi `DQ-009` (`542` warning, `received_at` < `event_timestamp`) qalıq
  keyfiyyət qeydi kimi sənədləşdirilib; kök səbəb MT5 Bridge `1.6.1`-də
  düzəldilib, canlı axına aid deyil, Phase 2 xam məlumatı dəyişdirmədiyi üçün
  tarixi tick-lər geriyə düzəldilməyib.
- `PROJECT_ROADMAP.md`-də Phase 2 statusu `IN PROGRESS`-dən
  `COMPLETED — STABLE`-ə, cari mərhələ `Phase 4`-ə yeniləndi.
- Kod, test və CI dəyişmədi — bu, sənədləşdirmə/qərar addımıdır.

## 2026-08-05 — Draft pattern namizədi generatoru (Phase 4)

- `pattern_candidate 1.0.0` əlavə edildi (`backend/app/strategies/pattern_candidate.py`):
  mövcud causal detektorların (bazar strukturu, likvidlik süpürməsi, BOS/CHoCH+retest)
  nəticələrini `pattern_hypothesis_registry`-dəki 6 hipotezə (market_structure_long/short,
  liquidity_sweep_reclaim_long/short, structure_break_long/short) birləşdirir.
- Hər namizəd yalnız `draft` lifecycle vəziyyətindədir; `candidate_confirmed`,
  `no_candidate` və `insufficient_data` şərt statusları açıq ayrılır. Backtest,
  label/horizon ölçümü, persistence/state machine və qəbul/rədd qərarı bu artıma
  daxil deyil — `PHASE_4_PATTERN_TECHNICAL_ANALYSIS_CONTRACT.md`-də ayrıca sonrakı
  addımlar kimi qeyd olunub.
- Yeni qorunan, yalnız-oxuma `GET /api/v2/replay-sessions/{session_id}/pattern-candidates`
  endpoint-i əlavə edildi (`replay_pattern_candidates.py`); ownership, completed-state
  və dataset-drift qoruması digər analiz endpoint-ləri ilə eynidir.
- `ReplayAnalysisContext` mövcud `market_structure`/`liquidity_sweep`/`bos_choch`/
  `retest` nəticələrini artıq dataclass kimi də daşıyır (əvvəllər yalnız dict idi);
  bu, `replay_strategy.py` kimi mövcud çağırış yerlərini pozmayıb.
- Frontend-də "Pattern namizədləri" bölməsi əlavə edildi
  (`pattern-candidates-panel.tsx`): 6 slotu ayrı kartlarda, `draft` etiketi və
  "backtest/label/qəbul qərarı yoxdur" xəbərdarlığı ilə göstərir.
- Yoxlama: backend `251 passed` (yeni `test_pattern_candidate.py` — `6` test,
  `test_replay_technical_analysis_api.py`-a `2` yeni API testi); frontend
  production build və `10/10` test keçdi, lint təmizdir.
- Bu qat strategiya, siqnal, giriş, risk ölçüsü və order yaratmır; "draft" statusu
  real ticarət icazəsi deyil.
- Canlı brauzerdə vizual yoxlama edilməyib (əvvəlki sessiyalardakı eyni xarici
  mühit məhdudiyyətinə görə); yalnız avtomatlaşdırılmış test/build sübutu var.

## 2026-08-05 — Causal Fair Value Gap 1.0.0 tamamlandı

- `fair_value_gap 1.0.0` üç ardıcıl bağlanmış bar arasında yaranan bullish/bearish
  qiymət boşluğunu yalnız bağlanmış barlarla izləyir; boşluq yalnız yaranandan
  sonrakı barlarla `open`, `partially_filled`, `filled` və ya `invalidated`
  vəziyyətinə keçir, gələcək bar boşluğun yaranmasına təsir etmir.
- Minimum boşluq (bps) konfiqurasiya olunur; `insufficient_data` və `no_gap`
  halları açıq göstərilir. Nəticə bar fingerprint-inə bağlı deterministik
  SHA-256 izi daşıyır və `replay_analysis` cavabına (`ANALYSIS_API_VERSION 1.5.0`)
  əlavə edilib.
- Frontend-də ayrıca "Fair Value Gap" menyusu və tədqiqat kartı əlavə edildi;
  köhnə backend cavabı üçün uyğunluq xəbərdarlığı qorunur.
- Tam yoxlama: backend `243 passed` (yeni `fair_value_gap` modul testləri daxil);
  frontend production build və `9/9` test keçdi.
- Bu qat strategiya, siqnal, giriş, risk ölçüsü və order yaratmır.
- Commit `1aa85c8` ilə edildi və istifadəçi təsdiqi ilə `origin/main`-ə push edildi.

## 2026-08-05 — Sidebar lint düzəlişi və CI yaşıl

- `dashboard-navigation.tsx`-də `eslint-plugin-react-hooks 7.x`-in
  `react-hooks/immutability` qaydasını pozan render-zamanı `previousGroup`
  mutasiyası aradan qaldırıldı; menyu qrup başlığı indi render-dən əvvəl
  modul səviyyəsində hesablanan sabit massivdən (`MENU_ENTRIES`) götürülür.
- Bu düzəliş FVG detektorundan asılı deyildi, əvvəldən mövcud koddan qaynaqlanırdı.
- Lokal `npm run lint`, `npm run test` (build + `9/9` test) təmiz keçdi.
- Commit `7d49f97` ilə `origin/main`-ə push edildi.
- GitHub Actions "Tests" iş axını (run `31011108501`) Backend və Frontend
  (lint daxil) job-larının hər ikisində **uğurlu** nəticə verdi; `main` budağı
  indi CI-də yaşıldır.

## 2026-08-05 — Causal retest 1.0.0 tamamlandı

- No-lookahead retest müşahidəsi backend və frontend-ə əlavə edildi.
- Tam backend regressiyası: `239 passed`; frontend hədəf testi və lint keçdi.
- Növbəti müstəqil mərhələ causal FVG detektorudur və ayrıca təsdiq tələb edir.

## Phase 4 causal BOS/CHoCH detektoru

2026-08-05 tarixində `bos_choch 1.0.0` tamamlandı. Təsdiqlənmiş causal bazar strukturu
pivotları yalnız təsdiq barından sonra gələn bağlanmış barların close qiyməti ilə yoxlanır.
Mövcud struktur rejimi ilə eyni istiqamətli qırılma BOS, əks istiqamətli qırılma CHoCH kimi
müşahidə olunur; rejim məlum deyilsə nəticə ayrıca `unclassified_break` qalır. Bullish və bearish
nəticələr, yetərsiz, qırılma olmayan və eyni barda iki istiqamətin qırıldığı ziddiyyətli hallar
ayrıdır. Parametrlər, upstream izlər və nəticə deterministik fingerprint ilə saxlanır. Frontend
nəticələri sadə Azərbaycan dilində ayrı kartlarda göstərir. Bu qat yalnız tarixi tədqiqatdır;
siqnal, giriş, risk ölçüsü və order yaratmır. Tam yoxlama: backend `236 passed`; frontend `4`
test, lint və production build keçdi.

## Phase 4 causal likvidlik süpürməsi detektoru

2026-08-05 tarixində `liquidity_sweep 1.0.0` tamamlandı. Təsdiqlənmiş causal pivotlardan
equal-high/equal-low hovuzları mərhələli snapshot kimi yaradılır; sonradan gələn pivot əvvəlki
hovuzun tarixini dəyişmir. Sweep yalnız hovuz məlum olduqdan sonra bağlanmış barın wick məsafəsi
və səviyyəyə geri bağlanması ilə təsdiqlənir. Bullish, bearish, yetərsiz, sweep olmayan və eyni
barda iki tərəfin süpürüldüyü ziddiyyətli hallar ayrıdır. Konfiqurasiya və upstream izlər
deterministik fingerprint-də saxlanır. Frontend nəticələri ayrı tədqiqat kartlarında göstərir.
Qat siqnal, giriş, risk ölçüsü və order yaratmır.
Tam yoxlama: backend `232 passed`; frontend `4` test, lint və production build keçdi.

## Phase 4 causal bazar strukturu detektoru

2026-08-05 tarixində `market_structure 1.0.0` tamamlandı. Yalnız bağlanmış barlardan
istifadə edən pivot qaydası sağ tərəfdəki barlar bağlandıqdan sonra təsdiq verir; buna görə
gələcək məlumat əvvəlki HH/HL və LH/LL nəticəsinə sızmır. Yüksəliş və eniş müşahidələri,
yetərsiz və ziddiyyətli hallar, pivotun bar vaxtı ilə təsdiq vaxtı və deterministik fingerprint
ayrıca saxlanılır. Frontend nəticəni iki müstəqil araşdırma kartında göstərir. Tam backend
`227 passed`; frontend `4` test, lint və production build keçdi. Qat ticarət siqnalı,
mövqe ölçüsü və order yaratmır.

## Phase 4 xronoloji walk-forward müqayisə təməli

2026-08-04 tarixində `chronological_holdout_comparison 1.0.0` əlavə edildi. EMA və
RSI nəticələri təsadüfi qarışdırılmadan xronoloji inkişaf və toxunulmamış yoxlama
intervallarına ayrılır. İnkişaf sərhədindən sonrakı qiymətə ehtiyac duyan nəticələr
inkişaf hesabından ayrıca çıxarılır; yoxlama qiymətlərinin dəyişməsi inkişaf yekununu
dəyişmir. Manifest strategiya parametrlərini, bölgünü, nəticə üfüqünü və bütün upstream
fingerprint-ləri saxlayır. Frontend 60/40, 70/30 və 80/20 bölgülərini, hər intervalın
əhatəsini, istiqamətini, orta xərcsiz dəyişməsini və sərhəddən çıxarılan nümunələri
Azərbaycan dilində ayrı göstərir. Qat yalnız tarixi tədqiqatdır, canlı siqnal və order
yaratmır. Tam backend `189 passed`, frontend lint/build və `3` test keçdi.

## Phase 4 tarixi nəticə ölçmə infrastrukturu

2026-08-04 tarixində `forward_closed_bar_outcome 1.0.0` əlavə edildi. EMA və RSI
müşahidələri seçilən üfüqdən sonrakı qapalı barın qiymət dəyişikliyi ilə ölçülür. Hazır,
yetkinləşməmiş və warm-up nəticələri ayrıdır; yuxarı/aşağı/dəyişməz istiqamət və rejim üzrə
orta dəyişiklik göstərilir. Gələcək bar yalnız nəticəni etiketləyir, ilkin müşahidəni və
əvvəlki hesablamaları dəyişmir. Hər nəticə dataset, bar və strategiya fingerprint-inə
bağlanır. Frontend-də hər strategiyanın öz tarixi nəticə bölməsi və üfüq seçimi var.
Bu qat uğur və ya al/sat siqnalı deyil, order yaratmır. Tam backend `181 passed`, frontend
lint/build və `3` test nəticəsi uğurludur.

## Phase 4 ikinci strategiya müşahidə modulu

2026-08-04 tarixində `rsi_regime_observation 1.0.0` əlavə edildi. Causal RSI yalnız
bağlanmış barlarda aşağı, neytral və yüksək rejimlərə ayrılır; hədlər konfiqurasiya olunur.
Warm-up, inclusive sərhədlər, determinizm və no-lookahead sınaqları keçir. EMA və RSI
frontend laboratoriyasında ayrı kartlardır və hər biri öz versiya/fingerprint izini göstərir.
Qat yalnız tədqiqat üçündür, siqnal və order yaratmır. Tam backend `173 passed`, frontend
lint/build və `3` test nəticəsi uğurludur.

## Phase 2 real replay qəbul sübutu

2026-08-04 tarixində production bazası yoxlanmış SQLite backup-dan sonra Phase 2
sxeminə keçirildi və real `GOLD` intervalı ilə qəbul sınağı tamamlandı.

- Eyni 60 saniyəlik, `542` tick-lik dataset iki `step` və iki `max_speed`
  sessiyasında müstəqil icra edildi.
- Dörd sessiyanın dataset və nəticə fingerprint-ləri eyni oldu; cross-mode
  müqayisəsi keçdi.
- Xam tick sayı sınaqdan əvvəl və sonra `1,258,269` qaldı.
- Qəbul nəticəsi `PASSED`, kritik keyfiyyət tapıntısı `0` oldu.
- `DQ-009` bütün `542` tarixi tick üçün `received_at` vaxtının `event_timestamp`-dan
  əvvəl görünməsini xəbərdarlıq kimi qeyd etdi. Kök səbəb broker server vaxtının UTC
  işarəsi ilə göndərilməsi idi.
- MT5 Bridge `1.6.1` yeni event-lərdə broker server vaxtını UTC-yə normallaşdırır;
  mövcud xam tick-lər dəyişdirilmədi. Canlı qəbulda yeni tick-lərin gecikməsi təxminən
  `0.74 saniyə`, event/source vaxt fərqi `0 ms`, növbə isə `0 / 1000` oldu.
- Backend `133 passed`; frontend lint, build və render testi keçdi.
- İlk yalnız-oxuma texniki analiz əsası quruldu: `bar-builder 1.0.0` replay
  tick-lərindən `M1`, `M5`, `M15` və `H1` üzrə yalnız tam bağlanmış UTC mid-price
  şamları yaradır. Nəticə mənbə lineage-i və deterministik fingerprint daşıyır,
  boş/açıq şamlar doldurulmur və xam tick bazasına yazılmır. Modul testləri `9 passed`,
  tam backend regressiyası `142 passed` nəticəsi verdi.
- Yalnız-oxuma `indicator-package 1.0.0` əlavə edildi. EMA ayrıca SMA seed və eksponensial
  yenilənmə, RSI və ATR isə Wilder hesablaması ilə yalnız bağlanmış şamlardan qurulur.
  Warm-up tamamlanmayan hər nöqtə `insufficient_data` kimi işarələnir; nəticə bar
  fingerprint-inə bağlanır və gələcək şam əvvəlki nöqtələri dəyişmir. Yeni indikator
  testləri `11 passed`, tam backend regressiyası `153 passed` nəticəsi verdi.
- Sübut faylı `.runtime/phase2-acceptance/phase2-replay-latest.json` yolunda saxlanır
  və xam tick payload-u ehtiva etmir.

## Replay idarəetmə dashboard-u

2026-08-04 tarixində qorunan monitorinq panelinə Phase 2 replay idarəetməsi əlavə edildi.

- İstifadəçi simvol, vaxt intervalı və `step/max_speed` rejimi ilə sessiya yarada bilir.
- Sessiya siyahısı, detalı, lifecycle əmrləri, event səhifələri və tamamlanmış
  sessiyanın keyfiyyət hesabatı bir ekrandan idarə olunur.
- Əmrlər unikal idempotency açarı və cari `state_version` ilə göndərilir.
- Loading, empty, API xətası, conflict və bitmiş giriş sessiyası göstərilir.
- Mobil görünüş və klaviatura ilə istifadə qorunur.
- Replay siyahısı və detal API-si istifadəçi sahibliyini serverdə də məcburi edir.
- Frontend lint/build/render və tam backend `133 passed` nəticəsi ilə keçdi.
- Bölmə ticarət qərarı və əməliyyatı vermir.

## Public replay keyfiyyət hesabatı

2026-08-04 tarixində
`GET /api/v2/replay-sessions/{session_id}/quality-report` endpoint-i əlavə edildi.

- Yalnız sessiyanın sahibi tamamlanmış replay hesabatını oxuya bilir.
- Public cavab `data` və `meta.api_version=2` contract-ı ilə versiyalanır.
- Mövcud report ID və content fingerprint deterministik saxlanır.
- Daxili quality-report endpoint-i geriyə uyğun qalıb.
- Xam tick dəyişməzliyi və təkrar hesabat reproduksiyası testlərlə təsdiqlənib.
- Tam backend nəticəsi `132 passed`.

## Replay event oxuma API-si

2026-08-04 tarixində qorunan
`GET /api/v2/replay-sessions/{session_id}/events` endpoint-i əlavə edildi.

- Yalnız sessiyanın sahibi event-ləri oxuya bilir.
- Sıra `(event_timestamp, event_id)` üzrə deterministikdir.
- Cursor imzalanır, istifadəçiyə və sessiyaya bağlanır və vaxtı məhduddur.
- Sessiya yaradıldıqdan sonra gələn tick-lər snapshot sərhədini keçə bilmir.
- Səhifələr arasında dublikat və boşluq yaranmır; xam tick-lər dəyişmir.
- Tam backend nəticəsi `129 passed`.

## Replay lifecycle command API-si

2026-08-04 tarixində qorunan
`POST /api/v2/replay-sessions/{session_id}/commands` endpoint-i əlavə edildi.

- `start`, `step`, `pause`, `resume` və `cancel` qanuni vəziyyətlərdə işləyir.
- Dəyişiklik yalnız sessiyanın sahibinə icazə verilir.
- `Idempotency-Key` açıq saxlanmır; SHA-256 hash-i append-only command jurnalına yazılır.
- `expected_state_version` köhnə yazını `409` ilə təhlükəsiz rədd edir.
- Session, progress/checkpoint, audit və idempotency qeydi eyni transaction-da saxlanır.
- Audit xətası bütün əməliyyatı geri qaytarır və xam tick-lər dəyişmir.
- Tam backend nəticəsi `125 passed`; frontend lint və production build keçdi.

Son yenilənmə: 2026-08-05
Cari mərhələ: Phase 4
Status: PHASE 1 STABLE — PHASE 2 STABLE — PHASE 4 IN PROGRESS
Əsas budaq: `main`

## Phase 1 yekun qəbul nəticəsi

- Rəsmi canlı sınaq `2026-08-03 08:33:13 +04:00` tarixində başlayıb və
  `2026-08-04 11:44:06 +04:00` tarixində müqayisə edilib.
- `27.18` saat ərzində `340866` yeni tick qəbul olunub.
- Yeni rədd edilmiş event yaranmayıb; sayğac `7343` səviyyəsində qalıb.
- Disk növbəsi `0 / 1000`, tick axını `active`, SQLite `quick_check=ok` qalıb.
- Məlumat itkisi təsdiqi və audit izi qorunub; avtomatik nəticə `PASSED` olub.
- Yekun regressiya: backend `16 passed`, frontend lint/build/render keçib, MT5
  Bridge və MQL5 queue test faylı `0 errors, 0 warnings` ilə kompilyasiya edilib.
- Phase 1 rəsmi bağlanıb və məlumat qəbul qatı `Stable` qəbul edilib. Bu qərar
  real ticarət və ya order icazəsi vermir.

## Phase 2 üçün bazardan asılı olmayan dizayn hazırlığı

- Phase 2-nin ilk istehsal kodu tamamlandı: SQLite bazasını `mode=ro` və
  `query_only` ilə açan tick replay repository-si əlavə edildi.
- Repository `[start_at, end_at)` intervalı, simvol sərhədi, `1..1000` limit və
  `(event_timestamp, event_id)` keyset səhifələməsi tətbiq edir.
- Eyni timestamp-li tick-lərin deterministik ardıcıllığı, səhifələr arasında
  boşluq/dublikat olmaması, boş interval, validation və xam sətirlərin
  dəyişməzliyi yoxlanıldı: yeni testlər `6 passed`, tam backend `22 passed`.
- Canlı bazada migration edilməyib, mövcud API dəyişdirilməyib və ticarət/order
  funksiyası əlavə olunmayıb.
- Versiyalanmış migration runner-i əlavə edildi: SHA-256 checksum nəzarəti,
  eksklüziv transaction, xətada rollback, təkrar icrada no-op və dağıdıcı SQL-in
  ilkin rəddi tətbiq olunur.
- `idx_tick_events_replay(symbol, event_timestamp, event_id)` indeksi yalnız
  müvəqqəti bazada tətbiq və query planında təsdiq edildi; canlı database faylına
  toxunulmadı və production yolu default olaraq açıq icazəsiz rədd edilir.
- Migration üzrə yeni `6` test və tam backend üzrə `28` test keçdi.
- Replay dataset snapshot modulu əlavə edildi: seçilmiş interval sabit read
  transaction-ında maksimum `1000`-lik batch-lərlə oxunur, bütün dataset yaddaşa
  yüklənmir.
- Snapshot tick sayını, ilk/son `(event_timestamp, event_id)` mövqeyini və kanonik
  `event_id` axınından versiyalanmış SHA-256 fingerprint-i hesablayır.
- Snapshot üzrə `7` yeni test və tam backend üzrə `35` test keçdi; canlı baza,
  mövcud API və ticarət sərhədləri dəyişdirilmədi.
- `0002` migration-u ilə `replay_sessions`, sessiya siyahı/state/owner indeksləri,
  `replay_session_audit` və append-only qoruyucu trigger-lər əlavə edildi.
- Müvəqqəti bazada rejim, vəziyyət, interval, tick/progress constraint-ləri,
  foreign key, `ON DELETE RESTRICT`, audit `UPDATE/DELETE` bloklanması və Phase 1
  sətirlərinin qorunması yoxlanıldı.
- Schema/migration hədəf testləri `16 passed`, tam backend `45 passed` oldu; canlı
  database faylına migration tətbiq edilmədi.
- Replay sessiyası yaratma repository-si əlavə edildi: qeyri-şəffaf kriptoqrafik
  session ID, immutable girişlər, snapshot metadatası və ilkin `create` audit sətri
  eyni transaction daxilində saxlanılır.
- Dolu dataset ilkin `created`, boş dataset ilkin `completed` vəziyyətində yaradılır;
  audit insert xətası sessiya insert-ini də tam rollback edir.
- Sessiya repository-si üzrə `11` yeni test və tam backend üzrə `56` test keçdi;
  xam tick məlumatı, canlı baza, API və ticarət sərhədləri dəyişdirilmədi.
- Replay sessiyasının qanuni `start`, `pause`, `resume`, `complete`, `cancel`,
  `interrupt` və `fail` keçidləri repository sərhədində tətbiq edildi.
- Terminal vəziyyətdən keçid, gözlənilməyən cari vəziyyət, geriyə gedən və dataset
  ölçüsünü aşan progress, yaxud datasetə aid olmayan checkpoint fail-closed rədd edilir.
- Vəziyyət, progress, checkpoint və append-only audit eyni transaction-da saxlanılır;
  audit xətasında bütün keçid rollback edilir və immutable sessiya girişləri qorunur.
- Sessiya yaradılması və həyat dövrü üzrə hədəf testlər `22 passed`, tam backend
  `67 passed` oldu; canlı baza, API, frontend və worker dəyişdirilmədi.
- `step` rejimi üçün `1..1000` tick həddində atomik batch emalı əlavə edildi;
  checkpoint-dən sonrakı tick-lər kanonik sıra ilə oxunur və son batch sessiyanı
  avtomatik `completed` edir.
- `0003` migration-u addım əmrlərini unikal idempotency açarı ilə append-only saxlayır;
  eyni parametrli təkrar əmr əvvəlki nəticəni qaytarır, fərqli parametrli təkrar açar
  fail-closed rədd edilir.
- Progress, checkpoint, audit və idempotency qeydi bir transaction-dadır; məcburi
  audit xətası bütün addımı rollback edir.
- `step` repository-si üzrə `8` yeni test, hədəf paket üzrə `25 passed` və tam backend
  üzrə `75 passed` nəticəsi əldə edildi; yalnız müvəqqəti test bazaları istifadə olundu.
- `max_speed` orchestrator-u əlavə edildi: hər transaction-da maksimum `1000` tick
  emal edir, bütün dataset-i yaddaşa yükləmir və hər batch-dən sonra vəziyyəti yenidən
  yoxlayır.
- Pause/resume və restart son uğurlu checkpoint-dən boşluqsuz davam edir; completed
  sessiya yenidən emal olunmur, audit xətasında cari batch rollback edilir.
- Hər yeni və restart olunmuş icrada dataset say, sərhəd və fingerprint ilə yenidən
  təsdiqlənir; tick sayı eyni qalsa belə event əvəzlənməsi fail-closed aşkarlanır.
- `max_speed` üzrə `9` yeni test və tam backend üzrə `84 passed` nəticəsi əldə edildi;
  canlı baza, API, frontend və ticarət sərhədləri dəyişdirilmədi.
- Tamamlanmış `step` və `max_speed` sessiyaları üçün dəyişməz nəticə manifesti əlavə
  edildi. Manifest intervalı, rejimi, müqavilə versiyalarını, dataset izini və
  domen-ayrılmış kanonik nəticə fingerprint-ini daşıyır.
- Eyni dataset-in fərqli icra və manifest batch ölçülərində eyni fingerprint verməsi,
  natamam sessiyanın və dəyişmiş/uyğun olmayan dataset və müqavilələrin fail-closed
  rəddi yoxlanıldı. `8` yeni test və tam backend üzrə `92 passed` nəticəsi əldə edildi;
  canlı baza, API, frontend və ticarət sərhədləri dəyişdirilmədi.
- İlk streaming məlumat keyfiyyəti analizatoru əlavə edildi: `DQ-002` geriyə gedən
  mənbə vaxtını source/module seqmentində, `DQ-004` konfiqurasiya olunan zaman
  boşluğunu, `DQ-011` isə ardıcıl eyni payload namizədini ayrıca aşkarlayır.
- Eyni timestamp-li qanuni tick, hədd sərhədləri, module keçidi, fərqli batch
  ölçülərində deterministik nəticə, stabil finding ID və xam tick dəyişməzliyi
  yoxlanıldı; `5` yeni test və tam backend üzrə `97 passed` nəticəsi əldə edildi.
- Tamamlanmış replay sessiyasını nəticə manifesti ilə bağlayan keyfiyyət hesabatı
  əlavə edildi. Hesabat tapıntı səviyyələrindən deterministik `pass`, `review` və
  `fail` statusu, səviyyə sayları, stabil report ID və məzmun fingerprint-i yaradır.
- `DQ-005` mənfi spread qaydası critical səviyyədə əlavə edildi; sıfır qiymət bu
  qaydaya düşmür. Hesabat üzrə `5` yeni test, bütün backend üzrə `102 passed` oldu.
- `DQ-003` event/source vaxt fərqi, `DQ-006` sıfır və natamam qiymət cütü, `DQ-007`
  qeyri-sonlu/mənfi ədəd, `DQ-008` event müqaviləsi və `DQ-009` qəbul gecikməsi
  qaydaları dəqiq warning/critical sərhədləri ilə streaming analizatora əlavə edildi.
- Dəqiq hədlər, mənfi qəbul gecikməsi, sıfır qiymətin spread-dən ayrılması və
  hesabat regressiyası yoxlanıldı; tam backend üzrə `105 passed` nəticəsi əldə edildi.
- `DQ-010` tick sürəti, interval və spread paylanmalarını sabit yaddaşla hesablayır;
  sıfır/natamam qiymət cütləri ayrıca sayılır və nəticə replay hesabatının məzmun
  fingerprint-inə daxildir. Tam backend üzrə `108 passed` nəticəsi əldə edildi.
- Tamamlanmış replay keyfiyyət hesabatı autentifikasiyalı daxili read-only endpoint-ə
  çıxarıldı; giriş, mövcud olmayan və tamamlanmamış sessiya sərhədləri yoxlanıldı.
  Tam backend üzrə `110 passed` nəticəsi əldə edildi.

- Phase 11 üçün tam qərar-nəticə lineage-i, abstain/risk-block daxil selection-bias
  qoruması, yetişmiş label, model performansı və drift monitorinqi, təhlükəsiz REVIEW,
  dəyişməz yeni model versiyası, yenidən SHADOW qapısı, Knowledge Base governance-i və
  rollback müqaviləsi hazırlandı; canlı model özbaşına dəyişmir və risk artırılmır.
- Phase 10 üçün default-bağlı məhdud icra, dəyişməz run manifesti, təzə manual təsdiq,
  atomik pre-trade risk qapısı, idempotent order həyatı, broker reconciliation, davamlı
  kill switch və audit müqaviləsi hazırlandı; bu yalnız gələcək dizayndır, MT5 order
  interfeysi və real ticarət aktivləşdirilməyib.
- Phase 9 üçün real bazar axınında order-siz SHADOW müşahidəsi, səbəbiyyətə uyğun
  nəzəri fill və portfolio, champion/challenger müqayisəsi, restart/kəsinti qoruması,
  statistik qəbul qapısı və yalnız məhdud icra baxışına tövsiyə müqaviləsi hazırlandı;
  tətbiq Phase 1–8 qəbulundan asılıdır və brokerə heç bir əmr göndərmir.
- Phase 8 üçün deterministik analiz birləşdirməsi, izahlı qərar proposal-u, abstain,
  müstəqil risk qapısı, nəzəri mövqe ölçüsü, portfolio limitləri, halt, manual
  müdaxilə və SHADOW eligibility müqaviləsi hazırlandı; tətbiq Phase 1–7 qəbulundan
  asılıdır və real order yaratmır.
- Phase 7 üçün versiyalanmış bilik claim-i, evidence graph, scope və bazar rejimi
  uyğunluğu, etibarlılıq müddəti, zidd sübut, REVIEW trigger-ləri, governance və
  təhlükəsiz retrieval müqaviləsi hazırlandı; tətbiq Phase 1–6 qəbulundan asılıdır.
- Phase 6 üçün xəbər mənbə/lisenziya reyestri, dərc və qəbul vaxtının ayrılması,
  revision və fundamental vintage qorunması, entity mapping, point-in-time analiz,
  təsir ölçümü və standart event sərhədi müqaviləsi hazırlandı; tətbiq Phase 1–5
  qəbulundan asılıdır.
- Phase 5 üçün deterministik qrafik renderi, Visual AI dataset lineage-i, zaman və
  label sızması qoruması, model reproduksiyası, statistik baseline müqayisəsi və
  SHADOW sərhədi müqaviləsi hazırlandı; tətbiq Phase 1–4 qəbulundan asılıdır.
- Replay oxuması, məlumat keyfiyyəti, sessiya həyat dövrü, frontend ekranları və
  təhlükəsiz database migration müqavilələri hazırlanıb.
- Performans və yaddaş sınağı müqaviləsi hazırlanıb: kiçik, orta, böyük və stress
  dataset pillələri; replay, keyfiyyət analizi, paralel SQLite yazma/oxuma,
  migration, qorunan API və frontend ölçüləri müəyyən edilib.
- Yük və migration sınaqlarının canlı `database/ESAS_PLATFORM.sqlite` üzərində
  aparılması qadağandır; onlar yalnız sintetik müvəqqəti bazada işləyəcək.
- Phase 2 giriş və icazə müqaviləsi hazırlanıb: müşahidəçi, operator, auditor və
  administrator rolları, ownership, yüksək riskli əməliyyatların yenidən
  autentifikasiyası və append-only təhlükəsizlik auditi müəyyən edilib.
- Heç bir rol xam tick və audit sətrini dəyişə, siqnal və ya order yarada bilməz.
- Phase 2 müşahidə və xəbərdarlıq müqaviləsi hazırlanıb: platforma sağlamlığı,
  replay vəziyyəti və məlumat keyfiyyəti ayrılıb; metric, təhlükəsiz log,
  correlation ID, xəta kateqoriyaları, heartbeat, alert və fail-closed qaydaları
  müəyyən edilib.
- Məlumat keyfiyyəti tapıntısı avtomatik platforma nasazlığı sayılmır;
  xəbərdarlığın təsdiqi sayğacı silmir və problemi həll olunmuş göstərmir.
- Phase 2 saxlama və ehtiyat nüsxə müqaviləsi hazırlanıb: xam tick və auditin
  müddətsiz qorunması, backup manifesti, bərpa sınağı, disk hədləri və təhlükəsiz
  təmizləmə qaydaları müəyyən edilib.
- Phase 2 konfiqurasiya və təhlükəsiz startup müqaviləsi hazırlanıb: mühit
  profilləri, secret sərhədi, startup preflight, funksiya açarları, rotasiya,
  rollback və uzaq giriş tələbləri müəyyən edilib.
- Phase 2 API müqaviləsi hazırlanıb: `/api/v2` versiyalanması, asinxron işlər,
  imzalanmış snapshot cursor-u, ölçü və rate limitləri, idempotency, optimistic
  locking və sabit xəta envelope-u müəyyən edilib.
- Phase 2 worker və scheduler müqaviləsi hazırlanıb: Phase 1-dən ayrı davamlı job
  növbəsi, claim/lease/fencing, prioritet və ədalət, retry, checkpoint, restart
  bərpası, backpressure və təhlükəsiz shutdown qaydaları müəyyən edilib.
- Phase 2 audit və qəbul sübutu ixrac müqaviləsi hazırlanıb: sanitizasiya edilmiş
  ZIP/JSONL paket, manifest, checksum, rəqəmsal imza, offline verifier,
  chain-of-custody və acceptance `pass/fail/inconclusive` qaydaları müəyyən edilib.
- Phase 3 tədqiqat və statistik validasiya müqaviləsi hazırlanıb: əvvəlcədən
  qeydiyyat, zaman əsaslı train/validation/holdout bölgüsü, leakage və overfitting
  qoruması, walk-forward, baseline, multiple-testing, real icra xərcləri və
  SHADOW hazırlığına keçid qapıları müəyyən edilib.
- Phase 3 statistik analiz nəticə müqaviləsi hazırlanıb: mid-price və log-return,
  volatilite, spread, tick sürəti, MT5 tick-volume, sessiya təqvimi, neytral bazar
  rejimi, uncertainty, məlumat keyfiyyəti qapısı, API və frontend təqdimatı
  müəyyən edilib.
- Phase 4 pattern və texniki analiz müqaviləsi hazırlanıb: deterministik bar,
  yalnız bağlanmış barlardan causal indikator, dəyişməz pattern namizədi, label və
  horizon ayrılığı, realist backtest, xərc/risk göstəriciləri və SHADOW hazırlığı
  qapıları müəyyən edilib.
- Bu işlər dizayndır. Phase 2 istehsal kodu Phase 1-in rəsmi qəbulundan əvvəl
  başladılmayıb.

## 2026-07-30 canlı bərpa sınağı

- Backend-in verilənlər bazasına yaza bilmədiyi real nasazlıq aşkarlandı.
- MT5 Bridge disk növbəsi `1000 / 1000` həddinə çatdı.
- Backend düzgün istifadəçi icazəsi ilə başladıldıqdan sonra yazma bərpa olundu.
- Gözləyən bütün event-lər FIFO qaydasında göndərildi və növbə `0 / 1000` oldu.
- Canlı tick axını yenidən `active` vəziyyətinə qayıtdı.
- Hadisə zamanı rədd edilmiş `7343` event audit göstəricisi kimi qorunur.
- Frontend-də boş növbənin keçmiş `queue_full` xətasına görə dolu göstərilməsi
  düzəldildi; məlumat itkisi xəbərdarlığı ayrıca saxlanılır.
- Backend başlanğıcında verilənlər bazasına geri qaytarılan yazma sınağı əlavə
  edildi; sınaq bazada heç bir cədvəl və ya məlumat saxlamır.
- `/health` verilənlər bazası yazıla bilmədikdə `503` qaytarır.
- Tick saxlanması zamanı SQLite xətası baş verdikdə `/events/ticks` `503` qaytarır
  və MT5 Bridge eventləri növbəyə əlavə edə bilir.
- Avtomatik backend testləri: `12 passed`.
- Tarixi `7343` rədd edilmiş event silinmədən saxlanılır və qorunan API vasitəsilə
  auditli şəkildə təsdiqlənə bilər.
- Təsdiq edən istifadəçi, təsdiq vaxtı və həmin anda olan rədd edilmiş event sayı ayrıca
  saxlanılır.
- Rədd edilmiş event sayı təsdiqlənmiş saydan yuxarı qalxarsa məlumat itkisi xəbərdarlığı
  avtomatik yenidən aktivləşir.
- Canlı backend yoxlamasında tick axını `active`, disk növbəsi `0 / 1000`,
  `loss_acknowledged=false` və `rejected_events=7343` göstərildi.
- Canlı qəbul sınağında `7343` tarixi rədd edilmiş event `RUFAT-091084` istifadəçisi
  tərəfindən təsdiqləndi.
- Təsdiqdən sonra API `status=ok`, `tick_stream.status=active`, `queue_count=0`,
  `loss_acknowledged=true` və `acknowledged_rejected_events=7343` qaytardı.
- Audit sətri SQLite bazasında istifadəçi, say və UTC vaxtı ilə saxlanıldı; tarixi
  rədd edilmiş event sayğacı silinmədi.
- 30 dəqiqəlik canlı sabitlik sınağında tick sayı `126685`-dən `158529`-a yüksəldi:
  `31844` yeni tick itkisiz saxlanıldı.
- Sınağın sonunda backend `/health=ok`, operational status `ok`, tick axını `active`,
  disk növbəsi `0 / 1000` və SQLite `quick_check=ok` oldu.
- Tarixi `7343` rədd edilmiş event üçün audit təsdiqi qorundu və yeni rədd edilmiş
  event qeydə alınmadı.
- 1 saatlıq canlı sabitlik sınağında tick sayı `169948`-dən `206454`-ə yüksəldi:
  `36506` yeni tick qəbul edildi.
- Sınağın sonunda yeni rədd edilmiş event `0`, disk növbəsi `0 / 1000`, backend
  health `ok`, operational status `ok` və SQLite `quick_check=ok` oldu.
- 12.62 saatlıq fasiləsiz canlı sınaqda tick sayı `209018`-dən `419186`-ya
  yüksəldi: `210168` yeni tick qəbul edildi.
- 12.62 saatlıq sınağın sonunda yeni rədd edilmiş event `0`, disk növbəsi
  `0 / 1000`, backend health `ok`, operational status `ok` və SQLite
  `quick_check=ok` oldu.
- Sınaqdan sonra backend `12 passed`, frontend lint, build və render testləri keçdi.
- PR #1 üçün GitHub Actions daxilində iki Backend və iki Frontend check-i uğurla
  tamamlandı.
- PR #1 `main` budağına merge commit ilə birləşdirildi.
- Merge commit üçün GitHub Actions Backend və Frontend testləri uğurla keçdi.
- Canlı restart sınağından sonra tick axını `active`, disk növbəsi `0 / 1000` oldu.
- `tools/start-local-platform.ps1` backend və frontend-i bir əmrlə başladır, mövcud
  sağlam prosesləri tanıyır və təkrar proses yaratmır.
- `tools/stop-local-platform.ps1` yalnız başlatma skriptinin qeydə aldığı, PID və
  başlanma vaxtı uyğun gələn prosesləri dayandırır.
- Başlatma skripti backend `/health` və frontend HTTP cavabını gözləyir; uğursuz
  başlanğıcda yaratdığı proses ağacını təhlükəsiz dayandırır.
- Başlatma və dayandırma skriptlərinin PowerShell sintaksisi, canlı backend
  sağlamlığı və frontend `200` cavabı yoxlanıldı.
- Phase 1 uzunmüddətli sınaqları üçün başlanğıc və son göstəriciləri lokal JSON
  sübutunda saxlayan qəbul aləti əlavə edildi.
- Qəbul aləti health, operational status, tick artımı, disk növbəsi, rejection,
  məlumat itkisi təsdiqi, SQLite `quick_check` və audit sayını avtomatik yoxlayır.
- Alətin real backend yoxlamasında tick artımı və dəyişməyən rejection düzgün
  hesablandı; məxfi məlumat sübut faylına yazılmadı və minimum 24 saat qapısı
  erkən müqayisəni düzgün rədd etdi.
- Starlette-in rəsmi tövsiyəsinə uyğun `httpx2 2.9.1` test transportu əlavə
  edildi; backend testləri `12 passed` nəticəsi ilə xəbərdarlıqsız keçdi.
- GitHub Actions `checkout@v6`, `setup-python@v6` və `setup-node@v6` versiyalarına
  yeniləndi; action runtime Node.js 24-ə keçirildi.

## Layihənin məqsədi

ESAS Platform bazar məlumatlarını toplayan, qoruyan, analiz edən və statistik olaraq sübut edilmiş nəticələr əsasında gələcəkdə qərar verə bilən modul platformadır.

Platforma əvvəlcədən seçilmiş strategiyanı sübut etməyə çalışmır. Strategiyalar müşahidə, toplanmış məlumat və statistik yoxlama nəticəsində yaranmalıdır.

## Cari Phase 1 məqsədi

Etibarlı və yoxlanıla bilən tick məlumatı axını yaratmaq:

```text
MT5 Tick
→ ESAS MT5 Bridge
→ TICK_RECEIVED Event
→ HTTP
→ FastAPI Validation
→ SQLite Storage
→ Tick Statistics
→ Operational Monitoring
```

## Tamamlanmış işlər

- Platformanın konstitusiya sənədləri yaradılıb.
- Ümumi arxitektura hazırlanıb.
- Standart event müqaviləsi müəyyən edilib.
- MT5 Bridge canlı tick qəbul edir.
- Tick məlumatı `TICK_RECEIVED` event-inə çevrilir.
- Event JSON formatında serializasiya edilir.
- Event HTTP vasitəsilə backend-ə göndərilir.
- FastAPI event strukturunu yoxlayır.
- Tick-lər SQLite bazasında saxlanılır.
- Eyni `event_id` ikinci dəfə bazaya yazılmır.
- Tick statistikası endpoint-i yaradılıb.
- Operational status endpoint-i yaradılıb.
- `waiting`, `active` və `stale` axın vəziyyətləri nəzərdə tutulub.
- Real MT5 axını ilə `active` və `stale` vəziyyətləri yoxlanılıb.
- Sınaq zamanı 172 tick-in saxlanması müşahidə edilib.
- Uğursuz HTTP göndərişləri üçün ilkin yaddaş FIFO buferi yaradılıb.
- Backend bərpa olduqda buferdəki event-lərin FIFO batch şəklində avtomatik göndərilməsi real MT5 axını ilə yoxlanılıb.
- Layihə GitHub-a yüklənib.

## Mövcud API endpoint-ləri

- `GET /health`
- `POST /events/ticks`
- `POST /status/bridge`
- `GET /statistics/ticks`
- `GET /status/operational`

## Cari modul vəziyyəti

### Backend

- Texnologiya: FastAPI
- Verilənlər bazası: SQLite
- Versiya: `0.3.0`
- Tick doğrulaması və saxlanması işləyir.
- Operational monitoring işləyir.

### MT5 Bridge

- Status: `EXPERIMENTAL`
- Sənədləşdirilmiş versiya: `1.6.1`
- Canlı tick oxunması işləyir.
- Event yaradılması işləyir.
- HTTP göndərişi işləyir.
- Uğursuz event-in disk əsaslı davamlı FIFO növbəsinə əlavə edilməsi işləyir.
- Növbədəki event-lər EA və MT5 restartından sonra bərpa olunur.
- Event-lər backend bərpa olduqda konfiqurasiya olunan batch ölçüsü ilə
  avtomatik göndərilir.
- Qəbul edilməyən event sayı restartlar arasında davamlı saxlanılır.
- Queue vəziyyəti və xəta səbəbi backend operational API-yə göndərilir.

### Frontend

- `frontend` qovluğunda Phase 1 monitorinq paneli yaradılıb.
- Panel yalnız backend API vasitəsilə məlumat alır.
- Tick, MT5 Bridge, disk növbəsi və rədd edilən event vəziyyətlərini göstərir.
- Məlumat 5 saniyədə bir yenilənir və müvəqqəti API xətasında son uğurlu
  göstəricilər qorunur.
- Brauzer səhifəsi arxa planda olduqda avtomatik sorğular dayandırılır; səhifə
  yenidən görünəndə və bağlantı bərpa olunanda məlumat dərhal təzələnir.
- Başlıq hissəsində sorğunun vəziyyətini göstərən əl ilə yeniləmə idarəsi var.
- Bir neçə Bridge olduqda növbə və rejection göstəriciləri ümumiləşdirilir;
  simvol/Bridge filtri ayrıca mənbənin vəziyyətini göstərir.
- Lokal lint, production build və server-render testi keçir.

## Məlum problemlər

1. Bridge operational vəziyyəti backend restartından sonra ilk status hesabatına
   qədər `waiting` olur.
2. Çox yüksək tick sürəti üçün retry batch ölçüsünün yekun uzunmüddətli yoxlaması
   24 saatlıq canlı qəbul sınağında aparılacaq.
3. Frontend yalnız lokal backend ilə işləyir; production hostinq üçün backend-in
   şəbəkədən əlçatan HTTPS ünvanı tələb olunur.

## Son tamamlanan texniki dəyişiklik

- Phase 2 SQLite sxemi və təhlükəsiz migration müqaviləsi hazırlandı. Replay
  sessiyası, checkpoint, append-only audit, idempotency, keyfiyyət hesabatı və
  tapıntı cədvəlləri müəyyən edildi.
- Real migration-dan əvvəl online backup, `quick_check`, sətir sayları və xam
  event fingerprint-i; migration-dan sonra isə eyni sübutların müqayisəsi və
  ayrıca bərpa sınağı tələb olunur.
- Real bazada heç bir migration icra edilməyib və xam `tick_events` cədvəlinə
  toxunulmayıb.
- Phase 2 frontend replay və məlumat keyfiyyəti ekranlarının funksional
  müqaviləsi hazırlandı. Qorunan naviqasiya, sessiya yaratma, addım və maksimum
  sürət idarəsi, progress, keyfiyyət tapıntıları və təhlükəsiz xəta davranışı
  müəyyən edildi.
- Frontend-in analiz qaydalarını özü hesablamaması, bazar fasiləsini məlumat
  itkisi kimi təqdim etməməsi, order və al/sat idarəsi göstərməməsi qorundu.
- Phase 2 replay sessiyasının həyat dövrü hazırlandı. `step` və `max_speed`
  rejimləri, dəyişməz giriş parametrləri, dataset fingerprint, checkpoint,
  backend restartından sonra `interrupted` vəziyyəti və idempotent idarəetmə
  əmrləri müəyyən edildi.
- Replay sessiyası yalnız törəmə vəziyyət və audit yaza bilər; xam tick məlumatını
  dəyişdirmək, siqnal yaratmaq və order açmaq müqavilə ilə qadağandır.
- Phase 2 məlumat keyfiyyəti müqaviləsi hazırlandı. Boşluq, timestamp,
  mənfi spread, natamam qiymət, qəbul gecikməsi və müqavilə uyğunsuzluğu
  qaydaları versiyalanmış formada müəyyən edildi.
- Bazar sessiyası təqvimi olmadan uzun fasilənin avtomatik məlumat itkisi
  sayılmaması və sıfır qiymətlərin səhv müsbət nəticə yaratmaması sənəddə
  qorundu.
- Phase 2 üçün yalnız-oxuma tick replay müqaviləsi hazırlandı. Müqavilə sabit
  `[start_at, end_at)` aralığını, `event_timestamp + event_id` deterministik
  sırasını, cursor səhifələməni, qorunan API sərhədini və məlumatın
  dəyişməzliyini təsdiqləyən qəbul testlərini müəyyən edir.
- Bu hazırlıq yalnız dizayn və qəbul meyarlarıdır; Phase 1 bağlanmadan Phase 2
  istehsal kodu başladılmayıb.

- MT5 tick və status qəbulu minimum 32 simvolluq ayrıca Bridge açarı ilə
  qorundu; açarsız və səhv açarlı sorğular `401` cavabı alır.
- Backend versiyası `0.3.0`, MT5 Bridge versiyası `1.6.0` edildi.
- Backend `16 / 16` test, MQL5 kompilyasiyası `0 errors, 0 warnings` nəticəsi
  verdi.
- Backend `0.3.0` və MT5 Bridge `1.6.0` eyni məxfi açarla canlı qoşuldu.
  Qısa qəbul müqayisəsində 3 saniyədə `15` yeni tick qəbul edildi, axın
  `active`, növbə `0 / 1000` və ümumi status `ok` oldu.
- Backend və frontend cavablarına keşdən qorunma, clickjacking, MIME sniffing,
  referrer və lazımsız brauzer icazələrinə qarşı təhlükəsizlik başlıqları
  əlavə edildi.
- Təhlükəsizlik başlıqları backend API və frontend server-render testlərində
  avtomatik təsdiqlənir; backend `15 / 15`, frontend lint, production build və
  server-render testləri uğurla keçdi.
- Monitorinq panelinin `Çıxış` əməliyyatı server tərəfli sessiya ləğvi ilə
  tamamlandı; çıxışdan sonra köhnə bearer nişanı yenidən istifadə edilə bilmir.
- Hər giriş üçün unikal sessiya identifikatoru yaradılır və backend restartı
  bütün əvvəlki monitorinq sessiyalarını etibarsız edir.
- Sessiya ləğvi testi daxil olmaqla backend `15 / 15`, frontend lint,
  production build və server-render testləri uğurla keçdi.
- Monitorinq girişinə eyni şəbəkə ünvanı üzrə uğursuz cəhd məhdudiyyəti əlavə
  edildi: 5 ardıcıl səhvdən sonra 15 dəqiqəlik müvəqqəti bloklama tətbiq olunur.
- Uğurlu giriş əvvəlki səhv cəhd sayğacını sıfırlayır və bloklanmış giriş
  sorğuları `429 Too Many Requests` cavabı alır.
- Backend giriş təhlükəsizliyi testləri daxil olmaqla `14 / 14`, frontend lint,
  production build və server-render testləri uğurla keçdi.

Frontend çoxsaylı Bridge və simvol üçün optimallaşdırılıb. Əsas kartlar bütün
Bridge-lərin növbə və rejection göstəricilərini düzgün ümumiləşdirir, seçim
filtri isə ayrıca Bridge-in versiyasını, növbəsini və audit vəziyyətini göstərir.
Məlumat itkisi təsdiqi yalnız konkret Bridge seçildikdə aparılır.

## Phase 1-in tamamlanması

Bütün qəbul qapıları keçib və Phase 1 `2026-08-04` tarixində rəsmi bağlanıb.

## Növbəti əsas texniki prioritet

Bağlanmış replay şamları üzərində versiyalanmış və deterministik ilk indikator
paketini (`EMA`, `RSI`, `ATR`) qurmaq; warm-up tamamlanmadıqda nəticəni açıq şəkildə
`insufficient_data` saxlamaq və ticarət qərarı/order icrasından ayrı tutmaq.

## Phase 2 replay yaratma API-si

- `POST /api/v2/replay-sessions` dashboard sessiyası ilə qorunur və `symbol`,
  `[start_at, end_at)` intervalı, eləcə də `step|max_speed` rejimini qəbul edir.
- Naməlum sahə, timezone-suz vaxt, boş/tərs interval və naməlum rejim fail-closed
  `422` cavabı alır; uğurlu yaradılma `202 Accepted` qaytarır.
- Snapshot, replay sessiyası və ilkin append-only audit mövcud repository
  transaction-u ilə atomik saxlanılır; audit xətası bütün yazını geri qaytarır.
- Məlumatlı dataset `created`, boş dataset təhlükəsiz `completed` vəziyyətində
  yaradılır və yaradıcı istifadəçi `operator` rolu ilə auditə yazılır.
- API testləri xam tick dəyişməzliyini, uğursuz audit rollback-ini və etibarsız
  sorğuların heç bir yazı yaratmamasını təsdiqləyir.
- Replay API hədəf testləri `11 passed`, tam backend `121 passed` nəticəsi verir;
  bütün testlər yalnız müvəqqəti SQLite bazasında işləyir.

## Böyük baza üçün frontend cavab müddəti düzəlişi

- Canlı bazada tick sayı `1.22` milyonu keçdikdə operational və statistika
  cavablarının əvvəlki `3` saniyə həddini aşdığı ölçüldü.
- Frontend sorğu müddəti `10` saniyəyə qaldırıldı və `event_id` primary key-inin
  artıq təmin etdiyi unikallıq üçün lazımsız `COUNT(DISTINCT event_id)` skanı
  çıxarıldı.
- Backend `116 passed`, frontend lint/build/render və GitHub yoxlamaları keçdi;
  düzəliş PR `#5` ilə `main` budağına birləşdirildi.

## Phase 2 replay oxuma API-si

- `GET /api/v2/replay-sessions` giriş sessiyası ilə qorunur və sessiyaları
  `created_at DESC, session_id DESC` sabit sırası ilə qaytarır.
- Səhifələmə cursor-u HMAC ilə imzalanır, istifadəçiyə və replay resursuna bağlanır,
  bir saat sonra etibarsız olur; dəyişdirilmiş cursor təhlükəsiz `400` alır.
- `GET /api/v2/replay-sessions/{session_id}` checkpoint daxil olmaqla saxlanmış
  sessiya metadatasını qaytarır, mövcud olmayan sessiya təhlükəsiz `404` alır.
- API yalnız oxuyur; xam tick, replay progress və audit məlumatını dəyişmir.
- Yeni API testləri `6 passed`, tam backend `116 passed`; frontend lint, build və
  render regressiyası keçib.

## Phase 1 RC1 release qeydləri

`docs/releases/PHASE_1_RC1.md` faylında backend `0.2.0`, MT5 Bridge `1.5.0`,
frontend `0.1.0`, qəbul sübutları, geriyə uyğunluq, məlum məlumat itkisi və qalıq
risklər sənədləşdirildi.

RC1 bütün qəbul qapılarını keçib. Stable qərarı və yekun sübutlar
`docs/releases/PHASE_1_STABLE.md` faylında sənədləşdirilib.

## Məlumat itkisi üzrə yekun hesabat

`docs/status/DATA_LOSS_REPORT.md` faylında `7343` tarixi rədd edilmiş event üzrə
kök səbəb, təsir dairəsi, audit izi, düzəlişlər, qəbul sübutları və qalıq risklər
sənədləşdirildi.

Hesabat tarixi məlumat itkisini bərpa edilmiş kimi göstərmir. Audit təsdiqi
itkinin görüldüyünü və qəbul edildiyini bildirir; payload-ları saxlanmayan
`7343` event bərpa edilə bilməz.

## UTF-8 kodlaşdırma auditi

2026-07-31 tarixində Git-də izlənən bütün `64` layihə faylı sərt UTF-8 decoder
ilə yoxlanıldı.

- Etibarsız UTF-8 faylı: `0`.
- Mojibake nümunəsi olan mətn faylı: `0`.
- Lazımsız UTF-8 BOM olan fayl: `0`.
- Repo üçün UTF-8 və LF qaydasını sabitləşdirən `.editorconfig` əlavə edildi.

Əvvəl Windows PowerShell-də görünən pozulmuş hərflər fayl məlumatının korlanması
deyil, Windows PowerShell 5-in BOM-suz UTF-8 fayllarını default kodlaşdırma ilə
oxumasının nəticəsi idi. Belə fayllar `Get-Content -Encoding utf8` ilə düzgün
göstərilir.

## Avtomatlaşdırılmış MT5 queue və retry qəbul testi

2026-07-31 tarixində `ESAS_PersistentQueue_Test` real MT5 terminalında işləndi.

- MQL5 kompilyasiyası: `0 errors, 0 warnings`.
- Avtomatik assertion nəticəsi: `44 / 44`, uğursuzluq `0`.
- FIFO sırası və yalnız ilk eventin acknowledgement ilə silinməsi yoxlanıldı.
- Pending event və rejection metriyinin restart simulyasiyasından sonra bərpası
  yoxlanıldı.
- Uğursuz göndəriş simulyasiyasında event növbədə saxlanıldı.
- Retry batch limitindən sonra qalan event restart simulyasiyasında bərpa edildi.
- Queue-full, serialization rejection və korlanmış jurnal aşkarlanması yoxlanıldı.
- Test unikal açarlar istifadə etdi və yaratdığı müvəqqəti faylları təmizlədi.

## Queue health monitorinqinin son canlı sınağı

2026-07-30 tarixində MT5 Bridge `1.5.0` və backend `0.2.0` birlikdə yoxlanıldı.

- Bridge hər 5 saniyədə `POST /status/bridge` hesabatı göndərdi.
- Operational API `bridge_delivery.status=healthy` göstərdi.
- `queue_count=0`, `queue_capacity=1000` göstərildi.
- `rejected_events=0`, `last_queue_error=none` göstərildi.
- Tick axını `active` oldu.
- Backend testləri `7 passed` nəticəsi verdi.
- MT5 layihə və terminal kompilyasiyaları `0 errors, 0 warnings` nəticəsi verdi.

## Backend test bazasının təcridi

2026-07-30 tarixində backend testləri canlı bazadan ayrıldı.

- Hər test ayrıca müvəqqəti SQLite faylı istifadə edir.
- Test bitdikdə database yolu production default dəyərinə qaytarılır.
- İdempotency testinin ilk cavabı deterministik olaraq `stored` olur.
- Operational status test database yolunun canlı bazadan fərqli olduğunu
  təsdiqləyir.
- Canlı `database/ESAS_PLATFORM.sqlite` testlər tərəfindən istifadə edilmir.
- Bütün `7` backend testi keçdi.

## Avtomatik GitHub test axını

2026-07-30 tarixində `.github/workflows/tests.yml` əlavə edildi.

- Workflow `main`, `agent/**` push-larında və pull request-lərdə başlayır.
- Python `3.13` təmiz GitHub runner mühitində qurulur.
- Backend dependency-ləri kilidlənmiş requirements faylından quraşdırılır.
- `module.json` JSON validation-dan keçirilir.
- Backend və test Python mənbələri compile edilir.
- `pytest` cache yazmadan icra olunur.
- Workflow lokal YAML validation və `7 passed` nəticəsi ilə yoxlanıldı.

## Disk növbəsi üzrə son canlı sınaq

2026-07-30 tarixində backend bağlı olduğu halda MT5 Bridge `1.4.0` yenidən
başladıldı.

- Başlanğıcda diskdən `queue_count=1000` bərpa edildi.
- FIFO növbə faylı EA restartı zamanı qorundu.
- Backend başladıldıqdan sonra event-lər hər dövrdə maksimum 50-lik batch-lərlə
  göndərildi.
- Növbə təxminən 16 saniyədə `1000`-dən `0`-a endi.
- Son batch `delivered=24 | queue_count=0` nəticəsi verdi.
- Operational endpoint tick axınını `active` göstərdi.
- Backend bazasında ümumi tick sayı `33570` oldu.
- Həm layihə, həm MT5 terminal nüsxəsi `0 errors, 0 warnings` ilə kompilyasiya
  edildi.
- Backend testləri `5 passed` nəticəsi verdi.

Sınaqda növbənin `1000` limitinə çatdığı da müşahidə edildi. Mövcud növbə
qorundu, lakin limitdən sonra gələn event-lər saxlanıla bilmədiyi üçün növbəti
prioritet itki sayğacı və queue health monitorinqidir.
## Qorunan texniki analiz API-si

2026-08-04 tarixində tamamlanmış replay sessiyaları üçün yalnız-oxuma texniki analiz
endpoint-i hazırlandı.

- Yalnız sessiya sahibi və yalnız `completed` sessiya nəticəni görə bilər.
- `M1`, `M5`, `M15`, `H1` qapalı şamları və EMA, RSI, ATR seriyaları təqdim edilir.
- Periodlar və qaytarılan şam sayı təhlükəsiz limitlərlə yoxlanılır.
- Dataset sessiyanın ilkin fingerprint-i ilə yenidən yoxlanılır; drift aşkar edilərsə
  nəticə verilmir.
- Dataset, bar və indikator versiyaları/fingerprint-ləri cavabda saxlanılır.
- Warm-up nöqtələri `insufficient_data` kimi açıq görünür.
- Endpoint strategiya, al/sat siqnalı və order yaratmır.
- Yeni API testləri və tam backend regressiyası `156 passed` nəticəsi verdi; frontend
  lint və production build yoxlamaları keçdi.

## Texniki analiz təqdimat qatı

2026-08-04 tarixində tamamlanmış replay sessiyalarının texniki analiz nəticələri
qorunan frontend panelinə çıxarıldı.

- İstifadəçi `M1`, `M5`, `M15`, `H1` timeframe, EMA/RSI/ATR periodları və görünən
  bar sayını seçə bilir.
- Bağlanış qiyməti və EMA eyni qrafikdə, RSI və ATR isə bir-birindən asılı olmayan
  ayrıca kartlarda göstərilir.
- Kifayət etməyən warm-up barları gizlədilmir və Azərbaycan dilində izah olunur.
- Dataset, bar və indikator fingerprint/versiya izi ayrıca açılan məlumat mənbəyi
  bölməsində saxlanılır.
- Boş nəticə, yüklənmə, API xətası və mobil görünüş üçün ayrıca vəziyyətlər quruldu.
- Panel yalnız tamamlanmış və istifadəçiyə məxsus replay sessiyasından açılır; alış/satış
  siqnalı vermir və order yaratmır.
- Frontend lint, production build və `2` frontend testi keçdi; tam backend regressiyası
  ayrıca runtime test qovluğu ilə `156 passed` nəticəsi verdi.

## Versiyalanmış strategiya modul müqaviləsi

2026-08-04 tarixində texniki indikatorlar üzərində yalnız tədqiqat məqsədli strategiya
modul sərhədi quruldu.

- Ümumi strategiya kontraktı, nəticə modeli və EXPERIMENTAL həyat dövrü yaradıldı.
- İlk istinad modulu `ema_close_relation` `1.0.0` olaraq ayrıca paketləndi.
- Modul yalnız bağlanmış barın close qiymətini eyni barın causal EMA-sı ilə müqayisə edir.
- Nəticə dataset, bar və indikator fingerprint-lərinə bağlanır və öz SHA-256
  fingerprint-ini yaradır.
- Warm-up `insufficient_data` kimi saxlanır; nəticə al/sat siqnalı və order yaratmır.
- Determinizm, warm-up, boş məlumat, zaman uyğunluğu və no-lookahead testləri keçirildi.

## Strategiya nəticəsi API-si və müqayisə görünüşü

2026-08-04 tarixində versiyalanmış strategiyaların tamamlanmış replay üzərində
işlədilməsi üçün qorunan, yalnız-oxuma təqdimat qatı tamamlandı.

- `/api/v2/replay-sessions/{session_id}/strategy-analysis` yalnız sessiya sahibinə və
  yalnız tamamlanmış replay məlumatına xidmət edir.
- Texniki analiz və strategiya eyni yoxlanmış dataset, bağlanmış bar və indikator
  kontekstini paylaşır; dataset drift nəticəni dayandırır.
- İlk modul `ema_close_relation` ayrıca versiya, lifecycle, parametr, sayım və
  fingerprint izi ilə qaytarılır.
- Frontenddə strategiya nəticəsi ayrıca kartda EMA-dan yuxarı/aşağı/bərabər payları,
  warm-up sayını və hesablama izini sadə Azərbaycan dilində göstərir.
- Görünüş mobil ölçüyə uyğunlaşır və gələcək modulların ayrıca kart kimi əlavə
  olunmasına hazırdır.
- Nəticə yalnız araşdırma müşahidəsidir; al/sat qərarı, mövqe ölçüsü və order yaratmır.
- Hədəf testləri `11 passed`, tam backend regressiyası `164 passed`, frontend lint,
  production build və `3` frontend testi uğurla keçdi.

## Çoxpəncərəli walk-forward sabitlik ölçümü

2026-08-04 tarixində EMA və RSI tədqiqat modullarının müxtəlif zaman hissələrində
sabitliyini ayrıca göstərən çoxpəncərəli qiymətləndirmə qatı tamamlandı.

- `expanding_chronological_validation_windows 1.0.0` ən azı iki, ən çox səkkiz
  ardıcıl yoxlama pəncərəsini deterministik yaradır.
- Hər növbəti pəncərənin inkişaf hissəsi yalnız əvvəlki məlumatla genişlənir;
  yoxlama pəncərələri üst-üstə düşmür və təsadüfi qarışdırılmır.
- İnkişaf sərhədini keçən gələcək nəticələr həmin inkişaf hesabından çıxarılır.
- Hər pəncərə inkişaf/yoxlama indeksləri, ayrıca bar fingerprint-ləri və upstream
  strategiya/nəticə fingerprint-ləri ilə izlənir.
- Əhatə, yetişmiş/yetişməmiş/tətbiq olunmayan müşahidələr və xərcsiz tarixi
  dəyişiklik ayrıca saxlanır.
- Frontend iki-beş pəncərə seçimini, hər pəncərənin tarixini, müşahidə sayını,
  yuxarı/aşağı bölgüsünü, çəkili orta dəyişiklik və pəncərələrarası aralığı göstərir.
- Kiçik dataset nəticəni uydurmur və `insufficient_data` kimi açıq göstərilir.
- Hədəf backend sınaqları `24 passed`, tam backend regressiyası `198 passed`,
  frontend lint, production build və `3` frontend testi uğurla keçdi.
- Bu qat yalnız tarixi tədqiqat üçündür; canlı siqnal, risk ölçüsü və order yaratmır.

## Tarixi əməliyyat xərci və stress ssenariləri

2026-08-05 tarixində EMA və RSI walk-forward nəticələri üçün şəffaf xərc fərziyyəsi
qatı tamamlandı.

- `historical_cost_stress_adjustment 1.0.0` normal, pis və stress ssenarilərini eyni
  deterministik qayda ilə bütün yoxlama pəncərələrinə tətbiq edir.
- Xam xərcsiz nəticə dəyişdirilmir; xərcdən sonrakı nəticə, ümumi xərc və əhatə ayrıca
  saxlanılır.
- Spread, komissiya, slippage və gecikmə `basis point` vahidi ilə açıq göstərilir və
  broker faktı deyil, tədqiqat fərziyyəsi kimi işarələnir.
- Konfiqurasiya, upstream multi-window fingerprint-i və nəticə öz SHA-256 izi ilə
  təkrar istehsal edilə bilir.
- Sıfır, mənfi, həddən artıq və natamam xərc, yanlış stress sırası, determinism və
  bütün pəncərələrdə eyni qayda testlərlə qorunur.
- Frontend normal, pis və stress kartlarında xam/xalis tarixi dəyişikliyi və xərc
  tərkibini sadə Azərbaycan dilində göstərir.
- Hədəf backend yoxlamaları `27 passed`, tam backend regressiyası `216 passed`,
  frontend lint, production build və `3` frontend testi uğurla keçdi.
- Qat ticarət mənfəəti hesablamır; siqnal, mövqe ölçüsü, risk icazəsi və order yaratmır.

## Statistik etibarlılıq və sıfır baza müqayisəsi

2026-08-05 tarixində EMA və RSI üzrə xərclərdən sonrakı walk-forward nəticələrinə
versiyalanmış qeyri-müəyyənlik qatı əlavə edildi.

- `purged_validation_mean_vs_zero_baseline 1.0.0` yalnız xronoloji validation
  müşahidələrindən və hər nəticə üfüqünə bir müşahidədən istifadə edir.
- Normal, pis və stress ssenariləri qarışdırılmadan ayrıca qiymətləndirilir.
- Effektiv nümunə sayı, orta xalis dəyişiklik, nümunə standart sapması, standartlaşdırılmış
  effekt ölçüsü və 95% etibar intervalı saxlanılır.
- Sadə baseline sıfır faiz dəyişiklikdir. Nəticə yalnız effektiv nümunə ən azı 30 olduqda,
  variasiya sıfır olmadıqda və intervalın aşağı sərhədi sıfırdan yuxarı olduqda
  `supportive_evidence` sayılır; digər hallar açıq səbəblə `insufficient_evidence` qalır.
- API müqaviləsi `1.2.0` versiyasına qaldırıldı və bütün nəticələr upstream fingerprint-lərlə
  təkrar istehsal edilə bilir.
- Frontend “Sübut yetərlidir / Sübut yetərli deyil” sərhədini, nümunə sayını, ortanı,
  95% intervalı və effekt ölçüsünü sadə Azərbaycan dilində göstərir.
- Tam backend regressiyası `222 passed`; frontend `3` test, lint və production build keçdi.
- Bu nəticə ticarət siqnalı, mənfəət zəmanəti, risk icazəsi və order deyil.
- 2026-08-05: `pattern_hypothesis_registry 1.0.0` tamamlandı. Bazar strukturu,
  likvidlik süpürməsi, BOS/CHoCH/retest və sonrakı zona modelləri üçün LONG/SHORT
  hipotezləri ayrıca, versiyalanmış və maşınla oxunan formada qeydiyyata alındı.
- Qorunan `/api/v2/research/pattern-hypotheses` endpoint-i və sadə Azərbaycan dilində
  frontend kartları əlavə edildi. Şəkillər sübut deyil, yalnız hipotez mənbəyidir.
- Reyestr heç bir siqnal, giriş, risk ölçüsü və order yaratmır. Növbəti mərhələ ayrıca
  təsdiqdən sonra causal HH/HL və LH/LL detektorunun tərifidir.
- Yoxlama: backend `224 passed`; frontend `4` test, lint və production build keçdi.

## 2026-08-05 — Bölmə əsaslı frontend iş sahəsi

- Uzun, alt-alta açılan monitorinq səhifəsi sol menyu və mərkəzi iş paneli ilə əvəz edildi.
- Standart açılan bölmə `Nəticələr`dir; istifadəçi başqa bölməni seçənədək ümumi GOLD xülasəsi görünür.
- Menyuda nəticələr, canlı vəziyyət, replay, texniki göstəricilər, bazar strukturu,
  likvidlik, BOS/CHoCH, retest, strategiya müqayisəsi və hipotez reyestri ayrıca bölmələrdir.
- Hər bölmə cari rəqəmi, GOLD-a mümkün təsirin sadə dildə izahını və açılan
  `Nəyə əsaslanır?` tədris qeydini göstərir.
- Texniki analiz alt panelləri seçilmiş menyuya görə ayrı göstərilir; mövcud hesablamalar və API müqavilələri dəyişdirilməyib.
- Masaüstü üçün sabit sol menyu, dar ekranlar üçün üfüqi və responsiv menyu əlavə edildi.
- Təhlükəsizlik sərhədi saxlanılıb: ekranlar araşdırma/monitorinq üçündür, siqnal və ticarət əməliyyatı yaratmır.
- Yoxlama: frontend production build və bütün `8/8` frontend testi uğurla keçdi.

## 2026-08-05 — Frontend fokus və istifadə təlimatı düzəlişi

- Replay sessiyalarının tam idarəetməsi yalnız `Replay sessiyaları` menyusunda göstərilir.
- Digər analiz bölmələrində yalnız seçilmiş replay-in qısa konteksti, aid analiz və
  `Sessiyanı dəyiş` keçidi göstərilir.
- Hər bölməyə yeni istifadəçi üçün üç addımlı istifadə qaydası əlavə edildi.
- Texniki `Phase 2` başlığı istifadəçi görünüşündən çıxarıldı.
- Platforma araşdırma/monitorinq rejimindədir; bu görünüşlər ticarət siqnalı deyil.
- Yoxlama: frontend production build və bütün `9/9` frontend testi uğurla keçdi.
