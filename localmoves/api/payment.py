import frappe
from frappe import _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import jwt
import traceback

# Your JWT configuration
JWT_SECRET = "my_secret_key"
JWT_ALGORITHM = "HS256"

# Subscription Plan Pricing
PLAN_PRICING = {
    "Free": {
        "monthly": 0,
        "yearly": 0,
        "features": {
            "request_limit": 10,
            "support": "Community Forum",
            "analytics": "None"
        }
    },
    "Basic": {
        "monthly": 999,
        "yearly": 9999,
        "features": {
            "request_limit": 20,
            "support": "Email",
            "analytics": "Basic"
        }
    },
    "Standard": {
        "monthly": 4999,
        "yearly": 49999,
        "features": {
            "request_limit": 50,
            "support": "Priority Email",
            "analytics": "Advanced"
        }
    },
    "Premium": {
        "monthly": 14999,
        "yearly": 149999,
        "features": {
            "request_limit": -1,
            "support": "24/7 Phone & Email",
            "analytics": "Premium with AI Insights"
        }
    }
}


def get_user_from_token():
    """Extract user from JWT token - Uses frappe.local.jwt_user set by jwt_auth"""
    try:
        # First, try to get from frappe.local.jwt_user (set by jwt_auth.py)
        if hasattr(frappe.local, 'jwt_user') and frappe.local.jwt_user:
            user_info = frappe.local.jwt_user
            if user_info and isinstance(user_info, dict):
                return user_info
        
        # Fallback: decode token directly
        token = frappe.get_request_header("Authorization")
        
        if not token:
            frappe.throw(_("No token provided"), frappe.AuthenticationError)
        
        # Clean token
        token = str(token).replace("Bearer", "").strip()
        
        if not token:
            frappe.throw(_("Empty token"), frappe.AuthenticationError)
        
        # Decode JWT directly
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        if not payload or not isinstance(payload, dict):
            frappe.throw(_("Invalid token payload"), frappe.AuthenticationError)
        
        # Verify required fields
        required_fields = ["user_id", "email", "role"]
        for field in required_fields:
            if field not in payload:
                frappe.throw(_(f"Token missing field: {field}"), frappe.AuthenticationError)
        
        return payload
        
    except jwt.ExpiredSignatureError:
        frappe.throw(_("Token has expired"), frappe.AuthenticationError)
    except jwt.InvalidTokenError:
        frappe.throw(_("Invalid token"), frappe.AuthenticationError)
    except frappe.AuthenticationError:
        raise
    except Exception as e:
        frappe.log_error(message=f"Auth error: {str(e)}", title="Auth Error")
        frappe.throw(_("Authentication failed"), frappe.AuthenticationError)


def get_json_data():
    """Parse JSON data from request"""
    try:
        # Try frappe.request.get_json()
        if hasattr(frappe, "request") and frappe.request:
            try:
                data = frappe.request.get_json(force=True, silent=True)
                if data and isinstance(data, dict):
                    return data
            except:
                pass
        
        # Try parsing raw data
        if hasattr(frappe, "request") and hasattr(frappe.request, "get_data"):
            try:
                raw = frappe.request.get_data(as_text=True)
                if raw:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        return parsed
            except:
                pass
        
        # Try form_dict
        if hasattr(frappe, "form_dict") and frappe.form_dict:
            try:
                form_data = dict(frappe.form_dict)
                if form_data:
                    return form_data
            except:
                pass
        
        # Try local.form_dict
        if hasattr(frappe.local, "form_dict") and frappe.local.form_dict:
            try:
                return dict(frappe.local.form_dict)
            except:
                pass
    except:
        pass
    
    return {}


def init_session_for_jwt():
    """Initialize minimal session data to avoid NoneType errors in version tracking"""
    if not hasattr(frappe, 'session') or frappe.session is None:
        frappe.session = frappe._dict()
    
    if not hasattr(frappe.session, 'data') or frappe.session.data is None:
        frappe.session.data = frappe._dict()
    
    # Set user if available
    if hasattr(frappe.local, 'jwt_user') and frappe.local.jwt_user:
        user_id = frappe.local.jwt_user.get('user_id')
        if user_id and not frappe.session.get('user'):
            frappe.session.user = user_id

    
