
import frappe
from frappe.model.document import Document
from datetime import datetime




class SchoolHoliday(Document):
    def validate(self):
        """Validate that end_date is after start_date"""
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                frappe.throw("End Date must be after Start Date")
   
    def before_insert(self):
        """Set timestamps"""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
   
    def on_update(self):
        """Update timestamp"""
        self.updated_at = datetime.now()

