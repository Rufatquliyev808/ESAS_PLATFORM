# Phase 2 — Replay və məlumat keyfiyyəti ekran müqaviləsi

Versiya: 1.0  
Status: DESIGN READY — NOT IMPLEMENTED  
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

## Məqsəd və sərhəd

Phase 2 frontend-i texniki biliyi olmayan istifadəçiyə aşağıdakı suallara aydın
cavab verməlidir:

1. Hansı simvol və vaxt aralığı replay edilir?
2. Sessiya hazırda hansı vəziyyətdədir və nə qədər irəliləyib?
3. Replay dayandırılıbsa səbəb nədir və hansı təhlükəsiz əməl mümkündür?
4. Məlumat keyfiyyəti hesabatında hansı tapıntılar var?
5. Nəticə hansı müqavilə versiyası və dataset izi ilə yaradılıb?

Frontend:

- siqnal, proqnoz, al/sat tövsiyəsi və order düyməsi göstərmir;
- SQLite bazasına birbaşa qoşulmur;
- tick sıralaması və keyfiyyət qaydalarını brauzerdə hesablamır;
- backend nəticəsini dəyişdirmədən, Azərbaycan dilində izah edir.

Əlaqəli müqavilələr:

- `docs/architecture/PHASE_2_REPLAY_CONTRACT.md`
- `docs/architecture/PHASE_2_REPLAY_SESSION_CONTRACT.md`
- `docs/architecture/PHASE_2_DATA_QUALITY_CONTRACT.md`

## Naviqasiya

Monitorinq panelinin qorunan hissəsində üç əsas bölmə olur:

1. **Canlı monitorinq** — mövcud Phase 1 ekranı;
2. **Replay sessiyaları** — sessiya siyahısı, yaratma və idarəetmə;
3. **Məlumat keyfiyyəti** — tamamlanmış aralıqların hesabatları.

Səhifə yenilənəndə cari bölmə URL-də qorunur. İcazəsiz istifadəçi bütün qorunan
bölmələrdən giriş ekranına yönləndirilir.

## Replay sessiyaları siyahısı

Siyahıda hər sessiya üçün:

- simvol;
- `[start_at, end_at)` vaxt aralığı;
- rejim: `Addım-addım` və ya `Maksimum sürət`;
- vəziyyət və mətn nişanı;
- emal edilmiş / ümumi tick;
- faiz və son yenilənmə vaxtı;
- sessiyanı yaradan istifadəçi.

Sıra backend müqaviləsinə uyğun `created_at DESC, session_id DESC` olur. “Daha çox
göstər” düyməsi backend cursor-u ilə növbəti səhifəni alır. Frontend offset və ya
lokal yenidən sıralama tətbiq etmir.

Boş vəziyyət mətni:

> Hələ replay sessiyası yaradılmayıb.

## Yeni sessiya forması

Forma sahələri:

- `Simvol` — backend-dən alınmış mövcud simvollar;
- `Başlanğıc vaxtı`;
- `Son vaxt`;
- `İcra rejimi` — Addım-addım və ya Maksimum sürət.

İstifadəçiyə vaxtların lokal saatla göstərildiyi, backend-ə isə UTC göndərildiyi
aydın qeyd edilir. Təsdiq ekranında həm lokal vaxt, həm UTC vaxt göstərilir.

İlkin doğrulama:

- bütün sahələr məcburidir;
- son vaxt başlanğıcdan böyük olmalıdır;
- gələcək vaxt seçilə bilməz;
- simvol boş ola bilməz.

Frontend doğrulaması rahatlıq üçündür. Yekun qərar backend `422` cavabıdır və
server xətası sahənin yanında Azərbaycan dilində göstərilir.

“Sessiya yarat” düyməsi sorğu tamamlanana qədər deaktiv olur. İki klik iki sessiya
yaratmamalıdır; hər yaratma sorğusu ayrıca `Idempotency-Key` istifadə edir.

## Sessiya detal ekranı

### Başlıq və əsas məlumat

- sessiyanın qısa identifikatoru;
- simvol və vaxt aralığı;
- rejim və vəziyyət;
- replay və keyfiyyət müqaviləsi versiyaları;
- yaradılma və son yenilənmə vaxtı.

Tam dataset fingerprint standart görünüşdə qısaldılır. “Audit detalı” bölməsində
tam dəyər kopyalana bilər. Kopyalama məxfi məlumat daşımır.

### İrəliləyiş

- `processed_ticks / tick_count`;
- `0..100%` progress bar;
- son emal edilmiş event vaxtı;
- son uğurlu checkpoint vaxtı.

Progress bar `aria-valuemin`, `aria-valuemax` və `aria-valuenow` istifadə edir.
Faiz mətnlə də göstərilir.

