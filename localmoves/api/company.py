import frappe
from frappe import _
from localmoves.utils.jwt_handler import get_current_user
from datetime import datetime
import json


# Add this constant at the top of the file, after imports
PLAN_LIMITS = {
    "Free": 5,      # Free plan gets 5 views
    "Basic": 20,
    "Standard": 50,
    "Premium": -1   # Unlimited
}

def safe_log(title, message):
    """Safely log without exceeding character limits"""
    try:
        safe_title = str(title)[:100]
        safe_message = str(message)[:4000]
        frappe.log_error(title=safe_title, message=safe_message)
    except:
        pass  # Fail silently if logging fails

def check_company_can_view_requests(company):
    """
    Check if company has remaining request views based on subscription plan
    
    Args:
        company: Company dict with subscription_plan and requests_viewed_this_month
    
    Returns:
        bool: True if company can view more requests, False otherwise
    """
    plan = company.get('subscription_plan', 'Free')
    viewed_count = int(company.get('requests_viewed_this_month', 0) or 0)
    
    # Get limit for the plan
    limit = PLAN_LIMITS.get(plan, 5)  # Default to 5 if plan not found
    
    # Premium (-1) means unlimited
    if limit == -1:
        return True
    
    # Check if under limit
    return viewed_count < limit


# ------------------------- Helper Function ------------------------- #
def get_user_from_token():
    """Extract and validate user from JWT token"""
    token = frappe.get_request_header("Authorization")
    if not token:
        frappe.throw(_("No token provided"), frappe.AuthenticationError)
    
    if token.startswith('Bearer '):
        token = token[7:]
    
    try:
        user_info = get_current_user(token)
        if not frappe.db.exists("LocalMoves User", user_info['email']):
            frappe.throw(_("User not found in system"), frappe.AuthenticationError)
        return user_info
    except Exception:
        frappe.throw(_("Invalid or expired token"), frappe.AuthenticationError)


def get_request_data():
    """Safely parse request data from JSON or form"""
    if frappe.request.data:
        try:
            return json.loads(frappe.request.data)
        except Exception:
            pass
    return frappe.form_dict or {}


def calculate_fleet_totals(data):
    """Calculate ONLY total carrying capacity (m³) based on quantity owned"""
    # Handle None data
    if data is None:
        return {'total_carrying_capacity': 0}
    
    # FIXED capacities per vehicle type
    capacities = {
        'swb_van_quantity': 5,
        'mwb_van_quantity': 8,
        'lwb_van_quantity': 11,
        'xlwb_van_quantity': 13,
        'mwb_luton_van_quantity': 17,
        'lwb_luton_van_quantity': 19,
        'tonne_7_5_lorry_quantity': 30,
        'tonne_12_lorry_quantity': 45,
        'tonne_18_lorry_quantity': 55
    }
    
    total_capacity = 0
    for field, capacity_per_vehicle in capacities.items():
        # More defensive get
        if isinstance(data, dict):
            quantity_owned = int(data.get(field, 0) or 0)
        else:
            quantity_owned = 0
        total_capacity += quantity_owned * capacity_per_vehicle
    
    return {'total_carrying_capacity': total_capacity}


def process_json_array(data, field_name):
    """Process any JSON array field - returns JSON string for storage"""
    if not data:
        return "[]"
    
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return data
        except:
            pass
        return "[]"
    
    if isinstance(data, list):
        return json.dumps(data)
    
    return "[]"


# def parse_json_fields(company):
#     """Parse all JSON fields in a company dict and filter out blob URLs"""
#     if company is None:
#         return {}
    
#     json_fields = [
#         "areas_covered",
#         "company_gallery",
#         "includes",
#         "material",
#         "protection",
#         "furniture",
#         "appliances",
#         "swb_van_images", "mwb_van_images", "lwb_van_images", "xlwb_van_images",
#         "mwb_luton_van_images", "lwb_luton_van_images", "tonne_7_5_lorry_images",
#         "tonne_12_lorry_images", "tonne_18_lorry_images"
#     ]
    
#     # Image fields that need blob URL filtering
#     image_fields = [
#         "company_gallery",
#         "swb_van_images", "mwb_van_images", "lwb_van_images", "xlwb_van_images",
#         "mwb_luton_van_images", "lwb_luton_van_images", "tonne_7_5_lorry_images",
#         "tonne_12_lorry_images", "tonne_18_lorry_images"
#     ]
    
#     for field in json_fields:
#         if field in company and company[field]:
#             try:
#                 # Parse JSON string to list
#                 if isinstance(company[field], str):
#                     company[field] = json.loads(company[field])
                
#                 # Filter out blob URLs from image fields
#                 if field in image_fields and isinstance(company[field], list):
#                     company[field] = [
#                         url for url in company[field] 
#                         if url and not url.startswith('blob:')
#                     ]
#             except:
#                 company[field] = []
#         else:
#             company[field] = []
    
#     return company

def parse_json_fields(company):
    """Parse all JSON fields in a company dict and filter out blob URLs"""
    # CRITICAL: Handle None or invalid input
    if not company:
        return {}
    
    if not isinstance(company, dict):
        try:
            # Try to convert to dict if it's a document
            company = company.as_dict() if hasattr(company, 'as_dict') else {}
        except:
            return {}
    
    json_fields = [
        "areas_covered",
        "company_gallery",
        "includes",
        "material",
        "protection",
        "furniture",
        "appliances",
        "swb_van_images", "mwb_van_images", "lwb_van_images", "xlwb_van_images",
        "mwb_luton_van_images", "lwb_luton_van_images", "tonne_7_5_lorry_images",
        "tonne_12_lorry_images", "tonne_18_lorry_images"
    ]
    
    # Image fields that need blob URL filtering
    image_fields = [
        "company_gallery",
        "swb_van_images", "mwb_van_images", "lwb_van_images", "xlwb_van_images",
        "mwb_luton_van_images", "lwb_luton_van_images", "tonne_7_5_lorry_images",
        "tonne_12_lorry_images", "tonne_18_lorry_images"
    ]
    
    for field in json_fields:
        try:
            if field in company and company[field]:
                # Parse JSON string to list
                if isinstance(company[field], str):
                    company[field] = json.loads(company[field])
                
                # Filter out blob URLs from image fields
                if field in image_fields and isinstance(company[field], list):
                    company[field] = [
                        url for url in company[field] 
                        if url and not url.startswith('blob:')
                    ]
            else:
                company[field] = []
        except Exception as e:
            safe_log(f"Parse field error: {field}", str(e))
            company[field] = []
    
    # CRITICAL: Always return the dict
    return company

# def format_company_response(company_doc):
#     """Format company document for API response with all pricing"""
#     if company_doc is None:
#         return {}
    
#     try:
#         company_dict = company_doc.as_dict()
#     except Exception as e:
#         frappe.log_error(f"Error in as_dict: {str(e)}", "Format Company Response")
#         # Fallback: manually build dict
#         company_dict = {}
#         for field in company_doc.meta.get_valid_columns():
#             try:
#                 company_dict[field.fieldname] = company_doc.get(field.fieldname)
#             except:
#                 pass
    
#     if company_dict is None:
#         return {}
    
#     # Parse all JSON fields
#     company_dict = parse_json_fields(company_dict)
    
#     # Add pricing summary for clarity
#     company_dict['pricing_summary'] = {
#         'loading_per_m3': company_dict.get('loading_cost_per_m3', 0) if company_dict else 0,
#         'packing_per_box': company_dict.get('packing_cost_per_box', 0) if company_dict else 0,
#         'assembly_per_item': company_dict.get('assembly_cost_per_item', 0) if company_dict else 0,
#         'disassembly_per_item': company_dict.get('disassembly_cost_per_item', 0) if company_dict else 0,
#         'cost_per_mile_under_25': company_dict.get('cost_per_mile_under_25', 0) if company_dict else 0,
#         'cost_per_mile_over_25': company_dict.get('cost_per_mile_over_25', 0) if company_dict else 0
#     }
    
#     return company_dict

def format_company_response(company_doc):
    """Format company document for API response with all pricing"""
    if company_doc is None:
        return {}
    
    try:
        company_dict = company_doc.as_dict()
    except Exception as e:
        safe_log("as_dict Error", str(e))
        # Fallback: manually build dict
        company_dict = {}
        try:
            for field in company_doc.meta.get_valid_columns():
                try:
                    company_dict[field.fieldname] = company_doc.get(field.fieldname)
                except:
                    pass
        except:
            # If even meta fails, return minimal dict
            return {
                'company_name': getattr(company_doc, 'company_name', 'Unknown'),
                'error': 'Could not format full response'
            }
    
    if not company_dict or not isinstance(company_dict, dict):
        return {'company_name': getattr(company_doc, 'company_name', 'Unknown')}
    
    # Parse all JSON fields - CRITICAL: Ensure it returns a dict
    try:
        parsed_dict = parse_json_fields(company_dict)
        # IMPORTANT: Only update if parse was successful
        if parsed_dict and isinstance(parsed_dict, dict):
            company_dict = parsed_dict
    except Exception as e:
        safe_log("Parse JSON Error", str(e))
    
    # Verify company_dict is still valid after parsing
    if not company_dict or not isinstance(company_dict, dict):
        return {'company_name': getattr(company_doc, 'company_name', 'Unknown')}
    
    # Add pricing summary with safe gets
    try:
        company_dict['pricing_summary'] = {
            'loading_per_m3': float(company_dict.get('loading_cost_per_m3') or 0),
            'packing_per_box': float(company_dict.get('packing_cost_per_box') or 0),
            'assembly_per_item': float(company_dict.get('assembly_cost_per_item') or 0),
            'disassembly_per_item': float(company_dict.get('disassembly_cost_per_item') or 0),
            'cost_per_mile_under_25': float(company_dict.get('cost_per_mile_under_25') or 0),
            'cost_per_mile_over_25': float(company_dict.get('cost_per_mile_over_25') or 0)
        }
    except Exception as e:
        safe_log("Pricing Summary Error", str(e))
        company_dict['pricing_summary'] = {}
    
    return company_dict


