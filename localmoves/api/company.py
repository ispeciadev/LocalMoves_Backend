
import frappe
from frappe import _
from localmoves.utils.jwt_handler import get_current_user
from localmoves.utils.config_manager import (
    get_config,
    get_vehicle_capacities,
    get_property_volumes,
    get_additional_spaces,
    get_quantity_multipliers,
    get_vehicle_space_multipliers,
    get_plan_limits,
    get_pricing_config,              # ADD THIS
    get_collection_assessment,       # ADD THIS
    get_notice_period_multipliers,   # ADD THIS
    get_move_day_multipliers         # ADD THIS
)
from datetime import datetime
import json

@frappe.whitelist(allow_guest=False)
def fix_assessment_config():
    from localmoves.utils.config_manager import update_config, get_config
    
    config = get_config()
    config['collection_assessment'] = {
        'parking': {'driveway': 0.0, 'roadside': 0.0},
        'parking_distance': {'less_than_10m': 0.05, '10_to_20m': 0.10, 'over_20m': 0.15},
        'house_type': {'house_ground_and_1st': 0.05, 'bungalow_ground': 0.0, 'townhouse_ground_1st_2nd': 0.10},
        'internal_access': {'stairs_only': 0.0, 'lift_access': 0.025},
        'floor_level': {'ground_floor': 0.0, '1st_floor': 0.10, '2nd_floor': 0.15, '3rd_floor_plus': 0.20}
    }
    update_config(config)
    return {"success": True, "message": "Fixed"}
# ==================== DYNAMIC CONSTANTS FROM CONFIG MANAGER ====================
# These constants are now loaded from the System Configuration doctype
# Admins can update these via the dashboard without code changes

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
    
    # Get limit for the plan from dynamic config
    plan_limits = get_plan_limits()
    limit = plan_limits.get(plan, 5)  # Default to 5 if plan not found
    
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
                # limit = PLAN_LIMITS.get(plan, 5)
                
                # company['subscription_info'] = {
                #     'plan': plan,
                #     'views_used': viewed,
                #     'views_limit': limit if limit != -1 else 'Unlimited',
                #     'views_remaining': (limit - viewed) if limit != -1 else 'Unlimited'
                # }
                
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



def auto_calculate_volumes(selected_items, dismantle_items):
    """
    Automatically calculate packing, dismantling, and reassembly volumes
    
    Args:
        selected_items: Dict of item names and quantities
        dismantle_items: Dict of item names marked for dismantling
    
    Returns:
        dict with packing_volume_m3, dismantling_volume_m3, reassembly_volume_m3
    """
    # Items that ALWAYS need packing (small/fragile items)
    # ALWAYS_PACK_KEYWORDS = [
    #     'ornaments', 'fragile', 'plant', 'suitcase', 'boxes',
    #     'kitchen bin', 'general', 'garden tools', 'shelves contents',
    #     'misc', 'other', 'accessories', 'decorations'
    # ]
    
    # # Items that NEVER need packing (large furniture/appliances)
    # NEVER_PACK_KEYWORDS = [
    #     'bed', 'mattress', 'sofa', 'wardrobe', 'table', 'chair',
    #     'desk', 'cabinet', 'bookcase', 'chest', 'drawers',
    #     'fridge', 'freezer', 'washing', 'dishwasher', 'cooker',
    #     'tv', 'stand', 'sideboard', 'cot', 'bunk'
    # ]
    
    # Small threshold: items under this volume (m³) need packing
    SMALL_ITEM_THRESHOLD = 0.5  # Items smaller than 0.5m³ typically need packing
    
    packing_volume = 0
    dismantling_volume = 0
    reassembly_volume = 0
    
    for item_name, quantity in selected_items.items():
        try:
            # Get item from inventory
            item = frappe.get_doc("Moving Inventory Item", item_name)
            volume_per_item = item.average_volume
            total_item_volume = volume_per_item * int(quantity)
            
            item_name_lower = item_name.lower()
            
            # ========== 1. PACKING VOLUME ==========
            needs_packing = False
            
            # First check: Does it ALWAYS need packing? (small items)
            for keyword in ALWAYS_PACK_KEYWORDS:
                if keyword in item_name_lower:
                    needs_packing = True
                    break
            
            # Second check: Is it large furniture that NEVER needs packing?
            is_large_furniture = False
            for keyword in NEVER_PACK_KEYWORDS:
                if keyword in item_name_lower:
                    is_large_furniture = True
                    break
            
            # If not explicitly categorized, use volume threshold
            if not needs_packing and not is_large_furniture:
                if volume_per_item < SMALL_ITEM_THRESHOLD:
                    needs_packing = True
            
            # Override: large furniture never gets packed
            if is_large_furniture:
                needs_packing = False
            
            # Add to packing volume if needed
            if needs_packing:
                packing_volume += total_item_volume
            
            # ========== 2. DISMANTLING VOLUME ==========
            # Check if item is marked for dismantling
            if dismantle_items.get(item_name, False):
                dismantling_volume += total_item_volume
                # If dismantled, it will also need reassembly
                reassembly_volume += total_item_volume
            
        except Exception as e:
            frappe.log_error(f"Volume calculation error for {item_name}: {str(e)}", 
                           "Auto Calculate Volumes")
            continue
    
    return {
        'packing_volume_m3': round(packing_volume, 2),
        'dismantling_volume_m3': round(dismantling_volume, 2),
        'reassembly_volume_m3': round(reassembly_volume, 2)
    }


