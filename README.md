# NaariRakshak — नारीरक्षक
### AI-Powered Women's Safety Emergency Response System

> **HackForImpact 2026** | Women's Safety Track

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-green)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Hackathon%20MVP-orange)](PRD.md)

---

## What is NaariRakshak?

NaariRakshak is a real-time women's safety emergency response platform built for India. When a woman is in danger, it:

1. **Detects the emergency** — SOS button, shake detection, voice trigger, or auto-pattern
2. **Assesses the threat** — AI engine scores severity in milliseconds
3. **Dispatches the nearest help** — Police, NGO volunteers, or medical teams
4. **Keeps a command center informed** — Live map, real-time updates, responder tracking
5. **Works offline** — Mesh network propagates alerts through smart poles, buses, and nearby phones

---

## The Problem

- 4 lakh+ crimes against women in India annually (NCRB 2022)
- Average police response time: **12–30 minutes** in urban areas
- Most safety apps alert contacts — not actual responders
- 70% of incidents happen in low-connectivity zones
- Victims hesitate to call 112 due to stigma and fear of disbelief

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                 THREE INTERFACES                         │
│                                                         │
│  [User Mobile App]  [Command Dashboard]  [Volunteer App] │
│   One-tap SOS        Live Alert Map       Dispatch View  │
└────────────────────────────┬────────────────────────────┘
                             │ WebSocket + REST
┌────────────────────────────▼────────────────────────────┐
│                   FLASK BACKEND                          │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │ AI Threat │  │  Mesh   │  │  E2E     │  │ Route  │  │
│  │ Engine   │  │ Network │  │ Encrypt  │  │ Safety │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
└────────────────────────────┬────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │    SQLite DB    │
                    └─────────────────┘
```

---

## Features

### For Women (User App)
| Feature | Description |
|---------|-------------|
| **One-Tap SOS** | Large, accessible emergency button |
| **Silent Trigger** | Shake detection or voice activation |
| **Safe Timer** | Set a check-in countdown — auto-SOS if missed |
| **Disguise Mode** | App hides as Weather or Calculator |
| **Audio Evidence** | Silent recording starts on SOS trigger |
| **Live Location** | Encrypted real-time GPS sharing |
| **Multi-language** | Hindi, English, Tamil, Telugu, Bengali |

### For Command Center (Dashboard)
| Feature | Description |
|---------|-------------|
| **Live Map** | All active alerts, responders, danger zones |
| **AI Threat Levels** | Critical / High / Moderate / Low classification |
| **One-Click Dispatch** | Assign nearest available responder |
| **Real-time Stats** | Response time, active alerts, coverage |
| **Sound Alerts** | Audio notification for new SOS |
| **Heatmap** | Community-reported danger zones overlay |

### For Volunteers/Responders (Volunteer App)
| Feature | Description |
|---------|-------------|
| **Alert Feed** | Incoming SOS with distance and threat level |
| **Navigation** | Deep link to Google Maps / OLA Maps |
| **Status Updates** | En route → Arrived → Resolved |
| **Secure Chat** | E2E encrypted chat with victim |
| **Shift Management** | Check-in/out for availability tracking |

### Infrastructure
| Feature | Description |
|---------|-------------|
| **Mesh Network** | Offline propagation via smart poles & buses |
| **AES-256-GCM** | All location data encrypted at rest |
| **Ephemeral IDs** | User IDs rotate daily — no persistent tracking |
| **AI Engine** | Time, location, trigger, behavioral analysis |
| **Audit Trail** | All data access logged for accountability |

---

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone the repo
git clone https://github.com/your-team/naarirakshak
cd naarirakshak

# Install dependencies
cd server
pip install -r requirements.txt

# Start the server
cd ..
./start.sh
```

### Access
| Interface | URL |
|-----------|-----|
| Command Dashboard | http://localhost:8000/dashboard |
| User Mobile App | http://localhost:8000/mobile |
| Volunteer App | http://localhost:8000/volunteer |
| API Health | http://localhost:8000/api/health |

### Demo Mode
The server auto-seeds:
- 25 responders (police, NGO volunteers, medical) around Delhi
- Demo mesh network nodes
- Mock GPS location for testing

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
Client → Server:
  user_register          Register user session
  dispatch_responder     Manually dispatch a responder
  update_alert_status    Change alert status
  check_in_timer         Set safe check-in timer

Server → Client:
  alert_triggered        New SOS broadcast
  alert_cancelled        Alert cancelled
  alert_status_changed   Workflow status update
  location_updated       Real-time location update
  responder_dispatched   Responder assigned to alert
  timer_expiring         Check-in timer warning
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10, Flask 3.0, Flask-SocketIO |
| Database | SQLite (dev) → PostgreSQL (prod) |
| ML/AI | scikit-learn, numpy, pandas |
| Encryption | cryptography (AES-256-GCM), pycryptodome |
| Maps | Leaflet.js + OpenStreetMap |
| Real-time | Socket.IO (WebSocket) |
| Mobile | PWA (HTML5 + JS), React Native (roadmap) |
| Infrastructure | ngrok (demo), Docker (roadmap) |

---

## Project Structure

```
naarirakshak/
├── server/
│   ├── app.py              # Main Flask application + routes
│   ├── config.py           # Environment configuration
│   ├── models.py           # SQLAlchemy database models
│   ├── encryption.py       # AES-256-GCM encryption layer
│   ├── ai_engine.py        # Threat assessment AI
│   ├── mesh_network.py     # Offline mesh propagation
│   ├── requirements.txt    # Python dependencies
│   ├── static/
│   │   └── js/
│   └── templates/
│       ├── dashboard.html  # Command center UI
│       ├── mobile.html     # User mobile app
│       └── volunteer.html  # Volunteer/responder app
├── start.sh                # Server startup script
├── PRD.md                  # Product Requirements Document
├── README.md               # This file
├── FEATURES.md             # Feature backlog & ideas
├── HACKATHON_PLAN.md       # 24-hour sprint plan
└── DESIGN.md               # UI/UX design decisions
```

---

## Privacy & Security

- **No persistent user tracking** — ephemeral IDs rotate every 24 hours
- **Location data encrypted** — AES-256-GCM with session-specific keys
- **Phone numbers hashed** — PBKDF2-HMAC-SHA256, never stored in plaintext
- **Auto-purge** — Alerts deleted after 48 hours, location updates after 2 days
- **Audit logs** — All data access logged with IP and timestamp
- **Coarse location privacy** — Initial broadcasts use 500m radius only
- **Compliant** — IT Act 2000, PDPB 2023 ready

---

## Roadmap

### Hackathon (24h)
- [x] SOS trigger + AI assessment + responder dispatch
- [x] Real-time command dashboard with live map
- [x] Mesh network simulation
- [x] E2E encryption
- [ ] Volunteer app UI
- [ ] Safe check-in timer
- [ ] Audio evidence capture
- [ ] Danger zone reporting
- [ ] Two-way responder chat

### Post-Hackathon (Phase 2)
- [ ] React Native mobile app (iOS + Android)
- [ ] 112 India API integration
- [ ] Multi-language support
- [ ] Safe route navigator
- [ ] Wearable device SOS (smartwatch)
- [ ] PostgreSQL migration
- [ ] Production deployment on GCP/AWS India region

---

## Team

Built with purpose at **HackForImpact 2026**.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

*"Technology can't solve everything, but it can make sure help arrives faster."*