# ------------------------- Create Company ------------------------- #
@frappe.whitelist(allow_guest=True)
def create_company(company_name=None, phone=None, pincode=None, location=None, address=None,
                   description=None, services_offered=None, personal_contact_name=None, **kwargs):
    """Create Logistics Company with manager-supplied pricing"""
    try:
        data = get_request_data()
        
        # Basic fields
        company_name = company_name or data.get("company_name")
        phone = phone or data.get("phone")
        pincode = pincode or data.get("pincode")
        location = location or data.get("location")
        address = address or data.get("address")
        description = description or data.get("description")
        services_offered = services_offered or data.get("services_offered")
        personal_contact_name = personal_contact_name or data.get("personal_contact_name")

        if not all([company_name, phone, pincode, location, address]):
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Missing required fields"}

        user_info = get_user_from_token()

        if user_info['role'] != "Logistics Manager":
            frappe.local.response['http_status_code'] = 403
            return {"success": False, "message": "Only Logistics Managers can create companies"}

        if frappe.db.exists("Logistics Company", company_name):
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Company with this name already exists"}

        # Get manager-supplied pricing
        loading_cost_per_m3 = float(data.get("loading_cost_per_m3", 0) or 0)
        packing_cost_per_box = float(data.get("packing_cost_per_box", 0) or 0)
        assembly_cost_per_item = float(data.get("assembly_cost_per_item", 0) or 0)
        cost_per_mile_under_25 = float(data.get("cost_per_mile_under_25", 0) or 0)
        cost_per_mile_over_25 = float(data.get("cost_per_mile_over_25", 0) or 0)
        
        # AUTO-CALCULATE: Disassembly = 50% of Assembly (unless manager provides it)
        disassembly_cost_per_item = float(data.get("disassembly_cost_per_item", 0) or 0)
        if not disassembly_cost_per_item and assembly_cost_per_item:
            disassembly_cost_per_item = assembly_cost_per_item * 0.5

        # Calculate fleet totals
        calculated = calculate_fleet_totals(data)

        # Build company document
        # Build company document
        company_dict = {
            "doctype": "Logistics Company",
            "company_name": company_name,
            "manager_email": user_info['email'],
            "phone": phone,
            "pincode": pincode,
            "location": location,
            "address": address,
            "description": description,
            "services_offered": services_offered,
            "personal_contact_name": personal_contact_name,
            "is_active": 1,

            # Fleet quantities (entered by manager)
            "swb_van_quantity": int(data.get("swb_van_quantity", 0) or 0),
            "mwb_van_quantity": int(data.get("mwb_van_quantity", 0) or 0),
            "lwb_van_quantity": int(data.get("lwb_van_quantity", 0) or 0),
            "xlwb_van_quantity": int(data.get("xlwb_van_quantity", 0) or 0),
            "mwb_luton_van_quantity": int(data.get("mwb_luton_van_quantity", 0) or 0),
            "lwb_luton_van_quantity": int(data.get("lwb_luton_van_quantity", 0) or 0),
            "tonne_7_5_lorry_quantity": int(data.get("tonne_7_5_lorry_quantity", 0) or 0),
            "tonne_12_lorry_quantity": int(data.get("tonne_12_lorry_quantity", 0) or 0),
            "tonne_18_lorry_quantity": int(data.get("tonne_18_lorry_quantity", 0) or 0),

            # Vehicle images (JSON arrays)
            "swb_van_images": process_json_array(data.get("swb_van_images"), "swb_van_images"),
            "mwb_van_images": process_json_array(data.get("mwb_van_images"), "mwb_van_images"),
            "lwb_van_images": process_json_array(data.get("lwb_van_images"), "lwb_van_images"),
            "xlwb_van_images": process_json_array(data.get("xlwb_van_images"), "xlwb_van_images"),
            "mwb_luton_van_images": process_json_array(data.get("mwb_luton_van_images"), "mwb_luton_van_images"),
            "lwb_luton_van_images": process_json_array(data.get("lwb_luton_van_images"), "lwb_luton_van_images"),
            "tonne_7_5_lorry_images": process_json_array(data.get("tonne_7_5_lorry_images"), "tonne_7_5_lorry_images"),
            "tonne_12_lorry_images": process_json_array(data.get("tonne_12_lorry_images"), "tonne_12_lorry_images"),
            "tonne_18_lorry_images": process_json_array(data.get("tonne_18_lorry_images"), "tonne_18_lorry_images"),

            # Calculated capacity (FIXED capacities × quantities owned)
            "total_carrying_capacity": calculated['total_carrying_capacity'],

            # MANAGER-SUPPLIED PRICING
            "loading_cost_per_m3": loading_cost_per_m3,
            "packing_cost_per_box": packing_cost_per_box,
            "assembly_cost_per_item": assembly_cost_per_item,
            "disassembly_cost_per_item": disassembly_cost_per_item,
            "cost_per_mile_under_25": cost_per_mile_under_25,
            "cost_per_mile_over_25": cost_per_mile_over_25,

            # JSON array fields
            "areas_covered": process_json_array(data.get("areas_covered"), "areas_covered"),
            "company_gallery": process_json_array(data.get("company_gallery"), "company_gallery"),
            
            # ADD THESE LINES:
            "includes": process_json_array(data.get("includes"), "includes"),
            "material": process_json_array(data.get("material"), "material"),
            "protection": process_json_array(data.get("protection"), "protection"),
            "furniture": process_json_array(data.get("furniture"), "furniture"),
            "appliances": process_json_array(data.get("appliances"), "appliances"),
        }

        company_doc = frappe.get_doc(company_dict)
        company_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "message": "Company created successfully",
            "data": format_company_response(company_doc)
        }

    except frappe.AuthenticationError as e:
        frappe.local.response['http_status_code'] = 401
        return {"success": False, "message": str(e)}
    except frappe.ValidationError as e:
        frappe.local.response['http_status_code'] = 400
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Create Company Error: {str(e)}", "Company Creation")
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": f"Failed to create company: {str(e)}"}



# @frappe.whitelist(allow_guest=True)
# def update_company(company_name=None, **kwargs):
#     """Update Logistics Company"""
#     try:
#         frappe.log_error("=== UPDATE COMPANY START ===", "Update Company Debug")
        
#         # Step 1: Get request data
#         frappe.log_error("Step 1: Getting request data", "Update Company Debug")
#         data = get_request_data()
#         safe_log("Step 1: Request Data", f"Type: {type(data)}, Keys: {list(data.keys()) if data else 'None'}")
        
#         if data is None:
#             frappe.local.response['http_status_code'] = 400
#             return {"success": False, "message": "No data provided"}
        
#         # Step 2: Get company name
#         frappe.log_error("Step 2: Getting company name", "Update Company Debug")
#         company_name = company_name or data.get("company_name") if data else None
#         frappe.log_error(f"Company name: {company_name}", "Update Company Debug")

#         if not company_name:
#             frappe.local.response['http_status_code'] = 400
#             return {"success": False, "message": "Company name is required"}

#         # Step 3: Get user info
#         frappe.log_error("Step 3: Getting user info", "Update Company Debug")
#         user_info = get_user_from_token()
#         frappe.log_error(f"User info: {user_info}", "Update Company Debug")
        
#         # Step 4: Check if company exists
#         frappe.log_error("Step 4: Checking company exists", "Update Company Debug")
#         if not frappe.db.exists("Logistics Company", company_name):
#             frappe.local.response['http_status_code'] = 404
#             return {"success": False, "message": "Company not found"}

#         # Step 5: Get company doc
#         frappe.log_error("Step 5: Getting company doc", "Update Company Debug")
#         company_doc = frappe.get_doc("Logistics Company", company_name)
#         frappe.log_error(f"Company doc type: {type(company_doc)}", "Update Company Debug")
        
#         if company_doc is None:
#             frappe.local.response['http_status_code'] = 404
#             return {"success": False, "message": "Company document not found"}

#         # Step 6: Check permissions
#         frappe.log_error("Step 6: Checking permissions", "Update Company Debug")
#         if company_doc.manager_email != user_info['email'] and user_info['role'] != "Admin":
#             frappe.local.response['http_status_code'] = 403
#             return {"success": False, "message": "You can only update your own company"}

#         # Step 7: Update basic fields
#         frappe.log_error("Step 7: Updating basic fields", "Update Company Debug")
#         basic_fields = ["phone", "pincode", "location", "address", "description", 
#                        "services_offered", "personal_contact_name"]
#         for field in basic_fields:
#             if field in data:
#                 frappe.log_error(f"Setting {field} to {data[field]}", "Update Company Debug")
#                 company_doc.set(field, data[field])
        
#         # Step 8: Update fleet quantities
#         frappe.log_error("Step 8: Updating fleet quantities", "Update Company Debug")
#         fleet_fields = [
#             "swb_van_quantity", "mwb_van_quantity", "lwb_van_quantity", "xlwb_van_quantity",
#             "mwb_luton_van_quantity", "lwb_luton_van_quantity", "tonne_7_5_lorry_quantity",
#             "tonne_12_lorry_quantity", "tonne_18_lorry_quantity"
#         ]
#         for field in fleet_fields:
#             if field in data:
#                 frappe.log_error(f"Setting {field} to {data[field]}", "Update Company Debug")
#                 company_doc.set(field, int(data[field]))
        
#         # Step 9: Update vehicle images
#         frappe.log_error("Step 9: Updating vehicle images", "Update Company Debug")
#         vehicle_image_fields = [
#             "swb_van_images", "mwb_van_images", "lwb_van_images", "xlwb_van_images",
#             "mwb_luton_van_images", "lwb_luton_van_images", "tonne_7_5_lorry_images",
#             "tonne_12_lorry_images", "tonne_18_lorry_images"
#         ]
#         for field in vehicle_image_fields:
#             if field in data:
#                 frappe.log_error(f"Processing {field}", "Update Company Debug")
#                 company_doc.set(field, process_json_array(data[field], field))
        
#         # Step 10: Update pricing
#         frappe.log_error("Step 10: Updating pricing fields", "Update Company Debug")
#         pricing_fields = [
#             "loading_cost_per_m3",
#             "packing_cost_per_box",
#             "assembly_cost_per_item",
#             "disassembly_cost_per_item",
#             "cost_per_mile_under_25",
#             "cost_per_mile_over_25"
#         ]
        
#         for field in pricing_fields:
#             if field in data:
#                 frappe.log_error(f"Setting {field} to {data[field]}", "Update Company Debug")
#                 company_doc.set(field, float(data[field]))

#         # Step 11: Auto-calculate disassembly
#         frappe.log_error("Step 11: Auto-calculating disassembly", "Update Company Debug")
#         if "assembly_cost_per_item" in data:
#             if "disassembly_cost_per_item" not in data:
#                 disassembly_value = float(data["assembly_cost_per_item"]) * 0.5
#                 frappe.log_error(f"Setting disassembly to {disassembly_value}", "Update Company Debug")
#                 company_doc.disassembly_cost_per_item = disassembly_value

#         # Step 12: Update JSON arrays
#         frappe.log_error("Step 12: Updating JSON arrays", "Update Company Debug")
#         json_array_fields = [
#             "areas_covered", 
#             "company_gallery",
#             "includes",
#             "material", 
#             "protection",
#             "furniture",
#             "appliances"
#         ]
#         for field in json_array_fields:
#             if field in data:
#                 frappe.log_error(f"Processing JSON field {field}", "Update Company Debug")
#                 company_doc.set(field, process_json_array(data[field], field))
        
#         # Step 13: Recalculate capacity
#         frappe.log_error("Step 13: Recalculating capacity", "Update Company Debug")
#         company_dict = {}
#         for field in fleet_fields:
#             try:
#                 val = company_doc.get(field)
#                 company_dict[field] = val if val is not None else 0
#                 frappe.log_error(f"Fleet field {field}: {company_dict[field]}", "Update Company Debug")
#             except Exception as e:
#                 frappe.log_error(f"Error getting {field}: {str(e)}", "Update Company Debug")
#                 company_dict[field] = 0
        
#         frappe.log_error(f"Company dict for calculation: {company_dict}", "Update Company Debug")
#         calculated = calculate_fleet_totals(company_dict)
#         frappe.log_error(f"Calculated capacity: {calculated}", "Update Company Debug")
#         company_doc.total_carrying_capacity = calculated['total_carrying_capacity']

#         # Step 14: Save
#         frappe.log_error("Step 14: Saving company doc", "Update Company Debug")
#         company_doc.save(ignore_permissions=True)
#         frappe.db.commit()

#         # Step 15: Format response
#         frappe.log_error("Step 15: Formatting response", "Update Company Debug")
#         response_data = format_company_response(company_doc)
#         frappe.log_error(f"Response data type: {type(response_data)}", "Update Company Debug")

#         frappe.log_error("=== UPDATE COMPANY SUCCESS ===", "Update Company Debug")
#         return {
#             "success": True, 
#             "message": "Company updated successfully", 
#             "data": response_data
#         }

