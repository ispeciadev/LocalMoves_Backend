
"""
CORRECTED Moving Cost Calculator API
Based on Client Spreadsheet Requirements


Key Changes from Spreadsheet Analysis:
1. Property Assessment is ADDITIVE (not multiplicative average)
2. Packing is 35% of INVENTORY COST (not per m3)
3. Assembly/Disassembly are PER M³ (as per spreadsheet: £50/m³ and £25/m³)
4. Total formula: (Inventory + Mileage + Optional Extras) × Move Date Multiplier
"""




import frappe
import json
from datetime import datetime
from localmoves.utils.config_manager import get_config




# ==================== PRICING CONSTANTS (NOW DYNAMIC) ====================
# These constants are now loaded from System Configuration doctype
# Use get_config() to load latest values




# Property Volumes (m³) - These are now loaded from config
# Keeping structure for reference but values loaded dynamically
PROPERTY_VOLUMES = {}


# Additional Spaces (m³) - These are now loaded from config
ADDITIONAL_SPACES = {}


# Quantity Multipliers - These are now loaded from config
QUANTITY_MULTIPLIERS = {}


# Vehicle Space Multipliers - These are now loaded from config
VEHICLE_SPACE_MULTIPLIERS = {}


# Assessment Multipliers - These are now loaded from config
COLLECTION_ASSESSMENT = {}
DELIVERY_ASSESSMENT = {}


# Notice Period Multipliers - These are now loaded from config
NOTICE_PERIOD_MULTIPLIERS = {}


# Move Day Multipliers - These are now loaded from config
MOVE_DAY_MULTIPLIERS = {}




# Collection Time
COLLECTION_TIME_MULTIPLIERS = {
    'flexible': 1.0,          # Anytime
    'morning': 1.0,           # 9am-5pm standard
    'afternoon': 1.0,         # 9am-5pm standard
}
DEFAULT_LOADING_COST_PER_M3 = 38.50
DEFAULT_COST_PER_MILE_UNDER_100 = 1.00
DEFAULT_COST_PER_MILE_OVER_100 = 0.50
DEFAULT_ASSEMBLY_PER_M3 = 50.00
DEFAULT_DISASSEMBLY_PER_M3 = 25.00
DEFAULT_PACKING_PERCENTAGE = 0.35







# ==================== CALCULATION FUNCTIONS ====================


def get_pricing_constants():
    """Get all pricing constants from config or defaults"""
    config = get_config()
    return {
        'loading_cost_per_m3': config.get('pricing', {}).get('loading_cost_per_m3', 35.00),
        'cost_per_mile_under_100': config.get('pricing', {}).get('cost_per_mile_under_100', 0.25),
        'cost_per_mile_over_100': config.get('pricing', {}).get('cost_per_mile_over_100', 0.15),
        'assembly_per_m3': config.get('pricing', {}).get('assembly_per_m3', 50.00),
        'disassembly_per_m3': config.get('pricing', {}).get('disassembly_per_m3', 25.00),
        'packing_percentage': config.get('pricing', {}).get('packing_percentage', 0.35),
    }




def get_volume_constants():
    """Get volume constants from config"""
    config = get_config()
    return {
        'property_volumes': config.get('property_volumes', {}),
        'additional_spaces': config.get('additional_spaces', {}),
        'quantity_multipliers': config.get('quantity_multipliers', {}),
        'vehicle_space_multipliers': config.get('vehicle_space_multipliers', {}),
    }




def get_multiplier_constants():
    """Get multiplier constants from config"""
    config = get_config()
    return {
        'collection_assessment': config.get('collection_assessment', {}),
        'notice_period_multipliers': config.get('notice_period_multipliers', {}),
        'move_day_multipliers': config.get('move_day_multipliers', {}),
    }






# def calculate_total_volume(pricing_data):
#     """
#     Calculate total volume based on property type
   
#     Returns: float (m³)
#     """
#     property_type = pricing_data.get('property_type')
#     total_volume = 0
   
#     # Load dynamic config
#     volume_config = get_volume_constants()
#     property_volumes = volume_config.get('property_volumes', {})
#     additional_spaces = volume_config.get('additional_spaces', {})
#     quantity_multipliers = volume_config.get('quantity_multipliers', {})
#     vehicle_space_multipliers = volume_config.get('vehicle_space_multipliers', {})
   
