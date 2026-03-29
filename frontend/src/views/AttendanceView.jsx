import Panel from "../components/Panel";
import DataTable from "../components/DataTable";
import { apiClient } from "../lib/api";
import { formatServerDateTime } from "../lib/datetime";

export default function AttendanceView({ token, attendance, onUpdated }) {
  async function handleDelete(attendanceId) {
    const confirmed = window.confirm("Delete this attendance record?");
    if (!confirmed) {
      return;
    }
    await apiClient.del(`/api/v2/attendance/${attendanceId}`, token);
    await onUpdated();
  }

  return (
    <Panel eyebrow="Audit Trail" title="Attendance History">
      <DataTable
        headers={["Worker", "Code", "Camera", "Matched Score", "Time", "Action"]}
        rows={attendance.map((row) => [
          row.name,
          row.employee_code,
          row.camera_id,
          Number(row.matched_score).toFixed(3),
          formatServerDateTime(row.created_at),
          <button
            className="button button-ghost button-small"
            key={row.id}
            onClick={() => handleDelete(row.id)}
          >
            Delete
          </button>,
        ])}
        emptyLabel="No attendance events recorded yet."
      />
    </Panel>
  );
}
