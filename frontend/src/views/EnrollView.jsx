import { useEffect, useRef, useState } from "react";
import Panel from "../components/Panel";
import { apiClient } from "../lib/api";
import { frameToBlob, startUserCamera, stopStream } from "../lib/media";

export default function EnrollView({ token, onUpdated }) {
  const [employeeCode, setEmployeeCode] = useState("");
  const [name, setName] = useState("");
  const [frames, setFrames] = useState([]);
  const [message, setMessage] = useState("Start the camera, capture multiple front-facing samples, then enroll.");
  const [busy, setBusy] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => () => stopStream(streamRef, videoRef), []);

  async function handleStartCamera() {
    await startUserCamera(videoRef, streamRef);
    setMessage("Camera is live. Capture at least 5 to 8 clear samples.");
  }

  async function handleCapture() {
    if (!videoRef.current || videoRef.current.readyState < 2) {
      setMessage("Camera is not ready yet.");
      return;
    }
    const blob = await frameToBlob(videoRef.current, canvasRef.current);
    const preview = URL.createObjectURL(blob);
    setFrames((current) => [
      ...current,
      { blob, preview, filename: `capture-${Date.now()}.jpg` },
    ]);
    setMessage("Sample captured.");
  }

  async function handleEnroll(event) {
    event.preventDefault();
    if (!frames.length) {
      setMessage("Capture at least one image before enrollment.");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("employee_code", employeeCode);
      form.append("name", name);
      form.append("replace_existing", "true");
      frames.forEach((frame) => form.append("images", frame.blob, frame.filename));
      await apiClient.post("/api/v2/workers/enroll", token, form);
      setEmployeeCode("");
      setName("");
      frames.forEach((frame) => URL.revokeObjectURL(frame.preview));
      setFrames([]);
      setMessage("Worker enrolled successfully and added to the active recognition index.");
      await onUpdated();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="dashboard-grid">
      <Panel eyebrow="Enrollment Form" title="Register a New Worker">
        <form className="form-stack" onSubmit={handleEnroll}>
          <label>
            <span>Employee Code</span>
            <input value={employeeCode} onChange={(event) => setEmployeeCode(event.target.value)} required />
          </label>
          <label>
            <span>Worker Name</span>
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>

          <div className="button-row">
            <button type="button" className="button button-secondary" onClick={handleStartCamera}>Start Camera</button>
            <button type="button" className="button button-ghost" onClick={handleCapture}>Capture Sample</button>
            <button type="submit" className="button button-primary" disabled={busy}>
              {busy ? "Enrolling..." : "Enroll Worker"}
            </button>
          </div>

          <div className="alert info">{message}</div>
        </form>
      </Panel>

      <Panel eyebrow="Live Capture" title="Enrollment Camera">
        <div className="video-frame">
          <video ref={videoRef} autoPlay playsInline muted />
          <canvas ref={canvasRef} hidden />
        </div>
        <div className="capture-strip">
          {frames.length ? frames.map((frame) => (
            <img key={frame.preview} src={frame.preview} alt="Enrollment capture" />
          )) : <div className="empty-state">Captured samples will appear here.</div>}
        </div>
      </Panel>
    </div>
  );
}