#     if property_type == 'a_few_items':
#         vehicle_type = pricing_data.get('vehicle_type')
#         space_usage = pricing_data.get('space_usage', 'whole_van')
       
#         base_volume = property_volumes.get('a_few_items', {}).get(vehicle_type, 0)
#         multiplier = vehicle_space_multipliers.get(space_usage, 1.0)
#         total_volume = base_volume * multiplier
       
#     elif property_type == 'house':
#         house_size = pricing_data.get('house_size')
#         add_spaces = pricing_data.get('additional_spaces', [])
#         quantity = pricing_data.get('quantity', 'everything')
       
#         base_volume = property_volumes.get('house', {}).get(house_size, 0)
       
#         # Add additional spaces
#         for space in add_spaces:
#             base_volume += additional_spaces.get(space, 0)
       
#         # Apply quantity multiplier
#         multiplier = quantity_multipliers.get(quantity, 1.0)
#         total_volume = base_volume * multiplier
       
#     elif property_type == 'flat':
#         flat_size = pricing_data.get('flat_size')
#         quantity = pricing_data.get('quantity', 'everything')
       
#         base_volume = property_volumes.get('flat', {}).get(flat_size, 0)
#         multiplier = quantity_multipliers.get(quantity, 1.0)
#         total_volume = base_volume * multiplier
       
#     elif property_type == 'office':
#         office_size = pricing_data.get('office_size')
#         quantity = pricing_data.get('quantity', 'everything')
       
#         base_volume = property_volumes.get('office', {}).get(office_size, 0)
#         multiplier = quantity_multipliers.get(quantity, 1.0)
#         total_volume = base_volume * multiplier
   
#     return round(total_volume, 2)


def calculate_total_volume(pricing_data):
    """
    Calculate total volume based on property type
    
    PRIORITY:
    1. If selected_items provided -> Calculate from database items
    2. Otherwise -> Use predefined property sizes
    
    Returns: float (m³)
    """
    property_type = pricing_data.get('property_type')
    total_volume = 0

    # Load dynamic config
    volume_config = get_volume_constants()
    property_volumes = volume_config.get('property_volumes', {})
    additional_spaces = volume_config.get('additional_spaces', {})
    quantity_multipliers = volume_config.get('quantity_multipliers', {})
    vehicle_space_multipliers = volume_config.get('vehicle_space_multipliers', {})

    # ===== NEW: CHECK FOR SELECTED_ITEMS FIRST =====
    selected_items = pricing_data.get('selected_items')
    
    if selected_items and isinstance(selected_items, dict) and len(selected_items) > 0:
        # Calculate volume from individual items in database
        frappe.logger().info(f"Calculating volume from {len(selected_items)} selected items")
        
        for item_name, quantity in selected_items.items():
            try:
                # Query database for item volume
                item_data = frappe.db.sql("""
                    SELECT average_volume 
                    FROM `tabMoving Inventory Item`
                    WHERE item_name = %s
                    LIMIT 1
                """, (item_name,), as_dict=True)
                
                if item_data:
                    item_volume = float(item_data[0]['average_volume'])
                    item_quantity = int(quantity)
                    item_total = item_volume * item_quantity
                    total_volume += item_total
                    
                    frappe.logger().info(f"Item: {item_name}, Volume: {item_volume} m³, Qty: {item_quantity}, Total: {item_total} m³")
                else:
                    frappe.logger().warning(f"Item not found in database: {item_name}")
                    
            except Exception as e:
                frappe.log_error(f"Error calculating volume for item {item_name}: {str(e)}", "Volume Calculation Error")
        
        # Add additional spaces if provided
        add_spaces = pricing_data.get('additional_spaces', [])
        if add_spaces:
            for space in add_spaces:
                space_volume = additional_spaces.get(space, 0)
                total_volume += space_volume
                frappe.logger().info(f"Added space: {space}, Volume: {space_volume} m³")
        
        frappe.logger().info(f"Total volume from selected items: {total_volume} m³")
        return round(total_volume, 2)
    
    # ===== FALLBACK: USE PREDEFINED PROPERTY SIZES =====
    
    if property_type == 'a_few_items':
        vehicle_type = pricing_data.get('vehicle_type')
        space_usage = pricing_data.get('space_usage', 'whole_van')

        base_volume = property_volumes.get('a_few_items', {}).get(vehicle_type, 0)
        multiplier = vehicle_space_multipliers.get(space_usage, 1.0)
        total_volume = base_volume * multiplier

    elif property_type == 'house':
        # Support both 'house_size' and 'property_size' field names
        house_size = pricing_data.get('house_size') or pricing_data.get('property_size')
        add_spaces = pricing_data.get('additional_spaces', [])
        quantity = pricing_data.get('quantity', 'everything')

        base_volume = property_volumes.get('house', {}).get(house_size, 0)

        # Add additional spaces
        for space in add_spaces:
            base_volume += additional_spaces.get(space, 0)

        # Apply quantity multiplier
        multiplier = quantity_multipliers.get(quantity, 1.0)
        total_volume = base_volume * multiplier

    elif property_type == 'flat':
        # Support both 'flat_size' and 'property_size'
        flat_size = pricing_data.get('flat_size') or pricing_data.get('property_size')
        quantity = pricing_data.get('quantity', 'everything')

        base_volume = property_volumes.get('flat', {}).get(flat_size, 0)
        multiplier = quantity_multipliers.get(quantity, 1.0)
        total_volume = base_volume * multiplier

    elif property_type == 'office':
        # Support both 'office_size' and 'property_size'
        office_size = pricing_data.get('office_size') or pricing_data.get('property_size')
        quantity = pricing_data.get('quantity', 'everything')

        base_volume = property_volumes.get('office', {}).get(office_size, 0)
        multiplier = quantity_multipliers.get(quantity, 1.0)
        total_volume = base_volume * multiplier

    return round(total_volume, 2)





