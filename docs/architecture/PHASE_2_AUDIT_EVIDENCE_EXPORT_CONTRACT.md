# ESAS Platform — Phase 2 audit və qəbul sübutu ixrac müqaviləsi

Versiya: 1.0
Status: **DESIGN READY — NOT IMPLEMENTED**
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

## Məqsəd

Bu müqavilə replay, məlumat keyfiyyəti, təhlükəsizlik, migration, backup və qəbul
nəticələrinin dəyişməz, sanitizasiya edilmiş və sonradan yoxlana bilən sübut
paketi kimi ixracını müəyyən edir.

İxrac:

- database backup-ı deyil;
- xam tick arxivini standart olaraq daşımır;
- sayğacı sıfırlamır və hadisəni həll olunmuş göstərmir;
- audit və xam məlumatı dəyişmir;
- siqnal, qərar, order və real ticarət yaratmır.

## İxrac növləri

### `audit_export`

Seçilmiş UTC intervalı və icazəli hadisə kateqoriyaları üzrə sanitizasiya edilmiş
append-only audit qeydləridir.

### `acceptance_evidence`

Müəyyən release/commit və dataset snapshot-ı üçün test, bütövlük, performans,
replay determinizmi, məlumat keyfiyyəti və bərpa nəticələrinin sübutudur.

### `incident_evidence`

Müəyyən insidentin occurrence, acknowledgment, əlaqəli audit, təhlükəsiz
operational göstərici və düzəliş tarixçəsidir. Hadisənin təsdiqi onun həll
olunması demək deyil.

### `migration_evidence`

Migration-dan əvvəl və sonrakı schema versiyası, checksum, tick sayı,
timestamp sərhədləri, dataset fingerprint və integrity nəticəsidir.

### `restore_evidence`

Backup manifesti, bərpa yoxlamaları, `quick_check`, `foreign_key_check`, say və
fingerprint müqayisəsi, izolə edilmiş smoke test nəticəsidir.

## İcazə və təsdiq

- Yalnız `auditor` və `administrator` ixrac yarada və yükləyə bilər.
- İxrac yaratmaq təzə autentifikasiya, məqsəd və təhlükəsiz səbəb tələb edir.
- İstifadəçi yalnız öz yaratdığı ixracı yükləyə bilər; administrator müdaxiləsi
  ayrıca səbəb və audit tələb edir.
- İxrac linki təxmin edilə bilməyən, tək istifadəli və qısa müddətli olur.
- Fayl yolu və object-storage açarı API-yə açıqlanmır.
- İxracın yaradılması, uğursuzluğu, yüklənməsi və vaxtının bitməsi audit olunur.

Frontend düyməsinin görünməsi permission yoxlamasını əvəz etmir.

## Asinxron həyat dövrü

İxrac background job-dur:

`requested -> validating -> collecting -> packaging -> verifying -> ready`

Terminal vəziyyətlər:

- `failed`;
- `cancelled`;
- `expired`;
- `downloaded`.

Job `202 Accepted` qaytarır. Eyni user, filter və `Idempotency-Key` retry zamanı
ikinci paket yaratmır. Hazır olmayan və ya yoxlanmamış paket endirilə bilməz.

İlkin limitlər:

- istifadəçi başına ən çox 2 aktiv ixrac;
- audit intervalı standart 7 gün, maksimum 31 gün;
- daha böyük interval idarəçi tərəfindən hissələrə bölünür;
- paket üçün standart sıxışdırılmamış maksimum 500 MiB;
- limitə yaxınlaşdıqda səssiz truncation qadağandır.

Limit keçilərsə job başlamazdan əvvəl təhlükəsiz xəta qaytarılır.

## Paket formatı

Paket UTF-8 fayllardan ibarət ZIP arxividir:

```text
esas-evidence-<export_id>.zip
├── manifest.json
├── summary.json
├── audit-events.jsonl
├── checksums.sha256
├── signature.json
└── reports/
    ├── acceptance-results.json
    ├── quality-summary.json
    ├── replay-summary.json
    └── restore-summary.json
```

Yalnız ixrac növünə aid fayllar daxil edilir. Olmayan hesabat boş fayl kimi
yaradılmır; `manifest.json` daxilində `not_applicable` səbəbi göstərilir.

JSON kanonik serializasiya qaydası müqavilə versiyası ilə sabitləşdirilir.
JSONL-də hər sətir müstəqil JSON obyektidir və audit sırası monoton audit açarı
ilə qorunur.

CSV yalnız insan rahatlığı üçün optional əlavə ola bilər. Kanonik sübut JSON/
JSONL-dir; CSV heç vaxt checksum və yoxlama mənbəyini əvəz etmir.

