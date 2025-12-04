import frappe

# JWT Configuration
JWT_SECRET = frappe.conf.get("jwt_secret_key") or "my_secret_key"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24