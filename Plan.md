# FORGE MVP --- Plan.md

## Goal

Build a working MVP for FORGE: an observability and incident-detection
layer for computer vision systems.

The MVP should:

-   Accept a single video file
-   Accept a directory of videos
-   Accept a live video stream (RTSP/webcam)
-   Run inference automatically
-   Monitor health and quality
-   Detect anomalies
-   Save evidence around incidents
-   Display results through an API/dashboard

------------------------------------------------------------------------

# Guiding Principle

Use a modular monolith.

Avoid full microservices.

Structure code cleanly so it can later become services if needed.

------------------------------------------------------------------------

# Target Users

-   Vision system support teams
-   OEMs
-   Factory operators

Primary MVP question:

"What changed, when did it change, and why?"

------------------------------------------------------------------------

# Supported Inputs

## Single Video

Example:

python main.py --input video.mp4

## Directory

Example:

python main.py --input ./videos/

Pipeline processes all videos sequentially.

## Stream

Examples:

python main.py --input rtsp://camera_url python main.py --input webcam

------------------------------------------------------------------------

# High-Level Architecture

Input Layer ↓ Frame Loader ↓ Inference Worker ↓ Monitoring Layer ↓
Incident Engine ↓ Storage Layer ↓ API ↓ Dashboard

------------------------------------------------------------------------

# Repo Structure

forge-mvp/

├── app/

│ ├── ingestion/ │ │ ├── video_loader.py │ │ ├── directory_loader.py │ │
└── stream_loader.py │ │ │ ├── inference/ │ │ ├── yolo_runner.py │ │ └──
model_wrapper.py │ │ │ ├── monitoring/ │ │ ├── confidence_monitor.py │ │
├── blur_monitor.py │ │ ├── brightness_monitor.py │ │ ├──
latency_monitor.py │ │ └── hardware_monitor.py │ │ │ ├── incidents/ │ │
├── incident_engine.py │ │ ├── evidence_manager.py │ │ └──
trigger_rules.py │ │ │ ├── storage/ │ │ ├── database.py │ │ └──
file_storage.py │ │ │ ├── api/ │ │ └── routes.py │ │ │ └── dashboard/

├── data/ ├── outputs/ ├── docker-compose.yml ├── requirements.txt └──
main.py

------------------------------------------------------------------------

# Core Pipeline

Frame

→ inference

→ metrics extraction

→ anomaly checks

→ incident rules

→ evidence capture

→ database

------------------------------------------------------------------------

# Metrics To Capture

Per frame:

-   timestamp
-   source_id
-   prediction
-   confidence
-   inference_time_ms
-   fps
-   brightness
-   blur score

Per system:

-   CPU usage
-   RAM usage
-   GPU usage
-   GPU memory
-   GPU temperature

------------------------------------------------------------------------

# Incident Rules V1

Confidence collapse:

if confidence \< baseline \* .7

Blur spike:

if blur \> threshold

Low FPS:

if fps \< threshold

Camera disconnected:

if no frame received

Temperature warning:

if GPU temperature high

------------------------------------------------------------------------

# Evidence Storage

Save:

-   frame before incident
-   incident frame
-   frame after incident
-   metrics snapshot
-   timestamps

Directory:

outputs/incidents/

------------------------------------------------------------------------

# Tech Stack

Backend: - FastAPI

Inference: - YOLO

Monitoring: - OpenCV - psutil - pynvml

Database: - PostgreSQL

Frontend: - React

Deployment: - Docker Compose

------------------------------------------------------------------------

# Milestone Plan

Week 1

-   Build loaders
-   Support video + directory + stream

Week 2

-   Add YOLO inference
-   Add metrics extraction

Week 3

-   Add anomaly detection
-   Add incident engine

Week 4

-   Dashboard
-   Incident review page
-   Export reports

------------------------------------------------------------------------

# Success Criteria

System can:

1.  Ingest videos automatically
2.  Run inference
3.  Detect failures
4.  Save evidence
5.  Display incidents

MVP complete when a demo can show:

Normal operation

→ degradation introduced

→ FORGE detects issue

→ evidence stored

→ incident visible in dashboard
