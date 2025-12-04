# ==================== RATING & REVIEW SYSTEM ====================
# Create this as: localmoves/api/rating_review.py
# This is a SEPARATE file to avoid circular imports

import frappe
from frappe import _
from datetime import datetime
import json
import traceback


# ==================== RATING & REVIEW CONFIGURATION ====================

RATING_CONFIG = {
    "min_rating": 1,
    "max_rating": 5,
    "allowed_statuses_for_rating": ["Assigned", "Accepted", "In Progress", "Completed"],
    "review_max_length": 1000
}


# ==================== HELPER FUNCTIONS ====================

def get_user_from_token():
    """Extract user from JWT token"""
    try:
        from localmoves.utils.jwt_handler import get_current_user
        
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


def get_json_data():
    """Force parse JSON even if frappe.request fails - ALWAYS RETURN DICT"""
    try:
        data = {}
        
        if hasattr(frappe, "request") and frappe.request:
            data = frappe.request.get_json(force=True, silent=True) or {}
        
        if not data and hasattr(frappe, "request") and hasattr(frappe.request, "get_data"):
            raw = frappe.request.get_data(as_text=True)
            if raw and raw.strip():
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    pass
        
        if not data and hasattr(frappe, "form_dict") and frappe.form_dict:
            data = dict(frappe.form_dict)
        
        return data or {}
        
    except Exception as e:
        frappe.log_error(f"get_json_data error: {str(e)}")
        return {}


def safe_get_dict_value(dictionary, key, default=None):
    """Safely get value from dictionary, handling None cases"""
    if not dictionary or not isinstance(dictionary, dict):
        return default
    return dictionary.get(key, default)


# ==================== SUBMIT RATING & REVIEW ====================

@frappe.whitelist(allow_guest=True)
def submit_rating_and_review():
    """
    Submit rating and review for an assigned/in-progress/completed request
    
    Request Body:
    {
        "request_id": "REQ-00001",
        "rating": 5,
        "review_comment": "Excellent service!",
        "service_aspects": {
            "punctuality": 5,
            "professionalism": 5,
            "care_of_items": 5,
            "communication": 4,
            "value_for_money": 5
        }
    }
    """
    try:
        # Step 1: Authenticate user
        user_info = get_user_from_token()
        
        if not user_info or not isinstance(user_info, dict):
            return {"success": False, "message": "Authentication failed"}
        
        user_email = safe_get_dict_value(user_info, "email")
        user_role = safe_get_dict_value(user_info, "role")
        
        # Step 2: Get request data
        data = get_json_data()
        
        request_id = safe_get_dict_value(data, "request_id")
        rating = safe_get_dict_value(data, "rating")
        review_comment = safe_get_dict_value(data, "review_comment", "")
        service_aspects = safe_get_dict_value(data, "service_aspects", {})
        
        # Step 3: Validate inputs
        if not request_id:
            return {"success": False, "message": "request_id is required"}
        
        if not rating:
            return {"success": False, "message": "rating is required"}
        
        # Validate rating range
        try:
            rating = int(rating)
            if rating < RATING_CONFIG["min_rating"] or rating > RATING_CONFIG["max_rating"]:
                return {
                    "success": False,
                    "message": f"Rating must be between {RATING_CONFIG['min_rating']} and {RATING_CONFIG['max_rating']}"
                }
        except (ValueError, TypeError):
            return {"success": False, "message": "Invalid rating format"}
        
        # Validate review length
        if review_comment and len(review_comment) > RATING_CONFIG["review_max_length"]:
            return {
                "success": False,
                "message": f"Review comment too long (max {RATING_CONFIG['review_max_length']} characters)"
            }
        
        # Step 4: Check request exists
        if not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        request_doc = frappe.get_doc("Logistics Request", request_id)
        
        # Step 5: Verify user owns this request
        if request_doc.user_email != user_email and user_role != "Admin":
            return {"success": False, "message": "You can only rate your own requests"}
        
        # Step 6: Check request is assigned or beyond
        if request_doc.status not in RATING_CONFIG["allowed_statuses_for_rating"]:
            return {
                "success": False,
                "message": f"You can only rate requests that have been assigned to a company. Current status: {request_doc.status}"
            }
        
        # Step 7: Check if request has a company assigned
        if not request_doc.company_name:
            return {"success": False, "message": "Request has no company assigned"}
        
        # Step 8: Check if already rated
        if hasattr(request_doc, 'rating') and request_doc.rating:
            return {
                "success": False,
                "message": "You have already rated this request. You can update it instead.",
                "existing_rating": request_doc.rating
            }
        
        # Step 9: Update request with rating
        request_doc.db_set('rating', rating, update_modified=False)
        request_doc.db_set('review_comment', review_comment, update_modified=False)
        request_doc.db_set('service_aspects', json.dumps(service_aspects), update_modified=False)
        request_doc.db_set('rated_at', datetime.now(), update_modified=False)
        
        frappe.db.commit()
        
        # Step 10: Update company's average rating
        update_company_average_rating(request_doc.company_name)
        
        return {
            "success": True,
            "message": "Rating and review submitted successfully!",
            "data": {
                "request_id": request_id,
                "rating": rating,
                "review_comment": review_comment,
                "company_name": request_doc.company_name,
                "rated_at": str(datetime.now())
            }
        }
        
    except Exception as e:
        print(f"Submit Rating Error: {str(e)}\n{traceback.format_exc()}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to submit rating: {str(e)}"}


