import { useEffect, useState } from "react";

export default function LoginView({ authStatus, onLogin, onSetup, onReset, error }) {
  const [mode, setMode] = useState(authStatus?.setup_required ? "setup" : "login");
  const [busy, setBusy] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [setupUsername, setSetupUsername] = useState("");
  const [setupPassword, setSetupPassword] = useState("");
  const [setupConfirmPassword, setSetupConfirmPassword] = useState("");
  const [resetForm, setResetForm] = useState({
    currentUsername: "",
    newUsername: "",
    newPassword: "",
    confirmPassword: "",
  });

  useEffect(() => {
    setMode(authStatus?.setup_required ? "setup" : "login");
  }, [authStatus?.setup_required]);

  async function handleLoginSubmit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await onLogin(loginUsername, loginPassword);
    } finally {
      setBusy(false);
    }
  }

  async function handleSetupSubmit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await onSetup(setupUsername, setupPassword, setupConfirmPassword);
    } finally {
      setBusy(false);
    }
  }

  async function handleResetSubmit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await onReset({
        current_username: resetForm.currentUsername,
        new_username: resetForm.newUsername,
        new_password: resetForm.newPassword,
        confirm_password: resetForm.confirmPassword,
      });
    } finally {
      setBusy(false);
    }
  }

  function updateResetForm(field, value) {
    setResetForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  return (
    <div className="login-layout">
      <section className="login-brand-card">
        <img className="login-logo" src="https://i.postimg.cc/25NqkrQb/tresenso-logo.png" alt="Tresenso Tech logo" />
        <div className="login-badge">Tresenso Tech Pvt Ltd</div>
        <h2>Face Attendance Device</h2>
        <p>Portrait-ready operator console for quick enrollment, scanning, database lookup, and attendance history.</p>
        <div className="security-note">
          Password rules:
          <strong> 10+ characters, uppercase, lowercase, number, and symbol.</strong>
        </div>
      </section>

      <section className="login-card">
        <div className="eyebrow">Secure Access</div>
        <h3>{authStatus?.setup_required ? "Create Device Login" : "Login"}</h3>
        <p className="muted-copy">
          {authStatus?.setup_required
            ? "This device has no credentials yet. Create the first secure login."
            : "Sign in or reset the device login securely."}
        </p>

        {!authStatus?.setup_required ? (
          <div className="auth-toggle">
            <button
              className={`auth-toggle-button ${mode === "login" ? "active" : ""}`}
              onClick={() => setMode("login")}
              type="button"
            >
              Login
            </button>
            <button
              className={`auth-toggle-button ${mode === "reset" ? "active" : ""}`}
              onClick={() => setMode("reset")}
              type="button"
            >
              Reset
            </button>
          </div>
        ) : null}

        {error ? <div className="alert error">{error}</div> : null}

        {mode === "login" ? (
          <form className="form-stack" onSubmit={handleLoginSubmit}>
            <label>
              <span>Username</span>
              <input
                value={loginUsername}
                onChange={(event) => setLoginUsername(event.target.value)}
                placeholder="Enter username"
                required
              />
            </label>

            <label>
              <span>Password</span>
              <input
                type="password"
                value={loginPassword}
                onChange={(event) => setLoginPassword(event.target.value)}
                placeholder="Enter password"
                required
              />
            </label>

            <button className="button button-primary button-block" type="submit" disabled={busy}>
              {busy ? "Signing in..." : "Login"}
            </button>
          </form>
        ) : null}

        {mode === "setup" ? (
          <form className="form-stack" onSubmit={handleSetupSubmit}>
            <label>
              <span>Create Username</span>
              <input
                value={setupUsername}
                onChange={(event) => setSetupUsername(event.target.value)}
                placeholder="Create username"
                required
              />
            </label>

            <label>
              <span>Create Password</span>
              <input
                type="password"
                value={setupPassword}
                onChange={(event) => setSetupPassword(event.target.value)}
                placeholder="Create password"
                required
              />
            </label>

            <label>
              <span>Confirm Password</span>
              <input
                type="password"
                value={setupConfirmPassword}
                onChange={(event) => setSetupConfirmPassword(event.target.value)}
                placeholder="Confirm password"
                required
              />
            </label>

            <button className="button button-primary button-block" type="submit" disabled={busy}>
              {busy ? "Creating..." : "Create Login"}
            </button>
          </form>
        ) : null}

        {mode === "reset" ? (
          <form className="form-stack" onSubmit={handleResetSubmit}>
            <label>
              <span>Current Username</span>
              <input
                value={resetForm.currentUsername}
                onChange={(event) => updateResetForm("currentUsername", event.target.value)}
                placeholder="Current username"
                required
              />
            </label>

            <label>
              <span>New Username</span>
              <input
                value={resetForm.newUsername}
                onChange={(event) => updateResetForm("newUsername", event.target.value)}
                placeholder="New username"
                required
              />
            </label>

            <label>
              <span>New Password</span>
              <input
                type="password"
                value={resetForm.newPassword}
                onChange={(event) => updateResetForm("newPassword", event.target.value)}
                placeholder="New password"
                required
              />
            </label>

            <label>
              <span>Confirm New Password</span>
              <input
                type="password"
                value={resetForm.confirmPassword}
                onChange={(event) => updateResetForm("confirmPassword", event.target.value)}
                placeholder="Confirm new password"
                required
              />
            </label>

            <button className="button button-primary button-block" type="submit" disabled={busy}>
              {busy ? "Resetting..." : "Reset Login"}
            </button>
          </form>
        ) : null}
      </section>
    </div>
  );
}
