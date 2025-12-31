import jwt
import frappe
from datetime import datetime, timedelta
from frappe import _

JWT_SECRET = "my_secret_key"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 168  # 7 days instead of 24 hours


def generate_token(user_id, email, role):
    """Generate JWT token"""
    try:
        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
            "iat": datetime.utcnow(),
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        print(f"✅ Token generated successfully for {email}")
        return token
    except Exception as e:
        frappe.log_error(f"Token generation failed: {str(e)}")
        return None


def verify_token(token):
    """Verify JWT token and return payload"""
    try:
        # ✅ Clean token before decoding (handles spaces)
        token = str(token).replace("Bearer", "").strip()
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        print(f"✅ Token verified. Payload: {payload}")
        return payload
    except jwt.ExpiredSignatureError:
        frappe.throw(_("Token has expired"), frappe.AuthenticationError)
    except jwt.InvalidTokenError as e:
        frappe.throw(_("Invalid token"), frappe.AuthenticationError)
    except Exception as e:
        frappe.log_error(f"Token verification failed: {str(e)}")
        frappe.throw(_("Authentication failed"), frappe.AuthenticationError)


def get_current_user(token):
    """Get current user from token"""
    try:
        payload = verify_token(token)

        if not payload:
            frappe.throw(_("Invalid token payload"), frappe.AuthenticationError)

        required_fields = ["user_id", "email", "role"]
        for field in required_fields:
            if field not in payload:
                frappe.throw(_(f"Token missing required field: {field}"), frappe.AuthenticationError)

        print(f"✅ User validated: {payload.get('email')} - {payload.get('role')}")
        return payload

    except frappe.AuthenticationError:
        raise
    except Exception as e:
        frappe.log_error(f"get_current_user failed: {str(e)}")
        frappe.throw(_("Failed to get user from token"), frappe.AuthenticationError)
