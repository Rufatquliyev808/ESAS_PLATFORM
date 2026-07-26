# Module Lifecycle

Version: 1.0

Status: Draft

---

# Purpose

Bu sənəd ESAS Platform-da hər yeni modulun necə yaranacağını, necə yoxlanacağını və necə aktivləşdiriləcəyini müəyyən edir.

Platformaya əlavə olunan hər bir logger, AI modeli, analiz modulu və ya qərar sistemi bu həyat dövrünə uyğun işləməlidir.

---# Lifecycle States

## 1. IDEA

Yeni fikir yaranır.

Bu mərhələdə:

- yalnız problem müəyyən edilir;
- həll yolu müzakirə olunur;
- heç bir kod yazılmır;
- platformanın mövcud hissələri dəyişdirilmir.

Bu mərhələnin məqsədi yalnız ideyanı sənədləşdirməkdir.

---## Lifecycle

Hər yeni modul aşağıdakı mərhələlərdən keçir:

IDEA → EXPERIMENTAL → SHADOW → ACTIVE → REVIEW → ARCHIVED

Heç bir modul bu mərhələləri keçmədən birbaşa ACTIVE vəziyyətinə keçirilə bilməz.

Platformanın sabitliyini qorumaq üçün bütün modullar bu qaydaya əməl etməlidir.

---## 2. EXPERIMENTAL

Bu mərhələdə modul ilk dəfə işləyən vəziyyətə gətirilir.

Məqsəd mükəmməl kod yazmaq deyil.

Məqsəd ideyanın işləyib-işləmədiyini yoxlamaqdır.

Bu mərhələdə icazə verilir:

- sadə implementasiya;
- sürətli dəyişikliklər;
- yeni eksperimentlər.

Bu mərhələdə qadağandır:

- köhnə modulları dəyişmək;
- əsas sistemə təsir etmək;
- nəticələri həqiqət kimi qəbul etmək.

EXPERIMENTAL modullar yalnız test mühitində işləyir.

---## 3. SHADOW

SHADOW mərhələsində modul real sistemlə eyni vaxtda işləyir, lakin heç bir qərara təsir etmir.

Modul:

- real məlumatları qəbul edir;
- öz nəticələrini hesablayır;
- bütün qərarlarını loglayır;
- mövcud ACTIVE sistemlə müqayisə olunur.

SHADOW modulu:

- əməliyyat açmır;
- digər modulları dəyişmir;
- nəticələri yalnız analiz üçün saxlayır.

Bu mərhələnin məqsədi modulun real bazar şəraitində etibarlılığını yoxlamaqdır.

SHADOW mərhələsi uğurla tamamlanmadan heç bir modul ACTIVE vəziyyətinə keçirilə bilməz.

---## 4. ACTIVE

ACTIVE mərhələsinə yalnız SHADOW mərhələsində statistik olaraq özünü sübut etmiş modullar keçə bilər.

ACTIVE modul:

- real qərar qəbul edə bilər;
- digər modullarla standart interfeyslər vasitəsilə işləyir;
- platformanın rəsmi hissəsi hesab olunur.

ACTIVE statusu daimi status deyil.

Hər ACTIVE modulun performansı davamlı olaraq izlənilir.

Əgər modulun keyfiyyəti zamanla aşağı düşərsə, o yenidən REVIEW mərhələsinə keçirilə bilər.

Platformanın məqsədi modulları qorumaq deyil.

Platformanın məqsədi ən yaxşı işləyən modulları istifadə etməkdir.

---## 5. REVIEW

REVIEW mərhələsində ACTIVE modul yenidən qiymətləndirilir.

Review aşağıdakı hallarda başladılır:

- performans aşağı düşdükdə;
- bazar davranışı dəyişdikdə;
- daha yaxşı alternativ modul yarandıqda;
- uzun müddət istifadə edildikdən sonra planlı audit zamanı.

REVIEW zamanı modul:

- yenidən SHADOW ilə müqayisə edilə bilər;
- statistik nəticələri analiz olunur;
- ACTIVE statusunu saxlaya, yenidən SHADOW-a qayıda və ya ARCHIVED ola bilər.

REVIEW prosesinin məqsədi modulu cəzalandırmaq deyil.

Məqsəd platformanın uzunmüddətli keyfiyyətini qorumaqdır.

---## 6. ARCHIVED

ARCHIVED modullar platformanın aktiv hissəsi deyil.

Lakin onlar silinmir.

Arxiv modulları:

- gələcək araşdırmalar üçün saxlanılır;
- yeni modullarla müqayisə üçün istifadə oluna bilər;
- lazım gələrsə yenidən EXPERIMENTAL mərhələsinə qaytarıla bilər.

Platforma uğursuz eksperimentləri itirmir.

Onlardan öyrənir.

---