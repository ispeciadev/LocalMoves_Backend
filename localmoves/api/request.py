import json
import frappe
from frappe import _
from localmoves.utils.jwt_handler import get_current_user
from datetime import datetime
from localmoves.api.request_pricing import calculate_comprehensive_price



# Subscription Plan Limits
PLAN_LIMITS = {
    "Basic": 20,
    "Standard": 50,
    "Premium": -1  # Unlimited
}

def safe_get_dict_value(dictionary, key, default=None):
    """Safely get value from dictionary, handling None cases"""
    # CRITICAL FIX: Check if dictionary is None OR not a dict BEFORE calling .get()
    if dictionary is None:
        return default
    if not isinstance(dictionary, dict):
        return default
    
    # Now it's safe to call .get()
    return dictionary.get(key, default)

def get_user_from_token():
    """Extract user from JWT token"""
    try:
        token = frappe.get_request_header("Authorization")
        if not token:
            frappe.throw(_("No token provided"))
        
        if token.startswith("Bearer "):
            token = token[7:]
        
        user_info = get_current_user(token)
        
        if not user_info:
            frappe.throw(_("Invalid token: No user information returned"))
        
        if not isinstance(user_info, dict):
            frappe.throw(_("Invalid token data format"))
            
        return user_info
        
    except Exception as e:
        frappe.log_error(f"get_user_from_token error: {str(e)}")
        frappe.throw(_("Authentication failed"))

# def get_json_data():
#     """Force parse JSON even if frappe.request fails - ALWAYS RETURN DICT"""
#     try:
#         data = {}
        
#         # Try frappe.request.get_json first
#         if hasattr(frappe, "request") and frappe.request:
#             data = frappe.request.get_json(force=True, silent=True) or {}
        
#         # If still empty, try parsing raw data
#         if not data and hasattr(frappe, "request") and hasattr(frappe.request, "get_data"):
#             raw = frappe.request.get_data(as_text=True)
#             if raw and raw.strip():
#                 try:
#                     data = json.loads(raw)
#                 except json.JSONDecodeError:
#                     # If JSON parsing fails, try form data
#                     pass
        
#         # Try form_dict as fallback
#         if not data and hasattr(frappe, "form_dict") and frappe.form_dict:
#             data = dict(frappe.form_dict)
        
#         return data or {}  # Ensure we always return a dict
        
#     except Exception as e:
#         frappe.log_error(f"get_json_data error: {str(e)}")
#         return {}  # Always return empty dict on error

def get_json_data():
    """Force parse JSON even if frappe.request fails - ALWAYS RETURN DICT"""
    try:
        data = {}
        
        # Try frappe.request.get_json first
        if hasattr(frappe, "request") and frappe.request:
            try:
                data = frappe.request.get_json(force=True, silent=True)
                if data is None:
                    data = {}
            except:
                data = {}
        
        # If still empty, try parsing raw data
        if not data and hasattr(frappe, "request") and hasattr(frappe.request, "get_data"):
            try:
                raw = frappe.request.get_data(as_text=True)
                if raw and raw.strip():
                    data = json.loads(raw)
                    if data is None:
                        data = {}
            except:
                pass
        
        # Try form_dict as fallback
        if not data and hasattr(frappe, "form_dict") and frappe.form_dict:
            data = dict(frappe.form_dict)
        
        # CRITICAL: Final safety check
        if data is None or not isinstance(data, dict):
            data = {}
        
        return data
        
    except Exception as e:
        frappe.log_error(f"get_json_data error: {str(e)}")
        return {}  # Always return empty dict on error

def reset_monthly_view_counts():
    """Reset view counts for all companies at month start (call via scheduler)"""
    try:
        frappe.db.sql("""
            UPDATE `tabLogistics Company`
            SET requests_viewed_this_month = 0
        """)
        frappe.db.commit()
        return {"success": True, "message": "Monthly view counts reset"}
    except Exception as e:
        frappe.log_error(f"Reset view counts error: {str(e)}")
        return {"success": False, "message": str(e)}

def check_subscription_active(company_name):
    """Check if company has an active subscription"""
    try:
        if not company_name:
            return {"active": False, "reason": "no_company", "message": "No company specified"}
        
        if not frappe.db.exists("Logistics Company", company_name):
            return {"active": False, "reason": "not_found", "message": f"Company '{company_name}' not found"}
        
        company = frappe.get_doc("Logistics Company", company_name)
        
        if not getattr(company, 'is_active', False):
            return {"active": False, "reason": "inactive", "message": "Company account is inactive"}
        
        end_date = getattr(company, 'subscription_end_date', None)
        if end_date:
            today = datetime.now().date()
            if end_date < today:
                return {
                    "active": False, 
                    "reason": "expired", 
                    "message": "Subscription has expired",
                    "expired_date": str(end_date)
                }
        
        return {
            "active": True,
            "plan": getattr(company, 'subscription_plan', 'Basic'),
            "end_date": str(end_date) if end_date else None
        }
        
    except Exception as e:
        frappe.log_error(f"check_subscription_active error: {str(e)}")
        return {"active": False, "reason": "error", "message": "Unable to verify subscription"}

def check_view_limit(company_name):
    """Check if company has exceeded their view limit"""
    try:
        if not company_name:
            return {
                "allowed": False, "remaining": 0, "limit": 10, "viewed": 0,
                "subscription_status": {"active": False, "reason": "no_company"}
            }
        
        if not frappe.db.exists("Logistics Company", company_name):
            return {
                "allowed": False, "remaining": 0, "limit": 10, "viewed": 0,
                "subscription_status": {"active": False, "reason": "not_found"}
            }
        
        company = frappe.get_doc("Logistics Company", company_name)
        subscription_check = check_subscription_active(company_name)
        
        if not safe_get_dict_value(subscription_check, "active", False):
            return {
                "allowed": False, "remaining": 0, "limit": 0, "viewed": 0,
                "subscription_status": subscription_check
            }
        
        plan = getattr(company, 'subscription_plan', 'Basic')
        limit = PLAN_LIMITS.get(plan, 10)
        
        if limit == -1:
            return {
                "allowed": True, "remaining": -1, "limit": -1, "viewed": 0,
                "subscription_status": subscription_check
            }
        
        viewed = getattr(company, 'requests_viewed_this_month', 0) or 0
        
        return {
            "allowed": viewed < limit,
            "remaining": max(0, limit - viewed),
            "limit": limit,
            "viewed": viewed,
            "subscription_status": subscription_check
        }
        
    except Exception as e:
        frappe.log_error(f"check_view_limit error: {str(e)}")
        return {
            "allowed": False, "remaining": 0, "limit": 10, "viewed": 0,
            "subscription_status": {"active": False, "reason": "error"}
        }

def increment_view_count(company_name):
    """Increment the view count for a company"""
    try:
        if company_name and frappe.db.exists("Logistics Company", company_name):
            company = frappe.get_doc("Logistics Company", company_name)
            current_count = getattr(company, 'requests_viewed_this_month', 0) or 0
            company.requests_viewed_this_month = current_count + 1
            company.save(ignore_permissions=True)
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"increment_view_count error: {str(e)}")

def unassign_request_from_company(request_id, original_company=None):
    """Unassign a request and mark who it belonged to"""
    try:
        request_doc = frappe.get_doc("Logistics Request", request_id)
        
        if original_company:
            request_doc.previously_assigned_to = original_company
        
        request_doc.company_name = None
        request_doc.status = "Pending"
        request_doc.assigned_date = None
        request_doc.save(ignore_permissions=True)
        frappe.db.commit()
        return True
    except Exception as e:
        frappe.log_error(f"Unassign request error: {str(e)}")
        return False

# Get Manager Requests
# @frappe.whitelist(allow_guest=True)
# def get_manager_requests():
#     """Get requests for manager's company with subscription limits"""
#     try:
#         user_info = get_user_from_token()
#         if safe_get_dict_value(user_info, "role") != "Logistics Manager":
#             return {"success": False, "message": "Only Logistics Managers can access this"}
        
#         companies = frappe.get_all(
#             "Logistics Company",
#             filters={"manager_email": safe_get_dict_value(user_info, "email")},
#             fields=["company_name", "subscription_plan", "requests_viewed_this_month", 
#                    "pincode", "is_active", "subscription_end_date"]
#         )
        
#         if not companies:
#             return {"success": False, "message": "No company found for this manager"}
        
#         company = companies[0]
#         company_name = safe_get_dict_value(company, "company_name")
#         subscription_plan = safe_get_dict_value(company, "subscription_plan", "Basic")
#         pincode = safe_get_dict_value(company, "pincode")
        
#         subscription_check = check_subscription_active(company_name)
        
#         if not safe_get_dict_value(subscription_check, "active", False):
#             all_available_requests = frappe.get_all(
#                 "Logistics Request",
#                 filters={
#                     "pickup_pincode": pincode,
#                     "status": "Pending",
#                     "company_name": ["is", "not set"]
#                 },
#                 fields=[
#                     "name", "pickup_pincode", "delivery_pincode", "pickup_city",
#                     "delivery_city", "status", "priority", "created_at",
#                     "delivery_date", "item_description", "user_email",
#                     "pickup_address", "delivery_address"
#                 ],
#                 order_by="created_at desc"
#             )
            
#             return {
#                 "success": False,
#                 "subscription_warning": True,
#                 "subscription_info": {
#                     "plan": subscription_plan,
#                     "active": False,
#                     "reason": safe_get_dict_value(subscription_check, "reason"),
#                     "message": safe_get_dict_value(subscription_check, "message"),
#                     "expired_date": safe_get_dict_value(subscription_check, "expired_date")
#                 },
#                 "visible_requests": {
#                     "count": 0,
#                     "data": [],
#                     "message": safe_get_dict_value(subscription_check, "message")
#                 },
#                 "available_requests": {
#                     "count": len(all_available_requests),
#                     "data": all_available_requests,
#                     "message": "These requests are available but you need an active subscription to accept them."
#                 }
#             }
        
#         limit_check = check_view_limit(company_name)
#         plan_limit = safe_get_dict_value(limit_check, "limit", 10)
        
#         all_assigned_requests = frappe.get_all(
#             "Logistics Request",
#             filters={"company_name": company_name},
#             fields=[
#                 "name", "pickup_pincode", "delivery_pincode", "pickup_city",
#                 "delivery_city", "item_description", "status", "priority",
#                 "estimated_cost", "actual_cost", "created_at", "delivery_date",
#                 "user_email", "full_name", "phone", "pickup_address",
#                 "delivery_address", "special_instructions", "assigned_date"
#             ],
#             order_by="assigned_date asc, created_at asc"
#         )
        
#         visible_requests = []
#         blurred_requests = []
        
#         if plan_limit == -1:
#             visible_requests = all_assigned_requests
#         else:
#             visible_requests = all_assigned_requests[:plan_limit]
#             blurred_requests_temp = all_assigned_requests[plan_limit:]
            
#             for req in blurred_requests_temp:
#                 unassign_request_from_company(req["name"], original_company=company_name)
                
#                 req["is_blurred"] = True
#                 req["blur_reason"] = f"Request limit exceeded. Upgrade to {('Premium' if subscription_plan == 'Standard' else 'Standard or Premium')} to reclaim."
#                 req["item_description"] = "*** BLURRED - Upgrade Plan ***"
#                 req["user_email"] = "*** HIDDEN ***"
#                 req["user_name"] = "*** HIDDEN ***"
#                 req["user_phone"] = "*** HIDDEN ***"
#                 req["pickup_address"] = "*** HIDDEN ***"
#                 req["delivery_address"] = "*** HIDDEN ***"
#                 req["special_instructions"] = "*** HIDDEN ***"
#                 req["company_name"] = None
                
#                 blurred_requests.append(req)
        
#         all_available_requests = frappe.get_all(
#             "Logistics Request",
#             filters={
#                 "pickup_pincode": pincode,
#                 "status": "Pending",
#                 "company_name": ["is", "not set"]
#             },
#             fields=[
#                 "name", "pickup_pincode", "delivery_pincode", "pickup_city",
#                 "delivery_city", "status", "priority", "created_at",
#                 "delivery_date", "item_description", "user_email",
#                 "pickup_address", "delivery_address"
#             ],
#             order_by="created_at desc"
#         )
        
#         reclaimable_requests = []
#         other_available_requests = []
        
#         has_tracking_field = frappe.db.has_column("Logistics Request", "previously_assigned_to")
        