# ==================== UPDATE RATING & REVIEW ====================

@frappe.whitelist(allow_guest=True)
def update_rating_and_review():
    """
    Update existing rating and review
    
    Request Body:
    {
        "request_id": "REQ-00001",
        "rating": 4,
        "review_comment": "Updated review"
    }
    """
    try:
        user_info = get_user_from_token()
        
        if not user_info or not isinstance(user_info, dict):
            return {"success": False, "message": "Authentication failed"}
        
        user_email = safe_get_dict_value(user_info, "email")
        
        data = get_json_data()
        
        request_id = safe_get_dict_value(data, "request_id")
        rating = safe_get_dict_value(data, "rating")
        review_comment = safe_get_dict_value(data, "review_comment")
        service_aspects = safe_get_dict_value(data, "service_aspects", {})
        
        if not request_id:
            return {"success": False, "message": "request_id is required"}
        
        if not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        request_doc = frappe.get_doc("Logistics Request", request_id)
        
        # Verify ownership
        if request_doc.user_email != user_email:
            return {"success": False, "message": "You can only update your own ratings"}
        
        # Check if rated before
        if not hasattr(request_doc, 'rating') or not request_doc.rating:
            return {"success": False, "message": "Request has not been rated yet. Use submit_rating_and_review instead."}
        
        # Update rating
        if rating:
            try:
                rating = int(rating)
                if rating < RATING_CONFIG["min_rating"] or rating > RATING_CONFIG["max_rating"]:
                    return {
                        "success": False,
                        "message": f"Rating must be between {RATING_CONFIG['min_rating']} and {RATING_CONFIG['max_rating']}"
                    }
                request_doc.db_set('rating', rating, update_modified=False)
            except (ValueError, TypeError):
                return {"success": False, "message": "Invalid rating format"}
        
        # Update review comment
        if review_comment is not None:
            if len(review_comment) > RATING_CONFIG["review_max_length"]:
                return {
                    "success": False,
                    "message": f"Review comment too long (max {RATING_CONFIG['review_max_length']} characters)"
                }
            request_doc.db_set('review_comment', review_comment, update_modified=False)
        
        # Update service aspects
        if service_aspects:
            request_doc.db_set('service_aspects', json.dumps(service_aspects), update_modified=False)
        
        request_doc.db_set('rating_updated_at', datetime.now(), update_modified=False)
        
        frappe.db.commit()
        
        # Recalculate company average
        update_company_average_rating(request_doc.company_name)
        
        return {
            "success": True,
            "message": "Rating and review updated successfully!",
            "data": {
                "request_id": request_id,
                "rating": rating or request_doc.rating,
                "review_comment": review_comment if review_comment is not None else request_doc.review_comment
            }
        }
        
    except Exception as e:
        print(f"Update Rating Error: {str(e)}\n{traceback.format_exc()}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to update rating: {str(e)}"}


