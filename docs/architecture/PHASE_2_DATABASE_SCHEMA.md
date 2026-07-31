# Phase 2 — Verilənlər bazası sxemi və migration müqaviləsi

Status: DESIGN READY — NOT IMPLEMENTED  
Tətbiq şərti: Phase 1-in bütün qəbul qapılarının uğurla bağlanması

## Məqsəd və sərhəd

Bu sənəd Phase 2 replay sessiyası, checkpoint, idempotency, məlumat keyfiyyəti və
audit məlumatının SQLite-da necə saxlanacağını müəyyən edir.

Phase 2 migration:

- mövcud `tick_events` sətrlərini dəyişmir və silmir;
- `loss_acknowledgements` məlumatına toxunmur;
- xam tick məlumatından ayrı törəmə cədvəllər yaradır;
- yalnız replay oxuması üçün yeni indeks əlavə edir;
- real bazada avtomatik və nəzarətsiz icra olunmur.

Əlaqəli müqavilələr:

- `docs/architecture/PHASE_2_REPLAY_CONTRACT.md`
- `docs/architecture/PHASE_2_REPLAY_SESSION_CONTRACT.md`
- `docs/architecture/PHASE_2_DATA_QUALITY_CONTRACT.md`

## Sxem versiyalanması

Yeni `schema_migrations` cədvəli tətbiq olunan migration-ları izləyir:

```sql
CREATE TABLE schema_migrations
(
    version         TEXT PRIMARY KEY,
    description     TEXT NOT NULL,
    checksum        TEXT NOT NULL,
    applied_at      TEXT NOT NULL,
    application_ver TEXT NOT NULL
);
```

Qaydalar:

- migration versiyası dəyişməz və artan olur;
- tətbiq edilmiş migration faylının checksum-u sonradan dəyişdirilə bilməz;
- eyni versiya fərqli checksum ilə aşkar edilərsə startup təhlükəsiz dayanır;
- migration yalnız bir proses tərəfindən və transaction sərhədində idarə olunur;
- dağıdıcı avtomatik “down migration” ilkin versiyaya daxil deyil.

## Mövcud xam tick cədvəli

`tick_events` Phase 2 üçün authoritative xam məlumat mənbəyidir. Cədvəlin mövcud
sahələri dəyişdirilmir.

Yalnız aşağıdakı oxuma indeksi əlavə edilir:

```sql
CREATE INDEX idx_tick_events_replay
ON tick_events(symbol, event_timestamp, event_id);
```

Bu indeks:

- `[start_at, end_at)` simvol sorğusunu sürətləndirir;
- `event_timestamp, event_id` kanonik sırasını dəstəkləyir;
- xam event məzmununu dəyişmir.

## Replay sessiyası cədvəli

Konseptual sxem:

```sql
CREATE TABLE replay_sessions
(
    session_id                 TEXT PRIMARY KEY,
    created_by                 TEXT NOT NULL,
    symbol                     TEXT NOT NULL,
    start_at                   TEXT NOT NULL,
    end_at                     TEXT NOT NULL,
    mode                       TEXT NOT NULL
                               CHECK (mode IN ('step', 'max_speed')),
    state                      TEXT NOT NULL
                               CHECK (state IN (
                                   'created',
                                   'running',
                                   'paused',
                                   'interrupted',
                                   'completed',
                                   'cancelled',
                                   'failed'
                               )),
    replay_contract_version    TEXT NOT NULL,
    quality_rule_version       TEXT NOT NULL,
    dataset_tick_count         INTEGER NOT NULL
                               CHECK (dataset_tick_count >= 0),
    dataset_fingerprint        TEXT NOT NULL,
    first_event_timestamp      TEXT,
    first_event_id             TEXT,
    last_event_timestamp       TEXT,
    last_event_id              TEXT,
    processed_ticks            INTEGER NOT NULL DEFAULT 0
                               CHECK (
                                   processed_ticks >= 0
                                   AND processed_ticks <= dataset_tick_count
                               ),
    checkpoint_event_timestamp TEXT,
    checkpoint_event_id        TEXT,
    last_batch_at              TEXT,
    error_category             TEXT,
    created_at                 TEXT NOT NULL,
    updated_at                 TEXT NOT NULL,
    completed_at               TEXT,
    CHECK (end_at > start_at)
);
```

