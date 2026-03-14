# NaariRakshak — Design System & UI Guidelines
> **Team CodeCatalysts** | HackForImpact 2026 — Track 2: Social Impact

---

## Brand Identity

| Element | Value |
|---------|-------|
| **Primary Color** | `#E53935` — Safety Red (urgency, action) |
| **Secondary Color** | `#7B1FA2` — Deep Purple (trust, tech) |
| **Accent Color** | `#FF6F00` — Amber (warnings, medium risk) |
| **Success** | `#2E7D32` — Forest Green (safe, resolved) |
| **Background** | `#0A0A1A` — Near Black (dashboard), `#FAFAFA` (mobile) |
| **Font** | Poppins (headings), Inter (body) |

### Threat Level Colors
| Level | Color | Hex |
|-------|-------|-----|
| Critical | Red pulse animation | `#D32F2F` |
| High | Solid red | `#E53935` |
| Moderate | Orange | `#FF6F00` |
| Low | Yellow | `#FDD835` |

---

## Platform-Specific Design

NaariRakshak consists of **4 platforms**, each with distinct design goals:

| # | Platform | Route | Template |
|---|----------|-------|----------|
| 1 | User Mobile App | `/app` | `mobile.html` |
| 2 | Command Center Dashboard | `/dashboard` | `dashboard.html` |
| 3 | Volunteer/Responder App | `/volunteer` | `volunteer.html` |
| 4 | CCTV AI Monitoring | `/cctv` | `cctv.html` |

### 1. User Mobile App (Route: `/app`)

**Design Principles:**
- **Panic-proof:** In an emergency, users have reduced fine motor control
- **Minimum 80x80px tap targets** (WCAG 2.1 AA minimum is 44x44, we go larger)
- **SOS button: 160x160px minimum**, always visible, always centered
- **High contrast:** 7:1 contrast ratio minimum (AAA)
- **One-thumb reachable:** All critical actions in bottom half of screen

**Screen Flow (Route: `/app`):**
```
Splash → Language Select → Onboarding (name + phone) → Home
                                                          ↓
                                                    [SOS BUTTON]
                                                    Timer Status
                                                    Quick Actions
                                                          ↓
                                                    Alert Active
                                                    Live Location
                                                    Chat Window
                                                    Evidence Capture
```

**Key Screens:**

#### Home Screen
```
┌─────────────────────────┐
│ 🔴 NaariRakshak    ⚙️  │
│ Hi, Priya               │
│ You are safe            │
│                         │
│  ┌──────────────────┐   │
│  │                  │   │
│  │   ⚠️  SOS       │   │
│  │                  │   │
│  │  PRESS & HOLD    │   │
│  │   FOR HELP       │   │
│  │                  │   │
│  └──────────────────┘   │
│                         │
│  ⏱️ Check-in Timer OFF  │
│  [Set Timer]            │
│                         │
│  [📍 Share Location]    │
│  [⚠️ Report Zone]      │
│  [📋 My Alerts]         │
└─────────────────────────┘
```

#### Active Alert Screen
```
┌─────────────────────────┐
│ 🔴 ALERT ACTIVE         │
│ Help is on the way      │
│                         │
│  ┌──────────────────┐   │
│  │   MAP VIEW       │   │
│  │   You 📍         │   │
│  │        → 🚗 Ravi │   │
│  │   ETA: 4 min     │   │
│  └──────────────────┘   │
│                         │
│  RESPONDER: Ravi Kumar  │
│  ● En Route (2.1 km)    │
│                         │
│  ┌──────────────────┐   │
│  │ 💬 I'm coming,   │   │
│  │ stay where you   │   │
│  │ are — Ravi       │   │
│  └──────────────────┘   │
│                         │
│  [Still in danger] [OK] │
│                         │
│  [Cancel Alert]         │
└─────────────────────────┘
```

---

### 2. Command Center Dashboard (Route: `/dashboard`)

**Design Principles:**
- **Information density:** Operators need as much data as possible at a glance
- **Dark mode default:** Reduces eye strain in 24/7 operations
- **Map-first:** 70% of screen is the map, sidebar for management
- **Color-coded immediately:** Threat levels visible without reading text
- **Sound + visual:** Multiple notification channels for critical alerts