def calculate_property_assessment_increment(assessment_data, property_type):
    """
    Calculate property assessment INCREMENT (ADDITIVE, not multiplicative)
    Based on spreadsheet: Start at 1.0, ADD increments
   
    Returns: float (total increment to add to 1.0)
    """
    total_increment = 0.0
   
    # Load dynamic config
    multiplier_config = get_multiplier_constants()
    collection_assessment = multiplier_config.get('collection_assessment', {})
   
    # Parking (no increment in spreadsheet for either option)
    parking = assessment_data.get('parking', 'driveway')
    total_increment += collection_assessment.get('parking', {}).get(parking, 0.0)
   
    # Parking Distance
    parking_distance = assessment_data.get('parking_distance', 'less_than_10m')
    total_increment += collection_assessment.get('parking_distance', {}).get(parking_distance, 0.0)
   
    # Property Type Access (House vs Flat/Office)
    if property_type in ['house']:
        house_type = assessment_data.get('house_type', 'house_ground_and_1st')
        total_increment += collection_assessment.get('house_type', {}).get(house_type, 0.0)
   
    elif property_type in ['flat', 'office', 'a_few_items']:
        # Internal Access (stairs vs lift)
        internal_access = assessment_data.get('internal_access', 'stairs_only')
        total_increment += collection_assessment.get('internal_access', {}).get(internal_access, 0.0)
       
        # Floor Level
        floor_level = assessment_data.get('floor_level', 'ground_floor')
        total_increment += collection_assessment.get('floor_level', {}).get(floor_level, 0.0)
   
    return round(total_increment, 3)








def calculate_inventory_cost(total_volume, loading_cost_per_m3, collection_increment, delivery_increment):
    """
    Calculate inventory cost with property assessment
   
    Formula from spreadsheet:
    Base Cost = Total Volume × Loading Cost per m³
    Collection Multiplier = 1.0 + collection_increment
    Delivery Multiplier = 1.0 + delivery_increment
   
    Final = Base Cost × Collection Multiplier × Delivery Multiplier
    """
    base_cost = total_volume * loading_cost_per_m3
   
    collection_multiplier = 1.0 + collection_increment
    delivery_multiplier = 1.0 + delivery_increment
   
    # Apply both multipliers
    inventory_cost = base_cost * collection_multiplier * delivery_multiplier
   
    return round(inventory_cost, 2), collection_multiplier, delivery_multiplier








def calculate_mileage_cost(distance_miles, total_volume, cost_per_mile_under_100, cost_per_mile_over_100):
    """
    Calculate mileage cost based on distance tiers
   
    Formula from spreadsheet:
    - Under 100 miles: Distance × Total m³ × £0.25/mile
    - Over 100 miles: Different rate for miles over 100
    """
    distance = float(distance_miles or 0)
   
    if distance <= 100:
        mileage_cost = distance * total_volume * cost_per_mile_under_100
    else:
        # First 100 miles
        cost_first_100 = 100 * total_volume * cost_per_mile_under_100
        # Remaining miles
        remaining_miles = distance - 100
        cost_remaining = remaining_miles * total_volume * cost_per_mile_over_100
        mileage_cost = cost_first_100 + cost_remaining
   
    return round(mileage_cost, 2)








