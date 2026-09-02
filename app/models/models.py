from app import db
from flask_login import UserMixin
from datetime import datetime, timezone
from sqlalchemy import Index

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(120), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, index=True)  # 'admin', 'doctor', 'patient'
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    specialty = db.Column(db.String(120), nullable=True, index=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    allergies = db.Column(db.String(255), nullable=True)
    family_doctor_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Relationships
    family_doctor = db.relationship('User', remote_side=[id], backref=db.backref('patients', lazy='dynamic'), foreign_keys=[family_doctor_id])
    appointments_as_doctor = db.relationship('Appointment', backref='doctor', 
                                            foreign_keys='Appointment.doctor_id', lazy='dynamic', cascade='all, delete-orphan')
    appointments_as_patient = db.relationship('Appointment', backref='patient', 
                                             foreign_keys='Appointment.patient_id', lazy='dynamic', cascade='all, delete-orphan')
    medical_records = db.relationship('MedicalRecord', backref='patient', lazy='dynamic', cascade='all, delete-orphan')
    prescriptions = db.relationship('Prescription', backref='patient', lazy='dynamic', cascade='all, delete-orphan')
    schedules = db.relationship('DoctorSchedule', backref='doctor', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'specialty': self.specialty,
            'family_doctor_id': self.family_doctor_id
        }

class Appointment(db.Model):
    __tablename__ = 'appointment'
    
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    status = db.Column(db.String(20), default='scheduled', nullable=False, index=True)  # scheduled, completed, cancelled
    is_online = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    medical_record = db.relationship('MedicalRecord', backref='appointment', uselist=False, lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        Index('idx_appointment_doctor_date', 'doctor_id', 'date'),
        Index('idx_appointment_patient_date', 'patient_id', 'date'),
        Index('idx_appointment_status_date', 'status', 'date'),
    )

class MedicalRecord(db.Model):
    __tablename__ = 'medical_record'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id', ondelete='SET NULL'), nullable=True, index=True)
    doctor_notes = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    prescriptions = db.relationship('Prescription', backref='medical_record', lazy='dynamic', cascade='all, delete-orphan')

class Prescription(db.Model):
    __tablename__ = 'prescription'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    medical_record_id = db.Column(db.Integer, db.ForeignKey('medical_record.id', ondelete='SET NULL'), nullable=True, index=True)
    medication_name = db.Column(db.String(150), nullable=False, index=True)
    dosage = db.Column(db.String(100), nullable=False)
    instructions = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    last_ordered = db.Column(db.DateTime(timezone=True), nullable=True)

class Message(db.Model):
    __tablename__ = 'message'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

    __table_args__ = (
        Index('idx_message_conversation', 'sender_id', 'receiver_id', 'created_at'),
        Index('idx_message_unread', 'receiver_id', 'is_read'),
    )

class Notification(db.Model):
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)

class DoctorSchedule(db.Model):
    __tablename__ = 'doctor_schedule'
    
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    start_time = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    end_time = db.Column(db.DateTime(timezone=True), nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        Index('idx_schedule_doctor_availability', 'doctor_id', 'start_time', 'is_available'),
    )

class HealthGuide(db.Model):
    __tablename__ = 'health_guide'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class PrescriptionRequest(db.Model):
    __tablename__ = 'prescription_request'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    medication_name = db.Column(db.String(150), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # pending, approved, rejected
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    patient = db.relationship('User', foreign_keys=[patient_id], backref='prescription_requests')
    doctor = db.relationship('User', foreign_keys=[doctor_id])

    __table_args__ = (
        Index('idx_presc_req_doctor_status', 'doctor_id', 'status'),
        Index('idx_presc_req_patient', 'patient_id', 'status'),
    )