import os
import requests
import json
import time
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash, session
from models import db, FAQ, Admin, Package, SiteContent, Raffle, Entry, Testimonial
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Global cache for Bitcoin price to reduce API calls
btc_price_cache = {
    'price': None,
    'timestamp': 0,
    'cache_duration': 300  # Cache duration in seconds (5 minutes)
}

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Function to get the current Bitcoin price in USD
def get_bitcoin_price(force_refresh=False):
    """Get the current Bitcoin price using multiple APIs for redundancy with caching"""
    global btc_price_cache
    
    print(f"BTC PRICE DEBUG - Cache: {btc_price_cache}, Force Refresh: {force_refresh}")
    
    current_time = time.time()
    # Check if we have a valid cached price
    if not force_refresh and btc_price_cache['price'] and (current_time - btc_price_cache['timestamp'] < btc_price_cache['cache_duration']):
        print(f"BTC PRICE DEBUG - Using cached price: {btc_price_cache['price']}")
        return btc_price_cache['price']
    
    # No valid cache, fetch new price
    try:
        # Try CoinGecko API first
        response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd')
        data = response.json()
        price = float(data['bitcoin']['usd'])
        
        # Update cache
        btc_price_cache['price'] = price
        btc_price_cache['timestamp'] = current_time
        
        return price
    except Exception as e:
        print(f"Error getting Bitcoin price from CoinGecko: {e}")
        
        # If CoinGecko fails, try Coindesk as backup
        try:
            response = requests.get('https://api.coindesk.com/v1/bpi/currentprice/USD.json')
            data = response.json()
            price = float(data['bpi']['USD']['rate'].replace(',', ''))
            
            # Update cache
            btc_price_cache['price'] = price
            btc_price_cache['timestamp'] = current_time
            
            return price
        except Exception as e:
            # If both APIs fail, try Binance as a last resort
            try:
                response = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT')
                data = response.json()
                price = float(data['price'])
                
                # Update cache
                btc_price_cache['price'] = price
                btc_price_cache['timestamp'] = current_time
                
                return price
            except Exception as e:
                print(f"All APIs failed. Error getting Bitcoin price: {e}")
                # If all APIs fail, use cached value if exists, otherwise fallback price
                if btc_price_cache['price']:
                    print("Using last cached Bitcoin price")
                    return btc_price_cache['price']
                else:
                    return 65000.00  # Fallback price in case all APIs are down

# Function to convert USD to BTC
def usd_to_btc(usd_amount):
    """Convert USD to BTC based on current exchange rate"""
    btc_price = get_bitcoin_price()
    btc_amount = usd_amount / btc_price
    return btc_amount

# Function to get wallet content from database
def get_wallet_content():
    """Get wallet content from database"""
    wallet_content = {
        'bitcoin_address': 'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh',  # Default
        'prize_amount': '0.1',  # Default
        'next_raffle_date': 'April 23, 2025'  # Default
    }
    
    # Override with values from database if they exist
    for key in wallet_content.keys():
        content = SiteContent.query.filter_by(section='wallet', key=key).first()
        if content:
            wallet_content[key] = content.value
    
    # Add countdown information
    wallet_content.update(get_countdown_info())
            
    return wallet_content