def calculate_optional_extras(pricing_data, inventory_cost, total_volume, company_rates):
    """
    Calculate optional extras based on spreadsheet formula
   
    AS PER SPREADSHEET:
    - Packing = Inventory Cost × 35%
    - Dismantling = Volume × £25 per m³
    - Reassembly = Volume × £50 per m³
    """
    extras = {}
    total = 0
   
    # Load pricing config
    pricing_config = get_pricing_constants()
    packing_percentage = pricing_config.get('packing_percentage', 0.35)
    disassembly_per_m3 = pricing_config.get('disassembly_per_m3', 25.00)
    assembly_per_m3 = pricing_config.get('assembly_per_m3', 50.00)
   
    # Packing = 35% of Inventory Cost (from spreadsheet)
    if pricing_data.get('include_packing', False):
        cost = inventory_cost * packing_percentage
        extras['packing'] = round(cost, 2)
        total += cost
   
    # Dismantling (per m³ as per spreadsheet: £25/m³)
    if pricing_data.get('include_dismantling', False):
        # Use total_volume unless specific volume provided
        dismantle_volume = float(pricing_data.get('dismantle_volume_m3', total_volume))
        cost = dismantle_volume * company_rates.get('disassembly_cost_per_m3', disassembly_per_m3)
        extras['dismantling'] = round(cost, 2)
        total += cost
   
    # Reassembly (per m³ as per spreadsheet: £50/m³)
    if pricing_data.get('include_reassembly', False):
        # Use total_volume unless specific volume provided
        assembly_volume = float(pricing_data.get('assembly_volume_m3', total_volume))
        cost = assembly_volume * company_rates.get('assembly_cost_per_m3', assembly_per_m3)
        extras['reassembly'] = round(cost, 2)
        total += cost
   
    extras['total'] = round(total, 2)
    return extras








def calculate_move_date_multiplier(move_date_data):
    """
    Calculate move date multiplier
    Based on client calendar
   
    Returns: float (multiplier)
    """
    multiplier = 1.0
   
    # Load dynamic config
    multiplier_config = get_multiplier_constants()
    notice_period_multipliers = multiplier_config.get('notice_period_multipliers', {})
    move_day_multipliers = multiplier_config.get('move_day_multipliers', {})
   
    # Notice Period
    notice = move_date_data.get('notice_period', 'within_month')
    multiplier *= notice_period_multipliers.get(notice, 1.0)
   
    # Move Day (Fri/Sat vs Sun-Thu)
    move_day = move_date_data.get('move_day', 'sun_to_thurs')
    multiplier *= move_day_multipliers.get(move_day, 1.0)
   
    # Collection Time (currently all same in client sheet)
    collection_time = move_date_data.get('collection_time', 'flexible')
    multiplier *= COLLECTION_TIME_MULTIPLIERS.get(collection_time, 1.0)
   
    return round(multiplier, 3)








