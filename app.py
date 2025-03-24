import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, FAQ, Admin, Package, SiteContent, Raffle
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Admin login required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Please log in to access this page.')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

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

# Package routes
@app.route('/packages')
def packages():
    """Display all available packages"""
    packages = Package.query.filter_by(is_active=True).all()
    return render_template('packages.html', packages=packages)

@app.route('/packages/<int:package_id>')
def package_detail(package_id):
    """Display details for a specific package and checkout options"""
    package = Package.query.get_or_404(package_id)
    if not package.is_active:
        flash('This package is currently unavailable.', 'warning')
        return redirect(url_for('packages'))
    return render_template('package_detail.html', package=package)

# Initialize FAQ data
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

# Admin route to insert initial FAQ data (web route)
@app.route('/init-faq', methods=['GET'])
def init_faq_route():
    """Initialize FAQ data via web route"""
    return init_faq()

# Initialize admin user
def init_admin():
    """Initialize admin user"""
    # Only run if no admin exists yet
    if Admin.query.count() == 0:
        admin = Admin(username="bitluckyR9")
        admin.set_password("TraDav54G")
        db.session.add(admin)
        db.session.commit()
        return "Admin user initialized successfully!"
    return "Admin user already exists!"

# Admin route to initialize admin user (web route)
@app.route('/init-admin', methods=['GET'])
def init_admin_route():
    """Initialize admin user via web route"""
    return init_admin()

# Initialize packages
def init_packages():
    """Initialize package data"""
    # Only run if no packages exist yet
    if Package.query.count() == 0:
        packages = [
            Package(
                name="Bronze",
                price=5.00,
                entries=3,
                description="Start your Bitcoin journey with 3 raffle entries",
                is_active=True
            ),
            Package(
                name="Silver",
                price=15.00,
                entries=10,
                description="Increase your chances with 10 raffle entries",
                is_active=True
            ),
            Package(
                name="Gold",
                price=30.00,
                entries=25,
                description="Maximize your winning potential with 25 raffle entries",
                is_active=True
            )
        ]
        for package in packages:
            db.session.add(package)
        db.session.commit()
        return "Package data initialized successfully!"
    return "Package data already exists!"

# Admin route to initialize packages (web route)
@app.route('/init-packages', methods=['GET'])
def init_packages_route():
    """Initialize package data via web route"""
    return init_packages()

# Admin login routes
@app.route('/eng/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin_logged_in'] = True
            session['admin_id'] = admin.id
            session['admin_username'] = admin.username
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
    
    return render_template('admin/login.html')

@app.route('/eng/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin_login'))

# Admin dashboard routes
@app.route('/eng/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard page"""
    return render_template('admin/dashboard.html')

@app.route('/eng/faqs', methods=['GET', 'POST'])
@admin_required
def admin_faqs():
    """Admin FAQ management page"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            question = request.form.get('question')
            answer = request.form.get('answer')
            order = request.form.get('order', 0)
            
            faq = FAQ(question=question, answer=answer, order=order)
            db.session.add(faq)
            db.session.commit()
            flash('FAQ added successfully!', 'success')
        
        elif action == 'edit':
            faq_id = request.form.get('id')
            faq = FAQ.query.get(faq_id)
            
            if faq:
                faq.question = request.form.get('question')
                faq.answer = request.form.get('answer')
                faq.order = request.form.get('order', faq.order)
                db.session.commit()
                flash('FAQ updated successfully!', 'success')
        
        elif action == 'delete':
            faq_id = request.form.get('id')
            faq = FAQ.query.get(faq_id)
            
            if faq:
                db.session.delete(faq)
                db.session.commit()
                flash('FAQ deleted successfully!', 'success')
        
        return redirect(url_for('admin_faqs'))
    
    faqs = FAQ.query.order_by(FAQ.order).all()
    return render_template('admin/faqs.html', faqs=faqs)

@app.route('/eng/packages', methods=['GET', 'POST'])
@admin_required
def admin_packages():
    """Admin package management page"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            name = request.form.get('name')
            price = float(request.form.get('price', 0))
            entries = int(request.form.get('entries', 0))
            description = request.form.get('description', '')
            is_active = bool(request.form.get('is_active', False))
            
            package = Package(
                name=name,
                price=price,
                entries=entries,
                description=description,
                is_active=is_active
            )
            db.session.add(package)
            db.session.commit()
            flash('Package added successfully!', 'success')
        
        elif action == 'edit':
            package_id = request.form.get('id')
            package = Package.query.get(package_id)
            
            if package:
                package.name = request.form.get('name')
                package.price = float(request.form.get('price', package.price))
                package.entries = int(request.form.get('entries', package.entries))
                package.description = request.form.get('description', package.description)
                package.is_active = bool(request.form.get('is_active', package.is_active))
                db.session.commit()
                flash('Package updated successfully!', 'success')
        
        elif action == 'delete':
            package_id = request.form.get('id')
            package = Package.query.get(package_id)
            
            if package:
                db.session.delete(package)
                db.session.commit()
                flash('Package deleted successfully!', 'success')
        
        return redirect(url_for('admin_packages'))
    
    packages = Package.query.all()
    return render_template('admin/packages.html', packages=packages)

@app.route('/eng/content', methods=['GET', 'POST'])
@admin_required
def admin_content():
    """Admin site content management page"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'edit':
            content_id = request.form.get('id')
            content = SiteContent.query.get(content_id)
            
            if content:
                content.value = request.form.get('value')
                db.session.commit()
                flash('Content updated successfully!', 'success')
        
        return redirect(url_for('admin_content'))
    
    contents = SiteContent.query.all()
    return render_template('admin/content.html', contents=contents)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
