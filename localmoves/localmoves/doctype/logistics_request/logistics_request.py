import frappe
from frappe.model.document import Document
from datetime import datetime

class LogisticsRequest(Document):
    def before_insert(self):
        """Set initial timestamps"""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def before_save(self):
        """Update timestamp and handle status-related logic"""
        self.updated_at = datetime.now()
        
        if self.status == "Completed" and not self.completed_at:
            self.completed_at = datetime.now()
        
        if self.company_name and not self.assigned_date:
            self.assigned_date = datetime.now()
    
    def validate(self):
        """Validate request data"""
        # Auto-update status when company is assigned
        if self.company_name and self.status == "Pending":
            self.status = "Assigned"
        
        # Validate status transitions (only for existing documents)
        if not self.is_new():
            self._validate_status_transition()
    
    def _validate_status_transition(self):
        """Validate that status transitions are logical"""
        # Get old status from database
        if self.name and frappe.db.exists("Logistics Request", self.name):
            old_doc = frappe.get_doc("Logistics Request", self.name)
            old_status = old_doc.status
            new_status = self.status
            
            # Cannot revert from Completed
            if old_status == "Completed" and new_status != "Completed":
                frappe.throw("Cannot change status from Completed to another status")
            
            # Cannot revert from Cancelled (except to Pending for admin corrections)
            if old_status == "Cancelled" and new_status not in ["Cancelled", "Pending"]:
                frappe.throw("Cannot change status from Cancelled (except back to Pending)")
    
    def on_trash(self):
        """Triggered before the document is deleted"""
        # Prevent deletion of completed requests
        if self.status == "Completed":
            frappe.throw("Cannot delete completed requests. You can cancel them instead.")