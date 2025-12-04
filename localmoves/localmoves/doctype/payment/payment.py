import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class Payment(Document):
    def before_insert(self):
        """Set initial timestamps and payment date"""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.payment_date = datetime.now()
        
        # Generate invoice number if not provided
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
    
    def before_save(self):
        """Update timestamp and handle status-related logic"""
        self.updated_at = datetime.now()
        
        # Set paid_date when status changes to Paid
        if self.payment_status == "Paid" and not self.paid_date:
            self.paid_date = datetime.now()
            
            # Generate receipt number on payment
            if not self.receipt_number:
                self.receipt_number = self.generate_receipt_number()
            
            # Update company subscription plan
            self.update_company_subscription()
    
    def validate(self):
        """Validate payment data"""
        # Validate billing period
        if self.billing_period_start and self.billing_period_end:
            if self.billing_period_end <= self.billing_period_start:
                frappe.throw("Billing period end date must be after start date")
        
        # Validate amount
        if self.amount < 0:
            frappe.throw("Amount cannot be negative")
        
        # Free plan should have 0 amount
        if self.subscription_plan == "Free" and self.amount > 0:
            frappe.throw("Free plan cannot have payment amount greater than 0")
        
        # Validate subscription plan pricing for paid plans
        if self.payment_type == "Subscription" and self.subscription_plan != "Free":
            self.validate_subscription_amount()
    
    def validate_subscription_amount(self):
        plan_prices = {
            "Free": 0,
            "Basic": 999,      
            "Standard": 4999,  
            "Premium": 14999   
        }        
        expected_amount = plan_prices.get(self.subscription_plan, 0)
        
        if abs(self.amount - expected_amount) > 100 and self.payment_type == "Subscription":
            frappe.msgprint(
                f"Note: Expected amount for {self.subscription_plan} plan is ₹{expected_amount}",
                alert=True
            )
    
    def update_company_subscription(self):
        """Update company's subscription plan when payment is successful"""
        if self.payment_status == "Paid" and self.company_name:
            try:
                company = frappe.get_doc("Logistics Company", self.company_name)
                
                # Update subscription plan
                company.subscription_plan = self.subscription_plan
                # Set subscription validity dates
                company.subscription_start_date = self.billing_period_start
                company.subscription_end_date = self.billing_period_end
                
                # Mark as active
                company.is_active = 1
                
                company.save(ignore_permissions=True)
                frappe.db.commit()
                
                frappe.msgprint(
                    f"Company subscription updated to {self.subscription_plan} plan",
                    alert=True
                )
            except Exception as e:
                frappe.log_error(f"Update company subscription error: {str(e)}")
    
    def generate_invoice_number(self):
        """Generate unique invoice number"""
        prefix = "INV"
        year = datetime.now().strftime("%Y")
        month = datetime.now().strftime("%m")
        
        # Get last invoice number for this month
        last_invoice = frappe.db.sql("""
            SELECT invoice_number 
            FROM `tabPayment` 
            WHERE invoice_number LIKE %s 
            ORDER BY creation DESC 
            LIMIT 1
        """, f"{prefix}-{year}{month}-%")
        
        if last_invoice and last_invoice[0][0]:
            last_num = int(last_invoice[0][0].split("-")[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{prefix}-{year}{month}-{new_num:04d}"
    
    def generate_receipt_number(self):
        """Generate unique receipt number"""
        prefix = "REC"
        year = datetime.now().strftime("%Y")
        month = datetime.now().strftime("%m")
        
        # Get last receipt number for this month
        last_receipt = frappe.db.sql("""
            SELECT receipt_number 
            FROM `tabPayment` 
            WHERE receipt_number LIKE %s 
            ORDER BY creation DESC 
            LIMIT 1
        """, f"{prefix}-{year}{month}-%")
        
        if last_receipt and last_receipt[0][0]:
            last_num = int(last_receipt[0][0].split("-")[-1])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"{prefix}-{year}{month}-{new_num:04d}"
    
    def on_trash(self):
        """Triggered before the document is deleted"""
        # Prevent deletion of paid payments
        if self.payment_status == "Paid":
            frappe.throw("Cannot delete paid payments. You can refund them instead.")


# Scheduler Functions
def check_subscription_expiry():
    """Check and notify companies about subscription expiry (Daily scheduler)"""
    try:
        today = datetime.now().date()
        warning_days = 7  # Notify 7 days before expiry
        
        # Get companies with subscriptions expiring soon (excluding Free plan)
        expiring_soon = frappe.db.sql("""
            SELECT 
                company_name, 
                manager_email, 
                subscription_plan,
                subscription_end_date
            FROM `tabLogistics Company`
            WHERE subscription_end_date BETWEEN %s AND %s
            AND is_active = 1
            AND subscription_plan != 'Free'
        """, (today, today + timedelta(days=warning_days)), as_dict=True)
        
        for company in expiring_soon:
            days_left = (company.subscription_end_date - today).days
            # Send notification (implement email/SMS as needed)
            frappe.log_error(
                f"Subscription expiring in {days_left} days for {company.company_name}",
                "Subscription Expiry Warning"
            )
        
        # Deactivate expired subscriptions (downgrade to Free, not deactivate)
        expired = frappe.db.sql("""
            SELECT company_name 
            FROM `tabLogistics Company`
            WHERE subscription_end_date < %s
            AND is_active = 1
            AND subscription_plan != 'Free'
        """, today, as_dict=True)
        
        for company in expired:
            company_doc = frappe.get_doc("Logistics Company", company.company_name)
            company_doc.subscription_plan = "Free"  # Downgrade to Free
            # Keep company active, just on Free plan
            company_doc.save(ignore_permissions=True)
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Check subscription expiry error: {str(e)}")


def auto_generate_monthly_invoices():
    """Auto-generate monthly subscription invoices (Monthly scheduler)"""
    try:
        today = datetime.now().date()
        
        # Get all active companies with paid subscriptions (not Free)
        active_companies = frappe.db.sql("""
            SELECT 
                company_name,
                manager_email,
                subscription_plan,
                subscription_end_date
            FROM `tabLogistics Company`
            WHERE is_active = 1
            AND subscription_plan IN ('Basic', 'Standard', 'Premium')
            AND (subscription_end_date IS NULL OR subscription_end_date >= %s)
        """, today, as_dict=True)
        
        plan_prices = {
            "Basic": 999,
            "Standard": 4999,
            "Premium": 14999
        }
        
        for company in active_companies:
            # Check if invoice already exists for this month
            existing = frappe.db.exists("Payment", {
                "company_name": company.company_name,
                "billing_period_start": today.replace(day=1),
                "payment_type": "Subscription"
            })
            
            if not existing:
                # Create new payment invoice
                payment = frappe.get_doc({
                    "doctype": "Payment",
                    "company_name": company.company_name,
                    "payment_type": "Subscription",
                    "subscription_plan": company.subscription_plan,
                    "amount": plan_prices.get(company.subscription_plan, 999),
                    "currency": "INR",
                    "payment_status": "Pending",
                    "billing_period_start": today.replace(day=1),
                    "billing_period_end": (today.replace(day=1) + relativedelta(months=1)) - timedelta(days=1),
                    "due_date": today + timedelta(days=7),  # 7 days to pay
                    "description": f"Monthly subscription for {company.subscription_plan} plan"
                })
                payment.insert(ignore_permissions=True)
        
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Auto-generate invoices error: {str(e)}")