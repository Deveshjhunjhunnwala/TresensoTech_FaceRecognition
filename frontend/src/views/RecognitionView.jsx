import { useEffect, useRef, useState } from "react";
import Panel from "../components/Panel";
import { apiClient } from "../lib/api";
import { drawBoxes, frameToBlob, startUserCamera, stopLive } from "../lib/media";

const SCAN_INTERVAL_MS = 700;

export default function RecognitionView({ token, onUpdated }) {
  const [message, setMessage] = useState("Press start to scan a face.");
  const [matches, setMatches] = useState([]);
  const [running, setRunning] = useState(false);
  const [lastUnknown, setLastUnknown] = useState(false);
  const [lastReason, setLastReason] = useState("");
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const overlayRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const requestInFlightRef = useRef(false);

  useEffect(() => () => stopLive(timerRef, streamRef, videoRef), []);

  async function handleStart() {
    if (running) {
      return;
    }

    try {
      setMatches([]);
      setLastUnknown(false);
      setLastReason("");
      setRunning(true);
      setMessage("Camera started. Hold the face steady and look at the screen.");
      await startUserCamera(videoRef, streamRef);

      timerRef.current = window.setInterval(async () => {
        if (requestInFlightRef.current) {
          return;
        }

        requestInFlightRef.current = true;
        try {
          if (!videoRef.current || videoRef.current.readyState < 2) {
            return;
          }

          const blob = await frameToBlob(videoRef.current, canvasRef.current);
          const form = new FormData();
          form.append("camera_id", "device-front-camera");
          form.append("top_k", "3");
          form.append("image", blob, "scan.jpg");

          const result = await apiClient.post("/api/v2/recognitions", token, form);
          setMatches(result.matches || []);
          drawBoxes(overlayRef.current, videoRef.current, result.boxes || []);

          if (result.matches?.length) {
            const firstMatch = result.matches[0];
            setLastUnknown(false);
            setLastReason("");
            setMessage(
              firstMatch.attendance_marked
                ? `${firstMatch.name} matched and attendance marked.`
                : `${firstMatch.name} matched. Attendance was already marked recently.`
            );
            if (result.matches.some((match) => match.attendance_marked)) {
              await onUpdated();
            }
            return;
          }

          if (result.detected_faces > 0) {
            const firstReason = result.debug_faces?.find((face) => face.reason)?.reason || "Face detected, but no valid employee match was confirmed.";
            setLastUnknown(true);
            setLastReason(firstReason);
            setMessage("Face detected. Matching is still not confirmed.");
            return;
          }

          setLastUnknown(false);
          setLastReason("");
          setMessage("No face detected.");
        } catch (requestError) {
          const text = requestError instanceof Error ? requestError.message : "Scan request failed.";
          setMessage(text);
        } finally {
          requestInFlightRef.current = false;
        }
      }, SCAN_INTERVAL_MS);
    } catch (requestError) {
      setRunning(false);
      requestInFlightRef.current = false;
      const text = requestError instanceof Error ? requestError.message : "Camera could not be started.";
      setMessage(text);
    }
  }

  function handleStop() {
    stopLive(timerRef, streamRef, videoRef);
    requestInFlightRef.current = false;
    drawBoxes(overlayRef.current, videoRef.current, []);
    setMatches([]);
    setLastUnknown(false);
    setLastReason("");
    setRunning(false);
    setMessage("Scan stopped.");
  }

  return (
    <div className="device-stack">
      <Panel
        eyebrow="Live Camera"
        title="Scan Face"
        actions={(
          <div className="button-row">
            <button className="button button-secondary" onClick={handleStart} disabled={running}>Start</button>
            <button className="button button-ghost" onClick={handleStop} type="button">Stop</button>
          </div>
        )}
      >
        <div className="alert info">{message}</div>
        <div className="video-frame">
          <video ref={videoRef} autoPlay playsInline muted />
          <canvas ref={overlayRef} className="overlay-canvas" />
          <canvas ref={canvasRef} hidden />
        </div>
      </Panel>

      <Panel eyebrow="Result" title="Scan Status">
        {matches.length ? (
          <div className="result-grid">
            {matches.map((match) => (
              <div className="result-card result-card-success" key={`${match.worker_id}-${match.source}`}>
                <strong>{match.name}</strong>
                <div className="mono">Employee ID: {match.employee_code}</div>
                <div className="mono">Match Score: {Number(match.score).toFixed(3)}</div>
                <div className="pill">
                  {match.attendance_marked ? "Attendance Marked" : "Already Marked"}
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {!matches.length && lastUnknown ? (
          <div className="result-card result-card-warning">
            <strong>User not confirmed</strong>
            <p>{lastReason || "No confirmed employee match was found for the scanned face."}</p>
          </div>
        ) : null}

        {!matches.length && !lastUnknown ? (
          <div className="empty-state">The result will appear here after scanning starts.</div>
        ) : null}
      </Panel>
    </div>
  );
}