def calculate_total_volume(pricing_data):
    """Calculate total volume based on property type"""
    property_type = pricing_data.get('property_type')
    total_volume = 0
    
    # Load dynamic config
    property_volumes = get_property_volumes()
    additional_spaces = get_additional_spaces()
    quantity_multipliers = get_quantity_multipliers()
    vehicle_space_multipliers = get_vehicle_space_multipliers()
    
    if property_type == 'a_few_items':
        vehicle_type = pricing_data.get('vehicle_type')
        space_usage = pricing_data.get('space_usage')
        base_volume = property_volumes['a_few_items'].get(vehicle_type, 0)
        multiplier = vehicle_space_multipliers.get(space_usage, 1.0)
        total_volume = base_volume * multiplier
        
    elif property_type == 'house':
        house_size = pricing_data.get('house_size')
        add_spaces = pricing_data.get('additional_spaces', [])
        quantity = pricing_data.get('quantity')
        base_volume = property_volumes['house'].get(house_size, 0)
        for space in add_spaces:
            base_volume += additional_spaces.get(space, 0)
        multiplier = quantity_multipliers.get(quantity, 1.0)
        total_volume = base_volume * multiplier
        
    elif property_type == 'flat':
        flat_size = pricing_data.get('flat_size')
        quantity = pricing_data.get('quantity')
        base_volume = property_volumes['flat'].get(flat_size, 0)
        multiplier = quantity_multipliers.get(quantity, 1.0)
        total_volume = base_volume * multiplier
        
    elif property_type == 'office':
        office_size = pricing_data.get('office_size')
        quantity = pricing_data.get('quantity')
        base_volume = property_volumes['office'].get(office_size, 0)
        multiplier = quantity_multipliers.get(quantity, 1.0)
        total_volume = base_volume * multiplier
    
    return round(total_volume, 2)


def calculate_loading_cost(total_volume, loading_cost_per_m3):
    """Calculate base loading cost"""
    return round(total_volume * loading_cost_per_m3, 2)


def calculate_mileage_cost(distance_miles, total_volume, cost_per_mile_under_25, cost_per_mile_over_25):
    """
    Calculate mileage cost based on distance and volume
    SIMPLIFIED: Uses cost_per_mile_under_25 for ALL distances (ignoring over_25 param)
    Formula: Distance × Volume × Cost per Mile
    """
    distance = float(distance_miles or 0)
    
    # Use only the under_25 rate for all distances (as per spreadsheet)
    mileage_cost = distance * total_volume * cost_per_mile_under_25
    
    return round(mileage_cost, 2)

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
            # Base total (loading + mileage only - as per spreadsheet)
            base_total = loading_cost + mileage_cost

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
                
                # NO estimated_range - just the base total as per spreadsheet
                'note': 'Base cost includes loading and mileage. Optional extras (packing, assembly, disassembly) quoted separately.',
                
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
            # limit = PLAN_LIMITS.get(plan, 5)
            
            # company['subscription_info'] = {
            #     'plan': plan,
            #     'views_used': viewed,
            #     'views_limit': limit if limit != -1 else 'Unlimited',
            #     'views_remaining': (limit - viewed) if limit != -1 else 'Unlimited'
            # }
            
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
    


"""
CORRECTED search_companies_with_cost
Aligned with request_pricing.py spreadsheet formula
"""

