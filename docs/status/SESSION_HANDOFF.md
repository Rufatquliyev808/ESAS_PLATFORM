# ESAS Platform — Sessiya handoff

Son yenilənmə: 2026-08-05

## Başlanğıc

- Əsas layihə: `D:\ESAS_PLATFORM`
- `AGENTS.md` sənədindəki oxuma sırasını tam icra et.
- Git statusunu, branch-i və son commitləri yoxla; mövcud dəyişiklikləri silmə və görülmüş işi təkrarlama.
- GitHub girişini `gh auth status` ilə yoxla; məxfi tokeni istəmə və çap etmə.

## Cari vəziyyət (ətraflı: `docs/status/CURRENT_STATE.md`)

- **Phase 1: STABLE. Phase 2 (Replay və məlumat keyfiyyəti): STABLE**
  (`docs/releases/PHASE_2_STABLE.md`). **Phase 4: IN PROGRESS** (cari aktiv
  mərhələ).
- Phase 4 detektorları (hamısı causal/no-lookahead, frontend-də ayrıca
  kartlar): bazar strukturu, likvidlik süpürməsi, BOS/CHoCH, retest, FVG.
- Pattern namizədi işi üç qatdan ibarətdir:
  1. **Draft generator** — hesablama-zamanı 6 hipotez slotu
     (`pattern_candidate.py`, `GET .../pattern-candidates`).
  2. **Persistence/`registered`** — `candidate_confirmed` slotları dəyişməz
     qeyd edir (`pattern_candidate_repository.py`, migration `0005`,
     `POST/GET/GET{id}/archive`).
  3. **Backtest v1** — İNDİ BÜTÜN 6 HİPOTEZİ ƏHATƏ EDİR
     (`structure_break_*`, `liquidity_sweep_reclaim_*`,
     `market_structure_*`). `market_structure` üçün "tarixi hadisə" =
     rejimin `confirmed_structure`-a keçdiyi an (transition-based, davam
     edən rejimin sonrakı pivotları təkrar hadisə yaratmır — üst-üstə
     düşən nümunələrin qarşısını almaq üçün). Tarixi hadisə skanı, horizon
     nəticəsi, xərc ssenariləri, statistik etibarlılıq
     (`pattern_candidate_backtest.py`, migration `0006`,
     `POST/GET .../{id}/backtest`). Uğurlu ilk backtest `registered →
     evaluated` keçirir.
- **Düzəldilmiş bug:** backtest funksiyası əvvəlcə səhvən `direction`
  parametrini `"bullish"/"bearish"` gözləyirdi, real namizədin `direction`
  sahəsi isə hipotez reyestrindən `"long"/"short"` gəlir — bu, real axında
  backtest-i həmişə uğursuz edərdi. İndi istiqamət yalnız `hypothesis_id`-dən
  təyin olunur.
- Vəziyyət maşınının qalanı (`running` async icra, `accepted_for_shadow`,
  `rejected`, `blocked_by_data_quality`, `invalid_leakage`,
  `insufficient_evidence`, `failed`, `cancelled`) DB CHECK-də icazəlidir
  (əvvəlcədən genişləndirilib), amma tətbiq məntiqi hələ yoxdur.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) var.
- Backend `286 passed`, frontend production build və `10/10` test, lint təmiz.

## Commit/push vəziyyəti

- Bu sənədin yazıldığı anda son artım (market_structure tarixi hadisələri,
  backtest 6/6 hipotez) hələ commit/push edilməyib — əvvəlki 6 addım
  (`1aa85c8` → `7d49f97` → `0a0f2d2` → `847249b` → `14345fd` → `73bf580` →
  `90133ac`) artıq push edilib və CI-də yaşıl idi.
- Diqqət: istifadəçi bir dəfə eyni lint düzəlişini paralel bir fon
  sessiyasında da (`task_b2a032b5`) başlatmışdı. Növbəti sessiya `git fetch`/
  `git log origin/main` ilə gözlənilməz commit olub-olmadığını yoxlamalıdır.
- `0005` migrasiyası bu sessiyada bir dəfə **amend edildi** (heç bir real
  bazaya tətbiq edilmədən) ki, `lifecycle_state` CHECK-i başdan tam
  müqavilə lüğətini əhatə etsin — SQLite-də CHECK genişləndirmək DROP tələb
  edir, migration runner isə DROP-u təhlükəsizlik naminə bloklayır. Əgər
  başqa migrasiya artıq tətbiq edilibsə, bu barədə diqqətli ol.

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində).
- Frontend: `npm run lint` və `npm run test` (build + testlər) təmiz.
- Canlı brauzerdə vizual yoxlama edilməyib (bu maşındakı naməlum xarici
  mühit məhdudiyyətinə görə, əvvəlki sessiyalardan bəri davam edir). Bütün
  frontend işi yalnız avtomatlaşdırılmış test/build ilə təsdiqlənib.

## Növbəti mərhələ

Seçilməyib. Backtest v1 bütün 6 hipotezi əhatə edir, hazır. Namizədlər
(`docs/status/NEXT_TASK.md`): vəziyyət maşınının qalanı (`running`,
`accepted_for_shadow`, `rejected` və s.), multiple-testing reyestri, SHADOW
hazırlığı. İstifadəçinin ayrıca təsdiqi tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir.
