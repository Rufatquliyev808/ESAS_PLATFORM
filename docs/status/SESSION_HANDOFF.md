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
- **Phase 1: STABLE. Phase 2: STABLE. Phase 4: namizəd lifecycle-ı əsasən
  tamamlanıb. Phase 3: İN PROGRESS** (cari aktiv mərhələ — indicə
  başlanıb). **Phase 9: hələ "DESIGN READY — NOT IMPLEMENTED"** — yalnız
  persistence skeleti + admin API/frontend tikilib (manifest + event
  reyestri + nəzəri portfolio/risk ledger), canlı qərar generatoru yoxdur.
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
- **Phase 9 SHADOW nəzəri portfolio/risk ledger (section 6)** (commit
  `a502a70`, PUSH EDİLİB, CI yaşıl). `shadow_theoretical_positions`
  (migration `0010`), `shadow_portfolio_repository.py`:
  `open_theoretical_position()` (mövqe-səviyyəli risk limitlərini
  namizədin öz `risk_budget_json`-undan yoxlayır — eyni-vaxtda mövqe sayı,
  simvol+istiqamət konsentrasiyası, ümumi ehtiyat risk; limit keçilirsə
  `SHADOW_RISK_BLOCKED` event-i qeydə alır, mövqe açmır),
  `close_theoretical_position()`, `get_theoretical_portfolio_summary()`.
  **Şüurlu şəkildə kənarda:** gündəlik itki/drawdown (realized PnL zaman
  sırası tələb edir, canlı axın olmadan mənasız).
- **Phase 9 SHADOW admin API + frontend** (commit `c380d08`, PUSH EDİLİB,
  CI yaşıl). İstifadəçinin "çağıranı düzəldək" tələbinə cavab — əvvəlki
  portfolio ledger artımının real çağıranı yox idi, indi var (əl ilə idarə
  olunan admin panel). 12 yeni qorunan endpoint
  (`POST/GET /api/v2/shadow-runs...` — yaratma, siyahı, detal, start/
  complete/halt keçidləri, event qeydiyyatı, mövqə açma/bağlama, portfolio
  xülasəsi). Yeni `backend/app/models/shadow.py` (Pydantic request
  modelləri). Frontend: yeni `shadow-runs-panel.tsx` bölməsi, məcburi
  `NƏZƏRİDİR — REAL ƏMƏLİYYAT YOXDUR` banneri ilə, `dashboard-navigation.tsx`
  və `page.tsx`-ə inteqrasiya olunub. Canlı brauzerdə (birdəfəlik test
  backend/frontend, real bazaya toxunmadan) tam dövr sınandı: run yaradıldı
  → başladıldı → 2 mövqə açıldı → 3-cü mövqə risk limiti ilə düzgün
  bloklandı → mövqə bağlandı → event qeydə alındı → run tamamlandı. Sınaq
  zamanı real bug tapılıb düzəldildi: `openPosition()`-da risk-blok
  xəbərdarlığı `setDetailError(...)`-dan sonra çağırılan `loadDetail()`
  öz növbəsində `detailError`-u sıfırlayırdı, xəbərdarlıq heç görünmürdü —
  çağırış sırası dəyişdirilərək düzəldildi. Backend `404 passed`, frontend
  lint/build/`11/11` test təmiz. Real bazaya toxunulmadı.
- **Phase 3 statistik analiz — pəncərə/resampling təməli + SA-001 gəlir
  seriyası** (commit `7467f95`, PUSH EDİLİB, CI yaşıl). `bars.py`-a
  `S1`/`S10` (1s/10s) pəncərələri (`BAR_BUILDER_VERSION 1.1.0`), yeni
  `return_series.py` (`compute_return_series()` — pəncərə-daxili
  log-return, tək-tick pəncərə return yaratmır, `insufficient_data` həddi),
  yeni `statistical_analysis.py` (orkestrasiya, dataset-drift qorumalı),
  yeni qorunan `GET .../statistical-analysis` endpoint-i.
