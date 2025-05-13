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