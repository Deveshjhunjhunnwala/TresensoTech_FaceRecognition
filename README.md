# Facial Recognition Attendance System

A local desktop attendance app built with Python, OpenCV, Tkinter, SQLite, and Excel export support.

## Scalable V2 API

This repo now also includes a `v2` backend-oriented architecture for larger deployments with `1,000-10,000` workers.

Important note:
- The new architecture is the right structural direction for scale.
- The supported startup path in this repo is now `MediaPipe + classical descriptor + LSH index`.
- That stack is what the app is configured to run by default on this machine.

### V2 Design

- Precompute one or more embeddings per worker at enrollment time
- Store worker metadata in SQL
- Store embeddings separately and build a vector index
- Run recognition as `detect -> embed -> nearest-neighbor search -> threshold -> attendance mark`
- Avoid scanning every worker one-by-one during live recognition

### V2 Files

- API app: `src/api_v2.py`
- Service layer: `src/v2/service.py`
- SQL repository: `src/v2/repository.py`
- Vector index: `src/v2/index.py`
- Embedder abstraction: `src/v2/embedder.py`
- Detection helpers: `src/v2/vision.py`

### V2 Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

`mediapipe` is now included and is used as the preferred face detector for the live web app. If MediaPipe is unavailable in a given environment, the app falls back to OpenCV cascade detection.

Backend selection is environment-driven:

```bash
ATTENDANCE_EMBEDDING_BACKEND=classical
ATTENDANCE_VECTOR_INDEX_BACKEND=lsh
ATTENDANCE_ALLOW_BACKEND_FALLBACK=true
```

Optional alternative backend:

```bash
ATTENDANCE_EMBEDDING_BACKEND=lbph
ATTENDANCE_VECTOR_INDEX_BACKEND=lsh
```

If you want the API to fail fast instead of silently falling back, disable fallback:

```bash
ATTENDANCE_ALLOW_BACKEND_FALLBACK=false
```

Run the API:

```bash
python api.py
```

Open the app:

```text
http://127.0.0.1:8000/
```

Open the docs:

```text
http://127.0.0.1:8000/docs
```

### V2 API Flow

1. Enroll a worker with multiple images
2. The service extracts one embedding per image and stores it
3. The service rebuilds the vector index
4. Recognition searches the index instead of looping through every worker manually

### Web App Features

- Browser-based webcam preview and live recognition loop
- Worker enrollment directly from the root page
- Live camera enrollment capture using the `Capture From Camera` button or the `S` key
- Detection check with face-box feedback in the browser UI
- Employee removal directly from the worker table in the web app
- Real-time status, worker list, and attendance table refresh
- One-screen operational UI for local demos and admin workflows

### Example V2 Endpoints

- `GET /health`
- `GET /api/v2/status`
- `GET /api/v2/workers`
- `POST /api/v2/workers/enroll`
- `POST /api/v2/recognitions`
- `GET /api/v2/attendance`
- `POST /api/v2/index/rebuild`

### Benchmarking

You can benchmark the current recognizer on a folder dataset without recording hundreds of people yourself.

Expected dataset layout:

```text
dataset_root/
  person_001/
    01.jpg
    02.jpg
    03.jpg
    ...
  person_002/
    01.jpg
    02.jpg
    ...
```

Run an accuracy and latency benchmark:

```bash
python benchmark_v2.py dataset --dataset-root "C:\path\to\dataset" --max-people 100 --enroll-per-person 3
```

This will:

- enroll the first few images per person into an isolated benchmark database
- test the remaining images
- report detection rate, recognition accuracy, false rejects, misidentifications, and latency

Run a pure search-speed benchmark:

```bash
python benchmark_v2.py load --workers 10000 --probes 500
```

This measures how fast the active index can search a large worker count even if you do not have a large real face dataset yet.

If you do not have a large dataset, you can generate a synthetic one from the face images already stored in `data/faces`:

```bash
python -m src.v2.synthetic_dataset --output-root "data/synthetic_dataset" --identities 100 --images-per-identity 8 --clean
```

