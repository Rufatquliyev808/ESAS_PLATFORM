# ESAS Platform — Növbəti tapşırıq

Status: READY — ayrıca təsdiq gözləyir
Prioritet: HIGH
Mərhələ: Phase 4 tarixi əməliyyat xərci və stress ssenariləri

## Tapşırıq

EMA və RSI üçün tamamlanmış xam tarixi nəticəni dəyişmədən onun yanında şəffaf,
versiyalanmış xərc ssenarisi qatı yaratmaq. Məqsəd spread, komissiya və slippage
fərziyyələrinin nəticəyə təsirini göstərməkdir; bu, real gəlir və ya ticarət icazəsi deyil.

## Sərhədlər

- Xam xərcsiz nəticə həmişə ayrıca və dəyişməz qalacaq.
- Normal, pis və stress ssenarilərinin hər fərziyyəsi vahidi ilə açıq göstəriləcək.
- Brokerə aid təsdiqlənməmiş rəqəm fakt kimi təqdim edilməyəcək; yalnız istifadəçi
  tərəfindən verilən və ya açıq “fərziyyə” kimi işarələnən dəyər işlənəcək.
- Eyni xərc qaydası EMA və RSI pəncərələrinə ayrı-ayrılıqda tətbiq ediləcək.
- Canlı siqnal, mövqe ölçüsü, risk icazəsi və order yaradılmayacaq.

## Tamamlanma meyarları

- Xərc modeli və ssenari konfiqurasiyası ayrıca versiyalanır və fingerprint saxlayır.
- Ümumi xərc, xalis tarixi dəyişiklik və əhatə bir-birindən ayrı göstərilir.
- Sıfır, mənfi, həddən artıq və natamam parametr testləri mövcuddur.
- Bütün walk-forward pəncərələrində eyni deterministik ssenari tətbiq olunur.
- Frontend xam və xalis nəticəni, fərziyyələri və xəbərdarlığı sadə Azərbaycan dilində göstərir.
- Tam backend və frontend yoxlamaları yaşıl qalır.

## Sonrakı addım

Bu mərhələ yalnız istifadəçinin ayrıca təsdiqindən sonra başlayacaq. Çoxpəncərəli
sabitlik ölçümünün tamamlanması xərc modelini avtomatik təsdiqləmir və ticarətə
başlamaq hüququ vermir.
