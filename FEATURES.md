# NaariRakshak — Feature Ideas & Backlog
> Living document for Team CodeCatalysts | HackForImpact 2026 | Track 2: Social Impact

---

## Currently Built (v1 MVP)

- [x] One-tap SOS button
- [x] Shake detection trigger
- [x] Voice trigger
- [x] Real-time GPS location sharing
- [x] AI threat level assessment (Critical/High/Moderate/Low)
- [x] Auto-dispatch to nearest responder
- [x] Command center dashboard with live Leaflet map
- [x] 25 pre-seeded responders (police, volunteers, medical)
- [x] WebSocket real-time updates
- [x] AES-256-GCM end-to-end encryption
- [x] Ephemeral user IDs (daily rotation)
- [x] Mesh network offline propagation simulator
- [x] Audit logging
- [x] Auto-purge after 48 hours
- [x] Volunteer/Responder App with alert feed, navigation, status updates
- [x] Volunteer online/offline shift management
- [x] Safe check-in timer (5/15/30/60 min + custom)
- [x] Community danger zone reporting + heatmap overlay
- [x] Two-way E2E encrypted chat (victim <-> responder)
- [x] Audio evidence capture (silent, encrypted)
- [x] Video evidence capture (encrypted WebM, linked to alert ID)
- [x] Disguise mode (Weather App / Calculator decoy)
- [x] CCTV AI violence detection (CLIP ViT-B/32 zero-shot + YOLOv8-nano person gate + optical flow)

---

## Hackathon Sprint (24h — Completed)

### HIGH IMPACT / LOW EFFORT — ALL DONE

#### H1 — Volunteer/Responder App [DONE]
A dedicated PWA for NGO volunteers and community responders.
- Alert feed showing distance + threat level
- "Accept" / "Decline" buttons
- Navigation deep-link to OLA Maps / Google Maps
- En Route → Arrived → Resolved status buttons
- Shift check-in/check-out
- **Why it matters:** Current system has no interface for volunteers. This closes the loop.

#### H2 — Safe Check-In Timer [DONE]
User sets a countdown before entering a risky situation.
- Timer options: 5 / 15 / 30 / 60 min, or custom
- Single-tap check-in to reset
- Push notification at 1 min warning
- Auto-SOS trigger with "check-in missed" context fed to AI
- **Why it matters:** Preventive safety for known-risk situations (late night travel, first dates, etc.)

#### H3 — Danger Zone Community Reporting [DONE]
Crowdsourced safety intelligence.
- Pin a zone on map with category: harassment, poor lighting, isolated, crime-prone
- Requires 3+ reports to appear publicly
- Heatmap overlay in command dashboard
- AI engine boosts threat score for alerts in danger zones (+15%)
- Zone expires after 30 days without reconfirmation
- **Why it matters:** Gives the AI real local knowledge, not just generic time/location scoring.

#### H4 — Two-Way Encrypted Chat [DONE]
Secure communication channel between victim and assigned responder.
- Opens automatically when responder is dispatched
- Pre-set quick-reply buttons: "I'm safe now", "Still in danger", "Send help fast"
- E2E encrypted (same layer as location data)
- Auto-closes on alert resolution, messages purged 24h later
- **Why it matters:** Right now victim gets no confirmation responder is coming.

#### H5 — Audio Evidence Capture (Silent) [DONE]
Silent audio recording on SOS trigger.
- 2-minute encrypted recording stored locally on device
- Option to upload to case file at alert resolution
- Encrypted using AES-256, associated with alert ID
- User must explicitly consent in onboarding
- **Why it matters:** Evidence capture dramatically improves prosecution rates.

#### H6 — Video Evidence Capture [DONE]
Video recording on SOS trigger.
- Encrypted WebM video capture linked to alert ID
- Stored in server evidence directory with unique filenames
- AES-256-GCM encrypted at rest
- Accessible from command dashboard for review
- **Why it matters:** Video evidence provides stronger documentation for legal proceedings.

#### H7 — CCTV AI Violence Detection [DONE]
Real-time violence detection from CCTV/webcam feeds using multi-model AI pipeline.
- **CLIP ViT-B/32 zero-shot classification** with balanced 6 safe + 6 threat labels
- **YOLOv8-nano person gating** -- only runs classification when people are detected in frame
- **Optical flow analysis** -- motion intensity scoring to filter out static false positives
- Configurable confidence threshold for alert triggering
- Auto-generates SOS alert in command dashboard when violence is detected
- Live feed display with real-time overlay showing detection status
- Event log with timestamps and confidence scores
- **Why it matters:** Turns passive CCTV infrastructure into an active safety system that detects threats without human monitoring.

#### H8 — Volunteer Online/Offline Shift Tracking [DONE]
Shift management system for volunteer responders.
- Online/Offline toggle in Volunteer App UI
- Only online volunteers receive dispatch assignments
- Shift status visible in command dashboard
- Proximity-based auto-dispatch considers only available (online) volunteers
- **Why it matters:** Ensures dispatch only targets available responders, reducing response time and failed dispatches.

---

### MEDIUM IMPACT / MEDIUM EFFORT

#### M1 — Silent/Disguise Mode [DONE]
For domestic violence situations where the attacker may see the phone.
- App icon replaceable with "Weather App" or "Calculator"
- Decoy screen shows on open
- Hidden trigger: triple-tap volume button or specific sequence
- Alert is sent silently (no sound, no vibration)
- Configurable in settings