#     except frappe.AuthenticationError as e:
#         frappe.log_error(f"Auth error: {str(e)}", "Update Company Error")
#         frappe.local.response['http_status_code'] = 401
#         return {"success": False, "message": str(e)}
#     except frappe.ValidationError as e:
#         safe_log("Validation Error", str(e)[:500])  # Limit error message length
#         frappe.local.response['http_status_code'] = 400
#         return {"success": False, "message": str(e)}
#     except Exception as e:
#         import traceback
#         error_details = traceback.format_exc()
#         frappe.log_error(f"Exception in update_company:\n{error_details}", "Update Company Error")
#         frappe.db.rollback()
#         frappe.local.response['http_status_code'] = 500
#         return {"success": False, "message": f"Failed to update company: {str(e)}"}






@frappe.whitelist(allow_guest=True)
def update_company(company_name=None, **kwargs):
    """Update Logistics Company"""
    line_number = "START"
    try:
        line_number = "1-Get data"
        data = get_request_data()
        if not data:
            data = {}
        
        line_number = "2-Get company_name"
        company_name = company_name or data.get("company_name")
        if not company_name:
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Company name is required"}

        line_number = "3-Get user"
        user_info = get_user_from_token()
        
        line_number = "4-Check exists"
        if not frappe.db.exists("Logistics Company", company_name):
            frappe.local.response['http_status_code'] = 404
            return {"success": False, "message": "Company not found"}

        line_number = "5-Get doc"
        company_doc = frappe.get_doc("Logistics Company", company_name)
        
        line_number = "6-Check permissions"
        if company_doc.manager_email != user_info['email'] and user_info['role'] != "Admin":
            frappe.local.response['http_status_code'] = 403
            return {"success": False, "message": "You can only update your own company"}

        line_number = "7-Update basic"
        basic_fields = ["phone", "pincode", "location", "address", "description", 
                       "services_offered", "personal_contact_name"]
        for field in basic_fields:
            if field in data and data.get(field) is not None:
                company_doc.set(field, data[field])
        
        line_number = "8-Update fleet"
        fleet_fields = [
            "swb_van_quantity", "mwb_van_quantity", "lwb_van_quantity", "xlwb_van_quantity",
            "mwb_luton_van_quantity", "lwb_luton_van_quantity", "tonne_7_5_lorry_quantity",
            "tonne_12_lorry_quantity", "tonne_18_lorry_quantity"
        ]
        for field in fleet_fields:
            if field in data:
                company_doc.set(field, int(data.get(field, 0) or 0))
        
        line_number = "9-Update images"
        vehicle_image_fields = [
            "swb_van_images", "mwb_van_images", "lwb_van_images", "xlwb_van_images",
            "mwb_luton_van_images", "lwb_luton_van_images", "tonne_7_5_lorry_images",
            "tonne_12_lorry_images", "tonne_18_lorry_images"
        ]
        for field in vehicle_image_fields:
            if field in data:
                company_doc.set(field, process_json_array(data.get(field), field))
        
        line_number = "10-Update pricing"
        pricing_fields = [
            "loading_cost_per_m3", "packing_cost_per_box", "assembly_cost_per_item",
            "disassembly_cost_per_item", "cost_per_mile_under_25", "cost_per_mile_over_25"
        ]
        for field in pricing_fields:
            if field in data:
                company_doc.set(field, float(data.get(field, 0) or 0))

        line_number = "11-Auto disassembly"
        if "assembly_cost_per_item" in data:
            if "disassembly_cost_per_item" not in data or not data.get("disassembly_cost_per_item"):
                company_doc.disassembly_cost_per_item = float(data.get("assembly_cost_per_item", 0) or 0) * 0.5

        line_number = "12-Update JSON arrays"
        json_array_fields = [
            "areas_covered", "company_gallery", "includes",
            "material", "protection", "furniture", "appliances"
        ]
        for field in json_array_fields:
            if field in data:
                company_doc.set(field, process_json_array(data.get(field), field))
        
        line_number = "13-Recalc capacity"
        fleet_data = {}
        for field in fleet_fields:
            val = company_doc.get(field)
            fleet_data[field] = int(val) if val is not None else 0
        
        calculated = calculate_fleet_totals(fleet_data)
        if calculated and 'total_carrying_capacity' in calculated:
            company_doc.total_carrying_capacity = calculated['total_carrying_capacity']

        # CRITICAL FIX: Ensure all JSON fields have valid defaults before save
        line_number = "13.5-Validate JSON fields"
        json_field_list = [
            "areas_covered", "company_gallery", "includes", "material", 
            "protection", "furniture", "appliances",
            "swb_van_images", "mwb_van_images", "lwb_van_images", "xlwb_van_images",
            "mwb_luton_van_images", "lwb_luton_van_images", "tonne_7_5_lorry_images",
            "tonne_12_lorry_images", "tonne_18_lorry_images"
        ]
        
        for field in json_field_list:
            try:
                current_val = company_doc.get(field)
                if current_val is None or current_val == '':
                    company_doc.set(field, "[]")
                elif isinstance(current_val, str):
                    # Validate it's proper JSON
                    try:
                        json.loads(current_val)
                    except:
                        company_doc.set(field, "[]")
            except Exception as e:
                safe_log(f"JSON field validation error: {field}", str(e))
                company_doc.set(field, "[]")

        # CRITICAL: Set flags to bypass validation if needed
        line_number = "13.6-Set flags"
        company_doc.flags.ignore_validate = False  # Keep validation
        company_doc.flags.ignore_mandatory = False  # Keep mandatory checks
        
        line_number = "14-Save"
        try:
            # Try save with full validation first
            company_doc.save(ignore_permissions=True)
        except AttributeError as attr_err:
            # This is the 'NoneType' has no attribute 'get' error
            safe_log("AttributeError in Save", f"Error: {str(attr_err)}\nAttempting direct DB update")
            
            # Fallback: Direct DB update (bypasses hooks entirely)
            line_number = "14-DB-Fallback"
            update_dict = {}
            
            # Collect all fields to update
            all_fields = basic_fields + fleet_fields + vehicle_image_fields + pricing_fields + json_array_fields
            for field in all_fields:
                if field in data:
                    if field in pricing_fields:
                        update_dict[field] = float(data.get(field, 0) or 0)
                    elif field in fleet_fields:
                        update_dict[field] = int(data.get(field, 0) or 0)
                    elif field in json_array_fields or field in vehicle_image_fields:
                        update_dict[field] = process_json_array(data.get(field), field)
                    else:
                        update_dict[field] = data[field]
            
            # Add calculated capacity
            update_dict['total_carrying_capacity'] = calculated['total_carrying_capacity']
            
            # Direct DB update
            frappe.db.set_value("Logistics Company", company_name, update_dict)
            
            # Reload the document
            company_doc = frappe.get_doc("Logistics Company", company_name)
        
        except Exception as save_error:
            # Log any other save errors
            import traceback
            error_trace = traceback.format_exc()
            safe_log("Save Error Details", f"Error: {str(save_error)}\nTrace: {error_trace[:1000]}")
            raise
        
        frappe.db.commit()

        line_number = "15-Format response"
        try:
            response_data = format_company_response(company_doc)
            if not response_data or not isinstance(response_data, dict):
                response_data = {"company_name": company_name, "message": "Updated successfully"}
        except Exception as format_error:
            safe_log("Format Response Error", str(format_error))
            response_data = {"company_name": company_name, "message": "Updated successfully"}

        return {
            "success": True, 
            "message": "Company updated successfully", 
            "data": response_data
        }

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        safe_log(f"Update Error at {line_number}", error_details[:2000])
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": f"Failed at step {line_number}: {str(e)}"}
# ------------------------- Delete Company ------------------------- #
@frappe.whitelist(allow_guest=True)
def delete_company(company_name=None):
    """Delete Logistics Company"""
    try:
        data = get_request_data()
        company_name = company_name or data.get("company_name")

        if not company_name:
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Company name is required"}

        user_info = get_user_from_token()
        if not frappe.db.exists("Logistics Company", company_name):
            frappe.local.response['http_status_code'] = 404
            return {"success": False, "message": "Company not found"}

        company_doc = frappe.get_doc("Logistics Company", company_name)
        if company_doc.manager_email != user_info['email'] and user_info['role'] != "Admin":
            frappe.local.response['http_status_code'] = 403
            return {"success": False, "message": "You can only delete your own company"}

        company_doc.delete(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "message": "Company deleted successfully"}

    except frappe.AuthenticationError as e:
        frappe.local.response['http_status_code'] = 401
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Delete Company Error: {str(e)}", "Company Deletion")
        frappe.db.rollback()
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": f"Failed to delete company: {str(e)}"}


# ------------------------- Get My Company ------------------------- #
@frappe.whitelist(allow_guest=True)
def get_my_company():
    """Get the logged-in manager's company"""
    try:
        user_info = get_user_from_token()
        if user_info['role'] != "Logistics Manager":
            frappe.local.response['http_status_code'] = 403
            return {"success": False, "message": "Only Logistics Managers can access this"}

        companies = frappe.get_all("Logistics Company",
                                   filters={"manager_email": user_info['email']},
                                   fields=["*"])
        
        for company in companies:
            parse_json_fields(company)
        
        return {"success": True, "data": companies}

    except frappe.AuthenticationError as e:
        frappe.local.response['http_status_code'] = 401
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get My Company Error: {str(e)}", "Get Company")
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": "Failed to fetch company"}


# ------------------------- Search Companies ------------------------- #
# @frappe.whitelist(allow_guest=True)
# def search_companies_by_pincode(pincode=None):
#     """Search logistics companies by pincode"""
#     try:
#         data = get_request_data()
#         pincode = pincode or data.get("pincode")

#         if not pincode:
#             frappe.local.response['http_status_code'] = 400
#             return {"success": False, "message": "Pincode is required"}

#         companies = frappe.db.sql("""
#             SELECT * 
#             FROM `tabLogistics Company`
#             WHERE is_active = 1 
#             AND (
#                 pincode = %(pincode)s 
#                 OR areas_covered LIKE %(pincode_pattern)s
#             )
#             ORDER BY created_at DESC
#         """, {
#             "pincode": pincode,
#             "pincode_pattern": f'%{pincode}%'
#         }, as_dict=True)
        
#         for company in companies:
#             parse_json_fields(company)
        
#         return {
#             "success": True, 
#             "count": len(companies), 
#             "data": companies
#         }

#     except Exception as e:
#         frappe.log_error(f"Search Companies Error: {str(e)}", "Company Search")
#         frappe.local.response['http_status_code'] = 500
#         return {"success": False, "message": "Failed to search companies"}

@frappe.whitelist(allow_guest=True)
def search_number_of_companies_by_pincode(pincode=None):
    """Search logistics companies by pincode (only those with available views)"""
    try:
        data = get_request_data()
        pincode = pincode or data.get("pincode")

        if not pincode:
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Pincode is required"}

        # Get all companies matching pincode
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
        
        # Filter companies based on subscription limits
        available_companies = []
        for company in companies:
            parse_json_fields(company)
            
            # Check if company can view more requests
            if check_company_can_view_requests(company):
                # Add plan info for transparency
                plan = company.get('subscription_plan', 'Free')
                viewed = int(company.get('requests_viewed_this_month', 0) or 0)
                limit = PLAN_LIMITS.get(plan, 5)
                
                company['subscription_info'] = {
                    'plan': plan,
                    'views_used': viewed,
                    'views_limit': limit if limit != -1 else 'Unlimited',
                    'views_remaining': (limit - viewed) if limit != -1 else 'Unlimited'
                }
                
                available_companies.append(company)
        
        return {
            "success": True, 
            "count": len(available_companies),
            "total_companies": len(companies),
            "filtered_out": len(companies) - len(available_companies),
            "data": available_companies
        }

    except Exception as e:
        frappe.log_error(f"Search Companies Error: {str(e)}", "Company Search")
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": "Failed to search companies"}