#         if has_tracking_field:
#             for req in all_available_requests:
#                 req_doc = frappe.get_doc("Logistics Request", req["name"])
#                 if hasattr(req_doc, 'previously_assigned_to') and getattr(req_doc, 'previously_assigned_to', None) == company_name:
#                     reclaimable_requests.append(req)
#                 else:
#                     other_available_requests.append(req)
#         else:
#             other_available_requests = all_available_requests
        
#         all_available = other_available_requests + reclaimable_requests
        
#         return {
#             "success": True,
#             "subscription_info": {
#                 "plan": subscription_plan,
#                 "active": True,
#                 "limit": plan_limit,
#                 "viewed": len(visible_requests),
#                 "remaining": max(0, plan_limit - len(visible_requests)) if plan_limit != -1 else -1,
#                 "exceeded": len(all_assigned_requests) > plan_limit if plan_limit != -1 else False,
#                 "end_date": safe_get_dict_value(subscription_check, "end_date")
#             },
#             "visible_requests": {
#                 "count": len(visible_requests),
#                 "data": visible_requests,
#                 "message": "These requests are fully visible to you"
#             },
#             "blurred_requests": {
#                 "count": len(blurred_requests),
#                 "data": blurred_requests,
#                 "message": f"⚠️ {len(blurred_requests)} requests unassigned due to plan limit. Upgrade to reclaim them before others accept!" if blurred_requests else None
#             },
#             "available_requests": {
#                 "count": len(all_available),
#                 "data": all_available,
#                 "message": "These requests are available in your pincode. Accept them to assign to your company."
#             },
#             "reclaimable_requests": {
#                 "count": len(reclaimable_requests),
#                 "data": reclaimable_requests,
#                 "message": f"🎯 {len(reclaimable_requests)} of your previous requests are still available! You can reclaim them if you have capacity." if reclaimable_requests else None,
#                 "can_reclaim": safe_get_dict_value(limit_check, "remaining", 0) > 0
#             }
#         }
#     except frappe.AuthenticationError as e:
#         return {"success": False, "message": str(e)}
#     except Exception as e:
#         frappe.log_error(f"Get Manager Requests Error: {str(e)}")
#         return {"success": False, "message": f"Failed to fetch requests: {str(e)}"}

# Get Manager Requests - FIXED to include pending-for-company in blurred
# Get Manager Requests - FIXED to include pending-for-company in blurred
# Get Manager Requests - COMPLETE FIX with exclusion logic
# Add this new function to calculate request statistics
def calculate_request_statistics(company_name):
    """Calculate statistics for pending, confirmed, and completed requests with average prices"""
    try:
        # Get all requests for this company
        all_requests = frappe.get_all(
            "Logistics Request",
            filters={"company_name": company_name},
            fields=["status", "remaining_amount", "total_amount", "estimated_cost"]
        )
        
        # Initialize counters
        stats = {
            "pending_count": 0,
            "confirmed_count": 0,
            "completed_count": 0,
            "total_requests": len(all_requests),
            "overall_avg_remaining": 0
        }
        
        # Categorize requests
        pending_amounts = []
        confirmed_amounts = []
        completed_amounts = []
        all_amounts = []
        
        for req in all_requests:
            status = req.get('status', '').lower()
            remaining = float(req.get('remaining_amount') or 0)
            
            # If remaining_amount is 0, use total_amount or estimated_cost
            if remaining == 0:
                remaining = float(req.get('total_amount') or req.get('estimated_cost') or 0)
            
            all_amounts.append(remaining)
            
            # Categorize by status
            if status in ['pending']:
                stats['pending_count'] += 1
                pending_amounts.append(remaining)
            elif status in ['assigned', 'accepted', 'in progress']:
                stats['confirmed_count'] += 1
                confirmed_amounts.append(remaining)
            elif status in ['completed']:
                stats['completed_count'] += 1
                completed_amounts.append(remaining)
        
        # Calculate averages
        stats['overall_avg_remaining'] = round(sum(all_amounts) / len(all_amounts), 2) if all_amounts else 0
        
        return stats
        
    except Exception as e:
        frappe.log_error(f"Calculate statistics error: {str(e)}")
        return {
            "pending_count": 0,
            "confirmed_count": 0,
            "completed_count": 0,
            "total_requests": 0,
            "overall_avg_remaining": 0
        }


# MODIFIED get_manager_requests with statistics
@frappe.whitelist(allow_guest=True)
def get_manager_requests():
    """Get requests for manager's company with subscription limits and statistics"""
    try:
        user_info = get_user_from_token()
        if safe_get_dict_value(user_info, "role") != "Logistics Manager":
            return {"success": False, "message": "Only Logistics Managers can access this"}
        
        companies = frappe.get_all(
            "Logistics Company",
            filters={"manager_email": safe_get_dict_value(user_info, "email")},
            fields=["company_name", "subscription_plan", "requests_viewed_this_month", 
                   "pincode", "is_active", "subscription_end_date"]
        )
        
        if not companies:
            return {"success": False, "message": "No company found for this manager"}
        
        company = companies[0]
        company_name = safe_get_dict_value(company, "company_name")
        subscription_plan = safe_get_dict_value(company, "subscription_plan", "Basic")
        pincode = safe_get_dict_value(company, "pincode")
        
        subscription_check = check_subscription_active(company_name)
        
        # 🆕 CALCULATE STATISTICS
        request_stats = calculate_request_statistics(company_name)
        
        # If subscription inactive, show available requests but no access
        if not safe_get_dict_value(subscription_check, "active", False):
            all_available_requests = frappe.get_all(
                "Logistics Request",
                filters={
                    "pickup_pincode": pincode,
                    "status": "Pending",
                    "company_name": ["is", "not set"]
                },
                fields=[
                    "name", "pickup_pincode", "delivery_pincode", "pickup_city",
                    "delivery_city", "status", "priority", "created_at",
                    "delivery_date", "item_description", "user_email",
                    "pickup_address", "delivery_address"
                ],
                order_by="created_at desc"
            )
            
            return {
                "success": False,
                "subscription_warning": True,
                "subscription_info": {
                    "plan": subscription_plan,
                    "active": False,
                    "reason": safe_get_dict_value(subscription_check, "reason"),
                    "message": safe_get_dict_value(subscription_check, "message"),
                    "expired_date": safe_get_dict_value(subscription_check, "expired_date")
                },
                "statistics": request_stats,  # 🆕 Added statistics
                "visible_requests": {
                    "count": 0,
                    "data": [],
                    "message": safe_get_dict_value(subscription_check, "message")
                },
                "available_requests": {
                    "count": len(all_available_requests),
                    "data": all_available_requests,
                    "message": "These requests are available but you need an active subscription to accept them."
                }
            }
        
        limit_check = check_view_limit(company_name)
        plan_limit = safe_get_dict_value(limit_check, "limit", 10)
        
        # Get all ASSIGNED requests
        all_assigned_requests = frappe.get_all(
            "Logistics Request",
            filters={"company_name": company_name},
            fields=[
                "name", "pickup_pincode", "delivery_pincode", "pickup_city",
                "delivery_city", "item_description", "status", "priority",
                "estimated_cost", "actual_cost", "created_at", "delivery_date",
                "user_email", "full_name", "phone", "pickup_address",
                "delivery_address", "special_instructions", "assigned_date",
                "remaining_amount", "total_amount", "payment_status"  # 🆕 Added payment fields
            ],
            order_by="assigned_date asc, created_at asc"
        )
        
        visible_requests = []
        blurred_requests = []
        
        # Split assigned requests into visible and blurred based on plan limit
        if plan_limit == -1:
            visible_requests = all_assigned_requests
        else:
            visible_requests = all_assigned_requests[:plan_limit]
            blurred_requests_temp = all_assigned_requests[plan_limit:]
            
            # Unassign and blur requests that exceed the limit
            for req in blurred_requests_temp:
                unassign_request_from_company(req["name"], original_company=company_name)
                
                req["is_blurred"] = True
                req["blur_reason"] = f"Request limit exceeded. Upgrade to {('Premium' if subscription_plan == 'Standard' else 'Standard or Premium')} to reclaim."
                req["item_description"] = "*** BLURRED - Upgrade Plan ***"
                req["user_email"] = "*** HIDDEN ***"
                req["user_name"] = "*** HIDDEN ***"
                req["user_phone"] = "*** HIDDEN ***"
                req["pickup_address"] = "*** HIDDEN ***"
                req["delivery_address"] = "*** HIDDEN ***"
                req["special_instructions"] = "*** HIDDEN ***"
                req["company_name"] = None
                
                blurred_requests.append(req)
        
        # Add requests that were created for this company but couldn't be assigned
        has_tracking_field = frappe.db.has_column("Logistics Request", "previously_assigned_to")
        
        if has_tracking_field:
            pending_for_company_requests = frappe.db.sql("""
                SELECT name, pickup_pincode, delivery_pincode, pickup_city,
                       delivery_city, status, priority, created_at, delivery_date
                FROM `tabLogistics Request`
                WHERE pickup_pincode = %(pincode)s
                AND status = 'Pending'
                AND (company_name IS NULL OR company_name = '')
                AND previously_assigned_to = %(company_name)s
            """, {"pincode": pincode, "company_name": company_name}, as_dict=True)
            
            for req in pending_for_company_requests:
                req_dict = {
                    "name": req["name"],
                    "pickup_pincode": req["pickup_pincode"],
                    "delivery_pincode": req["delivery_pincode"],
                    "pickup_city": req.get("pickup_city"),
                    "delivery_city": req.get("delivery_city"),
                    "status": req["status"],
                    "priority": req.get("priority"),
                    "created_at": str(req["created_at"]),
                    "delivery_date": str(req["delivery_date"]) if req.get("delivery_date") else None,
                    "is_blurred": True,
                    "blur_reason": "User requested YOU but you were at capacity when they created this request.",
                    "was_requested_for_you": True,
                    "item_description": "*** WAITING FOR CAPACITY - User Requested You ***",
                    "user_email": "*** HIDDEN ***",
                    "pickup_address": "*** HIDDEN ***",
                    "delivery_address": "*** HIDDEN ***",
                    "special_instructions": "*** HIDDEN ***"
                }
                
                blurred_requests.append(req_dict)
        
        # Get IDs of all blurred requests to exclude from available
        blurred_request_ids = [req["name"] for req in blurred_requests]
        
        # Get all available requests in their pincode
        all_available_requests = frappe.get_all(
            "Logistics Request",
            filters={
                "pickup_pincode": pincode,
                "status": "Pending",
                "company_name": ["is", "not set"]
            },
            fields=[
                "name", "pickup_pincode", "delivery_pincode", "pickup_city",
                "delivery_city", "status", "priority", "created_at",
                "delivery_date", "item_description", "user_email",
                "pickup_address", "delivery_address"
            ],
            order_by="created_at desc"
        )
        
        reclaimable_requests = []
        other_available_requests = []
        
        # Categorize available requests
        if has_tracking_field:
            for req in all_available_requests:
                if req["name"] in blurred_request_ids:
                    continue
                
                req_doc = frappe.get_doc("Logistics Request", req["name"])
                prev_assigned = getattr(req_doc, 'previously_assigned_to', None)
                assigned_date = getattr(req_doc, 'assigned_date', None)
                
                if prev_assigned == company_name and assigned_date:
                    reclaimable_requests.append(req)
                else:
                    other_available_requests.append(req)
        else:
            for req in all_available_requests:
                if req["name"] not in blurred_request_ids:
                    other_available_requests.append(req)
        
        all_available = other_available_requests + reclaimable_requests
        
        return {
            "success": True,
            "subscription_info": {
                "plan": subscription_plan,
                "active": True,
                "limit": plan_limit,
                "viewed": len(visible_requests),
                "remaining": max(0, plan_limit - len(visible_requests)) if plan_limit != -1 else -1,
                "exceeded": len(all_assigned_requests) > plan_limit if plan_limit != -1 else False,
                "end_date": safe_get_dict_value(subscription_check, "end_date")
            },
            "statistics": request_stats,  # 🆕 Added comprehensive statistics
            "visible_requests": {
                "count": len(visible_requests),
                "data": visible_requests,
                "message": "These requests are fully visible to you"
            },
            "blurred_requests": {
                "count": len(blurred_requests),
                "data": blurred_requests,
                "message": f"⚠️ {len(blurred_requests)} requests need your attention. Some exceeded your limit, others were created specifically for you but you were at capacity. Upgrade to view and accept them!" if blurred_requests else None
            },
            "available_requests": {
                "count": len(all_available),
                "data": all_available,
                "message": "These requests are available in your pincode. Accept them to assign to your company."
            },
            "reclaimable_requests": {
                "count": len(reclaimable_requests),
                "data": reclaimable_requests,
                "message": f"🎯 {len(reclaimable_requests)} of your previous requests are still available! You can reclaim them if you have capacity." if reclaimable_requests else None,
                "can_reclaim": safe_get_dict_value(limit_check, "remaining", 0) > 0
            }
        }
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get Manager Requests Error: {str(e)}")
        return {"success": False, "message": f"Failed to fetch requests: {str(e)}"}
        