Boş dataset üçün ilk/son event və checkpoint sahələri `NULL`, tick sayı `0`,
processed sayı `0`, vəziyyət `completed` olur.

Sessiya giriş sahələri yaradıldıqdan sonra repository səviyyəsində dəyişdirilmir.
Yalnız vəziyyət, progress, checkpoint, təhlükəsiz xəta və vaxt sahələri transition
əməliyyatı daxilində yenilənə bilər.

İndekslər:

```sql
CREATE INDEX idx_replay_sessions_list
ON replay_sessions(created_at DESC, session_id DESC);

CREATE INDEX idx_replay_sessions_state
ON replay_sessions(state, updated_at);

CREATE INDEX idx_replay_sessions_owner
ON replay_sessions(created_by, created_at DESC, session_id DESC);
```

## Append-only sessiya auditi

```sql
CREATE TABLE replay_session_audit
(
    audit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL,
    actor             TEXT NOT NULL,
    actor_role        TEXT NOT NULL,
    action            TEXT NOT NULL,
    previous_state    TEXT,
    next_state        TEXT NOT NULL,
    processed_ticks   INTEGER NOT NULL CHECK (processed_ticks >= 0),
    checkpoint_time   TEXT,
    checkpoint_event  TEXT,
    error_category    TEXT,
    occurred_at       TEXT NOT NULL,
    FOREIGN KEY (session_id)
        REFERENCES replay_sessions(session_id)
        ON DELETE RESTRICT
);
```

Audit cədvəli üçün tətbiq istifadəçisinə `UPDATE` və `DELETE` yolu verilməməlidir.
Əlavə müdafiə kimi migration aşağıdakı tip trigger-lər yaradır:

```sql
CREATE TRIGGER prevent_replay_audit_update
BEFORE UPDATE ON replay_session_audit
BEGIN
    SELECT RAISE(ABORT, 'replay audit is append-only');
END;

CREATE TRIGGER prevent_replay_audit_delete
BEFORE DELETE ON replay_session_audit
BEGIN
    SELECT RAISE(ABORT, 'replay audit is append-only');
END;
```

`actor_role` əməliyyat anında backend-in etibarlı mənbədən müəyyən etdiyi rolun
dəyişməz surətidir; frontend-dən qəbul edilmir.

Audit məxfi açar, bearer nişanı, parol, xam SQL, lokal yol və traceback saxlamır.

İndeks:

```sql
CREATE INDEX idx_replay_audit_session
ON replay_session_audit(session_id, audit_id);
```

## İdempotency qeydləri

```sql
CREATE TABLE replay_idempotency
(
    idempotency_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    actor             TEXT NOT NULL,
    key_hash          TEXT NOT NULL,
    operation         TEXT NOT NULL,
    request_hash      TEXT NOT NULL,
    response_status   INTEGER NOT NULL,
    response_json     TEXT,
    created_at        TEXT NOT NULL,
    expires_at        TEXT NOT NULL,
    UNIQUE (actor, key_hash)
);
```

Xam `Idempotency-Key` saxlanmır; SHA-256 hash saxlanılır. `response_json` yalnız
təhlükəsiz API cavabıdır və məxfi məlumat ehtiva etmir.

İlkin müddət `24 saat`dır. Müddəti bitmiş idempotency qeydlərinin təmizlənməsi:

- aktiv sorğu transaction-u xaricində kiçik batch-lərlə aparılır;
- sessiya və audit qeydlərinə toxunmur;
- ayrıca test və ölçülə bilən limit tələb edir.

## Məlumat keyfiyyəti hesabatı

