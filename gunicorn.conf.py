import os

# Gunicorn Production Server Configuration for Eventlet & WebSockets
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Use eventlet worker class for high-concurrency WebSocket & WebRTC signaling
worker_class = "eventlet"
workers = int(os.environ.get('WEB_CONCURRENCY', 1))  # 1 eventlet worker with coroutines for in-memory socket synchronization
worker_connections = 1000

# Timeouts & Keepalive
timeout = 120
keepalive = 5
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get('LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process Management
preload_app = False  # Avoid monkey patching issues with eventlet in preload
daemon = False