# ADD THIS EMAIL HELPER FUNCTION TO YOUR company.py FILE
# Place it BEFORE the search_companies_by_pincode function


# ============================================================================
# REPLACE YOUR EXISTING search_companies_by_pincode FUNCTION WITH THIS
# ============================================================================
# ADD THIS EMAIL HELPER FUNCTION TO YOUR company.py FILE
# Place it BEFORE the search_companies_by_pincode function

# def send_property_search_email(user_email, search_data, companies_data):
#     """
#     Send email to user with property-based company search results
    
#     Args:
#         user_email: User's email address
#         search_data: Dictionary with search parameters (property type, size, distance)
#         companies_data: List of companies with cost estimations
#     """
#     try:
#         from frappe.utils import get_url
        
#         total_companies = len(companies_data)
        
#         if total_companies == 0:
#             subject = "No Moving Companies Found for Your Search"
#             message = f"""
#             <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
#                 <h2 style="color: #333;">No Companies Found</h2>
#                 <p>We couldn't find any moving companies for pincode <strong>{search_data.get('pincode')}</strong>.</p>
#                 <p>Please try searching with a different pincode or contact our support team.</p>
#             </div>
#             """
#         else:
#             # Sort companies by base_total cost
#             sorted_companies = sorted(companies_data, key=lambda x: x['cost_estimation']['base_total'])
            
#             # Property type labels
#             property_labels = {
#                 'house': 'House',
#                 'flat': 'Flat',
#                 'office': 'Office',
#                 'a_few_items': 'A Few Items'
#             }
            
#             # Build company list HTML
#             company_list_html = ""
#             for idx, company in enumerate(sorted_companies[:5], 1):
#                 cost_est = company['cost_estimation']
                
#                 company_list_html += f"""
#                 <div style="border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #f9f9f9;">
#                     <h3 style="margin: 0 0 10px 0; color: #2c3e50;">{idx}. {company['company_name']}</h3>
#                     <p style="margin: 5px 0; color: #555;">
#                         <strong>Location:</strong> {company.get('location', 'N/A')}<br>
#                         <strong>Phone:</strong> {company.get('phone', 'N/A')}<br>
#                         <strong>Plan:</strong> {company.get('subscription_plan', 'Free')}
#                     </p>
                    
#                     <div style="background-color: #e8f5e9; padding: 12px; border-radius: 5px; margin-top: 10px;">
#                         <h4 style="margin: 0 0 8px 0; color: #2e7d32;">Estimated Cost Range</h4>
#                         <div style="text-align: center; padding: 15px; background-color: white; border-radius: 5px; margin: 10px 0;">
#                             <div style="font-size: 24px; color: #2e7d32; font-weight: bold;">
#                                 £{cost_est['estimated_range']['min']:,.2f} - £{cost_est['estimated_range']['max']:,.2f}
#                             </div>
#                             <div style="font-size: 12px; color: #666; margin-top: 5px;">Estimated Price Range</div>
#                         </div>
#                     </div>
                    
#                     <div style="margin-top: 10px; font-size: 12px; color: #666; background-color: #fff3cd; padding: 10px; border-radius: 5px;">
#                         <strong>📋 Move Details:</strong><br>
#                         • Distance: {cost_est['distance_miles']} miles<br>
#                         • Property: {property_labels.get(cost_est['property_type'], cost_est['property_type'])} - {cost_est['property_size']}<br>
#                         • Quantity: {cost_est['quantity']}
#                     </div>
                    
#                     <div style="margin-top: 10px; padding: 10px; background-color: #e3f2fd; border-radius: 5px; font-size: 12px;">
#                         <strong>ℹ️ Price Range Explanation:</strong><br>
#                         The range (£{cost_est['estimated_range']['min']:,.2f} - £{cost_est['estimated_range']['max']:,.2f}) accounts for:<br>
#                         • Property assessment variations<br>
#                         • Optional extras (packing, assembly)<br>
#                         • Move date adjustments
#                     </div>
#                 </div>
#                 """
            
#             # Prepare summary statistics
#             cheapest_min = sorted_companies[0]['cost_estimation']['estimated_range']['min']
#             cheapest_max = sorted_companies[0]['cost_estimation']['estimated_range']['max']
#             most_expensive_max = sorted_companies[-1]['cost_estimation']['estimated_range']['max']
#             avg_base = sum(c['cost_estimation']['base_total'] for c in companies_data) / total_companies
            
#             # Property info text
#             property_info = f"{property_labels.get(search_data.get('property_type'), search_data.get('property_type'))} - {search_data.get('property_size')}"
            
#             subject = f"LocalMoves - Estimated Price"
#             message = f"""
#             <div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
#                 <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; color: white; text-align: center;">
#                     <h1 style="margin: 0 0 10px 0;">Your Moving Company Results</h1>
#                 </div>
                
#                 <div style="margin: 20px 0; padding: 20px; background-color: #f0f4f8; border-radius: 8px;">
#                     <h3 style="margin: 0 0 15px 0; color: #333;">Your Move Details</h3>
#                     <table style="width: 100%; font-size: 14px;">
#                         <tr>
#                             <td style="padding: 5px 0;"><strong>Pincode:</strong></td>
#                             <td style="padding: 5px 0;">{search_data.get('pincode')}</td>
#                         </tr>
#                         <tr>
#                             <td style="padding: 5px 0;"><strong>Property Type:</strong></td>
#                             <td style="padding: 5px 0;">{property_labels.get(search_data.get('property_type'), search_data.get('property_type'))}</td>
#                         </tr>
#                         <tr>
#                             <td style="padding: 5px 0;"><strong>Property Size:</strong></td>
#                             <td style="padding: 5px 0;">{search_data.get('property_size')}</td>
#                         </tr>
#                         <tr>
#                             <td style="padding: 5px 0;"><strong>Distance:</strong></td>
#                             <td style="padding: 5px 0;">{search_data.get('distance_miles')} miles</td>
#                         </tr>
#                         <tr>
#                             <td style="padding: 5px 0;"><strong>Quantity:</strong></td>
#                             <td style="padding: 5px 0;">{search_data.get('quantity')}</td>
#                         </tr>
#                     </table>
#                 </div>
                
#                 <h2 style="color: #333; margin-top: 30px;">Top {min(5, total_companies)} Companies for Your Move</h2>
#                 {company_list_html}
                
#                 {'<p style="text-align: center; color: #666; font-style: italic;">Showing top 5 companies. Log in to view all results.</p>' if total_companies > 5 else ''}
                
#                 <div style="margin-top: 30px; padding: 20px; background-color: #e3f2fd; border-radius: 8px; text-align: center;">
#                     <p style="margin: 0 0 15px 0; color: #1565c0; font-size: 16px;">
#                         <strong>Ready to book your move?</strong>
#                     </p>
#                     <a href="{get_url()}" style="display: inline-block; padding: 12px 30px; background-color: #667eea; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
#                         View All Companies & Get Exact Quotes
#                     </a>
#                 </div>
                
#                 <div style="margin-top: 30px; padding: 15px; background-color: #fff8e1; border-left: 4px solid #ffa726; border-radius: 5px;">
#                     <h4 style="margin: 0 0 10px 0; color: #e65100;">📌 Important Pricing Information</h4>
#                     <ul style="margin: 10px 0; padding-left: 20px; font-size: 14px; color: #555;">
#                         <li><strong>Base costs</strong> include loading and mileage</li>
#                         <li><strong>Price ranges</strong> account for property assessment variations (±20-40%)</li>
#                         <li><strong>Not included:</strong> Optional packing, assembly/disassembly, special items</li>
#                         <li><strong>Final quote</strong> provided after property assessment</li>
#                         <li><strong>Peak times</strong> (weekends, month-end) may cost more</li>
#                     </ul>
#                 </div>
                
#                 <div style="margin-top: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 5px; font-size: 12px; color: #666;">
#                     <p style="margin: 0;"><strong>💡 Next Steps:</strong></p>
#                     <ol style="margin: 10px 0; padding-left: 20px;">
#                         <li>Review the companies above</li>
#                         <li>Contact 2-3 companies for detailed quotes</li>
#                         <li>Schedule property assessments</li>
#                         <li>Compare final quotes and book your preferred company</li>
#                     </ol>
#                 </div>
                
#                 <div style="margin-top: 20px; text-align: center; color: #999; font-size: 12px;">
#                     <p>© LocalMoves - Your Trusted Moving Partner</p>
#                     <p>Need help? Contact our support team</p>
#                 </div>
#             </div>
#             """
        
#         # Send email
#         frappe.sendmail(
#             recipients=[user_email],
#             subject=subject,
#             message=message,
#             delayed=False,
#             now=True
#         )
        
#         return True
        
#     except Exception as e:
#         frappe.log_error(f"Property Search Email Error: {str(e)}", "Property Search Email")
#         return False




# ADD THIS MINIMAL EMAIL HELPER FUNCTION TO YOUR company.py FILE
# Place it BEFORE the search_companies_by_pincode function

def send_property_search_email(user_email, search_data, companies_data):
    """
    Send minimal email to user with property-based company search results
    Shows only top 3 companies with name and price range
    
    Args:
        user_email: User's email address
        search_data: Dictionary with search parameters (property type, size, distance)
        companies_data: List of companies with cost estimations
    """
    try:
        from frappe.utils import get_url
        
        total_companies = len(companies_data)
        
        if total_companies == 0:
            subject = "No Moving Companies Found"
            message = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #333;">No Companies Found</h2>
                <p>We couldn't find any moving companies for pincode <strong>{search_data.get('pincode')}</strong>.</p>
                <p>Please try searching with a different pincode.</p>
            </div>
            """
        else:
            # Sort companies by base_total cost and get top 3
            sorted_companies = sorted(companies_data, key=lambda x: x['cost_estimation']['base_total'])[:3]
            
            # Build company list HTML - MINIMAL VERSION
            company_list_html = ""
            for idx, company in enumerate(sorted_companies, 1):
                cost_est = company['cost_estimation']
                
                company_list_html += f"""
                <div style="border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 15px; background-color: #fff;">
                    <h3 style="margin: 0 0 15px 0; color: #2c3e50; font-size: 18px;">{company['company_name']}</h3>
                    
                    <div style="text-align: center; padding: 20px; background-color: #f0f9ff; border-radius: 5px;">
                        <div style="font-size: 28px; color: #2563eb; font-weight: bold;">
                            £{cost_est['estimated_range']['min']:,.2f} - £{cost_est['estimated_range']['max']:,.2f}
                        </div>
                        <div style="font-size: 13px; color: #666; margin-top: 5px;">Estimated Price Range</div>
                    </div>
                </div>
                """
            
            subject = "LocalMoves - Estimated Price"
            message = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 10px; color: white; text-align: center; margin-bottom: 30px;">
                    <h2 style="margin: 0; font-size: 24px;">Welcome to LocalMoves!</h2>
                    <p style="margin: 0; font-size: 18px;">We found {total_companies} Companies for Your Move!</p>
                </div>
                
                {company_list_html}
                
                <div style="margin-top: 30px; padding: 25px; background-color: #f0f9ff; border-radius: 8px; text-align: center;">
                    <p style="margin: 0 0 15px 0; color: #1e40af; font-size: 16px; font-weight: 600;">
                        Ready to book your move?
                    </p>
                    <a href="{get_url()}" style="display: inline-block; padding: 14px 35px; background-color: #667eea; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 15px;">
                        View All Companies & Get Exact Quotes
                    </a>
                </div>
                
                <div style="margin-top: 25px; text-align: center; color: #999; font-size: 12px;">
                    <p style="margin: 0;">© LocalMoves - Your Trusted Moving Partner</p>
                </div>
            </div>
            """
        
        # Send email
        frappe.sendmail(
            recipients=[user_email],
            subject=subject,
            message=message,
            delayed=False,
            now=True
        )
        
        return True
        
    except Exception as e:
        frappe.log_error(f"Property Search Email Error: {str(e)}", "Property Search Email")
        return False


