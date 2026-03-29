import Panel from "../components/Panel";
import MetricCard from "../components/MetricCard";
import DataTable from "../components/DataTable";
import { formatServerDateTime } from "../lib/datetime";

const ACTIONS = [
  { key: "enroll", label: "Add New Face", description: "Capture and index a new worker." },
  { key: "recognize", label: "Detect Face", description: "Open the live recognition console." },
  { key: "workers", label: "Worker List", description: "Audit enrolled employee records." },
  { key: "attendance", label: "Attendance", description: "Inspect the latest worker check-ins." },
];

export default function OverviewView({ metrics, architecture, status, attendance, onJump }) {
  return (
    <div className="dashboard-grid">
      <section className="hero-metrics">
        {metrics.map((metric) => (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            tone={metric.tone}
          />
        ))}
      </section>

      <Panel eyebrow="Active Pipeline" title="Recognition Architecture">
        <div className="stack-grid two-col">
          <InfoPair label="Detector" value={architecture?.detector || "-"} />
          <InfoPair label="Embedder" value={architecture?.active_embedder || "-"} />
          <InfoPair label="Vector Index" value={architecture?.active_index || "-"} />
          <InfoPair label="Fallbacks" value={status?.fallback_enabled ? "Enabled" : "Disabled"} />
        </div>
        {architecture?.warnings?.length ? (
          <div className="warning-list">
            {architecture.warnings.map((warning) => <div key={warning} className="alert warning">{warning}</div>)}
          </div>
        ) : (
          <div className="alert success">Recognition stack is active with no current backend warnings.</div>
        )}
      </Panel>

      <Panel eyebrow="Operations" title="Primary Actions">
        <div className="action-grid">
          {ACTIONS.map((action) => (
            <button key={action.key} className="action-tile" onClick={() => onJump(action.key)}>
              <span>{action.label}</span>
              <small>{action.description}</small>
            </button>
          ))}
        </div>
      </Panel>

      <Panel eyebrow="Recent Activity" title="Latest Attendance Events" className="wide">
        <DataTable
          headers={["Worker", "Code", "Camera", "Time"]}
          rows={attendance.slice(0, 8).map((row) => [
            row.name,
            row.employee_code,
            row.camera_id,
            formatServerDateTime(row.created_at),
          ])}
          emptyLabel="No attendance events recorded yet."
        />
      </Panel>
    </div>
  );
}

function InfoPair({ label, value }) {
  return (
    <div className="info-pair">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