### Addım rejimi

`paused` vəziyyətində istifadəçi `1`, `10`, `100` və ya xüsusi `1..1000` tick
seçərək “İrəli apar” əmri verir.

- Sorğu gedərkən bütün idarəetmə düymələri müvəqqəti deaktiv olur.
- Uğurlu cavabdan sonra yalnız backend-in qaytardığı progress göstərilir.
- Şəbəkə xətasında eyni Idempotency-Key ilə təhlükəsiz retry mümkündür.

### Maksimum sürət rejimi

İcazə verilən əmrlər vəziyyətə görə göstərilir:

- `created`: Başlat, Ləğv et;
- `running`: Pauza et, Ləğv et;
- `paused`: Davam et, Ləğv et;
- `interrupted`: Yoxla və davam et, Ləğv et;
- terminal vəziyyət: yalnız audit və nəticəyə baxış.

Frontend backend-in icazə vermədiyi əmri gizlətsə də, backend `409` cavabını ayrıca
idarə edir.

### Ləğv təsdiqi

“Ləğv et” ayrıca modal təsdiq tələb edir:

> Bu replay sessiyası ləğv ediləcək. Xam tick məlumatı silinməyəcək, lakin bu
> sessiya davam etdirilə bilməyəcək.

İlkin fokus “Geri qayıt” düyməsində olur. Escape modalı bağlayır. Təsdiqdən sonra
eyni sessiya terminal `cancelled` vəziyyətində göstərilir.

## Vəziyyətlərin istifadəçi dili

| Backend vəziyyəti | İstifadəçi mətni | Ton |
| --- | --- | --- |
| `created` | Hazırdır | Mavi |
| `running` | İcra olunur | Yaşıl |
| `paused` | Pauzadadır | Sarı |
| `interrupted` | Davam üçün yoxlama lazımdır | Narıncı |
| `completed` | Tamamlandı | Yaşıl |
| `cancelled` | Ləğv edildi | Boz |
| `failed` | Uğursuz oldu | Qırmızı |

Rəng heç vaxt yeganə göstərici deyil. Hər vəziyyət mətn və ikonla təqdim edilir.

## Məlumat keyfiyyəti ekranı

### Hesabat başlığı

- simvol və sabit vaxt aralığı;
- yaradılma vaxtı;
- replay və keyfiyyət qayda versiyası;
- dataset fingerprint;
- ümumi status: `Keçdi`, `Baxış tələb edir`, `Uğursuz`.

“Keçdi” ticarət üçün hazır demək deyil. Ekranda daimi izah göstərilir:

> Bu nəticə yalnız məlumat keyfiyyəti qaydalarını qiymətləndirir; ticarət siqnalı
> və ya order icazəsi deyil.

### Xülasə kartları

- ümumi tick;
- kritik tapıntı;
- xəbərdarlıq;
- məlumat xarakterli müşahidə;
- zaman boşluğu namizədləri;
- mənfi spread;
- gecikmiş event-lər.

### Tapıntı siyahısı

İlkin sıra:

```text
severity DESC, rule_id ASC
```

Hər tapıntı:

- Azərbaycan dilində qayda adı və `rule_id`;
- səviyyə və say;
- ilk/son nümunə vaxtı;
- qayda versiyası;
- məhdud nümunə event ID-ləri;
- istifadəçiyə neytral izah.

Boşluq tapıntısında bu qeyd həmişə görünür:

> Bazar sessiyası təqvimi olmadan bu fasilə avtomatik məlumat itkisi sayılmır.

Frontend severity və status hesablamır; backend-in verdiyi nəticəni göstərir.

### Statistik göstəricilər

- tick/dəqiqə;
- tick intervalı: minimum, median, p95, maksimum;
- spread: minimum, median, p95, maksimum;
- natamam və sıfır qiymət cütləri;
- qəbul gecikməsi paylanması.

Qrafik əlavə edilərsə eyni məlumat cədvəl şəklində də əlçatan olmalıdır. Qrafik
vizual bəzək üçün deyil, müqayisəni anlamaq üçün istifadə edilir.

## Yenilənmə davranışı

- `running` sessiya detalı görünəndə 2 saniyədə bir yenilənir.
- `created`, `paused` və `interrupted` sessiya 10 saniyədə bir yenilənir.
- terminal sessiyada avtomatik yenilənmə dayanır.
- brauzer səhifəsi gizli olduqda polling dayanır.
- səhifə yenidən görünəndə dərhal bir sorğu edilir.
- sorğular üst-üstə düşmür və səhifədən çıxarkən dayandırılır.

