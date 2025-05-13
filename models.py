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
    