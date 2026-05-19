from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

import cv2
import numpy as np

from src.vision import detect_eyes
from src.v2 import repository
from src.v2.cache import RecognitionCache
from src.v2.config import (
    ALLOW_BACKEND_FALLBACK,
    AMBIGUITY_MARGIN,
    DEFAULT_LIST_LIMIT,
    FACE_SIZE,
    FAST_ACCEPT_SCORE,
    LBPH_CONFIDENCE_THRESHOLD,
    MAX_FACE_BRIGHTNESS,
    MATCH_THRESHOLD,
    MATCH_CONFIRMATION_FRAMES,
    MATCH_CONFIRMATION_WINDOW_SECONDS,
    MIN_FACE_BLUR_VARIANCE,
    MIN_FACE_BRIGHTNESS,
    MIN_FACE_HEIGHT,
    MIN_FACE_WIDTH,
    MAX_FACES_PER_REQUEST,
    MAX_TOP_K,
    RECOGNITION_CACHE_TTL_SECONDS,
)
from src.v2.embedder import resolve_embedder
from src.v2.index import resolve_index
from src.v2.schemas import (
    ArchitectureNote,
    AttendanceRow,
    CandidateDebug,
    DeleteAttendanceResult,
    DeleteWorkerResult,
    DetectionBox,
    DetectionResult,
    EnrollmentResult,
    FaceDebug,
    IndexStats,
    MatchResult,
    RecognitionResult,
    ServiceStatus,
    WorkerRead,
)
from src.v2.vision import detect_faces, detector_backend_name, expand_face_box, largest_face


@dataclass
class PendingMatch:
    worker_id: int
    count: int
    best_score: float
    expires_at: datetime


