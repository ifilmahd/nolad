import os
import logging
from flask import Flask
from models import db
from app import app

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Configure the SQLAlchemy part of the app to use SQLite
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bitlucky.db"
# No need for pool options with SQLite
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the SQLAlchemy extension
db.init_app(app)

# Create all database tables
with app.app_context():
    db.create_all()
    
    # Import initialization routes
    from app import init_admin, init_faq, init_packages
    
    # Initialize admin user if none exists
    init_admin()
    
    # Initialize FAQ data if none exists
    init_faq()
    
    # Initialize package data if none exists
    init_packages()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