# OPTIMIZED search_companies_with_cost - Fully Integrated with config_manager.py
# This version uses config_manager for ALL constants instead of hardcoding

@frappe.whitelist(allow_guest=True)
def search_companies_with_cost(
    pincode=None, 
    selected_items=None, 
    dismantle_items=None,
    distance_miles=None,
    pickup_address=None,
    pickup_city=None,
    delivery_address=None,
    delivery_city=None,
    property_type=None,
    property_size=None,
    additional_spaces=None,
    quantity=None,
    include_packing=True,
    include_dismantling=True,
    include_reassembly=True,
    collection_parking=None,
    collection_parking_distance=None,
    collection_house_type=None,
    collection_internal_access=None,
    collection_floor_level=None,
    delivery_parking=None,
    delivery_parking_distance=None,
    delivery_house_type=None,
    delivery_internal_access=None,
    delivery_floor_level=None,
    notice_period=None,
    move_day=None,
    collection_time=None,
    user_email=None,
    send_email=False
):
    """
    Search companies with EXACT pricing using config_manager.py
    All constants are now dynamically loaded from System Configuration
    """
    try:
        data = get_request_data()
        
        # Extract parameters
        pincode = pincode or data.get("pincode")
        selected_items = selected_items or data.get("selected_items")
        dismantle_items = dismantle_items or data.get("dismantle_items")
        distance_miles = distance_miles or data.get("distance_miles", 0)
        
        pickup_address = pickup_address or data.get("pickup_address")
        pickup_city = pickup_city or data.get("pickup_city")
        delivery_address = delivery_address or data.get("delivery_address")
        delivery_city = delivery_city or data.get("delivery_city")
        
        property_type = property_type or data.get("property_type")
        property_size = property_size or data.get("property_size")
        additional_spaces = additional_spaces or data.get("additional_spaces", [])
        quantity = quantity or data.get("quantity", "everything")
        
        include_packing = data.get("include_packing", True) if "include_packing" in data else True
        include_dismantling = data.get("include_dismantling", True) if "include_dismantling" in data else True
        include_reassembly = data.get("include_reassembly", True) if "include_reassembly" in data else True
        
        # Collection assessment
        collection_parking = collection_parking or data.get("collection_parking", "driveway")
        collection_parking_distance = collection_parking_distance or data.get("collection_parking_distance", "less_than_10m")
        collection_house_type = collection_house_type or data.get("collection_house_type", "house_ground_and_1st")
        collection_internal_access = collection_internal_access or data.get("collection_internal_access", "stairs_only")
        collection_floor_level = collection_floor_level or data.get("collection_floor_level", "ground_floor")
        
        # Delivery assessment
        delivery_parking = delivery_parking or data.get("delivery_parking", "driveway")
        delivery_parking_distance = delivery_parking_distance or data.get("delivery_parking_distance", "less_than_10m")
        delivery_house_type = delivery_house_type or data.get("delivery_house_type", "house_ground_and_1st")
        delivery_internal_access = delivery_internal_access or data.get("delivery_internal_access", "stairs_only")
        delivery_floor_level = delivery_floor_level or data.get("delivery_floor_level", "ground_floor")
        
        # Move date data
        notice_period = notice_period or data.get("notice_period", "within_month")
        move_day = move_day or data.get("move_day", "sun_to_thurs")
        collection_time = collection_time or data.get("collection_time", "flexible")
        
        user_email = user_email or data.get("user_email")
        send_email = send_email or data.get("send_email", False)
        
        if not pincode:
            frappe.local.response['http_status_code'] = 400
            return {"success": False, "message": "Pincode is required"}
        
        # Parse JSON inputs
        if isinstance(selected_items, str):
            selected_items = json.loads(selected_items)
        if isinstance(dismantle_items, str):
            dismantle_items = json.loads(dismantle_items)
        if isinstance(additional_spaces, str):
            additional_spaces = json.loads(additional_spaces)
        
        selected_items = selected_items or {}
        dismantle_items = dismantle_items or {}
        additional_spaces = additional_spaces or []
        
        # Get user email from token if needed
        if send_email and not user_email:
            try:
                user_info = get_user_from_token()
                user_email = user_info.get('email')
            except:
                user_email = None
        
        # ========== LOAD ALL CONSTANTS FROM CONFIG MANAGER ==========
        additional_spaces_config = get_additional_spaces()
        property_volumes_config = get_property_volumes()
        quantity_multipliers_config = get_quantity_multipliers()
        collection_assessment_config = get_collection_assessment()
        notice_multipliers_config = get_notice_period_multipliers()
        move_day_multipliers_config = get_move_day_multipliers()
        pricing_config = get_pricing_config()
        
        # ========== INITIALIZE ALL VOLUME VARIABLES ==========
        total_volume_m3 = 0
        packing_volume_m3 = 0
        dismantling_volume_m3 = 0
        reassembly_volume_m3 = 0
        item_details = []
        missing_items = []
        
        # ========== CALCULATE VOLUMES FROM SELECTED ITEMS ==========
        if selected_items:
            for item_name, quantity_val in selected_items.items():
                try:
                    # Check if item exists first
                    if not frappe.db.exists("Moving Inventory Item", item_name):
                        missing_items.append(item_name)
                        safe_log("Missing Inventory Item", f"Item '{item_name}' not found in database")
                        continue
                    
                    item = frappe.get_doc("Moving Inventory Item", item_name)
                    volume_per_item = item.average_volume
                    item_quantity = int(quantity_val)
                    item_total_volume = volume_per_item * item_quantity
                    
                    total_volume_m3 += item_total_volume
                    
                    # Check if this item is marked for dismantling
                    if dismantle_items.get(item_name, False):
                        dismantling_volume_m3 += item_total_volume
                    
                    # Check if this item needs packing (small items)
                    item_name_lower = item_name.lower()
                    needs_packing = determine_if_needs_boxing(item_name_lower, volume_per_item)
                    if needs_packing:
                        packing_volume_m3 += item_total_volume
                    
                    item_details.append({
                        "item_name": item_name,
                        "quantity": item_quantity,
                        "volume_per_item": volume_per_item,
                        "total_volume": round(item_total_volume, 2),
                        "needs_dismantling": dismantle_items.get(item_name, False),
                        "needs_packing": needs_packing
                    })
                    
                except Exception as e:
                    missing_items.append(item_name)
                    safe_log(f"Item Error: {item_name}", str(e))
                    continue
        
        # ========== FALLBACK TO PROPERTY-BASED CALCULATION ==========
        if total_volume_m3 == 0 and property_type:
            if property_type == 'house' and additional_spaces:
                # Use config for house calculation with additional spaces
                base_volume = property_volumes_config.get('house', {}).get(property_size, 0)
                for space in additional_spaces:
                    base_volume += additional_spaces_config.get(space, 0)
                multiplier = quantity_multipliers_config.get(quantity, 1.0)
                total_volume_m3 = base_volume * multiplier
            else:
                # Use standard property calculation
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
                    pricing_data['space_usage'] = quantity
                
                total_volume_m3 = calculate_total_volume(pricing_data)
            
            # For property-based, estimate packing/dismantling volumes
            if include_packing:
                packing_volume_m3 = total_volume_m3 * 0.3  # 30% needs packing
            if include_dismantling:
                dismantling_volume_m3 = total_volume_m3 * 0.1  # 10% needs dismantling
        
        # If dismantling is included, reassembly volume = dismantling volume
        reassembly_volume_m3 = dismantling_volume_m3 if include_dismantling else 0
        
        # ========== SEARCH COMPANIES ==========
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
            
            parse_json_fields(company)
            
            # ========== GET COMPANY RATES (with fallback to config defaults) ==========
            company_rates = {
                'loading_cost_per_m3': float(company.get('loading_cost_per_m3', 0) or pricing_config.get('loading_cost_per_m3', 35.00)),
                'disassembly_per_m3': float(company.get('disassembly_cost_per_item', 0) or pricing_config.get('disassembly_per_m3', 25.00)),
                'assembly_per_m3': float(company.get('assembly_cost_per_item', 0) or pricing_config.get('assembly_per_m3', 50.00)),
                'cost_per_mile_under_100': float(company.get('cost_per_mile_under_25', 0) or pricing_config.get('cost_per_mile_under_100', 0.25)),
                'cost_per_mile_over_100': float(company.get('cost_per_mile_over_25', 0) or pricing_config.get('cost_per_mile_over_100', 0.15)),
            }
            
            # ========== CALCULATE PROPERTY ASSESSMENT (ADDITIVE) - FROM CONFIG ==========
            collection_increment = 0.0
            collection_increment += collection_assessment_config.get('parking', {}).get(collection_parking, 0.0)
            collection_increment += collection_assessment_config.get('parking_distance', {}).get(collection_parking_distance, 0.0)
            
            if property_type in ['house']:
                collection_increment += collection_assessment_config.get('house_type', {}).get(collection_house_type, 0.0)
            else:
                collection_increment += collection_assessment_config.get('internal_access', {}).get(collection_internal_access, 0.0)
                collection_increment += collection_assessment_config.get('floor_level', {}).get(collection_floor_level, 0.0)
            
            # Delivery Assessment
            delivery_increment = 0.0
            delivery_increment += collection_assessment_config.get('parking', {}).get(delivery_parking, 0.0)
            delivery_increment += collection_assessment_config.get('parking_distance', {}).get(delivery_parking_distance, 0.0)
            
            if property_type in ['house']:
                delivery_increment += collection_assessment_config.get('house_type', {}).get(delivery_house_type, 0.0)
            else:
                delivery_increment += collection_assessment_config.get('internal_access', {}).get(delivery_internal_access, 0.0)
                delivery_increment += collection_assessment_config.get('floor_level', {}).get(delivery_floor_level, 0.0)
            
            collection_multiplier = 1.0 + collection_increment
            delivery_multiplier = 1.0 + delivery_increment
            
            # ========== CALCULATE INVENTORY COST ==========
            base_inventory = total_volume_m3 * company_rates['loading_cost_per_m3']
            inventory_cost = base_inventory * collection_multiplier * delivery_multiplier
            
            # ========== CALCULATE MILEAGE COST ==========
            distance = float(distance_miles or 0)
            if distance <= 100:
                mileage_cost = distance * total_volume_m3 * company_rates['cost_per_mile_under_100']
            else:
                cost_first_100 = 100 * total_volume_m3 * company_rates['cost_per_mile_under_100']
                remaining_miles = distance - 100
                cost_remaining = remaining_miles * total_volume_m3 * company_rates['cost_per_mile_over_100']
                mileage_cost = cost_first_100 + cost_remaining
            
            # ========== CALCULATE OPTIONAL EXTRAS ==========
            packing_cost = 0
            if include_packing and packing_volume_m3 > 0:
                # Use packing percentage from config
                packing_cost = inventory_cost * pricing_config.get('packing_percentage', 0.35)
            
            dismantling_cost = 0
            if include_dismantling and dismantling_volume_m3 > 0:
                dismantling_cost = dismantling_volume_m3 * company_rates['disassembly_per_m3']
            
            reassembly_cost = 0
            if include_reassembly and reassembly_volume_m3 > 0:
                reassembly_cost = reassembly_volume_m3 * company_rates['assembly_per_m3']
            
            # ========== CALCULATE SUBTOTAL ==========
            subtotal = inventory_cost + mileage_cost + packing_cost + dismantling_cost + reassembly_cost
            
            # ========== APPLY MOVE DATE MULTIPLIER - FROM CONFIG ==========
            notice_multiplier = notice_multipliers_config.get(notice_period, 1.0)
            day_multiplier = move_day_multipliers_config.get(move_day, 1.0)
            move_date_multiplier = notice_multiplier * day_multiplier
            
            final_total = subtotal * move_date_multiplier
            date_adjustment = final_total - subtotal
            
            # ========== ADD PRICING TO COMPANY ==========
            company['exact_pricing'] = {
                'total_volume_m3': round(total_volume_m3, 2),
                'distance_miles': distance,
                
                'volumes_breakdown': {
                    'total_volume': round(total_volume_m3, 2),
                    'packing_volume': round(packing_volume_m3, 2),
                    'dismantling_volume': round(dismantling_volume_m3, 2),
                    'reassembly_volume': round(reassembly_volume_m3, 2)
                },
                
                'collection_increment': round(collection_increment, 3),
                'collection_multiplier': round(collection_multiplier, 3),
                'delivery_increment': round(delivery_increment, 3),
                'delivery_multiplier': round(delivery_multiplier, 3),
                'combined_property_multiplier': round(collection_multiplier * delivery_multiplier, 3),
                
                'inventory_cost': round(inventory_cost, 2),
                'mileage_cost': round(mileage_cost, 2),
                
                'packing_cost': round(packing_cost, 2),
                'packing_formula': f"Inventory (£{round(inventory_cost, 2)}) × {int(pricing_config.get('packing_percentage', 0.35) * 100)}% = £{round(packing_cost, 2)}",
                
                'dismantling_cost': round(dismantling_cost, 2),
                'dismantling_formula': f"{round(dismantling_volume_m3, 2)}m³ × £{company_rates['disassembly_per_m3']}/m³ = £{round(dismantling_cost, 2)}",
                
                'reassembly_cost': round(reassembly_cost, 2),
                'reassembly_formula': f"{round(reassembly_volume_m3, 2)}m³ × £{company_rates['assembly_per_m3']}/m³ = £{round(reassembly_cost, 2)}",
                
                'subtotal_before_date': round(subtotal, 2),
                'move_date_multiplier': round(move_date_multiplier, 3),
                'date_adjustment': round(date_adjustment, 2),
                
                'final_total': round(final_total, 2),
                
                'breakdown': {
                    'inventory': round(inventory_cost, 2),
                    'mileage': round(mileage_cost, 2),
                    'packing': round(packing_cost, 2),
                    'dismantling': round(dismantling_cost, 2),
                    'reassembly': round(reassembly_cost, 2),
                    'date_adjustment': round(date_adjustment, 2)
                },
                
                'config_source': 'system_configuration',
                'formula_notes': {
                    'property_assessment': 'ADDITIVE (1.0 + increments)',
                    'packing': f"{int(pricing_config.get('packing_percentage', 0.35) * 100)}% of Inventory Cost (from config)",
                    'assembly_disassembly': 'Per m³ of items (from config)',
                    'all_constants': 'Loaded dynamically from System Configuration'
                }
            }
            
            company['pricing_rates'] = company_rates
            
            # Add subscription info - from config
            plan = company.get('subscription_plan', 'Free')
            viewed = int(company.get('requests_viewed_this_month', 0) or 0)
            plan_limits_config = get_plan_limits()
            limit = plan_limits_config.get(plan, 5)
            
            company['subscription_info'] = {
                'plan': plan,
                'views_used': viewed,
                'views_limit': limit if limit != -1 else 'Unlimited',
                'views_remaining': (limit - viewed) if limit != -1 else 'Unlimited'
            }
            
            available_companies.append(company)
        
        # Sort by final total
        available_companies.sort(key=lambda x: x['exact_pricing']['final_total'])
        
        result = {
            "success": True,
            "count": len(available_companies),
            "total_companies": len(companies),
            "filtered_out": len(companies) - len(available_companies),
            "data": available_companies,
            "search_parameters": {
                "pincode": pincode,
                "total_volume_m3": round(total_volume_m3, 2),
                "dismantling_volume_m3": round(dismantling_volume_m3, 2),
                "reassembly_volume_m3": round(reassembly_volume_m3, 2),
                "packing_volume_m3": round(packing_volume_m3, 2),
                "item_details": item_details,
                "missing_items": missing_items,
                "property_type": property_type,
                "property_size": property_size,
                "distance_miles": distance_miles,
                "pickup_address": pickup_address,
                "pickup_city": pickup_city,
                "delivery_address": delivery_address,
                "delivery_city": delivery_city,
                "additional_spaces": additional_spaces,
                "quantity": quantity,
                "optional_extras": {
                    "packing": include_packing,
                    "dismantling": include_dismantling,
                    "reassembly": include_reassembly
                },
                "move_date": {
                    "notice_period": notice_period,
                    "move_day": move_day,
                    "collection_time": collection_time
                }
            },
            "pricing_note": "All constants loaded dynamically from System Configuration via config_manager.py",
            "config_info": {
                "source": "System Configuration DocType",
                "editable_via": "Admin Dashboard",
                "constants_used": [
                    "additional_spaces",
                    "property_volumes",
                    "quantity_multipliers",
                    "collection_assessment",
                    "notice_period_multipliers",
                    "move_day_multipliers",
                    "pricing_config",
                    "plan_limits"
                ]
            },
            "warnings": []
        }
        
        # Add warnings if items were missing
        if missing_items:
            result["warnings"].append({
                "type": "missing_items",
                "message": f"{len(missing_items)} inventory items not found in database",
                "items": missing_items,
                "suggestion": "Calculation fell back to property-based volume estimation" if total_volume_m3 > 0 else "Please check item names"
            })
        
        # Send email if requested
        if send_email and user_email:
            try:
                email_sent = send_property_search_email(
                    user_email=user_email,
                    search_data=result.get('search_parameters', {}),
                    companies_data=available_companies
                )
                result['email_sent'] = email_sent
            except Exception as email_error:
                result['email_sent'] = False
                result['email_message'] = f"Email failed: {str(email_error)}"
        
        return result
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        safe_log("Search with Exact Cost Error", error_trace[:2000])
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