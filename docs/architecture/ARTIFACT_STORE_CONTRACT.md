# ESAS Platform — Local Content-Addressed Artifact Store müqaviləsi

Versiya: 1.0
Status: IMPLEMENTED (v1 — yalnız yerli fayl sistemi, PNG artefaktları üçün istifadədədir)
Tətbiq şərti: yoxdur — bu, Phase 5-in materializer-inin çıxardığı böyük binar
artefaktları (PNG, gələcəkdə model checkpoint-ləri) verilənlər bazasından
kənarda, deterministik şəkildə saxlamaq üçün ümumi infrastruktur qatıdır.

## Məqsəd və sərhəd

`visual_dataset_samples` cədvəli hər nümunənin `image_checksum`-unu saxlayır,
amma real PNG bytes-ı SQLite-da BLOB kimi saxlamır — bu, bazanı şişirdər və
platformanın "xam məlumat ayrıca, analiz nəticəsi ayrıca" prinsipinə ziddir.
Artifact store bu boşluğu doldurur: checksum-dan artefaktın DİSKDƏKİ yerini
deterministik hesablayan, məzmun-ünvanlı (content-addressed) yerli saxlama
qatıdır.

Artifact store:

- yalnız artıq hesablanmış checksum-a görə oxuyur/yazır — heç bir yeni hash
  alqoritmi təqdim etmir (mövcud `sha256:<hex>` formatını olduğu kimi qəbul
  edir);
- SQLite-a BLOB yazmır, ayrıca cədvəl yaratmır — checksum artıq mövcud
  `visual_dataset_samples.image_checksum` sütununda saxlanılır, artefaktın
  disk yolu bu checksum-dan HƏR ZAMAN yenidən hesablana bilər (əlavə "yol"
  sütunu lazım deyil);
- yazmadan əvvəl məzmunun artıq mövcud olub-olmadığını yoxlayır (idempotent
  — eyni checksum üçün ikinci yazı heç nə etmir);
- oxuyarkən checksum-u yenidən hesablayıb saxlanılan adla müqayisə edə bilir
  (bütövlük yoxlaması, korrupsiya aşkarlanması üçün);
- uzaq/bulud saxlama, replikasiya, garbage collection və ya retention
  siyasəti TƏTBİQ ETMİR — bunlar açıq şəkildə gələcək, ayrıca qərar tələb
  edən genişləndirmələrdir;
- yalnız artıq mövcud, immutable məzmunu saxlayır — heç bir analiz, render
  və ya label məntiqini təkrarlamır.

## Yerləşmə və content-addressing sxemi

Kök qovluq: `<layihə kökü>/storage/artifacts/` (məlumat bazası kimi,
`configure_artifact_root()` vasitəsilə test/scratch üçün dəyişdirilə bilər,
defolt yol production üçündür). Git-ə əlavə edilmir (`.gitignore`-da).

Yol düsturu, checksum `sha256:<64 hex simvol>` formatındadırsa:

```text
storage/artifacts/<ilk 2 hex>/<növbəti 2 hex>/<tam 64 hex simvol>.<uzantı>
```

Nümunə: `sha256:ab12cd...` → `storage/artifacts/ab/12/ab12cd....png`

İki səviyyəli alt-qovluq (sharding) tək qovluqda yüz minlərlə fayl
yaranmasının qarşısını alır (fayl sistemi performansı üçün).

## Zəmanətlər

- Eyni checksum + uzantı HƏMİŞƏ eyni yola uyğun gəlir (deterministik).
- Yazma idempotentdir: fayl artıq mövcuddursa, təkrar yazılmır.
- Oxuma zamanı könüllü bütövlük yoxlaması mövcuddur:
  oxunan bytes-ın həqiqi sha256-sı gözlənilən checksum ilə üst-üstə düşmürsə,
  `ArtifactIntegrityError` atılır — səssiz korrupsiya qəbul edilmir.
- Checksum formatı `visual_render.py`/`visual_label.py`/`visual_dataset.py`-ın
  artıq istifadə etdiyi `sha256:<hex>` sxemi ilə eynidir — yeni format
  uydurulmayıb.

## Sərhəd (bu versiyada YOXDUR)

- Uzaq/bulud saxlama (S3, object storage) — gələcək, ayrıca qərar.
- Silinmə/garbage collection — artefaktlar indiki halda əbədi saxlanılır
  (platformanın "xam məlumat itirilmir" prinsipinə uyğun).
- Model checkpoint-lərinin xüsusi formatı — store ümumi bytes+uzantı qəbul
  edir, model artefaktları da eyni funksiyalarla saxlana bilər, amma bu hələ
  tətbiq edilməyib (yalnız PNG istifadə olunur).
- API/frontend vasitəsilə artefakt yükləmə/baxma — bu, ayrıca gələcək addımdır.
