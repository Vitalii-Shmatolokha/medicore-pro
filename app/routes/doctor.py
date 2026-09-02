from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timezone
from app.models.models import Appointment, MedicalRecord, Prescription, Notification, User, Message, PrescriptionRequest, DoctorSchedule
from werkzeug.security import generate_password_hash
from app.services.schedule_service import generate_doctor_schedules
from app import db
from app.routes.chat import get_contacts, get_unread_counts
from sqlalchemy import or_, and_

bp = Blueprint('doctor', __name__, url_prefix='/doctor')

@bp.route('/dashboard')
@login_required
def dashboard():
    from flask import g
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    assigned_patients = User.query.filter_by(family_doctor_id=current_user.id, role='patient').all()
    appointment_patients = User.query.join(Appointment, Appointment.patient_id == User.id).filter(
        Appointment.doctor_id == current_user.id, User.role == 'patient'
    ).distinct().all()
    patients = list(set(assigned_patients + appointment_patients))
    
    patient_unread_counts = {}
    for patient in patients:
        unread_count = Message.query.filter_by(
            receiver_id=current_user.id,
            sender_id=patient.id,
            is_read=False
        ).count()
        patient_unread_counts[patient.id] = unread_count
    
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.status == 'scheduled',
        Appointment.date >= datetime.now(timezone.utc)
    ).order_by(Appointment.date).all()
    
    completed_appointments = Appointment.query.filter_by(
        doctor_id=current_user.id,
        status='completed'
    ).order_by(Appointment.date.desc()).limit(10).all()
    
    schedules = DoctorSchedule.query.filter(
        DoctorSchedule.doctor_id == current_user.id,
        DoctorSchedule.start_time >= datetime.now(timezone.utc)
    ).order_by(DoctorSchedule.start_time).all()
    
    prescription_requests = PrescriptionRequest.query.filter_by(
        doctor_id=current_user.id,
        status='pending'
    ).count()
    
    return render_template('doctor/dashboard.html',
                         upcoming_appointments=upcoming_appointments,
                         completed_appointments=completed_appointments,
                         patients=patients,
                         patient_unread_counts=patient_unread_counts,
                         schedules=schedules,
                         prescription_requests=prescription_requests,
                         unread_messages=g.unread_messages)

@bp.route('/patients')
@login_required
def view_patients():
    from flask import g
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    # Get patients assigned as family doctor or with appointments
    assigned_patients = User.query.filter_by(family_doctor_id=current_user.id, role='patient').all()
    appointment_patients = User.query.join(Appointment, Appointment.patient_id == User.id).filter(
        Appointment.doctor_id == current_user.id, User.role == 'patient'
    ).distinct().all()
    patients = list(set(assigned_patients + appointment_patients))
    
    return render_template('doctor/patients.html',
                         patients=patients,
                         unread_messages=g.unread_messages)

@bp.route('/patient/<int:patient_id>')
@login_required
def view_patient(patient_id):
    from flask import g
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('doctor.view_patients'))
    
    patient = User.query.get_or_404(patient_id)
    if patient.role != 'patient':
        flash('User is not a patient.', 'danger')
        return redirect(url_for('doctor.view_patients'))
    
    # Verify doctor has access (family doctor or past appointment)
    is_family_doctor = patient.family_doctor_id == current_user.id
    has_appointment = Appointment.query.filter_by(
        doctor_id=current_user.id,
        patient_id=patient_id
    ).first() is not None
    
    if not (is_family_doctor or has_appointment):
        flash('Access denied.', 'danger')
        return redirect(url_for('doctor.view_patients'))
    
    medical_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.created_at.desc()).all()
    appointments = Appointment.query.filter_by(patient_id=patient_id, doctor_id=current_user.id).order_by(Appointment.date.desc()).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient_id).order_by(Prescription.created_at.desc()).all()
    
    return render_template('doctor/view_patient.html',
                         patient=patient,
                         medical_records=medical_records,
                         appointments=appointments,
                         prescriptions=prescriptions,
                         unread_messages=g.unread_messages)

