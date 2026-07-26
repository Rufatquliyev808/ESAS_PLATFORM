# ESAS Platform Architecture

Version: 1.0

Status: Draft

---

# Purpose

Bu sənəd ESAS Platform-un ümumi arxitekturasını təsvir edir.

Burada platformanın əsas modulları, onların qarşılıqlı əlaqəsi və məlumat axını müəyyən edilir.

Bu sənəd platformanın "xəritəsi" hesab olunur.

Yeni yaradılan hər bir modul bu arxitekturaya uyğun yerləşdirilməlidir.

---

# High Level Architecture

Platforma aşağıdakı əsas hissələrdən ibarətdir:

```text
Market
  ↓
MT5 Bridge
  ↓
Collector Layer
  ↓
Event Bus
  ↓
Logger Layer
  ↓
Raw Database
  ↓
Analysis Layer
  ↓
Knowledge Base
  ↓
Decision Layer
  ↓
Execution Layer
  ↓
Feedback Layer
```

---

# Layer Overview

## Market

Real maliyyə bazarı.

Qiymətlər, tick-lər, order book, xəbərlər və digər xarici məlumat mənbələri.

---

## MT5 Bridge

MetaTrader 5 ilə ESAS Platform arasında əlaqə yaradır.

Bu modul:

- bazar məlumatlarını qəbul edir;
- platformadan gələn əmrləri MT5-ə ötürür;
- platformanı brokerdən ayırır.

---

## Collector Layer

Bazardan gələn bütün xam məlumatları toplayır.

Bu mərhələdə heç bir analiz aparılmır.

Məqsəd maksimum keyfiyyətli məlumat toplamaqdır.

---

## Event Bus

Platformanın daxili məlumat ötürmə sistemidir.

Modullar bir-biri ilə birbaşa deyil, Event Bus vasitəsilə əlaqə qururlar.

Bu yanaşma modulların bir-birindən asılılığını minimuma endirir.

---

## Logger Layer

Platformadakı bütün logger modulları burada yerləşir.

Məsələn:

- Price Logger
- Tick Logger
- Liquidity Logger
- Spread Logger
- Volume Logger
- News Logger
- Pattern Logger

Yeni logger-lər digər modullara toxunmadan əlavə edilə bilər.

---

## Raw Database

Toplanan bütün xam məlumat burada saxlanılır.

Bu məlumat:

- dəyişdirilmir;
- silinmir;
- gələcək analizlər üçün qorunur.

---

## Analysis Layer

Toplanmış məlumat burada analiz edilir.

Bu qat aşağıdakı modullardan ibarət ola bilər:

- Statistical Analysis
- Replay Engine
- Pattern Discovery
- Machine Learning
- AI Analysis
- Backtesting

---

## Knowledge Base

Platformanın öyrəndiyi bütün bilik burada saxlanılır.

Buraya daxildir:

- statistik modellər;
- pattern-lər;
- AI modelləri;
- risk modelləri;
- bazar davranışı haqqında biliklər.

Knowledge Base platformanın "yaddaşı" hesab olunur.

---

## Decision Layer

Platformanın qərar qəbul edən hissəsidir.

Bu qat:

- bütün analiz nəticələrini qiymətləndirir;
- riski hesablayır;
- əməliyyat açılıb-açılmayacağına qərar verir.

---

## Execution Layer

Qərar təsdiqləndikdən sonra əməliyyat icra olunur.

Bu qat:

- MT5 Bridge ilə əlaqə yaradır;
- order göndərir;
- əməliyyatları izləyir;
- bağlanmaları idarə edir.

---

## Feedback Layer

İcra olunmuş əməliyyatların nəticələri yenidən platformaya qaytarılır.

Burada:

- nəticələr analiz edilir;
- səhvlər müəyyən edilir;
- AI modelləri yenilənir;
- statistik göstəricilər yenidən hesablanır.

Feedback Layer platformanın davamlı öyrənməsini təmin edir.

---

# Continuous Learning

Platformanın məlumat axını əsasən yuxarıdan aşağıya hərəkət edir.

Lakin öyrənmə prosesi Feedback Layer vasitəsilə yenidən Knowledge Base-ə qayıdır.

Beləliklə platforma qapalı öyrənmə dövrəsi (Continuous Learning Loop) prinsipi ilə işləyir.

```text
Market
   │
   ▼
Collect
   │
   ▼
Analyze
   │
   ▼
Learn
   │
   ▼
Decide
   │
   ▼
Execute
   │
   ▼
Measure
   │
   └───────────────► Learn Again
```