# Get Subscription Plans
@frappe.whitelist(allow_guest=True)
def get_subscription_plans():
    """Get all available subscription plans with pricing"""
    try:
        return {
            "success": True,
            "plans": PLAN_PRICING,
            "message": "Subscription plans fetched successfully"
        }
    except Exception as e:
        frappe.log_error(f"Get Subscription Plans Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch subscription plans"}


# Process Payment - THE WORKING VERSION
# Process Payment - FIXED VERSION
@frappe.whitelist(allow_guest=True)
def process_payment():
    """
    Create and optionally mark payment as paid in one call
    If payment_immediately is True, payment is marked as paid right away
    and company subscription is updated
    """
    try:
        # Initialize session to avoid version tracking errors
        init_session_for_jwt()
        
        # Step 1: Authenticate user
        user_info = get_user_from_token()
        
        # Validate user_info
        if not user_info or not isinstance(user_info, dict):
            return {
                "success": False,
                "message": "Authentication failed: Invalid user data"
            }
        
        if "email" not in user_info or "role" not in user_info:
            return {
                "success": False,
                "message": "Authentication failed: Incomplete user data"
            }
        
        # Step 2: Get request data
        data = get_json_data()
        
        if not data or not isinstance(data, dict):
            return {
                "success": False,
                "message": "Invalid request data"
            }
        
        # Step 3: Extract and validate fields
        company_name = data.get("company_name", "")
        subscription_plan = data.get("subscription_plan", "")
        payment_method = data.get("payment_method", "")
        billing_cycle = data.get("billing_cycle", "monthly")
        payment_immediately = data.get("payment_immediately", False)
        transaction_ref = data.get("transaction_ref", "")
        notes = data.get("notes", "")
        
        # Validate required fields
        if not company_name or not subscription_plan:
            return {
                "success": False,
                "message": "Missing required fields: company_name and subscription_plan are required"
            }
        
        # Validate subscription plan
        if subscription_plan not in PLAN_PRICING:
            return {
                "success": False,
                "message": f"Invalid subscription plan: {subscription_plan}. Valid options: Free, Basic, Standard, Premium"
            }
        
        # Don't allow Free plan
        if subscription_plan == "Free":
            return {
                "success": False,
                "message": "Free plan doesn't require payment. It's automatically assigned."
            }
        
        # Check if company exists
        if not frappe.db.exists("Logistics Company", company_name):
            return {
                "success": False,
                "message": f"Company '{company_name}' not found"
            }
        
        # Get company document
        company = frappe.get_doc("Logistics Company", company_name)
        
        # Check permissions
        user_email = user_info.get("email", "")
        user_role = user_info.get("role", "")
        
        is_manager = (company.manager_email == user_email)
        is_admin = (user_role == "Admin")
        
        if not (is_manager or is_admin):
            return {
                "success": False,
                "message": "You don't have permission to create payment for this company"
            }
        
        # Calculate amount based on billing cycle
        amount = PLAN_PRICING[subscription_plan].get(billing_cycle, PLAN_PRICING[subscription_plan]["monthly"])
        
        # Calculate billing period
        today = datetime.now().date()
        billing_start = today
        
        if billing_cycle == "yearly":
            billing_end = billing_start + relativedelta(years=1) - timedelta(days=1)
        else:
            billing_end = billing_start + relativedelta(months=1) - timedelta(days=1)
        
        # Determine initial payment status
        initial_status = "Paid" if payment_immediately else "Pending"
        
        # Create payment document
        payment_doc = frappe.get_doc({
            "doctype": "Payment",
            "company_name": company_name,
            "payment_type": "Subscription",
            "subscription_plan": subscription_plan,
            "amount": amount,
            "currency": "INR",
            "payment_status": initial_status,
            "payment_method": payment_method,
            "billing_period_start": billing_start,
            "billing_period_end": billing_end,
            "due_date": today + timedelta(days=7),
            "description": f"{billing_cycle.capitalize()} subscription for {subscription_plan} plan",
            "notes": notes
        })
        
        # If paying immediately, update everything
        if payment_immediately:
            payment_doc.paid_date = datetime.now()
            
            # Add transaction reference
            if transaction_ref:
                current_notes = payment_doc.notes or ""
                payment_doc.notes = f"{current_notes}\nTransaction Ref: {transaction_ref}".strip()
            
            # Update company subscription details
            company.subscription_plan = subscription_plan
            company.subscription_start_date = billing_start
            company.subscription_end_date = billing_end
            company.is_active = 1
            company.requests_viewed_this_month = 0
            company.updated_at = datetime.now()
            
            # Disable version tracking temporarily for this save
            flags_before = company.flags.ignore_version if hasattr(company.flags, 'ignore_version') else False
            company.flags.ignore_version = True
            
            # Save company
            company.save(ignore_permissions=True)
            
            # Restore flags
            company.flags.ignore_version = flags_before
        
        # Insert payment document
        payment_doc.insert(ignore_permissions=True)
        
        # Commit transaction
        frappe.db.commit()
        
        # Prepare response
        response_data = {
            "payment_id": payment_doc.name,
            "invoice_number": payment_doc.invoice_number,
            "amount": payment_doc.amount,
            "subscription_plan": subscription_plan,
            "billing_cycle": billing_cycle,
            "payment_status": payment_doc.payment_status
        }
        
        if payment_immediately:
            response_data["receipt_number"] = payment_doc.receipt_number
            response_data["valid_until"] = str(payment_doc.billing_period_end)
            response_data["subscription_updated"] = True
            message = "Payment created and marked as paid successfully. Company subscription updated."
        else:
            response_data["due_date"] = str(payment_doc.due_date)
            message = "Payment created successfully. Please complete the payment."
        
        return {
            "success": True,
            "message": message,
            "data": response_data
        }
        
    except frappe.AuthenticationError as e:
        return {
            "success": False,
            "message": f"Authentication error: {str(e)}"
        }
    except Exception as e:
        error_msg = str(e)
        trace = traceback.format_exc()
        
        # Log with short title
        frappe.log_error(
            message=f"Payment Error\n{error_msg}\n{trace}",
            title="Payment Error"
        )
        
        frappe.db.rollback()
        
        return {
            "success": False,
            "message": f"Failed to process payment: {error_msg}"
        }