```sql
CREATE TABLE tick_quality_reports
(
    report_id                   TEXT PRIMARY KEY,
    session_id                  TEXT,
    created_by                  TEXT NOT NULL,
    symbol                      TEXT NOT NULL,
    start_at                    TEXT NOT NULL,
    end_at                      TEXT NOT NULL,
    replay_contract_version     TEXT NOT NULL,
    quality_rule_version        TEXT NOT NULL,
    dataset_tick_count          INTEGER NOT NULL
                                CHECK (dataset_tick_count >= 0),
    dataset_fingerprint         TEXT NOT NULL,
    status                      TEXT NOT NULL
                                CHECK (status IN (
                                    'running',
                                    'pass',
                                    'review',
                                    'fail',
                                    'failed'
                                )),
    critical_count              INTEGER NOT NULL DEFAULT 0
                                CHECK (critical_count >= 0),
    warning_count               INTEGER NOT NULL DEFAULT 0
                                CHECK (warning_count >= 0),
    info_count                  INTEGER NOT NULL DEFAULT 0
                                CHECK (info_count >= 0),
    metrics_json                TEXT,
    error_category              TEXT,
    created_at                  TEXT NOT NULL,
    completed_at                TEXT,
    CHECK (end_at > start_at),
    FOREIGN KEY (session_id)
        REFERENCES replay_sessions(session_id)
        ON DELETE RESTRICT
);
```

`session_id` könüllüdür: hesabat replay sessiyasından və ya eyni sabit aralıq üçün
birbaşa keyfiyyət sorğusundan yaradıla bilər.

İndekslər:

```sql
CREATE INDEX idx_quality_reports_list
ON tick_quality_reports(created_at DESC, report_id DESC);

CREATE INDEX idx_quality_reports_session
ON tick_quality_reports(session_id, created_at DESC);

CREATE INDEX idx_quality_reports_query
ON tick_quality_reports(
    symbol,
    start_at,
    end_at,
    quality_rule_version
);
```

## Keyfiyyət tapıntıları

```sql
CREATE TABLE tick_quality_findings
(
    finding_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id          TEXT NOT NULL,
    rule_id            TEXT NOT NULL,
    rule_version       TEXT NOT NULL,
    severity           TEXT NOT NULL
                       CHECK (severity IN ('info', 'warning', 'critical')),
    occurrence_count   INTEGER NOT NULL
                       CHECK (occurrence_count > 0),
    first_seen_at       TEXT,
    last_seen_at        TEXT,
    example_event_ids  TEXT NOT NULL,
    details_json       TEXT,
    FOREIGN KEY (report_id)
        REFERENCES tick_quality_reports(report_id)
        ON DELETE RESTRICT,
    UNIQUE (report_id, rule_id, rule_version)
);
```

`example_event_ids` məhdud JSON massividir. Bütün uyğun event-lər bu cədvələ
köçürülmür. `details_json` yalnız qaydaya aid təhlükəsiz, versiyalanmış ölçüləri
saxlayır.

İndeks:

```sql
CREATE INDEX idx_quality_findings_report
ON tick_quality_findings(report_id, severity, rule_id);
```

Tamamlanmış hesabat və tapıntıları repository dəyişməz oxuyur. Hesabat hazırlanarkən
`running` sətri transaction-larla yenilənə bilər; terminal statusdan sonra dəyişiklik
qadağan edilir.

## Transaction və kilidləmə qaydaları

- `PRAGMA foreign_keys = ON` bütün bağlantılarda məcburidir.
- Mövcud WAL rejimi qorunur.
- Checkpoint və uyğun audit sətri eyni transaction-da yazılır.
- Keyfiyyət hesabatının terminal xülasəsi və tapıntıları eyni yekun transaction-da
  bağlanır.
- Eyni sessiya üçün worker lock-u alınmadan progress yazılmır.
- Uzun replay oxuması bir transaction-u bütün sessiya boyu açıq saxlamır.
- `busy_timeout` xətanı gizlətmir; limit keçilərsə təhlükəsiz retry və ya `503`
  tətbiq olunur.

## Migration-dan əvvəl sübut

Real migration-dan əvvəl:

1. Backend və frontend versiyaları qeyd edilir.
2. Diskdə bazanın və backup-ın yerləşməsi üçün kifayət qədər boş yer təsdiqlənir.
3. SQLite online backup API-si ilə ayrıca backup yaradılır.
4. Sadə fayl kopyası istifadə edilmir; WAL məlumatının itməsi riski var.
5. Əsas baza və backup üçün `quick_check=ok` təsdiqlənir.
6. `tick_events` üçün aşağıdakılar saxlanılır:
   - sətir sayı;
   - unikal `event_id` sayı;
   - minimum/maksimum `event_timestamp`;
   - kanonik sıradakı event ID-lərdən axın SHA-256 fingerprint.
7. `loss_acknowledgements` sətir sayı saxlanılır.

Backup yolu və sübut faylı məxfi açar saxlamır və Git-ə əlavə edilmir.