# ============================================================================
# REPLACE YOUR EXISTING search_companies_by_pincode FUNCTION WITH THIS
# ============================================================================

@frappe.whitelist(allow_guest=True)
def search_companies_by_pincode(pincode=None, property_type=None, property_size=None, 
                                distance_miles=None, quantity=None, additional_spaces=None,
                                user_email=None, send_email=False):
    """
    Search logistics companies by pincode with property-based cost estimation
    NOW WITH EMAIL NOTIFICATION SUPPORT
    
    Args:
        pincode: Search pincode
        property_type: 'house', 'flat', 'office', 'a_few_items'
        property_size: Size based on property type
            - house: '2_bed', '3_bed', '4_bed', '5_bed', '6_bed'
            - flat: 'studio', '1_bed', '2_bed', '3_bed', '4_bed'
            - office: '2_workstations', '4_workstations', '8_workstations', '15_workstations', '25_workstations'
            - a_few_items: 'swb_van', 'mwb_van', 'lwb_van', 'xlwb_van'
        distance_miles: Distance in miles
        quantity: 'some_things', 'half_contents', 'three_quarter', 'everything' (optional, defaults to 'everything')
        additional_spaces: JSON array of additional spaces for houses ['shed', 'loft', etc.] (optional)
        user_email: Email to send results to (optional, gets from token if not provided)
        send_email: Boolean to enable email sending (default: False)
    
    Returns:
        Companies with estimated costs based on property type + email status
    """
    try:
        data = get_request_data()
        pincode = pincode or data.get("pincode")
        property_type = property_type or data.get("property_type")
        property_size = property_size or data.get("property_size")
        distance_miles = distance_miles or data.get("distance_miles", 0)
        quantity = quantity or data.get("quantity", "everything")
        additional_spaces = additional_spaces or data.get("additional_spaces", [])
        user_email = user_email or data.get("user_email")
        send_email = send_email or data.get("send_email", False)
        
        # Get user email from token if not provided and email is requested
        if send_email and not user_email:
            try:
                user_info = get_user_from_token()
                user_email = user_info.get('email')
            except:
                user_email = None

        if not pincode:
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Pincode is required"}
        
        if not property_type:
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Property type is required"}
        
        if not property_size:
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Property size is required"}

        # Parse additional spaces if string
        if isinstance(additional_spaces, str):
            try:
                additional_spaces = json.loads(additional_spaces)
            except:
                additional_spaces = []

        # Define pricing constants locally (since we can't import from request_pricing.py)
        # Vehicle capacities (m³)
        VEHICLE_CAPACITIES = {
            'swb_van': 5,
            'mwb_van': 8,
            'lwb_van': 11,
            'xlwb_van': 13,
        }

        # Property type base volumes (m³)
        PROPERTY_VOLUMES = {
            'a_few_items': {
                'swb_van': 5,
                'mwb_van': 8,
                'lwb_van': 11,
            },
            'house': {
                '2_bed': 25,
                '3_bed': 40,
                '4_bed': 50,
                '5_bed': 65,
                '6_bed': 80,
            },
            'flat': {
                'studio': 12,
                '1_bed': 18,
                '2_bed': 28,
                '3_bed': 38,
                '4_bed': 48,
            },
            'office': {
                '2_workstations': 7,
                '4_workstations': 12,
                '8_workstations': 22,
                '15_workstations': 40,
                '25_workstations': 70,
            }
        }

        # Additional spaces for houses (m³)
        ADDITIONAL_SPACES = {
            'shed': 8,
            'loft': 12,
            'basement': 20,
            'single_garage': 16,
            'double_garage': 30,
        }

        # Quantity multipliers
        QUANTITY_MULTIPLIERS = {
            'some_things': 0.25,
            'half_contents': 0.5,
            'three_quarter': 0.75,
            'everything': 1.0,
        }

        # Vehicle space multipliers (for a few items)
        VEHICLE_SPACE_MULTIPLIERS = {
            'quarter_van': 0.25,
            'half_van': 0.5,
            'three_quarter_van': 0.75,
            'whole_van': 1.0,
        }

        def calculate_total_volume(pricing_data):
            """Calculate total volume based on property type"""
            property_type = pricing_data.get('property_type')
            total_volume = 0
            
            if property_type == 'a_few_items':
                vehicle_type = pricing_data.get('vehicle_type')
                space_usage = pricing_data.get('space_usage')
                base_volume = PROPERTY_VOLUMES['a_few_items'].get(vehicle_type, 0)
                multiplier = VEHICLE_SPACE_MULTIPLIERS.get(space_usage, 1.0)
                total_volume = base_volume * multiplier
                
            elif property_type == 'house':
                house_size = pricing_data.get('house_size')
                additional_spaces = pricing_data.get('additional_spaces', [])
                quantity = pricing_data.get('quantity')
                base_volume = PROPERTY_VOLUMES['house'].get(house_size, 0)
                for space in additional_spaces:
                    base_volume += ADDITIONAL_SPACES.get(space, 0)
                multiplier = QUANTITY_MULTIPLIERS.get(quantity, 1.0)
                total_volume = base_volume * multiplier
                
            elif property_type == 'flat':
                flat_size = pricing_data.get('flat_size')
                quantity = pricing_data.get('quantity')
                base_volume = PROPERTY_VOLUMES['flat'].get(flat_size, 0)
                multiplier = QUANTITY_MULTIPLIERS.get(quantity, 1.0)
                total_volume = base_volume * multiplier
                
            elif property_type == 'office':
                office_size = pricing_data.get('office_size')
                quantity = pricing_data.get('quantity')
                base_volume = PROPERTY_VOLUMES['office'].get(office_size, 0)
                multiplier = QUANTITY_MULTIPLIERS.get(quantity, 1.0)
                total_volume = base_volume * multiplier
            
            return round(total_volume, 2)

        def calculate_loading_cost(total_volume, loading_cost_per_m3):
            """Calculate base loading cost"""
            return round(total_volume * loading_cost_per_m3, 2)

        def calculate_mileage_cost(distance_miles, total_volume, cost_per_mile_under_25, cost_per_mile_over_25):
            """Calculate mileage cost based on distance and volume"""
            distance = float(distance_miles or 0)
            
            if distance <= 25:
                cost_per_mile = cost_per_mile_under_25
                mileage_cost = distance * total_volume * cost_per_mile
            else:
                cost_first_25 = 25 * total_volume * cost_per_mile_under_25
                remaining_miles = distance - 25
                cost_remaining = remaining_miles * total_volume * cost_per_mile_over_25
                mileage_cost = cost_first_25 + cost_remaining
            
            return round(mileage_cost, 2)

        # Build pricing data based on property type
        pricing_data = {
            'property_type': property_type,
            'quantity': quantity
        }

        if property_type == 'house':
            pricing_data['house_size'] = property_size
            pricing_data['additional_spaces'] = additional_spaces
        elif property_type == 'flat':
            pricing_data['flat_size'] = property_size
        elif property_type == 'office':
            pricing_data['office_size'] = property_size
        elif property_type == 'a_few_items':
            pricing_data['vehicle_type'] = property_size
            pricing_data['space_usage'] = quantity  # For a_few_items, quantity means space usage

        # Search companies by pincode
        companies = frappe.db.sql("""
            SELECT * 
            FROM `tabLogistics Company`
            WHERE is_active = 1 
            AND (
                pincode = %(pincode)s 
                OR areas_covered LIKE %(pincode_pattern)s
            )
            
        """, {
            "pincode": pincode,
            "pincode_pattern": f'%{pincode}%'
        }, as_dict=True)

        # Filter and calculate costs for available companies
        available_companies = []
        
        for company in companies:
            # Check subscription limit FIRST
            if not check_company_can_view_requests(company):
                continue
            
            # Parse JSON fields
            parse_json_fields(company)
            
            # Get company pricing
            company_pricing = {
                'loading_cost_per_m3': float(company.get('loading_cost_per_m3', 0) or 0),
                'packing_cost_per_box': float(company.get('packing_cost_per_box', 0) or 0),
                'disassembly_cost_per_item': float(company.get('disassembly_cost_per_item', 0) or 0),
                'assembly_cost_per_item': float(company.get('assembly_cost_per_item', 0) or 0),
                'cost_per_mile_under_25': float(company.get('cost_per_mile_under_25', 0) or 0),
                'cost_per_mile_over_25': float(company.get('cost_per_mile_over_25', 0) or 0),
            }

            # Calculate total volume
            total_volume = calculate_total_volume(pricing_data)
            
            # Calculate base loading cost
            loading_cost = calculate_loading_cost(
                total_volume, 
                company_pricing['loading_cost_per_m3']
            )
            
            # Calculate mileage cost
            distance = float(distance_miles or 0)
            mileage_cost = calculate_mileage_cost(
                distance,
                total_volume,
                company_pricing['cost_per_mile_under_25'],
                company_pricing['cost_per_mile_over_25']
            )
            
            # Base total (without property assessment or optional extras)
            base_total = loading_cost + mileage_cost
            
            # Estimated range considering property assessments (±20%)
            estimated_min = round(base_total * 0.8, 2)
            estimated_max = round(base_total * 1.4, 2)
            
            # Add cost calculation to company data
            company['cost_estimation'] = {
                'property_type': property_type,
                'property_size': property_size,
                'total_volume_m3': round(total_volume, 2),
                'distance_miles': distance,
                'quantity': quantity,
                'additional_spaces': additional_spaces if property_type == 'house' else [],
                
                'loading_cost': round(loading_cost, 2),
                'mileage_cost': round(mileage_cost, 2),
                'base_total': round(base_total, 2),
                
                'estimated_range': {
                    'min': estimated_min,
                    'max': estimated_max,
                    'note': 'Final price varies based on property assessment, optional extras, and move date'
                },
                
                'breakdown': {
                    'loading': round(loading_cost, 2),
                    'mileage': round(mileage_cost, 2),
                }
            }
            
            # Add pricing rates for reference
            company['pricing_rates'] = company_pricing
            
            # Add subscription info
            plan = company.get('subscription_plan', 'Free')
            viewed = int(company.get('requests_viewed_this_month', 0) or 0)
            limit = PLAN_LIMITS.get(plan, 5)
            
            company['subscription_info'] = {
                'plan': plan,
                'views_used': viewed,
                'views_limit': limit if limit != -1 else 'Unlimited',
                'views_remaining': (limit - viewed) if limit != -1 else 'Unlimited'
            }
            
            available_companies.append(company)
        
        # Sort by estimated cost (base_total)
        available_companies.sort(key=lambda x: x['cost_estimation']['base_total'])
        
        # Prepare response
        result = {
            "success": True,
            "count": len(available_companies),
            "total_companies": len(companies),
            "filtered_out": len(companies) - len(available_companies),
            "data": available_companies,
            "search_parameters": {
                "pincode": pincode,
                "property_type": property_type,
                "property_size": property_size,
                "distance_miles": distance,
                "quantity": quantity,
                "additional_spaces": additional_spaces if property_type == 'house' else [],
                "total_volume_m3": round(calculate_total_volume(pricing_data), 2)
            },
            "pricing_note": "Estimates are base costs. Final prices include property assessment multipliers, optional extras (dismantling, reassembly, packing), and move date adjustments."
        }
        
        # ========== EMAIL FUNCTIONALITY ==========
        # Send email if requested and email available
        email_sent = False
        if send_email and user_email:
            try:
                email_sent = send_property_search_email(
                    user_email=user_email,
                    search_data=result.get('search_parameters', {}),
                    companies_data=available_companies
                )
                result['email_sent'] = email_sent
                if email_sent:
                    result['email_message'] = f"Results sent to {user_email}"
                else:
                    result['email_message'] = "Failed to send email"
            except Exception as email_error:
                frappe.log_error(f"Email send failed: {str(email_error)}", "Property Search Email")
                result['email_sent'] = False
                result['email_message'] = f"Email failed: {str(email_error)}"
        # ========================================
        
        return result

    except Exception as e:
        frappe.log_error(f"Search Companies Error: {str(e)}", "Company Search")
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": f"Failed to search companies: {str(e)}"}