def calculate_comprehensive_price(request_data, company_rates):
    """
    MAIN PRICING CALCULATION
    Based on client spreadsheet formula:
   
    FORMULA AS PER SPREADSHEET:
    1. Inventory Cost = Total m³ × Loading Cost × (1 + Collection Increment) × (1 + Delivery Increment)
    2. Mileage Cost = Distance × Total m³ × Cost per Mile
    3. Optional Extras:
       - Packing = Inventory Cost × 35%
       - Dismantling = Volume × £25 per m³
       - Reassembly = Volume × £50 per m³
    4. Subtotal = Inventory + Mileage + Extras
    5. Final Total = Subtotal × Move Date Multiplier
    """
   
    pricing_data = request_data.get('pricing_data', {})
    property_type = pricing_data.get('property_type')
   
    # Step 1: Calculate Total Volume
    total_volume = calculate_total_volume(pricing_data)
   
    # Step 2: Calculate Property Assessment Increments (ADDITIVE)
    collection_data = request_data.get('collection_assessment', {})
    delivery_data = request_data.get('delivery_assessment', {})
   
    collection_increment = calculate_property_assessment_increment(collection_data, property_type)
    delivery_increment = calculate_property_assessment_increment(delivery_data, property_type)
   
    # Step 3: Calculate Inventory Cost
    pricing_config = get_pricing_constants()
    loading_cost_per_m3 = company_rates.get('loading_cost_per_m3', pricing_config.get('loading_cost_per_m3', 35.00))
    inventory_cost, collection_multiplier, delivery_multiplier = calculate_inventory_cost(
        total_volume,
        loading_cost_per_m3,
        collection_increment,
        delivery_increment
    )
   
    # Step 4: Calculate Mileage Cost
    distance_miles = float(request_data.get('distance_miles', 0))
    mileage_cost = calculate_mileage_cost(
        distance_miles,
        total_volume,
        company_rates.get('cost_per_mile_under_100', pricing_config.get('cost_per_mile_under_100', 0.25)),
        company_rates.get('cost_per_mile_over_100', pricing_config.get('cost_per_mile_over_100', 0.15))
    )
   
    # Step 5: Calculate Optional Extras (using inventory cost for packing)
    optional_extras = calculate_optional_extras(pricing_data, inventory_cost, total_volume, company_rates)
   
    # Step 6: Calculate Subtotal (before move date)
    subtotal = inventory_cost + mileage_cost + optional_extras['total']
   
    # Step 7: Apply Move Date Multiplier
    move_date_data = request_data.get('move_date_data', {})
    move_date_multiplier = calculate_move_date_multiplier(move_date_data)
   
    # Step 8: Calculate Final Total
    final_total = subtotal * move_date_multiplier
   
    # Return complete breakdown
    return {
        'total_volume_m3': total_volume,
        'distance_miles': distance_miles,
       
        # Property Assessment (ADDITIVE)
        'collection_increment': collection_increment,
        'delivery_increment': delivery_increment,
        'collection_multiplier': collection_multiplier,
        'delivery_multiplier': delivery_multiplier,
        'combined_property_multiplier': round(collection_multiplier * delivery_multiplier, 3),
       
        # Costs
        'inventory_cost': round(inventory_cost, 2),
        'mileage_cost': round(mileage_cost, 2),
        'optional_extras': optional_extras,
       
        # Subtotal and Final
        'subtotal_before_date': round(subtotal, 2),
        'move_date_multiplier': move_date_multiplier,
        'date_adjustment': round(final_total - subtotal, 2),
        'final_total': round(final_total, 2),
       
        # Breakdown for display
        'breakdown': {
            'inventory': round(inventory_cost, 2),
            'mileage': round(mileage_cost, 2),
            'packing': optional_extras.get('packing', 0),
            'dismantling': optional_extras.get('dismantling', 0),
            'reassembly': optional_extras.get('reassembly', 0),
            'move_date_adjustment': round(final_total - subtotal, 2),
        }
    }








# ==================== API ENDPOINTS ====================




