import os
from flask import Flask, render_template

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

@app.route('/')
def index():
    """Render the main page of the BitLucky raffle site"""
    return render_template('index.html')

# Additional routes for placeholder pages
@app.route('/terms')
def terms():
    return render_template('index.html')  # Using same template as placeholder

@app.route('/privacy')
def privacy():
    return render_template('index.html')  # Using same template as placeholder

@app.route('/contact')
def contact():
    return render_template('index.html')  # Using same template as placeholder

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
