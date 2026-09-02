from flask import Blueprint, render_template, request, g, flash, jsonify
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from app import db, socketio
from app.models.models import User, Message, Appointment
from datetime import datetime, timezone
import logging

chat_bp = Blueprint('chat', __name__)
logger = logging.getLogger(__name__)

def get_unread_counts(user, contacts):
    unread_counts = {}
    for contact in contacts:
        count = Message.query.filter_by(
            receiver_id=user.id,
            sender_id=contact.id,
            is_read=False
        ).count()
        unread_counts[contact.id] = count
    return unread_counts

def get_contacts(user):
    contacts = []
    contact_type = 'doctor' if user.role == 'patient' else 'patient'
    
    if user.role == 'patient':
        if user.family_doctor_id:
            family_doctor = db.session.get(User, user.family_doctor_id)
            if family_doctor and family_doctor.role == 'doctor':
                contacts.append(family_doctor)
        
        appointment_doctors = User.query.join(Appointment, Appointment.doctor_id == User.id).filter(
            Appointment.patient_id == user.id,
            User.role == 'doctor'
        ).distinct().all()
        contacts.extend(appointment_doctors)
        
        message_doctors = User.query.join(Message, Message.sender_id == User.id).filter(
            Message.receiver_id == user.id,
            User.role == 'doctor'
        ).distinct().all()
        contacts.extend(message_doctors)
        
        message_doctors_sent = User.query.join(Message, Message.receiver_id == User.id).filter(
            Message.sender_id == user.id,
            User.role == 'doctor'
        ).distinct().all()
        contacts.extend(message_doctors_sent)
    
    elif user.role == 'doctor':
        assigned_patients = User.query.filter_by(family_doctor_id=user.id, role='patient').all()
        contacts.extend(assigned_patients)
        
        appointment_patients = User.query.join(Appointment, Appointment.patient_id == User.id).filter(
            Appointment.doctor_id == user.id,
            User.role == 'patient'
        ).distinct().all()
        contacts.extend(appointment_patients)
        
        message_patients = User.query.join(Message, Message.sender_id == User.id).filter(
            Message.receiver_id == user.id,
            User.role == 'patient'
        ).distinct().all()
        contacts.extend(message_patients)
        
        message_patients_sent = User.query.join(Message, Message.receiver_id == User.id).filter(
            Message.sender_id == user.id,
            User.role == 'patient'
        ).distinct().all()
        contacts.extend(message_patients_sent)
    else:
        # Admin can view all doctors and patients
        contacts = User.query.filter(User.id != user.id).all()
    
    # Deduplicate contacts
    unique_contacts = list({c.id: c for c in contacts if c.id != user.id}.values())
    return unique_contacts, contact_type

@chat_bp.route('/chats/<int:contact_id>/<int:page>')
@chat_bp.route('/chats/<int:contact_id>')
@chat_bp.route('/chats')
@login_required
def chats(contact_id=None, page=1):
    per_page = 30
    contacts, contact_type = get_contacts(current_user)
    unread_counts = get_unread_counts(current_user, contacts)
    
    messages = None
    error = None
    selected_contact = None
    
    if contact_id:
        selected_contact = db.session.get(User, contact_id)
        if not selected_contact:
            error = "Contact does not exist."
        else:
            messages = Message.query.filter(
                ((Message.sender_id == current_user.id) & (Message.receiver_id == contact_id)) |
                ((Message.sender_id == contact_id) & (Message.receiver_id == current_user.id))
            ).order_by(Message.created_at.asc()).paginate(page=page, per_page=per_page, error_out=False)
            
            # Mark messages as read
            unread_messages = Message.query.filter_by(
                receiver_id=current_user.id,
                sender_id=contact_id,
                is_read=False
            ).all()
            if unread_messages:
                for msg in unread_messages:
                    msg.is_read = True
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error marking messages as read: {str(e)}")
    
    return render_template(
        'chat/chats.html',
        contacts=contacts,
        selected_contact=selected_contact,
        selected_contact_id=contact_id,
        contact_type=contact_type,
        contact_unread_counts=unread_counts,
        messages=messages,
        error=error,
        unread_messages=g.unread_messages
    )

def register_chat_socket_events():
    @socketio.on('join_chat')
    def handle_join_chat(data):
        if not current_user.is_authenticated:
            emit('error', {'message': 'Authentication required'})
            return
        
        contact_id = data.get('contact_id')
        if not contact_id:
            emit('error', {'message': 'Missing contact_id'})
            return
        
        try:
            contact_id = int(contact_id)
        except (ValueError, TypeError):
            emit('error', {'message': 'Invalid contact_id'})
            return
            
        room = f"chat_{min(current_user.id, contact_id)}_{max(current_user.id, contact_id)}"
        join_room(room)
        emit('joined_chat', {'room': room, 'user_id': current_user.id}, room=room)

    @socketio.on('leave_chat')
    def handle_leave_chat(data):
        contact_id = data.get('contact_id')
        if contact_id and current_user.is_authenticated:
            try:
                contact_id = int(contact_id)
                room = f"chat_{min(current_user.id, contact_id)}_{max(current_user.id, contact_id)}"
                leave_room(room)
            except (ValueError, TypeError):
                pass

    @socketio.on('send_chat_message')
    def handle_send_message(data):
        if not current_user.is_authenticated:
            emit('error', {'message': 'Authentication required'})
            return
        
        receiver_id = data.get('receiver_id')
        content = (data.get('content') or '').strip()
        
        if not receiver_id or not content:
            emit('error', {'message': 'Receiver and content cannot be empty'})
            return
        
        try:
            receiver_id = int(receiver_id)
        except (ValueError, TypeError):
            emit('error', {'message': 'Invalid receiver ID'})
            return
        
        receiver = db.session.get(User, receiver_id)
        if not receiver:
            emit('error', {'message': 'Recipient not found'})
            return
        
        try:
            message = Message(
                sender_id=current_user.id,
                receiver_id=receiver_id,
                content=content,
                created_at=datetime.now(timezone.utc),
                is_read=False
            )
            db.session.add(message)
            db.session.commit()
            
            room = f"chat_{min(current_user.id, receiver_id)}_{max(current_user.id, receiver_id)}"
            payload = {
                'id': message.id,
                'sender_id': message.sender_id,
                'receiver_id': message.receiver_id,
                'content': message.content,
                'created_at': message.created_at.strftime('%H:%M'),
                'is_read': message.is_read,
                'sender_name': current_user.name
            }
            emit('receive_chat_message', payload, room=room)
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to persist chat message: {str(e)}", exc_info=True)
            emit('error', {'message': 'Failed to deliver message. Please retry.'})