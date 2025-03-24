import os
from flask import Flask, render_template, request
from models import db, FAQ

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

@app.route('/')
def index():
    """Render the main page of the BitLucky raffle site"""
    return render_template('index.html')

@app.route('/faq')
def faq():
    """Render the FAQ page with frequently asked questions"""
    # Get all FAQ entries from the database, ordered by their position
    faqs = FAQ.query.order_by(FAQ.order).all()
    return render_template('faq.html', faqs=faqs)

@app.route('/about')
def about():
    """Render the About page with information about BitLucky"""
    return render_template('about.html')

# Additional routes for placeholder pages
@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# Admin route to insert initial FAQ data (normally would be protected)
@app.route('/init-faq', methods=['GET'])
def init_faq():
    """Initialize FAQ data"""
    # Only run if no FAQs exist yet
    if FAQ.query.count() == 0:
        faqs = [
            FAQ(
                question="Why did you create BitLucky?",
                answer="Because we believe everyone deserves a win. In a world where the odds are often stacked against the average person, BitLucky gives you a fair chance at financial freedom while preserving your privacy.",
                order=1
            ),
            FAQ(
                question="How does the raffle work?",
                answer="Every 30 days, we raffle off a Bitcoin wallet containing 0.1 BTC. Entry tickets can be purchased with Bitcoin or Monero for complete anonymity. The more entries you buy, the better your chances of winning!",
                order=2
            ),
            FAQ(
                question="Is BitLucky anonymous?",
                answer="Absolutely! We never collect any personal information. All transactions are done through cryptocurrency, and winners are identified only by their wallet address. Your privacy is our top priority.",
                order=3
            ),
            FAQ(
                question="How do I know the raffle is fair?",
                answer="We use a provably fair algorithm that can be independently verified. The winning selection process is transparent and tamper-proof, ensuring every entry has an equal chance based on the number of tickets purchased.",
                order=4
            ),
            FAQ(
                question="What happens when I win?",
                answer="When you win, the entire wallet containing 0.1 BTC is transferred to you automatically. No claims to file, no forms to fill out - just instant cryptocurrency in your possession.",
                order=5
            )
        ]
        for faq_item in faqs:
            db.session.add(faq_item)
        db.session.commit()
        return "FAQ data initialized successfully!"
    return "FAQ data already exists!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
