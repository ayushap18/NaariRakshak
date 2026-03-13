# NaariRakshak — Product Requirements Document
> HackForImpact 2026 | 24-Hour Sprint

---

## 1. Product Vision

**NaariRakshak** (नारीरक्षक — "Women Protector") is a full-stack emergency response platform that bridges the gap between women in distress and immediate help. Unlike apps that just send a text or call a number, NaariRakshak is an **intelligent dispatch system** — combining AI threat assessment, encrypted location sharing, mesh networking, and a real-time command center — all designed to work even in low-connectivity environments across India.

**One sentence:** When a woman is in danger, NaariRakshak finds the nearest help, dispatches it in seconds, and keeps a command center informed — end to end.

---

## 2. Problem Statement

| Stat | Source |
|------|--------|
| 4 lakh+ crimes against women reported in India per year | NCRB 2022 |
| Average police response time in urban India: 12–30 minutes | CAG Report |
| 70% of incidents happen in areas with poor mobile connectivity | ITU |
| Most safety apps are "shout into the void" — they alert contacts, not responders | Market Research |
| Women hesitate to call 112 due to stigma or fear of not being believed | ICRW India |

**Core problem:** Existing solutions are reactive (post-incident) and disconnected from actual emergency dispatch infrastructure. There is no real-time coordination layer between distressed individuals and available responders.

---

## 3. Target Users

| Persona | Description | Key Need |
|---------|-------------|----------|
| **Priya** (Urban woman, 22) | College student, travels late | One-touch SOS, silent alert mode |
| **Lakshmi** (Rural woman, 35) | Factory worker, low-data phone | Offline mesh alert, SMS fallback |
| **Ravi** (Police officer) | Beat constable, field duty | Mobile-friendly dispatch app |
| **Ananya** (NGO Volunteer) | Community watch coordinator | Alert awareness, reporting tools |
| **CMD Operator** (25–45) | District control room staff | Full situational awareness dashboard |

---

## 4. Product Scope (Hackathon MVP)

### 4.1 Core Platforms

```
Platform A — User Mobile App       (mobile.html / React Native future)
Platform B — Central Command       (dashboard.html / React future)
Platform C — Volunteer/Responder   (NEW — volunteer.html)
```

### 4.2 Feature Priority Matrix

| Feature | Priority | Platform | Status |
|---------|----------|----------|--------|
| SOS Button (one-tap) | P0 | User | ✅ Built |
| Real-time location tracking | P0 | User | ✅ Built |
| AI threat level classification | P0 | Backend | ✅ Built |
| Responder auto-dispatch | P0 | Backend | ✅ Built |
| Live alert map | P0 | Dashboard | ✅ Built |
| Mesh network propagation | P0 | Backend | ✅ Built |
| E2E encryption | P0 | Backend | ✅ Built |
| Volunteer app | P1 | Volunteer | 🔴 TODO |
| Safe check-in timer | P1 | User | 🔴 TODO |
| Two-way responder chat | P1 | All | 🔴 TODO |
| Community danger zones | P1 | All | 🔴 TODO |
| Audio evidence recording | P1 | User | 🔴 TODO |
| Multi-language support | P1 | User | 🔴 TODO |
| Safe route navigator | P2 | User | 🔴 TODO |
| Wearable (smartwatch) SOS | P2 | User | 🔴 TODO |
| Anonymous incident reporting | P2 | User | 🔴 TODO |
| NGO integration API | P2 | Backend | 🔴 TODO |
| Crowdsourced safety heatmap | P2 | Dashboard | 🔴 TODO |

---

## 5. Feature Requirements

### F-001: Volunteer/Responder Mobile App (NEW)

**Problem:** Volunteers currently have no dedicated interface. They receive no real-time information.

**Solution:** A lightweight PWA for volunteers showing:
- Assigned alerts on map
- Navigation to victim location
- Status update buttons (en route → arrived → resolved)
- Two-way secure chat with victim
- Check-in for shift start/end

**Acceptance Criteria:**
- Volunteer sees alert within 5 seconds of SOS trigger
- Navigation shows Google Maps / OLA Maps deep link
- Status updates are reflected in command center in real-time
- Works on 2G/3G with offline fallback

---

### F-002: Safe Check-In Timer

**Problem:** Women often know they're entering a risky situation and want a passive safety net.

**Solution:** User sets a timer (5, 15, 30, 60 minutes). If they don't check in before it expires, an automatic SOS is triggered with reduced confidence level.

**Acceptance Criteria:**
- Timer visible on home screen
- Single-tap check-in to reset
- Push notification warning at 1 minute before expiry
- Auto-SOS with note "check-in missed" in AI context

---

### F-003: Community Danger Zone Reporting

**Problem:** Hotspot areas are known locally but not aggregated digitally.

**Solution:** Users and responders can flag zones on the map. Zones show a heatmap overlay in the dashboard. AI engine uses zone risk scores in threat assessment.

**Acceptance Criteria:**
- Flag a danger zone with type (harassment, poor lighting, isolated area)
- Minimum 3 independent reports to show on map
- Zone expires after 30 days without reconfirmation
- Integrated into AI risk scoring (+15% weight for known danger zones)

---

### F-004: Two-Way Secure Communication