# Accept Available Request - FIXED VERSION
# @frappe.whitelist(allow_guest=True)
# def accept_available_request():
#     """Manager accepts an available request from their pincode - FIXED VERSION"""
#     try:
#         # Step 1: Authentication
#         user_info = get_user_from_token()
#         if not user_info:
#             return {"success": False, "message": "Authentication failed"}
        
#         user_role = safe_get_dict_value(user_info, "role")
#         user_email = safe_get_dict_value(user_info, "email")
        
#         if user_role != "Logistics Manager":
#             return {"success": False, "message": "Only Logistics Managers can accept requests"}
        
#         # Step 2: Get request data with better validation
#         data = get_json_data()
#         frappe.log_error(f"Accept Request - Raw data received: {data}")  # Debug log
        
#         if not data or not isinstance(data, dict):
#             return {"success": False, "message": "No valid data provided"}
        
#         request_id = safe_get_dict_value(data, "request_id")
#         estimated_cost = safe_get_dict_value(data, "estimated_cost")
        
#         if not request_id:
#             return {"success": False, "message": "Missing request_id"}
        
#         # Step 3: Get manager's company
#         companies = frappe.get_all(
#             "Logistics Company",
#             filters={"manager_email": user_email},
#             fields=["company_name", "subscription_plan", "requests_viewed_this_month", "pincode", "is_active"]
#         )
        
#         if not companies:
#             return {"success": False, "message": "No company found for this manager"}
        
#         company_data = companies[0]
#         company_name = safe_get_dict_value(company_data, "company_name")
#         company_pincode = safe_get_dict_value(company_data, "pincode")
        
#         if not company_name:
#             return {"success": False, "message": "Invalid company data"}
        
#         # Step 4: Check subscription status
#         subscription_check = check_subscription_active(company_name)
#         if not safe_get_dict_value(subscription_check, "active", False):
#             return {
#                 "success": False,
#                 "message": safe_get_dict_value(subscription_check, "message", "Subscription issue"),
#                 "subscription_expired": True
#             }
        
#         # Step 5: Check request exists and is valid
#         if not frappe.db.exists("Logistics Request", request_id):
#             return {"success": False, "message": "Request not found"}
        
#         request_doc = frappe.get_doc("Logistics Request", request_id)
        
#         # Step 6: Validate request conditions
#         if getattr(request_doc, 'pickup_pincode', None) != company_pincode:
#             return {"success": False, "message": "Request not in your service area"}
        
#         if getattr(request_doc, 'status', None) != "Pending":
#             return {"success": False, "message": f"Request not available (status: {getattr(request_doc, 'status', 'Unknown')})"}
        
#         if getattr(request_doc, 'company_name', None):
#             return {"success": False, "message": "Request already assigned"}
        
#         # Step 7: Check subscription limit
#         limit_check = check_view_limit(company_name)
#         if not safe_get_dict_value(limit_check, "allowed", False):
#             was_previously_theirs = (
#                 hasattr(request_doc, 'previously_assigned_to') and 
#                 getattr(request_doc, 'previously_assigned_to', None) == company_name
#             )
            
#             message = (
#                 f"You still don't have capacity. You're at {safe_get_dict_value(limit_check, 'viewed', 0)}/{safe_get_dict_value(limit_check, 'limit', 0)} requests. Upgrade to reclaim."
#                 if was_previously_theirs
#                 else f"You have reached your plan limit ({safe_get_dict_value(limit_check, 'limit', 0)} requests/month). Upgrade to accept more."
#             )
            
#             return {
#                 "success": False,
#                 "message": message,
#                 "limit_exceeded": True,
#                 "was_yours": was_previously_theirs
#             }
        
#         # Step 8: ACCEPT THE REQUEST
#         request_doc.company_name = company_name
#         request_doc.status = "Assigned"
#         request_doc.assigned_date = datetime.now()
#         request_doc.updated_at = datetime.now()
        
#         if hasattr(request_doc, 'previously_assigned_to'):
#             request_doc.previously_assigned_to = None
        
#         if estimated_cost:
#             try:
#                 request_doc.estimated_cost = float(estimated_cost)
#             except (ValueError, TypeError):
#                 frappe.log_error(f"Invalid estimated_cost: {estimated_cost}")
        
#         request_doc.save(ignore_permissions=True)
        
#         increment_view_count(company_name)
        
#         frappe.db.commit()
        
#         # Step 9: Return success
#         was_previously_theirs = (
#             hasattr(request_doc, 'previously_assigned_to') and 
#             getattr(request_doc, 'previously_assigned_to', None) == company_name
#         )
        
#         return {
#             "success": True,
#             "message": f"Request {'reclaimed' if was_previously_theirs else 'accepted'} successfully!",
#             "data": {
#                 "request_id": request_doc.name,
#                 "status": request_doc.status,
#                 "company_name": company_name
#             }
#         }
        
#     except frappe.AuthenticationError as e:
#         return {"success": False, "message": f"Authentication error: {str(e)}"}
#     except Exception as e:
#         frappe.log_error(f"accept_available_request error: {str(e)}")
#         frappe.db.rollback()
#         return {"success": False, "message": f"Failed to accept request: {str(e)}"}


# accept Available Request
# Accept Available Request - SQL VERSION (More Reliable)
@frappe.whitelist(allow_guest=True)
def accept_available_request():
    """Manager accepts an available request - SQL VERSION"""
    try:
        # Authentication
        user_info = get_user_from_token()
        if not user_info:
            return {"success": False, "message": "Authentication failed"}
        
        user_role = safe_get_dict_value(user_info, "role")
        user_email = safe_get_dict_value(user_info, "email")
        
        if user_role != "Logistics Manager":
            return {"success": False, "message": "Only Logistics Managers can accept requests"}
        
        # Get request data
        data = get_json_data()
        
        if data is None or not isinstance(data, dict):
            return {"success": False, "message": "Invalid request data"}
        
        request_id = data.get("request_id")
        estimated_cost = data.get("estimated_cost")
        
        if not request_id:
            return {"success": False, "message": "Missing request_id"}
        
        # Get manager's company
        companies = frappe.get_all(
            "Logistics Company",
            filters={"manager_email": user_email},
            fields=["company_name", "subscription_plan", "requests_viewed_this_month", "pincode", "is_active"]
        )
        
        if not companies:
            return {"success": False, "message": "No company found for this manager"}
        
        company_data = companies[0]
        company_name = company_data.get("company_name")
        company_pincode = company_data.get("pincode")
        
        if not company_name:
            return {"success": False, "message": "Invalid company data"}
        
        # Check subscription
        subscription_check = check_subscription_active(company_name)
        if not subscription_check.get("active", False):
            return {
                "success": False,
                "message": subscription_check.get("message", "Subscription issue"),
                "subscription_expired": True
            }
        
        # Check request exists
        if not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        # Get request info using SQL
        request_info = frappe.db.get_value(
            "Logistics Request",
            request_id,
            ["pickup_pincode", "status", "company_name", "previously_assigned_to"],
            as_dict=True
        )
        
        if not request_info:
            return {"success": False, "message": "Request not found"}
        
        # Validate request conditions
        if request_info.get("pickup_pincode") != company_pincode:
            return {"success": False, "message": "Request not in your service area"}
        
        if request_info.get("status") != "Pending":
            return {"success": False, "message": f"Request not available (status: {request_info.get('status')})"}
        
        if request_info.get("company_name"):
            return {"success": False, "message": "Request already assigned"}
        
        # Check subscription limit
        limit_check = check_view_limit(company_name)
        if not limit_check.get("allowed", False):
            was_previously_theirs = request_info.get("previously_assigned_to") == company_name
            
            message = (
                f"You still don't have capacity. Upgrade to reclaim."
                if was_previously_theirs
                else f"Plan limit reached ({limit_check.get('limit', 0)} requests/month). Upgrade to accept more."
            )
            
            return {
                "success": False,
                "message": message,
                "limit_exceeded": True
            }
        
        # UPDATE REQUEST USING SQL (Bypasses versioning)
        now = datetime.now()
        
        update_values = {
            "company_name": company_name,
            "status": "Assigned",
            "assigned_date": now,
            "updated_at": now,
            "previously_assigned_to": None
        }
        
        if estimated_cost:
            try:
                update_values["estimated_cost"] = float(estimated_cost)
            except:
                pass
        
        # Build SQL update
        set_clause = ", ".join([f"`{k}` = %({k})s" for k in update_values.keys()])
        
        frappe.db.sql(f"""
            UPDATE `tabLogistics Request`
            SET {set_clause}
            WHERE name = %(request_id)s
        """, {**update_values, "request_id": request_id})
        
        # Increment view count
        increment_view_count(company_name)
        
        frappe.db.commit()
        
        # Get updated usage
        updated_limit_check = check_view_limit(company_name)
        
        was_reclaimed = request_info.get("previously_assigned_to") == company_name
        
        return {
            "success": True,
            "message": f"Request {'reclaimed' if was_reclaimed else 'accepted'} successfully!",
            "data": {
                "request_id": request_id,
                "status": "Assigned",
                "company_name": company_name,
                "assigned_date": str(now)
            },
            "updated_usage": {
                "used": updated_limit_check.get('viewed', 0),
                "limit": updated_limit_check.get('limit', 0),
                "remaining": updated_limit_check.get('remaining', 0)
            }
        }
        
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "message": f"Failed: {str(e)[:100]}"}

@frappe.whitelist(allow_guest=True)
def bulk_reclaim_requests():
    """After upgrade, automatically reclaim all previously assigned requests"""
    try:
        user_info = get_user_from_token()
        
        if safe_get_dict_value(user_info, "role") != "Logistics Manager":
            return {"success": False, "message": "Only Logistics Managers can reclaim requests"}
        
        companies = frappe.get_all(
            "Logistics Company",
            filters={"manager_email": safe_get_dict_value(user_info, "email")},
            fields=["company_name", "subscription_plan", "pincode"]
        )
        
        if not companies:
            return {"success": False, "message": "No company found"}
        
        company = companies[0]
        company_name = safe_get_dict_value(company, "company_name")
        pincode = safe_get_dict_value(company, "pincode")
        
        limit_check = check_view_limit(company_name)
        
        if not safe_get_dict_value(limit_check, "allowed", False):
            return {
                "success": False,
                "message": "You don't have any remaining capacity to reclaim requests.",
                "limit_info": limit_check
            }
        
        previously_theirs = frappe.get_all(
            "Logistics Request",
            filters={
                "pickup_pincode": pincode,
                "status": "Pending",
                "company_name": ["is", "not set"],
                "previously_assigned_to": company_name
            },
            fields=["name", "created_at"],
            order_by="created_at asc",
            limit_page_length=safe_get_dict_value(limit_check, "remaining", 0)
        )
        
        if not previously_theirs:
            return {
                "success": True,
                "message": "No requests available to reclaim. They may have been accepted by other companies.",
                "reclaimed_count": 0
            }
        
        reclaimed_count = 0
        failed_count = 0
        
        for req in previously_theirs:
            try:
                request_doc = frappe.get_doc("Logistics Request", req["name"])
                
                if getattr(request_doc, 'status', None) != "Pending" or getattr(request_doc, 'company_name', None):
                    failed_count += 1
                    continue
                
                request_doc.company_name = company_name
                request_doc.status = "Assigned"
                request_doc.assigned_date = datetime.now()
                if hasattr(request_doc, 'previously_assigned_to'):
                    request_doc.previously_assigned_to = None
                request_doc.save(ignore_permissions=True)
                
                increment_view_count(company_name)
                reclaimed_count += 1
                
            except Exception as e:
                frappe.log_error(f"Reclaim error for {req['name']}: {str(e)}")
                failed_count += 1
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Successfully reclaimed {reclaimed_count} requests!",
            "reclaimed_count": reclaimed_count,
            "failed_count": failed_count,
            "total_available": len(previously_theirs)
        }
        
    except Exception as e:
        frappe.log_error(f"Bulk Reclaim Requests Error: {str(e)}")
        frappe.db.rollback()
        return {"success": False, "message": str(e)}