- **Phase 3 SA-002 — pəncərə volatilitesi** (commit `1173d53`, PUSH
  EDİLİB, CI yaşıl). SA-001-in birbaşa davamı. Yeni `volatility.py`
  (`compute_volatility()` — artıq qurulmuş `return_series`-i və bar-ları
  girişi kimi qəbul edir, təkrar hesablama yoxdur):
  `window_range_absolute`/`window_range_relative` (`high-low`, bütün
  bar-lar, tək-tick pəncərələr də daxildir), `window_log_return_abs`
  (yalnız return-eligible pəncərələr), `robust_mad`. **Tick-to-tick return
  std-i qəsdən kənarda saxlanıldı** — yeni xam-tick keçidi tələb edir
  (hazırkı bütün analiz modulları yalnız artıq qurulmuş bar-lar üzərində
  işləyir), ayrıca kiçik artım kimi planlaşdırılıb.
  `minimum_window_returns` orkestrasiya qatında ümumi
  `minimum_sample_size`-a çevrildi. `STATISTICAL_ANALYSIS_API_VERSION
  1.0.0 → 1.1.0`.
- **YENİ, HƏLƏ COMMIT EDİLMƏYİB: Əsas ekrana canlı indikator konsensusu
  paneli.** İstifadəçi TradingView-un "Texniki analiz" widget-inə (Al/Sat
  konsensus gauge-ları) bənzər bir görünüş istədi; iki seçim təklif
  edildi (TradingView widget-ini gömmək / öz hesablamamızı qurmaq) —
  istifadəçi öz hesablamamızı seçdi. **Vacib:** "Al/Sat" dili platformanın
  "yalnız tədqiqat" prinsipinə zidd olduğu üçün "Yuxarı meyl/Aşağı
  meyl/Neytral" etiketləməsi seçildi, "TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT
  TÖVSİYƏSİ DEYİL" banneri ilə. **Arxitektur fərqi:** bu, sessiyada
  indiyədək tikilmiş hər şeydən fərqli — əvvəlki analiz modulları
  `completed` replay sessiyalarının sabit snapshot-u üzərində işləyirdi,
  bu isə ilk dəfə **canlı, dəyişən** pəncərə üzərində (replay sessiyası
  TƏLƏB ETMİR) işləyir. Yeni `indicator_consensus.py` (RSI+EMA-dan
  Bullish/Bearish/Neytral təsnifatı — TradingView-un 16 göstəricisinə
  qarşı qəsdən 2, `indicators.py`-a toxunmadan), yeni `live_analysis.py`
  (`create_live_technical_summary()`, `lineage.reproducible: false`), yeni
  `GET /api/v2/live-technical-summary` endpoint-i, yeni
  `live-technical-summary-panel.tsx` ("Nəticələr" əsas ekranında, mövcud
  5s polling konvensiyası ilə). Canlı brauzerdə tam sınandı (sintetik GOLD
  tick-ləri, birdəfəlik test backend/frontend, real bazaya toxunmadan) —
  düzgün RSI/EMA/konsensus nəticələri göstərildi. Backend `435 passed`,
  frontend lint/build/`12/12` test təmiz.
- Frontend: sol menyulu, bölmə əsaslı iş sahəsi. "Pattern namizədləri"
  bölməsində draft kartlar + qeydiyyat + arxivləşdirmə + backtest (v1) +
  nəticələndirmə var. "Nəticələr" (defolt) bölməsində indi canlı indikator
  konsensusu paneli də var.

## Commit/push vəziyyəti

- `main` origin ilə sinxrondur `1173d53`-ə qədər (job-queue,
  multiple-testing, Phase 9 manifest/event skeleti, bütün baseline-lar,
  real DB migrasiyası, `blocked_by_data_quality`, `invalid_leakage`, Phase 9
  portfolio ledger, Phase 9 admin API + frontend, Phase 3 SA-001 gəlir
  seriyası, Phase 3 SA-002 volatilite — hamısı push edilib, CI-də yaşıl).
