"""
Gemini AI Integration for NaariRakshak
- Threat assessment with real AI reasoning
- AI chat assistant for SOS situations
- Incident summary generation
- Reverse geocoding
"""
import os
import json
import requests
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Init — using new google-genai SDK
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
MAPS_API_KEY = os.environ.get('MAPS_API_KEY', '')

_client = None

def _get_client():
    global _client
    if _client is None and GEMINI_API_KEY:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client

def _generate(prompt: str) -> str:
    """Call Gemini and return text response. Returns None on failure."""
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        return response.text.strip() if response.text else None
    except Exception as e:
        print(f"[GeminiAI] API call failed: {e}")
        return None


# ---------------------------------------------------------------------------
# 1. AI Threat Assessment
# ---------------------------------------------------------------------------
def assess_threat_with_ai(alert_data: dict, danger_zones: list = None) -> dict:
    """
    Use Gemini to analyse an SOS and return structured threat assessment.
    Falls back to None if the API call fails (caller should use rule-based).
    """
    now = datetime.now(timezone.utc)
    hour = now.hour
    time_desc = (
        "late night (high risk)" if 0 <= hour < 6 else
        "early morning" if 6 <= hour < 9 else
        "daytime" if 9 <= hour < 17 else
        "evening" if 17 <= hour < 21 else
        "night (elevated risk)"
    )

    dz_text = "None nearby."
    if danger_zones:
        dz_text = "; ".join(
            f"{z.get('category','unknown')} zone ({z.get('report_count',0)} reports)"
            for z in danger_zones[:5]
        )

    prompt = f"""You are NaariRakshak, an AI women's safety threat-assessment engine deployed in Delhi-NCR, India.

CONTEXT:
- Time: {now.strftime('%Y-%m-%d %H:%M')} IST ({time_desc})
- Location: lat {alert_data.get('latitude')}, lon {alert_data.get('longitude')}
- Location name: {alert_data.get('location_name', 'Unknown')}
- Trigger method: {alert_data.get('trigger_method', 'button')}
- User prior alerts: {alert_data.get('prior_alerts', 0)}
- Nearby danger zones: {dz_text}
- Additional context: {alert_data.get('trigger_context', 'None')}

TASK: Assess the threat level for this SOS alert.

Respond ONLY with valid JSON (no markdown, no backticks):
{{
  "threat_level": "critical" | "high" | "moderate" | "low",
  "confidence": 0.0-1.0,
  "risk_score": 0.0-1.0,
  "reasoning": "1-2 sentence explanation",
  "risk_factors": {{
    "time_risk": 0.0-1.0,
    "location_risk": 0.0-1.0,
    "trigger_risk": 0.0-1.0,
    "pattern_risk": 0.0-1.0
  }},
  "recommended_actions": ["action1", "action2"],
  "auto_escalate_112": true/false
}}"""

    try:
        text = _generate(prompt)
        if not text:
            return None
        # Strip markdown fences if present
        if text.startswith('```'):
            text = text.split('\n', 1)[1]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)
    except Exception as e:
        print(f"[GeminiAI] Threat assessment failed: {e}")
        return None


# ---------------------------------------------------------------------------
# 2. AI Chat Assistant (auto-engages after SOS)
# ---------------------------------------------------------------------------
def get_safety_questions(alert_context: dict) -> list:
    """Generate contextual safety questions to ask the user after SOS."""
    prompt = f"""You are NaariRakshak safety assistant. A woman just triggered an SOS alert.

Context:
- Trigger: {alert_context.get('trigger_method', 'button')}
- Threat level: {alert_context.get('threat_level', 'unknown')}
- Location: {alert_context.get('location_name', 'Unknown area')}
- Time: {datetime.now(timezone.utc).strftime('%H:%M')} IST

Generate 3 short, empathetic safety questions to understand her situation.
Keep each under 15 words. Be calm, not alarming.

Respond ONLY with JSON array (no markdown):
["question1", "question2", "question3"]"""

    try:
        text = _generate(prompt)
        if not text:
            return _fallback_safety_questions()
        if text.startswith('```'):
            text = text.split('\n', 1)[1]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)
    except Exception as e:
        print(f"[GeminiAI] Safety questions failed: {e}")
        return _fallback_safety_questions()


def _fallback_safety_questions():
    return [
        "Are you safe to communicate right now?",
        "Can you describe what's happening around you?",
        "Is anyone nearby who can help you?"
    ]