class ScalableAttendanceService:
    def __init__(self) -> None:
        repository.init_schema()
        self.embedder, self.requested_embedder, self.active_embedder, embedder_warnings = resolve_embedder()
        self.index, self.requested_index, self.active_index, index_warnings = resolve_index()
        self.warnings = embedder_warnings + index_warnings
        self.recognition_cache = RecognitionCache(ttl_seconds=RECOGNITION_CACHE_TTL_SECONDS)
        self.lbph_recognizer: cv2.face_LBPHFaceRecognizer | None = None
        self.lbph_label_to_worker_id: dict[int, int] = {}
        self.pending_matches: dict[str, PendingMatch] = {}
        if not self.index.load(expected_namespace=self._index_namespace()):
            self.rebuild_index()

    def _index_namespace(self) -> str:
        return f"embedder:{self.embedder.name}"

    def _purge_pending_matches(self) -> None:
        now = datetime.utcnow()
        expired = [camera_id for camera_id, state in self.pending_matches.items() if state.expires_at <= now]
        for camera_id in expired:
            del self.pending_matches[camera_id]

    def _confirm_match_candidate(self, camera_id: str, worker_id: int, score: float) -> tuple[bool, float]:
        if score >= FAST_ACCEPT_SCORE:
            self.pending_matches.pop(camera_id, None)
            return True, score

        self._purge_pending_matches()
        now = datetime.utcnow()
        state = self.pending_matches.get(camera_id)
        expires_at = now + timedelta(seconds=MATCH_CONFIRMATION_WINDOW_SECONDS)

        if state is None or state.worker_id != worker_id or state.expires_at <= now:
            self.pending_matches[camera_id] = PendingMatch(
                worker_id=worker_id,
                count=1,
                best_score=score,
                expires_at=expires_at,
            )
            return False, score

        state.count += 1
        state.best_score = max(state.best_score, score)
        state.expires_at = expires_at
        self.pending_matches[camera_id] = state

        if state.count < MATCH_CONFIRMATION_FRAMES:
            return False, state.best_score

        del self.pending_matches[camera_id]
        return True, state.best_score

    def rebuild_index(self) -> IndexStats:
        if self.embedder.name == "lbph":
            return self._rebuild_lbph_model()

        raw_embeddings = repository.fetch_embeddings(
            backend=self.embedder.name,
            dimension=self.embedder.vector_size,
        )
        worker_ids = [worker_id for worker_id, _vector in raw_embeddings]
        vectors = [vector.astype(np.float32) for _worker_id, vector in raw_embeddings]

        self.index.build(worker_ids, vectors)
        self.index.save(namespace=self._index_namespace())
        return IndexStats(
            indexed_workers=repository.worker_count(),
            indexed_embeddings=self.index.size,
        )

    def _rebuild_lbph_model(self) -> IndexStats:
        samples = repository.fetch_face_samples(backend="lbph")
        raw_embeddings = repository.fetch_embeddings(
            backend="lbph",
            dimension=self.embedder.vector_size,
        )
        if not samples:
            self.lbph_recognizer = None
            self.lbph_label_to_worker_id = {}
            self.index.build([], [])
            self.index.save(namespace=self._index_namespace())
            return IndexStats(
                indexed_workers=repository.worker_count(),
                indexed_embeddings=0,
            )

        grouped: dict[int, list[np.ndarray]] = defaultdict(list)
        for worker_id, image_bytes in samples:
            image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is None:
                continue
            grouped[worker_id].append(image)

        if not grouped:
            self.lbph_recognizer = None
            self.lbph_label_to_worker_id = {}
            self.index.build([], [])
            self.index.save(namespace=self._index_namespace())
            return IndexStats(
                indexed_workers=repository.worker_count(),
                indexed_embeddings=0,
            )

        label_to_worker_id: dict[int, int] = {}
        face_images: list[np.ndarray] = []
        labels: list[int] = []
        for label, worker_id in enumerate(sorted(grouped)):
            label_to_worker_id[label] = worker_id
            for image in grouped[worker_id]:
                face_images.append(image)
                labels.append(label)

        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(face_images, np.asarray(labels, dtype=np.int32))
        self.lbph_recognizer = recognizer
        self.lbph_label_to_worker_id = label_to_worker_id
        self.index.build(
            [worker_id for worker_id, _vector in raw_embeddings],
            [vector.astype(np.float32) for _worker_id, vector in raw_embeddings],
        )
        self.index.save(namespace=self._index_namespace())
        return IndexStats(
            indexed_workers=repository.worker_count(),
            indexed_embeddings=len(face_images),
        )

    def list_workers(self) -> list[WorkerRead]:
        return [WorkerRead(**dict(row)) for row in repository.list_workers()]

    def list_attendance(self, limit: int = DEFAULT_LIST_LIMIT) -> list[AttendanceRow]:
        return [AttendanceRow(**dict(row)) for row in repository.list_attendance(limit=limit)]

    def delete_attendance(self, attendance_id: int) -> DeleteAttendanceResult:
        attendance = repository.delete_attendance_event(attendance_id)
        if attendance is None:
            raise RuntimeError(f"No attendance record found for id '{attendance_id}'.")
        return DeleteAttendanceResult(
            id=attendance["id"],
            worker_id=attendance["worker_id"],
            employee_code=attendance["employee_code"],
            name=attendance["name"],
            deleted=True,
        )

    def architecture_note(self) -> ArchitectureNote:
        warnings = list(self.warnings)
        if self.active_embedder != self.requested_embedder:
            warnings.append(
                "The requested production embedder is not active. Install the missing backend or disable fallback to fail fast."
            )
        if repository.worker_count() > 0 and repository.embedding_count(
            self.embedder.name,
            self.embedder.vector_size,
        ) == 0:
            warnings.append(
                f"No embeddings are stored for the active '{self.embedder.name}' backend yet. Re-enroll workers after switching backends."
            )
        return ArchitectureNote(
            detector=detector_backend_name(),
            requested_embedder=self.requested_embedder,
            active_embedder=self.active_embedder,
            requested_index=self.requested_index,
            active_index=self.active_index,
            fallback_enabled=ALLOW_BACKEND_FALLBACK,
            warnings=warnings,
        )

    def status(self) -> ServiceStatus:
        counts = repository.system_counts(
            backend=self.embedder.name,
            dimension=self.embedder.vector_size,
        )
        warnings = list(self.architecture_note().warnings)
        return ServiceStatus(
            indexed_workers=counts["workers"],
            indexed_embeddings=counts["embeddings"],
            attendance_events=counts["attendance_events"],
            cache_entries=self.recognition_cache.active_entries(),
            active_detector=detector_backend_name(),
            requested_embedder=self.requested_embedder,
            active_embedder=self.active_embedder,
            requested_index=self.requested_index,
            active_index=self.active_index,
            fallback_enabled=ALLOW_BACKEND_FALLBACK,
            warnings=warnings,
        )

    def enroll_worker(self, employee_code: str, name: str, image_bytes_list: list[bytes], replace_existing: bool = True) -> EnrollmentResult:
        if not image_bytes_list:
            raise RuntimeError("Enrollment requires at least one image.")

        worker = repository.upsert_worker(employee_code=employee_code, name=name)
        if replace_existing:
            repository.delete_embeddings_for_worker(worker["id"], backend=self.embedder.name)
        added = 0
        for image_bytes in image_bytes_list:
            image = _decode_image(image_bytes)
            face = largest_face(image)
            embedding = self.embedder.embed(face)
            encoded_face = _encode_training_face(self._prepare_lbph_face(face) if self.embedder.name == "lbph" else None)
            repository.store_embedding(
                worker["id"],
                embedding,
                backend=self.embedder.name,
                face_image=encoded_face,
            )
            added += 1

        stats = self.rebuild_index()
        return EnrollmentResult(
            worker=WorkerRead(**dict(worker)),
            embeddings_added=added,
            index_size=stats.indexed_embeddings,
        )

    def detect(self, image_bytes: bytes) -> DetectionResult:
        image = _decode_image(image_bytes)
        faces = detect_faces(image)
        return DetectionResult(
            detected_faces=len(faces),
            boxes=[DetectionBox(x=x, y=y, width=w, height=h) for (x, y, w, h) in faces],
            detector_backend=detector_backend_name(),
        )

    def delete_worker(self, employee_code: str) -> DeleteWorkerResult:
        worker = repository.delete_worker_by_employee_code(employee_code)
        if worker is None:
            raise RuntimeError(f"No worker found for employee code '{employee_code}'.")

        stats = self.rebuild_index()
        return DeleteWorkerResult(
            worker_id=worker["id"],
            employee_code=worker["employee_code"],
            name=worker["name"],
            deleted=True,
            index_size=stats.indexed_embeddings,
        )

    def recognize(self, image_bytes: bytes, camera_id: str, top_k: int = 3) -> RecognitionResult:
        if self.embedder.name == "lbph":
            return self._recognize_lbph(image_bytes=image_bytes, camera_id=camera_id)

        image = _decode_image(image_bytes)
        faces = detect_faces(image)
        if not faces:
            return RecognitionResult(matches=[], unknown_faces=0, detected_faces=0, boxes=[], debug_faces=[])

        face_regions: list[np.ndarray] = []
        debug_faces: list[FaceDebug] = []
        largest_first = sorted(faces, key=lambda rect: rect[2] * rect[3], reverse=True)[:MAX_FACES_PER_REQUEST]
        for face_index, (x, y, w, h) in enumerate(largest_first):
            crop_x, crop_y, crop_w, crop_h = expand_face_box(
                x, y, w, h, image.shape[1], image.shape[0], padding_ratio=0.18
            )
            face_crop = image[crop_y : crop_y + crop_h, crop_x : crop_x + crop_w]
            blur_variance, brightness = self._face_quality_metrics(face_crop)
            if not self._is_face_usable(face_crop, w, h, blur_variance=blur_variance, brightness=brightness):
                debug_faces.append(
                    FaceDebug(
                        face_index=face_index,
                        accepted=False,
                        reason=self._face_rejection_reason(
                            face_width=w,
                            face_height=h,
                            blur_variance=blur_variance,
                            brightness=brightness,
                        ),
                        blur_variance=blur_variance,
                        brightness=brightness,
                    )
                )
                continue
            face_regions.append(face_crop)
            debug_faces.append(
                FaceDebug(
                    face_index=face_index,
                    accepted=False,
                    reason="Pending descriptor search.",
                    blur_variance=blur_variance,
                    brightness=brightness,
                )
            )

        embeddings = [self.embedder.embed(face) for face in face_regions]
        search_results = self.index.batch_search(embeddings, top_k=min(MAX_TOP_K, top_k))

        unknown_faces = max(0, len(largest_first) - len(face_regions))
        grouped_hits: dict[int, tuple[float, str]] = defaultdict(lambda: (0.0, "fresh"))

        usable_debug_index = 0
        for hits in search_results:
            while usable_debug_index < len(debug_faces) and "Pending" not in debug_faces[usable_debug_index].reason:
                usable_debug_index += 1
            if not hits:
                unknown_faces += 1
                if usable_debug_index < len(debug_faces):
                    debug_faces[usable_debug_index].reason = "Rejected: no similar enrolled face found."
                continue

            best_worker_id, best_score, second_best_score = self._aggregate_descriptor_hits(hits)
            if best_worker_id is None or best_score < max(MATCH_THRESHOLD, 0.55):
                unknown_faces += 1
                if usable_debug_index < len(debug_faces):
                    debug_faces[usable_debug_index].reason = "Rejected: top similarity score is below threshold."
                    debug_faces[usable_debug_index].candidates = self._debug_candidates(hits)
                continue

            if (best_score - second_best_score) < max(AMBIGUITY_MARGIN, 0.03):
                unknown_faces += 1
                if usable_debug_index < len(debug_faces):
                    debug_faces[usable_debug_index].reason = "Rejected: top candidates are too close to each other."
                    debug_faces[usable_debug_index].candidates = self._debug_candidates(hits)
                continue

            confirmed, confirmed_score = self._confirm_match_candidate(
                camera_id=camera_id,
                worker_id=best_worker_id,
                score=best_score,
            )
            if not confirmed:
                unknown_faces += 1
                if usable_debug_index < len(debug_faces):
                    debug_faces[usable_debug_index].reason = "Pending: waiting for the same identity across more frames."
                    debug_faces[usable_debug_index].candidates = self._debug_candidates(hits)
                continue

            if self.recognition_cache.should_skip(camera_id=camera_id, worker_id=best_worker_id, score=confirmed_score):
                previous_score, _source = grouped_hits[best_worker_id]
                grouped_hits[best_worker_id] = (max(previous_score, confirmed_score), "cache")
                if usable_debug_index < len(debug_faces):
                    debug_faces[usable_debug_index].accepted = True
                    debug_faces[usable_debug_index].reason = "Accepted from cache: same worker was recently confirmed."
                    debug_faces[usable_debug_index].candidates = self._debug_candidates(hits)
                continue

            previous_score, _source = grouped_hits[best_worker_id]
            grouped_hits[best_worker_id] = (max(previous_score, confirmed_score), "fresh")
            if usable_debug_index < len(debug_faces):
                debug_faces[usable_debug_index].accepted = True
                debug_faces[usable_debug_index].reason = "Accepted: descriptor match passed threshold and stability checks."
                debug_faces[usable_debug_index].candidates = self._debug_candidates(hits)

        matches: list[MatchResult] = []
        for worker_id, (score, source) in sorted(grouped_hits.items(), key=lambda item: item[1][0], reverse=True):
            worker = repository.fetch_worker(worker_id)
            if worker is None:
                continue
            attendance_marked = False
            if source != "cache":
                attendance_marked = repository.mark_attendance(
                    worker_id=worker_id,
                    camera_id=camera_id,
                    matched_score=score,
                    intoxication_data={
                    "alcohol": "0.02 mg/L",
                    "cannabis": "12 ppm",
                    "terpeneConfidence": "91%",
                    "warning": True,
                    },
                    )
                
                self.recognition_cache.remember(camera_id=camera_id, worker_id=worker_id, score=score)
            matches.append(
                MatchResult(
                    worker_id=worker_id,
                    employee_code=worker["employee_code"],
                    name=worker["name"],
                    score=score,
                    attendance_marked=attendance_marked,
                    source=source,
                )
            )

        return RecognitionResult(
            matches=matches,
            unknown_faces=unknown_faces,
            detected_faces=len(largest_first),
            boxes=[DetectionBox(x=x, y=y, width=w, height=h) for (x, y, w, h) in largest_first],
            debug_faces=debug_faces,
        )

    def _recognize_lbph(self, image_bytes: bytes, camera_id: str) -> RecognitionResult:
        image = _decode_image(image_bytes)
        faces = detect_faces(image)
        if not faces:
            return RecognitionResult(matches=[], unknown_faces=0, detected_faces=0, boxes=[], debug_faces=[])
        if self.lbph_recognizer is None:
            self._rebuild_lbph_model()
        if self.lbph_recognizer is None:
            return RecognitionResult(
                matches=[],
                unknown_faces=len(faces),
                detected_faces=len(faces),
                boxes=[DetectionBox(x=x, y=y, width=w, height=h) for (x, y, w, h) in faces],
                debug_faces=[],
            )

        unknown_faces = 0
        grouped_hits: dict[int, tuple[float, str]] = defaultdict(lambda: (0.0, "fresh"))
        debug_faces: list[FaceDebug] = []
        largest_first = sorted(faces, key=lambda rect: rect[2] * rect[3], reverse=True)[:MAX_FACES_PER_REQUEST]

        for face_index, (x, y, w, h) in enumerate(largest_first):
            crop_x, crop_y, crop_w, crop_h = expand_face_box(
                x, y, w, h, image.shape[1], image.shape[0], padding_ratio=0.18
            )
            face_crop = image[crop_y : crop_y + crop_h, crop_x : crop_x + crop_w]
            blur_variance, brightness = self._face_quality_metrics(face_crop)
            if not self._is_face_usable(face_crop, w, h, blur_variance=blur_variance, brightness=brightness):
                unknown_faces += 1
                debug_faces.append(
                    FaceDebug(
                        face_index=face_index,
                        accepted=False,
                        reason=self._face_rejection_reason(
                            face_width=w,
                            face_height=h,
                            blur_variance=blur_variance,
                            brightness=brightness,
                        ),
                        blur_variance=blur_variance,
                        brightness=brightness,
                    )
                )
                continue
            normalized_face = self._prepare_lbph_face(face_crop)
            descriptor = self.embedder.embed(face_crop)
            predicted_label, raw_confidence = self.lbph_recognizer.predict(normalized_face)
            worker_id = self.lbph_label_to_worker_id.get(int(predicted_label))

            descriptor_hits = self.index.search(descriptor, top_k=min(MAX_TOP_K, 3))
            descriptor_worker_id, descriptor_score, second_descriptor_score = self._aggregate_descriptor_hits(descriptor_hits)
            lbph_score = self._lbph_score(raw_confidence)
            eyes_detected = len(detect_eyes(normalized_face))
            debug_entry = FaceDebug(
                face_index=face_index,
                accepted=False,
                reason="Pending LBPH and descriptor checks.",
                blur_variance=blur_variance,
                brightness=brightness,
                eyes_detected=eyes_detected,
                candidates=self._debug_candidates(descriptor_hits),
            )
            if eyes_detected > 0:
                lbph_score = min(1.0, lbph_score + 0.04)
                if descriptor_worker_id is not None:
                    descriptor_score = min(1.0, descriptor_score + 0.03)

            candidate_scores: dict[int, float] = {}
            if worker_id is not None:
                candidate_scores[worker_id] = max(candidate_scores.get(worker_id, 0.0), lbph_score)
            if descriptor_worker_id is not None:
                candidate_scores[descriptor_worker_id] = max(
                    candidate_scores.get(descriptor_worker_id, 0.0),
                    descriptor_score,
                )

            if worker_id is not None and descriptor_worker_id == worker_id:
                candidate_scores[worker_id] = min(
                    1.0,
                    max(candidate_scores[worker_id], (lbph_score * 0.55) + (descriptor_score * 0.45)),
                )

            if not candidate_scores:
                unknown_faces += 1
                debug_entry.reason = "Rejected: no candidate survived LBPH and descriptor scoring."
                debug_faces.append(debug_entry)
                continue

            ranked_candidates = sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)
            best_worker_id, best_score = ranked_candidates[0]
            second_best_score = ranked_candidates[1][1] if len(ranked_candidates) > 1 else 0.0
            raw_confidence_allows = worker_id is not None and raw_confidence <= LBPH_CONFIDENCE_THRESHOLD
            descriptor_is_clear = descriptor_worker_id is not None and (descriptor_score - second_descriptor_score) >= 0.04

            if best_score < 0.52 and not raw_confidence_allows:
                unknown_faces += 1
                debug_entry.reason = "Rejected: combined score is below threshold."
                debug_faces.append(debug_entry)
                continue

            if worker_id is not None and descriptor_worker_id is not None and worker_id != descriptor_worker_id:
                if not raw_confidence_allows or not descriptor_is_clear:
                    unknown_faces += 1
                    debug_entry.reason = "Rejected: LBPH and descriptor disagree on identity."
                    debug_faces.append(debug_entry)
                    continue

            if (best_score - second_best_score) < 0.05 and not (raw_confidence_allows and descriptor_is_clear):
                unknown_faces += 1
                debug_entry.reason = "Rejected: best candidate is not clearly ahead of the next one."
                debug_faces.append(debug_entry)
                continue

            accepted_score = max(best_score, lbph_score if best_worker_id == worker_id else 0.0)
            confirmed, confirmed_score = self._confirm_match_candidate(
                camera_id=camera_id,
                worker_id=best_worker_id,
                score=accepted_score,
            )
            if not confirmed:
                unknown_faces += 1
                debug_entry.reason = "Pending: waiting for the same identity across more frames."
                debug_faces.append(debug_entry)
                continue

            if self.recognition_cache.should_skip(camera_id=camera_id, worker_id=best_worker_id, score=confirmed_score):
                previous_score, _source = grouped_hits[best_worker_id]
                grouped_hits[best_worker_id] = (max(previous_score, confirmed_score), "cache")
                debug_entry.accepted = True
                debug_entry.reason = "Accepted from cache: same worker was recently confirmed."
                debug_faces.append(debug_entry)
                continue

            previous_score, _source = grouped_hits[best_worker_id]
            grouped_hits[best_worker_id] = (max(previous_score, confirmed_score), "fresh")
            debug_entry.accepted = True
            debug_entry.reason = "Accepted: LBPH and descriptor checks passed."
            debug_faces.append(debug_entry)

        matches: list[MatchResult] = []
        for worker_id, (score, source) in sorted(grouped_hits.items(), key=lambda item: item[1][0], reverse=True):
            worker = repository.fetch_worker(worker_id)
            if worker is None:
                continue
            attendance_marked = False
            if source != "cache":
                attendance_marked = repository.mark_attendance(worker_id=worker_id, camera_id=camera_id, matched_score=score)
                self.recognition_cache.remember(camera_id=camera_id, worker_id=worker_id, score=score)
            matches.append(
                MatchResult(
                    worker_id=worker_id,
                    employee_code=worker["employee_code"],
                    name=worker["name"],
                    score=score,
                    attendance_marked=attendance_marked,
                    source=source,
                )
            )

        return RecognitionResult(
            matches=matches,
            unknown_faces=unknown_faces,
            detected_faces=len(largest_first),
            boxes=[DetectionBox(x=x, y=y, width=w, height=h) for (x, y, w, h) in largest_first],
            debug_faces=debug_faces,
        )

    def _prepare_lbph_face(self, face_image: np.ndarray) -> np.ndarray:
        if len(face_image.shape) == 3:
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_image
        resized = cv2.resize(gray, FACE_SIZE)
        return cv2.equalizeHist(resized)

    def _lbph_score(self, raw_confidence: float) -> float:
        return float(max(0.0, min(1.0, 1.0 - (raw_confidence / 120.0))))

    def _is_face_usable(
        self,
        face_crop: np.ndarray,
        face_width: int,
        face_height: int,
        blur_variance: float | None = None,
        brightness: float | None = None,
    ) -> bool:
        if face_width < MIN_FACE_WIDTH or face_height < MIN_FACE_HEIGHT:
            return False

        if blur_variance is None or brightness is None:
            blur_variance, brightness = self._face_quality_metrics(face_crop)
        if blur_variance < MIN_FACE_BLUR_VARIANCE:
            return False
        if brightness < MIN_FACE_BRIGHTNESS or brightness > MAX_FACE_BRIGHTNESS:
            return False
        return True

    def _face_rejection_reason(
        self,
        face_width: int,
        face_height: int,
        blur_variance: float,
        brightness: float,
    ) -> str:
        reasons: list[str] = []
        if face_width < MIN_FACE_WIDTH or face_height < MIN_FACE_HEIGHT:
            reasons.append(
                f"face is too small ({face_width}x{face_height}, minimum {MIN_FACE_WIDTH}x{MIN_FACE_HEIGHT})"
            )
        if blur_variance < MIN_FACE_BLUR_VARIANCE:
            reasons.append(
                f"face is too blurry ({blur_variance:.1f} < {MIN_FACE_BLUR_VARIANCE:.1f})"
            )
        if brightness < MIN_FACE_BRIGHTNESS:
            reasons.append(
                f"frame is too dark ({brightness:.1f} < {MIN_FACE_BRIGHTNESS:.1f})"
            )
        elif brightness > MAX_FACE_BRIGHTNESS:
            reasons.append(
                f"frame is too bright ({brightness:.1f} > {MAX_FACE_BRIGHTNESS:.1f})"
            )
        if not reasons:
            return "Rejected by the face quality gate."
        return "Rejected: " + "; ".join(reasons) + "."

    def _face_quality_metrics(self, face_crop: np.ndarray) -> tuple[float, float]:
        if len(face_crop.shape) == 3:
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = face_crop
        blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(np.mean(gray))
        return blur_variance, brightness

    def _aggregate_descriptor_hits(self, hits: list) -> tuple[int | None, float, float]:
        if not hits:
            return None, 0.0, 0.0

        grouped: dict[int, list[float]] = defaultdict(list)
        for hit in hits:
            grouped[hit.worker_id].append(float(hit.score))

        ranked: list[tuple[int, float]] = []
        for worker_id, scores in grouped.items():
            best = max(scores)
            support_bonus = min(0.05, 0.015 * (len(scores) - 1))
            ranked.append((worker_id, min(1.0, best + support_bonus)))

        ranked.sort(key=lambda item: item[1], reverse=True)
        best_worker_id, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        return best_worker_id, best_score, second_score

    def _debug_candidates(self, hits: list, limit: int = 3) -> list[CandidateDebug]:
        grouped: dict[int, float] = {}
        for hit in hits:
            grouped[hit.worker_id] = max(grouped.get(hit.worker_id, 0.0), float(hit.score))
        ranked = sorted(grouped.items(), key=lambda item: item[1], reverse=True)[:limit]
        return [CandidateDebug(worker_id=worker_id, score=score) for worker_id, score in ranked]


def _decode_image(image_bytes: bytes) -> np.ndarray:
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("Could not decode image bytes.")
    return image


def _encode_training_face(face_image: np.ndarray | None) -> bytes | None:
    if face_image is None:
        return None
    ok, encoded = cv2.imencode(".png", face_image)
    if not ok:
        raise RuntimeError("Could not encode training face sample.")
    return encoded.tobytes()
