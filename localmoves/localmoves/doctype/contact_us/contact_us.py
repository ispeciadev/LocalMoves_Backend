# Copyright (c) 2025, LocalMoves and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ContactUs(Document):
    def before_insert(self):
        """Set created_at timestamp"""
        if not self.created_at:
            self.created_at = frappe.utils.now()
        
        if not self.status:
            self.status = "New"