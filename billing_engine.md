
# Billing Engine Demo

A simple Flask app demonstrating billing engine concepts from PRD sections 5.1–5.5.

## Setup
1. Install Python 3.8+.
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run a mock SMTP server for email testing:
   ```bash
   python -m smtpd -n -c DebuggingServer localhost:1025
   ```
5. Run the app:
   ```bash
   python app.py
   ```
6. Access the app at `http://localhost:5000`.

## API Endpoints
- `POST /api/customers`: Create a customer (e.g., `{"email": "test@example.com", "name": "Test User", "role": "user"}`).
- `GET /api/customers/<id>`: Get customer details.
- `POST /api/customers/<id>/payment_methods`: Add payment method (e.g., `{"card_number": "1234567890123456"}`).
- `POST /api/payments`: Process payment (e.g., `{"customer_id": 1, "amount": 50.0, "payment_method_id": 1}`).
- `POST /api/subscriptions`: Create subscription (e.g., `{"customer_id": 1, "plan_name": "Pro", "price": 50.0, "billing_interval": "monthly"}`).
- `POST /api/subscriptions/<id>/cancel`: Cancel subscription.
- `GET /api/invoices/<id>`: Get invoice details.
- `GET /dashboard?role=admin`: View admin dashboard.

### Curl Examples

**Create Customer**
```bash
curl -X POST http://localhost:5000/api/customers -H "Content-Type: application/json" -d '{"email": "test@example.com", "name": "Test User", "role": "user"}'
```

**Add Payment Method**
```bash
curl -X POST http://localhost:5000/api/customers/1/payment_methods -H "Content-Type: application/json" -d '{"card_number": "1234567890123456"}'
```

**Process Payment**
```bash
curl -X POST http://localhost:5000/api/payments -H "Content-Type: application/json" -d '{"customer_id": 1, "amount": 50.0, "payment_method_id": 1}'
```

**Create Subscription**
```bash
curl -X POST http://localhost:5000/api/subscriptions -H "Content-Type: application/json" -d '{"customer_id": 1, "plan_name": "Pro", "price": 50.0, "billing_interval": "monthly"}'
```

**Cancel Subscription**
```bash
curl -X POST http://localhost:5000/api/subscriptions/1/cancel
```







## Notes
- Uses SQLite for simplicity; adapt to PostgreSQL for production.
- Mock payment gateway with 70% success rate.
- Emails are logged to console (use a real SMTP server for production).
- Dunning retries are simplified (one retry after 2 days).


## Directory Structure
```
billing_engine/
├── app.py                # Main Flask app
├── models.py            # Database models (Customer, PaymentMethod, Subscription, Invoice)
├── payment_service.py   # Mock payment gateway logic
├── dunning_service.py   # Dunning and retry logic
├── templates/
│   ├── dashboard.html   # Admin dashboard
│   ├── invoice.html     # Invoice view
├── requirements.txt     # Dependencies
└── README.md           # Setup instructions
```


**requirements.txt**

```
Flask==2.3.2
Flask-SQLAlchemy==3.0.5
SQLAlchemy==2.0.23
```


**app.py**

```python
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

if __name__ == '__main__':
    app.run(debug=True)
```

**models.py**

```python
# models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'

class PaymentMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    card_number = db.Column(db.String(4))  # Last 4 digits
    token = db.Column(db.String(36))  # Mock tokenized card
    customer = db.relationship('Customer', backref=db.backref('payment_methods', lazy=True))

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    plan_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    billing_interval = db.Column(db.String(20), nullable=False)  # 'monthly' or 'yearly'
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')
    customer = db.relationship('Customer', backref=db.backref('subscriptions', lazy=True))

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscription.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'paid', 'failed'
    due_date = db.Column(db.DateTime, nullable=False)
    customer = db.relationship('Customer', backref=db.backref('invoices', lazy=True))
    subscription = db.relationship('Subscription', backref=db.backref('invoices', lazy=True))
```

**payment_service.py**

```python   
# payment_service.py
import random

def mock_payment_gateway(token, amount):
    # Simulate payment processing (70% success rate)
    if random.random() < 0.7:
        return {'status': 'success', 'transaction_id': str(random.randint(1000, 9999))}
    return {'status': 'failed', 'error': 'insufficient_funds'}

def process_payment(payment_method, amount):
    result = mock_payment_gateway(payment_method.token, amount)
    return result
``` 

**dunning_service.py**

```python
# dunning_service.py
from datetime import datetime, timedelta

def handle_failed_payment(customer, payment_method, amount):
    # Simplified retry logic: try once more after 2 days
    retry_date = datetime.utcnow() + timedelta(days=2)
    # Simulate storing retry attempt (in production, store in DB)
    print(f"Scheduled retry for {customer.email} on {retry_date}")
    # Send dunning email
    send_email(
        customer.email,
        "Payment Failed",
        f"Payment of ${amount:.2f} failed. We'll retry on {retry_date}. Please update your payment method."
    )
    # In production, implement multiple retries and escalation (e.g., suspend after 3 failures)

def send_email(to_email, subject, body):
    # Reuse email function from app.py (simplified here for clarity)
    print(f"Mock sending email to {to_email}: {subject} - {body}")
    return True
```

**templates/dashboard.html**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>Admin Dashboard</h1>
    <h2>Customers</h2>
    <table>
        <tr><th>ID</th><th>Email</th><th>Name</th><th>Role</th></tr>
        {% for customer in customers %}
        <tr>
            <td>{{ customer.id }}</td>
            <td>{{ customer.email }}</td>
            <td>{{ customer.name }}</td>
            <td>{{ customer.role }}</td>
        </tr>
        {% endfor %}
    </table>
    <h2>Invoices</h2>
    <table>
        <tr><th>ID</th><th>Customer ID</th><th>Amount</th><th>Status</th><th>Due Date</th><th>View</th></tr>
        {% for invoice in invoices %}
        <tr>
            <td>{{ invoice.id }}</td>
            <td>{{ invoice.customer_id }}</td>
            <td>${{ invoice.amount }}</td>
            <td>{{ invoice.status }}</td>
            <td>{{ invoice.due_date }}</td>
            <td><a href="/invoices/{{ invoice.id }}">View</a></td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
```

**templates/invoice.html**

```html
<!DOCTYPE html>
<html>
<head>
    <title>Invoice #{{ invoice.id }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .invoice { max-width: 600px; margin: auto; }
        .header { text-align: center; }
        .details { margin-top: 20px; }
    </style>
</head>
<body>
    <div class="invoice">
        <div class="header">
            <h1>Invoice #{{ invoice.id }}</h1>
        </div>
        <div class="details">
            <p><strong>Customer ID:</strong> {{ invoice.customer_id }}</p>
            <p><strong>Amount:</strong> ${{ invoice.amount }}</p>
            <p><strong>Status:</strong> {{ invoice.status }}</p>
            <p><strong>Due Date:</strong> {{ invoice.due_date }}</p>
        </div>
    </div>
</body>
</html>
```
