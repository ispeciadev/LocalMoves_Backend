import frappe
from frappe.model.document import Document
from datetime import datetime




class BankHoliday(Document):
    def before_save(self):
        """Auto-calculate day of week from date"""
        if self.date:
            date_obj = datetime.strptime(str(self.date), "%Y-%m-%d")
            self.day_of_week = date_obj.strftime("%A")
   
    def before_insert(self):
        """Set timestamps"""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
   
    def on_update(self):
        """Update timestamp"""
        self.updated_at = datetime.now()


