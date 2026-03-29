import cv2
import numpy as np

try:
    import mediapipe as mp
except ImportError:
    mp = None


FACE_CASCADE_PATHS = [
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
    cv2.data.haarcascades + "haarcascade_frontalface_alt.xml",
    cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml",
]

if mp is not None:
    _MP_FACE_DETECTION = mp.solutions.face_detection.FaceDetection(
        model_selection=0,
        min_detection_confidence=0.45,
    )
else:
    _MP_FACE_DETECTION = None


def detector_backend_name() -> str:
    return "mediapipe" if _MP_FACE_DETECTION is not None else "opencv-cascade"


def _load_cascades() -> list[cv2.CascadeClassifier]:
    cascades: list[cv2.CascadeClassifier] = []
    for path in FACE_CASCADE_PATHS:
        cascade = cv2.CascadeClassifier(path)
        if not cascade.empty():
            cascades.append(cascade)
    if not cascades:
        raise RuntimeError("Could not load any OpenCV face cascades.")
    return cascades


def _prepare_gray(image: np.ndarray) -> np.ndarray:
    gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    return cv2.GaussianBlur(gray, (5, 5), 0)


def detect_faces(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    mediapipe_faces = _detect_faces_mediapipe(image)
    if mediapipe_faces:
        return mediapipe_faces

    gray = _prepare_gray(image)
    height, width = gray.shape[:2]
    min_size = (max(48, width // 10), max(48, height // 10))
    candidates: list[tuple[int, int, int, int]] = []

    for cascade in _load_cascades():
        for scale_factor, min_neighbors in ((1.1, 4), (1.05, 3), (1.2, 5)):
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=scale_factor,
                minNeighbors=min_neighbors,
                minSize=min_size,
            )
            for face in faces:
                candidates.append(tuple(map(int, face)))

    return _deduplicate_faces(candidates)


def _detect_faces_mediapipe(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    if _MP_FACE_DETECTION is None:
        return []

    if len(image.shape) == 2:
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    results = _MP_FACE_DETECTION.process(rgb)
    if not results.detections:
        return []

    height, width = image.shape[:2]
    faces: list[tuple[int, int, int, int]] = []
    for detection in results.detections:
        bbox = detection.location_data.relative_bounding_box
        x = max(0, int(bbox.xmin * width))
        y = max(0, int(bbox.ymin * height))
        w = int(bbox.width * width)
        h = int(bbox.height * height)
        if w < 40 or h < 40:
            continue
        x2 = min(width, x + w)
        y2 = min(height, y + h)
        faces.append((x, y, x2 - x, y2 - y))
    return _deduplicate_faces(faces)


def _deduplicate_faces(faces: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    deduped: list[tuple[int, int, int, int]] = []
    for face in sorted(faces, key=lambda rect: rect[2] * rect[3], reverse=True):
        if any(_iou(face, existing) > 0.35 for existing in deduped):
            continue
        deduped.append(face)
    return deduped


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    if right <= left or bottom <= top:
        return 0.0
    intersection = float((right - left) * (bottom - top))
    union = float((aw * ah) + (bw * bh) - intersection)
    return 0.0 if union == 0 else intersection / union


def largest_face(image: np.ndarray) -> np.ndarray:
    faces = detect_faces(image)
    if not faces:
        raise RuntimeError("No face detected in image.")

    x, y, w, h = max(faces, key=lambda rect: rect[2] * rect[3])
    x, y, w, h = expand_face_box(x, y, w, h, image.shape[1], image.shape[0], padding_ratio=0.18)
    return image[y : y + h, x : x + w]


def expand_face_box(
    x: int,
    y: int,
    w: int,
    h: int,
    image_width: int,
    image_height: int,
    padding_ratio: float = 0.12,
) -> tuple[int, int, int, int]:
    pad_x = int(w * padding_ratio)
    pad_y = int(h * padding_ratio)
    left = max(0, x - pad_x)
    top = max(0, y - pad_y)
    right = min(image_width, x + w + pad_x)
    bottom = min(image_height, y + h + pad_y)
    return left, top, right - left, bottom - top