Şəbəkə xətasında son uğurlu məlumat saxlanır, lakin “Canlı deyil” banneri və son
uğurlu yenilənmə vaxtı göstərilir. Köhnə progress yeni kimi təqdim edilmir.

## Sessiyanın bitməsi və giriş təhlükəsizliyi

- `401` cavabında lokal sessiya nişanı silinir və giriş ekranına yönləndirilir.
- Girişdən sonra istifadəçi əvvəl baxdığı qorunan bölməyə təhlükəsiz qaytarıla bilər.
- Parol, bearer nişanı və Bridge açarı UI, URL, log və analitika hadisəsinə yazılmır.
- Replay Idempotency-Key yalnız əməliyyatın retry müddətində brauzer yaddaşında
  saxlanılır.
- Çıxış bütün Phase 2 sorğularını dayandırır və server sessiyasını ləğv edir.

## Xəta təqdimatı

| HTTP | İstifadəçi davranışı |
| --- | --- |
| `400` | Sorğu məlumatı etibarsızdır; yenidən yaradın |
| `401` | Sessiyanın vaxtı bitib; yenidən daxil olun |
| `404` | Sessiya tapılmadı və ya artıq əlçatan deyil |
| `409` | Vəziyyət dəyişib; məlumat yenilənərək təhlükəsiz əmrlər göstərilir |
| `422` | Sahə xətaları formanın yanında göstərilir |
| `503` | Xidmət müvəqqəti əlçatan deyil; son uğurlu məlumat saxlanılır |

İstifadəçiyə xam JSON, stack trace, SQL, lokal fayl yolu və daxili açar göstərilmir.

## Responsive və əlçatanlıq

- Desktop: siyahı və detal yan-yana istifadə edilə bilər.
- Tablet: siyahı üstə, detal aşağıda göstərilir.
- Mobil: bir sütun, idarəetmə düymələri tam en.
- Minimum toxunma sahəsi `44 × 44` pikseldir.
- Klaviatura fokusları aydın görünür.
- Bütün form sahələrinin görünən label-i var.
- Status və progress dəyişiklikləri ölçülü `aria-live` regionunda elan edilir.
- Fokus modal daxilində saxlanılır və bağlananda əvvəlki düyməyə qaytarılır.
- `prefers-reduced-motion` seçiminə hörmət edilir.
- Tarix, say və faizlər yalnız rəng və qrafiklə deyil, mətnlə verilir.

## Performans sərhədi

- Sessiya siyahısı cursor ilə səhifələnir.
- Tick payload-ları sessiya siyahısına yüklənmir.
- Tapıntı nümunələri backend tərəfindən məhdudlaşdırılır.
- Böyük hesabat hissələri tələb olunduqda yüklənir.
- Eyni API cavabı üçün lazımsız yenidən render minimuma endirilir.

## Qəbul testləri

1. İstifadəçi sessiyanın simvolunu, aralığını, rejimini və vəziyyətini 10 saniyədən
   az müddətdə anlaya bilir.
2. Sessiya yaratma forması lokal vaxtı UTC-yə düzgün çevirir.
3. İki klik iki sessiya və ya iki idarəetmə əmri yaratmır.
4. Vəziyyətə uyğun olmayan düymə göstərilmir; backend `409` təhlükəsiz yenilənir.
5. Addım rejimi backend-in qaytardığından artıq progress göstərmir.
6. Ləğv əməliyyatı aydın təsdiq tələb edir.
7. Polling gizli səhifədə dayanır və geri qayıdanda davam edir.
8. API xətasında son məlumat “canlı” kimi göstərilmir.
9. `401` istifadəçini giriş ekranına qaytarır.
10. Keyfiyyət statusu frontend tərəfindən yenidən hesablanmır.
11. Bazar fasiləsi məlumat itkisi hökmü kimi təqdim edilmir.
12. Rəngsiz və yalnız klaviatura ilə əsas axın istifadə edilə bilir.
13. Desktop, tablet və mobil görünüşlər istifadəyə yararlıdır.
14. Frontend lint, production build, server-render və interaksiya testləri keçir.
15. Ekranda siqnal, al/sat və order idarəetməsi yoxdur.

## Phase 1-dən sonra icra ardıcıllığı

1. Qorunan naviqasiya və route strukturu.
2. Sessiya siyahısı və yaratma forması.
3. Sessiya detalı və vəziyyətə bağlı əmrlər.
4. Addım rejimi və idempotent retry davranışı.
5. Keyfiyyət hesabatı və tapıntı detalları.
6. Responsive, klaviatura və ekran oxuyucu testləri.
7. Polling, xəta və performans optimallaşdırılması.

Bu sənədin hazırlanması Phase 2 frontend kodunun başladılması demək deyil.