## Manifest

`manifest.json` ən azı bunları daşıyır:

- `evidence_contract_version`;
- `export_id`, `export_type`, UTC yaranma və bitmə vaxtı;
- sanitizasiya edilmiş requester ID və faktiki rol;
- məqsəd və səbəb kateqoriyası;
- filter intervalı və hadisə kateqoriyaları;
- tətbiq, backend, frontend, Bridge və qayda versiyaları;
- Git commit SHA və dirty-worktree göstəricisi;
- konfiqurasiya sxemi və məxfi olmayan profil;
- database schema və migration checksum siyahısı;
- dataset fingerprint, tick sayı və ilk/son tick vaxtı;
- daxil edilən hər faylın yolu, media tipi, byte ölçüsü, sətir sayı və SHA-256;
- redaction policy versiyası;
- completeness nəticəsi və hər istisnanın təhlükəsiz səbəbi;
- imza alqoritmi və qeyri-həssas signing key ID;
- paket yoxlama nəticəsi.

Git iş qovluğu dirty-dirsə `acceptance_evidence` rəsmi release sübutu sayılmır.

## Qəbul sübutunun minimum tərkibi

Rəsmi qəbul paketi:

- dəqiq başlanğıc və son UTC vaxtı;
- bazar/sınaq konteksti və müddət;
- başlanğıc və son tick sayı, fərq və qəbul sürəti;
- yeni rədd edilmiş event sayı;
- tarixi rədd edilmiş event və acknowledgment vəziyyəti;
- disk növbəsinin başlanğıc, maksimum və son sayı;
- Bridge restart, retry və bərpa nəticələri;
- `quick_check` və lazım olduqda `foreign_key_check`;
- dataset fingerprint və timestamp sərhədləri;
- backend, frontend, MQL5 və GitHub check nəticələri;
- replay determinizm və məlumat keyfiyyəti nəticələri;
- performans referans mühiti və hədlər;
- backup/restore yoxlaması;
- məlum istisna, risk və manual addımlar;
- yekun `pass`, `fail` və ya `inconclusive` qərarı.

Sübut çatışmırsa nəticə avtomatik `pass` ola bilməz. Bazar bağlı olduğu üçün
kifayət qədər canlı vaxt toplanmayıbsa nəticə `inconclusive` olur.

## Audit event modeli

`audit-events.jsonl` hər sətirdə:

- monoton audit ID və UTC vaxtı;
- actor-un sanitizasiya edilmiş kodu və həmin andakı rol;
- action, resurs tipi və qeyri-həssas resurs ID;
- `allowed`, `denied`, `failed` və ya `acknowledged` nəticəsi;
- təhlükəsiz reason kateqoriyası;
- correlation/request ID;
- əvvəlki və yeni vəziyyətin məxfi olmayan xülasəsi;
- mənbə audit schema versiyası.

Eksport audit sırasını dəyişmir. Paketdə sətirlər audit ID üzrə artır.

## Sanitizasiya və qadağan edilmiş məlumat

Paketə daxil edilmir:

- parol, hash, token, cookie, sessiya və CSRF nişanı;
- Bridge, signing və backup açarı;
- `.env` məzmunu;
- tam IP, cihaz fingerprint-i və lazımsız şəxsi məlumat;
- tam lokal yol, istifadəçi home yolu və storage credential;
- xam SQL, traceback və process environment;
- xam tick JSON payload-ı;
- məhdudiyyətsiz log dump və memory dump.

İstifadəçi kodu accountability üçün lazım olduqda saxlanıla bilər. Xarici
paylaşım üçün ayrıca pseudonymized profil yaradılır. Redaction regex-ə təkbaşına
etibar etmir; allowlist schema əsasında qurulur.

Sanitizasiya olunan sahənin özü deyil, `redacted_fields_by_category` sayğacı
manifestdə göstərilir.

## Xam məlumat sübutu

Xam tick payload standart paketə daxil edilmir. Dataset aşağıdakılarla sübut
olunur:

- kanonik sıra qaydası;
- event sayı;
- ilk və son timestamp;
- simvol və interval;
- SHA-256 dataset fingerprint;
- seçilmiş deterministik nümunələrin yalnız qeyri-həssas identifikatorları.

Tam xam məlumat lazım olduqda bu müqavilə deyil, ayrıca şifrələnmiş data export
müqaviləsi və daha yüksək təsdiq tələb olunur.

## Bütövlük və imza

`checksums.sha256` paketdəki bütün faylların SHA-256 dəyərini saxlayır.
Checksum təsadüfi korlanmanı göstərir, amma təkbaşına müəllifliyi sübut etmir.

