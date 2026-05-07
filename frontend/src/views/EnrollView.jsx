import { useEffect, useRef, useState } from "react";
import Panel from "../components/Panel";
import { apiClient } from "../lib/api";
import { frameToBlob, startUserCamera, stopStream } from "../lib/media";

export default function EnrollView({ token, onUpdated }) {
  const [employeeCode, setEmployeeCode] = useState("");
  const [name, setName] = useState("");
  const [frames, setFrames] = useState([]);
  const [message, setMessage] = useState("Enter the employee details and add at least one picture.");
  const [busy, setBusy] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const framesRef = useRef([]);

  useEffect(() => {
    framesRef.current = frames;
  }, [frames]);

  useEffect(() => {
    return () => {
      stopStream(streamRef, videoRef);
      framesRef.current.forEach((frame) => URL.revokeObjectURL(frame.preview));
    };
  }, []);

  function appendFiles(files) {
    const nextFrames = Array.from(files).map((file) => ({
      blob: file,
      preview: URL.createObjectURL(file),
      filename: file.name || `upload-${Date.now()}.jpg`,
    }));
    setFrames((current) => [...current, ...nextFrames]);
  }

  function clearFrames() {
    frames.forEach((frame) => URL.revokeObjectURL(frame.preview));
    setFrames([]);
  }

  async function handleStartCamera() {
    try {
      await startUserCamera(videoRef, streamRef);
      setMessage("Camera is live. Capture a clear face picture.");
    } catch (requestError) {
      const text = requestError instanceof Error ? requestError.message : "Camera could not be started.";
      setMessage(text);
    }
  }

  async function handleCapture() {
    if (!videoRef.current || videoRef.current.readyState < 2) {
      setMessage("Camera is not ready.");
      return;
    }
    const blob = await frameToBlob(videoRef.current, canvasRef.current);
    const preview = URL.createObjectURL(blob);
    setFrames((current) => [
      ...current,
      { blob, preview, filename: `capture-${Date.now()}.jpg` },
    ]);
    setMessage("Picture captured.");
  }

  async function handleEnroll(event) {
    event.preventDefault();
    if (!frames.length) {
      setMessage("Add at least one employee picture.");
      return;
    }

    setBusy(true);
    try {
      const form = new FormData();
      form.append("employee_code", employeeCode.trim());
      form.append("name", name.trim());
      form.append("replace_existing", "true");
      frames.forEach((frame) => form.append("images", frame.blob, frame.filename));
      await apiClient.post("/api/v2/workers/enroll", token, form);
      setEmployeeCode("");
      setName("");
      clearFrames();
      setMessage("New user added successfully.");
      await onUpdated();
    } catch (requestError) {
      const text = requestError instanceof Error ? requestError.message : "Could not add the new user.";
      setMessage(text);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="device-stack">
      <Panel eyebrow="Step 1" title="Employee Details">
        <form className="form-stack" onSubmit={handleEnroll}>
          <label>
            <span>Employee ID</span>
            <input
              value={employeeCode}
              onChange={(event) => setEmployeeCode(event.target.value)}
              placeholder="Enter employee ID"
              required
            />
          </label>

          <label>
            <span>Name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Enter employee name"
              required
            />
          </label>

          <label className="file-picker">
            <span>Upload Picture</span>
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={(event) => {
                if (event.target.files?.length) {
                  appendFiles(event.target.files);
                  setMessage("Picture added.");
                  event.target.value = "";
                }
              }}
            />
          </label>

          <div className="button-row">
            <button className="button button-secondary" onClick={handleStartCamera} type="button">Open Camera</button>
            <button className="button button-ghost" onClick={handleCapture} type="button">Take Picture</button>
            <button className="button button-ghost" onClick={clearFrames} type="button">Clear Pictures</button>
            <button className="button button-primary" type="submit" disabled={busy}>
              {busy ? "Saving..." : "Save User"}
            </button>
          </div>

          <div className="alert info">{message}</div>
        </form>
      </Panel>

      <Panel eyebrow="Step 2" title="Picture Preview">
        <div className="video-frame">
          <video ref={videoRef} autoPlay playsInline muted />
          <canvas ref={canvasRef} hidden />
        </div>

        <div className="capture-strip">
          {frames.length ? (
            frames.map((frame) => (
              <img key={frame.preview} src={frame.preview} alt="Employee preview" />
            ))
          ) : (
            <div className="empty-state">Added pictures will appear here.</div>
          )}
        </div>
      </Panel>
    </div>
  );
}
