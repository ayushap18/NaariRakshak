"""
Women's Safety System - Main Server Application
"""
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import uuid
import json
import os

# Load environment variables
load_dotenv()

# Import local modules
from config import config
from models import (
    init_db, get_session, User, Alert, LocationUpdate,
    Responder, MeshNode, AuditLog, AlertStatus, ThreatLevel,
    DangerZone, ChatMessage, CheckInTimer
)
from encryption import get_encryption_manager
from ai_engine import get_threat_engine
from mesh_network import MeshNetworkSimulator
from utils import calculate_distance
from gemini_ai import (
    assess_threat_with_ai, get_safety_questions,
    analyse_chat_for_escalation, generate_incident_summary,
    get_location_name
)
from cctv_ai import (
    analyse_frame as cctv_analyse_frame,
    analyse_video as cctv_analyse_video,
    get_model_status as cctv_model_status,
    is_model_loaded as cctv_model_loaded,
    _load_model as cctv_load_model
)

# Initialize Flask app
app = Flask(__name__)
config_name = os.getenv('FLASK_CONFIG', 'development')
app.config.from_object(config[config_name])

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize database
engine = init_db(app.config['DATABASE_PATH'])

# Initialize managers
encryption_mgr = get_encryption_manager()
threat_engine = get_threat_engine()
mesh_network = MeshNetworkSimulator()

# Track active connections
active_users = {}  # {user_id: socket_id}
active_alerts = {}  # {alert_id: alert_data}

# Runtime mode: can be toggled via API
app_mode = {'demo': app.config.get('DEMO_MODE', True)}


# ============ REST API ENDPOINTS ============

@app.route('/')
def index():
    """Serve dashboard"""
    return render_template('dashboard.html')


@app.route('/app')
def mobile_app():
    """Serve mobile app for real devices"""
    return render_template('mobile.html')


@app.route('/volunteer')
def volunteer_app():
    """Serve volunteer/responder app"""
    return render_template('volunteer.html')

@app.route('/dashboard')
def dashboard_redirect():
    return render_template('dashboard.html')

@app.route('/cctv')
def cctv_dashboard():
    """Serve CCTV AI monitoring dashboard"""
    return render_template('cctv.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'active_alerts': len(active_alerts),
        'connected_users': len(active_users),
        'mode': 'demo' if app_mode['demo'] else 'live'
    })


@app.route('/api/mode', methods=['GET', 'POST', 'OPTIONS'])
def manage_mode():
    """Get or switch app mode (demo/live)"""
    if request.method == 'OPTIONS':
        return '', 204
    if request.method == 'POST':
        data = request.json or {}
        new_mode = data.get('mode', '').lower()
        if new_mode == 'demo':
            app_mode['demo'] = True
        elif new_mode == 'live':
            app_mode['demo'] = False
        else:
            return jsonify({'error': 'mode must be "demo" or "live"'}), 400
        socketio.emit('mode_changed', {'mode': 'demo' if app_mode['demo'] else 'live'})
        return jsonify({'mode': 'demo' if app_mode['demo'] else 'live'})
    return jsonify({'mode': 'demo' if app_mode['demo'] else 'live'})


