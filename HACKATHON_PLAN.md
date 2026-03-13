# NaariRakshak — 24-Hour Hackathon Sprint Plan
> HackForImpact 2026 | Start: Day 1, 9:00 AM

---

## Sprint Goals

By the end of 24 hours, we demo:
1. A **user mobile app** that triggers SOS in < 3 seconds
2. A **command dashboard** showing live alerts on a map with AI threat levels
3. A **volunteer app** where responders accept and navigate to incidents
4. **Safe check-in timer** with auto-SOS fallback
5. **Danger zone reporting** visible as heatmap on dashboard
6. **Two-way encrypted chat** between victim and responder
7. A convincing **end-to-end demo flow** from SOS to resolved

---

## Team Roles (Suggested for 3-5 person team)

| Role | Responsibilities |
|------|-----------------|
| **Backend Lead** | Flask routes, WebSocket handlers, new API endpoints |
| **Frontend Lead** | Volunteer app HTML/CSS/JS, improvements to mobile + dashboard |
| **AI/Data** | Enhance threat engine, danger zone scoring, route safety |
| **Design/UX** | Figma mockups, CSS polish, accessibility |
| **Demo/Docs** | PRD, pitch deck, demo script, video recording |

---

## Hour-by-Hour Schedule

### PHASE 1 — Setup & Foundation (Hours 0-3)
**Goal:** Everyone is running, no blockers

```
Hour 0-1: Setup
  [ ] All team members clone repo and run server successfully
  [ ] Confirm: dashboard loads, mobile app loads, demo data seeded
  [ ] Assign feature ownership — no overlapping work
  [ ] Create feature branches: feat/volunteer-app, feat/safe-timer, etc.

Hour 1-2: Architecture decisions
  [ ] Review existing code (app.py, models.py, ai_engine.py)
  [ ] Plan new DB columns needed (timer, danger zones, chat messages)
  [ ] Agree on volunteer app design (mockup reference)
  [ ] Set up ngrok for mobile testing on physical phones

Hour 2-3: Database schema additions
  [ ] Add CheckInTimer model (user_id, expires_at, is_active)
  [ ] Add DangerZone model (lat, lon, category, report_count, created_at)
  [ ] Add ChatMessage model (alert_id, sender_type, message_encrypted, timestamp)
  [ ] Run migrations (db.create_all())
```

---

### PHASE 2 — Core Features Build (Hours 3-12)
**Goal:** All P1 features working (not polished)

```
Hour 3-6: Volunteer App (Frontend Lead)
  [ ] Create server/templates/volunteer.html
  [ ] Add Flask route: GET /volunteer
  [ ] Volunteer registration: name, phone, type (police/volunteer/medical)
  [ ] Alert feed: list of active alerts sorted by distance
  [ ] Accept alert button → WebSocket event to backend
  [ ] Navigation button → OLA Maps deep link with victim coordinates
  [ ] Status update: En Route / Arrived / Resolved
  [ ] Connect to Socket.IO for real-time alert updates

Hour 3-6: Safe Check-In Timer (Backend Lead)
  [ ] POST /api/checkin-timer endpoint
  [ ] POST /api/checkin (reset timer)
  [ ] Background task: check expired timers every 30 seconds
  [ ] Auto-trigger SOS with trigger_method="timer_expired"
  [ ] Frontend: timer UI on mobile app home screen
  [ ] Push notification warning at T-1 minute

Hour 6-9: Danger Zones (AI/Data + Backend Lead)
  [ ] POST /api/danger-zones (report a zone, require lat/lon/category)
  [ ] GET /api/danger-zones (return all active zones as GeoJSON)
  [ ] Dashboard: heatmap overlay using Leaflet.heat plugin
  [ ] Mobile: "Report Danger Zone" button in menu
  [ ] AI engine: check if alert location is inside a danger zone, add risk factor
  [ ] Auto-expire zones > 30 days old

Hour 9-12: Two-Way Chat (Backend Lead)
  [ ] ChatMessage model with encryption
  [ ] WebSocket: send_chat_message event (user → responder)
  [ ] WebSocket: receive_chat_message event (broadcast to alert room)
  [ ] Mobile: simple chat UI shown when alert is active
  [ ] Volunteer app: chat panel on active alert screen
  [ ] Pre-built quick replies: ["I'm safe now", "Still in danger", "Hurry please"]
```

---

### PHASE 3 — Polish & Extra Features (Hours 12-18)
**Goal:** Make it look and feel real

```
Hour 12-14: Audio Evidence (Frontend Lead)
  [ ] Mobile: MediaRecorder API for silent audio capture
  [ ] Start recording 3 seconds after SOS trigger
  [ ] Store as encrypted blob (client-side for demo)
  [ ] Show "Upload evidence" button when alert resolves
  [ ] Backend: POST /api/evidence endpoint to receive file

Hour 14-16: Dashboard Enhancements (Frontend Lead)
  [ ] Add danger zone heatmap layer toggle
  [ ] Add volunteer status panel (separate from police/medical)
  [ ] Show chat messages in alert detail view
  [ ] Add AI confidence meter as visual progress bar
  [ ] Improve stats panel: add avg response time chart

Hour 16-17: Disguise Mode (Frontend Lead)
  [ ] Settings page on mobile app
  [ ] Toggle: "Enable Disguise Mode"
  [ ] Disguise as "Weather App" with realistic UI
  [ ] Hidden trigger: triple-tap top of screen
  [ ] Alert triggers silently

Hour 17-18: Multi-language Basics (Full Team)
  [ ] i18n JSON file: en.json, hi.json (Hindi)
  [ ] Language toggle on mobile home screen
  [ ] Translate all button labels, error messages, notifications
  [ ] Hindi voice trigger word: "bachao"
```

