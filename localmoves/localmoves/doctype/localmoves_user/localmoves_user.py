import frappe
from frappe.model.document import Document
from localmoves.utils.password_utils import hash_password
from datetime import datetime

class LocalMovesUser(Document):
    def before_insert(self):
        """Hash password before saving"""
        if self.password and not self.password.startswith("pbkdf2:sha256:"):
            self.password = hash_password(self.password)
        self.created_at = datetime.now()
    
    def before_save(self):
        """Hash password if changed"""
        if self.has_value_changed("password") and self.password:
            if not self.password.startswith("pbkdf2:sha256:"):
                self.password = hash_password(self.password)
                