# ==================== DELETE RATING & REVIEW ====================

@frappe.whitelist(allow_guest=True)
def delete_rating_and_review():
    """
    Delete rating and review
    
    Request Body:
    {
        "request_id": "REQ-00001"
    }
    """
    try:
        user_info = get_user_from_token()
        
        if not user_info or not isinstance(user_info, dict):
            return {"success": False, "message": "Authentication failed"}
        
        user_email = safe_get_dict_value(user_info, "email")
        
        data = get_json_data()
        request_id = safe_get_dict_value(data, "request_id")
        
        if not request_id:
            return {"success": False, "message": "request_id is required"}
        
        if not frappe.db.exists("Logistics Request", request_id):
            return {"success": False, "message": "Request not found"}
        
        request_doc = frappe.get_doc("Logistics Request", request_id)
        
        # Verify ownership
        if request_doc.user_email != user_email:
            return {"success": False, "message": "You can only delete your own ratings"}
        
        company_name = request_doc.company_name
        
        # Clear rating fields
        request_doc.db_set('rating', None, update_modified=False)
        request_doc.db_set('review_comment', None, update_modified=False)
        request_doc.db_set('service_aspects', None, update_modified=False)
        request_doc.db_set('rated_at', None, update_modified=False)
        request_doc.db_set('rating_updated_at', None, update_modified=False)
        
        frappe.db.commit()
        
        # Recalculate company average
        if company_name:
            update_company_average_rating(company_name)
        
        return {
            "success": True,
            "message": "Rating and review deleted successfully"
        }
        
    except Exception as e:
        print(f"Delete Rating Error: {str(e)}\n{traceback.format_exc()}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to delete rating: {str(e)}"}


# ==================== GET COMPANY RATINGS & REVIEWS ====================

