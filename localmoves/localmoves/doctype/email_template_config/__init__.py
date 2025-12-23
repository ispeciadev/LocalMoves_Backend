import frappe
from frappe.model.document import Document




class EmailTemplateConfig(Document):
    """
    Stores customizable email templates for system emails
   
    Allows admins to change email subjects and HTML bodies for:
    - User signup verification
    - Password reset requests
    - Property search results
    - Payment confirmations
    - Payment requests
    """
   
    def validate(self):
        """Validate template configuration"""
        # Validate template name
        valid_names = [
            "signup_verification",
            "password_reset",
            "property_search_results",
            "payment_confirmation",
            "payment_request"
        ]
       
        if self.template_name not in valid_names:
            frappe.throw(f"Invalid template name. Must be one of: {', '.join(valid_names)}")
   
    def before_save(self):
        """Update last_updated timestamp"""
        self.last_updated = frappe.utils.now()
        self.created_by = frappe.session.user
   
    def on_update(self):
        """Log template updates for audit"""
        frappe.log_error(
            f"Email template '{self.name}' was updated by {frappe.session.user}",
            "Email Template Update"
        )

