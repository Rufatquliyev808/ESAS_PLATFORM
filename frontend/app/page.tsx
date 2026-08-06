"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ReplayPanel } from "./replay-panel";
import { PatternHypothesisRegistry } from "./pattern-hypothesis-registry";
import { ShadowRunsPanel } from "./shadow-runs-panel";
import { LiveTechnicalSummaryPanel } from "./live-technical-summary-panel";
import { DashboardSidebar, SectionGuide, type DashboardSection } from "./dashboard-navigation";

type Bridge = {
  source: string;
  module_version: string;
  symbol: string;
  queue_status: string;
  queue_count: number;
  queue_capacity: number;
  rejected_events: number;
  last_queue_error: string;
  reported_at: string;
  loss_acknowledged: boolean;
  acknowledged_rejected_events: number;
  loss_acknowledged_at: string | null;
  loss_acknowledged_by: string | null;
};

type Operational = {
  status: string;
  tick_stream: {
    status: string;
    seconds_since_last_tick: number | null;
    last_received_at: string | null;
    total_ticks: number;
  };
  bridge_delivery: { status: string; bridges: Bridge[] };
};

type Statistics = {
  total_ticks: number;
  unique_event_ids: number;
  duplicate_rows: number;
  symbol_count: number;
  first_tick: string | null;
  last_tick: string | null;
  last_received_at: string | null;
};

type DashboardData = { operational: Operational; statistics: Statistics };
type Tone = "good" | "warning" | "danger" | "info" | "neutral";

const API_BASE =
  process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";
const REFRESH_INTERVAL_MS = 5000;
// Operational aggregates can take several seconds on a large live database.
// Keep the browser responsive without declaring a healthy backend unavailable.
const REQUEST_TIMEOUT_MS = 10000;
const numberFormatter = new Intl.NumberFormat("az-AZ");
const dateTimeFormatter = new Intl.DateTimeFormat("az-AZ", {
  dateStyle: "medium",
  timeStyle: "medium",
});

const labels: Record<string, string> = {
  ok: "İşləyir",
  active: "Aktiv",
  stale: "Gecikib",
  waiting: "Gözləyir",
  healthy: "Sağlam",
  backlogged: "Növbə var",
  degraded: "Problem aşkarlanıb",
  full: "Növbə dolub",
  acknowledged: "Təsdiqlənib",
  unavailable: "Backend əlçatan deyil",
  none: "Xəta yoxdur",
};

const errorLabels: Record<string, string> = {
  none: "Xəta yoxdur",
  queue_full: "Disk növbəsi dolub",
  serialization_failed: "Event hazırlana bilmədi",
  disk_open_failed: "Növbə faylı açıla bilmədi",
  disk_seek_failed: "Növbə faylında mövqe xətası",
  disk_write_failed: "Event diskə yazıla bilmədi",
  corrupt_queue: "Növbə faylı zədələnib",
};

function toneFor(status: string): Tone {
  if (["ok", "active", "healthy", "none"].includes(status)) return "good";
  if (["stale", "backlogged"].includes(status)) return "warning";
  if (status === "acknowledged") return "warning";
  if (["degraded", "full", "unavailable"].includes(status)) return "danger";
  if (status === "waiting") return "info";
  return "neutral";
}

function formatNumber(value: number | null | undefined) {
  return numberFormatter.format(value ?? 0);
}

function formatTime(value: string | null | undefined) {
  if (!value) return "Hələ məlumat yoxdur";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Vaxt məlum deyil"
    : dateTimeFormatter.format(date);
}

