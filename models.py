from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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

class Admin(db.Model):
    """Model for admin users"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Package(db.Model):
    """Model for raffle entry packages"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    price = db.Column(db.Float, nullable=False)
    entries = db.Column(db.Integer, nullable=False)  # Number of raffle entries
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship to entries
    entries_purchased = db.relationship('Entry', backref='package', lazy=True)
    
class Entry(db.Model):
    """Model for raffle entry purchases"""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    btc_wallet = db.Column(db.String(120), nullable=False)  # User's Bitcoin wallet for prize
    txid = db.Column(db.String(120), nullable=False)  # Bitcoin transaction ID
    btc_amount = db.Column(db.Float, nullable=False)  # BTC amount paid
    usd_amount = db.Column(db.Float, nullable=False)  # USD equivalent at time of purchase
    btc_price = db.Column(db.Float, nullable=False)  # BTC price at time of purchase
    
    # Verification status
    is_verified = db.Column(db.Boolean, default=False)  # Admin verified the transaction
    verification_notes = db.Column(db.Text, nullable=True)  # Admin notes on verification
    
    # Purchase timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to package
    package_id = db.Column(db.Integer, db.ForeignKey('package.id'), nullable=False)
    
    # Number of entries this purchase represents
    entry_count = db.Column(db.Integer, nullable=False, default=1)
    
class Testimonial(db.Model):
    """Model for winner testimonials shown in the Winners Circle"""
    id = db.Column(db.Integer, primary_key=True)
    winner_id = db.Column(db.String(64), nullable=False)  # Anonymous ID like "R74c9zKX"
    testimonial_text = db.Column(db.Text, nullable=False)  # The winner's testimonial
    order = db.Column(db.Integer, default=0)  # For ordering the testimonials
    is_active = db.Column(db.Boolean, default=True)  # To enable/disable testimonials
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SiteContent(db.Model):
    """Model for editable site content"""
    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(64), nullable=False)  # e.g. 'hero', 'footer', etc.
    key = db.Column(db.String(64), nullable=False)  # e.g. 'title', 'subtitle', etc.
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)  # For admin UI