def analyse_chat_for_escalation(messages: list, current_threat: str) -> dict:
    """Analyse chat messages to determine if threat should be escalated."""
    chat_text = "\n".join(
        f"[{m.get('sender_type','?')}] {m.get('message','')}"
        for m in messages[-10:]
    )

    prompt = f"""You are NaariRakshak AI safety engine. Analyse this emergency chat conversation.

Current threat level: {current_threat}
Chat transcript:
{chat_text}

Based on the conversation, should the threat level be changed?
Look for keywords indicating: physical danger, following/stalking, assault, distress, or false alarm.

Respond ONLY with JSON (no markdown):
{{
  "escalate": true/false,
  "new_threat_level": "critical"/"high"/"moderate"/"low" or null if no change,
  "reasoning": "1 sentence",
  "distress_indicators": ["indicator1", "indicator2"]
}}"""

    try:
        text = _generate(prompt)
        if not text:
            return None
        if text.startswith('```'):
            text = text.split('\n', 1)[1]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)
    except Exception as e:
        print(f"[GeminiAI] Chat escalation analysis failed: {e}")
        return None


# ---------------------------------------------------------------------------
# 3. Incident Summary
# ---------------------------------------------------------------------------
def generate_incident_summary(alert: dict, chat_messages: list = None) -> str:
    """Generate a human-readable incident summary for the dashboard."""
    chat_text = ""
    if chat_messages:
        chat_text = "Chat transcript:\n" + "\n".join(
            f"  [{m.get('sender_type','?')}] {m.get('message','')}"
            for m in chat_messages[-15:]
        )

    prompt = f"""Generate a brief incident summary for a women's safety command center dashboard.

Alert details:
- ID: {alert.get('alert_id', 'N/A')[:8]}
- Status: {alert.get('status', 'unknown')}
- Threat level: {alert.get('threat_level', 'unknown')}
- Trigger: {alert.get('trigger_method', 'unknown')}
- Location: {alert.get('location_name', f"lat {alert.get('latitude')}, lon {alert.get('longitude')}")}
- Time: {alert.get('triggered_at', 'unknown')}
- AI confidence: {alert.get('ai_confidence', 'N/A')}
- Responder assigned: {'Yes' if alert.get('assigned_responders') else 'No'}
{chat_text}

Write a 2-3 sentence professional incident summary. Include key facts and status.
Respond with plain text only (no JSON, no markdown)."""

    try:
        text = _generate(prompt)
        if text:
            return text
        return _fallback_summary(alert)
    except Exception as e:
        print(f"[GeminiAI] Incident summary failed: {e}")
        return _fallback_summary(alert)


def _fallback_summary(alert: dict) -> str:
    return (
        f"SOS alert triggered via {alert.get('trigger_method', 'unknown')} at "
        f"{alert.get('triggered_at', 'unknown time')}. "
        f"Threat level: {alert.get('threat_level', 'unknown').upper()}. "
        f"Status: {alert.get('status', 'unknown')}."
    )


# ---------------------------------------------------------------------------
# 4. Reverse Geocoding (Nominatim — free, no key)
# ---------------------------------------------------------------------------
def reverse_geocode(lat: float, lon: float) -> str:
    """Convert lat/lon to a readable address using Nominatim (free)."""
    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'lat': lat, 'lon': lon, 'format': 'json', 'zoom': 16},
            headers={'User-Agent': 'NaariRakshak-SafetyApp/1.0'},
            timeout=3
        )
        if resp.status_code == 200:
            data = resp.json()
            addr = data.get('address', {})
            # Build a short readable name
            parts = []
            for key in ['road', 'neighbourhood', 'suburb', 'city_district']:
                if key in addr:
                    parts.append(addr[key])
                    if len(parts) >= 2:
                        break
            city = addr.get('city') or addr.get('state_district') or addr.get('state', '')
            if parts:
                return f"{', '.join(parts)}, {city}" if city else ', '.join(parts)
            return data.get('display_name', '').split(',')[0]
    except Exception as e:
        print(f"[Geocode] Reverse geocoding failed: {e}")
    return None


def reverse_geocode_google(lat: float, lon: float) -> str:
    """Reverse geocode using Google Maps API (more reliable, needs key)."""
    if not MAPS_API_KEY:
        return None
    try:
        resp = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={'latlng': f'{lat},{lon}', 'key': MAPS_API_KEY, 'result_type': 'street_address|route|neighborhood'},
            timeout=3
        )
        if resp.status_code == 200:
            results = resp.json().get('results', [])
            if results:
                return results[0].get('formatted_address', '')
    except Exception as e:
        print(f"[Geocode] Google reverse geocoding failed: {e}")
    return None


def get_location_name(lat: float, lon: float) -> str:
    """Try Google Maps first, fall back to Nominatim."""
    name = reverse_geocode_google(lat, lon)
    if not name:
        name = reverse_geocode(lat, lon)
    return name or f"{lat:.4f}°N, {lon:.4f}°E"
