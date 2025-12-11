"""
IMPROVED Moving Cost Calculator API
Based on Client Spreadsheet Requirements

Key Changes:
1. Simplified pricing formula
2. Clear property assessment logic
3. Move date calendar-based pricing
4. Distance-based mileage calculation
"""

import frappe
import json
from datetime import datetime

# ==================== PRICING CONSTANTS ====================

# Base Rates (from client spreadsheet)
DEFAULT_LOADING_COST_PER_M3 = 35.00
DEFAULT_COST_PER_MILE_UNDER_100 = 0.25
DEFAULT_COST_PER_MILE_OVER_100 = 0.15
DEFAULT_ASSEMBLY_PER_M3 = 50.00
DEFAULT_DISASSEMBLY_PER_M3 = 25.00  # 50% of assembly
DEFAULT_PACKING_PER_M3 = 12.25  # 35% of loading cost

# Property Volumes (m³)
PROPERTY_VOLUMES = {
    'a_few_items': {
        'swb_van': 5,
        'mwb_van': 8,
        'lwb_van': 11,
        'xlwb_van': 13,
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

# Additional Spaces (m³)
ADDITIONAL_SPACES = {
    'shed': 8,
    'loft': 12,
    'basement': 20,
    'single_garage': 16,
    'double_garage': 30,
}

# Quantity Multipliers
QUANTITY_MULTIPLIERS = {
    'some_things': 0.25,
    'half_contents': 0.5,
    'three_quarter': 0.75,
    'everything': 1.0,
}

# Vehicle Space Multipliers
VEHICLE_SPACE_MULTIPLIERS = {
    'quarter_van': 0.25,
    'half_van': 0.5,
    'three_quarter_van': 0.75,
    'whole_van': 1.0,
}

# ==================== PROPERTY ASSESSMENT MULTIPLIERS ====================
# Based on client spreadsheet

# COLLECTION Assessment
COLLECTION_MULTIPLIERS = {
    'parking': {
        'driveway': 1.0,
        'roadside': 1.0,
    },
    'parking_distance': {
        'less_than_10m': 1.0,
        '10_to_20m': 1.05,
        'over_20m': 1.1,
    },
    'property_type_access': {
        # For Houses/Bungalows
        'house_ground_and_1st': 1.0,
        'bungalow_ground': 1.0,
        'townhouse_ground_1st_2nd': 1.025,
        # For Flats/Offices
        'stairs_only': 1.05,
        'lift_access': 1.1,
    },
    'floor_level': {
        'ground_floor': 1.0,
        '1st_floor': 1.1,
        '2nd_floor': 1.15,
        '3rd_floor_plus': 1.2,
    }
}

# DELIVERY Assessment (same structure)
DELIVERY_MULTIPLIERS = COLLECTION_MULTIPLIERS

# ==================== MOVE DATE MULTIPLIERS ====================
# Based on client calendar spreadsheet

# Notice Period
NOTICE_PERIOD_MULTIPLIERS = {
    'flexible': 0.8,          # Save 20%
    'within_3_days': 1.3,     # +30%
    'within_week': 1.2,       # +20%
    'within_2_weeks': 1.1,    # +10%
    'within_month': 1.0,      # Standard
    'over_month': 0.9,        # Save 10%
}

# Day of Week
MOVE_DAY_MULTIPLIERS = {
    'sun_to_thurs': 1.0,      # Standard (Mon-Thu, Sun)
    'friday_saturday': 1.15,  # +15% for Fri/Sat
}

# Collection Time
COLLECTION_TIME_MULTIPLIERS = {
    'flexible': 1.0,          # Anytime
    'morning': 1.0,           # 9am-5pm standard
    'afternoon': 1.0,         # 9am-5pm standard
}


# ==================== CALCULATION FUNCTIONS ====================

def calculate_total_volume(pricing_data):
    """
    Calculate total volume based on property type
    
    Returns: float (m³)
    """
    property_type = pricing_data.get('property_type')
    total_volume = 0
    
    if property_type == 'a_few_items':
        vehicle_type = pricing_data.get('vehicle_type')
        space_usage = pricing_data.get('space_usage', 'whole_van')
        
        base_volume = PROPERTY_VOLUMES['a_few_items'].get(vehicle_type, 0)
        multiplier = VEHICLE_SPACE_MULTIPLIERS.get(space_usage, 1.0)
        total_volume = base_volume * multiplier
        
    elif property_type == 'house':
        house_size = pricing_data.get('house_size')
        additional_spaces = pricing_data.get('additional_spaces', [])
        quantity = pricing_data.get('quantity', 'everything')
        
        base_volume = PROPERTY_VOLUMES['house'].get(house_size, 0)
        
        # Add additional spaces
        for space in additional_spaces:
            base_volume += ADDITIONAL_SPACES.get(space, 0)
        
        # Apply quantity multiplier
        multiplier = QUANTITY_MULTIPLIERS.get(quantity, 1.0)
        total_volume = base_volume * multiplier
        
    elif property_type == 'flat':
        flat_size = pricing_data.get('flat_size')
        quantity = pricing_data.get('quantity', 'everything')
        
        base_volume = PROPERTY_VOLUMES['flat'].get(flat_size, 0)
        multiplier = QUANTITY_MULTIPLIERS.get(quantity, 1.0)
        total_volume = base_volume * multiplier
        
    elif property_type == 'office':
        office_size = pricing_data.get('office_size')
        quantity = pricing_data.get('quantity', 'everything')
        
        base_volume = PROPERTY_VOLUMES['office'].get(office_size, 0)
        multiplier = QUANTITY_MULTIPLIERS.get(quantity, 1.0)
        total_volume = base_volume * multiplier
    
    return round(total_volume, 2)


def calculate_property_assessment_multiplier(assessment_data, property_type):
    """
    Calculate property assessment multiplier
    Based on client spreadsheet logic
    
    Returns: float (multiplier)
    """
    multiplier = 1.0
    
    # Parking
    parking = assessment_data.get('parking', 'driveway')
    multiplier *= COLLECTION_MULTIPLIERS['parking'].get(parking, 1.0)
    
    # Parking Distance
    parking_distance = assessment_data.get('parking_distance', 'less_than_10m')
    multiplier *= COLLECTION_MULTIPLIERS['parking_distance'].get(parking_distance, 1.0)
    
    # Property Type Access (House vs Flat/Office)
    if property_type in ['house']:
        access_type = assessment_data.get('house_type', 'house_ground_and_1st')
        multiplier *= COLLECTION_MULTIPLIERS['property_type_access'].get(access_type, 1.0)
    
    elif property_type in ['flat', 'office', 'a_few_items']:
        # Flat/Office use stairs vs lift
        internal_access = assessment_data.get('internal_access', 'stairs_only')
        multiplier *= COLLECTION_MULTIPLIERS['property_type_access'].get(internal_access, 1.0)
        
        # Floor Level
        floor_level = assessment_data.get('floor_level', 'ground_floor')
        multiplier *= COLLECTION_MULTIPLIERS['floor_level'].get(floor_level, 1.0)
    
    return round(multiplier, 3)


def calculate_loading_cost(total_volume, loading_cost_per_m3, property_multiplier):
    """
    Calculate loading cost with property assessment
    
    Formula: Total Volume × Loading Cost per m³ × Property Assessment Multiplier
    """
    base_cost = total_volume * loading_cost_per_m3
    adjusted_cost = base_cost * property_multiplier
    return round(adjusted_cost, 2)


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


def calculate_optional_extras(pricing_data, total_volume, company_rates):
    """
    Calculate optional extras: packing, dismantling, reassembly
    """
    extras = {}
    total = 0
    
    # Packing (based on volume)
    if pricing_data.get('include_packing', False):
        packing_volume = float(pricing_data.get('packing_volume_m3', total_volume))
        cost = packing_volume * company_rates.get('packing_cost_per_m3', DEFAULT_PACKING_PER_M3)
        extras['packing'] = round(cost, 2)
        total += cost
    
    # Dismantling (per m³ or per item)
    if pricing_data.get('include_dismantling', False):
        dismantle_volume = float(pricing_data.get('dismantle_volume_m3', total_volume))
        cost = dismantle_volume * company_rates.get('disassembly_cost_per_m3', DEFAULT_DISASSEMBLY_PER_M3)
        extras['dismantling'] = round(cost, 2)
        total += cost
    
    # Reassembly (per m³ or per item)
    if pricing_data.get('include_reassembly', False):
        assembly_volume = float(pricing_data.get('assembly_volume_m3', total_volume))
        cost = assembly_volume * company_rates.get('assembly_cost_per_m3', DEFAULT_ASSEMBLY_PER_M3)
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
    
    # Notice Period
    notice = move_date_data.get('notice_period', 'within_month')
    multiplier *= NOTICE_PERIOD_MULTIPLIERS.get(notice, 1.0)
    
    # Move Day (Fri/Sat vs Sun-Thu)
    move_day = move_date_data.get('move_day', 'sun_to_thurs')
    multiplier *= MOVE_DAY_MULTIPLIERS.get(move_day, 1.0)
    
    # Collection Time (currently all same in client sheet)
    collection_time = move_date_data.get('collection_time', 'flexible')
    multiplier *= COLLECTION_TIME_MULTIPLIERS.get(collection_time, 1.0)
    
    return round(multiplier, 3)


def calculate_comprehensive_price(request_data, company_rates):
    """
    MAIN PRICING CALCULATION
    Based on client spreadsheet formula:
    
    1. Inventory Cost = Total m³ × Loading Cost × Property Assessment
    2. Mileage Cost = Distance × Total m³ × Cost per Mile
    3. Optional Extras = Packing + Dismantling + Reassembly
    4. Subtotal = Inventory + Mileage + Extras
    5. Final Total = Subtotal × Move Date Multiplier
    """
    
    pricing_data = request_data.get('pricing_data', {})
    property_type = pricing_data.get('property_type')
    
    # Step 1: Calculate Total Volume
    total_volume = calculate_total_volume(pricing_data)
    
    # Step 2: Calculate Property Assessment Multipliers
    collection_data = request_data.get('collection_assessment', {})
    delivery_data = request_data.get('delivery_assessment', {})
    
    collection_multiplier = calculate_property_assessment_multiplier(collection_data, property_type)
    delivery_multiplier = calculate_property_assessment_multiplier(delivery_data, property_type)
    
    # Average of collection and delivery
    combined_property_multiplier = (collection_multiplier + delivery_multiplier) / 2
    
    # Step 3: Calculate Inventory/Loading Cost
    loading_cost_per_m3 = company_rates.get('loading_cost_per_m3', DEFAULT_LOADING_COST_PER_M3)
    inventory_cost = calculate_loading_cost(
        total_volume,
        loading_cost_per_m3,
        combined_property_multiplier
    )
    
    # Step 4: Calculate Mileage Cost
    distance_miles = float(request_data.get('distance_miles', 0))
    mileage_cost = calculate_mileage_cost(
        distance_miles,
        total_volume,
        company_rates.get('cost_per_mile_under_100', DEFAULT_COST_PER_MILE_UNDER_100),
        company_rates.get('cost_per_mile_over_100', DEFAULT_COST_PER_MILE_OVER_100)
    )
    
    # Step 5: Calculate Optional Extras
    optional_extras = calculate_optional_extras(pricing_data, total_volume, company_rates)
    
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
        
        # Property Assessment
        'collection_multiplier': collection_multiplier,
        'delivery_multiplier': delivery_multiplier,
        'combined_property_multiplier': combined_property_multiplier,
        
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
    Calculate move price with clear formula
    
    Request Body Example:
    {
        "company_name": "ABC Logistics",  // Optional, uses defaults if not provided
        "distance_miles": 150,
        "pricing_data": {
            "property_type": "house",
            "house_size": "3_bed",
            "additional_spaces": ["loft", "single_garage"],
            "quantity": "everything",
            "include_packing": true,
            "packing_volume_m3": 52,
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
        
        # Get company rates or use defaults
        company_name = data.get('company_name')
        
        if company_name and frappe.db.exists("Logistics Company", company_name):
            company = frappe.get_doc("Logistics Company", company_name)
            company_rates = {
                'loading_cost_per_m3': float(company.get('loading_cost_per_m3') or DEFAULT_LOADING_COST_PER_M3),
                'packing_cost_per_m3': float(company.get('packing_cost_per_box') or DEFAULT_PACKING_PER_M3),
                'disassembly_cost_per_m3': float(company.get('disassembly_cost_per_item') or DEFAULT_DISASSEMBLY_PER_M3),
                'assembly_cost_per_m3': float(company.get('assembly_cost_per_item') or DEFAULT_ASSEMBLY_PER_M3),
                'cost_per_mile_under_100': float(company.get('cost_per_mile_under_25') or DEFAULT_COST_PER_MILE_UNDER_100),
                'cost_per_mile_over_100': float(company.get('cost_per_mile_over_25') or DEFAULT_COST_PER_MILE_OVER_100),
            }
        else:
            # Use default rates
            company_rates = {
                'loading_cost_per_m3': DEFAULT_LOADING_COST_PER_M3,
                'packing_cost_per_m3': DEFAULT_PACKING_PER_M3,
                'disassembly_cost_per_m3': DEFAULT_DISASSEMBLY_PER_M3,
                'assembly_cost_per_m3': DEFAULT_ASSEMBLY_PER_M3,
                'cost_per_mile_under_100': DEFAULT_COST_PER_MILE_UNDER_100,
                'cost_per_mile_over_100': DEFAULT_COST_PER_MILE_OVER_100,
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
                "step_2": f"Inventory Cost: {price_breakdown['total_volume_m3']} × £{company_rates['loading_cost_per_m3']} × {price_breakdown['combined_property_multiplier']} = £{price_breakdown['inventory_cost']}",
                "step_3": f"Mileage Cost: {price_breakdown['distance_miles']} miles × {price_breakdown['total_volume_m3']} m³ × rate = £{price_breakdown['mileage_cost']}",
                "step_4": f"Optional Extras: £{price_breakdown['optional_extras']['total']}",
                "step_5": f"Subtotal: £{price_breakdown['subtotal_before_date']}",
                "step_6": f"Move Date Multiplier: × {price_breakdown['move_date_multiplier']}",
                "step_7": f"Final Total: £{price_breakdown['final_total']}"
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
            "collection_multipliers": COLLECTION_MULTIPLIERS,
            "delivery_multipliers": DELIVERY_MULTIPLIERS,
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
            "packing_per_m3": DEFAULT_PACKING_PER_M3,
        }
    }