---

### PHASE 4 — Demo Prep & Bug Fix (Hours 18-22)
**Goal:** Flawless 5-minute demo

```
Hour 18-20: Integration testing
  [ ] Full end-to-end flow: register → SOS → dispatch → volunteer accepts →
      navigates → chat → resolves
  [ ] Test safe timer: set 1-min timer, don't check in, verify auto-SOS
  [ ] Test danger zone: report zone, verify heatmap appears, verify AI scoring
  [ ] Test on physical phone (not just desktop browser)
  [ ] Test with 2 browser tabs (simulate victim + volunteer simultaneously)

Hour 20-21: Bug fixes
  [ ] Fix any critical failures from testing
  [ ] Ensure demo data resets cleanly (add /api/reset-demo endpoint)
  [ ] Test ngrok tunnel for mobile access

Hour 21-22: Performance & UX polish
  [ ] Increase SOS button size on mobile (min 120x120px)
  [ ] Ensure < 3-second SOS trigger on slow network (throttle Chrome to 3G)
  [ ] Add loading states everywhere
  [ ] Test sound alerts in dashboard
  [ ] Verify map centers correctly on demo data (Delhi)
```

---

### PHASE 5 — Presentation (Hours 22-24)
**Goal:** Win the hackathon

```
Hour 22-23: Demo script & slides
  [ ] Write 5-minute demo script (see below)
  [ ] Create 8-10 slide deck:
      1. Problem (stats, real stories)
      2. Solution overview (diagram)
      3. Live demo (or video)
      4. Technical architecture
      5. Privacy & security
      6. Impact metrics
      7. Roadmap
      8. Team
  [ ] Record backup demo video in case of live demo failure
  [ ] Prepare 2-3 judge Q&A answers

Hour 23-24: Final prep
  [ ] Full demo run-through × 2
  [ ] Print/display design mockups
  [ ] Ensure laptop is charged, ngrok is running
  [ ] Setup physical phone for demo
  [ ] REST
```

---

## Demo Script (5 Minutes)

### Opening (30 sec)
> "4 lakh crimes against women happen in India every year. When a woman is in danger, every second counts. But safety apps today just send a WhatsApp to mom. NaariRakshak is different — it dispatches real help, in real time."

### Demo Flow (3.5 min)

**Act 1 — The Incident (45 sec)**
- Open user mobile app on phone
- Show the safe check-in timer: "Priya set a 15-minute timer before getting in an auto"
- Skip ahead: "The timer expired. She didn't check in."
- Watch auto-SOS trigger on dashboard — alert appears on map, AI says "High threat"

**Act 2 — Command Center Response (45 sec)**
- Switch to dashboard on laptop
- Show live alert on Delhi map
- Point out AI threat level bar, nearby responders
- Click dispatch → nearest volunteer assigned
- Show stats update (response time counter starts)

**Act 3 — Volunteer Responds (45 sec)**
- Open volunteer app on second phone/tab
- Volunteer sees alert with distance: "2.3 km away — HIGH threat"
- Tap "Accept" — status changes to En Route in dashboard
- Tap "Navigate" — OLA Maps opens with victim coordinates
- Chat: volunteer sends "I'm on my way, please stay where you are"

**Act 4 — Resolution + Evidence (45 sec)**
- Back on user app: show chat message from volunteer
- Show "I'm Safe" quick reply sent
- Open evidence section: 2-minute audio recording captured silently
- Volunteer marks "Resolved" — alert closes on dashboard

**Act 5 — Danger Zones (30 sec)**
- Show heatmap overlay: "Community has reported 3 danger zones nearby"
- Point: "Our AI used this to increase the threat score by 15%"

### Closing (1 min)
> "In this demo, a woman got help in under 45 seconds. The national average is 12-30 minutes. NaariRakshak works offline via our mesh network, encrypts everything with AES-256, and never stores PII. We're ready to pilot with NGOs in Delhi, and we've already got interest from [mention any]. Thank you."

---

## Tech Debt & Known Issues (Don't fix during sprint unless breaking)

- SQLite is single-write; fine for demo, replace with PostgreSQL for scale
- Mesh network is currently a simulator; real LoRaWAN integration is post-hackathon
- AI engine uses rule-based scoring; full ML model is post-hackathon
- Audio evidence is client-side only; server upload is TODO
- No push notifications for iOS (PWA limitation); React Native resolves this

---

## Emergency Contingency (If Things Break)

| Problem | Fallback |
|---------|----------|
| Location permission denied | Pre-seeded mock GPS in Delhi |
| Audio recording fails | Skip evidence demo, focus on chat |
| Volunteer app not ready | Demo volunteer features from dashboard |
| ngrok down | Run everything on localhost, show on one laptop |
| Database corrupted | Delete womensafety.db, restart (auto-reseeds) |
| Socket.IO disconnects | Hard refresh, Socket.IO auto-reconnects |

---

## Success Criteria

By demo time, judges should see:
- [ ] < 5 second SOS to alert on dashboard
- [ ] < 30 second SOS to volunteer notified
- [ ] Live map with alert, responder, and danger zone markers
- [ ] AI threat level with explanation
- [ ] One complete chat exchange between victim and responder
- [ ] Encryption mentioned (no plaintext lat/lon in network tab)

---

*Plan owner: Hackathon Team | Start: 2026-03-13 | Target: 2026-03-14*