# Function to calculate countdown information
def get_countdown_info():
    """Calculate and return raffle countdown information"""
    from datetime import datetime, timedelta
    import re
    
    # Get the next raffle date from database
    next_raffle_content = SiteContent.query.filter_by(section='wallet', key='next_raffle_date').first()
    
    try:
        # Try to parse the date from the database
        if next_raffle_content:
            next_raffle_str = next_raffle_content.value
            
            # Clean up the date string - standardize it
            next_raffle_str = next_raffle_str.strip()
            # Convert first letter of month to uppercase and rest to lowercase
            if ' ' in next_raffle_str:
                month_part = next_raffle_str.split(' ')[0]
                if month_part:
                    month_part = month_part.capitalize()
                    next_raffle_str = month_part + next_raffle_str[len(month_part):]
            
            # Replace periods with commas after day numbers
            next_raffle_str = re.sub(r'(\d+)\.', r'\1,', next_raffle_str)
            
            # Try multiple date formats
            date_formats = [
                "%B %d, %Y",    # April 23, 2025
                "%B %d %Y",     # April 23 2025
                "%b %d, %Y",    # Apr 23, 2025
                "%b %d %Y",     # Apr 23 2025
                "%Y-%m-%d",     # 2025-04-23
                "%m/%d/%Y",     # 04/23/2025
                "%d %B %Y",     # 23 April 2025
                "%d %b %Y",     # 23 Apr 2025
                "%B %d.%Y",     # April 23.2025
                "%d.%m.%Y"      # 23.04.2025
            ]
            
            # Try each format until one works
            next_raffle_date = None
            for date_format in date_formats:
                try:
                    next_raffle_date = datetime.strptime(next_raffle_str, date_format)
                    break
                except ValueError:
                    continue
            
            # If none of the formats worked, use default
            if next_raffle_date is None:
                next_raffle_date = datetime.strptime("April 23, 2025", "%B %d, %Y")
                # Also update the database with the correct format
                if next_raffle_content:
                    next_raffle_content.value = "April 23, 2025"
                    db.session.commit()
        else:
            # Default to April 23, 2025 if not in database
            next_raffle_date = datetime.strptime("April 23, 2025", "%B %d, %Y")
        
        # Get current time
        now = datetime.now()
        
        # Calculate time difference
        time_diff = next_raffle_date - now
        
        # If the date has passed, calculate the next 30-day cycle
        if time_diff.total_seconds() <= 0:
            # Find the next raffle date by adding 30-day increments
            days_passed = (now - next_raffle_date).days
            cycles_passed = (days_passed // 30) + 1
            next_raffle_date = next_raffle_date + timedelta(days=cycles_passed * 30)
            time_diff = next_raffle_date - now
            
            # Update the database with the new raffle date
            if next_raffle_content:
                next_raffle_content.value = next_raffle_date.strftime("%B %d, %Y")
                db.session.commit()
        
        # Calculate days, hours, minutes
        days = time_diff.days
        hours = time_diff.seconds // 3600
        minutes = (time_diff.seconds % 3600) // 60
        seconds = time_diff.seconds % 60
        
        # Format the next raffle date
        formatted_date = next_raffle_date.strftime("%B %d, %Y")
        
        return {
            'countdown_days': days,
            'countdown_hours': hours,
            'countdown_minutes': minutes,
            'countdown_seconds': seconds,
            'next_raffle_date': formatted_date
        }
    except Exception as e:
        print(f"Error calculating countdown: {str(e)}")
        # Return default values if there's an error
        return {
            'countdown_days': 30,
            'countdown_hours': 0,
            'countdown_minutes': 0,
            'countdown_seconds': 0,
            'next_raffle_date': "April 23, 2025"
        }

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
    # Get wallet content from database with countdown info
    wallet_content = get_wallet_content()
    
    # Get active testimonials from the database, ordered by their position
    testimonials = Testimonial.query.filter_by(is_active=True).order_by(Testimonial.order).all()
    
    # Ensure we have at least one testimonial for display
    if not testimonials:
        # If no testimonials exist, create a default testimonial structure
        # This will be replaced when real testimonials are added via admin
        default_testimonial = {
            'winner_id': 'R74c9zKX',
            'testimonial_text': '"I never thought I\'d win. BitLucky changed my life while keeping my identity safe!"'
        }
        testimonials = [default_testimonial]
    
    # Add meta refresh tag to update countdown every minute
    meta_refresh = '<meta http-equiv="refresh" content="60">'
    
    return render_template('index.html', wallet_content=wallet_content, testimonials=testimonials, meta_refresh=meta_refresh)

@app.route('/faq')
def faq():
    """Render the FAQ page with frequently asked questions"""
    # Get all FAQ entries from the database, ordered by their position
    faqs = FAQ.query.order_by(FAQ.order).all()
    
    # Get wallet content from database with countdown info
    wallet_content = get_wallet_content()
            
    return render_template('faq.html', faqs=faqs, wallet_content=wallet_content)

@app.route('/about')
def about():
    """Render the About page with information about BitLucky"""
    # Get wallet content from database with countdown info
    wallet_content = get_wallet_content()
            
    return render_template('about.html', wallet_content=wallet_content)

# Additional routes for placeholder pages
@app.route('/terms')
def terms():
    # Get wallet content from database with countdown info
    wallet_content = get_wallet_content()
            
    return render_template('terms.html', wallet_content=wallet_content)

@app.route('/privacy')
def privacy():
    # Get wallet content from database with countdown info
    wallet_content = get_wallet_content()
            
    return render_template('privacy.html', wallet_content=wallet_content)

@app.route('/contact')
def contact():
    # Get wallet content from database with countdown info
    wallet_content = get_wallet_content()
            
    return render_template('contact.html', wallet_content=wallet_content)

@app.route('/transaction_confirmation', methods=['GET', 'POST'])
def transaction_confirmation():
    """Display transaction confirmation page after entry submission"""
    if request.method == 'POST':
        email = request.form.get('email', '')
        txid = request.form.get('txid', '')
        btc_amount = request.form.get('btc_amount', '0.0')
        entries = request.form.get('entries', '0')
        package_id = request.form.get('package_id', '')
        btc_wallet = request.form.get('btc_wallet', '')
        btc_price = request.form.get('btc_price', '0.0')
        
        print(f"CONFIRMATION POST - email: {email}, txid: {txid}, wallet: {btc_wallet}")
        
        # Process the entry form submission
        if all([package_id, email, btc_wallet, txid, btc_amount]):
            # Get the package details
            package = Package.query.get_or_404(package_id)
            
            try:
                # Create new entry in the database
                entry = Entry(
                    email=email,
                    btc_wallet=btc_wallet,
                    txid=txid,
                    btc_amount=float(btc_amount),
                    usd_amount=package.price,
                    btc_price=float(btc_price),
                    package_id=package.id,
                    entry_count=package.entries,
                    is_verified=False  # Admin will verify later
                )
                
                # Add entry to database
                db.session.add(entry)
                db.session.commit()
                
                # Return the confirmation page
                return render_template('transaction_confirmation.html', 
                                      email=email,
                                      txid=txid,
                                      btc_amount=btc_amount,
                                      entries=package.entries,
                                      wallet_content=get_wallet_content())
            except Exception as e:
                print(f"Error saving entry: {str(e)}")
                flash('There was an error processing your entry. Please try again or contact support.', 'danger')
                return redirect(url_for('package_detail', package_id=package_id))
        else:
            flash('All fields are required. Please try again.', 'warning')
            if package_id:
                return redirect(url_for('package_detail', package_id=package_id))
            else:
                return redirect(url_for('packages'))
    
    # GET request
    email = request.args.get('email', '')
    txid = request.args.get('txid', '')
    btc_amount = request.args.get('btc_amount', '0.0')
    entries = request.args.get('entries', '0')
    
    # Debug info
    print(f"TRANSACTION CONFIRMATION - email: {email}, txid: {txid}, btc_amount: {btc_amount}, entries: {entries}")
    print(f"TRANSACTION CONFIRMATION - All args: {request.args}")
    
    # Get wallet content from database with countdown info
    wallet_content = get_wallet_content()
    
    return render_template('transaction_confirmation.html', 
                          email=email,
                          txid=txid,
                          btc_amount=btc_amount,
                          entries=entries,
                          wallet_content=wallet_content)

# Package routes
@app.route('/packages', methods=['GET', 'POST'])
def packages():
    """Display all available packages or process entry form submission"""
    if request.method == 'POST':
        # Process the entry form submission
        package_id = request.form.get('package_id')
        email = request.form.get('email')
        btc_wallet = request.form.get('btc_wallet')
        txid = request.form.get('txid')
        btc_amount = request.form.get('btc_amount')
        usd_amount = request.form.get('usd_amount')
        btc_price = request.form.get('btc_price')
        
        # Debug info
        print(f"FORM DATA - package_id: {package_id}, email: {email}, wallet: {btc_wallet}, txid: {txid}")
        print(f"FORM DATA - btc_amount: {btc_amount}, usd_amount: {usd_amount}, btc_price: {btc_price}")
        
        # Basic validation
        if not all([package_id, email, btc_wallet, txid, btc_amount]):
            flash('All fields are required. Please try again.', 'warning')
            return redirect(url_for('package_detail', package_id=package_id))
        
        # Check for valid Bitcoin wallet address (basic format check)
        if not (btc_wallet.startswith('1') or btc_wallet.startswith('3') or btc_wallet.startswith('bc1')):
            flash('Please enter a valid Bitcoin wallet address.', 'warning')
            return redirect(url_for('package_detail', package_id=package_id))
        
        # Get the package details
        package = Package.query.get_or_404(package_id)
        
        try:
            # Create new entry in the database
            entry = Entry(
                email=email,
                btc_wallet=btc_wallet,
                txid=txid,
                btc_amount=float(btc_amount),
                usd_amount=package.price,
                btc_price=float(btc_price),
                package_id=package.id,
                entry_count=package.entries,
                is_verified=False  # Admin will verify later
            )
            
            # Add entry to database
            db.session.add(entry)
            db.session.commit()
            
            # Redirect to the transaction confirmation page using direct URL
            # Build the URL manually to bypass Flask's url_for which might be causing issues
            confirmation_params = f"?email={email}&txid={txid}&btc_amount={btc_amount}&entries={package.entries}"
            redirect_url = f"/transaction_confirmation{confirmation_params}"
            print(f"REDIRECT DEBUG - Redirecting to: {redirect_url}")
            return redirect(redirect_url)
        except Exception as e:
            # If there's an error saving to the database
            db.session.rollback()
            print(f"Error saving entry: {str(e)}")
            flash('There was an error processing your entry. Please try again or contact support.', 'danger')
            return redirect(url_for('package_detail', package_id=package_id))
    
    # GET request - display all packages
    packages = Package.query.filter_by(is_active=True).all()
    
    # Get wallet content from database with countdown info
    wallet_content = get_wallet_content()
            
    return render_template('packages.html', packages=packages, wallet_content=wallet_content)

@app.route('/packages/<int:package_id>')
def package_detail(package_id):
    """Display details for a specific package and checkout options"""
    package = Package.query.get_or_404(package_id)
    if not package.is_active:
        flash('This package is currently unavailable.', 'warning')
        return redirect(url_for('packages'))
        
    # Calculate Bitcoin price
    btc_price = get_bitcoin_price()
    btc_amount = usd_to_btc(package.price)
    
    # Format the Bitcoin amount to 8 decimal places (satoshi precision)
    btc_formatted = "{:.8f}".format(btc_amount)
    
    # Get wallet content from database with countdown info
    wallet_content = get_wallet_content()
    
    return render_template('package_detail.html', 
                          package=package, 
                          btc_price=btc_price,
                          btc_amount=btc_formatted,
                          wallet_content=wallet_content)

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
                answer="Every 30 days, we raffle off a Bitcoin wallet. Entry tickets can be purchased with Bitcoin for complete anonymity. The more entries you buy, the better your chances of winning!",
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
                answer="When you win, the entire wallet is transferred to you automatically. No claims to file, no forms to fill out - just instant cryptocurrency in your possession.",
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

# Initialize site content
def init_site_content():
    """Initialize site content data"""
    # Only run if no site content exists yet
    if SiteContent.query.count() == 0:
        contents = [
            SiteContent(
                section="wallet", 
                key="bitcoin_address", 
                value="bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                description="Bitcoin wallet address for payments"
            ),
            SiteContent(
                section="wallet", 
                key="prize_amount", 
                value="0.1",
                description="Raffle prize amount in BTC"
            ),
            SiteContent(
                section="wallet", 
                key="next_raffle_date", 
                value="April 23, 2025",
                description="Date of the next raffle drawing"
            ),
            SiteContent(
                section="winner", 
                key="winner_id", 
                value="1A2b3C...",
                description="Anonymous ID of the last winner (truncated for privacy)"
            ),
            SiteContent(
                section="winner", 
                key="testimonial", 
                value="\"I never thought I'd win. BitLucky changed my life while keeping my identity safe!\"",
                description="Winner testimonial quote displayed on the homepage"
            )
        ]
        
        for content in contents:
            db.session.add(content)
        
        db.session.commit()
        return "Site content initialized successfully!"
    return "Site content already exists!"

# Admin route to initialize site content (web route)
@app.route('/init-content', methods=['GET'])
def init_site_content_route():
    """Initialize site content via web route"""
    return init_site_content()

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
    # Get some stats for the dashboard
    entry_count = Entry.query.count()
    verified_count = Entry.query.filter_by(is_verified=True).count()
    pending_count = entry_count - verified_count
    
    # Get recent entries
    recent_entries = Entry.query.order_by(Entry.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                           entry_count=entry_count,
                           verified_count=verified_count,
                           pending_count=pending_count,
                           recent_entries=recent_entries)

@app.route('/eng/faqs', methods=['GET', 'POST'])
@admin_required
def admin_faqs():
    """Admin FAQ management page"""
    # Check if an FAQ ID is provided for editing
    faq_id = request.args.get('faq_id')
    if faq_id:
        # Show the edit form for a specific FAQ
        faq = FAQ.query.get_or_404(faq_id)
        return render_template('admin/faq_edit.html', faq=faq)
        
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
    # Check if a package ID is provided for editing
    package_id = request.args.get('package_id')
    if package_id:
        # Show the edit form for a specific package
        package = Package.query.get_or_404(package_id)
        return render_template('admin/package_edit.html', package=package)
    
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
                package.is_active = bool(request.form.get('is_active', False))
                if request.form.get('is_active'):
                    package.is_active = True
                else:
                    package.is_active = False
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

@app.route('/eng/testimonials', methods=['GET', 'POST'])
@admin_required
def admin_testimonials():
    """Admin testimonials management page"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'delete':
            # Delete testimonial
            testimonial_id = request.form.get('testimonial_id')
            if testimonial_id:
                try:
                    testimonial = Testimonial.query.get(testimonial_id)
                    if testimonial:
                        db.session.delete(testimonial)
                        db.session.commit()
                        flash('Testimonial deleted successfully!', 'success')
                    else:
                        flash('Testimonial not found.', 'warning')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error deleting testimonial: {str(e)}', 'danger')
        elif action == 'toggle_status':
            # Toggle testimonial active status
            testimonial_id = request.form.get('testimonial_id')
            if testimonial_id:
                try:
                    testimonial = Testimonial.query.get(testimonial_id)
                    if testimonial:
                        testimonial.is_active = not testimonial.is_active
                        db.session.commit()
                        status = "activated" if testimonial.is_active else "deactivated"
                        flash(f'Testimonial {status} successfully!', 'success')
                    else:
                        flash('Testimonial not found.', 'warning')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error updating testimonial status: {str(e)}', 'danger')
        elif action == 'update_order':
            # Update testimonial order
            for key, value in request.form.items():
                if key.startswith('order_'):
                    testimonial_id = key.replace('order_', '')
                    try:
                        testimonial = Testimonial.query.get(testimonial_id)
                        if testimonial:
                            testimonial.order = int(value)
                    except ValueError:
                        pass
            
            try:
                db.session.commit()
                flash('Testimonial order updated successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error updating testimonial order: {str(e)}', 'danger')
    
    # Get all testimonials, ordered by their position
    testimonials = Testimonial.query.order_by(Testimonial.order).all()
    return render_template('admin/testimonials.html', testimonials=testimonials)

@app.route('/eng/testimonials/add', methods=['GET', 'POST'])
@admin_required
def admin_testimonial_add():
    """Admin add testimonial page"""
    if request.method == 'POST':
        winner_id = request.form.get('winner_id')
        testimonial_text = request.form.get('testimonial_text')
        order = request.form.get('order', 0)
        is_active = 'is_active' in request.form
        
        # Basic validation
        if not all([winner_id, testimonial_text]):
            flash('Winner ID and testimonial text are required!', 'warning')
            return render_template('admin/testimonial_edit.html', 
                                  testimonial=None, 
                                  is_add=True)
        
        try:
            # Get the highest order value + 1 if no order provided
            if not order:
                highest_order = db.session.query(db.func.max(Testimonial.order)).scalar() or 0
                order = highest_order + 1
                
            # Create new testimonial
            testimonial = Testimonial(
                winner_id=winner_id,
                testimonial_text=testimonial_text,
                order=int(order),
                is_active=is_active
            )
            
            db.session.add(testimonial)
            db.session.commit()
            
            flash('Testimonial added successfully!', 'success')
            return redirect(url_for('admin_testimonials'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding testimonial: {str(e)}', 'danger')
    
    # For GET request
    highest_order = db.session.query(db.func.max(Testimonial.order)).scalar() or 0
    return render_template('admin/testimonial_edit.html', 
                          testimonial=None, 
                          is_add=True,
                          next_order=highest_order + 1)

@app.route('/eng/testimonials/edit/<int:testimonial_id>', methods=['GET', 'POST'])
@admin_required
def admin_testimonial_edit(testimonial_id):
    """Admin edit testimonial page"""
    testimonial = Testimonial.query.get_or_404(testimonial_id)
    
    if request.method == 'POST':
        winner_id = request.form.get('winner_id')
        testimonial_text = request.form.get('testimonial_text')
        order = request.form.get('order', 0)
        is_active = 'is_active' in request.form
        
        # Basic validation
        if not all([winner_id, testimonial_text]):
            flash('Winner ID and testimonial text are required!', 'warning')
            return render_template('admin/testimonial_edit.html', 
                                  testimonial=testimonial, 
                                  is_add=False)
        
        try:
            # Update testimonial
            testimonial.winner_id = winner_id
            testimonial.testimonial_text = testimonial_text
            testimonial.order = int(order)
            testimonial.is_active = is_active
            
            db.session.commit()
            
            flash('Testimonial updated successfully!', 'success')
            return redirect(url_for('admin_testimonials'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating testimonial: {str(e)}', 'danger')
    
    # For GET request
    return render_template('admin/testimonial_edit.html', 
                          testimonial=testimonial, 
                          is_add=False)

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
        
        elif action == 'edit_wallet':
            key = request.form.get('key')
            value = request.form.get('value')
            
            if key and value:
                # Special handling for the next_raffle_date to ensure it's in a consistent format
                if key == 'next_raffle_date':
                    # Try to parse and standardize the date format
                    from datetime import datetime
                    import re
                    
                    # Clean up the date string
                    value = value.strip()
                    
                    # Convert first letter of month to uppercase and rest to lowercase
                    if ' ' in value:
                        month_part = value.split(' ')[0]
                        if month_part:
                            month_part = month_part.capitalize()
                            value = month_part + value[len(month_part):]
                    
                    # Replace periods with commas after day numbers
                    value = re.sub(r'(\d+)\.', r'\1,', value)
                    
                    # Try multiple date formats
                    date_formats = [
                        "%B %d, %Y",    # April 23, 2025
                        "%B %d %Y",     # April 23 2025
                        "%b %d, %Y",    # Apr 23, 2025
                        "%b %d %Y",     # Apr 23 2025
                        "%Y-%m-%d",     # 2025-04-23
                        "%m/%d/%Y",     # 04/23/2025
                        "%d %B %Y",     # 23 April 2025
                        "%d %b %Y",     # 23 Apr 2025
                        "%B %d.%Y",     # April 23.2025
                        "%d.%m.%Y"      # 23.04.2025
                    ]
                    
                    # Try each format until one works
                    parsed_date = None
                    for date_format in date_formats:
                        try:
                            parsed_date = datetime.strptime(value, date_format)
                            break
                        except ValueError:
                            continue
                    
                    # If we successfully parsed the date, convert it to the standard format
                    if parsed_date is not None:
                        value = parsed_date.strftime("%B %d, %Y")
                    else:
                        flash("Warning: Couldn't interpret the date format. Please use Month Day, Year format.", 'warning')
                
                # Look up the wallet content item by key
                content = SiteContent.query.filter_by(section='wallet', key=key).first()
                
                if content:
                    content.value = value
                    db.session.commit()
                    flash(f'Wallet {key.replace("_", " ")} updated successfully!', 'success')
                else:
                    # If the content doesn't exist, create it
                    new_content = SiteContent(
                        section='wallet',
                        key=key,
                        value=value,
                        description=f'Wallet {key.replace("_", " ")} setting'
                    )
                    db.session.add(new_content)
                    db.session.commit()
                    flash(f'Wallet {key.replace("_", " ")} created successfully!', 'success')
        
        return redirect(url_for('admin_content'))
    
    # Get current Bitcoin price for display
    current_btc_price = get_bitcoin_price()
    
    # Get wallet content for the wallet settings section
    wallet_content = {}
    wallet_items = SiteContent.query.filter_by(section='wallet').all()
    for item in wallet_items:
        wallet_content[item.key] = item.value
    
    contents = SiteContent.query.all()
    return render_template('admin/content.html', contents=contents, btc_price=current_btc_price, wallet_content=wallet_content)

@app.route('/eng/refresh-btc-price')
@admin_required
def admin_refresh_btc_price():
    """Admin route to force refresh the Bitcoin price cache"""
    try:
        # Force refresh the Bitcoin price
        new_price = get_bitcoin_price(force_refresh=True)
        flash(f'Bitcoin price refreshed successfully. Current price: ${new_price:,.2f}', 'success')
    except Exception as e:
        flash(f'Error refreshing Bitcoin price: {str(e)}', 'danger')
    
    # Redirect back to the content management page
    return redirect(url_for('admin_content'))

@app.route('/eng/reset-countdown')
@admin_required
def admin_reset_countdown():
    """Admin route to manually reset the countdown timer"""
    try:
        # Get the current next_raffle_date content
        next_raffle_content = SiteContent.query.filter_by(section='wallet', key='next_raffle_date').first()
        
        if next_raffle_content:
            # Calculate a new date 30 days from now
            from datetime import datetime, timedelta
            new_date = datetime.now() + timedelta(days=30)
            formatted_new_date = new_date.strftime("%B %d, %Y")
            
            # Update the next raffle date
            next_raffle_content.value = formatted_new_date
            db.session.commit()
            
            flash(f'Countdown reset successfully! New raffle date: {formatted_new_date}', 'success')
        else:
            flash('Could not find next raffle date content in database.', 'danger')
    except Exception as e:
        flash(f'Error resetting countdown: {str(e)}', 'danger')
    
    # Redirect back to the content management page
    return redirect(url_for('admin_content'))

@app.route('/eng/entries', methods=['GET', 'POST'])
@admin_required
def admin_entries():
    """Admin entries management page - for verifying Bitcoin payments"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'verify':
            entry_id = request.form.get('id')
            entry = Entry.query.get(entry_id)
            
            if entry:
                entry.is_verified = True
                entry.verification_notes = request.form.get('verification_notes', '')
                db.session.commit()
                flash('Entry verified successfully!', 'success')
                
        elif action == 'reject':
            entry_id = request.form.get('id')
            entry = Entry.query.get(entry_id)
            
            if entry:
                entry.is_verified = False
                entry.verification_notes = request.form.get('verification_notes', '')
                db.session.commit()
                flash('Entry marked as rejected!', 'warning')
        
        # Get the entry_id from the form to determine where to redirect
        entry_id = request.form.get('id')
        if entry_id and request.args.get('entry_id'):
            # If we came from the details page, go back there
            return redirect(url_for('admin_entries', entry_id=entry_id))
        else:
            # Otherwise go back to the entries list
            return redirect(url_for('admin_entries'))
    
    # Check if we're looking at a specific entry (details view)
    entry_id = request.args.get('entry_id')
    if entry_id:
        entry = Entry.query.get(entry_id)
        if entry:
            return render_template('admin/entry_details.html', entry=entry)
        else:
            flash('Entry not found', 'danger')
            return redirect(url_for('admin_entries'))
    
    # Filter by verification status if requested
    filter_status = request.args.get('filter')
    if filter_status == 'verified':
        entries = Entry.query.filter_by(is_verified=True).order_by(Entry.created_at.desc()).all()
        filter_active = 'verified'
    elif filter_status == 'pending':
        entries = Entry.query.filter_by(is_verified=False).order_by(Entry.created_at.desc()).all()
        filter_active = 'pending'
    else:
        entries = Entry.query.order_by(Entry.created_at.desc()).all()
        filter_active = 'all'
    
    return render_template('admin/entries.html', entries=entries, filter_active=filter_active)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
