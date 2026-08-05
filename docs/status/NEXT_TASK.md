# ESAS Platform — Növbəti tapşırıq

Status: BLOCKED — növbəti mərhələ seçilməyib, istifadəçi təsdiqi tələb olunur
Prioritet: —
Mərhələ: Phase 4-ün qalan maddələri

## Tamamlanan

`Causal FVG detektoru 1.0.0` tamamlandı (backend + frontend, `243` backend testi,
frontend build və `9/9` test). Ətraflı: `docs/status/CURRENT_STATE.md`.

## Namizəd növbəti addımlar (Phase 4, `PROJECT_ROADMAP.md`-dən)

- Pattern namizədlərinin yaradılması
- Backtesting
- Uğursuz eksperimentlərin arxivləşdirilməsi
- SHADOW mərhələsi üçün hazırlıq

## Ayrıca (FVG-dən asılı olmayan, kiçik) düzəliş namizədi

`frontend/app/dashboard-navigation.tsx`-də `eslint-plugin-react-hooks 7.x`-in
yeni `react-hooks/immutability` qaydası `previousGroup` reassignment-ə görə
lint xətası verir (əvvəldən mövcud kod, FVG işi ilə əlaqəsi yoxdur). CI-də
`npm run lint` bunu bloklayır.

## Başlama şərti

Yuxarıdakı namizədlərdən hansının növbəti mərhələ olacağı istifadəçinin ayrıca
təsdiqindən sonra müəyyənləşdiriləcək.