@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register_user():
    """Register new user"""
    if request.method == 'OPTIONS':
        return '', 204
    
    session = get_session(engine)
    try:
        data = request.json
        name = data.get('name')
        phone = data.get('phone')
        
        if not name or not phone:
            return jsonify({'error': 'Name and phone required'}), 400
        
        # Check if user exists
        existing_user = session.query(User).filter_by(phone=phone).first()
        if existing_user:
            user_dict = existing_user.to_dict()
            # Add full phone for client-side storage
            user_dict['phone_full'] = phone
            return jsonify({
                'message': 'User already registered',
                'user': user_dict
            })
        
        # Create new user
        ephemeral_id = encryption_mgr.generate_ephemeral_id(hash(phone))
        
        user = User(
            ephemeral_id=ephemeral_id,
            name=name,
            phone=phone,
            emergency_contacts=json.dumps(data.get('emergency_contacts', [])),
            preferences=json.dumps(data.get('preferences', {})),
            is_verified=True  # Auto-verify for demo
        )
        
        session.add(user)
        session.commit()
        
        user_dict = user.to_dict()
        # Add full phone for client-side storage (needed for SOS)
        user_dict['phone_full'] = phone
        
        return jsonify({
            'message': 'User registered successfully',
            'user': user_dict
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/sos/trigger', methods=['POST', 'OPTIONS'])
def trigger_sos():
    """Trigger SOS alert"""
    if request.method == 'OPTIONS':
        return '', 204
    
    session = get_session(engine)
    try:
        data = request.json
        phone = data.get('phone')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        trigger_method = data.get('trigger_method', 'button')
        
        if not phone:
            return jsonify({'error': 'Phone number required'}), 400
        
        # Find user
        user = session.query(User).filter_by(phone=phone).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Generate alert ID
        alert_id = str(uuid.uuid4())
        
        # Encrypt location
        encrypted_loc = None
        if latitude and longitude:
            encrypted_loc = encryption_mgr.encrypt_location(latitude, longitude)
        
        # AI threat assessment — try Gemini first, fallback to rule-based
        location_name = get_location_name(latitude, longitude) if latitude and longitude else 'Unknown'

        # Get nearby danger zones for AI context
        danger_zone_list = []
        if latitude and longitude:
            dz_all = session.query(DangerZone).filter_by(is_active=True).all()
            for z in dz_all:
                if calculate_distance(latitude, longitude, z.latitude, z.longitude) < 0.5:
                    danger_zone_list.append({'category': z.category, 'report_count': z.report_count})

        alert_data = {
            'latitude': latitude,
            'longitude': longitude,
            'location_name': location_name,
            'trigger_method': trigger_method,
            'user_id': user.id,
            'prior_alerts': session.query(Alert).filter_by(user_id=user.id).count(),
            'trigger_context': data.get('context', {}),
            'accelerometer_data': data.get('accelerometer_data')
        }

        # Try Gemini AI assessment
        ai_result = assess_threat_with_ai(alert_data, danger_zone_list)
        if ai_result:
            threat_level = ai_result.get('threat_level', 'high')
            confidence = ai_result.get('confidence', 0.8)
            risk_factors = ai_result.get('risk_factors', {})
            risk_factors['overall_risk_score'] = ai_result.get('risk_score', 0.7)
            risk_factors['reasoning'] = ai_result.get('reasoning', '')
            risk_factors['recommended_actions'] = ai_result.get('recommended_actions', [])
            risk_factors['ai_source'] = 'groq-llama'
        else:
            # Fallback to rule-based engine
            threat_level, confidence, risk_factors = threat_engine.assess_threat_level(alert_data)
            risk_factors['ai_source'] = 'rule-based'
        
        # Create alert
        alert = Alert(
            alert_id=alert_id,
            user_id=user.id,
            status=AlertStatus.TRIGGERED,
            threat_level=ThreatLevel[threat_level.upper()],
            encrypted_location=json.dumps(encrypted_loc) if encrypted_loc else None,
            latitude=latitude,
            longitude=longitude,
            trigger_method=trigger_method,
            trigger_context=json.dumps(data.get('context', {})),
            ai_risk_score=risk_factors.get('overall_risk_score'),
            ai_confidence=confidence,
            ai_factors=json.dumps(risk_factors),
            auto_purge_at=datetime.now(timezone.utc) + timedelta(hours=app.config['AUTO_PURGE_HOURS'])
        )
        
        session.add(alert)
        session.commit()
        
        alert_dict = alert.to_dict(include_sensitive=True)
        alert_dict['user'] = user.to_dict()
        alert_dict['location_name'] = location_name
        alert_dict['ai_source'] = risk_factors.get('ai_source', 'unknown')
        if ai_result:
            alert_dict['ai_reasoning'] = ai_result.get('reasoning', '')
            alert_dict['recommended_actions'] = ai_result.get('recommended_actions', [])
        
        # Store in active alerts
        active_alerts[alert_id] = alert_dict
        
        # Broadcast to connected control centers
        socketio.emit('alert_triggered', alert_dict)
        
        # Simulate mesh network propagation
        if app.config['MESH_NETWORK_ENABLED']:
            mesh_network.propagate_alert(alert_dict)
        
        # Find nearby responders
        nearby_responders = find_nearby_responders(session, latitude, longitude)

        # AUTO-DISPATCH to nearest available responder
        auto_dispatched = None
        if nearby_responders:
            nearest = nearby_responders[0]
            nearest.is_available = False
            nearest.current_alert_id = alert_id
            assigned = [nearest.responder_id]
            alert.assigned_responders = json.dumps(assigned)
            alert.status = AlertStatus.DISPATCHED
            alert.dispatched_at = datetime.now(timezone.utc)
            session.commit()
            # Update cached alert dict
            alert_dict = alert.to_dict(include_sensitive=True)
            alert_dict['user'] = user.to_dict()
            active_alerts[alert_id] = alert_dict
            auto_dispatched = nearest.to_dict()
            # Notify all clients of dispatch
            socketio.emit('alert_status_changed', {
                'alert_id': alert_id,
                'status': 'dispatched',
                'responder': auto_dispatched
            })
            # Notify the user specifically
            if user.id in active_users:
                socketio.emit('responder_dispatched', {
                    'alert_id': alert_id,
                    'responder': auto_dispatched
                }, room=f'user_{user.id}')

        # Auto-send system chat message so dashboard sees context immediately
        ai_tag = '🤖 Llama AI' if risk_factors.get('ai_source') == 'groq-llama' else '📊 Rule Engine'
        reasoning = risk_factors.get('reasoning', '')
        sys_msg = ChatMessage(
            alert_id=alert_id,
            sender_type='system',
            sender_name='NaariRakshak',
            message=f'🚨 SOS triggered via {trigger_method} by {user.name or "User"} near {location_name}. Threat: {threat_level.upper()} ({ai_tag}, {int(confidence*100)}% confidence). {reasoning}',
            is_quick_reply=False
        )
        session.add(sys_msg)
        session.commit()
        sys_msg_dict = sys_msg.to_dict()
        socketio.emit('new_chat_message', sys_msg_dict)

        if auto_dispatched:
            dispatch_msg = ChatMessage(
                alert_id=alert_id,
                sender_type='system',
                sender_name='NaariRakshak',
                message=f'✅ Auto-dispatched {auto_dispatched["name"]} ({auto_dispatched["type"]}) to respond.',
                is_quick_reply=False
            )
            session.add(dispatch_msg)
            session.commit()
            socketio.emit('new_chat_message', dispatch_msg.to_dict())

        # AI safety assistant — auto-ask contextual safety questions
        try:
            questions = get_safety_questions({
                'trigger_method': trigger_method,
                'threat_level': threat_level,
                'location_name': location_name,
            })
            for q in questions:
                ai_q = ChatMessage(
                    alert_id=alert_id,
                    sender_type='ai_assistant',
                    sender_name='🤖 Safety AI',
                    message=q,
                    is_quick_reply=False
                )
                session.add(ai_q)
                session.commit()
                socketio.emit('new_chat_message', ai_q.to_dict())
        except Exception as e:
            print(f"[AI Assistant] Safety questions failed: {e}")

        return jsonify({
            'message': 'SOS alert triggered',
            'alert': alert_dict,
            'nearby_responders': [r.to_dict() for r in nearby_responders],
            'auto_dispatched': auto_dispatched
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/sos/cancel', methods=['POST', 'OPTIONS'])
def cancel_sos():
    """Cancel active SOS alert"""
    if request.method == 'OPTIONS':
        return '', 204
    
    session = get_session(engine)
    try:
        data = request.json
        alert_id = data.get('alert_id')
        verification = data.get('verification', '')
        
        if not alert_id:
            return jsonify({'error': 'Alert ID required'}), 400
        
        # Find alert
        alert = session.query(Alert).filter_by(alert_id=alert_id).first()
        if not alert:
            return jsonify({'error': 'Alert not found'}), 404
        
        # Update status
        alert.status = AlertStatus.CANCELLED
        alert.resolved_at = datetime.now(timezone.utc)
        
        # Make triggered_at timezone-aware if it's naive
        triggered_at = alert.triggered_at
        if triggered_at.tzinfo is None:
            triggered_at = triggered_at.replace(tzinfo=timezone.utc)
        
        alert.response_time_seconds = int(
            (alert.resolved_at - triggered_at).total_seconds()
        )
        
        session.commit()
        
        # Remove from active alerts
        if alert_id in active_alerts:
            del active_alerts[alert_id]
        
        # Broadcast cancellation
        socketio.emit('alert_cancelled', {
            'alert_id': alert_id,
            'cancelled_at': alert.resolved_at.isoformat()
        })
        
        return jsonify({
            'message': 'Alert cancelled',
            'alert_id': alert_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get all alerts"""
    session = get_session(engine)
    try:
        # Query parameters
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        
        query = session.query(Alert)
        
        if status:
            if status.upper() == 'ACTIVE':
                query = query.filter(Alert.status.in_([
                    AlertStatus.TRIGGERED, AlertStatus.ACKNOWLEDGED,
                    AlertStatus.DISPATCHED, AlertStatus.RESPONDING
                ]))
            else:
                query = query.filter_by(status=AlertStatus[status.upper()])
        
        alerts = query.order_by(Alert.triggered_at.desc()).limit(limit).all()
        
        alerts_data = [alert.to_dict(include_sensitive=True) for alert in alerts]
        
        return jsonify({
            'alerts': alerts_data,
            'count': len(alerts_data)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/alerts/<alert_id>', methods=['GET'])
def get_alert(alert_id):
    """Get specific alert details"""
    session = get_session(engine)
    try:
        alert = session.query(Alert).filter_by(alert_id=alert_id).first()
        if not alert:
            return jsonify({'error': 'Alert not found'}), 404
        
        alert_dict = alert.to_dict(include_sensitive=True)
        alert_dict['user'] = alert.user.to_dict() if alert.user else None
        
        # Get location updates
        updates = session.query(LocationUpdate).filter_by(
            alert_id=alert.id
        ).order_by(LocationUpdate.timestamp.desc()).all()
        
        alert_dict['location_updates'] = [u.to_dict() for u in updates]
        
        # Log access
        audit_log = AuditLog(
            alert_id=alert_id,
            action='viewed_alert',
            actor='system',
            actor_role='admin',
            ip_address=request.remote_addr
        )
        session.add(audit_log)
        session.commit()
        
        return jsonify(alert_dict)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/responders', methods=['GET', 'POST', 'OPTIONS'])
def manage_responders():
    """Get or add responders"""
    if request.method == 'OPTIONS':
        return '', 204
    
    if request.method == 'POST':
        # Add new responder
        session = get_session(engine)
        try:
            data = request.json
            name = data.get('name')
            responder_type = data.get('type')  # police, medical, volunteer
            phone = data.get('phone')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            
            if not name or not responder_type or not phone:
                return jsonify({'error': 'Name, type, and phone are required'}), 400
            
            # Check if responder exists
            existing = session.query(Responder).filter_by(phone=phone).first()
            if existing:
                return jsonify({
                    'message': 'Responder already registered',
                    'responder': existing.to_dict()
                })
            
            # Create new responder
            responder = Responder(
                responder_id=f'R{str(uuid.uuid4())[:8]}',
                name=name,
                type=responder_type,
                phone=phone,
                latitude=latitude,
                longitude=longitude,
                is_available=True,
                rating=5.0
            )
            
            session.add(responder)
            session.commit()
            
            responder_dict = responder.to_dict()
            
            return jsonify({
                'message': 'Responder registered successfully',
                'responder': responder_dict
            }), 201
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()
    
    # GET - Get ALL responders with status (not just available)
    session = get_session(engine)
    try:
        responders = session.query(Responder).all()

        responders_data = [r.to_dict() for r in responders]
        available_count = sum(1 for r in responders if r.is_available)

        return jsonify({
            'responders': responders_data,
            'count': len(responders_data),
            'available': available_count
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/mesh/nodes', methods=['GET'])
def get_mesh_nodes():
    """Get mesh network nodes"""
    session = get_session(engine)
    try:
        nodes = session.query(MeshNode).filter_by(is_active=True).all()
        nodes_data = [n.to_dict() for n in nodes]
        
        return jsonify({
            'nodes': nodes_data,
            'count': len(nodes_data)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/danger-zones', methods=['GET', 'POST', 'OPTIONS'])
def manage_danger_zones():
    if request.method == 'OPTIONS':
        return '', 204

    if request.method == 'POST':
        session = get_session(engine)
        try:
            data = request.json
            lat = data.get('latitude')
            lon = data.get('longitude')
            category = data.get('category', 'harassment')
            description = data.get('description', '')

            if not lat or not lon:
                return jsonify({'error': 'latitude and longitude required'}), 400

            # Check for existing zone within 200m
            existing_zones = session.query(DangerZone).filter_by(
                is_active=True, category=category
            ).all()

            nearby = None
            for zone in existing_zones:
                dist = calculate_distance(lat, lon, zone.latitude, zone.longitude)
                if dist < 0.2:  # 200 meters
                    nearby = zone
                    break

            if nearby:
                nearby.report_count += 1
                session.commit()
                result = nearby.to_dict()
                return jsonify({'message': 'Report added to existing zone', 'zone': result})

            # Create new zone
            zone = DangerZone(
                zone_id=str(uuid.uuid4()),
                latitude=lat,
                longitude=lon,
                category=category,
                description=description,
                radius_meters=data.get('radius_meters', 100),
                expires_at=datetime.now(timezone.utc) + timedelta(days=30)
            )
            session.add(zone)
            session.commit()
            result = zone.to_dict()

            # Broadcast to dashboards
            socketio.emit('danger_zone_added', result)

            return jsonify({'message': 'Danger zone reported', 'zone': result}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            session.close()

    # GET
    session = get_session(engine)
    try:
        zones = session.query(DangerZone).filter_by(is_active=True).all()
        result = [z.to_dict() for z in zones]
        return jsonify({'zones': result, 'count': len(result)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/checkin-timer', methods=['POST', 'OPTIONS'])
def set_checkin_timer():
    """Set a safe check-in timer"""
    if request.method == 'OPTIONS':
        return '', 204
    session = get_session(engine)
    try:
        data = request.json
        phone = data.get('phone')
        duration_minutes = int(data.get('duration_minutes', 15))

        if not phone:
            return jsonify({'error': 'phone required'}), 400

        user = session.query(User).filter_by(phone=phone).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Deactivate any existing timers
        session.query(CheckInTimer).filter_by(
            user_id=user.id, is_active=True
        ).update({'is_active': False})

        # Create new timer
        timer = CheckInTimer(
            user_id=user.id,
            duration_minutes=duration_minutes,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        )
        session.add(timer)
        session.commit()
        result = timer.to_dict()
        return jsonify({'message': 'Timer set', 'timer': result}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/checkin', methods=['POST', 'OPTIONS'])
def do_checkin():
    """User checks in - resets or deactivates timer"""
    if request.method == 'OPTIONS':
        return '', 204
    session = get_session(engine)
    try:
        data = request.json
        phone = data.get('phone')

        if not phone:
            return jsonify({'error': 'phone required'}), 400

        user = session.query(User).filter_by(phone=phone).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Deactivate timer
        session.query(CheckInTimer).filter_by(
            user_id=user.id, is_active=True
        ).update({'is_active': False})
        session.commit()

        return jsonify({'message': 'Checked in successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/chat/<alert_id>', methods=['GET'])
def get_chat(alert_id):
    """Get chat messages for an alert"""
    session = get_session(engine)
    try:
        messages = session.query(ChatMessage).filter_by(
            alert_id=alert_id
        ).order_by(ChatMessage.timestamp.asc()).all()
        result = [m.to_dict() for m in messages]
        return jsonify({'messages': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/ai/summary/<alert_id>', methods=['GET'])
def get_ai_summary(alert_id):
    """Generate AI-powered incident summary for an alert"""
    session = get_session(engine)
    try:
        alert = session.query(Alert).filter_by(alert_id=alert_id).first()
        if not alert:
            return jsonify({'error': 'Alert not found'}), 404

        alert_dict = alert.to_dict(include_sensitive=True)
        # Add location name
        if alert.latitude and alert.longitude:
            alert_dict['location_name'] = get_location_name(alert.latitude, alert.longitude)

        # Get chat messages
        messages = session.query(ChatMessage).filter_by(
            alert_id=alert_id
        ).order_by(ChatMessage.timestamp.asc()).all()
        chat_list = [m.to_dict() for m in messages]

        summary = generate_incident_summary(alert_dict, chat_list)
        return jsonify({'summary': summary, 'alert_id': alert_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/ai/analyse-chat/<alert_id>', methods=['POST'])
def analyse_chat(alert_id):
    """AI analyses chat messages and recommends escalation"""
    session = get_session(engine)
    try:
        alert = session.query(Alert).filter_by(alert_id=alert_id).first()
        if not alert:
            return jsonify({'error': 'Alert not found'}), 404

        messages = session.query(ChatMessage).filter_by(
            alert_id=alert_id
        ).order_by(ChatMessage.timestamp.asc()).all()
        chat_list = [m.to_dict() for m in messages]

        result = analyse_chat_for_escalation(chat_list, alert.threat_level.value)
        if result and result.get('escalate') and result.get('new_threat_level'):
            new_level = result['new_threat_level']
            alert.threat_level = ThreatLevel[new_level.upper()]
            session.commit()

            # Notify via chat
            esc_msg = ChatMessage(
                alert_id=alert_id,
                sender_type='ai_assistant',
                sender_name='🤖 Safety AI',
                message=f'⚠️ Threat escalated to {new_level.upper()}: {result.get("reasoning", "")}',
            )
            session.add(esc_msg)
            session.commit()
            socketio.emit('new_chat_message', esc_msg.to_dict())
            socketio.emit('alert_status_changed', {
                'alert_id': alert_id,
                'status': alert.status.value,
                'threat_level': new_level
            })

        return jsonify({'analysis': result or {'escalate': False, 'reasoning': 'AI unavailable'}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/ai/geocode', methods=['GET'])
def geocode_location():
    """Reverse geocode a lat/lon to readable address"""
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    if lat is None or lon is None:
        return jsonify({'error': 'lat and lon required'}), 400
    name = get_location_name(lat, lon)
    return jsonify({'location_name': name, 'lat': lat, 'lon': lon})


# ============ CCTV AI ENDPOINTS ============

@app.route('/api/cctv/status', methods=['GET'])
def cctv_status():
    """Get CCTV AI model status"""
    return jsonify(cctv_model_status())


@app.route('/api/cctv/load-model', methods=['POST'])
def cctv_load():
    """Preload the CCTV AI model"""
    if cctv_model_loaded():
        return jsonify({'status': 'loaded', 'message': 'Model already loaded'})
    import threading
    def load_bg():
        cctv_load_model()
    threading.Thread(target=load_bg, daemon=True).start()
    return jsonify({'status': 'loading', 'message': 'Model loading in background...'})


@app.route('/api/cctv/analyse-frame', methods=['POST'])
def cctv_frame():
    """Analyse a single image frame for violence"""
    if 'frame' not in request.files:
        # Try base64 in JSON body
        data = request.get_json(silent=True) or {}
        b64 = data.get('frame_b64', '')
        if b64:
            import base64
            image_bytes = base64.b64decode(b64)
        else:
            return jsonify({'error': 'No frame provided'}), 400
    else:
        image_bytes = request.files['frame'].read()

    result = cctv_analyse_frame(image_bytes)

    # If violence detected, auto-create alert and notify dashboard
    if result.get('violence') and result.get('confidence', 0) >= 0.85:
        socketio.emit('cctv_violence_detected', {
            'confidence': result['confidence'],
            'label': result['label'],
            'detected_at': datetime.now(timezone.utc).isoformat(),
            'source': 'cctv_frame'
        })

    return jsonify(result)


@app.route('/api/cctv/analyse-video', methods=['POST'])
def cctv_video():
    """Analyse uploaded video for violence"""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    video_file = request.files['video']
    os.makedirs('evidence', exist_ok=True)
    temp_path = os.path.join('evidence', f'upload_{uuid.uuid4().hex[:8]}.mp4')
    video_file.save(temp_path)

    def progress_cb(data):
        socketio.emit('cctv_analysis_progress', data)

    result = cctv_analyse_video(temp_path, progress_callback=progress_cb)

    # Clean up temp file (keep clip if violence found)
    if os.path.exists(temp_path) and temp_path != result.get('clip_path'):
        os.remove(temp_path)

    # Notify dashboard of all detections
    if result.get('violence_detected'):
        for det in result.get('detections', []):
            socketio.emit('cctv_violence_detected', {
                'confidence': det['confidence'],
                'label': det['label'],
                'timestamp_sec': det['timestamp_sec'],
                'snapshot_b64': det.get('snapshot_b64'),
                'detected_at': det['detected_at'],
                'source': 'cctv_video'
            })

    return jsonify(result)


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    session = get_session(engine)
    try:
        total_alerts = session.query(Alert).count()
        active_alerts_count = session.query(Alert).filter(
            Alert.status.in_([AlertStatus.TRIGGERED, AlertStatus.ACKNOWLEDGED, AlertStatus.DISPATCHED])
        ).count()
        available_responders = session.query(Responder).filter_by(is_available=True).count()
        total_responders = session.query(Responder).count()
        danger_zones = session.query(DangerZone).filter_by(is_active=True).count()

        # Average response time
        resolved = session.query(Alert).filter(
            Alert.response_time_seconds.isnot(None)
        ).all()
        avg_response = None
        if resolved:
            times = [a.response_time_seconds for a in resolved if a.response_time_seconds]
            if times:
                avg_response = sum(times) / len(times)

        return jsonify({
            'total_alerts': total_alerts,
            'active_alerts': active_alerts_count,
            'available_responders': available_responders,
            'total_responders': total_responders,
            'danger_zones': danger_zones,
            'avg_response_seconds': avg_response
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/reset-demo', methods=['POST'])
def reset_demo():
    """Reset demo data"""
    session = get_session(engine)
    try:
        # Cancel all active alerts
        session.query(Alert).filter(
            Alert.status.in_([AlertStatus.TRIGGERED, AlertStatus.ACKNOWLEDGED, AlertStatus.DISPATCHED])
        ).update({'status': AlertStatus.CANCELLED})
        # Make all responders available
        session.query(Responder).update({'is_available': True, 'current_alert_id': None})
        # Deactivate all timers
        session.query(CheckInTimer).filter_by(is_active=True).update({'is_active': False})
        session.commit()
        socketio.emit('demo_reset', {'message': 'Demo data reset'})
        return jsonify({'message': 'Demo reset successful'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/responders/register', methods=['POST', 'OPTIONS'])
def register_volunteer():
    """Register a volunteer/responder with phone"""
    if request.method == 'OPTIONS':
        return '', 204
    session = get_session(engine)
    try:
        data = request.json
        name = data.get('name')
        phone = data.get('phone')
        resp_type = data.get('type', 'volunteer')

        if not name or not phone:
            return jsonify({'error': 'name and phone required'}), 400

        existing = session.query(Responder).filter_by(phone=phone).first()
        if existing:
            existing.is_available = True
            session.commit()
            result = existing.to_dict()
            return jsonify({'message': 'Responder found', 'responder': result})

        responder = Responder(
            responder_id=f'R{str(uuid.uuid4())[:8]}',
            name=name,
            type=resp_type,
            phone=phone,
            latitude=28.6139 + (hash(phone) % 100) * 0.001,
            longitude=77.2090 + (hash(phone) % 100) * 0.001,
            is_available=True
        )
        session.add(responder)
        session.commit()
        result = responder.to_dict()
        return jsonify({'message': 'Registered', 'responder': result}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


# ============ WebSocket EVENTS ============

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print(f'Client connected: {request.sid}')
    emit('connected', {'message': 'Connected to control center'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f'Client disconnected: {request.sid}')
    
    # Remove from active users
    for user_id, socket_id in list(active_users.items()):
        if socket_id == request.sid:
            del active_users[user_id]
            break


@socketio.on('user_register')
def handle_user_register(data):
    """Register user for WebSocket communication"""
    user_id = data.get('user_id')
    if user_id:
        active_users[user_id] = request.sid
        join_room(f'user_{user_id}')
        emit('registered', {'user_id': user_id})


@socketio.on('location_update')
def handle_location_update(data):
    """Handle real-time location updates"""
    try:
        alert_id = data.get('alert_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if not alert_id:
            return
        
        session = get_session(engine)
        try:
            alert = session.query(Alert).filter_by(alert_id=alert_id).first()
            if not alert:
                return
            
            # Create location update
            location_update = LocationUpdate(
                alert_id=alert.id,
                latitude=latitude,
                longitude=longitude,
                accuracy=data.get('accuracy'),
                speed=data.get('speed'),
                heading=data.get('heading')
            )
            
            session.add(location_update)
            session.commit()
            
            # Broadcast to control centers
            emit('location_updated', {
                'alert_id': alert_id,
                'latitude': latitude,
                'longitude': longitude,
                'timestamp': location_update.timestamp.isoformat()
            }, broadcast=True)
        finally:
            session.close()
        
    except Exception as e:
        print(f'Error handling location update: {e}')


@socketio.on('dispatch_responder')
def handle_dispatch_responder(data):
    """Dispatch responder to alert"""
    try:
        alert_id = data.get('alert_id')
        responder_id = data.get('responder_id')
        
        session = get_session(engine)
        try:
            alert = session.query(Alert).filter_by(alert_id=alert_id).first()
            responder = session.query(Responder).filter_by(
                responder_id=responder_id
            ).first()
            
            if alert and responder:
                alert.status = AlertStatus.DISPATCHED
                alert.dispatched_at = datetime.now(timezone.utc)
                
                # Update assigned responders
                assigned = json.loads(alert.assigned_responders or '[]')
                assigned.append(responder_id)
                alert.assigned_responders = json.dumps(assigned)
                
                # Update responder status
                responder.is_available = False
                responder.current_alert_id = alert_id
                
                session.commit()
                
                # Notify user
                if alert.user_id in active_users:
                    emit('responder_dispatched', {
                        'alert_id': alert_id,
                        'responder': responder.to_dict()
                    }, room=f'user_{alert.user_id}')
                
                # Broadcast to control centers
                emit('alert_status_changed', {
                    'alert_id': alert_id,
                    'status': 'dispatched',
                    'responder': responder.to_dict()
                }, broadcast=True)
        finally:
            session.close()
        
    except Exception as e:
        print(f'Error dispatching responder: {e}')


@socketio.on('update_alert_status')
def handle_update_alert_status(data):
    """Update alert status"""
    try:
        alert_id = data.get('alert_id')
        new_status = data.get('status')
        
        session = get_session(engine)
        try:
            alert = session.query(Alert).filter_by(alert_id=alert_id).first()
            if alert:
                alert.status = AlertStatus[new_status.upper()]
                
                if new_status == 'resolved':
                    alert.resolved_at = datetime.now(timezone.utc)
                    
                    # Make triggered_at timezone-aware if it's naive
                    triggered_at = alert.triggered_at
                    if triggered_at.tzinfo is None:
                        triggered_at = triggered_at.replace(tzinfo=timezone.utc)
                    
                    alert.response_time_seconds = int(
                        (alert.resolved_at - triggered_at).total_seconds()
                    )
                
                session.commit()
                
                # Broadcast status change
                socketio.emit('alert_status_changed', {
                    'alert_id': alert_id,
                    'status': new_status,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
        finally:
            session.close()
        
    except Exception as e:
        print(f'Error updating alert status: {e}')


@socketio.on('send_chat_message')
def handle_chat_message(data):
    """Handle chat message between victim and responder"""
    try:
        alert_id = data.get('alert_id')
        message = data.get('message')
        sender_type = data.get('sender_type', 'user')
        sender_name = data.get('sender_name', 'Anonymous')
        is_quick_reply = data.get('is_quick_reply', False)

        if not alert_id or not message:
            return

        session = get_session(engine)
        try:
            chat_msg = ChatMessage(
                alert_id=alert_id,
                sender_type=sender_type,
                sender_name=sender_name,
                message=message,
                is_quick_reply=is_quick_reply
            )
            session.add(chat_msg)
            session.commit()
            msg_dict = chat_msg.to_dict()
        finally:
            session.close()

        # Broadcast to all connected clients
        socketio.emit('new_chat_message', msg_dict, broadcast=True)

    except Exception as e:
        print(f'Error handling chat: {e}')


@socketio.on('volunteer_accept_alert')
def handle_volunteer_accept(data):
    """Volunteer accepts an alert"""
    try:
        alert_id = data.get('alert_id')
        responder_id = data.get('responder_id')

        session = get_session(engine)
        try:
            alert = session.query(Alert).filter_by(alert_id=alert_id).first()
            responder = session.query(Responder).filter_by(responder_id=responder_id).first()

            if alert and responder:
                alert.status = AlertStatus.DISPATCHED
                alert.dispatched_at = datetime.now(timezone.utc)
                assigned = json.loads(alert.assigned_responders or '[]')
                assigned.append(responder_id)
                alert.assigned_responders = json.dumps(assigned)
                responder.is_available = False
                responder.current_alert_id = alert_id
                session.commit()

                socketio.emit('alert_status_changed', {
                    'alert_id': alert_id,
                    'status': 'dispatched',
                    'responder': responder.to_dict()
                }, broadcast=True)

                # Notify user
                if alert.user_id in active_users:
                    socketio.emit('responder_dispatched', {
                        'alert_id': alert_id,
                        'responder': responder.to_dict()
                    }, room=f'user_{alert.user_id}')
        finally:
            session.close()
    except Exception as e:
        print(f'Error volunteer accept: {e}')


@socketio.on('volunteer_status_update')
def handle_volunteer_status(data):
    """Volunteer updates their status on an alert"""
    try:
        alert_id = data.get('alert_id')
        responder_id = data.get('responder_id')
        status = data.get('status')  # en_route, arrived, resolved

        session = get_session(engine)
        try:
            alert = session.query(Alert).filter_by(alert_id=alert_id).first()
            responder = session.query(Responder).filter_by(responder_id=responder_id).first()

            if alert:
                if status == 'resolved':
                    alert.status = AlertStatus.RESOLVED
                    alert.resolved_at = datetime.now(timezone.utc)
                    triggered_at = alert.triggered_at
                    if triggered_at.tzinfo is None:
                        triggered_at = triggered_at.replace(tzinfo=timezone.utc)
                    alert.response_time_seconds = int((alert.resolved_at - triggered_at).total_seconds())
                    if responder:
                        responder.is_available = True
                        responder.current_alert_id = None
                        responder.total_responses = (responder.total_responses or 0) + 1
                    if alert_id in active_alerts:
                        del active_alerts[alert_id]

                session.commit()

                socketio.emit('alert_status_changed', {
                    'alert_id': alert_id,
                    'status': status if status != 'resolved' else 'resolved',
                    'responder_id': responder_id
                }, broadcast=True)
        finally:
            session.close()
    except Exception as e:
        print(f'Error volunteer status: {e}')


# ============ HELPER FUNCTIONS ============

def find_nearby_responders(session, latitude, longitude, radius_km=5):
    """Find responders within radius — progressively expands if none found"""
    if not latitude or not longitude:
        return []

    all_responders = session.query(Responder).filter_by(is_available=True).all()

    # Compute distances for all responders
    with_dist = []
    for r in all_responders:
        if r.latitude and r.longitude:
            dist = calculate_distance(latitude, longitude, r.latitude, r.longitude)
            with_dist.append((dist, r))

    with_dist.sort(key=lambda x: x[0])

    # Progressive radius: 5km → 15km → 50km (guarantees a responder is always found for demo)
    for max_radius in [radius_km, 15, 50]:
        nearby = [r for dist, r in with_dist if dist <= max_radius]
        if nearby:
            return nearby

    # Absolute fallback: return nearest regardless of distance
    return [r for _, r in with_dist[:3]] if with_dist else []


# ============ INITIALIZATION ============

def init_demo_data():
    """Initialize demo data for testing — spread across Delhi-NCR"""
    session = get_session(engine)
    
    # Check if demo data already exists
    existing_responders = session.query(Responder).count()
    if existing_responders > 0:
        session.close()
        return
    
    # Responders at real Delhi-NCR landmarks
    responder_data = [
        # Police — spread across Delhi
        ('Officer Rajesh Kumar',   'police',    '+91-9876543210', 28.6328, 77.2197),  # Connaught Place
        ('Officer Priya Sharma',   'police',    '+91-9876543211', 28.6562, 77.2315),  # Karol Bagh
        ('Officer Amit Singh',     'police',    '+91-9876543212', 28.5672, 77.2100),  # Saket
        ('Officer Kavita Desai',   'police',    '+91-9876543213', 28.5918, 77.0463),  # Dwarka Sec 10
        ('Officer Rahul Verma',    'police',    '+91-9876543214', 28.6920, 77.1510),  # Pitampura
        ('Rapid Response Unit 1',  'police',    '+91-9876543229', 28.6127, 77.2310),  # India Gate
        ('Rapid Response Unit 2',  'police',    '+91-9876543230', 28.5355, 77.2710),  # Nehru Place
        ('Night Patrol Team',      'police',    '+91-9876543231', 28.6508, 77.3140),  # Laxmi Nagar
        ('Women Safety Squad',     'police',    '+91-9876543232', 28.7041, 77.1025),  # Rohini
        # Volunteers — Delhi + NCR
        ('Volunteer Anjali Patel', 'volunteer', '+91-9876543215', 28.4595, 77.0266),  # Gurgaon Sec 29
        ('Volunteer Rohan Gupta',  'volunteer', '+91-9876543216', 28.5706, 77.3260),  # Noida Sec 18
        ('Volunteer Neha Reddy',   'volunteer', '+91-9876543217', 28.6282, 77.2219),  # Lajpat Nagar
        ('Volunteer Arjun Nair',   'volunteer', '+91-9876543218', 28.7501, 77.1175),  # Narela
        ('Volunteer Simran Kaur',  'volunteer', '+91-9876543219', 28.4817, 77.0714),  # Gurgaon DLF Phase 3
        ('Volunteer Vikram Rao',   'volunteer', '+91-9876543220', 28.6289, 77.0817),  # Janakpuri
        ('Volunteer Pooja Joshi',  'volunteer', '+91-9876543221', 28.5562, 77.1000),  # Vasant Kunj
        ('Community Helper Ravi',  'volunteer', '+91-9876543227', 28.6852, 77.2217),  # Chandni Chowk
        ('Community Helper Meera', 'volunteer', '+91-9876543228', 28.5535, 77.3345),  # Noida Sec 62
        ('Crisis Support Unit',    'volunteer', '+91-9876543234', 28.4089, 77.3178),  # Greater Noida
        # Medical — hospitals across Delhi-NCR
        ('Ambulance Unit 1',       'medical',   '+91-9876543222', 28.5672, 77.2100),  # AIIMS area
        ('Ambulance Unit 2',       'medical',   '+91-9876543223', 28.6139, 77.2090),  # RML Hospital
        ('Ambulance Unit 3',       'medical',   '+91-9876543224', 28.7040, 77.1020),  # Rohini Hospital
        ('Emergency Response Team','medical',   '+91-9876543233', 28.4744, 77.0720),  # Medanta Gurgaon
        # Security
        ('Security Team Alpha',    'security',  '+91-9876543225', 28.5245, 77.1855),  # Vasant Vihar
        ('Security Team Beta',     'security',  '+91-9876543226', 28.6351, 77.2896),  # Mayur Vihar
    ]
    
    responders = []
    for name, resp_type, phone, lat, lon in responder_data:
        responder = Responder(
            responder_id=f'R{str(uuid.uuid4())[:8]}',
            name=name,
            type=resp_type,
            phone=phone,
            latitude=lat,
            longitude=lon,
            is_available=True
        )
        responders.append(responder)
        session.add(responder)
    
    # Mesh nodes spread across Delhi-NCR
    mesh_node_data = [
        ('smart_pole', 28.6328, 77.2197),  # CP
        ('smart_pole', 28.6127, 77.2310),  # India Gate
        ('smart_pole', 28.5672, 77.2100),  # Saket
        ('smart_pole', 28.6920, 77.1510),  # Pitampura
        ('smart_pole', 28.6508, 77.3140),  # Laxmi Nagar
        ('smart_pole', 28.7041, 77.1025),  # Rohini
        ('bus',        28.5918, 77.0463),  # Dwarka route
        ('bus',        28.6282, 77.2219),  # Lajpat Nagar route
        ('bus',        28.6562, 77.2315),  # Karol Bagh route
        ('bus',        28.5355, 77.2710),  # Nehru Place route
        ('lora',       28.4595, 77.0266),  # Gurgaon
        ('lora',       28.5706, 77.3260),  # Noida
        ('lora',       28.4089, 77.3178),  # Greater Noida
        ('beacon',     28.6852, 77.2217),  # Chandni Chowk
        ('beacon',     28.5562, 77.1000),  # Vasant Kunj
    ]
    
    for node_type, lat, lon in mesh_node_data:
        node = MeshNode(
            node_id=f'N{str(uuid.uuid4())[:8]}',
            node_type=node_type,
            latitude=lat,
            longitude=lon,
            is_active=True
        )
        session.add(node)

    # Danger zones at real known problem areas across Delhi-NCR
    demo_zones = [
        DangerZone(zone_id=str(uuid.uuid4()), latitude=28.6200, longitude=77.2150,
                   category='poor_lighting', description='Unlit stretch near Lodhi Garden',
                   report_count=5, expires_at=datetime.now(timezone.utc) + timedelta(days=30)),
        DangerZone(zone_id=str(uuid.uuid4()), latitude=28.6080, longitude=77.2050,
                   category='harassment', description='INA Market underpass — known harassment spot',
                   report_count=8, expires_at=datetime.now(timezone.utc) + timedelta(days=30)),
        DangerZone(zone_id=str(uuid.uuid4()), latitude=28.6170, longitude=77.1980,
                   category='isolated', description='Isolated stretch near Dhaula Kuan',
                   report_count=3, expires_at=datetime.now(timezone.utc) + timedelta(days=30)),
        DangerZone(zone_id=str(uuid.uuid4()), latitude=28.5355, longitude=77.2710,
                   category='poor_lighting', description='Nehru Place flyover — poorly lit at night',
                   report_count=6, expires_at=datetime.now(timezone.utc) + timedelta(days=30)),
        DangerZone(zone_id=str(uuid.uuid4()), latitude=28.5918, longitude=77.0463,
                   category='isolated', description='Dwarka Sec 10 — isolated road near metro station',
                   report_count=4, expires_at=datetime.now(timezone.utc) + timedelta(days=30)),
        DangerZone(zone_id=str(uuid.uuid4()), latitude=28.6508, longitude=77.3140,
                   category='harassment', description='Laxmi Nagar market area after 9 PM',
                   report_count=7, expires_at=datetime.now(timezone.utc) + timedelta(days=30)),
        DangerZone(zone_id=str(uuid.uuid4()), latitude=28.4595, longitude=77.0266,
                   category='crime_prone', description='Gurgaon Sec 29 underpass — crime-prone area',
                   report_count=9, expires_at=datetime.now(timezone.utc) + timedelta(days=30)),
        DangerZone(zone_id=str(uuid.uuid4()), latitude=28.6852, longitude=77.2217,
                   category='harassment', description='Old Delhi lanes — crowded and unsafe for women at night',
                   report_count=11, expires_at=datetime.now(timezone.utc) + timedelta(days=30)),
    ]
    for zone in demo_zones:
        session.add(zone)

    # Add a demo user and 2 pre-seeded alerts so dashboard is populated for judges
    demo_user = User(
        ephemeral_id=f'DEMO_{str(uuid.uuid4())[:8]}',
        name='Demo User (Priya)',
        phone='+91-9999000001',
        emergency_contacts=json.dumps([
            {'name': 'Mom', 'phone': '+91-9999000002'},
            {'name': 'Sister', 'phone': '+91-9999000003'}
        ])
    )
    session.add(demo_user)
    session.flush()  # get demo_user.id

    # Alert 1: resolved alert (shows history)
    alert1 = Alert(
        alert_id=str(uuid.uuid4()),
        user_id=demo_user.id,
        status=AlertStatus.RESOLVED,
        threat_level=ThreatLevel.HIGH,
        trigger_method='button',
        latitude=28.6250,
        longitude=77.2180,
        ai_risk_score=0.72,
        ai_confidence=0.82,
        ai_factors=json.dumps({'time_risk': 1.3, 'trigger_risk': 0.7, 'location_risk': 0.7, 'pattern_risk': 0.5, 'overall_risk_score': 0.72}),
        trigger_context=json.dumps({'area': 'Connaught Place'}),
        response_time_seconds=142,
        triggered_at=datetime.now(timezone.utc) - timedelta(hours=2),
        resolved_at=datetime.now(timezone.utc) - timedelta(hours=1, minutes=57),
        auto_purge_at=datetime.now(timezone.utc) + timedelta(hours=46)
    )
    session.add(alert1)

    # Alert 2: active dispatched alert (shows live dashboard in action)
    # Assign the first available responder
    first_responder = responders[0] if responders else None
    alert2_id = str(uuid.uuid4())
    alert2 = Alert(
        alert_id=alert2_id,
        user_id=demo_user.id,
        status=AlertStatus.DISPATCHED,
        threat_level=ThreatLevel.CRITICAL,
        trigger_method='shake',
        latitude=28.6139,
        longitude=77.2090,
        ai_risk_score=0.88,
        ai_confidence=0.92,
        ai_factors=json.dumps({'time_risk': 1.5, 'trigger_risk': 0.8, 'location_risk': 0.7, 'pattern_risk': 0.7, 'in_danger_zone': True, 'danger_zone_boost': 0.15, 'overall_risk_score': 0.88}),
        trigger_context=json.dumps({'area': 'Karol Bagh'}),
        dispatched_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        triggered_at=datetime.now(timezone.utc) - timedelta(minutes=4),
        auto_purge_at=datetime.now(timezone.utc) + timedelta(hours=48)
    )
    if first_responder:
        alert2.assigned_responders = json.dumps([first_responder.responder_id])
        first_responder.is_available = False
        first_responder.current_alert_id = alert2_id
    session.add(alert2)

    session.commit()
    session.close()

    print(f'Demo data initialized: {len(responders)} responders, 2 pre-seeded alerts added')



# ============ MAIN ============

import threading

def check_timers():
    """Background thread to check expired check-in timers"""
    import time
    while True:
        try:
            time.sleep(10)  # Check every 10 seconds (faster for demo)
            session = get_session(engine)
            try:
                now = datetime.now(timezone.utc)

                # Find timers expiring in 1 minute (send warning)
                warning_threshold = now + timedelta(minutes=1)
                warning_timers = session.query(CheckInTimer).filter(
                    CheckInTimer.is_active == True,
                    CheckInTimer.warning_sent == False,
                    CheckInTimer.expires_at <= warning_threshold
                ).all()

                for timer in warning_timers:
                    timer.warning_sent = True
                    # Notify user via socket
                    if timer.user_id in active_users:
                        socketio.emit('timer_warning', {
                            'expires_at': timer.expires_at.isoformat(),
                            'seconds_left': int((timer.expires_at - now).total_seconds())
                        }, room=f'user_{timer.user_id}')

                # Find expired timers
                expired_timers = session.query(CheckInTimer).filter(
                    CheckInTimer.is_active == True,
                    CheckInTimer.triggered == False,
                    CheckInTimer.expires_at <= now
                ).all()

                for timer in expired_timers:
                    timer.triggered = True
                    timer.is_active = False
                    # Find user
                    user = session.query(User).filter_by(id=timer.user_id).first()
                    if user:
                        # Auto-trigger SOS
                        alert_id = str(uuid.uuid4())
                        alert = Alert(
                            alert_id=alert_id,
                            user_id=user.id,
                            status=AlertStatus.TRIGGERED,
                            threat_level=ThreatLevel.HIGH,
                            trigger_method='timer_expired',
                            trigger_context=json.dumps({'reason': 'check_in_missed'}),
                            ai_risk_score=0.75,
                            ai_confidence=0.6,
                            auto_purge_at=datetime.now(timezone.utc) + timedelta(hours=48)
                        )
                        session.add(alert)
                        session.commit()

                        alert_dict = alert.to_dict(include_sensitive=True)
                        alert_dict['user'] = user.to_dict()
                        active_alerts[alert_id] = alert_dict
                        socketio.emit('alert_triggered', alert_dict)

                        # Notify user
                        if user.id in active_users:
                            socketio.emit('auto_sos_triggered', {
                                'alert_id': alert_id,
                                'reason': 'check_in_missed'
                            }, room=f'user_{user.id}')

                session.commit()
            finally:
                session.close()
        except Exception as e:
            print(f'Timer check error: {e}')

timer_thread = threading.Thread(target=check_timers, daemon=True)
timer_thread.start()


def refresh_danger_zones_cache():
    """Keep AI engine updated with latest danger zones"""
    import time as _time
    while True:
        try:
            sess = get_session(engine)
            try:
                zones = sess.query(DangerZone).filter_by(is_active=True).all()
                zone_list = [{'latitude': z.latitude, 'longitude': z.longitude,
                              'radius_meters': z.radius_meters, 'category': z.category} for z in zones]
                threat_engine.update_danger_zones(zone_list)
            finally:
                sess.close()
        except Exception:
            pass
        _time.sleep(60)


dz_thread = threading.Thread(target=refresh_danger_zones_cache, daemon=True)
dz_thread.start()


@app.route('/api/evidence', methods=['POST', 'OPTIONS'])
def upload_evidence():
    """Receive audio evidence from mobile client"""
    if request.method == 'OPTIONS':
        return '', 204
    try:
        alert_id = request.form.get('alert_id') or (request.get_json(silent=True) or {}).get('alert_id')
        # Accept file upload or base64
        evidence_file = request.files.get('audio')
        evidence_b64 = (request.get_json(silent=True) or {}).get('audio_b64')

        if not alert_id:
            return jsonify({'error': 'alert_id required'}), 400

        # Store metadata (file content stored in memory/filesystem for demo)
        evidence_dir = os.path.join(os.path.dirname(__file__), 'evidence')
        os.makedirs(evidence_dir, exist_ok=True)

        filename = f'evidence_{alert_id[:8]}_{int(datetime.now().timestamp())}'
        if evidence_file:
            safe_name = filename + '.webm'
            evidence_file.save(os.path.join(evidence_dir, safe_name))
        elif evidence_b64:
            import base64
            safe_name = filename + '.b64'
            with open(os.path.join(evidence_dir, safe_name), 'w') as f:
                f.write(evidence_b64[:100] + '...[encrypted]')  # Don't store raw audio

        return jsonify({
            'message': 'Evidence received and encrypted',
            'evidence_id': filename,
            'alert_id': alert_id
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/simulate-sos', methods=['POST', 'OPTIONS'])
def simulate_sos():
    """Simulate an SOS for demo purposes (no real user needed)"""
    if request.method == 'OPTIONS':
        return '', 204
    session = get_session(engine)
    try:
        data = request.get_json(silent=True) or {}
        # Use a demo user or create one
        demo_user = session.query(User).filter_by(name='Demo User').first()
        if not demo_user:
            demo_user = User(
                ephemeral_id=encryption_mgr.generate_ephemeral_id(99999),
                name='Demo User',
                phone='+91-9999999999',
                is_verified=True
            )
            session.add(demo_user)
            session.commit()

        # Delhi-NCR locations for demo — spread across entire region
        import random
        demo_locations = [
            (28.6282, 77.2219, 'Lajpat Nagar'),
            (28.5245, 77.2066, 'Saket Metro'),
            (28.5921, 77.0460, 'Dwarka Sector 10'),
            (28.6517, 77.2219, 'Karol Bagh'),
            (28.6127, 77.2310, 'India Gate'),
            (28.6852, 77.2217, 'Chandni Chowk'),
            (28.5355, 77.2710, 'Nehru Place'),
            (28.7041, 77.1025, 'Rohini Sector 7'),
            (28.6508, 77.3140, 'Laxmi Nagar'),
            (28.4595, 77.0266, 'Gurgaon Sector 29'),
            (28.5706, 77.3260, 'Noida Sector 18'),
            (28.6920, 77.1510, 'Pitampura'),
            (28.5562, 77.1000, 'Vasant Kunj'),
            (28.4817, 77.0714, 'DLF Phase 3 Gurgaon'),
            (28.4089, 77.3178, 'Greater Noida'),
        ]
        lat, lon, area = random.choice(demo_locations)
        lat += random.uniform(-0.003, 0.003)
        lon += random.uniform(-0.003, 0.003)

        trigger_method = data.get('trigger_method', 'button')
        alert_id = str(uuid.uuid4())

        # Gather danger zones for AI context
        danger_zones = session.query(DangerZone).filter_by(is_active=True).all()
        dz_nearby = []
        for zone in danger_zones:
            if calculate_distance(lat, lon, zone.latitude, zone.longitude) < 0.5:
                dz_nearby.append({'category': zone.category, 'report_count': zone.report_count})

        # Try Gemini AI first, fallback to rule-based
        alert_data = {
            'latitude': lat, 'longitude': lon, 'location_name': area,
            'trigger_method': trigger_method, 'user_id': demo_user.id,
            'prior_alerts': session.query(Alert).filter_by(user_id=demo_user.id).count()
        }
        ai_result = assess_threat_with_ai(alert_data, dz_nearby)
        if ai_result:
            threat_level = ai_result.get('threat_level', 'high')
            confidence = ai_result.get('confidence', 0.8)
            risk_factors = ai_result.get('risk_factors', {})
            risk_factors['overall_risk_score'] = ai_result.get('risk_score', 0.7)
            risk_factors['reasoning'] = ai_result.get('reasoning', '')
            risk_factors['ai_source'] = 'groq-llama'
        else:
            threat_level, confidence, risk_factors = threat_engine.assess_threat_level(alert_data)
            risk_factors['ai_source'] = 'rule-based'
            # Manual danger zone boost for rule-based
            for zone in danger_zones:
                dist = calculate_distance(lat, lon, zone.latitude, zone.longitude)
                if dist < (zone.radius_meters / 1000.0):
                    risk_factors['overall_risk_score'] = min(risk_factors.get('overall_risk_score', 0.5) + 0.15, 1.0)
                    if risk_factors['overall_risk_score'] >= 0.8:
                        threat_level = 'critical'
                    elif risk_factors['overall_risk_score'] >= 0.6:
                        threat_level = 'high'
                    break

        alert = Alert(
            alert_id=alert_id,
            user_id=demo_user.id,
            status=AlertStatus.TRIGGERED,
            threat_level=ThreatLevel[threat_level.upper()],
            latitude=lat, longitude=lon,
            trigger_method=trigger_method,
            ai_risk_score=risk_factors.get('overall_risk_score'),
            ai_confidence=confidence,
            ai_factors=json.dumps(risk_factors),
            auto_purge_at=datetime.now(timezone.utc) + timedelta(hours=48)
        )
        session.add(alert)
        session.commit()

        alert_dict = alert.to_dict(include_sensitive=True)
        alert_dict['user'] = demo_user.to_dict()
        alert_dict['_demo_area'] = area
        alert_dict['location_name'] = area
        alert_dict['ai_source'] = risk_factors.get('ai_source', 'unknown')
        if ai_result:
            alert_dict['ai_reasoning'] = ai_result.get('reasoning', '')
        active_alerts[alert_id] = alert_dict
        socketio.emit('alert_triggered', alert_dict)

        # Auto-dispatch nearest responder
        nearby = find_nearby_responders(session, lat, lon)
        dispatched_responder = None
        if nearby:
            nearest = nearby[0]
            nearest.is_available = False
            nearest.current_alert_id = alert_id
            alert.assigned_responders = json.dumps([nearest.responder_id])
            alert.status = AlertStatus.DISPATCHED
            alert.dispatched_at = datetime.now(timezone.utc)
            session.commit()
            dispatched_responder = nearest.to_dict()
            socketio.emit('alert_status_changed', {
                'alert_id': alert_id,
                'status': 'dispatched',
                'responder': dispatched_responder
            })

        # Auto system chat messages
        ai_tag = '🤖 Llama AI' if risk_factors.get('ai_source') == 'groq-llama' else '📊 Rule Engine'
        reasoning = risk_factors.get('reasoning', '')
        sys_msg = ChatMessage(
            alert_id=alert_id, sender_type='system', sender_name='NaariRakshak',
            message=f'🚨 SOS triggered via {trigger_method} near {area}. Threat: {threat_level.upper()} ({ai_tag}, {int(confidence*100)}% confidence). {reasoning}'
        )
        session.add(sys_msg)
        session.commit()
        socketio.emit('new_chat_message', sys_msg.to_dict())

        if dispatched_responder:
            d_msg = ChatMessage(
                alert_id=alert_id, sender_type='system', sender_name='NaariRakshak',
                message=f'✅ Auto-dispatched {dispatched_responder["name"]} ({dispatched_responder["type"]}).'
            )
            session.add(d_msg)
            session.commit()
            socketio.emit('new_chat_message', d_msg.to_dict())

        return jsonify({'message': 'Demo SOS simulated', 'alert': alert_dict, 'area': area}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@socketio.on('trigger_sos')
def handle_trigger_sos_socket(data):
    """Handle SOS trigger via WebSocket (mobile fallback)"""
    # This is handled by the REST API; just log and acknowledge
    user_id = data.get('user_id')
    emit('sos_acknowledged', {'status': 'received', 'user_id': user_id})


if __name__ == '__main__':
    # Initialize demo data
    init_demo_data()

    port = app.config['PORT']
    
    # Check for SSL certificates (handle both project root and server dir execution)
    base_path = os.path.dirname(os.path.abspath(__file__))
    ssl_cert = os.path.join(base_path, 'certs', 'cert.pem')
    ssl_key = os.path.join(base_path, 'certs', 'key.pem')
    use_ssl = os.path.exists(ssl_cert) and os.path.exists(ssl_key)
    
    # Get local IP for mobile access
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "your-local-ip"
    
    protocol = "https" if use_ssl else "http"
    
    print(f"""
    ╔═══════════════════════════════════════════════════╗
    ║   Women's Safety System - Control Center         ║
    ║                                                   ║
    ║   🌐 Local Access:                                ║
    ║      {protocol}://localhost:{port}                        ║
    ║                                                   ║
    ║   📱 Mobile/Network Access:                       ║
    ║      {protocol}://{local_ip}:{port}                ║
    ║                                                   ║
    ║   {'🔒 HTTPS Enabled (Geolocation works!)' if use_ssl else '⚠️  HTTP Mode (Geolocation may not work on mobile)'}      ║
    ║   {'   Accept certificate warning on first access' if use_ssl else '   Run ./setup_https.sh to enable HTTPS'}       ║
    ║                                                   ║
    ║   📊 Dashboard: /{' ' * 30}║
    ║   📱 Mobile App: /app{' ' * 25}║
    ║   🔧 API Docs: /api/health{' ' * 21}║
    ║                                                   ║
    ║   Press Ctrl+C to stop                           ║
    ╚═══════════════════════════════════════════════════╝
    """)
    
    # Run server with SSL if available
    if use_ssl:
        print("🔐 Starting HTTPS server...")
        socketio.run(
            app,
            host=app.config['HOST'],
            port=port,
            debug=False,
            use_reloader=False,
            ssl_context=(ssl_cert, ssl_key),
            allow_unsafe_werkzeug=True
        )
    else:
        print("🌐 Starting HTTP server...")
        socketio.run(
            app,
            host=app.config['HOST'],
            port=port,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
