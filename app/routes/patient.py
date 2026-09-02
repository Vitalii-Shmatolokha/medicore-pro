from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from app.models.models import Appointment, DoctorSchedule, MedicalRecord, Prescription, Notification, User, Message, PrescriptionRequest
from app.services.schedule_service import generate_doctor_schedules
from datetime import datetime, timezone, timedelta
from app import db
from werkzeug.security import generate_password_hash
import pdfkit
import os
import pytz
import logging
from sqlalchemy.exc import SQLAlchemyError
import subprocess
import tempfile

bp = Blueprint('patient', __name__, url_prefix='/patient')

# Setup logging
logger = logging.getLogger(__name__)

@bp.route('/dashboard')
@login_required
def dashboard():
    from flask import g
    if current_user.role != 'patient':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    logger.debug(f"Loading dashboard for patient ID {current_user.id}, email {current_user.email}")
    try:
        appointments = Appointment.query.filter(
            Appointment.patient_id == current_user.id,
            Appointment.status == 'scheduled',
            Appointment.date >= datetime.now(timezone.utc)
        ).order_by(Appointment.date).all()
        
        notifications = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).order_by(Notification.created_at.desc()).all()
        
        doctors = []
        if current_user.family_doctor_id:
            family_doctor = db.session.get(User, current_user.family_doctor_id)
            if family_doctor and family_doctor.role == 'doctor':
                doctors.append(family_doctor)
        
        appointment_doctors = User.query.join(Appointment, Appointment.doctor_id == User.id).filter(
            Appointment.patient_id == current_user.id,
            User.role == 'doctor'
        ).distinct().all()
        doctors.extend(appointment_doctors)
        
        message_doctors = User.query.join(Message, Message.sender_id == User.id).filter(
            Message.receiver_id == current_user.id,
            User.role == 'doctor'
        ).distinct().all()
        doctors.extend(message_doctors)
        
        message_doctors_sent = User.query.join(Message, Message.receiver_id == User.id).filter(
            Message.sender_id == current_user.id,
            User.role == 'doctor'
        ).distinct().all()
        doctors.extend(message_doctors_sent)
        
        doctors = list({d.id: d for d in doctors}.values())
        
        doctor_unread_counts = {}
        for doctor in doctors:
            unread_count = Message.query.filter_by(
                receiver_id=current_user.id,
                sender_id=doctor.id,
                is_read=False
            ).count()
            doctor_unread_counts[doctor.id] = unread_count
        
        return render_template('patient/dashboard.html',
                             appointments=appointments,
                             notifications=notifications,
                             doctors=doctors,
                             doctor_unread_counts=doctor_unread_counts,
                             unread_messages=g.unread_messages)
    except SQLAlchemyError as e:
        logger.error(f"Database error in dashboard for user {current_user.id}: {str(e)}", exc_info=True)
        flash('Error loading dashboard. Please try again.', 'danger')
        return redirect(url_for('auth.index'))

@bp.route('/doctors')
@bp.route('/view_doctors')
@login_required
def view_doctors():
    from flask import g
    if current_user.role != 'patient':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    try:
        specialty = request.args.get('specialty', '')
        
        if specialty:
            doctors = User.query.filter_by(role='doctor', specialty=specialty).all()
        else:
            doctors = User.query.filter_by(role='doctor').all()
        
        specialties = db.session.query(User.specialty).filter_by(role='doctor').distinct()
        now = datetime.now(timezone.utc)
        
        return render_template('patient/doctors.html',
                             doctors=doctors,
                             specialties=specialties,
                             now=now,
                             unread_messages=g.unread_messages)
    except SQLAlchemyError as e:
        logger.error(f"Database error in view_doctors: {str(e)}", exc_info=True)
        flash('Error loading doctors. Please try again.', 'danger')
        return redirect(url_for('patient.dashboard'))

@bp.route('/appointment/<int:appointment_id>')
@login_required
def appointment_details(appointment_id):
    from flask import g
    if current_user.role != 'patient':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    try:
        appointment = Appointment.query.get_or_404(appointment_id)
        
        if appointment.patient_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('patient.dashboard'))
        
        return render_template('patient/appointment.html',
                             appointment=appointment,
                             unread_messages=g.unread_messages)
    except SQLAlchemyError as e:
        logger.error(f"Database error in appointment_details for ID {appointment_id}: {str(e)}", exc_info=True)
        flash('Error loading appointment details. Please try again.', 'danger')
        return redirect(url_for('patient.dashboard'))

