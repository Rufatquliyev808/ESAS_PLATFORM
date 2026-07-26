# Version Policy

Version: 1.0

Status: Draft

---

# Purpose

Bu sənəd ESAS Platform-da versiyaların idarə olunması qaydalarını müəyyən edir.

Platformanın hər bir komponenti ayrıca versiyaya malik ola bilər.

Versiyalar platformanın inkişaf tarixçəsini izləməyə, uyğunluğu qorumağa və dəyişiklikləri idarə etməyə xidmət edir.

---

# Semantic Versioning

Platforma Semantic Versioning prinsipindən istifadə edir.

Format:

MAJOR.MINOR.PATCH

Nümunələr:

1.0.0

1.2.0

2.0.0

---

## MAJOR

MAJOR versiyası yalnız geriyə uyğun olmayan böyük dəyişikliklər zamanı artırılır.

Nümunələr:

- arxitekturanın dəyişməsi;
- Event Contract dəyişməsi;
- modul interfeyslərinin dəyişməsi.

---

## MINOR

MINOR versiyası yeni funksiyalar əlavə olunduqda artırılır.

Mövcud funksiyalar işləməyə davam etməlidir.

Nümunələr:

- yeni Logger;
- yeni AI modeli;
- yeni analiz modulu;
- yeni Dashboard.

---

## PATCH

PATCH yalnız səhvlərin düzəldilməsi və optimallaşdırmalar üçün istifadə olunur.

Platformanın davranışı dəyişməməlidir.

Nümunələr:

- bug fix;
- performans optimallaşdırılması;
- təhlükəsizlik düzəlişi.

---

# Module Versioning

Hər modul ayrıca versiyaya malikdir.

Nümunə:

Collector v1.3.0

Liquidity Logger v2.1.0

Replay Engine v1.0.2

Visual AI v0.8.5

---

# Compatibility

Yeni versiyalar mümkün olduğu qədər əvvəlki versiyalarla uyğun işləməlidir.

Əgər uyğunluq pozulursa, MAJOR versiyası artırılmalıdır.

---

# Release Notes

Hər versiya üçün dəyişiklik siyahısı saxlanılır.

Minimum məlumat:

- Version
- Date
- Author
- Summary
- Changed Modules
- Breaking Changes (əgər varsa)

---

# Development Status

İnkişaf mərhələləri:

Prototype

Experimental

Beta

Release Candidate (RC)

Stable

Deprecated

Archived

---

# Versioning Principles

- Hər dəyişiklik izlənilə bilməlidir.
- Heç bir dəyişiklik sənədləşdirilmədən buraxılmamalıdır.
- Hər modul öz versiyasını saxlayır.
- Platforma və modullar müstəqil versiyalandırılır.