# View Request Detail
@frappe.whitelist(allow_guest=True)
def get_request_detail():
    """Get detailed information of a request"""
    try:
        user_info = get_user_from_token()
        data = get_json_data()
        
        request_id = safe_get_dict_value(data, "request_id")
        
        if not request_id or not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        request_doc = frappe.get_doc("Logistics Request", request_id)
        
        is_owner = getattr(request_doc, 'user_email', None) == safe_get_dict_value(user_info, "email")
        is_admin = safe_get_dict_value(user_info, "role") == "Admin"
        is_manager = False
        
        if getattr(request_doc, 'company_name', None):
            company = frappe.get_doc("Logistics Company", getattr(request_doc, 'company_name'))
            is_manager = getattr(company, 'manager_email', None) == safe_get_dict_value(user_info, "email")
            
            if is_manager:
                subscription_check = check_subscription_active(getattr(request_doc, 'company_name'))
                if not safe_get_dict_value(subscription_check, "active", False):
                    return {
                        "success": False,
                        "message": safe_get_dict_value(subscription_check, "message"),
                        "subscription_expired": True
                    }
        
        if not (is_owner or is_manager or is_admin):
            return {"success": False, "message": "You don't have permission to view this request"}
        
        return {"success": True, "data": request_doc.as_dict()}
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get Request Detail Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch request details"}

# Update Request Status
@frappe.whitelist(allow_guest=True)
def update_request_status():
    """Update request status (Manager/Admin) - SQL VERSION TO BYPASS VERSIONING BUG"""
    try:
        # Get user
        user_info = get_user_from_token()
        if not user_info:
            return {"success": False, "message": "Authentication failed"}
        
        # Get data
        data = get_json_data()
        if not data:
            data = {}
        
        # Extract fields
        request_id = data.get("request_id") if isinstance(data, dict) else None
        status = data.get("status") if isinstance(data, dict) else None
        notes = data.get("notes") if isinstance(data, dict) else None
        actual_cost = data.get("actual_cost") if isinstance(data, dict) else None
        
        if not request_id:
            return {"success": False, "message": "Missing request_id"}
        if not status:
            return {"success": False, "message": "Missing status"}
        
        # Check request exists
        if not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        # Get request info
        request_info = frappe.db.get_value(
            "Logistics Request",
            request_id,
            ["company_name", "status"],
            as_dict=True
        )
        
        # Get user details
        user_role = user_info.get("role") if isinstance(user_info, dict) else None
        user_email = user_info.get("email") if isinstance(user_info, dict) else None
        
        if not user_role or not user_email:
            return {"success": False, "message": "Invalid user information"}
        
        # Check permissions
        is_admin = user_role == "Admin"
        is_manager = False
        
        company_name = request_info.get('company_name')
        
        if company_name:
            try:
                company = frappe.get_doc("Logistics Company", company_name)
                is_manager = getattr(company, 'manager_email', None) == user_email
                
                if is_manager:
                    subscription_check = check_subscription_active(company_name)
                    if subscription_check and isinstance(subscription_check, dict):
                        if not subscription_check.get("active", False):
                            return {
                                "success": False,
                                "message": subscription_check.get("message", "Subscription inactive"),
                                "subscription_expired": True
                            }
            except Exception as e:
                frappe.log_error(f"Permission check error: {str(e)}")
        
        if not (is_admin or is_manager):
            return {"success": False, "message": "You don't have permission to update this request"}
        
        # Validate status
        valid_statuses = ["Pending", "Assigned", "Accepted", "In Progress", "Completed", "Cancelled", "Rejected"]
        if status not in valid_statuses:
            return {"success": False, "message": f"Invalid status: {status}"}
        
        # CRITICAL FIX: Use direct SQL update to bypass versioning
        update_dict = {
            "status": status,
            "updated_at": frappe.utils.now_datetime(),
            "request_id": request_id
        }
        
        # Build update query
        sql_parts = ["`status` = %(status)s", "`updated_at` = %(updated_at)s"]
        
        if notes:
            field_name = "admin_notes" if is_admin else "notes"
            update_dict[field_name] = notes
            sql_parts.append(f"`{field_name}` = %({field_name})s")
        
        if actual_cost:
            try:
                update_dict["actual_cost"] = float(actual_cost)
                sql_parts.append("`actual_cost` = %(actual_cost)s")
            except (ValueError, TypeError):
                pass
        
        # Execute SQL update
        sql = f"""
            UPDATE `tabLogistics Request`
            SET {', '.join(sql_parts)}
            WHERE name = %(request_id)s
        """
        
        frappe.db.sql(sql, update_dict)
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Request {request_id} updated successfully",
            "data": {
                "request_id": request_id,
                "status": status,
            },
        }
        
    except frappe.AuthenticationError as e:
        return {"success": False, "message": f"Authentication error: {str(e)}"}
    except Exception as e:
        import traceback
        error_msg = f"Update error: {str(e)}"
        frappe.log_error(f"{error_msg}\n{traceback.format_exc()}"[:500], "Update Request Status Error")
        frappe.db.rollback()
        return {"success": False, "message": error_msg[:100]}
    
# get_single_request_detail
@frappe.whitelist(allow_guest=True)
def get_single_request_detail():
    """
    Get detailed information of a single request - ONLY OWNER CAN VIEW
    
    Usage:
    POST /api/method/localmoves.api.request.get_single_request_detail
    Body: {"request_id": "REQ-00123"}
    """
    try:
        # Get authenticated user
        user_info = get_user_from_token()
        if not user_info:
            return {"success": False, "message": "Authentication required"}
        
        # Get request data
        data = get_json_data()
        if not data:
            data = {}
        
        request_id = data.get("request_id") if isinstance(data, dict) else None
        
        if not request_id:
            return {"success": False, "message": "Missing request_id"}
        
        # Check if request exists
        if not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        # Get request document
        request_doc = frappe.get_doc("Logistics Request", request_id)
        
        # Get user email from token
        user_email = user_info.get("email") if isinstance(user_info, dict) else None
        
        if not user_email:
            return {"success": False, "message": "Invalid user information"}
        
        # CRITICAL: Check if user is the owner of this request
        request_owner_email = getattr(request_doc, 'user_email', None)
        
        if request_owner_email != user_email:
            return {
                "success": False, 
                "message": "Access denied. You can only view your own requests.",
                "error_code": "PERMISSION_DENIED"
            }
        
        # User is the owner - return full details
        request_dict = request_doc.as_dict()
        
        # Parse JSON fields if they exist
        json_fields = [
            'pricing_data', 
            'collection_assessment', 
            'delivery_assessment', 
            'move_date_data', 
            'price_breakdown',
            'property_size'
        ]
        
        for field in json_fields:
            if field in request_dict and request_dict[field]:
                try:
                    if isinstance(request_dict[field], str):
                        request_dict[field] = json.loads(request_dict[field])
                except json.JSONDecodeError:
                    # If JSON parsing fails, leave as string
                    pass
                except Exception:
                    # Any other error, set to None
                    request_dict[field] = None
        
        # Get company details if assigned
        company_details = None
        if request_dict.get('company_name'):
            try:
                company = frappe.get_doc("Logistics Company", request_dict['company_name'])
                company_details = {
                    "company_name": company.company_name,
                    "pincode": getattr(company, 'pincode', None),
                    "manager_email": getattr(company, 'manager_email', None),
                    "phone": getattr(company, 'phone', None),
                    "address": getattr(company, 'address', None)
                }
            except Exception as e:
                frappe.log_error(f"Error fetching company details: {str(e)}")
                company_details = {"error": "Could not load company details"}
        
        return {
            "success": True,
            "message": "Request details retrieved successfully",
            "data": {
                "request": request_dict,
                "company_details": company_details,
                "is_owner": True
            }
        }
        
    except frappe.AuthenticationError as e:
        return {
            "success": False, 
            "message": f"Authentication error: {str(e)}",
            "error_code": "AUTH_ERROR"
        }
    except Exception as e:
        import traceback
        error_msg = f"Failed to fetch request: {str(e)}"
        frappe.log_error(f"{error_msg}\n{traceback.format_exc()}"[:500], "Get Single Request Error")
        return {
            "success": False, 
            "message": error_msg[:100],
            "error_code": "SYSTEM_ERROR"
        }
# Create Request
# @frappe.whitelist(allow_guest=True)
# def create_request():
#     """Create Logistics Request (User Only)"""
#     try:
#         user_info = get_user_from_token()
#         data = get_json_data()

#         full_name = safe_get_dict_value(data, "full_name")
#         email = safe_get_dict_value(data, "email")
#         phone = safe_get_dict_value(data, "phone")
#         property_size = safe_get_dict_value(data, "property_size")
#         pickup_pincode = safe_get_dict_value(data, "pickup_pincode")
#         pickup_address = safe_get_dict_value(data, "pickup_address")
#         pickup_city = safe_get_dict_value(data, "pickup_city")
#         delivery_pincode = safe_get_dict_value(data, "delivery_pincode")
#         delivery_address = safe_get_dict_value(data, "delivery_address")
#         delivery_city = safe_get_dict_value(data, "delivery_city")
#         item_description = safe_get_dict_value(data, "item_description")
#         requested_company_name = safe_get_dict_value(data, "company_name")
#         delivery_date = safe_get_dict_value(data, "delivery_date")
#         service_type = safe_get_dict_value(data, "service_type")
#         special_instructions = safe_get_dict_value(data, "special_instructions")

#         if not all([full_name, email, phone, pickup_pincode, pickup_address, pickup_city,
#                     delivery_pincode, delivery_address, delivery_city, item_description]):
#             return {"success": False, "message": "Missing required fields"}

#         if safe_get_dict_value(user_info, "role") not in ["User", "Admin"]:
#             return {"success": False, "message": "Only Users can create requests"}
        
#         assignment_message = ""
#         final_company_name = None
#         initial_status = "Pending"
        
#         if requested_company_name:
#             if not frappe.db.exists("Logistics Company", requested_company_name):
#                 return {"success": False, "message": "Selected company does not exist"}

#             sub_check = check_subscription_active(requested_company_name)
#             if not safe_get_dict_value(sub_check, "active", False):
#                 return {"success": False, "message": f"Cannot assign to {requested_company_name}. {safe_get_dict_value(sub_check, 'message')}"}
            
#             limit_check = check_view_limit(requested_company_name)
#             if safe_get_dict_value(limit_check, "allowed", False):
#                 final_company_name = requested_company_name
#                 initial_status = "Assigned"
#                 assignment_message = f" and assigned to {requested_company_name}"
#             else:
#                 final_company_name = None
#                 initial_status = "Pending"
#                 assignment_message = f" but {requested_company_name} has reached their limit. Request is pending and available to all companies."
#         else:
#             final_company_name = None
#             initial_status = "Pending"
#             assignment_message = ""

#         request_doc = frappe.get_doc({
#             "doctype": "Logistics Request",
#             "user_email": safe_get_dict_value(user_info, "email"),
#             "full_name": full_name,
#             "email": email,
#             "phone": phone,
#             "property_size": json.dumps(property_size) if isinstance(property_size, (list, dict)) else property_size,
#             "pickup_pincode": pickup_pincode,
#             "pickup_address": pickup_address,
#             "pickup_city": pickup_city,
#             "delivery_pincode": delivery_pincode,
#             "delivery_address": delivery_address,
#             "delivery_city": delivery_city,
#             "item_description": item_description,
#             "delivery_date": delivery_date,
#             "service_type": service_type or "Standard",
#             "special_instructions": special_instructions,
#             "company_name": final_company_name,
#             "status": initial_status,
#             "priority": "Medium",
#             "created_at": datetime.now(),
#             "updated_at": datetime.now(),
#         })

#         if final_company_name and initial_status == "Assigned":
#             request_doc.assigned_date = datetime.now()
#             increment_view_count(final_company_name)

#         request_doc.insert(ignore_permissions=True)
#         frappe.db.commit()

