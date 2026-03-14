# CodeCatalystsXNaarirakshak -- NaariRakshak
### AI-Powered Women's Safety Emergency Response System

> **Team CodeCatalysts** | **HackForImpact 2026** | **Track 2: Social Impact**

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green)](https://flask.palletsprojects.com)
[![Track](https://img.shields.io/badge/Track%202-Social%20Impact-purple)](PRD.md)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Hackathon%20MVP-orange)](PRD.md)

---

## What is NaariRakshak?

NaariRakshak is a real-time women's safety emergency response platform built for India by **Team CodeCatalysts**. When a woman is in danger, it:

1. **Detects the emergency** -- SOS button, shake detection, voice trigger, or auto-pattern
2. **Assesses the threat** -- AI engine scores severity in milliseconds (Critical/High/Moderate/Low)
3. **Dispatches the nearest help** -- Police, NGO volunteers, or medical teams via the Volunteer App
4. **Monitors public spaces** -- CCTV AI detects violence in real-time using CLIP + YOLO
5. **Keeps a command center informed** -- Live map, real-time updates, responder tracking
6. **Works offline** -- Mesh network propagates alerts through smart poles, buses, and nearby phones

---

## The Problem

- 4 lakh+ crimes against women in India annually (NCRB 2022)
- Average police response time: **12-30 minutes** in urban areas
- Most safety apps alert contacts -- not actual responders
- 70% of incidents happen in low-connectivity zones
- Victims hesitate to call 112 due to stigma and fear of disbelief
- Existing CCTV infrastructure is passive -- no real-time threat detection

---

## Screenshots

### Command Dashboard
Live alert map, AI threat levels, one-click dispatch, real-time stats, and danger zone heatmap.

![Command Dashboard](screenshots/dashboard.png)

### User Mobile App
One-tap SOS, safe check-in timer, disguise mode, audio/video evidence capture, and live location sharing.

![User Mobile App](screenshots/mobile.png)

### Volunteer App
Alert feed with distance and threat level, navigation, status updates, shift management, and encrypted chat.

![Volunteer App](screenshots/volunteer.png)

### CCTV AI Monitoring
Real-time violence detection using CLIP ViT-B/32 zero-shot classification, YOLOv8-nano person gating, and optical flow analysis.

![CCTV AI Monitoring](screenshots/cctv.png)

---

## Architecture Overview

```
+---------------------------------------------------------------+
|                     FOUR INTERFACES                            |
|                                                                |
| [User Mobile App] [Command Dashboard] [Volunteer App] [CCTV]  |
|  One-tap SOS       Live Alert Map      Dispatch View   AI Mon  |
+-------------------------------+-------------------------------+
                                | WebSocket + REST
+-------------------------------v-------------------------------+
|                       FLASK BACKEND                            |
|                                                                |
| +----------+  +----------+  +----------+  +------------------+ |
| | AI Threat |  |  Mesh   |  |  E2E     |  | CCTV AI Engine  | |
| | Engine    |  | Network |  | Encrypt  |  | CLIP + YOLO +   | |
| |           |  |         |  |          |  | Optical Flow    | |
| +----------+  +----------+  +----------+  +------------------+ |
|                                                                |
| +----------+  +----------+  +----------+  +------------------+ |
| | Route    |  | Volunteer|  | Evidence |  | Danger Zone     | |
| | Safety   |  | Dispatch |  | Capture  |  | Heatmap         | |
| +----------+  +----------+  +----------+  +------------------+ |
+-------------------------------+-------------------------------+
                                |
                       +--------v--------+
                       |    SQLite DB    |
                       +-----------------+
```

---

## Features

### For Women (User App -- `/app`)
| Feature | Description |
|---------|-------------|
| **One-Tap SOS** | Large, accessible emergency button |
| **Silent Trigger** | Shake detection or voice activation |
| **Safe Timer** | Set a check-in countdown -- auto-SOS if missed |
| **Disguise Mode** | App hides as Weather or Calculator |
| **Audio Evidence** | Silent audio recording starts on SOS trigger |
| **Video Evidence** | Video capture with encrypted storage |
| **Live Location** | Encrypted real-time GPS sharing |
| **Two-Way Chat** | E2E encrypted chat with assigned responder |
| **Community Reporting** | Report danger zones on the map |

### For Command Center (Dashboard -- `/dashboard`)
| Feature | Description |
|---------|-------------|
| **Live Map** | All active alerts, responders, danger zones on Leaflet |
| **AI Threat Levels** | Critical / High / Moderate / Low classification |
| **One-Click Dispatch** | Assign nearest available responder |
| **Real-time Stats** | Response time, active alerts, coverage metrics |
| **Sound Alerts** | Audio notification for new SOS |
| **Heatmap** | Community-reported danger zones overlay |
| **Responder Tracking** | Live location of all active responders |

### For Volunteers/Responders (Volunteer App -- `/volunteer`)
| Feature | Description |
|---------|-------------|
| **Alert Feed** | Incoming SOS with distance and threat level |
| **Navigation** | Deep link to Google Maps / OLA Maps |
| **Status Updates** | En route -> Arrived -> Resolved workflow |
| **Secure Chat** | E2E encrypted chat with victim |
| **Shift Management** | Online/Offline toggle for availability tracking |
| **Priority Dispatch** | Auto-assigned based on proximity and availability |

### CCTV AI Monitoring (`/cctv`)
| Feature | Description |
|---------|-------------|
| **Violence Detection** | Real-time classification using CLIP ViT-B/32 zero-shot |
| **Person Gating** | YOLOv8-nano filters frames -- only analyzes when people are present |
| **Optical Flow** | Motion intensity scoring to reduce false positives |
| **Balanced Labels** | 6 safe + 6 threat labels for calibrated confidence |
| **Auto-Alert** | Triggers SOS in command dashboard when violence detected |
| **Live Feed** | Webcam/CCTV stream with real-time overlay |

### Infrastructure
| Feature | Description |
|---------|-------------|
| **Mesh Network** | Offline propagation via smart poles and buses |
| **AES-256-GCM** | All location data encrypted at rest and in transit |
| **Ephemeral IDs** | User IDs rotate daily -- no persistent tracking |
| **AI Engine** | Time, location, trigger, behavioral analysis |
| **Audit Trail** | All data access logged for accountability |
| **Auto-Purge** | Alerts deleted after 48 hours, location data after 2 days |

---

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone the repo
git clone https://github.com/ayushap18/NaariRakshak.git
cd NaariRakshak

# Install dependencies
cd server
pip install -r requirements.txt

# Start the server
cd ..
./start.sh
```

### Access URLs
| Interface | URL |
|-----------|-----|
| User Mobile App | http://localhost:8000/app |
| Command Dashboard | http://localhost:8000/dashboard |
| Volunteer App | http://localhost:8000/volunteer |
| CCTV AI Monitoring | http://localhost:8000/cctv |
| API Health | http://localhost:8000/api/health |

### Demo Mode
The server auto-seeds:
- 25 responders (police, NGO volunteers, medical) around Delhi
- Demo mesh network nodes
- Mock GPS location for testing
- Sample danger zones for heatmap visualization

---

## API Reference

### REST Endpoints

```
POST /api/register              Register new user
POST /api/sos/trigger           Trigger emergency alert
POST /api/sos/cancel            Cancel active alert
GET  /api/alerts                List all alerts (filter by status)
GET  /api/alerts/<id>           Get specific alert
GET  /api/responders            List responders
POST /api/responders            Add responder
GET  /api/mesh/nodes            Get mesh network topology
GET  /api/health                System health check
GET  /api/danger-zones          Get community danger zones
POST /api/danger-zones          Report a danger zone
GET  /api/route/safety          Get safety score for route
POST /api/checkin-timer         Set safe check-in timer
```

### WebSocket Events

```
Client -> Server:
  user_register          Register user session
  dispatch_responder     Manually dispatch a responder
  update_alert_status    Change alert status
  check_in_timer         Set safe check-in timer
  volunteer_status       Toggle volunteer online/offline
  chat_message           Send encrypted chat message

Server -> Client:
  alert_triggered        New SOS broadcast
  alert_cancelled        Alert cancelled
  alert_status_changed   Workflow status update
  location_updated       Real-time location update
  responder_dispatched   Responder assigned to alert
  timer_expiring         Check-in timer warning
  cctv_violence_alert    CCTV AI violence detection alert
  chat_message           Incoming encrypted chat message
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10, Flask 3.0, Flask-SocketIO |
| Database | SQLite (dev) -> PostgreSQL (prod) |
| CCTV AI | OpenAI CLIP (ViT-B/32) zero-shot, YOLOv8-nano (Ultralytics), OpenCV optical flow |
| AI/ML | scikit-learn, numpy, pandas |
| Encryption | cryptography (AES-256-GCM), pycryptodome |
| Maps | Leaflet.js + OpenStreetMap, Google Maps API |
| Real-time | Socket.IO (WebSocket) |
| Mobile | PWA (HTML5 + JS) |
| Infrastructure | ngrok (demo), Docker (roadmap) |

---

## Project Structure

```
NaariRakshak/
+-- server/
|   +-- app.py                 # Main Flask application + routes
|   +-- config.py              # Environment configuration
|   +-- models.py              # SQLAlchemy database models
|   +-- encryption.py          # AES-256-GCM encryption layer
|   +-- ai_engine.py           # Threat assessment AI
|   +-- cctv_ai.py             # CCTV violence detection (CLIP + YOLO)
|   +-- gemini_ai.py           # Gemini AI integration
|   +-- mesh_network.py        # Offline mesh propagation
|   +-- requirements.txt       # Python dependencies
|   +-- static/
|   |   +-- js/
|   +-- templates/
|   |   +-- dashboard.html     # Command center UI
|   |   +-- mobile.html        # User mobile app
|   |   +-- volunteer.html     # Volunteer/responder app
|   |   +-- cctv.html          # CCTV AI monitoring UI
|   +-- evidence/              # Encrypted evidence storage
|   +-- models/                # AI model cache
+-- screenshots/               # Interface screenshots
+-- start.sh                   # Server startup script
+-- PRD.md                     # Product Requirements Document
+-- README.md                  # This file
+-- FEATURES.md                # Feature backlog & ideas
+-- HACKATHON_PLAN.md          # 24-hour sprint plan
+-- DESIGN.md                  # UI/UX design decisions
```

---

## Privacy & Security

- **No persistent user tracking** -- ephemeral IDs rotate every 24 hours
- **Location data encrypted** -- AES-256-GCM with session-specific keys
- **Phone numbers hashed** -- PBKDF2-HMAC-SHA256, never stored in plaintext
- **Auto-purge** -- Alerts deleted after 48 hours, location updates after 2 days
- **Audit logs** -- All data access logged with IP and timestamp
- **Coarse location privacy** -- Initial broadcasts use 500m radius only
- **Evidence encryption** -- Audio/video evidence encrypted with AES-256-GCM
- **Compliant** -- IT Act 2000, PDPB 2023 ready

---

## Roadmap

### Hackathon (24h) -- ALL COMPLETED
- [x] SOS trigger + AI assessment + responder dispatch
- [x] Real-time command dashboard with live map
- [x] Mesh network simulation
- [x] E2E encryption
- [x] Volunteer app with shift management
- [x] Safe check-in timer
- [x] Audio/video evidence capture
- [x] Danger zone reporting + heatmap
- [x] Two-way encrypted responder chat
- [x] Disguise mode
- [x] CCTV AI violence detection (CLIP + YOLO + optical flow)

### Post-Hackathon (Phase 2)
- [ ] React Native mobile app (iOS + Android)
- [ ] 112 India API integration
- [ ] Multi-language support (Hindi, Tamil, Telugu, Bengali)
- [ ] Safe route navigator with Walk With Me mode
- [ ] Wearable device SOS (smartwatch)
- [ ] PostgreSQL migration
- [ ] Production deployment on GCP/AWS India region
- [ ] NGO partnership dashboard
- [ ] Predictive safety analytics

---

## Team CodeCatalysts

Built with purpose at **HackForImpact 2026** -- Track 2: Social Impact.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

*"Technology can't solve everything, but it can make sure help arrives faster."*
