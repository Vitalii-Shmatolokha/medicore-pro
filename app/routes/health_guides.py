# app/routes/health_guides.py
from flask import Blueprint, render_template, request
from app.models.models import HealthGuide
from app import db

bp = Blueprint('health_guides', __name__)

@bp.route('/health_guides')
def health_guides():
    from flask import g
    search_query = request.args.get('q', '')
    
    if search_query:
        guides = HealthGuide.query.filter(
            db.or_(
                HealthGuide.title.ilike(f'%{search_query}%'),
                HealthGuide.description.ilike(f'%{search_query}%'),
                HealthGuide.content.ilike(f'%{search_query}%')
            )
        ).all()
    else:
        guides = HealthGuide.query.all()
    
    return render_template('health_guides.html', 
                         guides=guides, 
                         search_query=search_query, 
                         unread_messages=g.unread_messages)