#         return {
#             "success": True,
#             "message": f"Request created successfully{assignment_message}",
#             "data": {
#                 "user email": safe_get_dict_value(user_info, "email"),
#                 "request_id": request_doc.name,
#                 "status": request_doc.status,
#                 "pickup_pincode": request_doc.pickup_pincode,
#                 "delivery_pincode": request_doc.delivery_pincode,
#                 "created_at": str(request_doc.created_at),
#                 "company_name": final_company_name
#             },
#         }
#     except frappe.AuthenticationError as e:
#         return {"success": False, "message": str(e)}
#     except Exception as e:
#         frappe.log_error(f"Create Request Error: {str(e)}")
#         frappe.db.rollback()
#         return {"success": False, "message": f"Failed to create request: {str(e)}"}

# Create Request - FIXED to track blurred requests
# Create Request - FIXED VERSION
# @frappe.whitelist(allow_guest=True)
# def create_request():
#     """Create Logistics Request (User Only) - FIXED"""
#     try:
#         user_info = get_user_from_token()
#         data = get_json_data()

#         full_name = safe_get_dict_value(data, "full_name")
#         email = safe_get_dict_value(data, "email")
#         phone = safe_get_dict_value(data, "phone")
#         property_size = safe_get_dict_value(data, "property_size")
#         pickup_pincode = safe_get_dict_value(data, "pickup_pincode")
#         pickup_address = safe_get_dict_value(data, "pickup_address")
#         pickup_city = safe_get_dict_value(data, "pickup_city")
#         delivery_pincode = safe_get_dict_value(data, "delivery_pincode")
#         delivery_address = safe_get_dict_value(data, "delivery_address")
#         delivery_city = safe_get_dict_value(data, "delivery_city")
#         item_description = safe_get_dict_value(data, "item_description")
#         requested_company_name = safe_get_dict_value(data, "company_name")
#         delivery_date = safe_get_dict_value(data, "delivery_date")
#         service_type = safe_get_dict_value(data, "service_type")
#         special_instructions = safe_get_dict_value(data, "special_instructions")

#         if not all([full_name, email, phone, pickup_pincode, pickup_address, pickup_city,
#                     delivery_pincode, delivery_address, delivery_city, item_description]):
#             return {"success": False, "message": "Missing required fields"}

#         if safe_get_dict_value(user_info, "role") not in ["User", "Admin"]:
#             return {"success": False, "message": "Only Users can create requests"}
        
#         assignment_message = ""
#         final_company_name = None
#         initial_status = "Pending"
#         previously_assigned_to = None
#         assigned_date_value = None  # NEW: Track this separately
        
#         if requested_company_name:
#             if not frappe.db.exists("Logistics Company", requested_company_name):
#                 return {"success": False, "message": "Selected company does not exist"}

#             sub_check = check_subscription_active(requested_company_name)
#             if not safe_get_dict_value(sub_check, "active", False):
#                 return {"success": False, "message": f"Cannot assign to {requested_company_name}. {safe_get_dict_value(sub_check, 'message')}"}
            
#             limit_check = check_view_limit(requested_company_name)
#             print(limit_check)
#             if safe_get_dict_value(limit_check, "allowed", False):
#                 # Company HAS capacity - assign immediately
#                 final_company_name = requested_company_name
#                 initial_status = "Assigned"
#                 assigned_date_value = datetime.now()  # FIXED: Set assigned date
#                 previously_assigned_to = None  # Clear this since it's actually assigned
#                 assignment_message = f" and assigned to {requested_company_name}"
#             else:
#                 # Company at capacity - mark for blurred section
#                 final_company_name = None
#                 initial_status = "Pending"
#                 assigned_date_value = None  # FIXED: No assigned date since never assigned
#                 previously_assigned_to = requested_company_name  # Track who it was meant for
#                 assignment_message = f" but {requested_company_name} has reached their limit ({limit_check.get('viewed', 0)}/{limit_check.get('limit', 0)}). Request will appear in their 'Blurred Requests' section and they can accept it after upgrading."
#         else:
#             # No company requested - general request
#             final_company_name = None
#             initial_status = "Pending"
#             assigned_date_value = None
#             previously_assigned_to = None
#             assignment_message = ""

#         # FIXED: Create the request document with correct field values
#         request_doc = frappe.get_doc({
#             "doctype": "Logistics Request",
#             "user_email": safe_get_dict_value(user_info, "email"),
#             "full_name": full_name,
#             "email": email,
#             "phone": phone,
#             "property_size": json.dumps(property_size) if isinstance(property_size, (list, dict)) else property_size,
#             "pickup_pincode": pickup_pincode,
#             "pickup_address": pickup_address,
#             "pickup_city": pickup_city,
#             "delivery_pincode": delivery_pincode,
#             "delivery_address": delivery_address,
#             "delivery_city": delivery_city,
#             "item_description": item_description,
#             "delivery_date": delivery_date,
#             "service_type": service_type or "Standard",
#             "special_instructions": special_instructions,
#             "company_name": final_company_name,
#             "status": initial_status,
#             "priority": "Medium",
#             "created_at": datetime.now(),
#             "updated_at": datetime.now(),
#             "assigned_date": assigned_date_value,  # FIXED: Set during doc creation
#         })

#         # FIXED: Set previously_assigned_to if field exists
#         if previously_assigned_to and frappe.db.has_column("Logistics Request", "previously_assigned_to"):
#             request_doc.previously_assigned_to = previously_assigned_to

#         # Insert the document
#         request_doc.insert(ignore_permissions=True)
        
#         # FIXED: Only increment count if actually assigned
#         if final_company_name and initial_status == "Assigned":
#             increment_view_count(final_company_name)

#         frappe.db.commit()

#         return {
#             "success": True,
#             "message": f"Request created successfully{assignment_message}",
#             "data": {
#                 "user_email": safe_get_dict_value(user_info, "email"),
#                 "request_id": request_doc.name,
#                 "status": request_doc.status,
#                 "pickup_pincode": request_doc.pickup_pincode,
#                 "delivery_pincode": request_doc.delivery_pincode,
#                 "created_at": str(request_doc.created_at),
#                 "company_name": final_company_name,
#                 "previously_assigned_to": previously_assigned_to,
#                 "will_appear_in_blurred": previously_assigned_to is not None,  # Clear flag for UI
#                 "assigned_date": str(assigned_date_value) if assigned_date_value else None
#             },
#         }
#     except frappe.AuthenticationError as e:
#         return {"success": False, "message": str(e)}
#     except Exception as e:
#         frappe.log_error(f"Create Request Error: {str(e)}")
#         frappe.db.rollback()
#         return {"success": False, "message": f"Failed to create request: {str(e)}"}

# Get My Requests
@frappe.whitelist(allow_guest=True)
def get_my_requests():
    """Get all requests of logged-in user"""
    try:
        user_info = get_user_from_token()
        
        requests = frappe.get_all(
            "Logistics Request",
            filters={"user_email": safe_get_dict_value(user_info, "email")},
            fields=[
                "name", "pickup_pincode", "delivery_pincode", "pickup_city",
                "delivery_city", "item_description", "status", "priority",
                "company_name", "estimated_cost", "actual_cost", "created_at",
                "delivery_date",
            ],
            order_by="created_at desc",
        )
        
        return {"success": True, "count": len(requests), "data": requests}
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get My Requests Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch requests"}

# Assign Request to Company (Admin)
@frappe.whitelist(allow_guest=True)
def assign_request_to_company():
    """Assign request to a company (Admin only)"""
    try:
        user_info = get_user_from_token()
        data = get_json_data()
        
        if safe_get_dict_value(user_info, "role") != "Admin":
            return {"success": False, "message": "Only Admins can assign requests"}
        
        request_id = safe_get_dict_value(data, "request_id")
        company_name = safe_get_dict_value(data, "company_name")
        estimated_cost = safe_get_dict_value(data, "estimated_cost")
        
        if not (request_id and company_name):
            return {"success": False, "message": "Missing request_id or company_name"}
        
        if not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        if not frappe.db.exists("Logistics Company", company_name):
            return {"success": False, "message": "Company not found"}
        
        subscription_check = check_subscription_active(company_name)
        if not safe_get_dict_value(subscription_check, "active", False):
            return {
                "success": False,
                "message": f"Cannot assign to {company_name}. {safe_get_dict_value(subscription_check, 'message')}",
                "subscription_expired": True
            }
        
        limit_check = check_view_limit(company_name)
        if not safe_get_dict_value(limit_check, "allowed", False):
            return {
                "success": False,
                "message": f"{company_name} has reached their plan limit. They need to upgrade.",
                "limit_info": limit_check
            }
        
        request_doc = frappe.get_doc("Logistics Request", request_id)
        request_doc.company_name = company_name
        request_doc.status = "Assigned"
        request_doc.assigned_date = datetime.now()
        request_doc.updated_at = datetime.now()
        
        if estimated_cost:
            request_doc.estimated_cost = estimated_cost
        
        request_doc.save(ignore_permissions=True)
        
        increment_view_count(company_name)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Request assigned successfully",
            "data": {"request_id": request_doc.name, "status": request_doc.status},
        }
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Assign Request Error: {str(e)}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to assign request: {str(e)}"}

