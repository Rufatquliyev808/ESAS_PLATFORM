# ESAS Platform — Sessiya handoff

Son yenilənmə: 2026-08-05

## Başlanğıc

- Əsas layihə: `D:\ESAS_PLATFORM`
- `AGENTS.md` sənədindəki oxuma sırasını tam icra et.
- Git statusunu, branch-i və son commitləri yoxla; mövcud dəyişiklikləri silmə və görülmüş işi təkrarlama.
- GitHub girişini `gh auth status` ilə yoxla; məxfi tokeni istəmə və çap etmə.

## Cari vəziyyət (ətraflı: `docs/status/CURRENT_STATE.md`)

- **Phase 1: STABLE.** **Phase 2 (Replay və məlumat keyfiyyəti): STABLE**
  (`docs/releases/PHASE_2_STABLE.md`, 2026-08-05, 2026-08-04 tarixli real
  qəbul sınağına əsaslanır). **Phase 4: IN PROGRESS** (cari aktiv mərhələ).
- Phase 4-də tamamlanan detektorlar: bazar strukturu, likvidlik süpürməsi,
  BOS/CHoCH, retest, Fair Value Gap — hamısı causal/no-lookahead, frontend-də
  ayrıca kartlar.
- Pattern namizədi işi iki qatda var:
  1. **Draft generator** — mövcud detektorları 6 hipotezə (`pattern_hypothesis_registry`)
     bağlayıb hesablama-zamanı slot yaradır (`backend/app/strategies/pattern_candidate.py`,
     `GET /api/v2/replay-sessions/{id}/pattern-candidates`).
  2. **Persistence/`registered` qatı** — `candidate_confirmed` slotları
     dəyişməz qeyd edir (`pattern_candidate_repository.py`,
     `0005_pattern_candidates.sql`, `POST/GET/GET{id}/archive
     /api/v2/pattern-candidates`). Yalnız `registered`/`archived`
     vəziyyətləri var; `running`/`evaluated`/`accepted_for_shadow`/`rejected`
     backtest mühərriki olmadan qəsdən tətbiq edilməyib.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi (`dashboard-navigation.tsx`).
  Hər bölmə GOLD-a mümkün təsirin sadə izahını göstərir. "Pattern namizədləri"
  bölməsində indi həm draft kartlar, həm qeydiyyat düyməsi, həm də qeydə
  alınmış namizədlər cədvəli (arxivləşdirmə daxil) var.
- Backend `262 passed`, frontend production build və `10/10` test, lint təmiz
  (bax "Yoxlama vəziyyəti").

## Commit/push vəziyyəti

- `main` origin-ə sinxrondur, ta ki bu sessiyanın son işi (pattern namizədi
  persistence qatı) commit/push edilənə qədər — sənədin bu versiyası yazılan
  anda hələ commit edilməyib, tamamlanma qeydlərinə bax.
- Son push edilmiş commit-lər (xronoloji): `1aa85c8` (FVG) → `7d49f97`
  (sidebar lint) → `0a0f2d2` (draft pattern namizədi) → `847249b` (Phase 2
  Stable). Hamısı CI-də yaşıl idi.
- Diqqət: istifadəçi bir dəfə eyni lint düzəlişini paralel bir fon
  sessiyasında da (`task_b2a032b5`) başlatmışdı. Növbəti sessiya `git fetch`/
  `git log origin/main` ilə gözlənilməz commit olub-olmadığını yoxlamalıdır.

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — `262 passed`
  (bu maşında `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp`
  ilə başqa qovluq göstərmək lazımdır, məs. scratchpad daxilində).
- Frontend: `npm run lint` və `npm run test` (build + `10/10` test) təmiz.
- Canlı brauzerdə vizual yoxlama edilməyib (bu maşındakı naməlum xarici
  mühit məhdudiyyətinə görə, əvvəlki sessiyalardan bəri davam edir). Bütün
  frontend işi yalnız avtomatlaşdırılmış test/build ilə təsdiqlənib.

## Növbəti mərhələ

Seçilməyib. Namizədlər (`docs/status/NEXT_TASK.md`): backtesting (pattern
namizədini `registered`-dən `running`/`evaluated`-ə aparan məntiqi növbəti
addım), uğursuz eksperimentlərin arxivləşdirilməsi, SHADOW hazırlığı.
İstifadəçinin ayrıca təsdiqi tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir.