function relativeSeconds(seconds: number | null | undefined) {
  if (seconds == null) return "Tick məlumatı gözlənilir";
  if (seconds < 1) return "İndi";
  if (seconds < 60) return `${Math.round(seconds)} saniyə əvvəl`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} dəqiqə əvvəl`;
  return `${Math.round(seconds / 3600)} saat əvvəl`;
}

function relativeDate(value: string | null | undefined) {
  if (!value) return "Hesabat gözlənilir";
  return relativeSeconds(Math.max(0, (Date.now() - new Date(value).getTime()) / 1000));
}

function currentQueueStatusFor(bridge: Bridge | undefined) {
  if (!bridge) return "waiting";
  return queueStatusForValues(bridge.queue_count, bridge.queue_capacity);
}

function queueStatusForValues(count: number, capacity: number) {
  if (count === 0) return "healthy";
  if (capacity > 0 && count >= capacity) return "full";
  return "backlogged";
}

function bridgeKey(bridge: Bridge) {
  return `${bridge.source}::${bridge.symbol}`;
}

function StatusPill({ status }: { status: string }) {
  return (
    <span className={`status-pill tone-${toneFor(status)}`}>
      <span className="status-dot" aria-hidden="true" />
      {labels[status] ?? status}
    </span>
  );
}

function StatusCard({
  eyebrow,
  title,
  status,
  value,
  detail,
  children,
}: {
  eyebrow: string;
  title: string;
  status: string;
  value: string;
  detail: string;
  children?: React.ReactNode;
}) {
  return (
    <article className={`status-card tone-border-${toneFor(status)}`}>
      <div className="card-topline">
        <p className="eyebrow">{eyebrow}</p>
        <StatusPill status={status} />
      </div>
      <h2>{title}</h2>
      <p className="card-value">{value}</p>
      <p className="card-detail">{detail}</p>
      {children}
    </article>
  );
}

async function fetchJson<T>(
  path: string,
  signal: AbortSignal,
  token: string | null,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    signal,
    cache: "no-store",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [userCode, setUserCode] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginBusy, setLoginBusy] = useState(false);
  const [data, setData] = useState<DashboardData | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [acknowledgementBusy, setAcknowledgementBusy] = useState(false);
  const [acknowledgementError, setAcknowledgementError] = useState<string | null>(null);
  const [selectedBridgeKey, setSelectedBridgeKey] = useState("all");
  const [activeSection, setActiveSection] = useState<DashboardSection>("results");
  const running = useRef(false);
  const activeController = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    setRefreshing(true);
    const controller = new AbortController();
    activeController.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const [operational, statistics] = await Promise.all([
        fetchJson<Operational>("/status/operational", controller.signal, token),
        fetchJson<Statistics>("/statistics/ticks", controller.signal, token),
      ]);
      if (!operational.tick_stream || !operational.bridge_delivery) {
        throw new Error("Backend response shape is invalid");
      }
      setData({ operational, statistics });
      setLastRefresh(new Date());
      setError(null);
    } catch (requestError) {
      console.error("ESAS dashboard refresh failed", requestError);
      if (requestError instanceof Error && requestError.message.includes("401")) {
        setToken(null);
        setData(null);
        setError(null);
        setLoginError("Sessiyanın vaxtı bitib. Yenidən daxil olun.");
        return;
      }
      setError(
        requestError instanceof SyntaxError
          ? "Backend cavabı gözlənilən formata uyğun deyil."
          : "Backend ilə əlaqə qurmaq mümkün olmadı. Son uğurlu məlumat göstərilir.",
      );
    } finally {
      window.clearTimeout(timeout);
      if (activeController.current === controller) {
        activeController.current = null;
      }
      running.current = false;
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;

    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") {
        void refresh();
      }
    };
    const initialRefresh = window.setTimeout(refreshWhenVisible, 0);
    const interval = window.setInterval(refreshWhenVisible, REFRESH_INTERVAL_MS);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    window.addEventListener("online", refreshWhenVisible);

    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
      window.removeEventListener("online", refreshWhenVisible);
      activeController.current?.abort();
    };
  }, [refresh, token]);

  async function handleLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginBusy(true);
    setLoginError(null);
    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_code: userCode, password }),
      });
      if (!response.ok) {
        throw new Error(
          response.status === 401
            ? "invalid"
            : response.status === 429
              ? "locked"
              : "unavailable",
        );
      }
      const result = (await response.json()) as { access_token: string };
      setToken(result.access_token);
      setPassword("");
    } catch (loginFailure) {
      setLoginError(
        loginFailure instanceof Error
          ? loginFailure.message === "invalid"
            ? "İstifadəçi kodu və ya parol yanlışdır."
            : loginFailure.message === "locked"
              ? "Çox sayda uğursuz cəhd oldu. 15 dəqiqə sonra yenidən yoxlayın."
              : "Giriş xidməti hazırda əlçatan deyil."
          : "Giriş xidməti hazırda əlçatan deyil.",
      );
    } finally {
      setLoginBusy(false);
    }
  }

  async function handleLogout() {
    if (token) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch {
        // Lokal sessiya istənilən halda dərhal bağlanır.
      }
    }
    setToken(null);
    setData(null);
  }

  const handleReplayUnauthorized = useCallback(() => {
    setToken(null);
    setData(null);
    setLoginError("Sessiyanın vaxtı bitib. Yenidən daxil olun.");
  }, []);

  async function handleLossAcknowledgement(bridge: Bridge) {
    const confirmed = window.confirm(
      `${formatNumber(bridge.rejected_events)} rədd edilmiş eventi gördüyünüzü təsdiqləyirsiniz? Sayğac silinməyəcək və audit tarixçəsində saxlanacaq.`,
    );
    if (!confirmed) return;

    setAcknowledgementBusy(true);
    setAcknowledgementError(null);
    try {
      const response = await fetch(`${API_BASE}/status/loss/acknowledge`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          source: bridge.source,
          symbol: bridge.symbol,
        }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      await refresh();
    } catch (acknowledgementFailure) {
      console.error("ESAS loss acknowledgement failed", acknowledgementFailure);
      setAcknowledgementError("Təsdiq yadda saxlanmadı. Yenidən cəhd edin.");
    } finally {
      setAcknowledgementBusy(false);
    }
  }

  const stats = useMemo(
    () =>
      data
        ? [
            ["Toplam tick", formatNumber(data.statistics.total_ticks)],
            ["Unikal event", formatNumber(data.statistics.unique_event_ids)],
            ["Dublikat sətir", formatNumber(data.statistics.duplicate_rows)],
            ["Simvol sayı", formatNumber(data.statistics.symbol_count)],
            ["İlk tick", formatTime(data.statistics.first_tick)],
            ["Son tick", formatTime(data.statistics.last_tick)],
          ]
        : [],
    [data],
  );

  if (!token) {
    return (
      <main className="login-main">
        <section className="login-card">
          <div className="brand-mark" aria-hidden="true">E</div>
          <p className="product-name">ESAS Platform</p>
          <h1>Monitorinq panelinə giriş</h1>
          <p className="login-intro">
            Platforma məlumatlarını görmək üçün istifadəçi kodunuzu və parolunuzu daxil edin.
          </p>
          <form onSubmit={handleLogin}>
            <label htmlFor="user-code">İstifadəçi kodu</label>
            <input
              id="user-code"
              autoComplete="username"
              value={userCode}
              onChange={(event) => setUserCode(event.target.value)}
              required
            />
            <label htmlFor="password">Parol</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={8}
            />
            {loginError && <p className="login-error" role="alert">{loginError}</p>}
            <button type="submit" disabled={loginBusy}>
              {loginBusy ? "Yoxlanılır..." : "Daxil ol"}
            </button>
          </form>
          <p className="login-footnote">Qorunan lokal giriş · Sessiya müddəti 8 saat</p>
        </section>
      </main>
    );
  }

  const bridges = data?.operational.bridge_delivery.bridges ?? [];
  const selectedBridge =
    selectedBridgeKey === "all"
      ? undefined
      : bridges.find((bridge) => bridgeKey(bridge) === selectedBridgeKey);
  const visibleBridges = selectedBridge ? [selectedBridge] : bridges;
  const queueCount = visibleBridges.reduce(
    (total, bridge) => total + bridge.queue_count,
    0,
  );
  const queueCapacity = visibleBridges.reduce(
    (total, bridge) => total + bridge.queue_capacity,
    0,
  );
  const rejectedEvents = visibleBridges.reduce(
    (total, bridge) => total + bridge.rejected_events,
    0,
  );
  const unacknowledgedBridges = visibleBridges.filter(
    (bridge) => bridge.rejected_events > 0 && !bridge.loss_acknowledged,
  );
  const queuePercent = queueCapacity
    ? (queueCount / queueCapacity) * 100
    : 0;
  const currentQueueStatus = bridges.length
    ? queueStatusForValues(queueCount, queueCapacity)
    : "waiting";
  const bridgeStatus = selectedBridge
    ? unacknowledgedBridges.length > 0
      ? "degraded"
      : currentQueueStatusFor(selectedBridge)
    : data?.operational.bridge_delivery.status ?? "waiting";
  const lossStatus = rejectedEvents === 0
    ? "healthy"
    : unacknowledgedBridges.length === 0
      ? "acknowledged"
      : "degraded";
  const overallStatus = error
    ? "unavailable"
    : data?.operational.status ?? "waiting";
  const sectionGuides: Record<DashboardSection, { title: string; metric: string; impact: string; evidence: string }> = {
    results: {
      title: "Nəticələrin ümumi görünüşü",
      metric: data ? `${formatNumber(data.statistics.total_ticks)} tick` : "Gözlənilir",
      impact: "Məlumat axını sağlamdırsa, GOLD üzrə sonrakı analizlər daha etibarlı məlumat üzərində hesablanır. Bu göstərici qiymətin istiqamətini özü müəyyən etmir.",
      evidence: "Ümumi tick sayı, son tick vaxtı, Bridge vəziyyəti, disk növbəsi və rədd edilən event sayı birlikdə yoxlanılır.",
    },
    live: {
      title: "Canlı məlumatın sağlamlığı",
      metric: data ? relativeSeconds(data.operational.tick_stream.seconds_since_last_tick) : "Gözlənilir",
      impact: "Gecikmə az və növbə boş olduqda GOLD qiyməti platformaya vaxtında çatır; gecikmə artdıqda analiz köhnə qiymətə əsaslana bilər.",
      evidence: `Son tick yaşı, ${formatNumber(queueCount)} / ${formatNumber(queueCapacity)} növbə istifadəsi və ${formatNumber(rejectedEvents)} rədd edilən event izlənir.`,
    },
    replay: {
      title: "Replay sessiyasının seçimi",
      metric: "Tarixi interval",
      impact: "Seçilən vaxt aralığı GOLD davranışının hansı bazar şəraitində öyrənildiyini müəyyən edir; nəticə yalnız həmin interval üçün keçərlidir.",
      evidence: "Sessiyanın simvolu, başlanğıc və son vaxtı, emal olunan event sayı və tamamlanma vəziyyəti saxlanılır.",
    },
    technical: {
      title: "Texniki göstəricilər",
      metric: "EMA · RSI · ATR",
      impact: "EMA istiqaməti, RSI momentumu, ATR isə GOLD-un dəyişkənliyini izah edir. Birlikdə kontekst verir, təkbaşına əməliyyat qərarı vermir.",
      evidence: "Yalnız bağlanmış barlardan EMA, RSI və ATR hesablanır; warm-up nöqtələri və hesablama izi ayrıca göstərilir.",
    },
    structure: {
      title: "Bazar strukturu",
      metric: "HH · HL · LH · LL",
      impact: "Ardıcıl HH/HL yüksəliş quruluşunu, LH/LL isə eniş quruluşunu dəstəkləyir. Qarışıq quruluş qeyri-müəyyənlik deməkdir.",
      evidence: "Təsdiqlənmiş pivot zirvə və dibləri müqayisə olunur; gələcək bar istifadə edilmir və hər pivotun vaxtı ilə qiyməti göstərilir.",
    },
    liquidity: {
      title: "Likvidlik müşahidəsi",
      metric: "Sweep · reclaim",
      impact: "Əvvəlki zirvə və ya dibin süpürülüb səviyyənin geri alınması GOLD-da saxta qırılma ehtimalını göstərə bilər.",
      evidence: "Bərabər zirvə/diblər, fitilin səviyyəni keçməsi və bağlanışın səviyyəni geri alması bağlanmış barlarla yoxlanılır.",
    },
    "bos-choch": {
      title: "BOS və CHoCH müşahidəsi",
      metric: "Qırılma · dönüş",
      impact: "BOS mövcud istiqamətin davamını, CHoCH isə GOLD strukturunda mümkün istiqamət dəyişikliyini göstərən müşahidədir.",
      evidence: "Təsdiqlənmiş struktur səviyyəsinin bağlanışla qırılması və qırılmadan əvvəlki struktur ardıcıllığı yoxlanılır.",
    },
    retest: {
      title: "Retest müşahidəsi",
      metric: "Səviyyəyə dönüş",
      impact: "Qırılmış səviyyənin yenidən yoxlanıb saxlanması hərəkətin davam etmə ehtimalını izah edə bilər; uğursuz retest əks riski artırır.",
      evidence: "BOS/CHoCH səviyyəsinə sonrakı toxunuş, barın reaksiyası və bağlanışın səviyyənin hansı tərəfində qalması ölçülür.",
    },
    fvg: {
      title: "Fair Value Gap müşahidəsi",
      metric: "Qiymət boşluğu",
      impact: "Bağlanmış barlar arasında yaranan doldurulmamış boşluq GOLD-un geri qayıdıb həmin qiyməti test etmə ehtimalını izah edə bilər.",
      evidence: "Üç ardıcıl bağlanmış bar arasındakı boşluq və onun sonrakı barlarla doldurulma/etibarsızlaşma vəziyyəti ölçülür.",
    },
    strategies: {
      title: "Strategiya müqayisəsi",
      metric: "Ayrı qaydalar",
      impact: "Fərqli qaydaların eyni GOLD məlumatında necə davrandığını müqayisə etməyə imkan verir; ən çox siqnal verən yanaşma mütləq ən yaxşı deyil.",
      evidence: "Hər strategiyanın versiyası, qaydası, hadisə sayı və eyni replay sessiyasındakı nəticəsi ayrı saxlanılır.",
    },
    hypotheses: {
      title: "Hipotez reyestri",
      metric: "Sınaq qaydaları",
      impact: "GOLD üçün ideyaları koddan ayrı və ölçülə bilən formada saxlayır; təsdiqlənməmiş hipotez canlı qərar kimi istifadə edilmir.",
      evidence: "Hipotezin adı, versiyası, şərtləri, vəziyyəti və sınaq qeydləri audit izi ilə saxlanılır.",
    },
    "pattern-candidates": {
      title: "Pattern namizədləri (draft)",
      metric: "Hipotez + detektor",
      impact: "Struktur, likvidlik və struktur qırılması/retest detektorlarının eyni anda üst-üstə düşməsi GOLD üçün daha güclü kontekst yarada bilər, amma bu hələ sübut deyil.",
      evidence: "Hər namizəd mövcud causal detektorların nəticəsini müvafiq hipotezə bağlayır; yalnız `draft` vəziyyətdədir, backtest və qəbul qərarı yoxdur.",
    },
    "shadow-runs": {
      title: "SHADOW run-ları (Phase 9 skelet)",
      metric: "Nəzəri portfolio",
      impact: "Real qərar generatoru (Phase 5-8) hazır olmadığı üçün bu bölmə hələ heç bir GOLD nəticəsinə təsir etmir — yalnız gələcək SHADOW sisteminin saxlama əsasını göstərir.",
      evidence: "Run manifesti, append-only event reyestri və nəzəri (real hesaba toxunmayan) mövqe/risk ledger-i əl ilə idarə olunur.",
    },
  };

  const sectionSteps: Record<DashboardSection, string[]> = {
    results: [
      "Əvvəl ümumi vəziyyəti və xəbərdarlıqları yoxlayın.",
      "Canlı məlumat sağlamdırsa nəticə bölmələrinə keçin.",
      "Qırmızı xəbərdarlıq varsa analizdən əvvəl Canlı məlumat bölməsini açın.",
    ],
    live: [
      "Son tick yaşını, Bridge vəziyyətini və disk növbəsini birlikdə yoxlayın.",
      "Gecikmə və ya növbə artımı varsa analizi köhnə məlumat kimi qiymətləndirin.",
      "Axın yenidən sağlam olduqdan sonra nəticələri yeniləyin.",
    ],
    replay: [
      "Simvolu, başlanğıc və son vaxtı, sonra replay rejimini seçin.",
      "Replay yaradın və tamamlanmasını gözləyin.",
      "Tamamlanmış sessiyanı seçib digər analiz bölmələrinə keçin.",
    ],
    technical: [
      "Tamamlanmış replay sessiyasının seçildiyini yoxlayın.",
      "EMA, RSI və ATR dövrlərini seçib analizi hesablayın.",
      "Rəqəmləri birlikdə şərh edin; heç biri təkbaşına siqnal deyil.",
    ],
    structure: [
      "HH/HL və LH/LL ardıcıllığını müqayisə edin.",
      "Təsdiqlənmiş pivotların vaxt və qiymətinə baxın.",
      "Qarışıq strukturda istiqamət nəticəsi çıxarmayın.",
    ],
    liquidity: [
      "Əvvəlki zirvə və dib ətrafındakı süpürülmələri tapın.",
      "Səviyyənin bağlanışla geri alınıb-alınmadığını yoxlayın.",
      "Nəticəni BOS/CHoCH və retest müşahidəsi ilə birləşdirin.",
    ],
    "bos-choch": [
      "Qırılan səviyyəni və qırılmadan əvvəlki strukturu yoxlayın.",
      "BOS-u davam, CHoCH-u mümkün dəyişiklik müşahidəsi kimi oxuyun.",
      "Tək qırılmaya görə qərar verməyin; likvidlik və retest təsdiqi axtarın.",
    ],
    retest: [
      "Qırılmış səviyyəyə sonrakı qayıdışı yoxlayın.",
      "Bağlanışın səviyyəni saxlayıb-saxlamadığını müqayisə edin.",
      "Uğursuz retesti əks risk, uğurlu retesti isə əlavə müşahidə kimi qəbul edin.",
    ],
    fvg: [
      "Bağlanmış barlar arasında yaranan boşluğun istiqamətinə baxın.",
      "Doldurulma faizini və sonuncu vəziyyəti (açıq, qismən, tam, etibarsız) yoxlayın.",
      "Boşluğu təkbaşına deyil, struktur və likvidlik müşahidəsi ilə birlikdə qiymətləndirin.",
    ],
    strategies: [
      "Eyni replay sessiyasında strategiya versiyalarını müqayisə edin.",
      "Hadisə sayı ilə yanaşı sabitlik və xərc ssenarilərinə baxın.",
      "Çox siqnalı avtomatik olaraq daha yaxşı nəticə saymayın.",
    ],
    hypotheses: [
      "Qaydanı ölçülə bilən və versiyalanmış hipotez kimi qeyd edin.",
      "Hipotezi ayrıca replay məlumatında sınayın.",
      "Yalnız təkrar yoxlamalarda sabit qalan müşahidəni növbəti mərhələyə keçirin.",
    ],
    "pattern-candidates": [
      "Hər namizədin `draft` vəziyyətdə olduğunu, sübut olmadığını xatırlayın.",
      "Şərti təsdiqlənən (candidate_confirmed) namizədlərin sübutunu digər bölmələrdən yoxlayın.",
      "Backtest və qəbul qərarı hələ yoxdur; namizədi əməliyyat üçün istifadə etməyin.",
    ],
    "shadow-runs": [
      "Bu, əl ilə idarə olunan bir skeletdir — avtomatik qərar axını yoxdur.",
      "\"NƏZƏRİDİR\" bannerini həmişə diqqətdə saxlayın; heç bir order və ya real mövqe yaranmır.",
      "Run-ı yalnız test/araşdırma məqsədilə yaradın və nəticələrini ticarət qərarı kimi istifadə etməyin.",
    ],
  };

  return (
    <main>
      <header className="app-header">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">E</div>
          <div>
            <p className="product-name">ESAS Platform</p>
            <h1>Məlumat axınının monitorinqi</h1>
          </div>
        </div>
        <div className="header-status">
          <StatusPill status={overallStatus} />
          <p>
            Son yenilənmə:{" "}
            <strong>{lastRefresh ? formatTime(lastRefresh.toISOString()) : "gözlənilir"}</strong>
          </p>
          <button
            className="refresh-button"
            type="button"
            disabled={refreshing}
            onClick={() => void refresh()}
          >
            {refreshing ? "Yenilənir..." : "Yenilə"}
          </button>
          <button
            className="logout-button"
            type="button"
            onClick={() => void handleLogout()}
          >
            Çıxış
          </button>
        </div>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <span aria-hidden="true">!</span>
          <p>{error}</p>
          <button type="button" onClick={() => void refresh()}>Yenidən yoxla</button>
        </div>
      )}

      {!data ? (
        <section className="loading-panel" aria-live="polite">
          <span className="loading-ring" aria-hidden="true" />
          <div>
            <h2>Platforma qoşulur</h2>
            <p>Backend və MT5 Bridge vəziyyəti yoxlanılır.</p>
          </div>
        </section>
      ) : (
        <>
          <div className="dashboard-shell">
            <DashboardSidebar active={activeSection} onSelect={setActiveSection} />
            <div className="dashboard-workspace">
              <SectionGuide {...sectionGuides[activeSection]} steps={sectionSteps[activeSection]} />
              {activeSection === "results" && (
                <section className="panel results-overview" aria-labelledby="results-overview-title">
                  <div className="section-heading">
                    <div><p className="eyebrow">Defolt görünüş</p><h2 id="results-overview-title">Nəticələr</h2></div>
                    <StatusPill status={overallStatus} />
                  </div>
                  <div className="result-summary-grid">
                    <article><span>Canlı GOLD məlumatı</span><strong>{relativeSeconds(data.operational.tick_stream.seconds_since_last_tick)}</strong><p>Son qiymətin platformaya çatma vaxtı.</p></article>
                    <article><span>Toplanan məlumat</span><strong>{formatNumber(data.statistics.total_ticks)}</strong><p>Analiz üçün bazada olan ümumi tick sayı.</p></article>
                    <article><span>Disk növbəsi</span><strong>{formatNumber(queueCount)} / {formatNumber(queueCapacity)}</strong><p>Backend dayanarsa qorunan eventlər.</p></article>
                    <article><span>Məlumat itkisi</span><strong>{formatNumber(rejectedEvents)}</strong><p>Qəbul edilməyən eventlərin sayı.</p></article>
                  </div>
                  <div className="result-interpretation">
                    <h3>Bu nəticə nə deyir?</h3>
                    <p>{error ? "Backend hazırda əlçatan deyil; son uğurlu məlumat göstərilir." : queueCount === 0 && data.operational.tick_stream.status === "active" ? "Məlumat axını aktivdir və növbə boşdur. Texniki analiz üçün giriş məlumatı normal görünür." : "Məlumat axınında gecikmə və ya növbə var. Analiz nəticələrini şərh etməzdən əvvəl Canlı məlumat bölməsini yoxlayın."}</p>
                  </div>
                </section>
              )}
              {activeSection === "results" && token && (
                <LiveTechnicalSummaryPanel token={token} onUnauthorized={handleReplayUnauthorized} />
              )}
              {activeSection === "live" && (
                <>
          <section className="bridge-filter" aria-labelledby="bridge-filter-title">
            <div>
              <p className="eyebrow">Görünüş filtri</p>
              <h2 id="bridge-filter-title">Bridge və simvol seçimi</h2>
            </div>
            <label htmlFor="bridge-select">Göstərilən məlumat</label>
            <select
              id="bridge-select"
              value={selectedBridge ? selectedBridgeKey : "all"}
              onChange={(event) => setSelectedBridgeKey(event.target.value)}
            >
              <option value="all">
                Bütün Bridge-lər ({formatNumber(bridges.length)})
              </option>
              {bridges.map((bridge) => (
                <option key={bridgeKey(bridge)} value={bridgeKey(bridge)}>
                  {bridge.symbol} · {bridge.source}
                </option>
              ))}
            </select>
          </section>

          <section className="status-grid" aria-label="Əsas vəziyyət göstəriciləri">
            <StatusCard
              eyebrow="Bazar məlumatı"
              title="Tick axını"
              status={data.operational.tick_stream.status}
              value={relativeSeconds(data.operational.tick_stream.seconds_since_last_tick)}
              detail={formatTime(data.operational.tick_stream.last_received_at)}
            />
            <StatusCard
              eyebrow="Çatdırılma"
              title="MT5 Bridge"
              status={bridgeStatus}
              value={
                selectedBridge
                  ? selectedBridge.symbol
                  : bridges.length
                    ? `${formatNumber(bridges.length)} Bridge`
                    : "Hesabat gözlənilir"
              }
              detail={
                selectedBridge
                  ? `Versiya ${selectedBridge.module_version} · ${relativeDate(selectedBridge.reported_at)}`
                  : bridges.length
                    ? `${formatNumber(bridges.length)} aktiv hesabat birlikdə göstərilir`
                  : "MT5 Bridge hesabatı hələ alınmayıb"
              }
            />
            <StatusCard
              eyebrow="Davamlılıq"
              title="Disk növbəsi"
              status={currentQueueStatus}
              value={
                bridges.length
                  ? `${formatNumber(queueCount)} / ${formatNumber(queueCapacity)} event`
                  : "Hesabat gözlənilir"
              }
              detail={
                bridges.length
                  ? queueCount === 0
                    ? errorLabels.none
                    : selectedBridge
                      ? errorLabels[selectedBridge.last_queue_error] ??
                        selectedBridge.last_queue_error
                      : `${formatNumber(
                          visibleBridges.filter((bridge) => bridge.queue_count > 0).length,
                        )} Bridge-də gözləyən event var`
                  : "Növbə məlumatı yoxdur"
              }
            >
              <div
                className="queue-track"
                role="progressbar"
                aria-label="Disk növbəsinin istifadəsi"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={Math.min(100, queuePercent)}
              >
                <span style={{ width: `${Math.min(100, queuePercent)}%` }} />
              </div>
              <p className="queue-caption">{queuePercent.toFixed(1)}% istifadə olunur</p>
            </StatusCard>
            <StatusCard
              eyebrow="Təhlükəsizlik"
              title="Məlumat itkisi"
              status={lossStatus}
              value={`${formatNumber(rejectedEvents)} rədd edilən event`}
              detail={
                rejectedEvents === 0
                  ? "Aşkarlanmış məlumat itkisi yoxdur"
                  : unacknowledgedBridges.length === 0
                    ? selectedBridge
                      ? `${formatTime(selectedBridge.loss_acknowledged_at)} tarixində ${selectedBridge.loss_acknowledged_by} tərəfindən təsdiqlənib`
                      : "Bütün qeydə alınmış məlumat itkisi hadisələri təsdiqlənib"
                    : `${formatNumber(unacknowledgedBridges.length)} Bridge üzrə təsdiqlənməmiş hadisə var`
              }
            >
              {selectedBridge &&
                selectedBridge.rejected_events > 0 &&
                !selectedBridge.loss_acknowledged && (
                  <button
                    className="acknowledge-button"
                    type="button"
                    disabled={acknowledgementBusy}
                    onClick={() => void handleLossAcknowledgement(selectedBridge)}
                  >
                    {acknowledgementBusy ? "Yadda saxlanılır..." : "Hadisəni təsdiqlə"}
                  </button>
                )}
              {!selectedBridge && unacknowledgedBridges.length > 0 && (
                <p className="selection-hint">
                  Təsdiq üçün yuxarıdan problemli Bridge-i seçin.
                </p>
              )}
              {acknowledgementError && (
                <p className="acknowledgement-error" role="alert">
                  {acknowledgementError}
                </p>
              )}
            </StatusCard>
          </section>

          <section className="panel" aria-labelledby="statistics-title">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Məlumat bazası</p>
                <h2 id="statistics-title">Toplanma statistikası</h2>
              </div>
              <p className="section-note">Canlı backend göstəriciləri</p>
            </div>
            <div className="stats-grid">
              {stats.map(([label, value]) => (
                <div className="stat-item" key={label}>
                  <p>{label}</p>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="panel" aria-labelledby="bridges-title">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Əlaqəli terminallar</p>
                <h2 id="bridges-title">Bridge detalları</h2>
              </div>
              <p className="section-note">
                {data.operational.bridge_delivery.bridges.length} aktiv hesabat
              </p>
            </div>
            {data.operational.bridge_delivery.bridges.length === 0 ? (
              <div className="empty-state">MT5 Bridge hesabatı gözlənilir.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Simvol</th>
                      <th>Versiya</th>
                      <th>Vəziyyət</th>
                      <th>Növbə</th>
                      <th>Rədd edilən</th>
                      <th>Son hesabat</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.operational.bridge_delivery.bridges.map((bridge) => (
                      <tr key={`${bridge.source}-${bridge.symbol}`}>
                        <td><strong>{bridge.symbol}</strong></td>
                        <td>{bridge.module_version}</td>
                        <td><StatusPill status={currentQueueStatusFor(bridge)} /></td>
                        <td>{formatNumber(bridge.queue_count)} / {formatNumber(bridge.queue_capacity)}</td>
                        <td className={
                          bridge.rejected_events > 0 && !bridge.loss_acknowledged
                            ? "danger-text"
                            : bridge.rejected_events > 0
                              ? "acknowledged-text"
                              : ""
                        }>
                          {formatNumber(bridge.rejected_events)}
                          {bridge.loss_acknowledged && <small>Təsdiqlənib</small>}
                        </td>
                        <td>
                          <strong>{relativeDate(bridge.reported_at)}</strong>
                          <small>{formatTime(bridge.reported_at)}</small>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
                </>
              )}
              {(["replay", "technical", "structure", "liquidity", "bos-choch", "retest", "fvg", "strategies", "pattern-candidates"] as DashboardSection[]).includes(activeSection) && (
          <ReplayPanel
            view={activeSection}
            token={token}
            onUnauthorized={handleReplayUnauthorized}
            onOpenReplay={() => setActiveSection("replay")}
          />
              )}
              {activeSection === "hypotheses" && (
          <PatternHypothesisRegistry
            token={token}
            onUnauthorized={handleReplayUnauthorized}
          />
              )}
              {activeSection === "shadow-runs" && (
          <ShadowRunsPanel
            token={token}
            onUnauthorized={handleReplayUnauthorized}
          />
              )}
            </div>
          </div>
        </>
      )}

      <footer>
        <p>Yalnız monitorinq · Ticarət əməliyyatı aparılmır</p>
        <p>Avtomatik yenilənmə: səhifə aktiv olduqda 5 saniyə</p>
      </footer>
    </main>
  );
}
