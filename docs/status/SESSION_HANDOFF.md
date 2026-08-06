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
     varsa `registered → blocked_by_data_quality`.
  4. **Backtest v1** — bütün 6 hipotezi əhatə edir, **4/4 baseline
     müqayisəsi ilə tamamlanıb** (no-signal, təsadüfi-zaman, tək-feature,
     əvvəlki namizəd), **İNDİ ÜST-ÜSTƏ DÜŞƏN HADİSƏLƏR ÜÇÜN PURGE/EMBARGO
     İLƏ** (bax aşağıda).
  5. **Nəticələndirmə** — `evaluated → accepted_for_shadow | rejected |
     insufficient_evidence | invalid_leakage`, multiple-testing ailəvi
     xəta düzəlişi ilə.
  6. **Job-queue** — Phase 2 worker/scheduler mühərriki (mövcud sinxron
     `POST .../backtest` dəyişməz qalıb, job-queue əlavədir).
  Vəziyyət maşını indi tamdır: `draft → registered → evaluated →
  accepted_for_shadow | rejected | insufficient_evidence | invalid_leakage
  | blocked_by_data_quality → archived`.
- **Düzəldilmiş bug (1):** backtest funksiyası əvvəlcə səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, real namizədin `direction`
  sahəsi isə hipotez reyestrindən `"long"/"short"` gəlir. Düzəldilib.
- **Düzəldilmiş bug (2):** `enqueue_job`-da idempotency key hash-i
  `created_by` ilə birlikdə hesablanırdı, ownership qoruması dead code idi.
- **`blocked_by_data_quality` lifecycle vəziyyəti** (commit `4e46f0f`, PUSH
  EDİLİB, CI yaşıl) — `block_pattern_candidate_for_data_quality()`, yalnız
  `registered`-dən əlçatan. Frontend toxunulub (etiket + gizli düymə).
- **YENİ, HƏLƏ COMMIT EDİLMƏYİB: `invalid_leakage` lifecycle vəziyyəti.**
  Real, əvvəllər qorunmayan boşluq: backtest v1 üst-üstə düşən tarixi
  hadisələri (eyni `[giriş, giriş+horizon_bars)` pəncərəsinə düşənləri)
  müstəqil nümunə sayırdı, effektiv sample/CI-ni süni şişirdirdi.
  `_purge_overlapping_events()` (`pattern_candidate_backtest.py`) BÜTÜN
  namizədlər üçün tətbiq olunur (embargo, xronoloji). Əgər xam siqnal
  kifayət idi (`≥30`) amma purge onu `30`-dan aşağı salıbsa →
  `invalid_leakage` (`insufficient_evidence`-dən fərqli: birincisi "sübut
  üst-üstə düşmə ilə şişirdilib", ikincisi "hələ kifayət qədər hadisə
  yoxdur"). `PatternCandidateBacktest`-ə `raw_event_count`/
  `discarded_for_overlap` sahələri, `CLASSIFICATION_OUTCOMES`/
  `ARCHIVABLE_STATES`-ə `invalid_leakage` əlavə edildi. `BACKTEST_VERSION
  1.5.0`. Frontend: yeni etiket. Backend `381 passed`, frontend
  lint/build/`10/10` test təmiz. **Real causal leakage artıq hər detektorda
  struktur olaraq qarşısı alınıb (no-lookahead) — bu, əlavə edilə bilən
  YEGANƏ real, boş olmayan leakage-adjacent qorunma idi.**
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var.

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `4e46f0f`-ə qədər (job-queue,
  multiple-testing, Phase 9 skeleti, bütün baseline-lar, real DB
  migrasiyası, `blocked_by_data_quality` — hamısı push edilib, CI-də
  yaşıl).
- **Yeni, hələ commit edilməyib:** `invalid_leakage` artımı (kod + testlər
  + sənədlər), yuxarıda təsvir edilib. AGENTS.md qaydasına görə commit/push
  istifadəçinin ayrıca açıq təsdiqini gözləyir. İşçi qovluqda `.tmp/`
  (əvvəlki sessiyanın pytest qalıqları, untracked, əhəmiyyətsiz) də qalıb.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi**. `0006`-
  `0009` isə real bazaya tətbiq edilib. Bu artımda yeni migration yoxdur.

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində).
- Frontend: `npm run lint` və `npm run test` `blocked_by_data_quality` VƏ
  `invalid_leakage` artımlarında təmiz keçdi (hər ikisi frontend-ə
  toxunub).
- Canlı brauzerdə vizual yoxlama (2026-08-05, əvvəlki sessiya): Pattern
  namizədi bölməsinin tam dövrü sınandı. 2026-08-06-da real bazanın
  `HTTP 500` problemi istifadəçi ilə birlikdə canlı brauzerdə aşkarlanıb
  düzəldilib.

## Növbəti mərhələ

İstifadəçi ilə razılaşdırılıb: **Phase 9 sxeminin davamı** (nəzəri
portfolio/risk cədvəlləri, section 6, eyni skelet formatında — hələ real
çağıranı yoxdur, Phase 5-8 yoxdur). Namizədlər (`docs/status/NEXT_TASK.md`):
job-queue-nun frontend səthi (yalnız istəsə).

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir. Real bazaya (`database/ESAS_PLATFORM.sqlite`) hər hansı
dəyişiklikdən əvvəl ayrıca açıq icazə al.
