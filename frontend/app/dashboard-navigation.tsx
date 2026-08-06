"use client";

export type DashboardSection =
  | "results"
  | "live"
  | "replay"
  | "technical"
  | "structure"
  | "liquidity"
  | "bos-choch"
  | "retest"
  | "fvg"
  | "strategies"
  | "hypotheses"
  | "pattern-candidates"
  | "shadow-runs";

type MenuItem = {
  id: DashboardSection;
  title: string;
  description: string;
  group: string;
};

const MENU_ITEMS: MenuItem[] = [
  { id: "results", title: "Nəticələr", description: "Əsas vəziyyət və yekun baxış", group: "Ümumi" },
  { id: "live", title: "Canlı məlumat", description: "Tick, Bridge və növbə", group: "Ümumi" },
  { id: "replay", title: "Replay sessiyaları", description: "Tarixi məlumatın seçimi", group: "Araşdırma" },
  { id: "technical", title: "Texniki göstəricilər", description: "Qiymət, EMA, RSI və ATR", group: "Araşdırma" },
  { id: "structure", title: "Bazar strukturu", description: "HH, HL, LH və LL", group: "Qiymət davranışı" },
  { id: "liquidity", title: "Likvidlik", description: "Süpürülmə və geri alınma", group: "Qiymət davranışı" },
  { id: "bos-choch", title: "BOS / CHoCH", description: "Qırılma və istiqamət dəyişikliyi", group: "Qiymət davranışı" },
  { id: "retest", title: "Retest", description: "Qırılmış səviyyənin yoxlanması", group: "Qiymət davranışı" },
  { id: "fvg", title: "Fair Value Gap", description: "Qiymət boşluğu və doldurulması", group: "Qiymət davranışı" },
  { id: "strategies", title: "Strategiya müqayisəsi", description: "Ayrı yanaşmaların nəticələri", group: "Qiymətləndirmə" },
  { id: "hypotheses", title: "Hipotezlər", description: "Sınaq üçün qaydalar reyestri", group: "Qiymətləndirmə" },
  { id: "pattern-candidates", title: "Pattern namizədləri", description: "Draft — hipotezlərin birləşmiş nəticəsi", group: "Qiymətləndirmə" },
  { id: "shadow-runs", title: "SHADOW run-ları", description: "Phase 9 skeleti — nəzəridir, order yaratmır", group: "Qiymətləndirmə" },
];

const MENU_ENTRIES = MENU_ITEMS.map((item, index) => ({
  item,
  showGroup: index === 0 || item.group !== MENU_ITEMS[index - 1].group,
}));

export function DashboardSidebar({ active, onSelect }: { active: DashboardSection; onSelect: (section: DashboardSection) => void }) {
  return (
    <aside className="dashboard-sidebar" aria-label="Platforma bölmələri">
      <div className="sidebar-heading">
        <p className="eyebrow">İdarə paneli</p>
        <h2>Bölmələr</h2>
        <p>İstədiyiniz nəticəni seçin. Mərkəzdə yalnız həmin bölmə açılacaq.</p>
      </div>
      <nav className="dashboard-menu">
        {MENU_ENTRIES.map(({ item, showGroup }) => {
          return (
            <div className="menu-entry" key={item.id}>
              {showGroup && <p className="menu-group">{item.group}</p>}
              <button
                type="button"
                className={active === item.id ? "active" : ""}
                aria-current={active === item.id ? "page" : undefined}
                onClick={() => onSelect(item.id)}
              >
                <strong>{item.title}</strong>
                <span>{item.description}</span>
              </button>
            </div>
          );
        })}
      </nav>
    </aside>
  );
}

export function SectionGuide({ title, metric, impact, evidence, steps }: { title: string; metric: string; impact: string; evidence: string; steps: string[] }) {
  return (
    <section className="section-guide" aria-label={`${title} izahı`}>
      <div>
        <p className="eyebrow">GOLD üçün sadə izah</p>
        <h2>{title}</h2>
      </div>
      <div className="guide-metric">
        <span>Cari rəqəm</span>
        <strong>{metric}</strong>
      </div>
      <div className="guide-impact">
        <span>GOLD-a mümkün təsiri</span>
        <p>{impact}</p>
        <details>
          <summary>Nəyə əsaslanır?</summary>
          <p>{evidence}</p>
        </details>
      </div>
      <details className="guide-usage" open>
        <summary>Bu bölmədən necə istifadə etməli?</summary>
        <ol>{steps.map((step, index) => <li key={`${title}-${index}`}>{step}</li>)}</ol>
      </details>
      <p className="guide-boundary">Bu izah araşdırma üçündür; təkbaşına alış və ya satış siqnalı deyil.</p>
    </section>
  );
}