@frappe.whitelist(allow_guest=True)
def get_property_size_options(property_type=None):
    """
    Get available property size options for a given property type
    
    Args:
        property_type: 'house', 'flat', 'office', 'a_few_items'
    
    Returns:
        List of available size options
    """
    try:
        data = get_request_data()
        property_type = property_type or data.get("property_type")
        
        if not property_type:
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Property type is required"}
        
        # Define constants locally
        PROPERTY_VOLUMES = {
            'a_few_items': {
                'swb_van': 5,
                'mwb_van': 8,
                'lwb_van': 11,
            },
            'house': {
                '2_bed': 25,
                '3_bed': 40,
                '4_bed': 50,
                '5_bed': 65,
                '6_bed': 80,
            },
            'flat': {
                'studio': 12,
                '1_bed': 18,
                '2_bed': 28,
                '3_bed': 38,
                '4_bed': 48,
            },
            'office': {
                '2_workstations': 7,
                '4_workstations': 12,
                '8_workstations': 22,
                '15_workstations': 40,
                '25_workstations': 70,
            }
        }
        
        ADDITIONAL_SPACES = {
            'shed': 8,
            'loft': 12,
            'basement': 20,
            'single_garage': 16,
            'double_garage': 30,
        }
        
        QUANTITY_MULTIPLIERS = {
            'some_things': 0.25,
            'half_contents': 0.5,
            'three_quarter': 0.75,
            'everything': 1.0,
        }
        
        VEHICLE_SPACE_MULTIPLIERS = {
            'quarter_van': 0.25,
            'half_van': 0.5,
            'three_quarter_van': 0.75,
            'whole_van': 1.0,
        }
        
        size_options = []
        additional_options = {}
        quantity_options = []
        
        if property_type == 'house':
            size_options = list(PROPERTY_VOLUMES['house'].keys())
            additional_options = {
                'available_spaces': list(ADDITIONAL_SPACES.keys()),
                'spaces_info': ADDITIONAL_SPACES
            }
            quantity_options = list(QUANTITY_MULTIPLIERS.keys())
            
        elif property_type == 'flat':
            size_options = list(PROPERTY_VOLUMES['flat'].keys())
            quantity_options = list(QUANTITY_MULTIPLIERS.keys())
            
        elif property_type == 'office':
            size_options = list(PROPERTY_VOLUMES['office'].keys())
            quantity_options = list(QUANTITY_MULTIPLIERS.keys())
            
        elif property_type == 'a_few_items':
            size_options = list(PROPERTY_VOLUMES['a_few_items'].keys())
            quantity_options = list(VEHICLE_SPACE_MULTIPLIERS.keys())
        
        return {
            "success": True,
            "property_type": property_type,
            "size_options": size_options,
            "quantity_options": quantity_options,
            "additional_options": additional_options if additional_options else None,
            "volumes": PROPERTY_VOLUMES.get(property_type, {})
        }
        
    except Exception as e:
        frappe.log_error(f"Get Property Options Error: {str(e)}", "Property Options")
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": f"Failed to get options: {str(e)}"}
    
# ------------------------- Admin: Get All Companies ------------------------- #
@frappe.whitelist(allow_guest=True)
def get_all_companies():
    """Get all companies (Admin only)"""
    try:
        user_info = get_user_from_token()
        if user_info['role'] != "Admin":
            frappe.local.response['http_status_code'] = 403
            return {"success": False, "message": "Only Admins can access all companies"}

        companies = frappe.get_all("Logistics Company",
                                   fields=["*"],
                                   order_by="created_at desc")
        
        for company in companies:
            parse_json_fields(company)
        
        return {"success": True, "count": len(companies), "data": companies}

    except frappe.AuthenticationError as e:
        frappe.local.response['http_status_code'] = 401
        return {"success": False, "message": str(e)}
    except Exception as e:
        frappe.log_error(f"Get All Companies Error: {str(e)}", "Get All Companies")
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": f"Failed to fetch companies: {str(e)}"}
    

# @frappe.whitelist(allow_guest=True)
# def search_companies_with_cost(pincode=None, selected_items=None, distance_miles=None):
#     """
#     Search logistics companies by pincode and calculate approximate costs
    
#     Args:
#         pincode: Search pincode
#         selected_items: JSON object with item names and quantities 
#                        e.g., {"Single Bed": 2, "Wardrobe Double": 1}
#         distance_miles: Distance in miles for the move
    
#     Returns:
#         Companies with calculated costs for each
#     """
#     try:
#         data = get_request_data()
#         pincode = pincode or data.get("pincode")
#         selected_items = selected_items or data.get("selected_items")
#         distance_miles = distance_miles or data.get("distance_miles", 0)
        
#         if not pincode:
#             frappe.local.response['http_status_code'] = 400
#             return {"success": False, "message": "Pincode is required"}
        
#         # Parse selected items
#         if isinstance(selected_items, str):
#             selected_items = json.loads(selected_items)
        
#         if not selected_items:
#             selected_items = {}
        
#         # Calculate total volume from inventory
#         total_volume_m3 = 0
#         total_boxes = 0
#         item_details = []
        
#         if selected_items:
#             for item_name, quantity in selected_items.items():
#                 try:
#                     # Get item from inventory
#                     item = frappe.get_doc("Moving Inventory Item", item_name)
#                     volume = item.average_volume * int(quantity)
#                     total_volume_m3 += volume
                    
#                     # Count boxes (items with "Boxes" in name)
#                     if "box" in item_name.lower():
#                         total_boxes += int(quantity)
                    
#                     item_details.append({
#                         "item_name": item_name,
#                         "quantity": quantity,
#                         "volume_per_item": item.average_volume,
#                         "total_volume": round(volume, 2)
#                     })
#                 except Exception as e:
#                     frappe.log_error(f"Item not found: {item_name}", "Search Cost Calculation")
        
#         # Search companies by pincode
#         companies = frappe.db.sql("""
#             SELECT * 
#             FROM `tabLogistics Company`
#             WHERE is_active = 1 
#             AND (
#                 pincode = %(pincode)s 
#                 OR areas_covered LIKE %(pincode_pattern)s
#             )
#             ORDER BY created_at DESC
#         """, {
#             "pincode": pincode,
#             "pincode_pattern": f'%{pincode}%'
#         }, as_dict=True)
        
#         # Calculate costs for each company
#         for company in companies:
#             # Parse JSON fields
#             parse_json_fields(company)
            
#             # Get company pricing
#             loading_cost_per_m3 = float(company.get('loading_cost_per_m3', 0) or 0)
#             packing_cost_per_box = float(company.get('packing_cost_per_box', 0) or 0)
#             disassembly_cost_per_item = float(company.get('disassembly_cost_per_item', 0) or 0)
#             assembly_cost_per_item = float(company.get('assembly_cost_per_item', 0) or 0)
#             cost_per_mile_under_25 = float(company.get('cost_per_mile_under_25', 0) or 0)
#             cost_per_mile_over_25 = float(company.get('cost_per_mile_over_25', 0) or 0)
            
#             # Calculate component costs
#             loading_cost = total_volume_m3 * loading_cost_per_m3
#             packing_cost = total_boxes * packing_cost_per_box
            
#             # Count items needing assembly/disassembly (exclude boxes)
#             assembly_items = sum(
#                 int(qty) for name, qty in selected_items.items() 
#                 if "box" not in name.lower()
#             )
#             disassembly_cost = assembly_items * disassembly_cost_per_item
#             assembly_cost = assembly_items * assembly_cost_per_item
            
#             # Calculate distance cost
#             distance_miles = float(distance_miles or 0)
#             if distance_miles <= 25:
#                 distance_cost = distance_miles * cost_per_mile_under_25
#             else:
#                 distance_cost = (25 * cost_per_mile_under_25) + \
#                                ((distance_miles - 25) * cost_per_mile_over_25)
            
#             # Fixed content insurance (you can make this configurable)
#             content_insurance = 2000  # £2,000 fixed as shown in your UI
            
#             # Total cost
#             total_cost = (
#                 loading_cost + 
#                 packing_cost + 
#                 disassembly_cost + 
#                 assembly_cost + 
#                 distance_cost
#             )
            
#             # Add cost breakdown to company data
#             company['cost_calculation'] = {
#                 'total_volume_m3': round(total_volume_m3, 2),
#                 'total_boxes': total_boxes,
#                 'assembly_items': assembly_items,
#                 'distance_miles': distance_miles,
                
#                 'loading_cost': round(loading_cost, 2),
#                 'packing_cost': round(packing_cost, 2),
#                 'disassembly_cost': round(disassembly_cost, 2),
#                 'assembly_cost': round(assembly_cost, 2),
#                 'distance_cost': round(distance_cost, 2),
#                 'content_insurance': content_insurance,
                
#                 'removal_price': round(disassembly_cost, 2),  # Disassembly cost
#                 'add_packing': round(packing_cost, 2),        # Packing cost
#                 'total_cost': round(total_cost, 2),           # Total without insurance
#                 'total_with_insurance': round(total_cost, 2)  # Insurance shown separately
#             }
            
#             # Add pricing rates for reference
#             company['pricing_rates'] = {
#                 'loading_per_m3': loading_cost_per_m3,
#                 'packing_per_box': packing_cost_per_box,
#                 'disassembly_per_item': disassembly_cost_per_item,
#                 'assembly_per_item': assembly_cost_per_item,
#                 'cost_per_mile_under_25': cost_per_mile_under_25,
#                 'cost_per_mile_over_25': cost_per_mile_over_25
#             }
        
#         return {
#             "success": True,
#             "count": len(companies),
#             "data": companies,
#             "search_parameters": {
#                 "pincode": pincode,
#                 "total_volume_m3": round(total_volume_m3, 2),
#                 "total_boxes": total_boxes,
#                 "assembly_items": assembly_items,
#                 "distance_miles": distance_miles,
#                 "item_details": item_details
#             }
#         }
    
#     except Exception as e:
#         frappe.log_error(f"Search with Cost Error: {str(e)}", "Search Cost Calculation")
#         frappe.local.response['http_status_code'] = 500
#         return {"success": False, "message": f"Failed to search companies: {str(e)}"}


