import frappe

def custom_validate_auth():
    """
    Override frappe.api.validate_auth
    Skip frappe auth if JWT already validated.
    """
    if getattr(frappe.local, "jwt_authenticated", False) or getattr(frappe.flags, "jwt_authenticated", False):
        return  # JWT already validated successfully
    else:
        from frappe.api import validate_auth as original_validate_auth
        return original_validate_auth()