@frappe.whitelist(allow_guest=True)
def get_company_ratings_and_reviews(company_name=None, limit=None, offset=0):
    """
    Get all ratings and reviews for a company
    
    Query Parameters:
    - company_name: Company name
    - limit: Number of reviews to return (optional)
    - offset: Pagination offset (optional)
    """
    try:
        data = get_json_data()
        
        company_name = company_name or safe_get_dict_value(data, "company_name")
        limit = limit or safe_get_dict_value(data, "limit", 20)
        offset = offset or safe_get_dict_value(data, "offset", 0)
        
        if not company_name:
            return {"success": False, "message": "company_name is required"}
        
        if not frappe.db.exists("Logistics Company", company_name):
            return {"success": False, "message": "Company not found"}
        
        # Get company document
        company = frappe.get_doc("Logistics Company", company_name)
        
        # Get all rated requests for this company
        rated_requests = frappe.db.sql("""
            SELECT 
                name as request_id,
                rating,
                review_comment,
                service_aspects,
                rated_at,
                rating_updated_at,
                full_name as user_name,
                user_email,
                status,
                completed_at,
                pickup_city,
                delivery_city
            FROM `tabLogistics Request`
            WHERE company_name = %(company_name)s
            AND rating IS NOT NULL
            AND rating > 0
            ORDER BY rated_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """, {
            "company_name": company_name,
            "limit": limit,
            "offset": offset
        }, as_dict=True)
        
        # Get total count
        total_count = frappe.db.sql("""
            SELECT COUNT(*) as count
            FROM `tabLogistics Request`
            WHERE company_name = %(company_name)s
            AND rating IS NOT NULL
            AND rating > 0
        """, {"company_name": company_name}, as_dict=True)[0]['count']
        
        # Parse service aspects JSON
        for review in rated_requests:
            if review.get('service_aspects'):
                try:
                    review['service_aspects'] = json.loads(review['service_aspects'])
                except:
                    review['service_aspects'] = {}
            
            # Mask email for privacy
            if review.get('user_email'):
                email = review['user_email']
                review['user_email_masked'] = email[:3] + "***@" + email.split('@')[1] if '@' in email else "***"
            
            # Format dates
            for date_field in ['rated_at', 'rating_updated_at', 'completed_at']:
                if review.get(date_field):
                    review[date_field] = str(review[date_field])
        
        # Calculate rating distribution
        rating_distribution = frappe.db.sql("""
            SELECT 
                rating,
                COUNT(*) as count
            FROM `tabLogistics Request`
            WHERE company_name = %(company_name)s
            AND rating IS NOT NULL
            AND rating > 0
            GROUP BY rating
            ORDER BY rating DESC
        """, {"company_name": company_name}, as_dict=True)
        
        # Calculate average for each service aspect
        service_aspect_averages = {}
        if rated_requests:
            aspects = ['punctuality', 'professionalism', 'care_of_items', 'communication', 'value_for_money']
            for aspect in aspects:
                total = 0
                count = 0
                for review in rated_requests:
                    if review.get('service_aspects') and isinstance(review['service_aspects'], dict):
                        if aspect in review['service_aspects']:
                            total += review['service_aspects'][aspect]
                            count += 1
                if count > 0:
                    service_aspect_averages[aspect] = round(total / count, 2)
        
        return {
            "success": True,
            "company_name": company_name,
            "rating_summary": {
                "average_rating": getattr(company, 'average_rating', 0),
                "total_ratings": getattr(company, 'total_ratings', 0),
                "rating_distribution": {str(r['rating']): r['count'] for r in rating_distribution},
                "service_aspect_averages": service_aspect_averages
            },
            "reviews": {
                "total_count": total_count,
                "current_page": int(offset / limit) + 1 if limit > 0 else 1,
                "per_page": limit,
                "data": rated_requests
            }
        }
        
    except Exception as e:
        print(f"Get Ratings Error: {str(e)}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to fetch ratings: {str(e)}"}


# ==================== GET MY RATINGS ====================

@frappe.whitelist(allow_guest=True)
def get_my_ratings():
    """Get all ratings submitted by the current user"""
    try:
        user_info = get_user_from_token()
        
        if not user_info or not isinstance(user_info, dict):
            return {"success": False, "message": "Authentication failed"}
        
        user_email = safe_get_dict_value(user_info, "email")
        
        my_ratings = frappe.db.sql("""
            SELECT 
                name as request_id,
                company_name,
                rating,
                review_comment,
                service_aspects,
                rated_at,
                rating_updated_at,
                status,
                completed_at,
                pickup_city,
                delivery_city
            FROM `tabLogistics Request`
            WHERE user_email = %(user_email)s
            AND rating IS NOT NULL
            AND rating > 0
            ORDER BY rated_at DESC
        """, {"user_email": user_email}, as_dict=True)
        
        # Parse service aspects
        for rating in my_ratings:
            if rating.get('service_aspects'):
                try:
                    rating['service_aspects'] = json.loads(rating['service_aspects'])
                except:
                    rating['service_aspects'] = {}
            
            # Format dates
            for date_field in ['rated_at', 'rating_updated_at', 'completed_at']:
                if rating.get(date_field):
                    rating[date_field] = str(rating[date_field])
        
        return {
            "success": True,
            "count": len(my_ratings),
            "data": my_ratings
        }
        
    except Exception as e:
        print(f"Get My Ratings Error: {str(e)}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to fetch ratings: {str(e)}"}


# ==================== GET PENDING RATINGS ====================