Acceptance və production paketində manifest ayrıca dedicated signing key ilə
imzalanır. İlkin uyğun seçim Ed25519-dur. `signature.json`:

- alqoritm;
- key ID;
- imzalanan manifest checksum-u;
- Base64 imza;
- imza vaxtı;
- verifier versiyası

daşıyır. Private key paketə, loga və Git-ə daxil edilmir.

İmza xidməti əlçatan deyilsə rəsmi sübut `ready` olmur və fail-closed dayanır.
Development/test paketi `unsigned_test_only` kimi aydın işarələnə bilər və
rəsmi qəbul sübutu sayılmır.

## Completeness və doğrulama

Paket hazır olmamışdan əvvəl verifier:

1. manifest schema və contract versiyasını yoxlayır;
2. bütün elan edilmiş faylların mövcudluğunu təsdiqləyir;
3. ölçü, sətir sayı və checksum-ları yenidən hesablayır;
4. audit sırası, intervalı və dublikat olmadığını yoxlayır;
5. dataset say və fingerprint uyğunluğunu yoxlayır;
6. redaction scan və qadağan edilmiş açar adları yoxlamasını aparır;
7. rəqəmsal imzanı public key ilə doğrulayır;
8. nəticəni `verified`, `failed` və ya `unsigned_test_only` kimi yazır.

Verifier offline işləyə bilməli və database-ə yazmamalıdır.

## Chain of custody

Hər paket üçün:

- kim yaratdı;
- kim endirdi;
- nə vaxt yaradıldı və endirildi;
- hansı filter və müqavilə versiyası istifadə olundu;
- hansı key ID ilə imzalandı;
- verifier nəticəsi

append-only auditdə saxlanır. Endirilmiş faylın sonrakı nüsxələnməsinə platforma
nəzarət etmir; istifadəçiyə məxfilik və saxlanma məsuliyyəti göstərilir.

## Saxlama və silinmə

- Audit, qəbul və insident paketinin manifesti və yaradılma auditi müddətsizdir.
- Hazır ZIP lokal staging-də 24 saat saxlanılır, sonra exact export ID ilə silinə
  bilər.
- Rəsmi qəbul sübutunun təsdiqlənmiş arxiv nüsxəsi retention müqaviləsinə görə
  müddətsiz qorunur.
- Hold altındakı paket və metadata silinmir.
- ZIP-in expiry-si mənbə audit və acceptance qeydlərini silmir.

## API davranışı

API müqaviləsinə uyğun ilkin resurslar:

- `POST /api/v2/evidence-exports`;
- `GET /api/v2/evidence-exports/{id}`;
- `POST /api/v2/evidence-exports/{id}/cancel`;
- `POST /api/v2/evidence-exports/{id}/download-token`.

Yaratma və cancel idempotency tələb edir. Download token URL query-də deyil,
qorunan mexanizmlə ötürülür. Expired və başqa istifadəçiyə aid resurs eyni
təhlükəsiz `404` davranışını verir.

## Məcburi testlər

1. Hər export növü yalnız allowlist fayl və sahələrini yaradır.
2. Observer və operator export yarada bilmir.
3. Auditor təzə autentifikasiya olmadan rədd edilir.
4. Idempotent retry ikinci paket yaratmır.
5. Interval, aktiv job və ölçü limitləri fail-closed işləyir.
6. Sətir sayı, checksum və manifest fayllarla tam uyğun gəlir.
7. Bir byte dəyişdikdə verifier paketi rədd edir.
8. Yanlış key, imza və manifest checksum-u rədd edilir.
9. Secret, `.env`, token, cookie, SQL, tam yol və traceback paketdə görünmür.
10. Xam tick payload standart paketə daxil edilmir.
11. Audit sırası deterministikdir, dublikat və boşluq izah olunur.
12. Çatışmayan acceptance sübutu `pass` yaratmır.
13. Bazar vaxtı kifayət deyilsə nəticə `inconclusive` olur.
14. Dirty commit rəsmi release acceptance kimi işarələnmir.
15. Download və expiry chain-of-custody auditini qoruyur.
16. Verifier offline və read-only işləyir.
17. Bütün testlər sintetik müvəqqəti data ilə aparılır.

## İcra ardıcıllığındakı yeri

1. Evidence schema və kanonik JSON/JSONL serializer.
2. Allowlist redaction policy.
3. Export job və idempotency repository-si.
4. Manifest, checksum və offline verifier.
5. Signing provider və key rotation inteqrasiyası.
6. Qorunan export API-si.
7. Frontend export statusu və download axını.
8. Sintetik security, corruption və acceptance testləri.

Bu sənəd canlı audit ixracı aparmır, Phase 2 istehsal kodunu başlatmır və rəsmi
24 saatlıq START vermir.