@frappe.whitelist(allow_guest=True)
def calculate_move_price():
    """
    Calculate move price with corrected formula
   
    Request Body Example:
    {
        "company_name": "ABC Logistics",
        "distance_miles": 150,
        "pricing_data": {
            "property_type": "house",
            "house_size": "3_bed",
            "additional_spaces": ["loft", "single_garage"],
            "quantity": "everything",
            "include_packing": true,
            "include_dismantling": true,
            "dismantle_volume_m3": 52,
            "include_reassembly": true,
            "assembly_volume_m3": 52
        },
        "collection_assessment": {
            "parking": "roadside",
            "parking_distance": "10_to_20m",
            "house_type": "house_ground_and_1st"
        },
        "delivery_assessment": {
            "parking": "driveway",
            "parking_distance": "less_than_10m",
            "internal_access": "lift_access",
            "floor_level": "2nd_floor"
        },
        "move_date_data": {
            "notice_period": "within_3_days",
            "move_day": "friday_saturday",
            "collection_time": "flexible"
        }
    }
    """
    try:
        data = frappe.request.get_json() or {}
       
        # Load pricing config for defaults
        pricing_config = get_pricing_constants()
       
        # Get company rates or use defaults
        company_name = data.get('company_name')
       
        if company_name and frappe.db.exists("Logistics Company", company_name):
            company = frappe.get_doc("Logistics Company", company_name)
            company_rates = {
                'loading_cost_per_m3': float(company.get('loading_cost_per_m3') or pricing_config.get('loading_cost_per_m3', 35.00)),
                'disassembly_cost_per_m3': float(company.get('disassembly_cost_per_item') or pricing_config.get('disassembly_per_m3', 25.00)),
                'assembly_cost_per_m3': float(company.get('assembly_cost_per_item') or pricing_config.get('assembly_per_m3', 50.00)),
                'cost_per_mile_under_100': float(company.get('cost_per_mile_under_25') or pricing_config.get('cost_per_mile_under_100', 0.25)),
                'cost_per_mile_over_100': float(company.get('cost_per_mile_over_25') or pricing_config.get('cost_per_mile_over_100', 0.15)),
            }
        else:
            # Use default rates from config
            company_rates = {
                'loading_cost_per_m3': pricing_config.get('loading_cost_per_m3', 35.00),
                'disassembly_cost_per_m3': pricing_config.get('disassembly_per_m3', 25.00),
                'assembly_cost_per_m3': pricing_config.get('assembly_per_m3', 50.00),
                'cost_per_mile_under_100': pricing_config.get('cost_per_mile_under_100', 0.25),
                'cost_per_mile_over_100': pricing_config.get('cost_per_mile_over_100', 0.15),
            }
       
        # Calculate price
        price_breakdown = calculate_comprehensive_price(data, company_rates)
       
        return {
            "success": True,
            "company_name": company_name or "Default Rates",
            "company_rates": company_rates,
            "calculation": price_breakdown,
            "currency": "GBP",
            "formula_explanation": {
                "step_1": f"Total Volume: {price_breakdown['total_volume_m3']} m³",
                "step_2": f"Base Inventory: {price_breakdown['total_volume_m3']} × £{company_rates['loading_cost_per_m3']} = £{round(price_breakdown['total_volume_m3'] * company_rates['loading_cost_per_m3'], 2)}",
                "step_3": f"Collection Multiplier: 1.0 + {price_breakdown['collection_increment']} = {price_breakdown['collection_multiplier']}",
                "step_4": f"Delivery Multiplier: 1.0 + {price_breakdown['delivery_increment']} = {price_breakdown['delivery_multiplier']}",
                "step_5": f"Inventory Cost: Base × {price_breakdown['collection_multiplier']} × {price_breakdown['delivery_multiplier']} = £{price_breakdown['inventory_cost']}",
                "step_6": f"Mileage Cost: {price_breakdown['distance_miles']} miles × {price_breakdown['total_volume_m3']} m³ × rate = £{price_breakdown['mileage_cost']}",
                "step_7": f"Packing (35% of Inventory): £{price_breakdown['inventory_cost']} × 0.35 = £{price_breakdown['optional_extras'].get('packing', 0)}",
                "step_8": f"Subtotal: £{price_breakdown['subtotal_before_date']}",
                "step_9": f"Move Date Multiplier: × {price_breakdown['move_date_multiplier']}",
                "step_10": f"Final Total: £{price_breakdown['final_total']}"
            }
        }
       
    except Exception as e:
        frappe.log_error(f"Calculate Move Price Error: {str(e)}", "Move Price Calculation")
        return {
            "success": False,
            "message": f"Calculation failed: {str(e)}"
        }








@frappe.whitelist(allow_guest=True)
def get_pricing_constants():
    """
    Get all pricing constants for frontend
    """
    return {
        "success": True,
        "constants": {
            "property_volumes": PROPERTY_VOLUMES,
            "additional_spaces": ADDITIONAL_SPACES,
            "quantity_multipliers": QUANTITY_MULTIPLIERS,
            "vehicle_space_multipliers": VEHICLE_SPACE_MULTIPLIERS,
            "collection_assessment": COLLECTION_ASSESSMENT,
            "delivery_assessment": DELIVERY_ASSESSMENT,
            "notice_period_multipliers": NOTICE_PERIOD_MULTIPLIERS,
            "move_day_multipliers": MOVE_DAY_MULTIPLIERS,
            "collection_time_multipliers": COLLECTION_TIME_MULTIPLIERS,
        },
        "default_rates": {
            "loading_cost_per_m3": DEFAULT_LOADING_COST_PER_M3,
            "cost_per_mile_under_100": DEFAULT_COST_PER_MILE_UNDER_100,
            "cost_per_mile_over_100": DEFAULT_COST_PER_MILE_OVER_100,
            "assembly_per_m3": DEFAULT_ASSEMBLY_PER_M3,
            "disassembly_per_m3": DEFAULT_DISASSEMBLY_PER_M3,
            "packing_percentage": DEFAULT_PACKING_PERCENTAGE,
        }
    }



