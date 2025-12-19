import frappe

# # Keep reference to original Frappe auth validator
# if not hasattr(frappe.api, "validate_auth_original"):
#     frappe.api.validate_auth_original = frappe.api.validate_auth