@bp.route('/appointment/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
def view_appointment(appointment_id):
    from flask import g
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('doctor.dashboard'))
    
    appointment = Appointment.query.get_or_404(appointment_id)
    
    if appointment.doctor_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('doctor.dashboard'))
    
    patient = db.session.get(User, appointment.patient_id)
    medical_records = MedicalRecord.query.filter_by(patient_id=patient.id).order_by(MedicalRecord.created_at.desc()).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient.id).order_by(Prescription.created_at.desc()).all()
    medical_record = MedicalRecord.query.filter_by(appointment_id=appointment_id).first()
    
    medications = ['Aspirin', 'Ibuprofen', 'Amoxicillin']
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'complete':
            diagnosis = request.form.get('diagnosis')
            notes = request.form.get('notes')
            medications_list = request.form.getlist('medication[]')
            dosages = request.form.getlist('dosage[]')
            instructions_list = request.form.getlist('instructions[]')
            
            new_record = MedicalRecord(
                patient_id=patient.id,
                appointment_id=appointment_id,
                diagnosis=diagnosis,
                doctor_notes=notes,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(new_record)
            db.session.flush()
            appointment.status = 'completed'
            
            for med, dosage, instr in zip(medications_list, dosages, instructions_list):
                if med and dosage and instr:
                    new_prescription = Prescription(
                        patient_id=patient.id,
                        medical_record_id=new_record.id,
                        medication_name=med,
                        dosage=dosage,
                        instructions=instr,
                        created_at=datetime.now(timezone.utc)
                    )
                    db.session.add(new_prescription)
            
            notification = Notification(
                user_id=patient.id,
                content=f"Your appointment on {appointment.date.strftime('%Y-%m-%d %H:%M')} has been completed.",
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(notification)
            
            db.session.commit()
            
            flash('Appointment completed.', 'success')
            return redirect(url_for('doctor.dashboard'))
        elif action == 'cancel':
            appointment.status = 'cancelled'
            notification = Notification(
                user_id=patient.id,
                content=f"Your appointment on {appointment.date.strftime('%Y-%m-%d %H:%M')} was cancelled.",
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(notification)
            db.session.commit()
            flash('Appointment cancelled.', 'success')
            return redirect(url_for('doctor.dashboard'))
    
    return render_template('doctor/appointment.html',
                         appointment=appointment,
                         patient=patient,
                         medical_records=medical_records,
                         prescriptions=prescriptions,
                         medical_record=medical_record,
                         medications=medications,
                         unread_messages=g.unread_messages)

@bp.route('/prescribe/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def prescribe_medication(patient_id):
    from flask import g
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    patient = User.query.get_or_404(patient_id)
    medical_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.created_at.desc()).all()
    
    if request.method == 'POST':
        medication = request.form.get('medication')
        dosage = request.form.get('dosage')
        instructions = request.form.get('instructions')
        medical_record_id = request.form.get('medical_record_id')
        
        new_prescription = Prescription(
            patient_id=patient_id,
            medical_record_id=medical_record_id if medical_record_id else None,
            medication_name=medication,
            dosage=dosage,
            instructions=instructions,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(new_prescription)
        
        notification = Notification(
            user_id=patient_id,
            content=f"New prescription for {medication} added.",
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(notification)
        
        db.session.commit()
        
        flash('Prescription created!', 'success')
        return redirect(url_for('doctor.dashboard'))
    
    return render_template('doctor/prescribe.html',
                         patient=patient,
                         medical_records=medical_records,
                         unread_messages=g.unread_messages)

@bp.route('/prescription_requests', methods=['GET', 'POST'])
@login_required
def prescription_requests():
    from flask import g
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    requests = PrescriptionRequest.query.filter_by(
        doctor_id=current_user.id,
        status='pending'
    ).order_by(PrescriptionRequest.created_at.desc()).all()
    
    if request.method == 'POST':
        request_id = request.form.get('request_id')
        action = request.form.get('action')
        medical_record_id = request.form.get('medical_record_id')
        dosage = request.form.get('dosage')
        instructions = request.form.get('instructions')
        
        req = PrescriptionRequest.query.get_or_404(request_id)
        if req.doctor_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('doctor.prescription_requests'))
        
        if action == 'approve':
            if not (dosage and instructions):
                flash('Please provide dosage and instructions.', 'danger')
                return redirect(url_for('doctor.prescription_requests'))
            
            new_prescription = Prescription(
                patient_id=req.patient_id,
                medical_record_id=medical_record_id if medical_record_id else None,
                medication_name=req.medication_name,
                dosage=dosage,
                instructions=instructions,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(new_prescription)
            req.status = 'approved'
            
            notification = Notification(
                user_id=req.patient_id,
                content=f"Your request for {req.medication_name} has been approved.",
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(notification)
        
        elif action == 'reject':
            req.status = 'rejected'
            notification = Notification(
                user_id=req.patient_id,
                content=f"Your request for {req.medication_name} has been rejected.",
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(notification)
        
        db.session.commit()
        flash(f'Prescription request {req.status}!', 'success')
        return redirect(url_for('doctor.prescription_requests'))
    
    patients = {req.patient_id: db.session.get(User, req.patient_id) for req in requests}
    medical_records = MedicalRecord.query.filter(MedicalRecord.patient_id.in_([req.patient_id for req in requests])).all()
    
    return render_template('doctor/prescription_requests.html',
                         requests=requests,
                         patients=patients,
                         medical_records=medical_records,
                         unread_messages=g.unread_messages)

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    from flask import g
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.specialty = request.form.get('specialty')
        date_of_birth = request.form.get('date_of_birth')
        new_password = request.form.get('password')
        
        if date_of_birth:
            try:
                current_user.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                flash('Invalid date of birth format.', 'danger')
                return redirect(url_for('doctor.profile'))
        if new_password:
            current_user.password = generate_password_hash(new_password)
        
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('doctor.dashboard'))
    
    return render_template('doctor/profile.html',
                         user=current_user,
                         unread_messages=g.unread_messages)

@bp.route('/availability', methods=['GET', 'POST'])
@login_required
def availability():
    from flask import g
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add':
                start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc)
                end_time = datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc)
                if start_time >= end_time:
                    flash('End time must be after start time.', 'danger')
                    return redirect(url_for('doctor.availability'))
                
                new_schedule = DoctorSchedule(
                    doctor_id=current_user.id,
                    start_time=start_time,
                    end_time=end_time,
                    is_available=True
                )
                db.session.add(new_schedule)
                db.session.commit()
                flash('Availability slot added successfully!', 'success')
            elif action == 'generate':
                generate_doctor_schedules(current_user.id)
                flash('New availability slots generated!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating availability: {str(e)}', 'danger')
        return redirect(url_for('doctor.availability'))
    
    schedules = DoctorSchedule.query.filter(
        DoctorSchedule.doctor_id == current_user.id,
        DoctorSchedule.start_time >= datetime.now(timezone.utc)
    ).order_by(DoctorSchedule.start_time).all()
    
    return render_template('doctor/availability.html',
                         schedules=schedules,
                         unread_messages=g.unread_messages)

@bp.route('/get_availability')
@login_required
def get_availability():
    if current_user.role != 'doctor':
        return jsonify({'error': 'Access denied'}), 403
    
    schedules = DoctorSchedule.query.filter_by(doctor_id=current_user.id).all()
    events = [{
        'id': schedule.id,
        'title': 'Available',
        'start': schedule.start_time.isoformat(),
        'end': schedule.end_time.isoformat(),
        'color': 'green' if schedule.is_available else 'red'
    } for schedule in schedules]
    return jsonify(events)

@bp.route('/delete_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('doctor.availability'))
    
    schedule = DoctorSchedule.query.get_or_404(schedule_id)
    if schedule.doctor_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('doctor.availability'))
    
    appointments = Appointment.query.filter(
        Appointment.doctor_id == current_user.id,
        Appointment.date >= schedule.start_time,
        Appointment.date <= schedule.end_time,
        Appointment.status == 'scheduled'
    ).all()
    
    for appointment in appointments:
        appointment.status = 'cancelled'
        notification = Notification(
            user_id=appointment.patient_id,
            content=f"Your appointment on {appointment.date.strftime('%Y-%m-%d %H:%M')} was cancelled.",
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(notification)
    
    db.session.delete(schedule)
    db.session.commit()
    
    flash('Schedule deleted!', 'success')
    return redirect(url_for('doctor.availability'))

@bp.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    appointments = Appointment.query.filter_by(
        doctor_id=current_user.id,
        status='scheduled'
    ).all()
    
    for appointment in appointments:
        appointment.status = 'cancelled'
        notification = Notification(
            user_id=appointment.patient_id,
            content=f"Your appointment on {appointment.date.strftime('%Y-%m-%d %H:%M')} was cancelled.",
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(notification)
    
    db.session.delete(current_user)
    db.session.commit()
    
    flash('Account deleted.', 'success')
    return redirect(url_for('auth.index'))

@bp.route('/chats/<int:contact_id>/<int:page>')
@bp.route('/chats/<int:contact_id>')
@bp.route('/chats')
@login_required
def chats(contact_id=None, page=1):
    from flask import g
    if current_user.role != 'doctor':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    per_page = 20
    contacts, contact_type = get_contacts(current_user)
    unread_counts = get_unread_counts(current_user, contacts)
    
    messages = None
    error = None
    if contact_id:
        contact = User.query.filter_by(id=contact_id, role='patient').first()
        if not contact:
            error = f"Contact ID {contact_id} does not exist"
        elif contact not in contacts:
            error = f"Contact ID {contact_id} is not in your contact list"
        else:
            messages = Message.query.filter(
                or_(
                    and_(Message.sender_id == current_user.id, Message.receiver_id == contact_id),
                    and_(Message.sender_id == contact_id, Message.receiver_id == current_user.id)
                )
            ).order_by(Message.created_at.asc()).paginate(page=page, per_page=per_page, error_out=False)
            
            unread_messages = Message.query.filter_by(
                receiver_id=current_user.id,
                sender_id=contact_id,
                is_read=False
            ).all()
            for msg in unread_messages:
                msg.is_read = True
            db.session.commit()
    
    return render_template(
        'chat/chats.html',
        contacts=contacts,
        selected_contact_id=contact_id,
        contact_type=contact_type,
        contact_unread_counts=unread_counts,
        messages=messages,
        error=error,
        unread_messages=g.unread_messages
    )