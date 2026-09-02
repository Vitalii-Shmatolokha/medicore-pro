from flask import Blueprint, render_template, flash, redirect, url_for, g
from flask_login import login_required, current_user
from app.models.models import Appointment, User
from app import db, socketio
from flask_socketio import emit, join_room, leave_room
import logging

bp = Blueprint('video', __name__)
logger = logging.getLogger(__name__)

@bp.route('/video_call/<int:appointment_id>')
@login_required
def video_call(appointment_id):
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        flash('Appointment not found.', 'danger')
        return redirect(url_for('auth.index'))
    
    # Authorize user for this appointment
    if current_user.id != appointment.doctor_id and current_user.id != appointment.patient_id and current_user.role != 'admin':
        flash('Access denied to this consultation room.', 'danger')
        return redirect(url_for('auth.index'))
    
    if not appointment.is_online:
        flash('This appointment is marked as in-person, not online consultation.', 'warning')
        return redirect(url_for('doctor.dashboard') if current_user.role == 'doctor' else url_for('patient.dashboard'))
    
    other_user_id = appointment.patient_id if current_user.id == appointment.doctor_id else appointment.doctor_id
    other_user = db.session.get(User, other_user_id)
    
    return render_template(
        'video_call.html', 
        appointment=appointment,
        other_user=other_user,
        unread_messages=g.unread_messages
    )

def register_video_socket_events():
    @socketio.on('join_video_room', namespace='/video')
    def on_join_video_room(data):
        if not current_user.is_authenticated:
            emit('error', {'message': 'Unauthorized'}, namespace='/video')
            return
        
        appointment_id = data.get('appointment_id')
        peer_id = data.get('peer_id')
        
        if not appointment_id:
            return
            
        appointment = db.session.get(Appointment, int(appointment_id))
        if not appointment or (current_user.id != appointment.doctor_id and current_user.id != appointment.patient_id and current_user.role != 'admin'):
            emit('error', {'message': 'Access to room forbidden'}, namespace='/video')
            return
            
        room = f"video_{appointment_id}"
        join_room(room, namespace='/video')
        logger.info(f"User {current_user.id} ({current_user.name}) joined video room {room}")
        
        emit('user_joined_video', {
            'peer_id': peer_id,
            'user_id': current_user.id,
            'user_name': current_user.name,
            'role': current_user.role
        }, room=room, namespace='/video', include_self=False)

    @socketio.on('leave_video_room', namespace='/video')
    def on_leave_video_room(data):
        appointment_id = data.get('appointment_id')
        if appointment_id:
            room = f"video_{appointment_id}"
            leave_room(room, namespace='/video')
            emit('user_left_video', {
                'user_id': current_user.id if current_user.is_authenticated else None,
                'user_name': current_user.name if current_user.is_authenticated else 'Participant'
            }, room=room, namespace='/video')

    @socketio.on('send_video_chat_message', namespace='/video')
    def on_send_video_chat(data):
        if not current_user.is_authenticated:
            return
            
        appointment_id = data.get('appointment_id')
        message = (data.get('message') or '').strip()
        
        if not appointment_id or not message:
            return
            
        room = f"video_{appointment_id}"
        emit('receive_video_chat_message', {
            'sender_id': current_user.id,
            'sender_name': current_user.name,
            'message': message,
            'timestamp': data.get('timestamp')
        }, room=room, namespace='/video')

    @socketio.on('stream_status_change', namespace='/video')
    def on_stream_status_change(data):
        if not current_user.is_authenticated:
            return
        appointment_id = data.get('appointment_id')
        room = f"video_{appointment_id}"
        emit('remote_stream_status_change', {
            'user_id': current_user.id,
            'is_audio_muted': data.get('is_audio_muted', False),
            'is_video_off': data.get('is_video_off', False)
        }, room=room, namespace='/video', include_self=False)