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