- **Yeni, hələ commit edilməyib:** Əsas ekranın canlı indikator konsensusu
  paneli artımı (kod + testlər + sənədlər), yuxarıda təsvir edilib.
  AGENTS.md qaydasına görə commit/push istifadəçinin ayrıca açıq
  təsdiqini gözləyir. İşçi qovluqda `.tmp/` (əvvəlki sessiyanın pytest
  qalıqları, untracked, əhəmiyyətsiz) də qalıb.
- `0005` migrasiyası əvvəlki sessiyada bir dəfə **amend edildi**. `0006`-
  `0009` real bazaya tətbiq edilib. `0010` (bu artımın portfolio ledger
  cədvəli) yalnız kodda/test bazalarında mövcuddur, real bazaya tətbiq
  edilməyib (real çağıran yoxdur, ehtiyac yarandıqda ayrıca icazə tələb
  olunur).

## Yoxlama vəziyyəti

- Backend: `.venv/Scripts/python -m pytest tests/backend -q` — bu maşında
  `pytest-of-user` temp qovluğuna icazə xətası var; `--basetemp` ilə başqa
  qovluq göstərmək lazımdır (məs. scratchpad daxilində). Bu artımla `435
  passed`.
- Frontend: bu artımda (canlı indikator konsensusu paneli) lint təmiz,
  `12/12` test, production build uğurlu.
- Canlı brauzerdə vizual yoxlama (2026-08-05, əvvəlki sessiya): Pattern
  namizədi bölməsinin tam dövrü sınandı. 2026-08-06-da real bazanın
  `HTTP 500` problemi istifadəçi ilə birlikdə canlı brauzerdə aşkarlanıb
  düzəldilib; eyni gün Phase 9 admin panelinin tam dövrü də (birdəfəlik
  test backend/frontend ilə, real bazaya toxunmadan) canlı brauzerdə
  sınanıb, bir real bug tapılıb düzəldilib. Yenə eyni gün, əsas ekranın
  yeni canlı indikator konsensusu paneli (sintetik GOLD tick-ləri,
  birdəfəlik test backend/frontend ilə) canlı brauzerdə sınanıb — düzgün
  RSI/EMA/konsensus nəticələri göstərilib. Sınaq zamanı avtomatlaşdırılmış
  brauzer mühitinin `document.visibilityState`-i "hidden" olduğu üçün
  (əvvəlki sessiyalarda da qeyd edilib) müvəqqəti override ilə tək təmiz
  refresh tetiklənib; override-i silmədən saxlamaq test alətinin öz daxili
  compositing yoxlamaları ilə toqquşaraq sürətli sorğu axınına səbəb oldu
  (YALNIZ test artefaktı — köhnə `/status/operational` pollingi də eyni
  cür təsirləndi, tətbiq kodunda problem yox idi; override silinən kimi
  dərhal dayandı). Real production backend/frontend (8000/3000) sınaq
  boyu toxunulmadan işlədi.

## Növbəti mərhələ

Seçilməyib. Phase 3-ün SA-001 (gəlir seriyası) və SA-002 (pəncərə
volatilitesi) tamamlandı, əsas ekrana canlı indikator konsensusu paneli
əlavə edildi. Namizədlər (`docs/status/NEXT_TASK.md`): SA-002-nin qalan
hissəsi (tick-to-tick return std-i), SA-003-SA-007 (spread, tick sürəti,
tick-volume, sessiya, rejim), canlı konsensusun daha çox indikatorla
genişləndirilməsi, Phase 9-un qalan bölmələri (istəsə), job-queue-nun
frontend səthi (istəsə). İstifadəçinin ayrıca təsdiqi tələb olunur.

## Təhlükəsizlik

Platforma araşdırma/monitorinq rejimindədir. Açıq istifadəçi təsdiqi olmadan
real ticarət aktivləşdirilməməlidir. Push yalnız istifadəçi ayrıca tələb
etdikdə edilməlidir. Real bazaya (`database/ESAS_PLATFORM.sqlite`) hər hansı
dəyişiklikdən əvvəl ayrıca açıq icazə al.