# Create Payment / Subscribe
@frappe.whitelist(allow_guest=True)
def create_payment():
    """Create a new payment for subscription (Manager/Admin)"""
    try:
        user_info = get_user_from_token()
        data = get_json_data() or {}
        
        company_name = data.get("company_name", "")
        subscription_plan = data.get("subscription_plan", "")
        payment_method = data.get("payment_method", "")
        billing_cycle = data.get("billing_cycle", "monthly")
        
        if not company_name or not subscription_plan:
            return {"success": False, "message": "Missing required fields"}
        
        if subscription_plan not in PLAN_PRICING:
            return {"success": False, "message": "Invalid subscription plan"}
        
        if subscription_plan == "Free":
            return {"success": False, "message": "Free plan doesn't require payment"}
        
        if not frappe.db.exists("Logistics Company", company_name):
            return {"success": False, "message": "Company not found"}
        
        company = frappe.get_doc("Logistics Company", company_name)
        
        is_manager = company.manager_email == user_info.get("email", "")
        is_admin = user_info.get("role", "") == "Admin"
        
        if not (is_manager or is_admin):
            return {"success": False, "message": "You don't have permission"}
        
        amount = PLAN_PRICING[subscription_plan].get(billing_cycle, PLAN_PRICING[subscription_plan]["monthly"])
        
        today = datetime.now().date()
        billing_start = today
        
        if billing_cycle == "yearly":
            billing_end = billing_start + relativedelta(years=1) - timedelta(days=1)
        else:
            billing_end = billing_start + relativedelta(months=1) - timedelta(days=1)
        
        payment_doc = frappe.get_doc({
            "doctype": "Payment",
            "company_name": company_name,
            "payment_type": "Subscription",
            "subscription_plan": subscription_plan,
            "amount": amount,
            "currency": "INR",
            "payment_status": "Pending",
            "payment_method": payment_method,
            "billing_period_start": billing_start,
            "billing_period_end": billing_end,
            "due_date": today + timedelta(days=7),
            "description": f"{billing_cycle.capitalize()} subscription for {subscription_plan} plan",
            "notes": data.get("notes", "")
        })
        
        payment_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Payment created successfully",
            "data": {
                "payment_id": payment_doc.name,
                "invoice_number": payment_doc.invoice_number,
                "amount": payment_doc.amount,
                "due_date": str(payment_doc.due_date),
                "subscription_plan": subscription_plan,
                "billing_cycle": billing_cycle
            }
        }
        
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Create Payment Error: {str(e)}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to create payment: {str(e)}"}


