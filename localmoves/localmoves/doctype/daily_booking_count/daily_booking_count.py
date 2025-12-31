


import frappe
from frappe.model.document import Document
from datetime import datetime




class DailyBookingCount(Document):
    def validate(self):
        """Auto-set demand_multiplier_active based on booking_count"""
        if self.booking_count >= self.demand_threshold:
            self.demand_multiplier_active = 1
        else:
            self.demand_multiplier_active = 0
   
    def before_insert(self):
        """Set timestamps"""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
   
    def on_update(self):
        """Update timestamp"""
        self.updated_at = datetime.now()




@frappe.whitelist()
def increment_booking_count(date):
    """
    Increment booking count for a specific date
    Creates record if it doesn't exist
    """
    if not frappe.db.exists("Daily Booking Count", date):
        doc = frappe.get_doc({
            "doctype": "Daily Booking Count",
            "date": date,
            "booking_count": 1
        })
        doc.insert(ignore_permissions=True)
    else:
        doc = frappe.get_doc("Daily Booking Count", date)
        doc.booking_count += 1
        doc.save(ignore_permissions=True)
   
    frappe.db.commit()
    return doc.booking_count




@frappe.whitelist()
def get_booking_count(date):
    """Get booking count for a specific date"""
    if frappe.db.exists("Daily Booking Count", date):
        return frappe.db.get_value("Daily Booking Count", date, "booking_count")
    return 0




@frappe.whitelist()
def is_demand_multiplier_active(date):
    """Check if demand multiplier is active for a date"""
    if frappe.db.exists("Daily Booking Count", date):
        return frappe.db.get_value("Daily Booking Count", date, "demand_multiplier_active")
    return 0






