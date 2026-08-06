# ESAS Platform — Sessiya handoff

Son yenilənmə: 2026-08-06

## Başlanğıc

- Əsas layihə: `D:\ESAS_PLATFORM`
- `AGENTS.md` sənədindəki oxuma sırasını tam icra et.
- Git statusunu, branch-i və son commitləri yoxla; mövcud dəyişiklikləri silmə və görülmüş işi təkrarlama.
- GitHub girişini `gh auth status` ilə yoxla; məxfi tokeni istəmə və çap etmə.
- Real xidmətlər (`tools/start-local-platform.ps1`/`stop-local-platform.ps1`)
  işə salınmış ola bilər — `netstat -ano | grep :8000` / `:3000` ilə yoxla.

## Cari vəziyyət (ətraflı: `docs/status/CURRENT_STATE.md`)

- **Real production baza (`database/ESAS_PLATFORM.sqlite`) `0009`
  migrasiyasındadır** (əvvəllər `0004`-də donub qalmışdı — istifadəçi
  brauzerdə `HTTP 500` gördü, kök səbəb tapılıb düzəldildi, istifadəçinin
  açıq təsdiqi ilə). Ehtiyat nüsxə `database/backups/`-dadır
  (`.gitignore`-a əlavə edilib). Xam `tick_events`/sessiya sətirlərinə
  toxunulmayıb.
- **Phase 1: STABLE. Phase 2: STABLE. Phase 4: IN PROGRESS** (cari aktiv
  mərhələ). **Phase 9: hələ "DESIGN READY — NOT IMPLEMENTED"** — yalnız
  persistence skeleti tikilib, canlı sistem yoxdur.
- Pattern namizədi işi bu qatlardan ibarətdir:
  1. **Draft generator** — hesablama-zamanı 6 hipotez slotu.
  2. **Persistence/`registered`** — migration `0005`.
  3. **Data-quality bloku** — namizədin ilk backtest cəhdindən əvvəl
     replay sessiyasının keyfiyyət hesabatı yoxlanılır; kritik tapıntı
     varsa `registered → blocked_by_data_quality` (bax aşağıda).
  4. **Backtest v1** — bütün 6 hipotezi əhatə edir, **4/4 baseline
     müqayisəsi ilə tamamlanıb** (no-signal, təsadüfi-zaman, tək-feature,
     əvvəlki namizəd).
  5. **Nəticələndirmə** — `evaluated → accepted_for_shadow | rejected |
     insufficient_evidence`, multiple-testing ailəvi xəta düzəlişi ilə.
  6. **Job-queue** — Phase 2 worker/scheduler mühərriki (mövcud sinxron
     `POST .../backtest` dəyişməz qalıb, job-queue əlavədir).
- **Düzəldilmiş bug (1):** backtest funksiyası əvvəlcə səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, real namizədin `direction`
  sahəsi isə hipotez reyestrindən `"long"/"short"` gəlir. Düzəldilib.
- **Düzəldilmiş bug (2):** `enqueue_job`-da idempotency key hash-i
  `created_by` ilə birlikdə hesablanırdı, ownership qoruması dead code idi.
- **YENİ, HƏLƏ COMMIT EDİLMƏYİB: `blocked_by_data_quality` lifecycle
  vəziyyəti.** `block_pattern_candidate_for_data_quality()`
  (`pattern_candidate_repository.py`, yalnız `registered`-dən əlçatan,
  `ARCHIVABLE_STATES`-ə əlavə edildi). `evaluate_replay_pattern_candidate_backtest`
  indi `create_replay_quality_report()` çağırır (yalnız `registered`
  namizəddə), `critical_count > 0`-dırsa `PatternCandidateBlockedByDataQualityError`
  atır (API `409`). **Frontend TOXUNULUB** — `LIFECYCLE_LABELS`-ə yeni
  etiket, bloklanmış sətirdə backtest düyməsi gizlənir. Backend `375
  passed`, frontend lint/build/`10/10` test təmiz.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var.

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `66f8d51`-ə qədər (job-queue,
  multiple-testing, Phase 9 skeleti, bütün baseline-lar, real DB
  migrasiyası — hamısı push edilib, CI-də yaşıl).
- **Yeni, hələ commit edilməyib:** `blocked_by_data_quality` artımı (kod
  + testlər + sənədlər), yuxarıda təsvir edilib. AGENTS.md qaydasına görə
  commit/push istifadəçinin ayrıca açıq təsdiqini gözləyir. İşçi qovluqda
  `.tmp/` (əvvəlki sessiyanın pytest qalıqları, untracked, əhəmiyyətsiz)
  də qalıb.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi** (heç bir
  real bazaya tətbiq edilmədən, o vaxt). `0006`-`0009` isə adi əlavə
  migrasiyalardır və İNDİ REAL BAZAYA TƏTBİQ EDİLİB (bax yuxarı bölmə).

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində).
- Frontend: `npm run lint` və `npm run test` bu artımda da (blocked_by_data_quality)
  təmiz keçdi — job-queue/multiple-testing/Phase 9/baseline artımları isə
  frontend-ə toxunmadığı üçün ayrıca yoxlanmayıb.
- Canlı brauzerdə vizual yoxlama (2026-08-05, əvvəlki sessiya): Pattern
  namizədi bölməsinin tam dövrü sınandı. 2026-08-06-da real bazanın
  `HTTP 500` problemi istifadəçi ilə birlikdə canlı brauzerdə aşkarlanıb
  düzəldilib.

## Növbəti mərhələ

Seçilməyib. Namizədlər (`docs/status/NEXT_TASK.md`): `invalid_leakage`
son vəziyyəti (Phase 3 leakage/holdout ayrılığına bağlıdır, hazırkı
backtest v1 arxitekturasında train/holdout bölgüsü yoxdur — əvvəlcə
dizayn qərarı lazımdır), Phase 9 sxeminin davamı (yalnız istəsə),
job-queue-nun frontend səthi (yalnız istəsə). İstifadəçinin ayrıca təsdiqi
tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir. Real bazaya (`database/ESAS_PLATFORM.sqlite`) hər hansı
dəyişiklikdən əvvəl ayrıca açıq icazə al.
