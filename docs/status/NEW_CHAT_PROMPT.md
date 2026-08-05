# Yeni çat üçün davametmə mətni

Aşağıdakı mətni yeni Codex çatına bütöv şəkildə göndər:

```text
D:\ESAS_PLATFORM layihəsində qaldığımız yerdən davam et.

Əvvəl heç bir faylı dəyişmə və əvvəlki əməliyyatları təkrarlama. İlk olaraq D:\ESAS_PLATFORM\AGENTS.md faylını tam oxu və oradakı qaydalara əməl et. Sonra bu ardıcıllıqla PROJECT_CONSTITUTION.md, docs\architecture\SYSTEM_ARCHITECTURE.md, PROJECT_ROADMAP.md, docs\status\CURRENT_STATE.md, docs\status\NEXT_TASK.md, docs\status\SESSION_HANDOFF.md və CHANGELOG.md fayllarını oxu.

Bundan sonra faktiki vəziyyəti sənədlərlə kifayətlənmədən yoxla: cari Git branch/status/log, dəyişdirilmiş fayllar, test nəticələri və işləyən xidmətlər. İstifadəçinin mövcud dəyişikliklərini qoruyub saxla. GitHub bağlantısı varsa PR-ları və checks nəticələrini yoxla; connector yoxdursa mövcud `gh` sessiyasından istifadə et. GitHub girişini təxmin etmə və heç bir tokeni göstərmə.

Konfiqurasiyadan aktiv SQLite bazasının yolunu müəyyən et və əvvəlcə yalnız oxuma rejimində sxemi, cədvəlləri, sayğacları, son eventləri, audit/replay məlumatlarını yoxla. Bazada dəyişiklik etməzdən əvvəl ayrıca əsas və icazə tələb et.

docs\status\SESSION_HANDOFF.md-də göstərilən ən son yarımçıq işi faktiki kod və testlərlə təsdiqlə, yalnız sonra davam et. Hər tamamlanan işdən dərhal sonra CURRENT_STATE.md, NEXT_TASK.md, CHANGELOG.md və SESSION_HANDOFF.md fayllarını yenilə. Bu dörd qeyd yenilənməyibsə işi tamamlanmış sayma.

Əvvəl uyğun testləri icra et. Commit yalnız yoxlanmış, məqsədli fayllardan yaradılsın. GitHub-a push yalnız mən açıq şəkildə istəyəndə edilsin. Yeni mərhələyə başlamazdan əvvəl mənə qısa nəticə və növbəti mərhələni bildirərək təsdiq al. Real ticarət və order açılması mənim ayrıca açıq icazəm olmadan qadağandır.

Cavabları Azərbaycan dilində, qısa və konkret ver. Kontekstə qənaət et; artıq məlum olanları təkrar izah etmə.
```
