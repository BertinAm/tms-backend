from cryptography.fernet import Fernet
import jwt
import os
import environ
from django.conf import settings

# Load environment variables
environ.Env.read_env(os.path.join(settings.BASE_DIR, '.env'))
env = environ.Env()

# Generate a key for encryption/decryption
# In production, store this key securely
key = Fernet.generate_key()
cipher_suite = Fernet(key)
JWT_SECRET = settings.SECRET_KEY


def create_token(payload):
    """
    Create an encrypted JWT token from payload
    """
    try:
        # Create JWT token
        token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')
        # Encrypt the JWT token
        encrypted_token = cipher_suite.encrypt(token.encode()).decode()
        return encrypted_token
    except Exception as e:
        print(f"Error creating token: {e}")
        return None


def decrypt_token(enc_token):
    """
    Decrypt an encrypted token and extract payload
    """
    try:
        # Decrypt the token
        dec_token = cipher_suite.decrypt(enc_token.encode()).decode()
        # Decode the JWT token
        payload = jwt.decode(dec_token, JWT_SECRET, algorithms=['HS256'])
        return {'payload': payload, 'status': True}
    except jwt.ExpiredSignatureError:
        return {'status': False, 'error': 'Token expired'}
    except jwt.InvalidTokenError:
        return {'status': False, 'error': 'Invalid token'}
    except Exception as e:
        return {'status': False, 'error': str(e)}