## Migration icrası

Phase 1 bağlandıqdan sonra nəzarətli pəncərədə:

1. Yeni replay/quality əməliyyatları bloklanır.
2. Canlı tick qəbulu üçün qısa kilid təsiri əvvəlcədən ölçülür.
3. Migration eksklüziv tətbiq lock-u ilə başlanır.
4. `schema_migrations` və törəmə cədvəllər transaction daxilində yaradılır.
5. Replay indeksi ayrıca ölçülən addımda yaradılır; böyük bazada yazmanı
   bloklama müddəti müşahidə edilir.
6. Hər migration yalnız tam uğurda commit olunur.
7. Uğursuzluqda transaction rollback edilir və platforma Phase 1 sxemi ilə qalır.

SQLite indeks yaradılması uzun çəkərsə onu canlı yüksək tick axınında məcburi icra
etmək olmaz. Aşağı aktivlik pəncərəsi və ya nəzarətli qısa qəbul fasiləsi ayrıca
istifadəçi qərarı tələb edir.

## Migration-dan sonra qəbul

1. `quick_check=ok` və `foreign_key_check` boş nəticə verir.
2. Migration versiya/checksum qeydi düzgündür.
3. Migration-dan əvvəlki bütün xam tick ölçüləri və fingerprint dəyişməyib.
4. `loss_acknowledgements` sətir sayı dəyişməyib.
5. Yeni cədvəl, constraint, indeks və trigger-lər mövcuddur.
6. Replay sorğusunun query planı `idx_tick_events_replay` indeksindən istifadə edir.
7. Canlı tick yazısı və idempotent duplicate davranışı yenidən test edilir.
8. Backend health və operational status `ok` olur.
9. Backup bərpa sınağı production faylından ayrı müvəqqəti yerdə keçir.

## Rollback və bərpa

- Transaction commit-dən əvvəl xəta: avtomatik rollback.
- Commit-dən sonra qəbul meyarı uğursuzdur: platforma dayandırılır, yeni yazılar
  qəbul edilmədən təsdiqlənmiş backup ayrıca fayla bərpa edilir.
- Bərpa hədəfi dəqiq absolute yol və production-dan ayrı müvəqqəti fayl ilə
  əvvəlcədən yoxlanılır.
- Production bazası üzərinə kor-koranə kopyalama edilmir.
- Bərpadan sonra `quick_check`, sətir sayları, fingerprint və canlı qəbul testi
  təkrar aparılır.

Rollback xam məlumatı riskə atan avtomatik `DROP TABLE` ardıcıllığı deyil.

## Test strategiyası

1. Hər migration təzə müvəqqəti bazada işləyir.
2. Mövcud Phase 1 fixture bazası Phase 2-yə yüksəldilir.
3. Eyni migration ikinci dəfə məlumatı dəyişmir.
4. Eyni versiya fərqli checksum ilə rədd edilir.
5. Constraint və foreign key pozuntuları rədd edilir.
6. Audit `UPDATE` və `DELETE` trigger-ləri əməliyyatı bloklayır.
7. Checkpoint və audit transaction-u yarıda xəta alanda heç biri qismən qalmır.
8. Terminal keyfiyyət hesabatı dəyişdirilə bilmir.
9. Idempotency xam açarı bazada saxlanmır.
10. Böyük sintetik tick bazasında indeks vaxtı və query planı ölçülür.
11. Migration-dan əvvəl və sonra xam məlumat fingerprint-i eyni qalır.
12. Online backup ayrıca bazada uğurla açılır və `quick_check=ok` verir.
13. Bütün testlər canlı `database/ESAS_PLATFORM.sqlite` faylından təcrid olunur.

## Phase 1-dən sonra icra ardıcıllığı

1. Migration runner və checksum nəzarəti.
2. Müvəqqəti bazada schema migration testləri.
3. Replay indeksinin performans ölçümü.
4. Sessiya, audit və idempotency repository-ləri.
5. Keyfiyyət hesabatı və tapıntı repository-ləri.
6. Backup, qəbul və bərpa alətlərinin dry-run sınağı.
7. İstifadəçi təsdiqli nəzarətli production migration.

Bu sənədin hazırlanması real migration və ya Phase 2 istehsal kodunun başladılması
demək deyil.