# Mark Payment as Paid
@frappe.whitelist(allow_guest=True)
def mark_payment_paid():
    """Mark a payment as paid and update company subscription"""
    try:
        user_info = get_user_from_token()
        data = get_json_data() or {}
        
        payment_id = data.get("payment_id", "")
        payment_method = data.get("payment_method", "")
        transaction_ref = data.get("transaction_ref", "")
        
        if not payment_id:
            return {"success": False, "message": "Missing payment_id"}
        
        if not frappe.db.exists("Payment", payment_id):
            return {"success": False, "message": "Payment not found"}
        
        payment_doc = frappe.get_doc("Payment", payment_id)
        company = frappe.get_doc("Logistics Company", payment_doc.company_name)
        
        is_manager = company.manager_email == user_info.get("email", "")
        is_admin = user_info.get("role", "") == "Admin"
        
        if not (is_manager or is_admin):
            return {"success": False, "message": "You don't have permission"}
        
        payment_doc.payment_status = "Paid"
        payment_doc.paid_date = datetime.now()
        
        if payment_method:
            payment_doc.payment_method = payment_method
        
        if transaction_ref:
            payment_doc.notes = f"{payment_doc.notes or ''}\nTransaction Ref: {transaction_ref}"
        
        payment_doc.save(ignore_permissions=True)
        
        # Update company subscription
        if payment_doc.payment_type == "Subscription":
            company.subscription_plan = payment_doc.subscription_plan
            company.subscription_start_date = payment_doc.billing_period_start
            company.subscription_end_date = payment_doc.billing_period_end
            company.is_active = 1
            company.requests_viewed_this_month = 0
            company.updated_at = datetime.now()
            company.save(ignore_permissions=True)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Payment marked as paid successfully",
            "data": {
                "payment_id": payment_doc.name,
                "receipt_number": payment_doc.receipt_number,
                "subscription_plan": payment_doc.subscription_plan,
                "valid_until": str(payment_doc.billing_period_end),
                "subscription_updated": True
            }
        }
        
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Mark Payment Paid Error: {str(e)}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed: {str(e)}"}


# Get My Payments
@frappe.whitelist(allow_guest=True)
def get_my_payments():
    """Get all payments for manager's company"""
    try:
        user_info = get_user_from_token()
        
        if user_info.get("role", "") != "Logistics Manager":
            return {"success": False, "message": "Only Logistics Managers can access this"}
        
        companies = frappe.get_all(
            "Logistics Company",
            filters={"manager_email": user_info.get("email", "")},
            fields=["company_name"]
        )
        
        if not companies:
            return {"success": False, "message": "No company found"}
        
        company_name = companies[0].get("company_name")
        
        payments = frappe.get_all(
            "Payment",
            filters={"company_name": company_name},
            fields=[
                "name", "payment_type", "subscription_plan", "amount", "currency",
                "payment_status", "payment_method", "payment_date", "due_date",
                "paid_date", "billing_period_start", "billing_period_end",
                "invoice_number", "receipt_number", "description", "created_at"
            ],
            order_by="created_at desc"
        )
        
        return {
            "success": True,
            "count": len(payments),
            "data": payments
        }
        
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get My Payments Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch payments"}


# Get Payment Detail
@frappe.whitelist(allow_guest=True)
def get_payment_detail():
    """Get detailed information of a payment"""
    try:
        user_info = get_user_from_token()
        data = get_json_data() or {}
        
        payment_id = data.get("payment_id", "")
        
        if not payment_id or not frappe.db.exists("Payment", payment_id):
            return {"success": False, "message": "Payment not found"}
        
        payment_doc = frappe.get_doc("Payment", payment_id)
        company = frappe.get_doc("Logistics Company", payment_doc.company_name)
        
        is_manager = company.manager_email == user_info.get("email", "")
        is_admin = user_info.get("role", "") == "Admin"
        
        if not (is_manager or is_admin):
            return {"success": False, "message": "You don't have permission"}
        
        return {
            "success": True,
            "data": payment_doc.as_dict()
        }
        
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get Payment Detail Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch payment details"}


