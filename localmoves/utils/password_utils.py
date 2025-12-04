from werkzeug.security import generate_password_hash, check_password_hash
import frappe

def hash_password(password):
    """Hash a password using Werkzeug"""
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(plain_password, hashed_password):
    """Verify a password against a hash"""
    try:
        if not plain_password or not hashed_password:
            return False
        return check_password_hash(hashed_password, plain_password)
    except Exception as e:
        frappe.log_error(f"Password verification error: {str(e)}")
        return False