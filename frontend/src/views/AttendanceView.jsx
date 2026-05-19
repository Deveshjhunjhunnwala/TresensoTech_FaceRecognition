import Panel from "../components/Panel";
import DataTable from "../components/DataTable";
import { formatServerDate, formatServerTime } from "../lib/datetime";

export default function AttendanceView({ attendance }) {
  return (
    <Panel eyebrow="Attendance Records" title="Attendance History">
      <DataTable
        headers={[
          "Employee ID",
          "Date",
          "Time",
          "Attendance",
          "Intoxication",
          "Alcohol",
          "Cannabis"
        ]}
        rows={attendance.map((row) => [
          row.name,
          row.employee_code,
          formatServerDate(row.created_at),
          formatServerTime(row.created_at),
          "Marked",
          row.intoxication_status || "Clear",
          row.alcohol_level || "-",
          row.cannabis_level || "-",
        ])}
        emptyLabel="No attendance has been marked yet."
      />
    </Panel>
  );
}
