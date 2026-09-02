import os
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, g, session, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from flask_migrate import Migrate
from config import Config

# Configure application logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Extensions
db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions with app instance
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to access this clinical service.'
    login_manager.login_message_category = 'info'

    # Initialize SocketIO with eventlet and configured CORS origins
    socketio.init_app(
        app,
        cors_allowed_origins=app.config.get('CORS_ALLOWED_ORIGINS', '*'),
        async_mode='eventlet',
        logger=False,
        engineio_logger=False
    )
    
    migrate.init_app(app, db)

    logger.info("Flask extensions initialized successfully")

    # Security Headers for production compliance
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    # Jinja2 filter for British (UK) datetime formatting (DD/MM/YYYY, HH:MM)
    @app.template_filter('datetimeformat')
    def datetimeformat(value, format='%d/%m/%Y at %H:%M GMT'):
        if value == 'now':
            return datetime.now(timezone.utc).strftime(format)
        if isinstance(value, datetime):
            return value.strftime(format)
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').strftime(format)
        except (ValueError, TypeError):
            return str(value)

    # Jinja2 filter to ensure offset-aware datetimes
    def to_utc(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=ZoneInfo('UTC'))
        return dt.astimezone(ZoneInfo('UTC')) if dt else dt
    app.jinja_env.filters['to_utc'] = to_utc

    # Jinja2 filter for strftime (24-hour time)
    def strftime(dt, format='%H:%M'):
        if dt is None:
            return ''
        try:
            return dt.strftime(format)
        except AttributeError:
            return ''
    app.jinja_env.filters['strftime'] = strftime

    # Jinja2 filter to truncate to midnight
    @app.template_filter('date_truncate')
    def date_truncate(dt):
        if dt is None:
            return None
        return dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)

    # Register blueprints
    try:
        from app.routes import auth, patient, doctor, admin, chat, video, health_guides
        app.register_blueprint(auth.bp)
        app.register_blueprint(patient.bp)
        app.register_blueprint(doctor.bp)
        app.register_blueprint(admin.bp)
        app.register_blueprint(chat.chat_bp)
        app.register_blueprint(video.bp)
        app.register_blueprint(health_guides.bp)
        
        # Register SocketIO event handlers
        chat.register_chat_socket_events()
        video.register_video_socket_events()
        
        logger.info("Blueprints and real-time event handlers registered successfully")
    except ImportError as e:
        logger.error(f"Failed to import routes: {str(e)}")
        raise

    # Import models
    from app.models.models import User, Message, Appointment, PrescriptionRequest, DoctorSchedule, MedicalRecord, Prescription, HealthGuide

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except Exception as e:
            logger.error(f"Error loading user ID {user_id}: {str(e)}")
            return None

    @app.before_request
    def load_unread_messages():
        g.unread_messages = 0
        if current_user.is_authenticated:
            try:
                g.unread_messages = Message.query.filter_by(
                    receiver_id=current_user.id,
                    is_read=False
                ).count()
            except Exception as e:
                logger.error(f"Error loading unread messages for user {current_user.id}: {str(e)}")
                g.unread_messages = 0

    # CLI command for database initialization and seeding (Strict UK / Personalized)
    @app.cli.command('init-db')
    def init_db_command():
        from werkzeug.security import generate_password_hash
        from app.services.schedule_service import generate_doctor_schedules
        with app.app_context():
            try:
                db.drop_all()
                db.create_all()
                logger.info("Database schema initialized.")

                # Admin Account: Vitalii Shmatolokha
                admin = User(
                    email='admin@healthcare.co.uk',
                    password=generate_password_hash('admin123'),
                    name='Vitalii Shmatolokha',
                    role='admin'
                )
                db.session.add(admin)

                # Primary Patient Account: Vitalii Shmatolokha
                patient = User(
                    email='patient@healthcare.co.uk',
                    password=generate_password_hash('patient123'),
                    name='Vitalii Shmatolokha',
                    role='patient',
                    family_doctor_id=2
                )
                db.session.add(patient)

                # Doctor 1: Dr. James Smith (Lead GP)
                doctor1 = User(
                    email='doctor@healthcare.co.uk',
                    password=generate_password_hash('doctor123'),
                    name='Dr. James Smith',
                    role='doctor',
                    specialty='General Practice (GP)'
                )
                db.session.add(doctor1)

                # Doctor 2: Dr. Eleanor Davies (Cardiologist)
                doctor2 = User(
                    email='cardiologist@healthcare.co.uk',
                    password=generate_password_hash('doctor123'),
                    name='Dr. Eleanor Davies',
                    role='doctor',
                    specialty='Cardiology'
                )
                db.session.add(doctor2)

                # Doctor 3: Dr. Alistair Finch (Clinical Oncology)
                doctor3 = User(
                    email='oncologist@healthcare.co.uk',
                    password=generate_password_hash('doctor123'),
                    name='Dr. Alistair Finch',
                    role='doctor',
                    specialty='Clinical Oncology'
                )
                db.session.add(doctor3)
                db.session.commit()

                # Seed Appointments
                appointments = [
                    Appointment(
                        patient_id=patient.id,
                        doctor_id=doctor1.id,
                        date=datetime.now(timezone.utc) - timedelta(days=2),
                        status='completed',
                        is_online=True,
                        created_at=datetime.now(timezone.utc) - timedelta(days=2)
                    ),
                    Appointment(
                        patient_id=patient.id,
                        doctor_id=doctor2.id,
                        date=datetime.now(timezone.utc) - timedelta(days=1),
                        status='completed',
                        is_online=False,
                        created_at=datetime.now(timezone.utc) - timedelta(days=1)
                    ),
                    Appointment(
                        patient_id=patient.id,
                        doctor_id=doctor1.id,
                        date=datetime.now(timezone.utc) + timedelta(hours=3),
                        status='scheduled',
                        is_online=True,
                        created_at=datetime.now(timezone.utc)
                    )
                ]
                db.session.add_all(appointments)
                db.session.commit()

                # Seed UK Medical Records
                medical_records = [
                    MedicalRecord(
                        patient_id=patient.id,
                        appointment_id=appointments[0].id,
                        doctor_notes="Patient presents with acute upper respiratory tract symptoms. Lungs clear on auscultation. Advised rest, oral fluids, and paracetamol.",
                        diagnosis='Acute Upper Respiratory Tract Infection (URTI)',
                        created_at=datetime.now(timezone.utc) - timedelta(days=2)
                    ),
                    MedicalRecord(
                        patient_id=patient.id,
                        appointment_id=appointments[1].id,
                        doctor_notes="Routine cardiovascular assessment and blood pressure review. Blood pressure 124/82 mmHg. Resting ECG normal sinus rhythm.",
                        diagnosis='Essential Hypertension — Routine Review',
                        created_at=datetime.now(timezone.utc) - timedelta(days=1)
                    )
                ]
                db.session.add_all(medical_records)
                db.session.commit()

                # Seed UK Prescriptions (BNF Standards & £ Currency)
                prescriptions = [
                    Prescription(
                        patient_id=patient.id,
                        medical_record_id=medical_records[0].id,
                        medication_name='Paracetamol 500mg tablets',
                        dosage='1000 mg (2 tablets) four times daily as required (max 4g/24h)',
                        instructions='Take orally with a glass of water. Standard NHS prescription charge: £9.90.',
                        is_active=True,
                        created_at=datetime.now(timezone.utc) - timedelta(days=2)
                    ),
                    Prescription(
                        patient_id=patient.id,
                        medical_record_id=medical_records[1].id,
                        medication_name='Amlodipine 5mg tablets',
                        dosage='5 mg once daily in the morning',
                        instructions='Continuous maintenance therapy for blood pressure regulation.',
                        is_active=True,
                        created_at=datetime.now(timezone.utc) - timedelta(days=1)
                    )
                ]
                db.session.add_all(prescriptions)

                # Seed Prescription Refill Request
                prescription_request = PrescriptionRequest(
                    patient_id=patient.id,
                    doctor_id=doctor1.id,
                    medication_name='Salbutamol 100mcg inhaler (CFC-free)',
                    reason='Repeat prescription request for seasonal exercise-induced bronchospasm',
                    status='pending',
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(prescription_request)

                # Seed Clinical Health Guides
                sample_guides = [
                    HealthGuide(
                        title='Managing Blood Pressure: NHS Clinical Guidance',
                        description='Evidence-based lifestyle interventions and blood pressure monitoring in primary care.',
                        content='Maintaining blood pressure within healthy parameters (below 130/80 mmHg in clinic) requires balanced salt intake (<6g daily), 150 minutes of moderate aerobic exercise weekly, and regular ambulatory blood pressure monitoring.'
                    ),
                    HealthGuide(
                        title='Respiratory Tract Infections: Symptom Self-Management',
                        description='Guidance on managing common viral colds, influenza, and when to seek urgent GP consultation.',
                        content='Adequate hydration, warm fluids, antipyretic analgesia (paracetamol or ibuprofen), and recognizing red-flag symptoms such as breathlessness, haemoptysis, or chest pain.'
                    ),
                    HealthGuide(
                        title='Cardiovascular Health & Lipid Profile Interpretation',
                        description='Understanding QRISK3 scores, cholesterol ratios, and cardiovascular risk reduction.',
                        content='Maintaining optimal non-HDL cholesterol levels, adopting a Mediterranean-style dietary programme, and attending regular NHS Health Checks.'
                    )
                ]
                db.session.add_all(sample_guides)

                # Seed Direct Messages
                messages = [
                    Message(
                        sender_id=patient.id,
                        receiver_id=doctor1.id,
                        content='Good morning Dr. Smith, I have submitted a repeat prescription request for my inhaler.',
                        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
                        is_read=True
                    ),
                    Message(
                        sender_id=doctor1.id,
                        receiver_id=patient.id,
                        content='Good morning Vitalii. I have reviewed your request and authorised the repeat prescription. It has been routed to your designated pharmacy.',
                        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
                        is_read=False
                    )
                ]
                db.session.add_all(messages)
                db.session.commit()

                # Generate doctor availability slots
                start_date = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                generate_doctor_schedules(
                    doctor_id=doctor1.id,
                    start_date=start_date,
                    days=7,
                    start_hour=9,
                    end_hour=17,
                    slot_duration=30,
                    skip_weekends=True,
                    delete_existing=False
                )
                generate_doctor_schedules(
                    doctor_id=doctor2.id,
                    start_date=start_date,
                    days=7,
                    start_hour=10,
                    end_hour=18,
                    slot_duration=30,
                    skip_weekends=True,
                    delete_existing=False
                )
                generate_doctor_schedules(
                    doctor_id=doctor3.id,
                    start_date=start_date,
                    days=7,
                    start_hour=9,
                    end_hour=16,
                    slot_duration=30,
                    skip_weekends=True,
                    delete_existing=False
                )

                print('Database initialised and seeded with UK clinical fixtures and personalized accounts!')
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to initialise database: {str(e)}", exc_info=True)
                print(f"Error initialising database: {str(e)}")

    return app