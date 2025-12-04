import frappe
import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from frappe import _

SECRET_KEY = "my_secret_key"  # must match JWT_SECRET in jwt_handler.py


def validate_jwt_before_request():
    """
    Runs before every request. Validates JWT and sets frappe.local.session.user if valid.
    """

    path = frappe.request.path

    # Skip public APIs (login, signup, etc.)
    public_routes = [
        "/api/method/localmoves.api.auth.login",
        "/api/method/localmoves.api.auth.signup",
    ]
    if any(path.startswith(r) for r in public_routes):
        return

    auth_header = frappe.get_request_header("Authorization")

    # ✅ Early exit if header is missing
    if not auth_header:
        return

    # ✅ Clean and extract token safely (handles multiple spaces or missing token)
    token = auth_header.replace("Bearer", "").strip()

    if not token:
        frappe.throw(_("Missing token after Bearer"), frappe.AuthenticationError)

    try:
        # ✅ Decode JWT
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = decoded.get("user_id")

        if not user_id:
            frappe.throw(_("Invalid token: user_id missing"), frappe.AuthenticationError)

        # ✅ Set frappe user manually
        frappe.set_user(user_id)
        frappe.local.session = frappe._dict(user=user_id)
        frappe.local.login_manager = frappe._dict(user=user_id)

        # ✅ Store decoded JWT data for use later (get_current_user, etc.)
        frappe.local.jwt_user = decoded
        frappe.flags.jwt_authenticated = True
        frappe.local.jwt_authenticated = True

    except ExpiredSignatureError:
        frappe.throw(_("Token expired. Please login again."), frappe.AuthenticationError)

    except InvalidTokenError as e:
        frappe.log_error(f"Invalid token error: {str(e)}\nToken: {token[:50]}...", "JWT Validation Failed")
        frappe.throw(_("Invalid token."), frappe.AuthenticationError)

    except Exception as e:
        frappe.log_error(f"JWT validation error: {str(e)}\nToken: {token[:50]}...", "JWT Auth Error")
        frappe.throw(_("JWT Authentication Failed"), frappe.AuthenticationError)
