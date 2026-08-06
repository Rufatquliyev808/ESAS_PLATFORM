# ESAS Platform — Növbəti tapşırıq

Status: BLOCKED — növbəti addım seçilməyib, istifadəçi təsdiqi tələb olunur
Prioritet: —
Mərhələ: Phase 4-ün qalan maddələri

## Tamamlanan (bu sessiya)

- `Causal FVG detektoru 1.0.0` (commit `1aa85c8`).
- Sidebar render-zamanı mutasiya lint düzəlişi (commit `7d49f97`).
- Draft pattern namizədi generatoru — 6 hipotez (commit `0a0f2d2`).
- Faza 2 rəsmi olaraq `STABLE` elan edildi (`docs/releases/PHASE_2_STABLE.md`).
- Pattern namizədi persistence/`registered` qatı (commit `14345fd`).
- Pattern namizədi backtest v1 — indi bütün 6 hipotezi əhatə edir.
- `evaluated → accepted_for_shadow | rejected | insufficient_evidence`
  keçidi əlavə edildi.
- Pattern namizədi bölməsinin tam dövrü canlı brauzerdə vizual təsdiqləndi.
- **Phase 2 worker/scheduler müqaviləsi** (commit `4739854`, push edilib, CI yaşıl).
- **Multiple-testing reyestri** (commit `76e2e13`, push edilib, CI yaşıl).
- **Phase 9 SHADOW: run manifest + append-only event reyestri skeleti**
  (commit `404922a`, push edilib, CI yaşıl). Canlı sistem deyil.
- **Random-timing baseline müqayisəsi** (commit `6b5b210`, push edilib, CI yaşıl).
- **Tək-feature qaydası + əvvəlki qəbul edilmiş namizəd baseline-ları**
  (commit `4c8b2fa`, push edilib, CI yaşıl) — Phase 3/4-ün 4 baseline
  tələbi tam tətbiq olundu.
- **Real production baza `0005`-`0009` migrasiyalarına köçürüldü**
  (commit `66f8d51`, push edilib, CI yaşıl) — əvvəllər `0004`-də donub
  qalmışdı, "Qeydə alınmış namizədlər" siyahısı `HTTP 500` verirdi. Ehtiyat
  nüsxə götürüldü, doğrulandı, tətbiq edildi.
- **`blocked_by_data_quality` lifecycle vəziyyəti tətbiq edildi** (commit
  `4e46f0f`, push edilib, CI yaşıl) — namizədin ilk backtest cəhdindən
  əvvəl replay sessiyasının keyfiyyət hesabatı yoxlanılır; `critical_count
  > 0`-dırsa namizəd `evaluated`-ə deyil, `blocked_by_data_quality`-yə
  keçir (API `409`).
- **`invalid_leakage` lifecycle vəziyyəti tətbiq edildi** (commit
  `2753fcc`, push edilib, CI yaşıl) — backtest v1-ə üst-üstə düşən tarixi
  hadisələr üçün purge/embargo əlavə edildi (bütün namizədlər üçün,
  statistik doğruluğu artırır); əgər xam siqnal kifayət idi (`≥30`) amma
  purge onu `30`-dan aşağı salıbsa, namizəd `insufficient_evidence`-ə
  deyil `invalid_leakage`-ə keçir.
- **Phase 9 SHADOW: nəzəri portfolio/risk ledger (section 6)** (commit
  `a502a70`, push edilib, CI yaşıl) — `shadow_theoretical_positions`
  cədvəli (migration `0010`), mövqe-səviyyəli risk limitləri. Gündəlik
  itki/drawdown şüurlu şəkildə kənarda saxlanılıb.
- **Phase 9 SHADOW-a admin API + frontend əlavə edildi** (hələ commit
  edilməyib) — istifadəçinin "çağıranı düzəldək" tələbinə cavab: 12 yeni
  qorunan endpoint (`/api/v2/shadow-runs...`) + yeni `shadow-runs-panel.tsx`
  bölməsi (NƏZƏRİDİR banneri ilə). Canlı brauzerdə real qərar generatoru
  olmadan (əl ilə, admin kimi) tam sınandı: run yaradıldı → başladıldı →
  risk limiti ilə mövqə düzgün bloklandı → mövqə bağlandı → event qeydə
  alındı → tamamlandı. Sınaq zamanı real bug tapılıb düzəldildi (risk-blok
  xəbərdarlığı `loadDetail()`-un öz sıfırlanması ilə görünmədən itirdi).
  Backend `404 passed`, frontend lint/build/`11/11` test təmiz. Real
  bazaya toxunulmadı.

Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 3/4, `PROJECT_ROADMAP.md`-dən)

- Baseline müqayisəsi tamamlandı (4/4).
- `blocked_by_data_quality` tamamlandı.
- `invalid_leakage` tamamlandı (purge/embargo əsaslı).
- Backtest v1-in son vəziyyət maşını indi tamdır: `draft → registered →
  evaluated → accepted_for_shadow | rejected | insufficient_evidence |
  invalid_leakage | blocked_by_data_quality → archived`.
- Phase 9: manifest + event + portfolio skeleti VƏ admin API/frontend
  tamamlandı. Real bazaya migration `0010` hələ tətbiq edilməyib (ayrıca
  icazə tələb olunacaq, real istifadəyə başlanmaq istənsə). Qalan
  bölmələr (champion/challenger müqayisə mühərriki section 7,
  kəsinti/restart section 8) — yalnız istifadəçi ayrıca istəsə, çünki hələ
  real qərar generatoru (Phase 5-8) yoxdur.
- Job-queue-nun frontend səthi — yalnız istifadəçi ayrıca istəsə.

## Vizual yoxlama qeydi

Tamamlandı (2026-08-05): Pattern namizədi bölməsinin tam dövrü canlı
brauzerdə uğurla yoxlanıldı; heç bir konsol xətası olmadı. Real bazaya
toxunulmadı. Ətraflı: `docs/status/CURRENT_STATE.md`.

2026-08-06: real production bazanın `0005`-`0009` migrasiyaları istifadəçi
ilə birlikdə canlı brauzerdə aşkarlanan `HTTP 500` xətasından yola çıxaraq
tətbiq edildi və doğrulandı. Eyni gün, Phase 9 admin panelinin tam dövrü
də (real bazaya toxunmadan, birdəfəlik test backend/frontend ilə) canlı
brauzerdə sınandı.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti addım olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
