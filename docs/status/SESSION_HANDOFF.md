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

- **Real production baza (`database/ESAS_PLATFORM.sqlite`) hazırda `0009`
  migrasiyasındadır** (əvvəllər `0004`-də donub qalmışdı — istifadəçi
  brauzerdə `HTTP 500` gördü, kök səbəb tapılıb düzəldildi, istifadəçinin
  açıq təsdiqi ilə). Ehtiyat nüsxə `database/backups/`-dadır
  (`.gitignore`-a əlavə edilib). Xam `tick_events`/sessiya sətirlərinə
  toxunulmayıb. **`0010` (bu sessiyanın Phase 9 portfolio ledger artımı)
  yalnız test bazalarında sınanıb — real bazaya HƏLƏ TƏTBİQ EDİLMƏYİB**,
  çünki heç bir real çağıran yoxdur (bu, canlı SHADOW sisteminin bir
  hissəsi deyil, yalnız gələcək üçün skelet). Real bazaya tətbiq lazım
  olduqda ayrıca icazə tələb olunacaq.
- **Phase 1: STABLE. Phase 2: STABLE. Phase 4: IN PROGRESS** (cari aktiv
  mərhələ). **Phase 9: hələ "DESIGN READY — NOT IMPLEMENTED"** — yalnız
  persistence skeleti tikilib (manifest + event reyestri + nəzəri
  portfolio/risk ledger), canlı sistem yoxdur.
- Pattern namizədi işi bu qatlardan ibarətdir:
  1. **Draft generator** — hesablama-zamanı 6 hipotez slotu.
  2. **Persistence/`registered`** — migration `0005`.
  3. **Data-quality bloku** — namizədin ilk backtest cəhdindən əvvəl
     replay sessiyasının keyfiyyət hesabatı yoxlanılır; kritik tapıntı
     varsa `registered → blocked_by_data_quality`.
  4. **Backtest v1** — bütün 6 hipotezi əhatə edir, 4/4 baseline
     müqayisəsi ilə tamamlanıb, üst-üstə düşən hadisələr üçün
     purge/embargo ilə.
  5. **Nəticələndirmə** — `evaluated → accepted_for_shadow | rejected |
     insufficient_evidence | invalid_leakage`, multiple-testing ailəvi
     xəta düzəlişi ilə.
  6. **Job-queue** — Phase 2 worker/scheduler mühərriki (mövcud sinxron
     `POST .../backtest` dəyişməz qalıb, job-queue əlavədir).
  Vəziyyət maşını tamdır: `draft → registered → evaluated →
  accepted_for_shadow | rejected | insufficient_evidence | invalid_leakage
  | blocked_by_data_quality → archived`.
- **Düzəldilmiş bug (1):** backtest funksiyası əvvəlcə səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, real namizədin `direction`
  sahəsi isə hipotez reyestrindən `"long"/"short"` gəlir. Düzəldilib.
- **Düzəldilmiş bug (2):** `enqueue_job`-da idempotency key hash-i
  `created_by` ilə birlikdə hesablanırdı, ownership qoruması dead code idi.
- **`blocked_by_data_quality` lifecycle vəziyyəti** (commit `4e46f0f`, PUSH
  EDİLİB, CI yaşıl).
- **`invalid_leakage` lifecycle vəziyyəti** (commit `2753fcc`, PUSH EDİLİB,
  CI yaşıl) — backtest v1-ə üst-üstə düşən tarixi hadisələr üçün
  purge/embargo (`_purge_overlapping_events()`, bütün namizədlər üçün
  tətbiq olunur). Xam siqnal kifayət idisə (`≥30`) amma purge onu aşağı
  salıbsa → `invalid_leakage`. `BACKTEST_VERSION 1.5.0`.
- **YENİ, HƏLƏ COMMIT EDİLMƏYİB: Phase 9 SHADOW nəzəri portfolio/risk
  ledger (section 6).** `shadow_theoretical_positions` (migration `0010`),
  `shadow_portfolio_repository.py`:
  `open_theoretical_position()` (mövqe-səviyyəli risk limitlərini
  namizədin öz `risk_budget_json`-undan yoxlayır — eyni-vaxtda mövqe sayı,
  simvol+istiqamət konsentrasiyası, ümumi ehtiyat risk; limit keçilirsə
  `SHADOW_RISK_BLOCKED` event-i qeydə alır, mövqe açmır),
  `close_theoretical_position()`, `get_theoretical_portfolio_summary()`.
  **Şüurlu şəkildə kənarda:** gündəlik itki/drawdown (realized PnL zaman
  sırası tələb edir, canlı axın olmadan mənasız). **Hələ də canlı sistem
  deyil** — API/frontend yoxdur (real çağıran yoxdur, əvvəlki skelet
  artımı ilə eyni səbəb). Backend `391 passed`.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var.

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `2753fcc`-ə qədər (job-queue,
  multiple-testing, Phase 9 manifest/event skeleti, bütün baseline-lar,
  real DB migrasiyası, `blocked_by_data_quality`, `invalid_leakage` —
  hamısı push edilib, CI-də yaşıl).
- **Yeni, hələ commit edilməyib:** Phase 9 nəzəri portfolio/risk ledger
  artımı (kod + testlər + sənədlər), yuxarıda təsvir edilib. AGENTS.md
  qaydasına görə commit/push istifadəçinin ayrıca açıq təsdiqini gözləyir.
  İşçi qovluqda `.tmp/` (əvvəlki sessiyanın pytest qalıqları, untracked,
  əhəmiyyətsiz) də qalıb.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi**. `0006`-
  `0009` real bazaya tətbiq edilib. `0010` (bu artımın portfolio ledger
  cədvəli) yalnız kodda/test bazalarında mövcuddur, real bazaya tətbiq
  edilməyib (real çağıran yoxdur, ehtiyac yarandıqda ayrıca icazə tələb
  olunur).

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində).
- Frontend: bu artımda (Phase 9 portfolio ledger) toxunulmayıb — API/UI
  yoxdur, ona görə ayrıca frontend sınağı aparılmadı.
  `blocked_by_data_quality`/`invalid_leakage` artımlarında frontend
  lint/build/`10/10` test təmiz keçmişdi.
- Canlı brauzerdə vizual yoxlama (2026-08-05, əvvəlki sessiya): Pattern
  namizədi bölməsinin tam dövrü sınandı. 2026-08-06-da real bazanın
  `HTTP 500` problemi istifadəçi ilə birlikdə canlı brauzerdə aşkarlanıb
  düzəldilib.

## Növbəti mərhələ

Seçilməyib. Phase 9-un manifest/event/portfolio skeleti tamdır (section
3, 6, 9). Qalan bölmələr (section 7 champion/challenger müqayisə
mühərriki, section 8 kəsinti/restart) — real çağıranı hələ yoxdur.
Namizədlər (`docs/status/NEXT_TASK.md`): Phase 9-un davamı (istəsə),
job-queue-nun frontend səthi (istəsə). İstifadəçinin ayrıca təsdiqi tələb
olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir. Real bazaya (`database/ESAS_PLATFORM.sqlite`) hər hansı
dəyişiklikdən əvvəl ayrıca açıq icazə al.
