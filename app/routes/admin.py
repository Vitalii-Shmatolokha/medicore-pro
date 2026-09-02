from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, send_file
from flask_login import login_required, current_user
from datetime import datetime, timezone, timedelta
from app.models.models import User, Appointment, MedicalRecord, DoctorSchedule, Notification
from app.services.schedule_service import generate_doctor_schedules
from werkzeug.security import generate_password_hash
from app import db
import logging
import csv
from io import StringIO
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/dashboard')
@login_required
def dashboard():
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    doctors = User.query.filter_by(role='doctor').all()
    patients = User.query.filter_by(role='patient').all()
    appointments = Appointment.query.order_by(Appointment.date.desc()).limit(10).all()
    
    return render_template('admin/dashboard.html', 
                         doctors=doctors,
                         patients=patients,
                         appointments=appointments,
                         unread_messages=g.unread_messages)

@bp.route('/manage_doctors', methods=['GET', 'POST'])
@login_required
def manage_doctors():
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        specialty = request.form.get('specialty')
        date_of_birth = request.form.get('date_of_birth')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.', 'danger')
            return redirect(url_for('admin.manage_doctors'))
        
        hashed_password = generate_password_hash(password)
        new_doctor = User(
            name=name,
            email=email,
            password=hashed_password,
            role='doctor',
            specialty=specialty,
            date_of_birth=datetime.strptime(date_of_birth, '%Y-%m-%d').replace(tzinfo=timezone.utc) if date_of_birth else None
        )
        
        db.session.add(new_doctor)
        db.session.commit()
        
        try:
            start_date = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            generate_doctor_schedules(
                doctor_id=new_doctor.id,
                start_date=start_date,
                days=7,
                start_hour=9,
                end_hour=17,
                slot_duration=30,
                skip_weekends=True,
                delete_existing=False
            )
            flash('Doctor added! Schedules generated.', 'success')
        except Exception as e:
            flash(f'Doctor added, but failed to generate schedules: {str(e)}', 'warning')
        
        return redirect(url_for('admin.manage_doctors'))
    
    doctors = User.query.filter_by(role='doctor').all()
    return render_template('admin/manage_doctors.html', 
                         doctors=doctors, 
                         unread_messages=g.unread_messages)

