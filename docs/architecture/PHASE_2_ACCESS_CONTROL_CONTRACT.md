# ESAS Platform — Phase 2 giriş və icazə müqaviləsi

Versiya: 1.0
Status: DESIGN READY — NOT IMPLEMENTED
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

Konfiqurasiya, secret və təhlükəsiz bootstrap qaydaları:
`docs/architecture/PHASE_2_CONFIGURATION_STARTUP_CONTRACT.md`

Audit və qəbul sübutunun ixrac qaydaları:
`docs/architecture/PHASE_2_AUDIT_EVIDENCE_EXPORT_CONTRACT.md`

## Məqsəd

Bu müqavilə Phase 2 replay, məlumat keyfiyyəti və audit funksiyalarına kimin baxa
və hansı əməliyyatı edə biləcəyini müəyyən edir.

İcazə sistemi:

- ən az səlahiyyət prinsipinə əsaslanır;
- hər dəyişdirici əməliyyatı konkret istifadəçi və rol ilə audit edir;
- xam tick məlumatına `UPDATE` və `DELETE` səlahiyyəti vermir;
- siqnal, order və real ticarət səlahiyyəti yaratmır;
- frontend görünüşünü təhlükəsizlik sərhədi hesab etmir; qərarı backend verir.

## Mövcud Phase 1 vəziyyəti

Hazırkı lokal monitorinq girişi:

- bir istifadəçi kodu və parol istifadə edir;
- uğurlu girişdə 8 saatlıq imzalanmış sessiya yaradır;
- logout zamanı sessiyanı dərhal etibarsızlaşdırır;
- ardıcıl uğursuz girişləri müvəqqəti bloklayır;
- ayrıca rol və çox-istifadəçi qeydiyyatı saxlamır.

Phase 2 istehsal kodu başlamazdan əvvəl rol məlumatı backend-in etibarlı
konfiqurasiyasına və ya ayrıca istifadəçi repository-sinə əlavə edilməlidir.
Frontend-in göndərdiyi rol heç vaxt etibarlı mənbə sayılmır.

## Rollar

### `observer` — Müşahidəçi

- canlı monitorinqi oxuyur;
- replay sessiyalarının siyahı və detallarını oxuyur;
- məlumat keyfiyyəti hesabatlarını oxuyur;
- heç bir dəyişdirici replay əmri verə bilmir.

### `operator` — Operator

Müşahidəçi hüquqlarına əlavə olaraq:

- replay sessiyası yaradır;
- öz yaratdığı sessiyanı başladır, addımlayır, pauza edir, davam etdirir və
  ləğv edir;
- məlumat keyfiyyəti analizini başladır.

Operator başqa istifadəçinin sessiyasını idarə edə bilmir.

### `auditor` — Auditor

Müşahidəçi hüquqlarına əlavə olaraq:

- bütün replay və keyfiyyət audit tarixçəsini oxuyur;
- qəbul və audit sübutunu məxfi məlumatdan təmizlənmiş formatda ixrac edir;
- məlumat itkisi hadisəsini təsdiqləyir.

Auditor replay sessiyasını yaratmır və idarə etmir. Təsdiq sayğacı silmir,
tarixi itkini bərpa olunmuş kimi göstərmir.

### `administrator` — Administrator

- bütün müşahidə, operator və auditor hüquqlarına malikdir;
- istifadəçi rollarını idarə edir;
- başqa istifadəçinin yarımçıq replay sessiyasını əməliyyat səbəbi ilə idarə edə
  bilər;
- təhlükəsizlik auditinə baxır.

Administrator da:

- xam tick payload-ını dəyişdirə və silə bilməz;
- append-only audit qeydini dəyişdirə və silə bilməz;
- tamamlanmış replay nəticəsini səssiz yenidən yaza bilməz;
- bu müqavilədən real ticarət səlahiyyəti əldə etmir.

## İcazə matrisi

