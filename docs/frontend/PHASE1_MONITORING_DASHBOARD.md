# Phase 1 monitorinq panelinin spesifikasiyası

Versiya: 1.0

Tarix: 2026-07-30

Status: Tətbiq edilib

## Məqsəd

Panel texniki biliyi olmayan istifadəçiyə dörd suala tez cavab verir:

1. Bazar məlumatı hazırda gəlirmi?
2. MT5 Bridge məlumatı təhlükəsiz çatdırırmı?
3. Disk növbəsində gözləyən event varmı?
4. Hər hansı event rədd edilibmi?

Panel ticarət siqnalı, proqnoz və order idarəetməsi vermir.

## Məlumat mənbələri

Frontend yalnız aşağıdakı backend API-lərindən istifadə edir:

- `GET /status/operational`
- `GET /statistics/ticks`

Brauzer SQLite bazasına birbaşa qoşulmur.

## Ekran bölmələri

### Əsas vəziyyət kartları

- `Tick axını`: active, stale və waiting vəziyyətləri, son tick vaxtı.
- `MT5 Bridge`: çatdırılma vəziyyəti, simvol, modul versiyası, son hesabat.
- `Disk növbəsi`: gözləyən event sayı, tutum, istifadə faizi, son xəta.
- `Məlumat itkisi`: davamlı rədd edilən event sayğacı.

### Toplanma statistikası

- toplam tick;
- unikal event ID;
- dublikat verilənlər bazası sətri;
- simvol sayı;
- ilk və son tick vaxtı.

### Bridge detalları

Hər Bridge hesabatı üçün simvol, versiya, növbə vəziyyəti, tutum, rədd edilən
event sayı və son hesabat vaxtı göstərilir.

## Status qaydaları

| API statusu | İstifadəçi mətni | Rəng |
|---|---|---|
| `active` | Aktiv | Yaşıl |
| `healthy` | Sağlam | Yaşıl |
| `waiting` | Gözləyir | Mavi |
| `stale` | Gecikib | Sarı |
| `backlogged` | Növbə var | Sarı |
| `degraded` | Problem aşkarlanıb | Qırmızı |
| `full` | Növbə dolub | Qırmızı |

Rəng heç vaxt yeganə göstərici deyil; hər status mətnlə də göstərilir.

## Yenilənmə və xəta davranışı

- Hər iki API 5 saniyədə bir sorğulanır.
- Sorğu 3 saniyədən sonra dayandırılır.
- Sorğular üst-üstə düşmür.
- Son uğurlu tam yenilənmənin vaxtı göstərilir.
- API müvəqqəti əlçatmaz olduqda son uğurlu məlumat silinmir.
- Əlaqə xətası qırmızı bannerlə göstərilir.

## Responsive və əlçatanlıq

- Desktop: dörd əsas kart bir sırada.
- Tablet: iki kart bir sırada.
- Mobil: bir kart bir sırada.
- Minimum əsas mətn ölçüsü 16 pikseldir.
- Klaviatura fokusları görünür.
- Statuslar semantik mətn və canlı regionlarla verilir.
- Azaldılmış animasiya seçiminə hörmət edilir.

## Qəbul meyarları

- İstifadəçi tick, Bridge, növbə və məlumat itkisi vəziyyətini 10 saniyədən az
  müddətdə anlaya bilir.
- Bütün dəyərlər backend API-dən gəlir.
- API xətası ilə stale vəziyyəti bir-birindən aydın fərqlənir.
- Rədd edilən event sayı sıfırdan böyük olduqda həmişə qırmızı göstərilir.
- Desktop, tablet və mobil ekranlar istifadəyə yararlıdır.
- Frontend lint, build və server-render testi keçir.
