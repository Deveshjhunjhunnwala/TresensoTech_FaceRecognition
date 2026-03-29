import { useCallback, useEffect, useMemo, useState } from "react";
import { apiClient, ApiError } from "./lib/api";
import LoginView from "./views/LoginView";
import OverviewView from "./views/OverviewView";
import EnrollView from "./views/EnrollView";
import RecognitionView from "./views/RecognitionView";
import WorkersView from "./views/WorkersView";
import AttendanceView from "./views/AttendanceView";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";

const TOKEN_KEY = "attendance_operator_token";

export const NAV_ITEMS = [
  { key: "overview", label: "Overview" },
  { key: "enroll", label: "Add New Face" },
  { key: "recognize", label: "Detect Face" },
  { key: "workers", label: "Worker List" },
  { key: "attendance", label: "Attendance" },
];

const VIEW_TITLES = {
  overview: {
    eyebrow: "Operations Centre",
    title: "System Overview",
    subtitle: "Monitor enrollment, live recognition, and workforce movement from one operator console.",
  },
  enroll: {
    eyebrow: "Enrollment",
    title: "Add New Face",
    subtitle: "Capture high-quality face samples directly from the operator camera before indexing them.",
  },
  recognize: {
    eyebrow: "Recognition",
    title: "Live Detection Console",
    subtitle: "Run continuous face recognition, inspect matches, and review decision traces in real time.",
  },
  workers: {
    eyebrow: "Directory",
    title: "Worker Register",
    subtitle: "Audit enrolled identities, remove old records, and keep the employee directory clean.",
  },
  attendance: {
    eyebrow: "Attendance",
    title: "Attendance Ledger",
    subtitle: "Review the latest worker check-ins recorded by the live recognition pipeline.",
  },
};

export default function App() {
  const [token, setToken] = useState(() => window.localStorage.getItem(TOKEN_KEY) || "");
  const [view, setView] = useState("overview");
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState(null);
  const [architecture, setArchitecture] = useState(null);
  const [workers, setWorkers] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const viewMeta = VIEW_TITLES[view] ?? VIEW_TITLES.overview;

  const loadDashboard = useCallback(async (activeToken = token, silent = false) => {
    if (!activeToken) {
      return;
    }
    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");
    try {
      const me = await apiClient.me(activeToken);
      const [statusData, architectureData, workersData, attendanceData] = await Promise.all([
        apiClient.get("/api/v2/status", activeToken),
        apiClient.get("/api/v2/architecture", activeToken),
        apiClient.get("/api/v2/workers", activeToken),
        apiClient.get("/api/v2/attendance", activeToken),
      ]);
      setSession(me);
      setStatus(statusData);
      setArchitecture(architectureData);
      setWorkers(workersData);
      setAttendance(attendanceData);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Could not load the operator workspace.";
      setError(message);
      window.localStorage.removeItem(TOKEN_KEY);
      setToken("");
      setSession(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) {
      setSession(null);
      setLoading(false);
      return;
    }
    loadDashboard(token);
  }, [token, loadDashboard]);

  const metrics = useMemo(() => ([
    { label: "Workers", value: workers.length, tone: "teal" },
    { label: "Indexed Faces", value: status?.indexed_embeddings ?? 0, tone: "cyan" },
    { label: "Attendance Events", value: status?.attendance_events ?? 0, tone: "slate" },
    { label: "Live Cache", value: status?.cache_entries ?? 0, tone: "amber" },
  ]), [status, workers]);

  async function handleLogin(username, password) {
    setError("");
    try {
      const response = await apiClient.login(username, password);
      window.localStorage.setItem(TOKEN_KEY, response.token);
      setToken(response.token);
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        setError(requestError.message);
        return;
      }
      throw requestError;
    }
  }

  async function handleLogout() {
    if (token) {
      try {
        await apiClient.post("/api/v2/auth/logout", token);
      } catch {}
    }
    window.localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setSession(null);
    setStatus(null);
    setArchitecture(null);
    setWorkers([]);
    setAttendance([]);
  }

  async function handleRefresh() {
    await loadDashboard(token, true);
  }

  if (loading && !session) {
    return (
      <div className="loading-shell">
        <div className="loading-orb" />
        <div className="loading-copy">Loading operator workspace...</div>
      </div>
    );
  }

  if (!session) {
    return <LoginView onLogin={handleLogin} error={error} />;
  }

  return (
    <div className="app-shell">
      <Sidebar
        items={NAV_ITEMS}
        currentView={view}
        onChangeView={setView}
        username={session.username}
        onLogout={handleLogout}
      />
      <main className="main-shell">
        <Topbar
          eyebrow={viewMeta.eyebrow}
          title={viewMeta.title}
          subtitle={viewMeta.subtitle}
          onRefresh={handleRefresh}
          refreshing={refreshing}
        />

        {error ? <div className="alert error">{error}</div> : null}

        {view === "overview" ? (
          <OverviewView
            metrics={metrics}
            architecture={architecture}
            status={status}
            attendance={attendance}
            onJump={setView}
          />
        ) : null}

        {view === "enroll" ? (
          <EnrollView token={token} onUpdated={() => loadDashboard(token, true)} />
        ) : null}

        {view === "recognize" ? (
          <RecognitionView token={token} onUpdated={() => loadDashboard(token, true)} />
        ) : null}

        {view === "workers" ? (
          <WorkersView
            token={token}
            workers={workers}
            architecture={architecture}
            onUpdated={() => loadDashboard(token, true)}
          />
        ) : null}

        {view === "attendance" ? (
          <AttendanceView
            token={token}
            attendance={attendance}
            onUpdated={() => loadDashboard(token, true)}
          />
        ) : null}
      </main>
    </div>
  );
}