**Layout:**
```
┌────────────────────────────────────────────────────────────────────┐
│ 🔴 NaariRakshak Command Center    [Active: 3] [Responders: 22/25] │
├──────────────┬─────────────────────────────────────┬───────────────┤
│  ALERTS      │                                     │  RESPONDERS   │
│  ─────────   │         LIVE MAP                    │  ──────────── │
│  🔴 #1032    │   [Leaflet.js + OpenStreetMap]      │  🟢 Ravi K.   │
│  Lajpat Nagar│                                     │  Police • 1km │
│  CRITICAL    │   📍 SOS Markers                    │               │
│  2 min ago   │   👮 Police Markers                 │  🟢 Sunita M. │
│  [Ack] [Dis] │   🙋 Volunteer Markers              │  NGO • 2.3km  │
│  ──────────  │   🔥 Danger Zone Heatmap            │               │
│  🟠 #1031    │   [Layers toggle]                   │  🟡 Dr. Arora │
│  Saket       │                                     │  Medical • 4km│
│  HIGH        │                                     │               │
│  5 min ago   │                                     │  [+ Add]      │
│  [Dispatch]  │                                     │               │
│  ──────────  │                                     │  STATS        │
│  🟡 #1030    │                                     │  ──────────── │
│  Dwarka      │                                     │  Avg: 4m 32s  │
│  MODERATE    │                                     │  Today: 12    │
│  Resolved    │                                     │  Month: 287   │
└──────────────┴─────────────────────────────────────┴───────────────┘
│  AI Insight: High-risk time window (11 PM - 2 AM) — 3 clusters     │
└────────────────────────────────────────────────────────────────────┘
```

**Color Scheme:** Dark background `#0A0A1A`, card backgrounds `#12122A`, accent `#E53935`

---

### 3. Volunteer App (Route: `/volunteer`)

**Design Principles:**
- **Action-first:** Volunteers need to accept/decline fast
- **Navigation-ready:** Big "Navigate" button always visible on active alert
- **Field-friendly:** Works in bright sunlight (high contrast), one-handed
- **Offline-tolerant:** Show last known data gracefully when offline

**Screen Flow:**
```
Login (phone + OTP) → Shift Check-In → Alert Feed
                                            ↓
                                     Alert Detail
                                     Accept / Decline
                                            ↓
                                     Active Navigation
                                     [En Route] → [Arrived] → [Resolved]
                                     Chat Panel
```

**Alert Card (Feed Item):**
```
┌─────────────────────────────────────────┐
│ 🔴 CRITICAL     2.3 km away   2 min ago │
│ ─────────────────────────────────────── │
│ Lajpat Nagar, New Delhi                 │
│ SOS triggered via shake detection       │
│                                         │
│ AI Confidence: ████████░░ 82%           │
│                                         │
│ [ACCEPT]              [SKIP]            │
└─────────────────────────────────────────┘
```

**Active Alert Screen:**
```
┌─────────────────────────────────────────┐
│ 🔴 ALERT #1032 — EN ROUTE               │
│                                         │
│  Distance remaining: 1.8 km             │
│  ████████░░░░░░ (ETA: 4 min)            │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  📍 Victim Location             │    │
│  │  Lajpat Nagar, Near Metro Gate  │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │  🗺️  NAVIGATE NOW                │   │
│  │  (Opens OLA / Google Maps)       │   │
│  └──────────────────────────────────┘   │
│                                         │
│  STATUS:                                │
│  [En Route ✓]  [Arrived]  [Resolved]    │
│                                         │
│  💬 CHAT                                │
│  ─────────────────────────────────      │
│  Victim: "Please hurry"                 │
│  You: "I'm 2 min away"                  │
│  ─────────────────────────────────      │
│  [I'm nearby] [Be calm] [Type...]       │
└─────────────────────────────────────────┘
```

---

### 4. CCTV AI Monitoring Dashboard (Route: `/cctv`)

**Design Principles:**
- **Dark theme default:** Consistent with command center; reduces eye strain during continuous monitoring
- **Video-first:** Primary focus is the live camera feed — large, centered, high-resolution
- **Status at a glance:** Detection state (Safe / Warning / Violence) communicated via color-coded indicators
- **Non-intrusive logging:** Event log scrolls automatically but does not obstruct the video feed
- **Evidence-ready:** Recording controls always accessible for manual capture

**Color Scheme:**
| Element | Color | Hex |
|---------|-------|-----|
| Background | Near Black | `#0a0a0a` |
| Card/Panel | Dark Gray | `#1a1a2e` |
| Safe status | Green | `#00ff88` |
| Warning status | Amber/Orange | `#ff6f00` |
| Violence detected | Red (pulsing) | `#ff0000` |
| Text primary | White | `#ffffff` |
| Text secondary | Muted gray | `#888888` |

