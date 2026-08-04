# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca təsdiq gözləyir
Prioritet: HIGH
Mərhələ: Phase 4 statistik etibarlılıq və sadə baseline müqayisəsi

## Tapşırıq

EMA və RSI üzrə tamamlanmış, xərclərdən sonrakı walk-forward nəticələrinə statistik
etibarlılıq qatı əlavə etmək. Məqsəd müşahidə olunan fərqin təsadüfi dalğalanmadan
ayrılıb-ayrılmadığını və ən sadə müqayisə bazasını keçib-keçmədiyini göstərməkdir.

## Sərhədlər

- Mövcud xam və xərcdən sonrakı nəticələr dəyişdirilməyəcək.
- Əsas metric, baseline və qəbul həddi hesablamadan əvvəl açıq qeyd ediləcək.
- Confidence interval, effect size, nümunə sayı və uncertainty ayrı göstəriləcək.
- EMA və RSI nəticələri eyni qayda ilə qiymətləndiriləcək, yalnız uğurlu variantlar
  seçilib gizli saxlanmayacaq.
- Nəticə `accepted_for_shadow` statusu verməyəcək; yalnız növbəti araşdırma qərarı üçün
  sübut yaradacaq.
- Canlı siqnal, mövqe ölçüsü, risk icazəsi və order yaradılmayacaq.

## Tamamlanma meyarları

- Versiyalanmış və fingerprint-li statistik qiymətləndirici mövcuddur.
- Sadə baseline, əsas metric və qeyri-müəyyənlik vahidləri açıq göstərilir.
- Kiçik nümunə, sıfır variasiya, mənfi nəticə və natamam məlumat testləri mövcuddur.
- Xərcli normal, pis və stress nəticələri qarışdırılmadan müqayisə edilir.
- Frontend nəticəni sadə Azərbaycan dilində, “sübut yetərlidir/yetərli deyil” sərhədi
  ilə göstərir və mənfəət vədi vermir.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Başlama şərti

Bu mərhələ yalnız istifadəçinin ayrıca təsdiqindən sonra başlayacaq. Xərc və stress
ssenarilərinin tamamlanması statistik nəticəni avtomatik etibarlı etmir və ticarətə
başlamaq hüququ vermir.
