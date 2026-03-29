export default function Sidebar({ items, currentView, onChangeView, username, onLogout }) {
  return (
    <aside className="sidebar">
      <div className="brand-block">
        <div className="brand-mark">IA</div>
        <div>
          <h1>Industrial Attendance</h1>
          <p>Operator-grade face recognition console</p>
        </div>
      </div>

      <div className="sidebar-section-label">Workspace</div>
      <nav className="nav-list">
        {items.map((item) => (
          <button
            key={item.key}
            className={`nav-item ${currentView === item.key ? "active" : ""}`}
            onClick={() => onChangeView(item.key)}
          >
            <span className="nav-item-label">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <div className="operator-chip">
          <span className="operator-chip-label">Signed in as</span>
          <strong>{username}</strong>
        </div>
        <button className="button button-dark" onClick={onLogout}>Sign out</button>
      </div>
    </aside>
  );
}
