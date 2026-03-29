import { useEffect, useRef, useState } from "react";
import Panel from "../components/Panel";
import { apiClient } from "../lib/api";
import { drawBoxes, frameToBlob, startUserCamera, stopLive } from "../lib/media";

export default function RecognitionView({ token, onUpdated }) {
  const [message, setMessage] = useState("Start recognition to begin the live operator loop.");
  const [matches, setMatches] = useState([]);
  const [debugFaces, setDebugFaces] = useState([]);
  const [busy, setBusy] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const overlayRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => () => stopLive(timerRef, streamRef, videoRef), []);

  async function handleStart() {
    if (busy) {
      return;
    }
    setBusy(true);
    await startUserCamera(videoRef, streamRef);
    timerRef.current = window.setInterval(async () => {
      try {
        if (!videoRef.current || videoRef.current.readyState < 2) {
          return;
        }
        const blob = await frameToBlob(videoRef.current, canvasRef.current);
        const form = new FormData();
        form.append("camera_id", "gate-1");
        form.append("top_k", "3");
        form.append("image", blob, "frame.jpg");
        const result = await apiClient.post("/api/v2/recognitions", token, form);
        setMatches(result.matches || []);
        setDebugFaces(result.debug_faces || []);
        drawBoxes(overlayRef.current, videoRef.current, result.boxes || []);
        if (result.matches?.length) {
          setMessage(`${result.matches.length} confirmed match(es) in the latest cycle.`);
          await onUpdated();
        } else {
          setMessage(`Detected ${result.detected_faces} face(s). Unknown faces: ${result.unknown_faces}.`);
        }
      } catch (requestError) {
        const text = requestError instanceof Error ? requestError.message : "Recognition request failed.";
        setMessage(text);
      }
    }, 1200);
  }

  function handleStop() {
    stopLive(timerRef, streamRef, videoRef);
    setBusy(false);
    setMessage("Recognition stopped.");
    drawBoxes(overlayRef.current, videoRef.current, []);
  }

  return (
    <div className="dashboard-grid">
      <Panel
        eyebrow="Live Recognition"
        title="Detection Console"
        className="wide"
        actions={(
          <div className="button-row">
            <button className="button button-secondary" onClick={handleStart} disabled={busy}>Start Recognition</button>
            <button className="button button-ghost" onClick={handleStop}>Stop</button>
          </div>
        )}
      >
        <div className="alert info">{message}</div>
        <div className="video-frame video-frame-large">
          <video ref={videoRef} autoPlay playsInline muted />
          <canvas ref={overlayRef} className="overlay-canvas" />
          <canvas ref={canvasRef} hidden />
        </div>
      </Panel>

      <Panel eyebrow="Confirmed Matches" title="Recognition Results">
        <div className="result-grid">
          {matches.length ? matches.map((match) => (
            <div className="result-card result-card-success" key={`${match.worker_id}-${match.source}`}>
              <strong>{match.name}</strong>
              <div className="mono">{match.employee_code}</div>
              <div className="mono">Score: {Number(match.score).toFixed(3)}</div>
              <div className="pill">{match.source === "cache" ? "Cached confirmation" : "Fresh confirmation"}</div>
            </div>
          )) : <div className="empty-state">Confirmed matches will appear here.</div>}
        </div>
      </Panel>

      <Panel eyebrow="Decision Trace" title="Face-Level Debug" className="wide">
        <div className="result-grid">
          {debugFaces.length ? debugFaces.map((face) => (
            <div className={`result-card ${face.accepted ? "result-card-success" : "result-card-warning"}`} key={`face-${face.face_index}`}>
              <strong>Face {face.face_index + 1}</strong>
              <p>{face.reason}</p>
              <div className="mono">Blur: {face.blur_variance?.toFixed?.(1) ?? "-"}</div>
              <div className="mono">Brightness: {face.brightness?.toFixed?.(1) ?? "-"}</div>
              <div className="mono">Eyes: {face.eyes_detected ?? "-"}</div>
              {face.candidates?.length ? (
                <div className="candidate-list">
                  {face.candidates.map((candidate) => (
                    <div className="candidate-row" key={`${face.face_index}-${candidate.worker_id}`}>
                      <span>Worker #{candidate.worker_id}</span>
                      <strong>{Number(candidate.score).toFixed(3)}</strong>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          )) : <div className="empty-state">Debug reasoning appears here when recognition runs.</div>}
        </div>
      </Panel>
    </div>
  );
}
