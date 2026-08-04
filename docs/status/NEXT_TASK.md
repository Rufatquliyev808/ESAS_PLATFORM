# ESAS Platform — Növbəti tapşırıq

Status: READY
Prioritet: HIGH
Mərhələ: Phase 2

## Tapşırıq

Eyni dataset və immutable replay parametrləri ilə iki müstəqil icranın eyni
checkpoint ardıcıllığı və nəticə fingerprint-i verdiyini sübut edən deterministik
replay nəticə manifesti hazırlamaq.

## Sərhədlər

- Manifest sessiyanın dataset fingerprint-i, müqavilə versiyası, rejim və intervalını
  daşımalıdır.
- Nəticə fingerprint-i kanonik emal ardıcıllığından axın şəklində hesablanmalıdır.
- Eyni giriş iki müstəqil sessiyada eyni nəticə fingerprint-i verməlidir.
- Fərqli batch ölçüsü nəticənin mənasını və fingerprint-i dəyişməməlidir.
- Dataset, müqavilə versiyası və ya interval fərqi müqayisəni fail-closed rədd etməlidir.
- Manifest replay bitmədən yekun kimi təqdim edilməməlidir.
- Xam tick-lər dəyişdirilməməli; API, frontend və canlı migration hələ əlavə edilməməlidir.

## Tamamlanma meyarları

- `step` və `max_speed` üçün tamamlanmış sessiyadan nəticə manifesti yaradılır.
- Eyni dataset-in fərqli batch ölçülü iki icrası eyni nəticə fingerprint-i verir.
- Natamam və uyğun olmayan sessiyalar müqayisə edilmir.
- Manifest hesablanması bütün dataset-i yaddaşa yükləmir.
- Mövcud backend testləri keçir və canlı baza toxunulmaz qalır.

## Sonrakı addım

Replay reproduksiyası qəbul edildikdən sonra məlumat keyfiyyəti analiz qatının ilk
qaydaları: zaman boşluğu, geriyə gedən timestamp və dublikat aşkarlanması hazırlanacaq.
