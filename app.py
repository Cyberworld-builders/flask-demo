# app.py
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from models import db, Customer, PaymentMethod, Subscription, Invoice
from payment_service import process_payment, mock_payment_gateway
from dunning_service import handle_failed_payment
import uuid

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///billing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Initialize database
with app.app_context():
    db.create_all()

# Mock SMTP server settings (replace with real SMTP for production)
SMTP_SERVER = "localhost"
SMTP_PORT = 1025  # For testing with `python -m smtpd -n -c DebuggingServer localhost:1025`

# Helper to send emails
def send_email(to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'billing@example.com'
    msg['To'] = to_email
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False

# 5.1 Customer & Account Management
@app.route('/api/customers', methods=['POST'])
def create_customer():
    data = request.json
    customer = Customer(
        email=data['email'],
        name=data.get('name', ''),
        role=data.get('role', 'user')  # Role-based access: 'admin' or 'user'
    )
    db.session.add(customer)
    db.session.commit()
    return jsonify({'id': customer.id, 'email': customer.email, 'role': customer.role}), 201

@app.route('/api/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return jsonify({
        'id': customer.id,
        'email': customer.email,
        'name': customer.name,
        'role': customer.role
    })

# 5.2 Payment Methods & Processing
@app.route('/api/customers/<int:customer_id>/payment_methods', methods=['POST'])
def add_payment_method(customer_id):
    Customer.query.get_or_404(customer_id)
    data = request.json
    token = str(uuid.uuid4())  # Simulate tokenization
    payment_method = PaymentMethod(
        customer_id=customer_id,
        card_number=data['card_number'][-4:],  # Store last 4 digits
        token=token
    )
    db.session.add(payment_method)
    db.session.commit()
    return jsonify({'id': payment_method.id, 'card_number': payment_method.card_number}), 201

@app.route('/api/payments', methods=['POST'])
def process_payment_route():
    data = request.json
    customer_id = data['customer_id']
    amount = data['amount']
    payment_method_id = data['payment_method_id']
    payment_method = PaymentMethod.query.get_or_404(payment_method_id)
    result = process_payment(payment_method, amount)
    if result['status'] == 'success':
        return jsonify(result), 200
    else:
        # Trigger dunning logic for failed payment
        customer = Customer.query.get_or_404(customer_id)
        handle_failed_payment(customer, payment_method, amount)
        return jsonify(result), 400

# 5.3 Subscription Management
@app.route('/api/subscriptions', methods=['POST'])
def create_subscription():
    data = request.json
    customer = Customer.query.get_or_404(data['customer_id'])
    start_date = datetime.utcnow()
    subscription = Subscription(
        customer_id=customer.id,
        plan_name=data['plan_name'],
        price=data['price'],
        billing_interval=data['billing_interval'],  # 'monthly' or 'yearly'
        start_date=start_date,
        status='active'
    )
    db.session.add(subscription)
    db.session.commit()
    # Generate invoice
    invoice = generate_invoice(customer, subscription, data['price'])
    return jsonify({
        'id': subscription.id,
        'plan_name': subscription.plan_name,
        'status': subscription.status,
        'invoice_id': invoice.id
    }), 201

@app.route('/api/subscriptions/<int:subscription_id>/cancel', methods=['POST'])
def cancel_subscription(subscription_id):
    subscription = Subscription.query.get_or_404(subscription_id)
    subscription.status = 'canceled'
    subscription.end_date = datetime.utcnow()
    # Prorate refund (simplified)
    days_remaining = 30 - (datetime.utcnow() - subscription.start_date).days
    if days_remaining > 0:
        prorated_amount = (days_remaining / 30) * subscription.price
        send_email(
            subscription.customer.email,
            "Subscription Canceled",
            f"Your subscription has been canceled. Prorated refund: ${prorated_amount:.2f}"
        )
    db.session.commit()
    return jsonify({'id': subscription.id, 'status': subscription.status}), 200

# 5.4 Invoicing & Billing
def generate_invoice(customer, subscription, amount):
    invoice = Invoice(
        customer_id=customer.id,
        subscription_id=subscription.id,
        amount=amount,
        status='pending',
        due_date=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(invoice)
    db.session.commit()
    # Send invoice email
    send_email(
        customer.email,
        f"Invoice #{invoice.id}",
        f"New invoice for {subscription.plan_name}. Amount: ${amount:.2f}, Due: {invoice.due_date}"
    )
    return invoice

@app.route('/api/invoices/<int:invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return jsonify({
        'id': invoice.id,
        'customer_id': invoice.customer_id,
        'amount': invoice.amount,
        'status': invoice.status,
        'due_date': invoice.due_date
    })

# 5.5 Dunning & Retry Logic (handled in dunning_service.py)
# Admin Dashboard (5.10 simplified)
@app.route('/dashboard')
def dashboard():
    if request.args.get('role') != 'admin':  # Simulate role-based access
        return "Access denied", 403
    customers = Customer.query.all()
    invoices = Invoice.query.all()
    return render_template('dashboard.html', customers=customers, invoices=invoices)

@app.route('/invoices/<int:invoice_id>')
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('invoice.html', invoice=invoice)

@app.route('/')
def home():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)