# Get All Payments (Admin)
@frappe.whitelist(allow_guest=True)
def get_all_payments():
    """Get all payments (Admin only)"""
    try:
        user_info = get_user_from_token()
        
        if user_info.get("role", "") != "Admin":
            return {"success": False, "message": "Only Admins can access"}
        
        data = get_json_data() or {}
        
        filters = {}
        if data.get("company_name"):
            filters["company_name"] = data.get("company_name")
        if data.get("payment_status"):
            filters["payment_status"] = data.get("payment_status")
        if data.get("subscription_plan"):
            filters["subscription_plan"] = data.get("subscription_plan")
        
        payments = frappe.get_all(
            "Payment",
            filters=filters,
            fields=[
                "name", "company_name", "manager_email", "payment_type",
                "subscription_plan", "amount", "currency", "payment_status",
                "payment_method", "payment_date", "due_date", "paid_date",
                "billing_period_start", "billing_period_end", "invoice_number",
                "receipt_number", "created_at"
            ],
            order_by="created_at desc"
        )
        
        total_revenue = sum([p.amount for p in payments if p.payment_status == "Paid"])
        pending_amount = sum([p.amount for p in payments if p.payment_status == "Pending"])
        
        return {
            "success": True,
            "count": len(payments),
            "statistics": {
                "total_payments": len(payments),
                "total_revenue": total_revenue,
                "pending_amount": pending_amount,
                "paid_count": len([p for p in payments if p.payment_status == "Paid"]),
                "pending_count": len([p for p in payments if p.payment_status == "Pending"])
            },
            "data": payments
        }
        
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get All Payments Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch payments"}


# Cancel Payment
@frappe.whitelist(allow_guest=True)
def cancel_payment():
    """Cancel a pending payment"""
    try:
        user_info = get_user_from_token()
        data = get_json_data() or {}
        
        payment_id = data.get("payment_id", "")
        reason = data.get("reason", "")
        
        if not payment_id or not frappe.db.exists("Payment", payment_id):
            return {"success": False, "message": "Payment not found"}
        
        payment_doc = frappe.get_doc("Payment", payment_id)
        company = frappe.get_doc("Logistics Company", payment_doc.company_name)
        
        is_manager = company.manager_email == user_info.get("email", "")
        is_admin = user_info.get("role", "") == "Admin"
        
        if not (is_manager or is_admin):
            return {"success": False, "message": "You don't have permission"}
        
        if payment_doc.payment_status == "Paid":
            return {"success": False, "message": "Cannot cancel paid payment"}
        
        payment_doc.payment_status = "Cancelled"
        payment_doc.updated_at = datetime.now()
        
        if reason:
            payment_doc.notes = f"{payment_doc.notes or ''}\nCancellation Reason: {reason}"
        
        payment_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Payment cancelled successfully"
        }
        
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Cancel Payment Error: {str(e)}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed: {str(e)}"}


# Get Subscription Status
@frappe.whitelist(allow_guest=True)
def get_subscription_status():
    """Get current subscription status for manager's company"""
    try:
        user_info = get_user_from_token()
        
        if user_info.get("role", "") != "Logistics Manager":
            return {"success": False, "message": "Only Logistics Managers can access"}
        
        companies = frappe.get_all(
            "Logistics Company",
            filters={"manager_email": user_info.get("email", "")},
            fields=[
                "company_name", "subscription_plan", "subscription_start_date",
                "subscription_end_date", "is_active", "requests_viewed_this_month"
            ]
        )
        
        if not companies:
            return {"success": False, "message": "No company found"}
        
        company = companies[0]
        plan = company.get("subscription_plan", "Free")
        plan_details = PLAN_PRICING.get(plan, PLAN_PRICING["Free"])
        
        days_remaining = None
        if company.get("subscription_end_date"):
            days_remaining = (company.get("subscription_end_date") - datetime.now().date()).days
        
        return {
            "success": True,
            "subscription": {
                "plan": plan,
                "is_active": company.get("is_active"),
                "start_date": str(company.get("subscription_start_date")) if company.get("subscription_start_date") else None,
                "end_date": str(company.get("subscription_end_date")) if company.get("subscription_end_date") else None,
                "days_remaining": days_remaining,
                "requests_used": company.get("requests_viewed_this_month", 0),
                "request_limit": plan_details["features"]["request_limit"],
                "features": plan_details["features"]
            },
            "pricing": {
                "monthly": plan_details["monthly"],
                "yearly": plan_details["yearly"]
            }
        }
        
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get Subscription Status Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch status"}