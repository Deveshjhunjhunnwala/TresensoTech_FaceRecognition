export default function Topbar({ eyebrow, title, subtitle, onRefresh, refreshing }) {
  return (
    <header className="topbar">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      <button className="button button-ghost" onClick={onRefresh}>
        {refreshing ? "Refreshing..." : "Refresh Data"}
      </button>
    </header>
  );
}