#### M2 — Safe Route Navigator
Pre-journey safety intelligence.
- Enter destination → system evaluates route safety
- Safety score overlay on map (green/yellow/red segments)
- Route scores based on: time of day, danger zones, responder coverage, historical alerts
- "Walk With Me" mode: auto-SOS if movement stops for > 3 minutes
- Integration with Google Directions API / OLA Maps

#### M3 — Trusted Contacts Network
Beyond emergency responders — personal safety network.
- Add 3–5 trusted contacts (family, friends)
- On SOS: encrypted SMS + WhatsApp-deep-link sent to contacts
- Contacts can see live location on a shareable link (24h expiry)
- "I'm home safe" one-tap notification to all contacts
- Contacts can trigger wellness check (ping user)

#### M4 — Multi-Language Support (Hindi First)
- Language selection on onboarding screen
- All UI strings in: Hindi, English, Tamil, Telugu, Bengali
- Alert messages to contacts sent in user's preferred language
- Voice trigger in regional language
- i18n JSON files per language

#### M5 — Responder Rating System
Post-incident feedback loop.
- After alert resolved: user rates responder (1–5 stars + optional note)
- Ratings visible in command dashboard per responder
- Low-rated responders flagged for review
- Top-rated volunteers get priority dispatch

---

### FUTURE / POST-HACKATHON

#### F1 — Wearable SOS (Smartwatch)
- Apple Watch / Wear OS companion app
- Hold side button for 3 seconds → triggers NaariRakshak SOS
- Watch shows responder status and ETA
- Haptic feedback when responder is dispatched

#### F2 — Smart Panic Button Hardware
- IoT device (Raspberry Pi Pico W based)
- Clips to bag or clothing
- Single button → MQTT message to NaariRakshak backend
- Configurable LED feedback: solid (safe), blinking (alert active), pulsing (responder en route)
- Battery lasts 6 months

#### F3 — 112 India API Integration
- Direct integration with India's emergency number dispatch system
- Auto-escalate Critical threats to 112 with pre-formatted FIR report
- Two-way sync: if 112 closes a case, NaariRakshak updates alert

#### F4 — AI-Powered Predictive Policing (Privacy-Preserving)
- Federated learning across all city deployments
- Predict high-risk time windows for specific areas
- Pre-position volunteers before incidents happen
- Fully anonymized — no user-level data used

#### F5 — NGO Partnership Dashboard
- Separate login for NGO partners (Blank Noise, iCall, etc.)
- See anonymized incident data in their service area
- Resource planning tools (volunteer scheduling, coverage gaps)
- Direct intake for post-incident counseling referral

#### F6 — Evidence Chain of Custody
- Court-admissible evidence packaging
- Cryptographic hash of audio/location evidence
- Timestamped with RFC 3161 trusted timestamp
- Export as PDF affidavit for FIR filing

#### F7 — React Native Mobile App
- Full native iOS and Android experience
- Background location updates
- Native push notifications
- Offline-first with local SQLite sync
- Secure enclave for key storage

#### F8 — Multilingual Voice Commands
- "Bachao" (Save me) → triggers SOS in Hindi
- "Help me" → English trigger
- Works in all 5 supported languages
- On-device speech recognition (no cloud dependency)

#### F9 — Community Safety Score
- Each area gets a real-time safety score (A-F grade)
- Based on: current active alerts, historical incidents, time of day, responder density
- Displayed on map as color-coded zones
- API endpoint for third-party integration (cab apps, delivery apps)

#### F10 — Incident Pattern Analytics (Command Center)
- Weekly/monthly incident reports for operators
- Peak time analysis
- Responder performance metrics
- Geographic clustering of incidents
- Export to CSV / PDF for police reports

---

## Feature Voting Board

Use this table to prioritize during the sprint:

| Feature | Impact (1-5) | Effort (1-5) | Score (I/E) | Sprint? |
|---------|-------------|--------------|-------------|---------|
| Volunteer App | 5 | 2 | 2.5 | DONE |
| Safe Timer | 5 | 1 | 5.0 | DONE |
| Danger Zones | 4 | 2 | 2.0 | DONE |
| Two-way Chat | 4 | 2 | 2.0 | DONE |
| Audio Evidence | 4 | 2 | 2.0 | DONE |
| Video Evidence | 4 | 2 | 2.0 | DONE |
| Disguise Mode | 4 | 3 | 1.3 | DONE |
| CCTV AI Violence Detection | 5 | 3 | 1.7 | DONE |
| Volunteer Shift Tracking | 4 | 1 | 4.0 | DONE |
| Safe Route | 3 | 4 | 0.75 | MAYBE |
| Trusted Contacts | 4 | 3 | 1.3 | MAYBE |
| Multi-language | 3 | 3 | 1.0 | MAYBE |
| Wearable SOS | 5 | 5 | 1.0 | NO |
| 112 Integration | 5 | 5 | 1.0 | NO |

---

## Design Principles

1. **Panic-proof UI** — In an emergency, fine motor control degrades. Tap targets must be huge.
2. **3-second rule** — From unlock to SOS triggered in under 3 seconds.
3. **Privacy by default** — Collect the minimum needed. Encrypt everything. Delete fast.
4. **Works for everyone** — Rural women with 2G phones, illiterate users, elderly users.
5. **No gatekeeping** — No account needed to send an SOS. Registration optional.
6. **Trust through transparency** — Open source, auditable encryption, no dark patterns.

---

*Last updated: 2026-03-14 | Team CodeCatalysts | NaariRakshak HackForImpact 2026*