**Problem:** Once SOS is triggered, there's no channel between victim and responder.

**Solution:** Encrypted real-time text channel opened between user and assigned responder for the duration of the alert.

**Acceptance Criteria:**
- Channel opens automatically upon responder dispatch
- Messages encrypted (same E2E encryption layer)
- Supports pre-set quick-replies for victim (e.g., "I'm safe now", "Still in danger")
- Auto-closes when alert is resolved
- Message history purged after 24 hours

---

### F-005: Silent/Disguise Mode

**Problem:** In domestic violence situations, the attacker may be watching the victim's phone.

**Solution:** App can be disguised as a "Weather App" or "Calculator". SOS can be triggered via a hidden gesture (e.g., triple-tap power button or specific number sequence).

**Acceptance Criteria:**
- Alternative app icon selectable in settings
- Hidden trigger gesture configurable
- App launcher shows decoy screen
- Alert is triggered silently (no sound, no vibration by default)

---

### F-006: Audio Evidence Capture

**Problem:** Incident evidence is rarely captured, making prosecution difficult.

**Solution:** When SOS is triggered, the app silently begins a 2-minute audio recording stored locally and encrypted. User can choose to upload to case file.

**Acceptance Criteria:**
- Recording starts within 3 seconds of SOS
- Stored in AES-256 encrypted container on device
- User shown option to upload/discard at alert resolution
- Compliant with IT Act (recording in own presence)

---

### F-007: Multi-Language Support

**Problem:** India has 22 official languages. English-only app excludes most at-risk users.

**Solution:** i18n support for Hindi, English, Tamil, Telugu, Bengali (Phase 1).

**Acceptance Criteria:**
- Language selectable on onboarding
- All UI strings translated
- Alert messages to contacts in selected language
- Fallback to Hindi if translation missing

---

### F-008: Safe Route Navigator

**Problem:** Preventive safety is as important as incident response.

**Solution:** Before travel, user can request a "safety score" for a route based on:
- Time of day
- Known danger zones
- Distance from mesh nodes / responders
- Historical incident density

**Acceptance Criteria:**
- Integration with Google Maps Directions API
- Safety overlay on route (green/yellow/red segments)
- Suggested safer alternative routes
- "Walk with me" mode that auto-triggers SOS if movement stops unexpectedly

---

## 6. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Latency** | SOS trigger to first responder notification < 3 seconds |
| **Availability** | 99.9% uptime during active incidents |
| **Offline** | Core SOS functional with no internet (mesh / SMS fallback) |
| **Privacy** | Zero PII in logs; ephemeral IDs rotate daily |
| **Security** | AES-256-GCM for all location data; PBKDF2 for phone storage |
| **Scale** | Support 10,000 concurrent users per city deployment |
| **Compliance** | IT Act 2000, PDPB 2023 compliant |
| **Accessibility** | WCAG 2.1 AA for dashboard; large tap targets on mobile |

---

## 7. Technical Architecture (Hackathon Target)

```
┌────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                            │
├──────────────────┬─────────────────────┬───────────────────────┤
│  User App        │  Command Dashboard  │  Volunteer App        │
│  (mobile.html)   │  (dashboard.html)   │  (volunteer.html NEW) │
│  React Native    │  React + Leaflet    │  PWA + React          │
│  (future)        │  (future)           │  (hackathon: HTML)    │
└────────┬─────────┴──────────┬──────────┴────────────┬──────────┘
         │    WebSocket       │    REST API            │
         └────────────────────┼────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│                       BACKEND (Flask)                          │
├──────────────────────────────────────────────────────────────┬─┤
│  SOS Handler │ Responder Dispatch │ WebSocket Events          │ │
│  AI Engine   │ Mesh Network       │ Encryption Manager       │ │
│  Route Safety│ Danger Zone API    │ Audio Evidence Store     │ │
└──────────────────────────────────────────────────┬───────────┘ │
                                                   │             │
                              ┌────────────────────▼──────────┐  │
                              │   SQLite → PostgreSQL (prod)  │  │
                              └───────────────────────────────┘  │
                                                                  │
                              ┌───────────────────────────────┐   │
                              │  External Integrations        │   │
                              │  - OLA Maps / Google Maps     │   │
                              │  - Twilio SMS fallback        │   │
                              │  - 112 India API (future)     │   │
                              └───────────────────────────────┘   │
```

---

## 8. Success Metrics

| Metric | Target (Demo Day) |
|--------|-------------------|
| SOS to dispatch time | < 5 seconds |
| False positive rate | < 10% |
| Responder acceptance rate | > 80% |
| Offline coverage (mesh demo) | 5+ node relay |
| Concurrent demo users | 50+ |

---

## 9. Out of Scope (Hackathon)

- Native iOS / Android apps
- 112 government API integration
- Production-grade deployment (Kubernetes, etc.)
- Payment / subscription model
- Legal / court submission workflow for evidence

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Geolocation not available (browser permissions) | Mock GPS demo mode fallback |
| SQLite not scalable | Documented migration path to PostgreSQL |
| Battery drain from continuous location | Adaptive location update interval |
| Privacy law compliance | Minimal data, E2E encryption, user consent flow |

---

*Document owner: Hackathon Team NaariRakshak | Last updated: 2026-03-13*