**Layout:**
```
┌──────────────────────────────────────────────────────────────────────┐
│  CCTV AI Monitoring — NaariRakshak              [REC ●] [Settings]  │
├──────────────────────────────────────────┬───────────────────────────┤
│                                          │  DETECTION STATUS         │
│                                          │  ────────────────         │
│          LIVE VIDEO FEED                 │  ● SAFE                   │
│          (Webcam / CCTV Stream)          │  Confidence: 92%          │
│                                          │                           │
│          ┌────────────────────┐          │  PIPELINE                 │
│          │   AI Analysis      │          │  ────────────────         │
│          │   Overlay          │          │  YOLOv8: 2 persons        │
│          │   (bounding boxes, │          │  Motion: Low (0.12)       │
│          │    detection info) │          │  CLIP: Safe scene         │
│          └────────────────────┘          │                           │
│                                          │  ──────────────────       │
│  [▶ Start Camera] [⏹ Stop] [● Record]   │  CONTROLS                 │
│                                          │  Analysis: Every 3s       │
├──────────────────────────────────────────┤  Threshold: 0.60          │
│  EVENT LOG                               │                           │
│  ──────────────────────                  │                           │
│  14:32:07 — SAFE (0.92)                  │  EVIDENCE                 │
│  14:32:10 — SAFE (0.88)                  │  ────────────────         │
│  14:32:13 — WARNING (0.61)               │  evidence_a7ce.webm       │
│  14:32:16 — VIOLENCE (0.78) ⚠️           │  evidence_7d69.webm       │
│  14:32:19 — SAFE (0.85)                  │  [View All Evidence]      │
│                                          │                           │
└──────────────────────────────────────────┴───────────────────────────┘
```

**Screen Flow:**
```
Load /cctv → Camera Permission → Live Feed Active
                                       ↓
                              AI Pipeline Running
                              (YOLOv8 → Optical Flow → CLIP)
                                       ↓
                              Detection Results
                              ├─ Safe → Green indicator, log entry
                              ├─ Warning → Amber indicator, log entry
                              └─ Violence → Red pulse, log entry, auto-record
```

**Key UI Elements:**
- **Video feed area:** 640x480 minimum, scales to available width, dark border (`#333`)
- **Detection status badge:** Large pill-shaped indicator, color changes with state, includes confidence percentage
- **Event log:** Scrollable panel, newest entries at top, timestamps in `HH:MM:SS` format, color-coded by severity
- **Recording indicator:** Red dot with "REC" label, pulses when active
- **Pipeline details:** Show each stage (YOLO person count, optical flow intensity, CLIP classification) for transparency

---

## Component Library

### Buttons
```css
/* Primary SOS Button */
.btn-sos {
  width: 160px;
  height: 160px;
  border-radius: 50%;
  background: radial-gradient(#E53935, #B71C1C);
  box-shadow: 0 0 0 0 rgba(229, 57, 53, 0.7);
  animation: pulse 1.5s infinite;
  font-size: 24px;
  font-weight: 700;
  color: white;
}

/* Pulse animation for SOS */
@keyframes pulse {
  0%   { box-shadow: 0 0 0 0 rgba(229, 57, 53, 0.7); }
  70%  { box-shadow: 0 0 0 20px rgba(229, 57, 53, 0); }
  100% { box-shadow: 0 0 0 0 rgba(229, 57, 53, 0); }
}

/* Threat level badges */
.badge-critical { background: #D32F2F; animation: pulse 1s infinite; }
.badge-high     { background: #E53935; }
.badge-moderate { background: #FF6F00; }
.badge-low      { background: #FDD835; color: #333; }
```

### Cards
- Border radius: 12px
- Padding: 16px
- Shadow: `0 4px 24px rgba(0,0,0,0.3)` (dashboard dark), `0 2px 12px rgba(0,0,0,0.08)` (mobile light)

### Typography Scale
| Use | Size | Weight |
|-----|------|--------|
| Hero (SOS) | 28px | 700 |
| Section heading | 20px | 600 |
| Card title | 16px | 600 |
| Body | 14px | 400 |
| Caption | 12px | 400 |
| Micro | 11px | 400 |

---

## Accessibility Checklist

- [ ] All interactive elements keyboard accessible
- [ ] ARIA labels on icon-only buttons
- [ ] Focus visible (outline: 3px solid #E53935)
- [ ] Color never used as sole differentiator (always + icon or text)
- [ ] Minimum touch target: 80x80px (mobile), 44x44px (dashboard)
- [ ] Screen reader tested: SOS button announces "Emergency SOS button, press to call for help"
- [ ] Reduced motion mode: disable pulse animations if prefers-reduced-motion

---

## Responsive Breakpoints

| Breakpoint | Width | Target |
|-----------|-------|--------|
| Mobile S | 320px | Older Android phones |
| Mobile M | 375px | iPhone SE |
| Mobile L | 414px | Most modern phones |
| Tablet | 768px | iPad, large tablets |
| Desktop | 1024px+ | Command dashboard |

---

*Design system maintained by: Team CodeCatalysts — NaariRakshak | HackForImpact 2026*
