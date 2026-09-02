<div align="center">

# MediCore Pro
### Enterprise Clinical Management & Telemedicine Platform

[![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3%2B-black?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://supabase.com)
[![WebRTC](https://img.shields.io/badge/WebRTC-Telemedicine-333333?style=for-the-badge&logo=webrtc&logoColor=white)](https://webrtc.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![Docker](https://img.shields.io/badge/Docker-Production_Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](LICENSE)

<p align="center">
  <b>A comprehensive, high-density clinical operating system designed for primary care practices, real-time telemedicine consultations, longitudinal electronic health records (EHR), and automated prescription authorisations.</b>
</p>

*Final-Year University Diploma Project by **Vitalii Shmatolokha** • Vasyl Stefanyk Precarpathian National University*

---

</div>

## 📌 Executive Summary

**MediCore Pro** is a modern, full-stack healthcare workflow platform built to eliminate administrative latency in general practice surgeries and outpatient clinics. Developed to adhere to strict UK National Health Service (NHS) conventions, British English localization, and UK GDPR data privacy standards, it delivers a unified clinical experience across patients, attending physicians, and practice administrators.

The platform replaces legacy monolithic clinic portals with high-density data views, fluid Apple-inspired tactile micro-interactions (`spring-action`), dark mode support, encrypted real-time WebSocket messaging, in-browser WebRTC video consultations, and automated pharmaceutical prescribing workflows.

---

## 🚀 Key Functional Modules

### 👨‍⚕️ 1. Physician Clinical Portal
* **Worklist & Patient Register**: Instant searchable registry of assigned patients with allergy badges, date of birth, and encounter history.
* **Longitudinal EHR Encounter Charting**: Record clinical diagnoses, examination notes, and contemporaneous observations during consultations.
* **Pharmaceutical E-Prescriptions**: Direct prescription issuance with dosage regimens, administration instructions, and repeat refill approval queue.
* **FullCalendar Availability Engine**: Drag-and-drop interactive shift calendar with automated bulk slot generator (configurable slot duration: 15/30/60 mins, working hours, and weekend exclusion).

### 🧑‍💼 2. Patient Healthcare Portal
* **General Practice Directory**: Search and filter certified doctors and consultants by clinical specialty (General Practice, Cardiology, Oncology, Pediatrics, etc.).
* **Smart Appointment Booking**: Real-time slot booking with instant availability verification and toggle for in-surgery or encrypted telemedicine visits.
* **Longitudinal Health Records**: Self-service access to past encounter summaries, doctor notes, and active medication history.
* **Direct Real-Time Consultation Chat**: Low-latency 1-on-1 messaging with attending medical practitioners powered by Flask-SocketIO.

### 🛡️ 3. Clinical Governance & Administration Suite
* **Master Consultation Registry (`/admin/manage_appointments`)**: Practice-wide audit trail with multivariate filtering (by doctor, patient, status, consultation channel, and keyword search).
* **Practitioner & Patient Lifecycle**: Add, edit, schedule, or deactivate licensed practitioners and enrolled patient records.
* **Clinical PDF Dossier Export**: Generate publication-grade A4 medical record summaries on-the-fly using **ReportLab**.
* **Audit CSV Export**: One-click streaming CSV export for practice compliance and appointment audit logs.

### 📹 4. WebRTC Telemedicine Studio
* **Encrypted Audiovisual Consultations**: Peer-to-peer browser video stream with Google STUN failover signaling.
* **Mobile Picture-in-Picture (PiP)**: Self-view camera stream seamlessly scales and positions on small viewports without obscuring the physician.
* **Floating Glassmorphic Control Pill**: Tactile toggles for audio mute, camera toggle, screen sharing, and call termination.

---

## 🏗️ Architecture & Technology Stack

| Domain | Technology | Description |
| :--- | :--- | :--- |
| **Backend Core** | **Python 3.11+ / Flask 2.3** | Modular application factory pattern with blueprinted route isolation. |
| **Database & ORM** | **PostgreSQL (Supabase) / SQLAlchemy 2.0** | Relational integrity, foreign key cascades, connection pooling (`QueuePool`). Fallback to SQLite for local development. |
| **Real-Time Layer** | **Flask-SocketIO / Eventlet** | High-concurrency asynchronous coroutines for messaging and call signaling. |
| **Video Telehealth** | **WebRTC / PeerJS** | Peer-to-peer encrypted media streams with STUN negotiation. |
| **Document Generation** | **ReportLab** | High-performance programmatic A4 medical records PDF generation. |
| **Design System** | **Tailwind CSS / Lucide Icons** | Custom clinical UI with typography hierarchy (Inter & Plus Jakarta Sans), dark mode, and tactile spring physics. |
| **Production Server** | **Gunicorn (Eventlet Worker)** | Production WSGI server binding with coroutine-based request scheduling. |
| **Containerization** | **Docker (Multi-Stage)** | Hardened `python:3.11-slim` image running under an unprivileged `medicore` system user. |

---

## 📂 Repository Structure

```
medicore-pro/
├── app/
│   ├── __init__.py            # Flask app factory, extension init, CLI commands
│   ├── models/
│   │   └── models.py          # SQLAlchemy models (User, Appointment, MedicalRecord, Prescription)
│   ├── routes/
│   │   ├── admin.py           # Practice administration & consultation registry
│   │   ├── auth.py            # Authentication, registration & legal terms
│   │   ├── chat.py            # Real-time WebSocket messaging
│   │   ├── doctor.py          # Physician dashboard, EHR charting & availability
│   │   ├── patient.py         # Patient portal, specialist booking & health records
│   │   ├── video.py           # WebRTC Telemedicine signaling
│   │   └── health_guides.py   # Clinical guidance and articles
│   ├── services/
│   │   └── schedule_service.py # Automated doctor shift & slot generation
│   ├── static/                # Compiled static assets & client logic
│   └── templates/             # Jinja2 HTML templates (Tailwind CSS)
├── .env.example               # Environment variables template
├── .gitignore                 # Strict production security rules
├── Dockerfile                 # Hardened multi-stage Docker build
├── gunicorn.conf.py           # Production Gunicorn configuration (Eventlet)
├── render.yaml                # Infrastructure-as-Code for 1-click cloud deployment
├── requirements.txt           # Pinned production Python dependencies
├── run.py                     # Application entrypoint
└── README.md                  # Project documentation
```

---

## ⚡ Quick Start & Local Setup

### Prerequisites
* Python 3.11 or higher
* Git

### 1. Clone the Repository
```bash
git clone https://github.com/Vitalii-Shmatolokha/medicore-pro.git
cd medicore-pro
```

### 2. Create and Activate Virtual Environment
```bash
# macOS/Linux:
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell):
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory by copying the template:
```bash
cp .env.example .env
```
*(For local development, leaving `DATABASE_URL` empty will automatically fall back to an internal SQLite database in `instance/healthcare.db`).*

### 5. Initialize & Seed Database
Run the custom CLI command to generate schema and populate realistic UK NHS practice fixtures:
```bash
flask --app run.py init-db
```

### 6. Start the Development Server
```bash
python run.py
```
Open your browser and navigate to: **`http://127.0.0.1:5000`**

---

## 🔐 Default Demo Accounts

The database seed command generates the following pre-configured credentials for evaluation:

| Role | Name | Email Address | Password | Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **Administrator** | Vitalii Shmatolokha | `admin@healthcare.co.uk` | `admin123` | Full clinical audit, practitioner credentials, consultation registry. |
| **Primary Care GP** | Dr. James Smith | `doctor@healthcare.co.uk` | `doctor123` | Patient register, EHR encounter charts, prescription refills, schedule manager. |
| **Cardiologist** | Dr. Eleanor Davies | `eleanor.davies@healthcare.co.uk` | `doctor123` | Consultant clinic worklist, specialty appointments. |
| **Enrolled Patient** | Vitalii Shmatolokha | `patient@healthcare.co.uk` | `patient123` | Specialist booking, personal EHR records, e-prescriptions, direct chat. |

---

## 🐳 Docker Deployment

To build and run the production-grade multi-stage container locally:

```bash
# 1. Build the Docker image
docker build -t medicore-pro:latest .

# 2. Run container on port 8000
docker run -d -p 8000:8000 \
  -e SECRET_KEY="your-production-secret-key" \
  -e FLASK_ENV="production" \
  --name medicore-app medicore-pro:latest

# 3. Access application
http://localhost:8000
```

---

## ☁️ Cloud Deployment (Render / Railway)

This repository is pre-configured with **Infrastructure-as-Code** ([`render.yaml`](render.yaml)):

1. Fork or push this repository to your GitHub account.
2. Sign in to [Render.com](https://render.com) and click **New +** → **Blueprint**.
3. Connect your `medicore-pro` repository.
4. Render will automatically provision:
   * A managed **PostgreSQL** database (`medicore-db`).
   * A containerized **Web Service** running Gunicorn + Eventlet on HTTPS.
5. In the Render Web Shell, run:
   ```bash
   flask --app run.py init-db
   ```

---

## 🛡️ Security & Privacy Compliance

* **UK GDPR & NHS Standards**: Patient records are isolated, immutable identifiers prevent account hijacking, and data minimization is strictly applied.
* **Authentication Security**: Password hashing via PBKDF2:SHA256 (`werkzeug.security`).
* **Session Protection**: `HttpOnly`, `SameSite=Lax`, and automated `Secure` cookies when running over HTTPS in production.
* **Least Privilege Container**: Docker runtime drops root privileges to an isolated system account (`USER medicore`).

---

## 📜 License & Academic Attribution

This project is submitted as a **Final-Year University Diploma Project** at:  
**Vasyl Stefanyk Precarpathian National University**

* **Author:** Vitalii Shmatolokha
* **GitHub:** [@Vitalii-Shmatolokha](https://github.com/Vitalii-Shmatolokha)
* **License:** Released under the [MIT License](LICENSE).