| Əməliyyat | observer | operator | auditor | administrator |
| --- | :---: | :---: | :---: | :---: |
| Canlı monitorinqi oxumaq | Bəli | Bəli | Bəli | Bəli |
| Replay siyahı və detalını oxumaq | Bəli | Bəli | Bəli | Bəli |
| Keyfiyyət hesabatını oxumaq | Bəli | Bəli | Bəli | Bəli |
| Replay sessiyası yaratmaq | Xeyr | Bəli | Xeyr | Bəli |
| Öz replay sessiyasını idarə etmək | Xeyr | Bəli | Xeyr | Bəli |
| Başqasının replay sessiyasını idarə etmək | Xeyr | Xeyr | Xeyr | Bəli |
| Keyfiyyət analizini başlatmaq | Xeyr | Bəli | Xeyr | Bəli |
| Tam audit tarixçəsini oxumaq | Xeyr | Xeyr | Bəli | Bəli |
| Audit sübutunu ixrac etmək | Xeyr | Xeyr | Bəli | Bəli |
| Məlumat itkisini təsdiqləmək | Xeyr | Xeyr | Bəli | Bəli |
| İstifadəçi rolunu idarə etmək | Xeyr | Xeyr | Xeyr | Bəli |
| Xam tick və audit sətrini dəyişmək | Xeyr | Xeyr | Xeyr | Xeyr |
| Siqnal və ya order yaratmaq | Xeyr | Xeyr | Xeyr | Xeyr |

## Sessiya müqaviləsi

- Sessiya identifikatoru təxmin edilə bilməyən kriptoqrafik dəyərdir.
- İmzalanmış sessiya ən çox 8 saat yaşayır.
- Logout sessiyanı server tərəfində dərhal etibarsızlaşdırır.
- Vaxtı bitmiş, geri çağırılmış və ya imzası səhv sessiya `401` alır.
- Rol hər qorunan sorğuda backend tərəfindən yenidən müəyyən edilir.
- İstifadəçinin rolu dəyişdirildikdə onun bütün aktiv sessiyaları ləğv edilir.
- Sessiya nişanı URL, log, audit, xəta cavabı və analitika məlumatına yazılmır.
- Production mühitində sessiya yalnız HTTPS üzərindən ötürülür.

Brauzer sessiya nişanının saxlanma üsulu implementasiyadan əvvəl ayrıca təhlükə
modeli ilə seçilir. Nişan JavaScript tərəfindən oxuna bilən persistent
`localStorage` daxilində saxlanmamalıdır. Cookie seçilərsə `HttpOnly`, `Secure`
və uyğun `SameSite` siyasəti məcburidir; dəyişdirici sorğular CSRF müdafiəsi
almalıdır.

## Backend icazə yoxlaması

Hər qorunan endpoint aşağıdakı ardıcıllıqla qərar verir:

1. sessiyanı doğrula;
2. istifadəçinin aktiv olduğunu və cari rolunu etibarlı mənbədən oxu;
3. tələb olunan permission-u yoxla;
4. ownership tələb edilirsə resurs sahibini yoxla;
5. dəyişdirici əməliyyatı idempotency və vəziyyət müqaviləsi ilə icra et;
6. uğurlu və rədd edilmiş təhlükəsizlik hadisəsini audit et.

Frontend-də düymənin gizlədilməsi backend yoxlamasını əvəz etmir.

## Resurs görünməsi və ownership

- Autentifikasiya olunmuş bütün rollar replay və keyfiyyət nəticələrini oxuya
  bilər; bunlar platformanın daxili müşahidə nəticələridir.
- Operator yalnız `created_by` öz istifadəçi koduna bərabər olan sessiyaya
  dəyişdirici əmr verə bilər.
- Administrator başqa istifadəçinin sessiyasına müdaxilə edəndə məcburi səbəb
  yazır və bu səbəb auditdə saxlanır.
- Mövcud olmayan və istifadəçiyə görünməyən resurs eyni `404` cavabını verir.
- Ardıcıl rəqəm və ya istifadəçi məlumatı daşıyan resurs identifikatoru olmaz.

## Yüksək riskli əməliyyatlar

Aşağıdakılar ayrıca təsdiq və təzə autentifikasiya tələb edir:

- istifadəçinin rolunu dəyişmək;
- istifadəçini deaktiv etmək;
- başqa istifadəçinin replay sessiyasını ləğv etmək;
- məlumat itkisi hadisəsini təsdiqləmək;
- audit sübutunu ixrac etmək.

“Təzə autentifikasiya” son 15 dəqiqədə parolun yenidən doğrulanması deməkdir.
Təsdiq pəncərəsi əməliyyatın təsirini və auditdə saxlanacağını aydın göstərir.

## Audit

Uğurlu dəyişdirici əməliyyatlar və təhlükəsizlik baxımından əhəmiyyətli rədd
halları append-only audit izi yaradır:

- UTC vaxtı;
- istifadəçi kodu və həmin andakı rol;
- əməliyyat və resurs tipi;
- qeyri-həssas resurs identifikatoru;
- nəticə: `allowed` və ya `denied`;
- təhlükəsiz səbəb kateqoriyası;
- administrator müdaxiləsində istifadəçinin yazdığı səbəb;
- request correlation ID.

