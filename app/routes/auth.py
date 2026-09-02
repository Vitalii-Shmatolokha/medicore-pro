from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.models import User
from app import db
import re

bp = Blueprint('auth', __name__)

@bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'doctor':
            return redirect(url_for('doctor.dashboard'))
        else:
            return redirect(url_for('patient.dashboard'))
    return render_template('index.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            flash('Authenticated successfully.', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'doctor':
                return redirect(url_for('doctor.dashboard'))
            else:
                return redirect(url_for('patient.dashboard'))
        else:
            flash('Invalid email address or password. Please verify your credentials.', 'danger')
    
    return render_template('auth/login.html', unread_messages=g.unread_messages)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    form_data = {'name': '', 'email': ''}
    if request.method == 'POST':
        form_data['name'] = request.form.get('name', '').strip()
        form_data['email'] = request.form.get('email', '').strip().lower()
        password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''
        terms = request.form.get('terms')

        errors = []
        
        if not form_data['name'] or len(form_data['name']) < 2 or len(form_data['name']) > 100 or not re.match(r'^[A-Za-z\s\.\-]+$', form_data['name']):
            errors.append('Full name must be 2-100 characters and contain standard alphabetic characters.')
        
        if not form_data['email'] or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', form_data['email']):
            errors.append('Please provide a valid institutional or personal email address.')
        
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        elif password != confirm_password:
            errors.append('Passwords do not match.')
        
        if not terms:
            errors.append('You must review and accept the HIPAA & GDPR Data Agreement to proceed.')

        if User.query.filter_by(email=form_data['email']).first():
            errors.append('An account with this email address already exists.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html', unread_messages=g.unread_messages, form_data=form_data)

        try:
            hashed_password = generate_password_hash(password)
            new_user = User(
                email=form_data['email'],
                password=hashed_password,
                name=form_data['name'],
                role='patient'
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            flash('Patient account registered successfully. Please sign in.', 'success')
            return redirect(url_for('auth.login'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Account registration failed: {str(e)}', 'danger')
            return render_template('auth/register.html', unread_messages=g.unread_messages, form_data=form_data)
    
    return render_template('auth/register.html', unread_messages=g.unread_messages, form_data=form_data)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Signed out of session.', 'info')
    return redirect(url_for('auth.index'))

@bp.route('/about')
def about():
    return render_template('about.html')

@bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        if name and email and message:
            flash('Inquiry submitted. A clinical support specialist will contact you within 2 business hours.', 'success')
            return redirect(url_for('auth.contact'))
        else:
            flash('Please complete all mandatory inquiry fields.', 'danger')
    
    return render_template('contact.html', unread_messages=g.unread_messages)

@bp.route('/terms')
def terms():
    return render_template('terms.html')

@bp.route('/privacy')
def privacy():
    return render_template('privacy.html')