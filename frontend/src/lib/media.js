export function stopStream(streamRef, videoRef) {
  if (streamRef.current) {
    streamRef.current.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }
  if (videoRef.current) {
    videoRef.current.srcObject = null;
  }
}

export function stopLive(timerRef, streamRef, videoRef) {
  if (timerRef.current) {
    window.clearInterval(timerRef.current);
    timerRef.current = null;
  }
  stopStream(streamRef, videoRef);
}

export function drawBoxes(canvas, video, boxes = []) {
  if (!canvas || !video) {
    return;
  }
  canvas.width = video.videoWidth || 0;
  canvas.height = video.videoHeight || 0;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = "#27d0bd";
  context.lineWidth = 3;
  context.setLineDash([]);
  boxes.forEach((box) => {
    context.strokeRect(box.x, box.y, box.width, box.height);
  });
}

export function frameToBlob(video, canvas) {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const context = canvas.getContext("2d");
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("Could not capture the current video frame."));
        return;
      }
      resolve(blob);
    }, "image/jpeg", 0.92);
  });
}

export async function startUserCamera(videoRef, streamRef) {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: { ideal: "user" },
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        frameRate: { ideal: 30 },
      },
      audio: false,
    });
  } catch {
    stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false,
    });
  }
  streamRef.current = stream;
  if (videoRef.current) {
    videoRef.current.srcObject = stream;
  }
}