@frappe.whitelist(allow_guest=True)
def get_pending_ratings():
    """Get all assigned/in-progress/completed requests that haven't been rated yet"""
    try:
        user_info = get_user_from_token()
        
        if not user_info or not isinstance(user_info, dict):
            return {"success": False, "message": "Authentication failed"}
        
        user_email = safe_get_dict_value(user_info, "email")
        
        pending_ratings = frappe.db.sql("""
            SELECT 
                name as request_id,
                company_name,
                status,
                completed_at,
                assigned_date,
                pickup_city,
                delivery_city,
                full_name,
                item_description
            FROM `tabLogistics Request`
            WHERE user_email = %(user_email)s
            AND status IN ('Assigned', 'Accepted', 'In Progress', 'Completed')
            AND (rating IS NULL OR rating = 0)
            AND company_name IS NOT NULL
            ORDER BY 
                CASE 
                    WHEN status = 'Completed' THEN 1
                    WHEN status = 'In Progress' THEN 2
                    WHEN status = 'Accepted' THEN 3
                    WHEN status = 'Assigned' THEN 4
                END,
                COALESCE(completed_at, assigned_date) DESC
        """, {"user_email": user_email}, as_dict=True)
        
        # Format dates and add status message
        for request in pending_ratings:
            if request.get('completed_at'):
                request['completed_at'] = str(request['completed_at'])
            if request.get('assigned_date'):
                request['assigned_date'] = str(request['assigned_date'])
            
            # Add helpful status message
            if request['status'] == 'Completed':
                request['rating_prompt'] = "Move completed - Please rate your experience"
            elif request['status'] == 'In Progress':
                request['rating_prompt'] = "Move in progress - Rate anytime"
            elif request['status'] == 'Accepted':
                request['rating_prompt'] = "Company accepted - You can rate now"
            else:
                request['rating_prompt'] = "Company assigned - You can rate anytime"
        
        return {
            "success": True,
            "count": len(pending_ratings),
            "message": f"You have {len(pending_ratings)} requests that can be rated",
            "data": pending_ratings
        }
        
    except Exception as e:
        print(f"Get Pending Ratings Error: {str(e)}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to fetch pending ratings: {str(e)}"}


# ==================== HELPER FUNCTION: UPDATE COMPANY AVERAGE ====================

def update_company_average_rating(company_name):
    """Calculate and update company's average rating"""
    try:
        # Calculate average rating
        result = frappe.db.sql("""
            SELECT 
                AVG(rating) as avg_rating,
                COUNT(*) as total_ratings
            FROM `tabLogistics Request`
            WHERE company_name = %(company_name)s
            AND rating IS NOT NULL
            AND rating > 0
        """, {"company_name": company_name}, as_dict=True)
        
        if result and result[0]:
            avg_rating = round(result[0]['avg_rating'], 2) if result[0]['avg_rating'] else 0
            total_ratings = result[0]['total_ratings']
            
            # Update company
            company = frappe.get_doc("Logistics Company", company_name)
            company.db_set('average_rating', avg_rating, update_modified=False)
            company.db_set('total_ratings', total_ratings, update_modified=False)
            
            frappe.db.commit()
            
            print(f"Updated {company_name}: avg={avg_rating}, total={total_ratings}")
            return True
        
        return False
        
    except Exception as e:
        print(f"Update Company Average Error: {str(e)}\n{traceback.format_exc()}")
        return False


# ==================== BULK RECALCULATE ALL COMPANY RATINGS ====================

@frappe.whitelist(allow_guest=True)
def recalculate_all_company_ratings():
    """
    Admin function to recalculate ratings for all companies
    """
    try:
        user_info = get_user_from_token()
        
        if not user_info or not isinstance(user_info, dict):
            return {"success": False, "message": "Authentication failed"}
        
        # Only admins can run this
        if safe_get_dict_value(user_info, "role") != "Admin":
            return {"success": False, "message": "Only admins can recalculate ratings"}
        
        # Get all companies
        companies = frappe.get_all("Logistics Company", fields=["company_name"])
        
        updated_count = 0
        for company in companies:
            if update_company_average_rating(company['company_name']):
                updated_count += 1
        
        return {
            "success": True,
            "message": f"Recalculated ratings for {updated_count} companies",
            "total_companies": len(companies)
        }
        
    except Exception as e:
        print(f"Recalculate Ratings Error: {str(e)}\n{traceback.format_exc()}")
        return {"success": False, "message": f"Failed to recalculate: {str(e)}"}
    







    