@frappe.whitelist(allow_guest=True)
def search_companies_with_cost(pincode=None, selected_items=None, distance_miles=None):
    """
    Search logistics companies by pincode and calculate costs with detailed box requirements
    Only shows companies with available request views
    
    Args:
        pincode: Search pincode
        selected_items: JSON object with item names and quantities 
                       e.g., {"Single Bed": 2, "Wardrobe Double": 1}
        distance_miles: Distance in miles for the move
    
    Returns:
        Companies with calculated costs including category-wise box breakdown
    """
    try:
        data = get_request_data()
        pincode = pincode or data.get("pincode")
        selected_items = selected_items or data.get("selected_items")
        distance_miles = distance_miles or data.get("distance_miles", 0)
        
        if not pincode:
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Pincode is required"}
        
        # Parse selected items
        if isinstance(selected_items, str):
            selected_items = json.loads(selected_items)
        
        if not selected_items:
            selected_items = {}
        
        # Box packing standards (items per box by category)
        BOX_PACKING_STANDARDS = {
            # Small items: ~5-8 items per box
            "ornaments": 8,
            "fragile": 6,
            "kitchen_small": 10,
            "bathroom_small": 10,
            
            # Medium items: ~2-4 items per box
            "books": 15,  # Books are heavy
            "clothes": 20,  # Clothes per wardrobe section
            "bedding": 5,
            "kitchenware": 8,
            
            # Default fallback
            "default_small": 8,
            "default_medium": 4
        }
        
        # Box volume capacity (standard moving boxes)
        STANDARD_BOX_VOLUME = 0.07  # m³ (approximately 1.5 cubic feet)
        
        # Calculate volume and boxes by category
        category_breakdown = {}
        total_volume_m3 = 0
        total_boxes_needed = 0
        item_details = []
        assembly_items_count = 0
        
        if selected_items:
            for item_name, quantity in selected_items.items():
                try:
                    # Get item from inventory
                    item = frappe.get_doc("Moving Inventory Item", item_name)
                    category = item.category
                    volume_per_item = item.average_volume
                    total_item_volume = volume_per_item * int(quantity)
                    total_volume_m3 += total_item_volume
                    
                    # Initialize category if not exists
                    if category not in category_breakdown:
                        category_breakdown[category] = {
                            "items": [],
                            "total_volume": 0,
                            "boxes_needed": 0,
                            "item_count": 0
                        }
                    
                    # Determine if item needs boxes (small/medium items vs furniture)
                    needs_boxing = determine_if_needs_boxing(item_name, volume_per_item)
                    
                    # Calculate boxes for this item
                    item_boxes = 0
                    if needs_boxing:
                        # Small items that fit in boxes
                        item_boxes = calculate_boxes_for_item(
                            item_name, 
                            int(quantity), 
                            volume_per_item,
                            STANDARD_BOX_VOLUME
                        )
                        category_breakdown[category]["boxes_needed"] += item_boxes
                        total_boxes_needed += item_boxes
                    else:
                        # Large furniture items don't need boxes but need assembly
                        if not is_box_item(item_name):
                            assembly_items_count += int(quantity)
                    
                    # Update category data
                    category_breakdown[category]["items"].append({
                        "item_name": item_name,
                        "quantity": quantity,
                        "volume_per_item": volume_per_item,
                        "total_volume": round(total_item_volume, 2),
                        "needs_boxing": needs_boxing,
                        "boxes_for_item": item_boxes
                    })
                    category_breakdown[category]["total_volume"] += total_item_volume
                    category_breakdown[category]["item_count"] += int(quantity)
                    
                    # Add to item details
                    item_details.append({
                        "item_name": item_name,
                        "category": category,
                        "quantity": quantity,
                        "volume_per_item": volume_per_item,
                        "total_volume": round(total_item_volume, 2),
                        "needs_boxing": needs_boxing,
                        "boxes_needed": item_boxes
                    })
                    
                except Exception as e:
                    frappe.log_error(f"Item not found: {item_name} - {str(e)}", "Search Cost Calculation")
        
        # Round category volumes
        for category in category_breakdown:
            category_breakdown[category]["total_volume"] = round(
                category_breakdown[category]["total_volume"], 2
            )
        
        # Search companies by pincode
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
        
        # Filter and calculate costs for available companies
        available_companies = []
        
        for company in companies:
            # Check subscription limit FIRST
            if not check_company_can_view_requests(company):
                continue
            
            # Parse JSON fields
            parse_json_fields(company)
            
            # Get company pricing
            loading_cost_per_m3 = float(company.get('loading_cost_per_m3', 0) or 0)
            packing_cost_per_box = float(company.get('packing_cost_per_box', 0) or 0)
            disassembly_cost_per_item = float(company.get('disassembly_cost_per_item', 0) or 0)
            assembly_cost_per_item = float(company.get('assembly_cost_per_item', 0) or 0)
            cost_per_mile_under_25 = float(company.get('cost_per_mile_under_25', 0) or 0)
            cost_per_mile_over_25 = float(company.get('cost_per_mile_over_25', 0) or 0)
            
            # Calculate component costs
            loading_cost = total_volume_m3 * loading_cost_per_m3
            
            # ACCURATE PACKING COST based on actual boxes needed
            packing_cost = total_boxes_needed * packing_cost_per_box
            
            # Assembly costs (only for furniture, not boxes)
            disassembly_cost = assembly_items_count * disassembly_cost_per_item
            assembly_cost = assembly_items_count * assembly_cost_per_item
            
            # Calculate distance cost
            distance_miles = float(distance_miles or 0)
            if distance_miles <= 25:
                distance_cost = distance_miles * cost_per_mile_under_25
            else:
                distance_cost = (25 * cost_per_mile_under_25) + \
                               ((distance_miles - 25) * cost_per_mile_over_25)
            
            # Fixed content insurance
            content_insurance = 2000
            
            # Total cost
            total_cost = (
                loading_cost + 
                packing_cost + 
                disassembly_cost + 
                assembly_cost + 
                distance_cost
            )
            
            # Add cost breakdown to company data
            company['cost_calculation'] = {
                'total_volume_m3': round(total_volume_m3, 2),
                'total_boxes_needed': total_boxes_needed,
                'assembly_items': assembly_items_count,
                'distance_miles': distance_miles,
                
                'loading_cost': round(loading_cost, 2),
                'packing_cost': round(packing_cost, 2),
                'disassembly_cost': round(disassembly_cost, 2),
                'assembly_cost': round(assembly_cost, 2),
                'distance_cost': round(distance_cost, 2),
                'content_insurance': content_insurance,
                
                'removal_price': round(disassembly_cost, 2),
                'add_packing': round(packing_cost, 2),
                'total_cost': round(total_cost, 2),
                'total_with_insurance': round(total_cost, 2),
                
                # Category-wise breakdown
                'category_breakdown': category_breakdown
            }
            
            # Add pricing rates
            company['pricing_rates'] = {
                'loading_per_m3': loading_cost_per_m3,
                'packing_per_box': packing_cost_per_box,
                'disassembly_per_item': disassembly_cost_per_item,
                'assembly_per_item': assembly_cost_per_item,
                'cost_per_mile_under_25': cost_per_mile_under_25,
                'cost_per_mile_over_25': cost_per_mile_over_25
            }
            
            # Add subscription info
            plan = company.get('subscription_plan', 'Free')
            viewed = int(company.get('requests_viewed_this_month', 0) or 0)
            limit = PLAN_LIMITS.get(plan, 5)
            
            company['subscription_info'] = {
                'plan': plan,
                'views_used': viewed,
                'views_limit': limit if limit != -1 else 'Unlimited',
                'views_remaining': (limit - viewed) if limit != -1 else 'Unlimited'
            }
            
            available_companies.append(company)
        
        return {
            "success": True,
            "count": len(available_companies),
            "total_companies": len(companies),
            "filtered_out": len(companies) - len(available_companies),
            "data": available_companies,
            "search_parameters": {
                "pincode": pincode,
                "total_volume_m3": round(total_volume_m3, 2),
                "total_boxes_needed": total_boxes_needed,
                "assembly_items": assembly_items_count,
                "distance_miles": distance_miles,
                "item_details": item_details,
                "category_breakdown": category_breakdown
            },
            "packing_summary": {
                "standard_box_volume": STANDARD_BOX_VOLUME,
                "total_boxes_needed": total_boxes_needed,
                "categories_requiring_boxes": len([c for c in category_breakdown.values() if c["boxes_needed"] > 0])
            }
        }
    
    except Exception as e:
        frappe.log_error(f"Search with Cost Error: {str(e)}", "Search Cost Calculation")
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": f"Failed to search companies: {str(e)}"}


# Helper functions for box calculation
def is_box_item(item_name):
    """Check if item is already a box"""
    return "box" in item_name.lower() or "boxes" in item_name.lower()


def determine_if_needs_boxing(item_name, volume):
    """
    Determine if an item needs to be packed in boxes
    Returns True for small/medium items, False for large furniture
    """
    item_name_lower = item_name.lower()
    
    # Items that DON'T need boxes (large furniture)
    large_furniture_keywords = [
        "bed", "sofa", "wardrobe", "table", "chair", "desk", 
        "cabinet", "bookcase", "fridge", "freezer", "washing machine",
        "dishwasher", "cooker", "piano", "chest of drawers"
    ]
    
    for keyword in large_furniture_keywords:
        if keyword in item_name_lower:
            return False
    
    # Items that DO need boxes (small/medium items)
    boxing_keywords = [
        "ornaments", "plant", "shelves contents", "fragile",
        "kitchen bin", "general", "garden tools", "suitcase",
        "other", "misc"
    ]
    
    for keyword in boxing_keywords:
        if keyword in item_name_lower:
            return True
    
    # If already a box item, it doesn't need more boxes
    if is_box_item(item_name):
        return False
    
    # Default: items with volume < 0.5 m³ typically need boxing
    return volume < 0.5


def calculate_boxes_for_item(item_name, quantity, volume_per_item, box_volume):
    """
    Calculate number of boxes needed for an item
    
    Args:
        item_name: Name of the item
        quantity: Number of items
        volume_per_item: Volume of one item in m³
        box_volume: Volume of standard box in m³
    
    Returns:
        Number of boxes needed (rounded up)
    """
    import math
    
    item_name_lower = item_name.lower()
    
    # Special cases where items are already counted as boxes
    if is_box_item(item_name):
        return quantity
    
    # Calculate total volume for these items
    total_item_volume = volume_per_item * quantity
    
    # Packing efficiency factor (boxes aren't packed 100% efficiently)
    PACKING_EFFICIENCY = 0.7  # 70% efficiency
    
    # Calculate boxes needed
    effective_box_volume = box_volume * PACKING_EFFICIENCY
    boxes_needed = total_item_volume / effective_box_volume
    
    # Round up to nearest box
    return math.ceil(boxes_needed)


def get_category_box_summary(category_breakdown):
    """
    Generate a human-readable summary of boxes per category
    """
    summary = []
    for category, data in category_breakdown.items():
        if data["boxes_needed"] > 0:
            summary.append({
                "category": category,
                "boxes": data["boxes_needed"],
                "items": data["item_count"],
                "volume": data["total_volume"]
            })
    return summary