Audit aşağıdakıları saxlamır:

- parol və parol hash-i;
- bearer nişanı, cookie və sessiya identifikatorunun tam dəyəri;
- Bridge açarı;
- xam tick payload-ı;
- xam SQL, lokal fayl yolu və traceback;
- lazımsız IP və cihaz fingerprint-i.

Login rate-limit üçün şəbəkə ünvanı əməliyyat yaddaşında istifadə edilə bilər,
amma daimi auditə yazılması ayrıca retention və məxfilik qərarı tələb edir.

## API cavabları

- `401 Unauthorized`: sessiya yoxdur, səhvdir və ya vaxtı bitib;
- `403 Forbidden`: sessiya doğrudur, permission kifayət deyil;
- `404 Not Found`: resurs yoxdur və ya istifadəçiyə görünmür;
- `409 Conflict`: ownership doğrudur, amma vəziyyət keçidi və ya idempotency
  müqaviləsi əməliyyata icazə vermir;
- `429 Too Many Requests`: giriş və ya yüksək riskli əməliyyat limiti aşılıb.

`403` cavabı tələb olunan daxili rol strukturunu və başqa istifadəçinin kimliyini
açıqlamır.

## İlkin istifadəçi keçidi

Phase 2-yə keçiddə mövcud lokal istifadəçi avtomatik olaraq
`administrator` roluna yüksəldilmir.

Təhlükəsiz keçid:

1. ayrıca, lokal və Git-dən kənar bootstrap prosesi ilk administratoru yaradır;
2. bootstrap yalnız sistemdə administrator olmadıqda bir dəfə işləyir;
3. ilkin parol ilk girişdə dəyişdirilir;
4. mövcud monitorinq istifadəçisi üçün uyğun rol açıq şəkildə seçilir;
5. bootstrap məxfi məlumatı log və Git tarixçəsinə yazmır;
6. proses bitdikdən sonra bootstrap imkanını yenidən işlətmək bloklanır.

İlkin tək istifadəçili quraşdırmada eyni şəxsə bir neçə rol permission-u verilə
bilər, lakin audit hər əməliyyatda istifadə edilən faktiki rolu saxlayır.

## Qəbul testləri

1. Sessiyasız bütün qorunan Phase 2 endpoint-ləri `401` qaytarır.
2. Hər rol yalnız matrisi üzrə icazə verilən əməliyyatı edə bilir.
3. Frontend sorğuda saxta rol göndərsə backend onu nəzərə almır.
4. Operator başqa istifadəçinin sessiyasını idarə edə bilmir.
5. Administrator müdaxiləsi səbəbsiz qəbul edilmir və səbəb audit olunur.
6. Auditor replay sessiyasını yarada və idarə edə bilmir.
7. Heç bir rol xam tick və append-only audit sətrini dəyişə bilmir.
8. Rol dəyişikliyi bütün əvvəlki sessiyaları etibarsızlaşdırır.
9. Logout sessiyanı dərhal etibarsızlaşdırır.
10. Vaxtı bitmiş sessiya `401` qaytarır.
11. Yüksək riskli əməliyyat təzə autentifikasiya olmadan rədd edilir.
12. Login rate-limit uğurlu girişdən sonra təhlükəsiz sıfırlanır.
13. `403` və `404` cavabları başqa istifadəçi haqqında məlumat sızdırmır.
14. Auditdə parol, token, cookie, Bridge açarı və traceback görünmür.
15. Bütün icazə testləri müvəqqəti bazada işləyir və production bazasına toxunmur.
16. Frontend rol üzrə düymələri düzgün göstərir, lakin backend ayrıca eyni
    qadağanı tətbiq edir.

## Phase 2 icra ardıcıllığındakı yeri

1. İstifadəçi və rol repository-si üçün təhlükəsiz schema qərarı.
2. Permission sabitləri və mərkəzi backend authorization dependency-si.
3. Mövcud sessiya mexanizminin rol dəyişikliyində revocation dəstəyi.
4. Bootstrap və ilkin parol dəyişmə axını.
5. Replay və keyfiyyət endpoint-lərinə permission və ownership tətbiqi.
6. Təhlükəsizlik audit repository-si.
7. Frontend rol əsaslı naviqasiya və əməliyyat görünüşü.
8. Tam backend və frontend qəbul testləri.

Bu sənədin hazırlanması Phase 2 istehsal kodunun başladılması demək deyil.
