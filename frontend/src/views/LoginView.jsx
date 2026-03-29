import { useState } from "react";

export default function LoginView({ onLogin, error }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await onLogin(username, password);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-layout">
      <section className="login-promo">
        <div className="login-badge">Industrial Facial Recognition</div>
        <h1>Secure workforce attendance, live monitoring, and operator-led verification from a single control surface.</h1>
        <p>
          Built for plant floors, factory gates, warehouses, and secured industrial entry points where speed and traceability matter.
        </p>
        <div className="login-promo-grid">
          <div>
            <span>Live Detection</span>
            <strong>Operator camera loop</strong>
          </div>
          <div>
            <span>Worker Records</span>
            <strong>Enrollment and removal</strong>
          </div>
          <div>
            <span>Attendance Logs</span>
            <strong>Immediate review</strong>
          </div>
        </div>
      </section>

      <form className="login-card" onSubmit={handleSubmit}>
        <div className="eyebrow">Authentication</div>
        <h2>Enter Operator Workspace</h2>
        <p className="muted-copy">Use authorized credentials to access enrollment, live detection, and attendance operations.</p>

        <label>
          <span>Username</span>
          <input value={username} onChange={(event) => setUsername(event.target.value)} required />
        </label>

        <label>
          <span>Password</span>
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>

        {error ? <div className="alert error">{error}</div> : null}

        <button className="button button-primary" type="submit" disabled={busy}>
          {busy ? "Authenticating..." : "Access Dashboard"}
        </button>
      </form>
    </div>
  );
}