@frappe.whitelist(allow_guest=True)
def calculate_box_requirements(selected_items=None):
    """
    Calculate box requirements without searching for companies
    Useful for previewing packing needs
    
    Args:
        selected_items: JSON object with item names and quantities
    
    Returns:
        Detailed breakdown of boxes needed per category
    """
    try:
        data = get_request_data()
        selected_items = selected_items or data.get("selected_items")
        
        if isinstance(selected_items, str):
            selected_items = json.loads(selected_items)
        
        if not selected_items:
            return {
                "success": False,
                "message": "No items provided"
            }
        
        STANDARD_BOX_VOLUME = 0.07  # m³
        
        category_breakdown = {}
        total_boxes = 0
        total_volume = 0
        
        for item_name, quantity in selected_items.items():
            try:
                item = frappe.get_doc("Moving Inventory Item", item_name)
                category = item.category
                volume_per_item = item.average_volume
                total_item_volume = volume_per_item * int(quantity)
                total_volume += total_item_volume
                
                if category not in category_breakdown:
                    category_breakdown[category] = {
                        "items": [],
                        "total_volume": 0,
                        "boxes_needed": 0,
                        "item_count": 0
                    }
                
                needs_boxing = determine_if_needs_boxing(item_name, volume_per_item)
                item_boxes = 0
                
                if needs_boxing:
                    item_boxes = calculate_boxes_for_item(
                        item_name,
                        int(quantity),
                        volume_per_item,
                        STANDARD_BOX_VOLUME
                    )
                    category_breakdown[category]["boxes_needed"] += item_boxes
                    total_boxes += item_boxes
                
                category_breakdown[category]["items"].append({
                    "item_name": item_name,
                    "quantity": quantity,
                    "volume_per_item": volume_per_item,
                    "total_volume": round(total_item_volume, 2),
                    "needs_boxing": needs_boxing,
                    "boxes_for_item": item_boxes
                })
                category_breakdown[category]["total_volume"] += total_item_volume
                category_breakdown[category]["item_count"] += int(quantity)
                
            except Exception as e:
                frappe.log_error(f"Item error: {item_name} - {str(e)}", "Box Calculation")
        
        # Round volumes
        for category in category_breakdown:
            category_breakdown[category]["total_volume"] = round(
                category_breakdown[category]["total_volume"], 2
            )
        
        return {
            "success": True,
            "total_boxes_needed": total_boxes,
            "total_volume_m3": round(total_volume, 2),
            "standard_box_volume": STANDARD_BOX_VOLUME,
            "category_breakdown": category_breakdown,
            "box_summary": get_category_box_summary(category_breakdown),
            "estimated_box_cost_range": {
                "min_per_box": 5,  # Example rates
                "max_per_box": 15,
                "estimated_min_total": total_boxes * 5,
                "estimated_max_total": total_boxes * 15,
                "note": "Actual packing cost depends on company rates"
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Box Requirements Error: {str(e)}", "Box Calculation")
        frappe.local.response['http_status_code'] = 500
        return {"success": False, "message": f"Failed to calculate: {str(e)}"}

@frappe.whitelist(allow_guest=True)
def get_inventory_categories():
    """Get all inventory categories for filtering"""
    try:
        categories = frappe.db.sql("""
            SELECT DISTINCT category 
            FROM `tabMoving Inventory Item`
            ORDER BY category
        """, as_dict=True)
        
        return {
            "success": True,
            "data": [cat['category'] for cat in categories]
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def get_items_by_category(category=None):
    """Get inventory items by category for selection"""
    try:
        data = get_request_data()
        category = category or data.get("category")
        
        filters = {}
        if category:
            filters["category"] = category
        
        items = frappe.get_all(
            "Moving Inventory Item",
            filters=filters,
            fields=["name", "category", "item_name", "average_volume", "unit"],
            order_by="item_name"
        )
        
        return {
            "success": True,
            "count": len(items),
            "data": items
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
    


@frappe.whitelist(allow_guest=True)
def search_companies_with_ratings(pincode=None):
    """
    Enhanced company search that includes rating information
    
    Request Body:
    {
        "pincode": "SW1A 1AA"
    }
    
    Response includes:
    - Basic company info
    - Average rating and total ratings
    - Recent reviews preview
    - Rating distribution
    """
    try:
        data = frappe.request.get_json() or {}
        pincode = pincode or safe_get_dict_value(data, 'pincode')
        
        if not pincode:
            return {"success": False, "message": "Pincode is required"}
        
        # Search companies
        companies = frappe.db.sql("""
            SELECT 
                company_name,
                manager_email,
                phone,
                pincode,
                location,
                address,
                description,
                subscription_plan,
                is_active,
                average_rating,
                total_ratings,
                created_at
            FROM `tabLogistics Company`
            WHERE is_active = 1 
            AND (
                pincode = %(pincode)s 
                OR areas_covered LIKE %(pincode_pattern)s
            )
            ORDER BY average_rating DESC, total_ratings DESC, created_at DESC
        """, {
            "pincode": pincode,
            "pincode_pattern": f'%{pincode}%'
        }, as_dict=True)
        
        enriched_companies = []
        
        for company in companies:
            # Get rating distribution
            rating_dist = frappe.db.sql("""
                SELECT 
                    rating,
                    COUNT(*) as count
                FROM `tabLogistics Request`
                WHERE company_name = %(company_name)s
                AND rating IS NOT NULL
                AND rating > 0
                GROUP BY rating
                ORDER BY rating DESC
            """, {"company_name": company['company_name']}, as_dict=True)
            
            company['rating_distribution'] = {
                str(r['rating']): r['count'] for r in rating_dist
            }
            
            # Get 3 most recent reviews preview
            recent_reviews = frappe.db.sql("""
                SELECT 
                    rating,
                    review_comment,
                    rated_at,
                    full_name as user_name
                FROM `tabLogistics Request`
                WHERE company_name = %(company_name)s
                AND rating IS NOT NULL
                AND rating > 0
                AND review_comment IS NOT NULL
                AND review_comment != ''
                ORDER BY rated_at DESC
                LIMIT 3
            """, {"company_name": company['company_name']}, as_dict=True)
            
            # Format recent reviews
            for review in recent_reviews:
                review['rated_at'] = str(review['rated_at'])
                # Truncate long reviews
                if len(review['review_comment']) > 150:
                    review['review_comment'] = review['review_comment'][:150] + "..."
            
            company['recent_reviews_preview'] = recent_reviews
            
            # Calculate rating badge
            avg_rating = company.get('average_rating', 0)
            if avg_rating >= 4.5:
                company['rating_badge'] = "Excellent"
                company['rating_badge_color'] = "#28a745"
            elif avg_rating >= 4.0:
                company['rating_badge'] = "Very Good"
                company['rating_badge_color'] = "#5cb85c"
            elif avg_rating >= 3.5:
                company['rating_badge'] = "Good"
                company['rating_badge_color'] = "#f0ad4e"
            elif avg_rating >= 3.0:
                company['rating_badge'] = "Average"
                company['rating_badge_color'] = "#ff9800"
            elif avg_rating > 0:
                company['rating_badge'] = "Below Average"
                company['rating_badge_color'] = "#dc3545"
            else:
                company['rating_badge'] = "No Ratings Yet"
                company['rating_badge_color'] = "#6c757d"
            
            enriched_companies.append(company)
        
        return {
            "success": True,
            "count": len(enriched_companies),
            "data": enriched_companies,
            "search_criteria": {
                "pincode": pincode
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Search Companies with Ratings Error: {str(e)}")
        return {"success": False, "message": f"Failed to search: {str(e)}"}


# ==================== GET TOP RATED COMPANIES ====================

@frappe.whitelist(allow_guest=True)
def get_top_rated_companies(limit=10):
    """
    Get top rated companies across the platform
    
    Query Parameters:
    - limit: Number of companies to return (default: 10)
    """
    try:
        data = frappe.request.get_json() or {}
        limit = limit or safe_get_dict_value(data, 'limit', 10)
        
        # Get top rated companies (must have at least 5 ratings)
        top_companies = frappe.db.sql("""
            SELECT 
                company_name,
                location,
                pincode,
                average_rating,
                total_ratings,
                description
            FROM `tabLogistics Company`
            WHERE is_active = 1
            AND total_ratings >= 5
            ORDER BY average_rating DESC, total_ratings DESC
            LIMIT %(limit)s
        """, {"limit": limit}, as_dict=True)
        
        # Get sample reviews for each
        for company in top_companies:
            reviews = frappe.db.sql("""
                SELECT 
                    rating,
                    review_comment,
                    full_name as user_name,
                    rated_at
                FROM `tabLogistics Request`
                WHERE company_name = %(company_name)s
                AND rating >= 4
                AND review_comment IS NOT NULL
                AND review_comment != ''
                ORDER BY rated_at DESC
                LIMIT 2
            """, {"company_name": company['company_name']}, as_dict=True)
            
            for review in reviews:
                review['rated_at'] = str(review['rated_at'])
                if len(review['review_comment']) > 200:
                    review['review_comment'] = review['review_comment'][:200] + "..."
            
            company['featured_reviews'] = reviews
        
        return {
            "success": True,
            "count": len(top_companies),
            "data": top_companies,
            "message": f"Top {len(top_companies)} rated companies (minimum 5 ratings)"
        }
        
    except Exception as e:
        frappe.log_error(f"Get Top Rated Companies Error: {str(e)}")
        return {"success": False, "message": f"Failed to fetch: {str(e)}"}


# ==================== GET COMPANY DETAILED INFO WITH RATINGS ====================

@frappe.whitelist(allow_guest=True)
def get_company_detailed_info(company_name=None):
    """
    Get comprehensive company information including ratings
    
    Request Body:
    {
        "company_name": "ABC Logistics"
    }
    """
    try:
        data = frappe.request.get_json() or {}
        company_name = company_name or safe_get_dict_value(data, 'company_name')
        
        if not company_name:
            return {"success": False, "message": "company_name is required"}
        
        if not frappe.db.exists("Logistics Company", company_name):
            return {"success": False, "message": "Company not found"}
        
        # Get company basic info
        company = frappe.get_doc("Logistics Company", company_name)
        company_dict = company.as_dict()
        
        # Parse JSON fields
        json_fields = ['areas_covered', 'company_gallery', 'includes', 'material',
                      'protection', 'furniture', 'appliances']
        for field in json_fields:
            if field in company_dict and company_dict[field]:
                try:
                    if isinstance(company_dict[field], str):
                        company_dict[field] = json.loads(company_dict[field])
                except:
                    company_dict[field] = []
        
        # Get rating statistics
        rating_stats = frappe.db.sql("""
            SELECT 
                AVG(rating) as avg_rating,
                COUNT(*) as total_ratings,
                SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) as five_star,
                SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) as four_star,
                SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) as three_star,
                SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) as two_star,
                SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as one_star
            FROM `tabLogistics Request`
            WHERE company_name = %(company_name)s
            AND rating IS NOT NULL
            AND rating > 0
        """, {"company_name": company_name}, as_dict=True)
        
        rating_info = rating_stats[0] if rating_stats else {}
        
        # Calculate percentages
        total = rating_info.get('total_ratings', 0)
        if total > 0:
            rating_info['five_star_pct'] = round((rating_info.get('five_star', 0) / total) * 100, 1)
            rating_info['four_star_pct'] = round((rating_info.get('four_star', 0) / total) * 100, 1)
            rating_info['three_star_pct'] = round((rating_info.get('three_star', 0) / total) * 100, 1)
            rating_info['two_star_pct'] = round((rating_info.get('two_star', 0) / total) * 100, 1)
            rating_info['one_star_pct'] = round((rating_info.get('one_star', 0) / total) * 100, 1)
        
        # Get all reviews with pagination
        all_reviews = frappe.db.sql("""
            SELECT 
                name as request_id,
                rating,
                review_comment,
                service_aspects,
                rated_at,
                full_name as user_name,
                pickup_city,
                delivery_city
            FROM `tabLogistics Request`
            WHERE company_name = %(company_name)s
            AND rating IS NOT NULL
            AND rating > 0
            ORDER BY rated_at DESC
            LIMIT 50
        """, {"company_name": company_name}, as_dict=True)
        
        # Format reviews
        for review in all_reviews:
            review['rated_at'] = str(review['rated_at'])
            if review.get('service_aspects'):
                try:
                    review['service_aspects'] = json.loads(review['service_aspects'])
                except:
                    review['service_aspects'] = {}
        
        company_dict['rating_statistics'] = rating_info
        company_dict['all_reviews'] = all_reviews
        
        return {
            "success": True,
            "data": company_dict
        }
        
    except Exception as e:
        frappe.log_error(f"Get Company Detailed Info Error: {str(e)}")
        return {"success": False, "message": f"Failed to fetch: {str(e)}"}