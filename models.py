from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Create database instance
db = SQLAlchemy()

class Raffle(db.Model):
    """Model for keeping track of raffles"""
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    prize_amount = db.Column(db.Float, nullable=False)
    prize_currency = db.Column(db.String(10), default="BTC")
    is_active = db.Column(db.Boolean, default=True)
    winner_id = db.Column(db.String(64), nullable=True)  # Anonymous ID of winner

class FAQ(db.Model):
    """Model for FAQ entries"""
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, default=0)  # For ordering the FAQs