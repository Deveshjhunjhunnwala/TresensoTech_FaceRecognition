import { useEffect, useState } from "react";
import { apiClient, ApiError } from "./lib/api";
import LoginView from "./views/LoginView";
import OverviewView from "./views/OverviewView";
import EnrollView from "./views/EnrollView";
import RecognitionView from "./views/RecognitionView";
import WorkersView from "./views/WorkersView";
import AttendanceView from "./views/AttendanceView";

const TOKEN_KEY = "attendance_operator_token";

const VIEW_TITLES = {
  overview: {
    title: "Home",
    subtitle: "Choose one action to continue.",
  },
  enroll: {
    title: "New User",
    subtitle: "Add employee name, ID, and picture.",
  },
  recognize: {
    title: "Scan",
    subtitle: "Scan a face and mark attendance.",
  },
  workers: {
    title: "Database",
    subtitle: "View registered employees.",
  },
  attendance: {
    title: "Attendance History",
    subtitle: "View marked attendance records.",
  },
};

export default function App() {
  const [token, setToken] = useState(() => window.localStorage.getItem(TOKEN_KEY) || "");
  const [view, setView] = useState("overview");
  const [session, setSession] = useState(null);
  const [authStatus, setAuthStatus] = useState({
    configured: false,
    setup_required: true,
    source: "none",
  });
  const [status, setStatus] = useState(null);
  const [workers, setWorkers] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (token) {
      void loadDeviceData(token);
      return;
    }
    setSession(null);
    setStatus(null);
    setWorkers([]);
    setAttendance([]);
    void loadAuthStatus();
  }, [token]);

  async function loadAuthStatus() {
    setLoading(true);
    try {
      const authState = await apiClient.getAuthStatus();
      setAuthStatus(authState);
      setError("");
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Could not load login state.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function loadDeviceData(activeToken = token, silent = false) {
    if (!activeToken) {
      return;
    }

    if (silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const me = await apiClient.me(activeToken);
      const [statusData, workersData, attendanceData] = await Promise.all([
        apiClient.get("/api/v2/status", activeToken),
        apiClient.get("/api/v2/workers", activeToken),
        apiClient.get("/api/v2/attendance", activeToken),
      ]);
      setSession(me);
      setStatus(statusData);
      setWorkers(workersData);
      setAttendance(attendanceData);
      setAuthStatus({ configured: true, setup_required: false, source: "session" });
      setError("");
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Could not load the device data.";
      window.localStorage.removeItem(TOKEN_KEY);
      setToken("");
      setSession(null);
      setStatus(null);
      setWorkers([]);
      setAttendance([]);
      setError(message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  function storeSession(loginResponse) {
    window.localStorage.setItem(TOKEN_KEY, loginResponse.token);
    setToken(loginResponse.token);
    setView("overview");
  }

  async function handleLogin(username, password) {
    setError("");
    try {
      const response = await apiClient.login(username, password);
      storeSession(response);
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        setError(requestError.message);
        return;
      }
      throw requestError;
    }
  }

  async function handleSetup(username, password, confirmPassword) {
    setError("");
    try {
      const response = await apiClient.setupCredentials(username, password, confirmPassword);
      storeSession(response);
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        setError(requestError.message);
        return;
      }
      throw requestError;
    }
  }

  async function handleReset(payload) {
    setError("");
    try {
      const response = await apiClient.resetCredentials(payload);
      storeSession(response);
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
    setView("overview");
  }

  async function handleRefresh() {
    if (session) {
      await loadDeviceData(token, true);
      return;
    }
    await loadAuthStatus();
  }

  const viewMeta = VIEW_TITLES[view] ?? VIEW_TITLES.overview;

  return (
    <div className="device-shell">
      <main className="device-screen">
        {loading ? (
          <div className="loading-shell">
            <div className="loading-orb" />
            <div className="loading-copy">Loading device...</div>
          </div>
        ) : null}

        {!loading && !session ? (
          <LoginView
            authStatus={authStatus}
            onLogin={handleLogin}
            onSetup={handleSetup}
            onReset={handleReset}
            error={error}
          />
        ) : null}

        {!loading && session ? (
          <>
            <header className="device-header">
              <div>
                <div className="device-brand-line">Tresenso Face Attendance</div>
                <h1>{viewMeta.title}</h1>
                <p>{viewMeta.subtitle}</p>
              </div>

              <div className="device-header-actions">
                {view !== "overview" ? (
                  <button className="button button-ghost" onClick={() => setView("overview")}>Home</button>
                ) : null}
                <button className="button button-ghost" onClick={handleRefresh}>
                  {refreshing ? "Refreshing..." : "Refresh"}
                </button>
                <button className="button button-dark" onClick={handleLogout}>Logout</button>
              </div>
            </header>

            {error ? <div className="alert error">{error}</div> : null}

            {view === "overview" ? (
              <OverviewView
                status={status}
                onJump={setView}
              />
            ) : null}

            {view === "enroll" ? (
              <EnrollView token={token} onUpdated={() => loadDeviceData(token, true)} />
            ) : null}

            {view === "recognize" ? (
              <RecognitionView token={token} onUpdated={() => loadDeviceData(token, true)} />
            ) : null}

            {view === "workers" ? (
              <WorkersView
                token={token}
                workers={workers}
                onUpdated={() => loadDeviceData(token, true)}
              />
            ) : null}

            {view === "attendance" ? (
              <AttendanceView attendance={attendance} />
            ) : null}
          </>
        ) : null}
      </main>

      <footer className="device-footer">Made by Tresenso Tech Pvt Ltd</footer>
    </div>
  );
}