@bp.route('/book_appointment')
@login_required
def book_appointment_no_id():
    return redirect(url_for('patient.view_doctors'))

@bp.route('/book_appointment/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def book_appointment(doctor_id):
    from flask import g
    if current_user.role != 'patient':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    try:
        doctor = User.query.get_or_404(doctor_id)
        
        if doctor.role != 'doctor':
            flash('User is not a doctor.', 'danger')
            return redirect(url_for('patient.view_doctors'))
        
        if request.method == 'POST':
            schedule_id = request.form.get('schedule_id')
            is_online = request.form.get('is_online') == 'on'
            
            schedule = DoctorSchedule.query.get_or_404(schedule_id)
            appointment_datetime = schedule.start_time
            
            existing_appointment = Appointment.query.filter(
                Appointment.doctor_id == doctor_id,
                Appointment.date == appointment_datetime,
                Appointment.status != 'cancelled'
            ).first()
            
            if existing_appointment:
                flash('This time slot is already booked.', 'danger')
                return redirect(url_for('patient.book_appointment', doctor_id=doctor_id))
            
            new_appointment = Appointment(
                doctor_id=doctor_id,
                patient_id=current_user.id,
                date=appointment_datetime,
                status='scheduled',
                is_online=is_online,
                created_at=datetime.now(timezone.utc)
            )
            
            schedule.is_available = False
            
            db.session.add(new_appointment)
            
            notification = Notification(
                user_id=doctor_id,
                content=f"New appointment booked by {current_user.name} on {appointment_datetime.strftime('%Y-%m-%d %H:%M')}.",
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(notification)
            
            db.session.commit()
            
            flash('Appointment booked successfully!', 'success')
            return redirect(url_for('patient.dashboard'))
        
        schedules = DoctorSchedule.query.filter(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.is_available == True,
            DoctorSchedule.start_time >= datetime.now(timezone.utc)
        ).order_by(DoctorSchedule.start_time).all()
        
        if not schedules:
            try:
                generate_doctor_schedules(
                    doctor_id=doctor_id,
                    start_date=(datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
                    days=7,
                    start_hour=9,
                    end_hour=17,
                    slot_duration=30,
                    skip_weekends=True,
                    delete_existing=False
                )
                schedules = DoctorSchedule.query.filter(
                    DoctorSchedule.doctor_id == doctor_id,
                    DoctorSchedule.is_available == True,
                    DoctorSchedule.start_time >= datetime.now(timezone.utc)
                ).order_by(DoctorSchedule.start_time).all()
                logger.debug(f"Schedules for doctor_id={doctor_id}: {[s.start_time.isoformat() for s in schedules]}")
            except Exception as e:
                logger.error(f"Error generating schedules for doctor_id={doctor_id}: {str(e)}", exc_info=True)
                flash(f'Error generating schedules: {str(e)}', 'danger')
        
        return render_template('patient/book_appointment.html',
                             doctor=doctor,
                             schedules=schedules,
                             unread_messages=g.unread_messages)
    except SQLAlchemyError as e:
        logger.error(f"Database error in book_appointment for doctor_id {doctor_id}: {str(e)}", exc_info=True)
        flash('Error booking appointment. Please try again.', 'danger')
        return redirect(url_for('patient.dashboard'))

@bp.route('/prescriptions')
@login_required
def prescriptions():
    from flask import g
    if current_user.role != 'patient':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        doctors = User.query.filter_by(role='doctor').all()
        pagination = Prescription.query.filter_by(patient_id=current_user.id)\
            .order_by(Prescription.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        return render_template('patient/prescriptions.html',
                             prescriptions=pagination.items,
                             doctors=doctors,
                             pagination=pagination,
                             unread_messages=g.unread_messages)
    except SQLAlchemyError as e:
        logger.error(f"Database error in prescriptions for user {current_user.id}: {str(e)}", exc_info=True)
        flash('Error loading prescriptions. Please try again.', 'danger')
        return redirect(url_for('patient.prescriptions'))

@bp.route('/request_prescription', methods=['GET', 'POST'])
@login_required
def request_prescription():
    from flask import g
    if current_user.role != 'patient':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    try:
        doctors = User.query.filter_by(role='doctor').all()
        
        if request.method == 'POST':
            doctor_id = request.form.get('doctor_id')
            medication_name = request.form.get('medication_name')
            reason = request.form.get('reason')
            
            if not (doctor_id and medication_name and reason):
                flash('All fields are required.', 'danger')
                return redirect(url_for('patient.prescriptions'))
            
            new_request = PrescriptionRequest(
                patient_id=current_user.id,
                doctor_id=doctor_id,
                medication_name=medication_name,
                reason=reason,
                status='pending',
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(new_request)
            
            notification = Notification(
                user_id=doctor_id,
                content=f"New prescription request from {current_user.name} for {medication_name}.",
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(notification)
            
            db.session.commit()
            
            flash('Prescription request submitted!', 'success')
            return redirect(url_for('patient.prescriptions'))
        
        return render_template('patient/request_prescription.html',
                             doctors=doctors,
                             unread_messages=g.unread_messages)
    except SQLAlchemyError as e:
        logger.error(f"Database error in request_prescription for user {current_user.id}: {str(e)}", exc_info=True)
        flash('Error submitting prescription request. Please try again.', 'danger')
        return redirect(url_for('patient.prescriptions'))

@bp.route('/reorder_prescription/<int:prescription_id>', methods=['POST'])
@login_required
def reorder_prescription(prescription_id):
    try:
        if current_user.role != 'patient':
            flash('Access denied.', 'danger')
            return redirect(url_for('patient.prescriptions'))
        
        prescription = Prescription.query.get_or_404(prescription_id)
        
        if prescription.patient_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('patient.prescriptions'))
        
        if not prescription.is_active:
            flash('This prescription is no longer active.', 'danger')
            return redirect(url_for('patient.prescriptions'))
        
        if prescription.last_ordered:
            last_ordered = prescription.last_ordered
            if last_ordered.tzinfo is None:
                last_ordered = pytz.utc.localize(last_ordered)
            days_since_last_order = (datetime.now(timezone.utc) - last_ordered).days
            if days_since_last_order < 30:
                flash(f'You can only reorder this prescription every 30 days. Wait {30 - days_since_last_order} days.', 'danger')
                return redirect(url_for('patient.prescriptions'))
        
        # Determine the doctor for the reorder request
        doctor_id = None
        if current_user.family_doctor_id:
            doctor_id = current_user.family_doctor_id
        else:
            # Fallback: Get doctor from the prescription's medical record
            if prescription.medical_record_id:
                medical_record = db.session.get(MedicalRecord, prescription.medical_record_id)
                if medical_record and medical_record.appointment:
                    doctor_id = medical_record.appointment.doctor_id
        
        if not doctor_id:
            flash('No doctor available to handle this reorder request.', 'danger')
            return redirect(url_for('patient.prescriptions'))
        
        # Create a new PrescriptionRequest
        new_request = PrescriptionRequest(
            patient_id=current_user.id,
            doctor_id=doctor_id,
            medication_name=prescription.medication_name,
            reason=f"Reorder request for existing prescription (ID: {prescription.id})",
            status='pending',
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(new_request)
        
        # Send notification to the doctor
        notification = Notification(
            user_id=doctor_id,
            content=f"New prescription reorder request from {current_user.name} for {prescription.medication_name}.",
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(notification)
        
        # Update the last_ordered timestamp
        prescription.last_ordered = datetime.now(timezone.utc)
        
        db.session.commit()
        
        flash('Prescription reordered successfully! A request has been sent to your doctor.', 'success')
        return redirect(url_for('patient.prescriptions'))
    except SQLAlchemyError as e:
        logger.error(f"Database error in reorder_prescription for ID {prescription_id}: {str(e)}", exc_info=True)
        flash('Error reordering prescription. Please try again.', 'danger')
        return redirect(url_for('patient.prescriptions'))

@bp.route('/download_prescription/<int:prescription_id>')
@login_required
def download_prescription(prescription_id):
    from flask import g
    if current_user.role != 'patient':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    logger.debug(f"Fetching prescription ID {prescription_id} for user {current_user.id}")
    try:
        # Fetch prescription
        prescription = db.session.execute(
            db.select(Prescription).filter_by(id=prescription_id)
        ).scalar_one_or_none()
        if not prescription:
            logger.warning(f"Prescription ID {prescription_id} not found")
            flash('Prescription not found.', 'danger')
            return redirect(url_for('patient.prescriptions'))
        
        if prescription.patient_id != current_user.id:
            logger.warning(f"Unauthorized access to prescription ID {prescription_id} by user {current_user.id}")
            flash('Unauthorized access.', 'danger')
            return redirect(url_for('patient.prescriptions'))
        
        # Fetch related data
        patient = db.session.execute(
            db.select(User).filter_by(id=prescription.patient_id)
        ).scalar_one_or_none() or current_user
        
        medical_record = None
        if prescription.medical_record_id:
            medical_record = db.session.execute(
                db.select(MedicalRecord).filter_by(id=prescription.medical_record_id)
            ).scalar_one_or_none()
        
        appointment = None
        if medical_record and medical_record.appointment_id:
            appointment = db.session.execute(
                db.select(Appointment).filter_by(id=medical_record.appointment_id)
            ).scalar_one_or_none()
        
        doctor = None
        if appointment and appointment.doctor_id:
            doctor = db.session.execute(
                db.select(User).filter_by(id=appointment.doctor_id)
            ).scalar_one_or_none()
        if not doctor:
            doctor = db.session.execute(
                db.select(User).filter_by(role='doctor').limit(1)
            ).scalar_one_or_none()
        
        # Prepare template data
        template_data = {
            'patient_name': patient.name or 'Unknown Patient',
            'patient_email': patient.email or 'N/A',
            'doctor_name': doctor.name if doctor else 'Unknown Doctor',
            'doctor_specialty': doctor.specialty if doctor else 'Not specified',
            'medication_name': prescription.medication_name or 'N/A',
            'dosage': prescription.dosage or 'N/A',
            'instructions': prescription.instructions or 'N/A',
            'issue_date': prescription.created_at.strftime('%Y-%m-%d') if prescription.created_at else 'N/A',
            'diagnosis': medical_record.diagnosis if medical_record else 'Not specified',
            'discharge_date': (appointment.date.strftime('%Y-%m-%d') if appointment 
                            else prescription.created_at.strftime('%Y-%m-%d') if prescription.created_at 
                            else 'N/A'),
            'prescription_id': prescription.id,
            'current_date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'logo_path': os.path.abspath('app/static/images/hospital_logo.png')
        }

        
        logger.debug(f"Rendering template for prescription ID {prescription_id}")
        html = render_template('patient/discharge_summary.html', **template_data)
        
        # Save HTML for debugging
        with open(f'debug_prescription_{prescription_id}.html', 'w', encoding='utf-8') as f:
            f.write(html)
        
        # Configure wkhtmltopdf
        wkhtmltopdf_path = os.getenv('WKHTMLTOPDF_PATH', r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
        if not os.path.exists(wkhtmltopdf_path):
            logger.error(f"wkhtmltopdf not found at {wkhtmltopdf_path}")
            flash('PDF generation failed: wkhtmltopdf not found.', 'danger')
            return redirect(url_for('patient.prescriptions'))
        
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        options = {
            'enable-local-file-access': '',
            'quiet': '',
            'page-size': 'A4',
            'margin-top': '0.75in',
            'margin-right': '0.75in',
            'margin-bottom': '0.75in',
            'margin-left': '0.75in',
            'encoding': 'UTF-8',
            'no-outline': None
        }
        
        logger.debug(f"Generating PDF for prescription ID {prescription_id}")
        try:
            # Write HTML to a temporary file to avoid wkhtmltopdf input issues
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_html:
                temp_html.write(html)
                temp_html_path = temp_html.name
            
            # Generate PDF to a temporary file
            temp_pdf_path = tempfile.mktemp(suffix='.pdf')
            pdfkit.from_file(temp_html_path, temp_pdf_path, configuration=config, options=options)
            
            # Read PDF content
            with open(temp_pdf_path, 'rb') as f:
                pdf = f.read()
            
            logger.debug(f"PDF generated successfully for prescription ID {prescription_id}, size: {len(pdf)} bytes")
            
            # Clean up temporary files
            os.unlink(temp_html_path)
            os.unlink(temp_pdf_path)
            
        except Exception as e:
            logger.error(f"PDF generation failed for prescription ID {prescription_id}: {str(e)}", exc_info=True)
            flash(f'Error generating PDF: {str(e)}', 'danger')
            return redirect(url_for('patient.prescriptions'))
        
        headers = {
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'attachment;filename=discharge_summary_{prescription.id}.pdf'
        }
        logger.debug(f"Returning PDF response for prescription ID {prescription_id}")
        return Response(pdf, headers=headers)
    
    except SQLAlchemyError as e:
        logger.error(f"Database error in download_prescription for ID {prescription_id}: {str(e)}", exc_info=True)
        flash('Database error occurred. Please try again.', 'danger')
        return redirect(url_for('patient.prescriptions'))
    except Exception as e:
        logger.error(f"Unexpected error in download_prescription for ID {prescription_id}: {str(e)}", exc_info=True)
        flash(f'An unexpected error occurred: {str(e)}', 'danger')
        return redirect(url_for('patient.prescriptions'))

@bp.route('/medical_records')
@login_required
def medical_records():
    from flask import g
    if current_user.role != 'patient':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    try:
        logger.debug(f"Fetching medical records for patient ID {current_user.id}, email {current_user.email}")
        records = MedicalRecord.query.filter_by(patient_id=current_user.id).order_by(MedicalRecord.created_at.desc()).all()
        logger.debug(f"Found {len(records)} medical records for patient ID {current_user.id}")
        if records:
            for record in records:
                logger.debug(f"Record ID {record.id}: patient_id={record.patient_id}, appointment_id={record.appointment_id}, diagnosis={record.diagnosis}")
        return render_template('patient/medical_records.html',
                             medical_records=records,
                             unread_messages=g.unread_messages)
    except SQLAlchemyError as e:
        logger.error(f"Database error in medical_records for user {current_user.id}: {str(e)}", exc_info=True)
        flash('Error loading medical records. Please try again.', 'danger')
        return redirect(url_for('patient.dashboard'))

@bp.route('/mark_notification/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification(notification_id):
    try:
        if current_user.role != 'patient':
            flash('Access denied.', 'danger')
            return redirect(url_for('patient.dashboard'))
        
        notification = Notification.query.get_or_404(notification_id)
        
        if notification.user_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('patient.dashboard'))
        
        notification.is_read = True
        db.session.commit()
        
        flash('Notification marked as read.', 'success')
        return redirect(url_for('patient.dashboard'))
    except SQLAlchemyError as e:
        logger.error(f"Database error in mark_notification for ID {notification_id}: {str(e)}", exc_info=True)
        flash('Error marking notification as read. Please try again.', 'danger')
        return redirect(url_for('patient.dashboard'))

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    from flask import g
    if current_user.role != 'patient':
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.index'))
    
    try:
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            date_of_birth = request.form.get('date_of_birth')
            allergies = request.form.get('allergies')
            password = request.form.get('password')
            
            # Validate email uniqueness
            if email != current_user.email:
                existing_user = User.query.filter_by(email=email).first()
                if existing_user:
                    flash('This email is already registered.', 'danger')
                    return redirect(url_for('patient.profile'))
            
            # Update fields
            current_user.name = name
            current_user.email = email
            if date_of_birth:
                try:
                    current_user.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').replace(tzinfo=timezone.utc)
                except ValueError:
                    flash('Invalid date of birth format.', 'danger')
                    return redirect(url_for('patient.profile'))
            else:
                current_user.date_of_birth = None
            current_user.allergies = allergies or None
            if password:
                current_user.password = generate_password_hash(password)
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('patient.profile'))
        
        return render_template('patient/profile.html',
                             user=current_user,
                             unread_messages=g.unread_messages)
    except SQLAlchemyError as e:
        logger.error(f"Database error in profile for user {current_user.id}: {str(e)}", exc_info=True)
        db.session.rollback()
        flash('Error updating profile. Please try again.', 'danger')
        return redirect(url_for('patient.profile'))