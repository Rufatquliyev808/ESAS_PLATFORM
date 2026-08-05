# ESAS Platform Phase 2 Stable buraxılış qeydləri

Version: `Phase 2 Stable`

Tarix: `2026-08-05`

Status: STABLE

## Qərar

Phase 2-nin bütün roadmap bəndləri (`PROJECT_ROADMAP.md`) tamamlanıb və real
məlumat üzərində qəbul sınağı keçib:

- Tarixi tick məlumatının yalnız-oxuma repository-si
- `step` və `max_speed` replay rejimləri
- Məlumat boşluğu, geriyə gedən timestamp və dublikat aşkarlanması
- Tick ardıcıllığının yoxlanması
- Spread və tick sürəti statistikası
- Simvollar üzrə deterministik məlumat keyfiyyəti hesabatı
- Replay nəticələrinin təkrar istehsal edilə bilməsi (cross-mode fingerprint bərabərliyi)

Bu qərar yalnız replay və məlumat keyfiyyəti qatına aiddir. Phase 2 heç bir
strategiya, siqnal, qərar və ya order yaratmır.

## Rəsmi qəbul sübutu

2026-08-04 tarixində production bazası (`database/ESAS_PLATFORM.sqlite`)
yoxlanmış SQLite backup-dan sonra Phase 2 sxeminə keçirildi və real `GOLD`
intervalı ilə qəbul sınağı aparıldı. Sübut `.runtime/phase2-acceptance/
phase2-replay-latest.json` faylında saxlanılır (xam tick payload-u ehtiva
etmir):

- Eyni 60 saniyəlik, `542` tick-lik dataset iki `step` və iki `max_speed`
  sessiyasında müstəqil icra edildi.
- Dörd sessiyanın dataset və nəticə fingerprint-ləri eyni oldu
  (`result_fingerprint: sha256:2708ed0b…`); cross-mode müqayisəsi (`cross_mode_equal`)
  `true` nəticəsi verdi.
- Xam tick sayı sınaqdan əvvəl və sonra `1,258,269` qaldı (`unchanged: true`).
- Qəbul nəticəsi (`evidence_contract: phase2-replay-acceptance-v1`) `PASSED`,
  kritik keyfiyyət tapıntısı (`critical_count`) `0` oldu.
- `DQ-009` bütün `542` tarixi tick üçün `received_at` vaxtının
  `event_timestamp`-dan əvvəl görünməsini `warning` səviyyəsində qeyd etdi;
  kök səbəb broker server vaxtının UTC işarəsi ilə göndərilməsi idi.
- MT5 Bridge `1.6.1` yeni event-lərdə broker server vaxtını UTC-yə
  normallaşdırır; mövcud xam tick-lər dəyişdirilmədi (Phase 2 xam məlumatı
  dəyişdirmir). Canlı qəbulda yeni tick-lərin gecikməsi təxminən
  `0.74 saniyə`, event/source vaxt fərqi `0 ms`, növbə `0 / 1000` olaraq
  təsdiqləndi — yəni `DQ-009` yalnız düzəlişdən əvvəlki tarixi tick-lərə
  aiddir, canlı axına aid deyil.

## Yekun regressiya nəticələri (qəbul tarixinə uyğun)

- Backend: `133 passed`.
- Frontend lint, production build və render testi: passed.
- Bu tarixdən sonra Phase 4 üzərində davam edən iş backend testlərini
  `251`-ə qədər genişləndirib; regressiya heç vaxt pozulmayıb (bax
  `docs/status/CURRENT_STATE.md`).

## Qalıq risklər

- Tarixi `DQ-009` tapıntısı (`542` warning) arxivlənmiş sübutda qalır;
  bu, kök səbəbi düzəldilmiş, lakin geriyə düzəldilməyən (Phase 2 müqaviləsinə
  görə xam məlumat dəyişdirilmir) tarixi keyfiyyət qeydidir.
- Performans və yük sınaqları (`PHASE_2_PERFORMANCE_TEST_CONTRACT.md`) yalnız
  sintetik müvəqqəti bazada aparılmalıdır; bu sınaqlar bu Stable qərarının
  hissəsi deyil və ayrıca aparılmayıb.
- Bu Stable qərarı yalnız replay/məlumat keyfiyyəti qatına aiddir; real
  ticarət və ya order icazəsi vermir.

## Növbəti mərhələ

Phase 4 (pattern və texniki analiz) artıq paralel başlanıb və bu qərardan
asılı deyil — bax `docs/status/CURRENT_STATE.md` və
`docs/status/NEXT_TASK.md`.