@bp.route('/edit_doctor/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def edit_doctor(doctor_id):
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    doctor = User.query.get_or_404(doctor_id)
    
    if doctor.role != 'doctor':
        flash('User is not a doctor.', 'danger')
        return redirect(url_for('admin.manage_doctors'))
    
    if request.method == 'POST':
        doctor.name = request.form.get('name')
        doctor.specialty = request.form.get('specialty')
        date_of_birth = request.form.get('date_of_birth')
        new_password = request.form.get('password')
        
        if date_of_birth:
            try:
                doctor.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                flash('Invalid date of birth format.', 'danger')
                return redirect(url_for('admin.edit_doctor', doctor_id=doctor_id))
        if new_password:
            doctor.password = generate_password_hash(new_password)
        
        db.session.commit()
        
        flash('Doctor updated!', 'success')
        return redirect(url_for('admin.manage_doctors'))
    
    return render_template('admin/edit_doctor.html', 
                         doctor=doctor, 
                         unread_messages=g.unread_messages)

@bp.route('/delete_doctor/<int:doctor_id>', methods=['POST'])
@login_required
def delete_doctor(doctor_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    doctor = User.query.get_or_404(doctor_id)
    
    if doctor.role != 'doctor':
        flash('User is not a doctor.', 'danger')
        return redirect(url_for('admin.manage_doctors'))
    
    appointments = Appointment.query.filter_by(
        doctor_id=doctor_id,
        status='scheduled'
    ).all()
    
    for appointment in appointments:
        appointment.status = 'cancelled'
        notification = Notification(
            user_id=appointment.patient_id,
            content=f"Your appointment on {appointment.date.strftime('%Y-%m-%d %H:%M')} was cancelled."
        )
        db.session.add(notification)
    
    db.session.delete(doctor)
    db.session.commit()
    
    flash('Doctor deleted!', 'success')
    return redirect(url_for('admin.manage_doctors'))

@bp.route('/manage_patients', methods=['GET', 'POST'])
@login_required
def manage_patients():
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        date_of_birth = request.form.get('date_of_birth')
        
        if not all([name, email, password]):
            flash('Name, email, and password are required.', 'danger')
            return redirect(url_for('admin.manage_patients'))
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.', 'danger')
            return redirect(url_for('admin.manage_patients'))
        
        hashed_password = generate_password_hash(password)
        new_patient = User(
            name=name,
            email=email,
            password=hashed_password,
            role='patient',
            date_of_birth=datetime.strptime(date_of_birth, '%Y-%m-%d').replace(tzinfo=timezone.utc) if date_of_birth else None
        )
        
        try:
            db.session.add(new_patient)
            db.session.commit()
            flash('Patient added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding patient: {str(e)}', 'danger')
        
        return redirect(url_for('admin.manage_patients'))
    
    patients = User.query.filter_by(role='patient').all()
    return render_template('admin/manage_patients.html', 
                         patients=patients, 
                         unread_messages=g.unread_messages)

@bp.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def edit_patient(patient_id):
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    patient = User.query.get_or_404(patient_id)
    
    if patient.role != 'patient':
        flash('User is not a patient.', 'danger')
        return redirect(url_for('admin.manage_patients'))
    
    if request.method == 'POST':
        patient.name = request.form.get('name')
        date_of_birth = request.form.get('date_of_birth')
        new_password = request.form.get('password')
        
        if date_of_birth:
            try:
                patient.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                flash('Invalid date of birth format.', 'danger')
                return redirect(url_for('admin.edit_patient', patient_id=patient_id))
        else:
            patient.date_of_birth = None
        
        if new_password:
            patient.password = generate_password_hash(new_password)
        
        try:
            db.session.commit()
            flash('Patient updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating patient: {str(e)}', 'danger')
        
        return redirect(url_for('admin.manage_patients'))
    
    return render_template('admin/edit_patient.html', 
                         patient=patient, 
                         unread_messages=g.unread_messages)

@bp.route('/delete_patient/<int:patient_id>', methods=['POST'])
@login_required
def delete_patient(patient_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    patient = User.query.get_or_404(patient_id)
    
    if patient.role != 'patient':
        flash('User is not a patient.', 'danger')
        return redirect(url_for('admin.manage_patients'))
    
    appointments = Appointment.query.filter_by(
        patient_id=patient_id,
        status='scheduled'
    ).all()
    
    for appointment in appointments:
        appointment.status = 'cancelled'
        notification = Notification(
            user_id=appointment.doctor_id,
            content=f"Patient {patient.name}'s appointment on {appointment.date.strftime('%Y-%m-%d %H:%M')} was cancelled."
        )
        db.session.add(notification)
    
    try:
        db.session.delete(patient)
        db.session.commit()
        flash('Patient deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting patient: {str(e)}', 'danger')
    
    return redirect(url_for('admin.manage_patients'))

@bp.route('/patient/<int:patient_id>')
@login_required
def view_patient(patient_id):
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    patient = User.query.get_or_404(patient_id)
    
    if patient.role != 'patient':
        flash('User is not a patient.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    medical_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.created_at.desc()).all()
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.date.desc()).all()
    
    return render_template('admin/view_patient.html', 
                         patient=patient,
                         medical_records=medical_records,
                         appointments=appointments,
                         unread_messages=g.unread_messages)

@bp.route('/export_appointments', methods=['GET'])
@login_required
def export_appointments():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    appointments = Appointment.query.order_by(Appointment.date.desc()).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Doctor', 'Patient', 'Date', 'Type', 'Status'])
    
    for appointment in appointments:
        writer.writerow([
            appointment.doctor.name,
            appointment.patient.name,
            appointment.date.strftime('%Y-%m-%d %H:%M'),
            'Online' if appointment.is_online else 'In-person',
            appointment.status.capitalize()
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=appointments.csv'}
    )

@bp.route('/export_patient_appointments/<int:patient_id>', methods=['GET'])
@login_required
def export_patient_appointments(patient_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    patient = User.query.get_or_404(patient_id)
    if patient.role != 'patient':
        flash('User is not a patient.', 'danger')
        return redirect(url_for('auth.index'))
    
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.date.desc()).all()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Doctor', 'Date', 'Type', 'Status'])
    
    for appointment in appointments:
        writer.writerow([
            appointment.doctor.name,
            appointment.date.strftime('%Y-%m-%d %H:%M'),
            'Online' if appointment.is_online else 'In-person',
            appointment.status.capitalize()
        ])
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={patient.name}_appointments.csv'}
    )

@bp.route('/export_medical_records/<int:patient_id>', methods=['GET'])
@login_required
def export_medical_records(patient_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    patient = User.query.get_or_404(patient_id)
    if patient.role != 'patient':
        flash('User is not a patient.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    medical_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.created_at.desc()).all()
    
    # Generating LaTeX document
    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0f172a'),
            spaceAfter=6
        )
        subtitle_style = ParagraphStyle(
            'SubtitleStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=12
        )
        section_style = ParagraphStyle(
            'SectionStyle',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=colors.HexColor('#0284c7'),
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=colors.HexColor('#334155'),
            spaceAfter=4
        )
        bold_body_style = ParagraphStyle(
            'BoldBodyStyle',
            parent=body_style,
            fontName='Helvetica-Bold'
        )

        story = []
        story.append(Paragraph("MediCore Clinical Healthcare Systems", title_style))
        story.append(Paragraph(f"Longitudinal Electronic Medical Record &bull; Patient: <b>{patient.name}</b>", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0'), spaceAfter=12))

        story.append(Paragraph("Patient Demographics", section_style))
        dob_str = patient.date_of_birth.strftime('%d/%m/%Y') if patient.date_of_birth else 'Not recorded'
        allergies_str = patient.allergies or 'No documented allergies (NKDA)'
        story.append(Paragraph(f"<b>NHS / Patient ID:</b> #{patient.id} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Email:</b> {patient.email}", body_style))
        story.append(Paragraph(f"<b>Date of Birth:</b> {dob_str} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Allergies:</b> <font color='#e11d48'>{allergies_str}</font>", body_style))
        story.append(Spacer(1, 10))

        story.append(Paragraph("Clinical Consultation & Encounter History", section_style))
        if medical_records:
            for rec in medical_records:
                rec_date = rec.created_at.strftime('%d/%m/%Y at %H:%M GMT') if rec.created_at else 'Unknown Date'
                diag = rec.diagnosis or 'Routine Assessment'
                notes = rec.doctor_notes or 'No notes recorded.'
                story.append(Paragraph(f"<b>Encounter Date:</b> {rec_date} &nbsp;&bull;&nbsp; <b>Diagnosis:</b> {diag}", bold_body_style))
                story.append(Paragraph(f"<b>Attending Notes:</b> {notes}", body_style))
                if rec.prescriptions:
                    p_list = ", ".join([f"{p.medication_name} ({p.dosage})" for p in rec.prescriptions])
                    story.append(Paragraph(f"<b>Prescriptions Issued:</b> {p_list}", body_style))
                story.append(Spacer(1, 6))
        else:
            story.append(Paragraph("No medical records documented.", body_style))

        doc.build(story)
        buffer.seek(0)

        clean_name = "".join(c for c in patient.name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{clean_name}_medical_records.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        flash(f'Error generating PDF: {str(e)}', 'danger')
        return redirect(url_for('admin.view_patient', patient_id=patient_id))

@bp.route('/schedule_doctor/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def schedule_doctor(doctor_id):
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    doctor = User.query.get_or_404(doctor_id)
    
    if doctor.role != 'doctor':
        flash('User is not a doctor.', 'danger')
        return redirect(url_for('admin.manage_doctors'))
    
    if request.method == 'POST':
        schedule_type = request.form.get('schedule_type')
        
        if schedule_type == 'single':
            start_time_str = request.form.get('start_time')
            end_time_str = request.form.get('end_time')
            
            if not (start_time_str and end_time_str):
                flash('Start time and end time are required for manual scheduling.', 'danger')
                return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
            
            try:
                start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc)
                end_time = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M').replace(tzinfo=timezone.utc)
                
                if end_time <= start_time:
                    flash('End time must be after start time.', 'danger')
                    return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
                
                new_schedule = DoctorSchedule(
                    doctor_id=doctor_id,
                    start_time=start_time,
                    end_time=end_time,
                    is_available=True
                )
                
                db.session.add(new_schedule)
                db.session.commit()
                
                flash('Schedule added!', 'success')
                logger.info(f"Added single schedule for doctor_id={doctor_id}: {start_time} to {end_time}")
            except ValueError as e:
                flash(f'Invalid date/time format: {str(e)}', 'danger')
                logger.error(f"Invalid date/time format for doctor_id={doctor_id}: {str(e)}")
                return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
        
        elif schedule_type == 'bulk':
            start_date_str = request.form.get('start_date')
            days = request.form.get('days')
            start_hour = request.form.get('start_hour')
            end_hour = request.form.get('end_hour')
            slot_duration = request.form.get('slot_duration')
            skip_weekends = 'skip_weekends' in request.form
            delete_existing = 'delete_existing' in request.form
            
            if not all([start_date_str, days, start_hour, end_hour, slot_duration]):
                flash('All fields are required for auto scheduling.', 'danger')
                return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
            
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                days = int(days)
                start_hour = int(start_hour)
                end_hour = int(end_hour)
                slot_duration = int(slot_duration)
                
                if not (1 <= days <= 90):
                    flash('Number of days must be between 1 and 90.', 'danger')
                    return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
                
                if not (0 <= start_hour <= 23) or not (1 <= end_hour <= 24):
                    flash('Invalid start or end hour.', 'danger')
                    return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
                
                if end_hour <= start_hour:
                    flash('End hour must be after start hour.', 'danger')
                    return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
                
                if slot_duration not in [15, 30, 60]:
                    flash('Invalid slot duration. Choose 15, 30, or 60 minutes.', 'danger')
                    return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
                
                generate_doctor_schedules(
                    doctor_id=doctor_id,
                    start_date=start_date,
                    days=days,
                    start_hour=start_hour,
                    end_hour=end_hour,
                    slot_duration=slot_duration,
                    skip_weekends=skip_weekends,
                    delete_existing=delete_existing
                )
                
                flash('Schedules generated successfully!', 'success')
                logger.info(f"Generated bulk schedules for doctor_id={doctor_id}: {days} days starting {start_date}")
            except ValueError as e:
                flash(f'Invalid input format: {str(e)}', 'danger')
                logger.error(f"Invalid input for bulk scheduling doctor_id={doctor_id}: {str(e)}")
                return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
            except Exception as e:
                flash(f'Error generating schedules: {str(e)}', 'danger')
                logger.error(f"Error generating schedules for doctor_id={doctor_id}: {str(e)}")
                return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
        
        else:
            flash('Invalid schedule type.', 'danger')
            logger.warning(f"Invalid schedule type for doctor_id={doctor_id}: {schedule_type}")
            return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))
    
    schedules = DoctorSchedule.query.filter_by(doctor_id=doctor_id).order_by(DoctorSchedule.start_time).all()
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return render_template('admin/schedule_doctor.html', 
                         doctor=doctor, 
                         schedules=schedules, 
                         today=today,
                         unread_messages=g.unread_messages)

@bp.route('/delete_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    schedule = DoctorSchedule.query.get_or_404(schedule_id)
    doctor_id = schedule.doctor_id
    
    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.date >= schedule.start_time,
        Appointment.date <= schedule.end_time,
        Appointment.status == 'scheduled'
    ).all()
    
    for appointment in appointments:
        appointment.status = 'cancelled'
        notification = Notification(
            user_id=appointment.patient_id,
            content=f"Your appointment on {appointment.date.strftime('%Y-%m-%d %H:%M')} was cancelled."
        )
        db.session.add(notification)
    
    db.session.delete(schedule)
    db.session.commit()
    
    flash('Schedule deleted!', 'success')
    logger.info(f"Deleted schedule_id={schedule_id} for doctor_id={doctor_id}")
    return redirect(url_for('admin.schedule_doctor', doctor_id=doctor_id))

@bp.route('/generate_schedule/<int:doctor_id>', methods=['POST'])
@login_required
def generate_schedule(doctor_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    doctor = User.query.get_or_404(doctor_id)
    if doctor.role != 'doctor':
        flash('User is not a doctor.', 'danger')
        return redirect(url_for('admin.manage_doctors'))
    
    start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    days = int(request.form.get('days', 7))
    start_hour = int(request.form.get('start_hour', 9))
    end_hour = int(request.form.get('end_hour', 17))
    slot_duration = int(request.form.get('slot_duration', 30))
    skip_weekends = 'skip_weekends' in request.form
    delete_existing = 'delete_existing' in request.form
    
    try:
        generate_doctor_schedules(
            doctor_id=doctor_id,
            start_date=start_date,
            days=days,
            start_hour=start_hour,
            end_hour=end_hour,
            slot_duration=slot_duration,
            skip_weekends=skip_weekends,
            delete_existing=delete_existing
        )
        flash(f'Schedules generated for Dr. {doctor.name}!', 'success')
        logger.info(f"Generated schedules for doctor_id={doctor_id} via generate_schedule route")
    except Exception as e:
        flash(f'Error generating schedules: {str(e)}', 'danger')
        logger.error(f"Error in generate_schedule for doctor_id={doctor_id}: {str(e)}")
    
    return redirect(url_for('admin.manage_doctors'))

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    settings = {
        'slot_duration': 30,
        'notification_email': True,
        'notification_sms': False
    }
    
    if request.method == 'POST':
        try:
            settings['slot_duration'] = int(request.form.get('slot_duration', 30))
            settings['notification_email'] = 'notification_email' in request.form
            settings['notification_sms'] = 'notification_sms' in request.form
            flash('Settings updated successfully!', 'success')
            logger.info("Updated admin settings")
        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'danger')
            logger.error(f"Error updating settings: {str(e)}")
        return redirect(url_for('admin.settings'))
    
    return render_template('admin/settings.html', 
                         settings=settings, 
                         unread_messages=g.unread_messages)

@bp.route('/manage_appointments', methods=['GET'])
@bp.route('/appointments', methods=['GET'])
@login_required
def manage_appointments():
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))

    doctor_id = request.args.get('doctor_id', type=int)
    patient_id = request.args.get('patient_id', type=int)
    status = request.args.get('status', type=str)
    is_online = request.args.get('is_online', type=str)
    search = request.args.get('search', type=str)

    query = Appointment.query

    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if patient_id:
        query = query.filter(Appointment.patient_id == patient_id)
    if status:
        query = query.filter(Appointment.status == status)
    if is_online in ('1', 'true', 'True'):
        query = query.filter(Appointment.is_online == True)
    elif is_online in ('0', 'false', 'False'):
        query = query.filter(Appointment.is_online == False)

    appointments = query.order_by(Appointment.date.desc()).all()
    doctors = User.query.filter_by(role='doctor').order_by(User.name).all()
    patients = User.query.filter_by(role='patient').order_by(User.name).all()

    return render_template(
        'admin/manage_appointments.html',
        appointments=appointments,
        doctors=doctors,
        patients=patients,
        doctor_id=doctor_id,
        patient_id=patient_id,
        selected_status=status,
        selected_is_online=is_online,
        unread_messages=g.unread_messages
    )

@bp.route('/appointment/<int:appointment_id>', methods=['GET'])
@login_required
def view_appointment(appointment_id):
    from flask import g
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))

    appointment = Appointment.query.get_or_404(appointment_id)
    return render_template(
        'admin/appointment_detail.html',
        appointment=appointment,
        unread_messages=g.unread_messages
    )

@bp.route('/appointment/<int:appointment_id>/update_status', methods=['POST'])
@login_required
def update_appointment_status(appointment_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))

    appointment = Appointment.query.get_or_404(appointment_id)
    new_status = request.form.get('status')
    if new_status in ('scheduled', 'completed', 'cancelled'):
        appointment.status = new_status
        db.session.commit()
        flash(f'Consultation #{appointment.id} status updated to {new_status.capitalize()}.', 'success')
    else:
        flash('Invalid status provided.', 'danger')

    redirect_to = request.form.get('next') or url_for('admin.manage_appointments')
    return redirect(redirect_to)

@bp.route('/appointment/<int:appointment_id>/delete', methods=['POST'])
@login_required
def delete_appointment(appointment_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))

    appointment = Appointment.query.get_or_404(appointment_id)
    db.session.delete(appointment)
    db.session.commit()
    flash(f'Consultation record #{appointment_id} deleted successfully.', 'success')
    return redirect(url_for('admin.manage_appointments'))