# Cancel Request
@frappe.whitelist(allow_guest=True)
def cancel_request():
    """Cancel request (User/Admin)"""
    try:
        user_info = get_user_from_token()
        data = get_json_data()
        
        request_id = safe_get_dict_value(data, "request_id")
        reason = safe_get_dict_value(data, "reason")
        
        if not request_id or not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        request_doc = frappe.get_doc("Logistics Request", request_id)
        
        is_owner = getattr(request_doc, 'user_email', None) == safe_get_dict_value(user_info, "email")
        is_admin = safe_get_dict_value(user_info, "role") == "Admin"
        
        if not (is_owner or is_admin):
            return {"success": False, "message": "You can only cancel your own requests"}
        
        if getattr(request_doc, 'status', None) == "Completed":
            return {"success": False, "message": "Cannot cancel completed request"}
        
        if getattr(request_doc, 'company_name', None):
            try:
                company = frappe.get_doc("Logistics Company", getattr(request_doc, 'company_name'))
                if getattr(company, 'requests_viewed_this_month', 0) > 0:
                    company.requests_viewed_this_month = getattr(company, 'requests_viewed_this_month', 0) - 1
                    company.save(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Decrement view count error on cancel: {str(e)}")
        
        request_doc.status = "Cancelled"
        request_doc.updated_at = datetime.now()
        
        if reason:
            request_doc.special_instructions = f"{getattr(request_doc, 'special_instructions', '')}\nCancellation Reason: {reason}"
        
        request_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {"success": True, "message": "Request cancelled successfully"}
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Cancel Request Error: {str(e)}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to cancel request: {str(e)}"}

# Get Subscription Info for Manager
@frappe.whitelist(allow_guest=True)
def get_quick_subscription_info():
    """Quick check of subscription status for manager"""
    try:
        user_info = get_user_from_token()
        
        if safe_get_dict_value(user_info, "role") != "Logistics Manager":
            return {"success": False, "message": "Only Logistics Managers can access this"}
        
        companies = frappe.get_all(
            "Logistics Company",
            filters={"manager_email": safe_get_dict_value(user_info, "email")},
            fields=["company_name", "subscription_plan", "requests_viewed_this_month", 
                   "is_active", "subscription_end_date"]
        )
        
        if not companies:
            return {"success": False, "message": "No company found for this manager"}
        
        company = companies[0]
        company_name = safe_get_dict_value(company, "company_name")
        
        subscription_check = check_subscription_active(company_name)
        limit_check = check_view_limit(company_name)
        
        return {
            "success": True,
            "company_name": company_name,
            "subscription": {
                "active": safe_get_dict_value(subscription_check, "active", False),
                "plan": safe_get_dict_value(company, "subscription_plan", "Basic"),
                "end_date": str(safe_get_dict_value(company, "subscription_end_date")) if safe_get_dict_value(company, "subscription_end_date") else None,
                "reason": safe_get_dict_value(subscription_check, "reason") if not safe_get_dict_value(subscription_check, "active", False) else None
            },
            "usage": {
                "used": safe_get_dict_value(company, "requests_viewed_this_month", 0),
                "limit": safe_get_dict_value(limit_check, "limit", 10),
                "remaining": safe_get_dict_value(limit_check, "remaining", 0),
                "percentage": round((safe_get_dict_value(company, "requests_viewed_this_month", 0) / safe_get_dict_value(limit_check, "limit", 10) * 100), 2) if safe_get_dict_value(limit_check, "limit", 10) != -1 else 0
            }
        }
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get Quick Subscription Info Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch subscription info"}
    

@frappe.whitelist(allow_guest=True)
def create_request():
    """Create Logistics Request (User Only) - FIXED with Email"""
    try:
        user_info = get_user_from_token()
        data = get_json_data()

        full_name = safe_get_dict_value(data, "full_name")
        email = safe_get_dict_value(data, "email")
        phone = safe_get_dict_value(data, "phone")
        property_size = safe_get_dict_value(data, "property_size")
        pickup_pincode = safe_get_dict_value(data, "pickup_pincode")
        pickup_address = safe_get_dict_value(data, "pickup_address")
        pickup_city = safe_get_dict_value(data, "pickup_city")
        delivery_pincode = safe_get_dict_value(data, "delivery_pincode")
        delivery_address = safe_get_dict_value(data, "delivery_address")
        delivery_city = safe_get_dict_value(data, "delivery_city")
        item_description = safe_get_dict_value(data, "item_description")
        requested_company_name = safe_get_dict_value(data, "company_name")
        delivery_date = safe_get_dict_value(data, "delivery_date")
        service_type = safe_get_dict_value(data, "service_type")
        special_instructions = safe_get_dict_value(data, "special_instructions")

        if not all([full_name, email, phone, pickup_pincode, pickup_address, pickup_city,
                    delivery_pincode, delivery_address, delivery_city, item_description]):
            return {"success": False, "message": "Missing required fields"}

        if safe_get_dict_value(user_info, "role") not in ["User", "Admin"]:
            return {"success": False, "message": "Only Users can create requests"}
        
        assignment_message = ""
        final_company_name = None
        initial_status = "Pending"
        previously_assigned_to = None
        assigned_date_value = None
        
        if requested_company_name:
            if not frappe.db.exists("Logistics Company", requested_company_name):
                return {"success": False, "message": "Selected company does not exist"}

            sub_check = check_subscription_active(requested_company_name)
            if not safe_get_dict_value(sub_check, "active", False):
                return {"success": False, "message": f"Cannot assign to {requested_company_name}. {safe_get_dict_value(sub_check, 'message')}"}
            
            limit_check = check_view_limit(requested_company_name)
            print(limit_check)
            if safe_get_dict_value(limit_check, "allowed", False):
                # Company HAS capacity - assign immediately
                final_company_name = requested_company_name
                initial_status = "Assigned"
                assigned_date_value = datetime.now()
                previously_assigned_to = None
                assignment_message = f" and assigned to {requested_company_name}"
            else:
                # Company at capacity - mark for blurred section
                final_company_name = None
                initial_status = "Pending"
                assigned_date_value = None
                previously_assigned_to = requested_company_name
                assignment_message = f" but {requested_company_name} has reached their limit ({limit_check.get('viewed', 0)}/{limit_check.get('limit', 0)}). Request will appear in their 'Blurred Requests' section and they can accept it after upgrading."
        else:
            # No company requested - general request
            final_company_name = None
            initial_status = "Pending"
            assigned_date_value = None
            previously_assigned_to = None
            assignment_message = ""

        # Create the request document
        request_doc = frappe.get_doc({
            "doctype": "Logistics Request",
            "user_email": safe_get_dict_value(user_info, "email"),
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "property_size": json.dumps(property_size) if isinstance(property_size, (list, dict)) else property_size,
            "pickup_pincode": pickup_pincode,
            "pickup_address": pickup_address,
            "pickup_city": pickup_city,
            "delivery_pincode": delivery_pincode,
            "delivery_address": delivery_address,
            "delivery_city": delivery_city,
            "item_description": item_description,
            "delivery_date": delivery_date,
            "service_type": service_type or "Standard",
            "special_instructions": special_instructions,
            "company_name": final_company_name,
            "status": initial_status,
            "priority": "Medium",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "assigned_date": assigned_date_value,
        })

        # Set previously_assigned_to if field exists
        if previously_assigned_to and frappe.db.has_column("Logistics Request", "previously_assigned_to"):
            request_doc.previously_assigned_to = previously_assigned_to

        # Insert the document
        request_doc.insert(ignore_permissions=True)
        
        # Only increment count if actually assigned
        if final_company_name and initial_status == "Assigned":
            increment_view_count(final_company_name)

        frappe.db.commit()

        # 🔥 SEND CONFIRMATION EMAIL WITH ROUTE MAP
       
        return {
            "success": True,
            "message": f"Request created successfully{assignment_message}. Confirmation email sent to {email}.",
            "data": {
                "user_email": safe_get_dict_value(user_info, "email"),
                "request_id": request_doc.name,
                "status": request_doc.status,
                "pickup_pincode": request_doc.pickup_pincode,
                "delivery_pincode": request_doc.delivery_pincode,
                "created_at": str(request_doc.created_at),
                "company_name": final_company_name,
                "previously_assigned_to": previously_assigned_to,
                "will_appear_in_blurred": previously_assigned_to is not None,
                "assigned_date": str(assigned_date_value) if assigned_date_value else None
            },
        }
    except frappe.AuthenticationError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Create Request Error: {str(e)}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to create request: {str(e)}"}


def send_request_confirmation_email(user_email, user_name, request_id, 
                                    pickup_address, pickup_city, pickup_pincode,
                                    delivery_address, delivery_city, delivery_pincode,
                                    item_description, delivery_date, company_name, status,
                                    property_size=None, service_type="Standard"):
    """Send confirmation email with embedded route map using OpenStreetMap (FREE)"""
    
    # FREE OpenStreetMap route link - No API key needed!
    osm_map_url = f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route={pickup_pincode}%2CIndia;{delivery_pincode}%2CIndia"
    
    # Format property size if it exists
    property_size_html = ""
    if property_size:
        if isinstance(property_size, (list, dict)):
            property_size_display = json.dumps(property_size)
        else:
            property_size_display = str(property_size)
        property_size_html = f'<tr><td style="padding: 8px; font-weight: bold;">Property Size:</td><td style="padding: 8px;">{property_size_display}</td></tr>'
    
    # Email HTML content
    email_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
            🚚 Logistics Request Confirmation
        </h2>
        
        <p>Dear <strong>{user_name}</strong>,</p>
        
        <p>Your logistics request has been created successfully!</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #2c3e50; margin-top: 0;">Request Details</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; font-weight: bold; width: 40%;">Request ID:</td>
                    <td style="padding: 8px;">{request_id}</td>
                </tr>
                <tr style="background-color: white;">
                    <td style="padding: 8px; font-weight: bold;">Status:</td>
                    <td style="padding: 8px;"><span style="background-color: {'#28a745' if status == 'Assigned' else '#ffc107'}; color: white; padding: 3px 10px; border-radius: 3px; font-size: 12px;">{status}</span></td>
                </tr>
                <tr>
                    <td style="padding: 8px; font-weight: bold;">Item Description:</td>
                    <td style="padding: 8px;">{item_description}</td>
                </tr>
                <tr style="background-color: white;">
                    <td style="padding: 8px; font-weight: bold;">Service Type:</td>
                    <td style="padding: 8px;">{service_type}</td>
                </tr>
                {property_size_html}
                {f'<tr style="background-color: white;"><td style="padding: 8px; font-weight: bold;">Assigned Company:</td><td style="padding: 8px;">{company_name}</td></tr>' if company_name else ''}
                {f'<tr><td style="padding: 8px; font-weight: bold;">Expected Delivery:</td><td style="padding: 8px;">{delivery_date}</td></tr>' if delivery_date else ''}
            </table>
        </div>
        
        <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #2c3e50; margin-top: 0;">📍 Pickup Location</h3>
            <p style="margin: 5px 0;"><strong>{pickup_address}</strong></p>
            <p style="margin: 5px 0; color: #666;">{pickup_city}, PIN: {pickup_pincode}</p>
        </div>
        
        <div style="background-color: #ffebee; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="color: #2c3e50; margin-top: 0;">🎯 Delivery Location</h3>
            <p style="margin: 5px 0;"><strong>{delivery_address}</strong></p>
            <p style="margin: 5px 0; color: #666;">{delivery_city}, PIN: {delivery_pincode}</p>
        </div>
        
        <div style="text-align: center; margin: 30px 0;">
            <h3 style="color: #2c3e50;">Route Map</h3>
            <a href="{osm_map_url}" target="_blank" style="display: inline-block; text-decoration: none;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 60px 20px; border-radius: 8px; color: white; font-size: 18px; margin: 10px 0;">
                    🗺️ Click to View Route Map<br/>
                    <span style="font-size: 14px; opacity: 0.9;">From {pickup_city} to {delivery_city}</span>
                </div>
            </a>
            <p style="font-size: 12px; color: #666; margin-top: 10px;">
                Click the map above to view detailed route in your browser
            </p>
        </div>
        
        <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
            <p style="margin: 0; color: #856404;">
                <strong>📱 Track Your Request:</strong> You can track your request status anytime by logging into your account.
            </p>
        </div>
        
        <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
            <p style="color: #666; font-size: 12px;">
                This is an automated email. Please do not reply to this message.<br/>
                For support, contact us at support@localmoves.com
            </p>
        </div>
    </div>
    """
    
    # Send email using Frappe's email system
    try:
        # Send email immediately
        frappe.sendmail(
            recipients=[user_email],
            sender="megha250903@gmail.com",  # Your configured email
            subject=f"Logistics Request Confirmation - {request_id}",
            message=email_content,
            delayed=False,
            now=True
        )
        frappe.logger().info(f"Email sent successfully to {user_email}")
    except Exception as e:
        frappe.log_error(f"Failed to send email to {user_email}: {str(e)}", "Email Send Error")
        pass


# TEST API ENDPOINTS

@frappe.whitelist(allow_guest=True)
def test_email():
    """Test email configuration - sends a simple test email"""
    try:
        data = get_json_data()
        
        # Get recipient email (or use default)
        recipient_email = data.get("email", "megha250903@gmail.com")
        
        # Simple test email
        test_content = """
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                ✅ Email Configuration Test
            </h2>
            
            <p>Hello,</p>
            
            <p>This is a test email from your LocalMoves application.</p>
            
            <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745;">
                <p style="margin: 0; color: #155724;">
                    <strong>✅ Success!</strong> Your email configuration is working correctly.
                </p>
            </div>
            
            <p>You can now send logistics request confirmation emails with route maps!</p>
            
            <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                <p style="color: #666; font-size: 12px;">
                    LocalMoves - Logistics Management System
                </p>
            </div>
        </div>
        """
        
        frappe.sendmail(
            recipients=[recipient_email],
            sender="megha250903@gmail.com",
            subject="Test Email - LocalMoves Configuration",
            message=test_content,
            delayed=False,
            now=True
        )
        
        return {
            "success": True,
            "message": f"Test email sent successfully to {recipient_email}",
            "email": recipient_email
        }
        
    except Exception as e:
        frappe.log_error(f"Test Email Error: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to send test email: {str(e)}"
        }


@frappe.whitelist(allow_guest=True)
def test_email_with_map():
    """Test email with route map - complete simulation"""
    try:
        data = get_json_data()
        
        # Get test data or use defaults
        recipient_email = data.get("email", "megha250903@gmail.com")
        pickup_city = data.get("pickup_city", "Delhi")
        pickup_pincode = data.get("pickup_pincode", "110001")
        delivery_city = data.get("delivery_city", "Mumbai")
        delivery_pincode = data.get("delivery_pincode", "400001")
        
        # Send test email with map
        send_request_confirmation_email(
            user_email=recipient_email,
            user_name="Test User",
            request_id="TEST-REQ-001",
            pickup_address="123 Test Street, Connaught Place",
            pickup_city=pickup_city,
            pickup_pincode=pickup_pincode,
            delivery_address="456 Marine Drive",
            delivery_city=delivery_city,
            delivery_pincode=delivery_pincode,
            item_description="Test Package - Electronics",
            delivery_date="2025-11-20",
            company_name=None,
            status="Pending",
            property_size="2 BHK",
            service_type="Express"
        )
        
        return {
            "success": True,
            "message": f"Test email with route map sent to {recipient_email}",
            "route": f"{pickup_city} ({pickup_pincode}) → {delivery_city} ({delivery_pincode})"
        }
        
    except Exception as e:
        frappe.log_error(f"Test Email with Map Error: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to send test email: {str(e)}"
        }
    
@frappe.whitelist(allow_guest=True)
def create_request_with_detailed_pricing():
    """
    Create Logistics Request with comprehensive pricing calculation
    
    Request Body Structure:
    {
        "user_details": {
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": "+44 1234 567890"
        },
        "addresses": {
            "pickup_address": "123 Main St",
            "pickup_city": "London",
            "pickup_pincode": "SW1A 1AA",
            "delivery_address": "456 Oak Ave",
            "delivery_city": "Manchester",
            "delivery_pincode": "M1 1AA"
        },
        "distance_miles": 200,
        "delivery_date": "2025-12-01",
        "special_instructions": "Handle with care",
        "company_name": "ABC Logistics",  // optional
        
        "pricing_data": {
            "property_type": "house",
            "house_size": "3_bed",
            "additional_spaces": ["shed", "loft"],
            "quantity": "everything",
            "include_dismantling": true,
            "dismantling_items": 5,
            "include_reassembly": true,
            "reassembly_items": 5,
            "include_packing": false
        },
        "collection_assessment": {
            "parking": "driveway",
            "parking_distance": "less_than_5m",
            "external_stairs": "none",
            "floor_level": "ground_floor"
        },
        "delivery_assessment": {
            "parking": "roadside",
            "parking_distance": "10_to_15m",
            "external_stairs": "up_to_5_steps",
            "floor_level": "1st_floor"
        },
        "move_date_data": {
            "notice_period": "within_week",
            "move_day": "sun_to_thurs",
            "collection_time": "9am_to_5pm"
        }
    }
    """
    try:
        user_info = get_user_from_token()
        data = frappe.request.get_json() or {}
        
        # Extract user details
        user_details = data.get('user_details', {})
        full_name = user_details.get('full_name')
        email = user_details.get('email')
        phone = user_details.get('phone')
        
        # Extract addresses
        addresses = data.get('addresses', {})
        pickup_address = addresses.get('pickup_address')
        pickup_city = addresses.get('pickup_city')
        pickup_pincode = addresses.get('pickup_pincode')
        delivery_address = addresses.get('delivery_address')
        delivery_city = addresses.get('delivery_city')
        delivery_pincode = addresses.get('delivery_pincode')
        
        # Validate required fields
        if not all([full_name, email, phone, pickup_address, pickup_city, pickup_pincode,
                   delivery_address, delivery_city, delivery_pincode]):
            return {"success": False, "message": "Missing required fields"}
        
        if safe_get_dict_value(user_info, "role") not in ["User", "Admin"]:
            return {"success": False, "message": "Only Users can create requests"}
        
        # Get optional fields
        delivery_date = data.get('delivery_date')
        special_instructions = data.get('special_instructions')
        requested_company_name = data.get('company_name')
        distance_miles = float(data.get('distance_miles', 0))
        
        # Get pricing data
        pricing_data = data.get('pricing_data', {})
        collection_assessment = data.get('collection_assessment', {})
        delivery_assessment = data.get('delivery_assessment', {})
        move_date_data = data.get('move_date_data', {})
        
        # Generate item description from pricing data
        item_description = generate_item_description(pricing_data)
        
        # Determine assignment
        assignment_message = ""
        final_company_name = None
        initial_status = "Pending"
        previously_assigned_to = None
        assigned_date_value = None
        price_breakdown = None
        
        if requested_company_name:
            if not frappe.db.exists("Logistics Company", requested_company_name):
                return {"success": False, "message": "Selected company does not exist"}
            
            # Check subscription
            sub_check = check_subscription_active(requested_company_name)
            if not safe_get_dict_value(sub_check, "active", False):
                return {
                    "success": False,
                    "message": f"Cannot assign to {requested_company_name}. {safe_get_dict_value(sub_check, 'message')}"
                }
            
            # Check capacity
            limit_check = check_view_limit(requested_company_name)
            
            # Get company for pricing
            company = frappe.get_doc("Logistics Company", requested_company_name)
            
            # Calculate detailed pricing
            price_breakdown = calculate_comprehensive_price({
                'pricing_data': pricing_data,
                'collection_assessment': collection_assessment,
                'delivery_assessment': delivery_assessment,
                'move_date_data': move_date_data,
                'distance_miles': distance_miles
            }, company)
            
            if safe_get_dict_value(limit_check, "allowed", False):
                # Assign immediately
                final_company_name = requested_company_name
                initial_status = "Assigned"
                assigned_date_value = datetime.now()
                previously_assigned_to = None
                assignment_message = f" and assigned to {requested_company_name}"
            else:
                # Mark for blurred section
                final_company_name = None
                initial_status = "Pending"
                assigned_date_value = None
                previously_assigned_to = requested_company_name
                assignment_message = f" but {requested_company_name} has reached their limit. Request will appear in their 'Blurred Requests' section."
        
        # Create request document
        request_doc = frappe.get_doc({
            "doctype": "Logistics Request",
            "user_email": safe_get_dict_value(user_info, "email"),
            "full_name": full_name,
            "email": email,
            "phone": phone,
            
            # Addresses
            "pickup_pincode": pickup_pincode,
            "pickup_address": pickup_address,
            "pickup_city": pickup_city,
            "delivery_pincode": delivery_pincode,
            "delivery_address": delivery_address,
            "delivery_city": delivery_city,
            
            # Move details
            "item_description": item_description,
            "delivery_date": delivery_date,
            "special_instructions": special_instructions,
            
            # Assignment
            "company_name": final_company_name,
            "status": initial_status,
            "priority": "Medium",
            
            # Pricing (store as JSON)
            "pricing_data": json.dumps(pricing_data),
            "collection_assessment": json.dumps(collection_assessment),
            "delivery_assessment": json.dumps(delivery_assessment),
            "move_date_data": json.dumps(move_date_data),
            "distance_miles": distance_miles,
            
            # Price breakdown
            "estimated_cost": price_breakdown['final_total'] if price_breakdown else 0,
            "price_breakdown": json.dumps(price_breakdown) if price_breakdown else None,
            
            # Timestamps
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "assigned_date": assigned_date_value,
        })
        
        # Set previously_assigned_to if needed
        if previously_assigned_to and frappe.db.has_column("Logistics Request", "previously_assigned_to"):
            request_doc.previously_assigned_to = previously_assigned_to
        
        # Insert
        request_doc.insert(ignore_permissions=True)
        
        # Increment view count if assigned
        if final_company_name and initial_status == "Assigned":
            increment_view_count(final_company_name)
        
        frappe.db.commit()
        
        # Send confirmation email
        # try:
        #     send_request_confirmation_email(
        #         user_email=email,
        #         user_name=full_name,
        #         request_id=request_doc.name,
        #         pickup_address=pickup_address,
        #         pickup_city=pickup_city,
        #         pickup_pincode=pickup_pincode,
        #         delivery_address=delivery_address,
        #         delivery_city=delivery_city,
        #         delivery_pincode=delivery_pincode,
        #         item_description=item_description,
        #         delivery_date=delivery_date,
        #         company_name=final_company_name,
        #         status=initial_status,
        #         property_size=pricing_data.get('property_type'),
        #         service_type="Standard"
        #     )
        # except Exception as email_error:
        #     frappe.log_error(f"Email failed for {request_doc.name}: {str(email_error)}")
        
        return {
            "success": True,
            "message": f"Request created successfully{assignment_message}",
            "data": {
                "request_id": request_doc.name,
                "status": request_doc.status,
                "estimated_cost": price_breakdown['final_total'] if price_breakdown else 0,
                "price_breakdown": price_breakdown,
                "company_name": final_company_name,
                "will_appear_in_blurred": previously_assigned_to is not None,
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Create Request Error: {str(e)}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to create request: {str(e)}"}



@frappe.whitelist(allow_guest=True)
def get_all_active_companies():
    """Get list of all active companies - useful for debugging"""
    try:
        companies = frappe.get_all(
            "Logistics Company",
            filters={"is_active": 1},
            fields=[
                "company_name", 
                "pincode", 
                "subscription_plan",
                "manager_email",
                "areas_covered"
            ],
            order_by="created_at desc"
        )
        
        return {
            "success": True,
            "count": len(companies),
            "companies": companies,
            "message": f"Found {len(companies)} active companies"
        }
    except Exception as e:
        frappe.log_error(f"Get Companies Error: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def check_company_exists(company_name=None):
    """Check if a company exists and get its details"""
    try:
        data = frappe.request.get_json() or {}
        company_name = company_name or data.get('company_name')
        
        if not company_name:
            return {"success": False, "message": "company_name is required"}
        
        exists = frappe.db.exists("Logistics Company", company_name)
        
        if not exists:
            return {
                "success": False,
                "exists": False,
                "message": f"Company '{company_name}' does not exist",
                "hint": "Use get_all_active_companies API to see available companies"
            }
        
        company = frappe.get_doc("Logistics Company", company_name)
        
        return {
            "success": True,
            "exists": True,
            "company": {
                "company_name": company.company_name,
                "is_active": company.is_active,
                "pincode": company.pincode,
                "subscription_plan": company.subscription_plan,
                "manager_email": company.manager_email,
                "has_pricing_config": bool(
                    getattr(company, 'base_price_per_mile', None) or
                    getattr(company, 'flat_1_bed_price', None)
                )
            }
        }
    except Exception as e:
        frappe.log_error(f"Check Company Error: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def validate_request_data():
    """Validate request data before creating - helps debug issues"""
    try:
        data = frappe.request.get_json() or {}
        
        validation_results = {
            "user_details": {},
            "addresses": {},
            "pricing_data": {},
            "company": {}
        }
        
        # Validate user details
        user_details = data.get('user_details', {})
        validation_results["user_details"] = {
            "has_full_name": bool(user_details.get('full_name')),
            "has_email": bool(user_details.get('email')),
            "has_phone": bool(user_details.get('phone'))
        }
        
        # Validate addresses
        addresses = data.get('addresses', {})
        validation_results["addresses"] = {
            "has_pickup": bool(addresses.get('pickup_address')),
            "has_pickup_city": bool(addresses.get('pickup_city')),
            "has_pickup_pincode": bool(addresses.get('pickup_pincode')),
            "has_delivery": bool(addresses.get('delivery_address')),
            "has_delivery_city": bool(addresses.get('delivery_city')),
            "has_delivery_pincode": bool(addresses.get('delivery_pincode'))
        }
        
        # Validate pricing data
        pricing_data = data.get('pricing_data', {})
        validation_results["pricing_data"] = {
            "has_property_type": bool(pricing_data.get('property_type')),
            "property_type": pricing_data.get('property_type'),
            "is_valid": pricing_data.get('property_type') in ['house', 'flat', 'office', 'a_few_items']
        }
        
        # Validate company
        company_name = data.get('company_name')
        if company_name:
            exists = frappe.db.exists("Logistics Company", company_name)
            validation_results["company"] = {
                "provided": True,
                "company_name": company_name,
                "exists": exists
            }
            if exists:
                company = frappe.get_doc("Logistics Company", company_name)
                validation_results["company"]["is_active"] = company.is_active
        else:
            validation_results["company"] = {
                "provided": False,
                "message": "No company specified"
            }
        
        # Check overall validity
        all_valid = all([
            validation_results["user_details"].get("has_full_name"),
            validation_results["user_details"].get("has_email"),
            validation_results["user_details"].get("has_phone"),
            validation_results["addresses"].get("has_pickup"),
            validation_results["addresses"].get("has_delivery"),
            validation_results["pricing_data"].get("is_valid"),
            validation_results["company"].get("exists")
        ])
        
        return {
            "success": True,
            "is_valid": all_valid,
            "validation_results": validation_results,
            "message": "Data is valid and ready for request creation" if all_valid else "Data has validation issues"
        }
        
    except Exception as e:
        frappe.log_error(f"Validate Data Error: {str(e)}")
        return {"success": False, "message": str(e)}

def generate_item_description(pricing_data):
    """Generate human-readable description from pricing data"""
    property_type = pricing_data.get('property_type')
    
    if property_type == 'house':
        house_size = pricing_data.get('house_size', '').replace('_', ' ').title()
        quantity = pricing_data.get('quantity', '').replace('_', ' ').title()
        additional = pricing_data.get('additional_spaces', [])
        
        desc = f"{house_size} House - {quantity}"
        if additional:
            spaces = ', '.join([s.replace('_', ' ').title() for s in additional])
            desc += f" (with {spaces})"
        return desc
        
    elif property_type == 'flat':
        flat_size = pricing_data.get('flat_size', '').replace('_', ' ').title()
        quantity = pricing_data.get('quantity', '').replace('_', ' ').title()
        return f"{flat_size} Flat - {quantity}"
        
    elif property_type == 'office':
        office_size = pricing_data.get('office_size', '').replace('_', ' ').title()
        quantity = pricing_data.get('quantity', '').replace('_', ' ').title()
        return f"{office_size} Office - {quantity}"
        
    elif property_type == 'a_few_items':
        vehicle = pricing_data.get('vehicle_type', '').replace('_', ' ').title()
        space = pricing_data.get('space_usage', '').replace('_', ' ').title()
        return f"A Few Items - {vehicle} ({space})"
    
    return "Move Request"


# ==================== UPDATED SEARCH WITH ENHANCED PRICING ====================

@frappe.whitelist(allow_guest=True)
def search_companies_with_detailed_pricing(pincode=None, request_data=None):
    """
    Search companies and calculate detailed pricing for each
    
    Request Body:
    {
        "pincode": "SW1A 1AA",
        "request_data": {
            // Same structure as create_request_with_detailed_pricing
            "pricing_data": {...},
            "collection_assessment": {...},
            "delivery_assessment": {...},
            "move_date_data": {...},
            "distance_miles": 200
        }
    }
    """
    try:
        data = frappe.request.get_json() or {}
        pincode = pincode or data.get('pincode')
        request_data = request_data or data.get('request_data', {})
        
        if not pincode:
            return {"success": False, "message": "Pincode is required"}
        
        # Search companies
        companies = frappe.db.sql("""
            SELECT * 
            FROM `tabLogistics Company`
            WHERE is_active = 1 
            AND (
                pincode = %(pincode)s 
                OR areas_covered LIKE %(pincode_pattern)s
            )
            ORDER BY created_at DESC
        """, {
            "pincode": pincode,
            "pincode_pattern": f'%{pincode}%'
        }, as_dict=True)
        
        available_companies = []
        
        for company in companies:
            # Check subscription limit
            if not check_company_can_view_requests(company):
                continue
            
            # Parse JSON fields
            parse_json_fields(company)
            
            # Get company document
            company_doc = frappe.get_doc("Logistics Company", company['company_name'])
            
            # Calculate detailed pricing
            try:
                price_breakdown = calculate_comprehensive_price(request_data, company_doc)
                company['detailed_pricing'] = price_breakdown
                company['estimated_total'] = price_breakdown['final_total']
            except Exception as pricing_error:
                frappe.log_error(f"Pricing error for {company['company_name']}: {str(pricing_error)}")
                company['detailed_pricing'] = None
                company['estimated_total'] = 0
            
            # Add subscription info
            plan = company.get('subscription_plan', 'Free')
            viewed = int(company.get('requests_viewed_this_month', 0) or 0)
            from localmoves.api.company import PLAN_LIMITS
            limit = PLAN_LIMITS.get(plan, 5)
            
            company['subscription_info'] = {
                'plan': plan,
                'views_used': viewed,
                'views_limit': limit if limit != -1 else 'Unlimited',
                'views_remaining': (limit - viewed) if limit != -1 else 'Unlimited'
            }
            
            available_companies.append(company)
        
        # Sort by estimated total (lowest first)
        available_companies.sort(key=lambda x: x.get('estimated_total', 999999))
        
        return {
            "success": True,
            "count": len(available_companies),
            "data": available_companies,
            "search_parameters": {
                "pincode": pincode,
                "pricing_data": request_data.get('pricing_data'),
                "distance_miles": request_data.get('distance_miles')
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Search with Detailed Pricing Error: {str(e)}")
        return {"success": False, "message": f"Failed to search: {str(e)}"}


def check_company_can_view_requests(company):
    """Check if company has remaining request views"""
    from localmoves.api.company import PLAN_LIMITS
    
    plan = company.get('subscription_plan', 'Free')
    viewed_count = int(company.get('requests_viewed_this_month', 0) or 0)
    limit = PLAN_LIMITS.get(plan, 5)
    
    if limit == -1:
        return True
    return viewed_count < limit


def parse_json_fields(company):
    """Parse JSON fields in company dict"""
    json_fields = [
        "areas_covered", "company_gallery", "includes", "material",
        "protection", "furniture", "appliances"
    ]
    
    for field in json_fields:
        if field in company and company[field]:
            try:
                if isinstance(company[field], str):
                    company[field] = json.loads(company[field])
            except:
                company[field] = []
        else:
            company[field] = []
    
    return company


# ==================== GET REQUEST WITH PRICING DETAILS ====================

@frappe.whitelist(allow_guest=True)
def get_request_with_pricing_details(request_id=None):
    """Get request details including full pricing breakdown"""
    try:
        user_info = get_user_from_token()
        data = frappe.request.get_json() or {}
        
        request_id = request_id or data.get('request_id')
        
        if not request_id or not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        request_doc = frappe.get_doc("Logistics Request", request_id)
        
        # Check permissions
        is_owner = getattr(request_doc, 'user_email', None) == safe_get_dict_value(user_info, "email")
        is_admin = safe_get_dict_value(user_info, "role") == "Admin"
        is_manager = False
        
        if getattr(request_doc, 'company_name', None):
            company = frappe.get_doc("Logistics Company", getattr(request_doc, 'company_name'))
            is_manager = getattr(company, 'manager_email', None) == safe_get_dict_value(user_info, "email")
        
        if not (is_owner or is_manager or is_admin):
            return {"success": False, "message": "Permission denied"}
        
        # Get request as dict
        request_dict = request_doc.as_dict()
        
        # Parse JSON fields
        json_fields = ['pricing_data', 'collection_assessment', 'delivery_assessment', 
                      'move_date_data', 'price_breakdown']
        
        for field in json_fields:
            if field in request_dict and request_dict[field]:
                try:
                    if isinstance(request_dict[field], str):
                        request_dict[field] = json.loads(request_dict[field])
                except:
                    request_dict[field] = {}
        
        return {
            "success": True,
            "data": request_dict
        }
        
    except Exception as e:
        frappe.log_error(f"Get Request Detail Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch request details"}




@frappe.whitelist(allow_guest=True)
def diagnose_company_pricing(company_name=None):
    """
    Diagnostic API to check company pricing configuration
    Usage: POST with {"company_name": "None Moves"}
    """
    try:
        data = frappe.request.get_json() or {}
        company_name = company_name or data.get('company_name')
        
        if not company_name:
            return {"success": False, "message": "company_name is required"}
        
        # Check existence
        exists = frappe.db.exists("Logistics Company", company_name)
        if not exists:
            return {
                "success": False,
                "exists": False,
                "message": f"Company '{company_name}' does not exist"
            }
        
        # Get company document
        try:
            company = frappe.get_doc("Logistics Company", company_name)
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to load company: {str(e)}"
            }
        
        # Check basic info
        basic_info = {
            "company_name": company.name,
            "is_active": getattr(company, 'is_active', None),
            "subscription_plan": getattr(company, 'subscription_plan', None),
            "pincode": getattr(company, 'pincode', None),
            "manager_email": getattr(company, 'manager_email', None)
        }
        
        # Check all pricing fields
        pricing_config = {
            "loading_cost_per_m3": {
                "value": getattr(company, 'loading_cost_per_m3', None),
                "type": type(getattr(company, 'loading_cost_per_m3', None)).__name__,
                "is_set": getattr(company, 'loading_cost_per_m3', None) is not None,
                "is_zero": getattr(company, 'loading_cost_per_m3', None) == 0
            },
            "packing_cost_per_box": {
                "value": getattr(company, 'packing_cost_per_box', None),
                "type": type(getattr(company, 'packing_cost_per_box', None)).__name__,
                "is_set": getattr(company, 'packing_cost_per_box', None) is not None,
                "is_zero": getattr(company, 'packing_cost_per_box', None) == 0
            },
            "assembly_cost_per_item": {
                "value": getattr(company, 'assembly_cost_per_item', None),
                "type": type(getattr(company, 'assembly_cost_per_item', None)).__name__,
                "is_set": getattr(company, 'assembly_cost_per_item', None) is not None,
                "is_zero": getattr(company, 'assembly_cost_per_item', None) == 0
            },
            "disassembly_cost_per_item": {
                "value": getattr(company, 'disassembly_cost_per_item', None),
                "type": type(getattr(company, 'disassembly_cost_per_item', None)).__name__,
                "is_set": getattr(company, 'disassembly_cost_per_item', None) is not None,
                "is_zero": getattr(company, 'disassembly_cost_per_item', None) == 0
            },
            "cost_per_mile_under_25": {
                "value": getattr(company, 'cost_per_mile_under_25', None),
                "type": type(getattr(company, 'cost_per_mile_under_25', None)).__name__,
                "is_set": getattr(company, 'cost_per_mile_under_25', None) is not None,
                "is_zero": getattr(company, 'cost_per_mile_under_25', None) == 0
            },
            "cost_per_mile_over_25": {
                "value": getattr(company, 'cost_per_mile_over_25', None),
                "type": type(getattr(company, 'cost_per_mile_over_25', None)).__name__,
                "is_set": getattr(company, 'cost_per_mile_over_25', None) is not None,
                "is_zero": getattr(company, 'cost_per_mile_over_25', None) == 0
            }
        }
        
        # Check for missing or zero values
        missing_fields = []
        zero_fields = []
        for field, info in pricing_config.items():
            if not info['is_set']:
                missing_fields.append(field)
            elif info['is_zero']:
                zero_fields.append(field)
        
        # Overall validation
        is_valid = len(missing_fields) == 0 and len(zero_fields) == 0
        
        return {
            "success": True,
            "company_name": company_name,
            "is_valid_for_pricing": is_valid,
            "basic_info": basic_info,
            "pricing_config": pricing_config,
            "validation": {
                "missing_fields": missing_fields,
                "zero_value_fields": zero_fields,
                "total_issues": len(missing_fields) + len(zero_fields)
            },
            "recommendation": (
                "✅ Company is ready for pricing calculations" if is_valid else
                f"❌ Company needs {len(missing_fields) + len(zero_fields)} pricing fields to be configured"
            )
        }
        
    except Exception as e:
        frappe.log_error(f"Diagnose Company Error: {str(e)}", "Company Diagnosis Error")
        return {
            "success": False,
            "message": f"Diagnosis failed: {str(e)}"
        }


@frappe.whitelist(allow_guest=True)
def fix_company_pricing(company_name=None):
    """
    Set default pricing for a company that's missing configuration
    Usage: POST with {"company_name": "None Moves"}
    """
    try:
        data = frappe.request.get_json() or {}
        company_name = company_name or data.get('company_name')
        
        if not company_name:
            return {"success": False, "message": "company_name is required"}
        
        if not frappe.db.exists("Logistics Company", company_name):
            return {"success": False, "message": f"Company '{company_name}' does not exist"}
        
        # Get company
        company = frappe.get_doc("Logistics Company", company_name)
        
        # Set default pricing if missing
        defaults = {
            'loading_cost_per_m3': 25.0,
            'packing_cost_per_box': 5.0,
            'assembly_cost_per_item': 15.0,
            'disassembly_cost_per_item': 15.0,
            'cost_per_mile_under_25': 2.0,
            'cost_per_mile_over_25': 1.5
        }
        
        updated_fields = []
        for field, default_value in defaults.items():
            current_value = getattr(company, field, None)
            if current_value is None or current_value == 0:
                setattr(company, field, default_value)
                updated_fields.append(f"{field}: {default_value}")
        
        if updated_fields:
            company.save(ignore_permissions=True)
            frappe.db.commit()
            
            return {
                "success": True,
                "message": f"Updated {len(updated_fields)} pricing fields for {company_name}",
                "updated_fields": updated_fields
            }
        else:
            return {
                "success": True,
                "message": f"No updates needed - {company_name} already has all pricing configured"
            }
        
    except Exception as e:
        frappe.log_error(f"Fix Company Pricing Error: {str(e)}", "Fix Pricing Error")
        frappe.db.rollback()
        return {
            "success": False,
            "message": f"Failed to fix pricing: {str(e)}"
        }