Then benchmark it:

```bash
python benchmark_v2.py dataset --dataset-root "data/synthetic_dataset" --max-people 100 --enroll-per-person 3
```

Important note:
- this synthetic dataset is useful for pipeline, throughput, and stress testing
- it is not a substitute for real cross-person accuracy testing on 100 truly different people

### Current Supported Stack

- Detector: `MediaPipe` with OpenCV cascade fallback
- Embedder: `classical` handcrafted face descriptor
- Search index: `lsh` approximate nearest-neighbor search
- Storage: `SQLite`

### What Changed In V2

- The embedder is now pluggable through `build_embedder()` in `src/v2/embedder.py`
- The vector index is now pluggable through `build_vector_index()` in `src/v2/index.py`
- The API architecture endpoint now reports requested and active backends
- The API now defaults to the supported local backend instead of an experimental deep-model install
- Recognition now batch-searches faces from a request instead of searching one-by-one
- Recognition now suppresses repeat camera matches for a short TTL to reduce redundant work
- Enrollment can now replace old embeddings for a worker to keep the index cleaner
- The API now exposes `/api/v2/status` for operational visibility
- The current defaults prioritize a stable startup path and immediate search over experimental installs

### Next Upgrade Path

For stronger accuracy later, the cleanest route is:

- keep `MediaPipe` detection
- replace the descriptor in `src/v2/embedder.py` with a supported deep embedding backend
- replace `lsh` in `src/v2/index.py` with `FAISS` or another dedicated vector index
- move from SQLite to PostgreSQL for central multi-camera deployments

### Operational Notes

- `ATTENDANCE_RECOGNITION_CACHE_TTL_SECONDS` controls short-term duplicate suppression per camera
- `ATTENDANCE_MAX_FACES_PER_REQUEST` limits how many faces a single recognition request will process
- `ATTENDANCE_DEFAULT_LIST_LIMIT` controls default list sizes for attendance reads
- `replace_existing=true` on enrollment replaces a worker's previous embeddings for the active backend with a fresh set
- embeddings are stored per backend, so switching from `classical` to `lbph` requires re-enrollment for that backend
- ambiguous matches are rejected if the top score is too close to the second-best score

## Features

- Admin login for dashboard access
- Person enrollment from webcam captures
- Face training from saved face images using OpenCV LBPH
- Live recognition with attendance marking
- SQLite storage for people and attendance records
- Daily CSV logging plus Excel export
- Basic liveness check based on face movement across frames

## Default Admin Login

- Username: `admin`
- Password: `admin123`

You can override these with environment variables:

```bash
ATTENDANCE_ADMIN_USERNAME=your_user
ATTENDANCE_ADMIN_PASSWORD=your_password
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

Launch the desktop app:

```bash
python app.py
```

Or:

```bash
python app.py gui
```

## CLI Commands

Enroll a person:

```bash
python app.py enroll --name "Alice" --images 10
```

Train encodings:

```bash
python app.py train
```

Start recognition:

```bash
python app.py recognize
```

Export today's attendance:

```bash
python app.py export --today
```

Export a date range:

```bash
python app.py export --start-date 2026-03-01 --end-date 2026-03-31
```

## Controls

- Enrollment window:
  - `s` saves a frame
  - `q` closes the window
- Recognition window:
  - `q` closes the window

## Data

- Face images: `data/faces`
- CSV attendance logs: `data/attendance`
- Excel exports: `data/exports`
- SQLite database: `data/attendance.db`
- Face encodings: `data/encodings.pkl`

## Anti-Spoofing Note

The app includes a basic liveness gate that waits for face movement across several frames before marking attendance. This helps reduce simple photo-based spoofing, but it is not a production-grade anti-spoofing system.

## Notes

- A webcam is required for enrollment and recognition.
- `face_recognition` may require extra native build tools on some systems.
- Better lighting and multiple enrollment images improve recognition quality.
- This version uses OpenCV's built-in recognizer instead of `face_recognition/dlib`, which makes installation much easier on Windows.
