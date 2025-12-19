"""
Configuration Manager - Dynamically manage constants from System Configuration
Allows admins to update pricing, volumes, and multipliers without code changes
"""


import frappe
import json




# ==================== DEFAULT CONSTANTS ====================


DEFAULT_CONFIG = {
    # Pricing Constants
    'pricing': {
        'loading_cost_per_m3': 35.00,
        'cost_per_mile_under_100': 0.25,
        'cost_per_mile_over_100': 0.15,
        'assembly_per_m3': 50.00,
        'disassembly_per_m3': 25.00,
        'packing_percentage': 0.35,
    },
   
    # Vehicle Capacities (m³)
    'vehicle_capacities': {
        'swb_van': 5,
        'mwb_van': 8,
        'lwb_van': 11,
    },
   
    # Property Volumes (m³)
    'property_volumes': {
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
    },
   
    # Additional Spaces (m³)
    'additional_spaces': {
        'shed': 4,
        'loft': 6,
        'basement': 10,
        'single_garage': 8,
        'double_garage': 15,
    },
   
    # Quantity Multipliers
    'quantity_multipliers': {
        'some_things': 0.25,
        'half_contents': 0.5,
        'three_quarter': 0.75,
        'everything': 1.0,
    },
   
    # Vehicle Space Multipliers
    'vehicle_space_multipliers': {
        'quarter_van': 0.25,
        'half_van': 0.5,
        'three_quarter_van': 0.75,
        'whole_van': 1.0,
    },
   
    # Subscription Plan Limits
    'plan_limits': {
        'Free': 5,
        'Basic': 20,
        'Standard': 50,
        'Premium': -1,
    },
   
    # Collection Assessment Multipliers
    'collection_assessment': {
        'parking': {
            'driveway': 1.0,
            'roadside': 0.0,
        },
        'parking_distance': {
            'less_than_10m': 1.05,
            '10_to_20m': 1.1,
            'over_20m': 1.15,
        },
        'house_type': {
            'house_ground_and_1st': 1.05,
            'bungalow_ground': 1.0,
            'townhouse_ground_1st_2nd': 1.1,
        },
        'internal_access': {
            'stairs_only': 0.00,
            'lift_access': 1.025,
        },
        'floor_level': {
            'ground_floor': 1.0,
            '1st_floor': 1.10,
            '2nd_floor': 1.15,
            '3rd_floor_plus': 1.20,
        }
    },
   
    # Notice Period Multipliers
    'notice_period_multipliers': {
        'flexible': 0.8,
        'within_3_days': 1.3,
        'within_week': 1.2,
        'within_2_weeks': 1.1,
        'within_month': 1.0,
        'over_month': 0.9,
    },
   
    # Move Day Multipliers
    'move_day_multipliers': {
        'sun_to_thurs': 1.0,
        'friday_saturday': 1.15,
    },
}




def get_config(key=None):
    """
    Get configuration from database or use defaults
   
    Args:
        key (str): Optional key to get specific config (e.g., 'pricing', 'vehicle_capacities')
                  If None, returns entire config
   
    Returns:
        dict: Configuration data
    """
    try:
        config_doc = frappe.db.get_value(
            'System Configuration',
            filters={'config_name': 'localmoves_config', 'is_active': 1},
            fieldname=['config_data'],
            as_dict=True
        )
       
        if config_doc and config_doc.get('config_data'):
            try:
                config_data = json.loads(config_doc['config_data'])
                if key:
                    return config_data.get(key, DEFAULT_CONFIG.get(key, {}))
                return config_data
            except (json.JSONDecodeError, TypeError):
                pass
    except:
        pass
   
    # Return defaults if no config found in database
    if key:
        return DEFAULT_CONFIG.get(key, {})
    return DEFAULT_CONFIG




def update_config(config_data):
    """
    Update configuration in database
   
    Args:
        config_data (dict): Configuration data to save
   
    Returns:
        tuple: (bool, str) - Success status and message
    """
    try:
        # First check if System Configuration doctype exists
        if not frappe.db.exists('DocType', 'System Configuration'):
            error_msg = "System Configuration doctype not found. Please run 'bench migrate' first."
            frappe.log_error(title="Config Update Error", message=error_msg)
            return False, error_msg
       
        config_doc = frappe.db.get_value(
            'System Configuration',
            filters={'config_name': 'localmoves_config'},
            as_dict=True
        )
       
        if not config_doc:
            # Create new config doc if it doesn't exist
            doc = frappe.new_doc('System Configuration')
            doc.config_name = 'localmoves_config'
            doc.config_data = json.dumps(config_data, indent=2)
            doc.is_active = 1
            doc.save(ignore_permissions=True)
            frappe.cache().delete_value('localmoves_config')
            return True, "Configuration created successfully"
        else:
            # Update existing config doc
            doc = frappe.get_doc('System Configuration', config_doc['name'])
            doc.config_data = json.dumps(config_data, indent=2)
            doc.save(ignore_permissions=True)
            frappe.cache().delete_value('localmoves_config')
            return True, "Configuration updated successfully"
    except Exception as e:
        error_msg = f"Config Update Error: {str(e)}"
        frappe.log_error(title="Config Update Error", message=str(e))
        return False, error_msg




def get_pricing_config():
    """Get pricing configuration"""
    return get_config('pricing')




def get_vehicle_capacities():
    """Get vehicle capacities"""
    return get_config('vehicle_capacities')




def get_property_volumes():
    """Get property volumes"""
    return get_config('property_volumes')




def get_additional_spaces():
    """Get additional spaces"""
    return get_config('additional_spaces')




def get_quantity_multipliers():
    """Get quantity multipliers"""
    return get_config('quantity_multipliers')




def get_vehicle_space_multipliers():
    """Get vehicle space multipliers"""
    return get_config('vehicle_space_multipliers')




def get_plan_limits():
    """Get subscription plan limits"""
    return get_config('plan_limits')




def get_collection_assessment():
    """Get collection assessment multipliers"""
    return get_config('collection_assessment')




def get_notice_period_multipliers():
    """Get notice period multipliers"""
    return get_config('notice_period_multipliers')




def get_move_day_multipliers():
    """Get move day multipliers"""
    return get_config('move_day_multipliers')


