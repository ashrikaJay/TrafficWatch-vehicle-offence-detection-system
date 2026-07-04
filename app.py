from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os, uuid, random, string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-not-for-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///violations.db'  # Start with SQLite
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    license_number = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(15))
    violations = db.relationship('Violation', backref='user', lazy=True)

    notifications = db.relationship('Notification', backref='user', lazy=True)
    disputes = db.relationship('Dispute', backref='user', lazy=True)


class Violation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    violation_type = db.Column(db.String(50), nullable=False)  # helmet, redlight, stopline
    location = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    image_path = db.Column(db.String(200))
    penalty_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')  # pending, paid, appealed
    confidence_score = db.Column(db.Float)

    payment = db.relationship('Payment', backref='violation', uselist=False, lazy=True)
    dispute = db.relationship('Dispute', backref='violation', uselist=False, lazy=True)
    notifications = db.relationship('Notification', backref='violation', lazy=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    violation_id = db.Column(db.Integer, db.ForeignKey('violation.id'))
    message = db.Column(db.String(500))
    channel = db.Column(db.String(20), default='sms')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

class Dispute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    violation_id = db.Column(db.Integer, db.ForeignKey('violation.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.String(100))
    explanation = db.Column(db.Text)
    evidence_path = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    decision_explanation = db.Column(db.Text)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    violation_id = db.Column(db.Integer, db.ForeignKey('violation.id'), nullable=False)
    amount = db.Column(db.Float)
    payment_method = db.Column(db.String(50))
    transaction_ref = db.Column(db.String(50))
    paid_at = db.Column(db.DateTime, default=datetime.utcnow)
    receipt_number = db.Column(db.String(30))

# FR7
VIOLATION_RULES = {
    'helmet': {
        'title': 'Helmet Non-Compliance',
        'rule': 'Motor Traffic Act No. 14 of 1951 – Section 138A requires all motorcycle riders and pillion passengers to wear a properly fastened protective helmet at all times while the vehicle is in motion.',
        'why': 'Helmets reduce the risk of fatal head injury by up to 69%. Riding without a helmet endangers the rider and increases the burden on emergency health services.',
        'penalty': 1000.0
    },
    'redlight': {
        'title': 'Red Light Violation',
        'rule': 'Motor Traffic Act – Section 106 prohibits vehicles from proceeding past a red traffic signal. Failure to stop at a red light constitutes a serious traffic offence.',
        'why': 'Red light violations are a leading cause of intersection collisions, endangering pedestrians, cyclists, and other road users.',
        'penalty': 2500.0
    },
    'stopline': {
        'title': 'Stop Line Violation',
        'rule': 'Motor Traffic Act – Section 107 requires all vehicles to stop completely behind the designated stop line at controlled junctions and pedestrian crossings.',
        'why': 'Stopping beyond the line blocks pedestrian crossings and reduces visibility for other road users, increasing accident risk.',
        'penalty': 1500.0
    }
}

# Helpers
def get_compliance(user):
    violations = Violation.query.filter(
        Violation.user_id == user.id,
        Violation.status != 'cancelled'
    ).order_by(Violation.timestamp.desc()).all()

    if not violations:
        days_clean = 999
        status, color = 'Perfect Record', '#28a745'
    else:
        days_clean = (datetime.utcnow() - violations[0].timestamp).days
        if days_clean < 30:
            status, color = 'Recent Violation', '#dc3545'
        elif days_clean < 180:
            status, color = 'Improving', '#e67e22'
        elif days_clean < 365:
            status, color = 'Good Standing', '#17a2b8'
        else:
            status, color = 'Excellent', '#28a745'

    dc = days_clean if days_clean < 999 else 730
    rewards = [
        {'type': 'Insurance Discount (5%)', 'icon': '🛡️', 'milestone': 180,
         'eligible': dc >= 180,
         'detail': '5% discount on vehicle insurance renewal' if dc >= 180
                   else f'{180 - dc} more days needed'},
        {'type': 'Revenue License Discount (10%)', 'icon': '📄', 'milestone': 365,
         'eligible': dc >= 365,
         'detail': '10% off annual revenue license' if dc >= 365
                   else f'{365 - dc} more days needed'},
        {'type': 'Toll Fee Reduction', 'icon': '🛣️', 'milestone': 730,
         'eligible': dc >= 730,
         'detail': 'Reduced toll rates on expressways' if dc >= 730
                   else f'{730 - dc} more days needed'},
    ]
    return {
        'days_clean': dc if days_clean < 999 else '730+',
        'status': status, 'color': color,
        'rewards': rewards,
        'score': min(100, int((dc / 730) * 100))
    }

def log_notification(user_id, violation_id, message, channel='sms'):
    db.session.add(Notification(
        user_id=user_id, violation_id=violation_id,
        message=message, channel=channel, timestamp=datetime.utcnow()
    ))
    db.session.commit()


def img_url(path):
    if not path:
        return None
    return url_for('static', filename=path.replace('static/', '', 1))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

# user route
@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        ln = request.form.get('license_number', '').upper().strip()
        user = User.query.filter_by(license_number=ln).first()
        if user:
            session['user_id'] = user.id
            session['user_type'] = 'user'
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='License number not found.')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('user_type') != 'user':
        return redirect(url_for('user_login'))
    user = User.query.get(session['user_id'])
    violations = Violation.query.filter_by(user_id=user.id).order_by(Violation.timestamp.desc()).all()
    notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.timestamp.desc()).limit(10).all()
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    total_penalty = sum(v.penalty_amount for v in violations if v.status == 'pending')
    compliance = get_compliance(user)
    Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return render_template('dashboard.html', user=user, violations=violations,
                           notifications=notifications, unread=unread,
                           total_penalty=total_penalty, compliance=compliance)

@app.route('/violation/<int:vid>')
def violation_detail(vid):
    if 'user_id' not in session or session.get('user_type') != 'user':
        return redirect(url_for('user_login'))
    v = Violation.query.get_or_404(vid)
    if v.user_id != session['user_id']:
        return redirect(url_for('dashboard'))
    rule = VIOLATION_RULES.get(v.violation_type, VIOLATION_RULES['helmet'])
    return render_template('violation_detail.html', v=v, rule=rule, ev=img_url(v.image_path))


@app.route('/violation/<int:vid>/pay', methods=['GET', 'POST'])
def pay_violation(vid):
    if 'user_id' not in session or session.get('user_type') != 'user':
        return redirect(url_for('user_login'))
    v = Violation.query.get_or_404(vid)
    if v.user_id != session['user_id'] or v.status != 'pending':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        method = request.form.get('payment_method', 'govpay')
        txn = f"TXN{uuid.uuid4().hex[:10].upper()}"
        rcpt = f"RCP{datetime.utcnow().strftime('%Y%m%d')}{random.randint(1000,9999)}"
        p = Payment(violation_id=v.id, amount=v.penalty_amount,
                    payment_method=method, transaction_ref=txn,
                    paid_at=datetime.utcnow(), receipt_number=rcpt)
        db.session.add(p)
        v.status = 'paid'
        db.session.commit()
        log_notification(session['user_id'], v.id,
            f"Payment confirmed. Rs. {v.penalty_amount:.2f} for Violation #{v.id}. "
            f"Receipt: {rcpt}. Ref: {txn}. Thank you.")
        return render_template('payment_confirm.html', v=v, p=p, rcpt=rcpt, txn=txn)
    return render_template('payment.html', v=v)


@app.route('/violation/<int:vid>/dispute', methods=['GET', 'POST'])
def submit_dispute(vid):
    if 'user_id' not in session or session.get('user_type') != 'user':
        return redirect(url_for('user_login'))
    v = Violation.query.get_or_404(vid)
    if v.user_id != session['user_id'] or v.status != 'pending':
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        ev_path = None
        if 'evidence' in request.files and request.files['evidence'].filename:
            f = request.files['evidence']
            fn = f"dispute_{uuid.uuid4().hex}_{f.filename}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            ev_path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
            f.save(ev_path)
        d = Dispute(violation_id=v.id, user_id=session['user_id'],
                    reason=request.form.get('reason'),
                    explanation=request.form.get('explanation'),
                    evidence_path=ev_path, status='pending',
                    submitted_at=datetime.utcnow())
        db.session.add(d)
        v.status = 'disputed'
        db.session.commit()
        log_notification(session['user_id'], v.id,
            f"Dispute DSP-{d.id:04d} for Violation #{v.id} received. "
            f"Under review. You will be notified within 14 working days.")
        return render_template('dispute_confirm.html', v=v, d=d)

    rule = VIOLATION_RULES.get(v.violation_type, VIOLATION_RULES['helmet'])
    return render_template('dispute.html', v=v, rule=rule, ev=img_url(v.image_path))

# admin route
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('username') == 'admin' and request.form.get('password') == 'admin123':
            session['admin_logged_in'] = True
            session['user_type'] = 'admin'
            return redirect(url_for('admin'))
        return render_template('admin_login.html', error='Invalid username or password')
    return render_template('admin_login.html')


@app.route('/admin')
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    violations = Violation.query.order_by(Violation.timestamp.desc()).limit(50).all()
    paid = Violation.query.filter_by(status='paid').all()
    today = datetime.utcnow().date()
    return render_template('admin.html',
        violations=violations,
        total_violations=Violation.query.count(),
        pending_count=Violation.query.filter_by(status='pending').count(),
        disputed_count=Violation.query.filter_by(status='disputed').count(),
        total_revenue=sum(v.penalty_amount for v in paid),
        resolved_today=Violation.query.filter(
            Violation.status == 'paid',
            Violation.timestamp >= datetime.combine(today, datetime.min.time())).count(),
        helmet_count=Violation.query.filter_by(violation_type='helmet').count(),
        redlight_count=Violation.query.filter_by(violation_type='redlight').count(),
        stopline_count=Violation.query.filter_by(violation_type='stopline').count())

@app.route('/admin/disputes')
def admin_disputes():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    disputes = Dispute.query.order_by(Dispute.submitted_at.desc()).all()
    return render_template('admin_disputes.html', disputes=disputes)


@app.route('/admin/dispute/<int:did>/review', methods=['POST'])
def review_dispute(did):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    d = Dispute.query.get_or_404(did)
    decision = request.form.get('decision')
    note = request.form.get('decision_explanation', '')
    d.status = decision
    d.reviewed_at = datetime.utcnow()
    d.decision_explanation = note
    v = Violation.query.get(d.violation_id)
    v.status = 'cancelled' if decision == 'approved' else 'pending'
    db.session.commit()
    outcome = 'approved — fine cancelled' if decision == 'approved' else 'rejected — fine remains payable'
    log_notification(d.user_id, v.id,
        f"Dispute DSP-{d.id:04d} for Violation #{v.id} has been {outcome}. Note: {note}")
    return redirect(url_for('admin_disputes'))

@app.route('/detect', methods=['GET', 'POST'])
def detect_violation():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    if request.method == 'GET':
        return render_template('detect.html')

    if 'image' not in request.files or not request.files['image'].filename:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    fname = f"{uuid.uuid4().hex}_{file.filename}"
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    file.save(fpath)

    from helmet_detection import detect_helmet_violation
    result = detect_helmet_violation(fpath)

    if result['violation_detected']:
        codes = ['WP','CP','SP','NP','EP','NC','SG','UV','NW']
        plate = (f"{random.choice(codes)}-"
                 f"{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}-"
                 f"{''.join(random.choices(string.digits, k=4))}")
        user = User.query.filter_by(license_number=plate).first()
        if not user:
            user = User(license_number=plate, name='Registered Owner (Simulated)',
                        email='notify@simulation.lk', phone='0700000000')
            db.session.add(user)
            db.session.commit()
        v = Violation(user_id=user.id, violation_type='helmet',
                      location='Galle Road, Ratmalana–Kollupitiya Route',
                      image_path=fpath, penalty_amount=1000.0,
                      confidence_score=round(result['confidence'], 4), status='pending')
        db.session.add(v)
        db.session.commit()
        log_notification(user.id, v.id,
            f"DMT Alert: HELMET violation recorded for {plate} at Galle Road. "
            f"Fine: Rs. 1,000.00. Login with your plate number to view and pay.")
        return jsonify({'detected': True, 'violation_type': 'helmet',
                        'confidence': round(result['confidence'] * 100, 1),
                        'penalty': 1000.0, 'plate': plate, 'violation_id': v.id,
                        'labels_found': result['all_labels']})

    return jsonify({'detected': False, 'message': 'No helmet violation detected.',
                    'labels_found': result['all_labels']})

@app.route('/logout')
def logout():
    t = session.get('user_type')
    session.clear()
    return redirect(url_for('admin_login') if t == 'admin' else url_for('user_login'))

# Seed
with app.app_context():
    db.create_all()

    if User.query.count() == 0:
        users = [
            User(license_number='CAA-1234', name='Nimal Perera', email='nimal@example.com', phone='0771234567'),
            User(license_number='CAB-5678', name='Kamala Silva', email='kamala@example.com', phone='0779876543'),
            User(license_number='CAC-9012', name='Sunil Fernando', email='sunil@example.com', phone='0772345678'),
            User(license_number='CAD-3456', name='Dilani Rajapaksa', email='dilani@example.com', phone='0773456789'),
            User(license_number='CAT-8888', name='Ashrika Jay', email='ash2023@example.com', phone='0717145678'),
            User(license_number='CAP-0000', name='Kathy Thompson', email='kathy@example.com', phone='0777145078'),
        ]
        db.session.add_all(users)
        db.session.commit()

        pm = {'helmet': 1000.0, 'redlight': 2500.0, 'stopline': 1500.0}
        locs = ['Galle Road, Ratmalana', 'Duplication Road, Colombo 4',
                'Marine Drive, Colombo 3', 'Galle Road, Bambalapitiya']

        for i in range(15):
            u = random.choice(users)
            vt = random.choice(['helmet', 'redlight', 'stopline'])
            vs = random.choice(['pending', 'paid', 'pending', 'pending'])
            vtime = datetime.utcnow() - timedelta(days=random.randint(1, 45))

            v = Violation(user_id=u.id, violation_type=vt, location=random.choice(locs),
                          timestamp=vtime, penalty_amount=pm[vt], status=vs,
                          confidence_score=round(random.uniform(0.70, 0.98), 4))
            db.session.add(v)
            db.session.commit()

            db.session.add(Notification(
                user_id=u.id, violation_id=v.id,
                message=f"DMT Alert: {vt.upper()} violation for {u.license_number} at {v.location}. Fine: Rs. {pm[vt]:.2f}. Login to view and pay.",
                channel=random.choice(['sms', 'email']),
                timestamp=vtime + timedelta(minutes=5), is_read=(i < 10)))

            if vs == 'paid':
                db.session.add(Payment(
                    violation_id=v.id, amount=pm[vt],
                    payment_method=random.choice(['govpay', 'card']),
                    transaction_ref=f"TXN{uuid.uuid4().hex[:10].upper()}",
                    paid_at=vtime + timedelta(days=2),
                    receipt_number=f"RCP{vtime.strftime('%Y%m%d')}{random.randint(1000,9999)}"))

            if i == 4 and vs == 'pending':
                db.session.add(Dispute(
                    violation_id=v.id, user_id=u.id, reason='not_my_vehicle',
                    explanation='I was not driving on this date. My vehicle was parked at home. Please review the CCTV carefully.',
                    status='pending', submitted_at=vtime + timedelta(days=1)))
                v.status = 'disputed'

        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=5000)