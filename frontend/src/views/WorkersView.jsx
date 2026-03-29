import Panel from "../components/Panel";
import DataTable from "../components/DataTable";
import { apiClient } from "../lib/api";

export default function WorkersView({ token, workers, architecture, onUpdated }) {
  async function handleRemove(employeeCode) {
    await apiClient.del(`/api/v2/workers/${encodeURIComponent(employeeCode)}`, token);
    await onUpdated();
  }

  async function handleRebuildIndex() {
    await apiClient.post("/api/v2/index/rebuild", token);
    await onUpdated();
  }

  return (
    <div className="dashboard-grid">
      <Panel
        eyebrow="Directory Controls"
        title="Worker Register"
        actions={<button className="button button-secondary" onClick={handleRebuildIndex}>Rebuild Index</button>}
      >
        <div className="stack-grid two-col">
          <InfoPair label="Recognition Backend" value={architecture?.active_embedder || "-"} />
          <InfoPair label="Search Backend" value={architecture?.active_index || "-"} />
        </div>
      </Panel>

      <Panel eyebrow="Enrolled Personnel" title="Registered Workers" className="wide">
        <DataTable
          headers={["Employee Code", "Name", "Created", "Action"]}
          rows={workers.map((worker) => [
            worker.employee_code,
            worker.name,
            new Date(worker.created_at).toLocaleString(),
            <button
              className="button button-ghost button-small"
              key={worker.employee_code}
              onClick={() => handleRemove(worker.employee_code)}
            >
              Remove
            </button>,
          ])}
          emptyLabel="No workers enrolled yet."
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
