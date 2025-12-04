"""
Enhanced Logistics Request Pricing Calculator
File Location: localmoves/localmoves/api/request_pricing.py

This module calculates detailed pricing based on property type, property assessment,
move dates, and optional extras.
"""

import frappe
import json
from frappe import _


# ==================== PRICING CONSTANTS ====================

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

# Collection Property Assessment Multipliers
COLLECTION_PARKING_MULTIPLIERS = {
    'driveway': 1.0,
    'allocated_bay': 1.0,
    'roadside': 1.0,
}

COLLECTION_PARKING_DISTANCE_MULTIPLIERS = {
    'less_than_5m': 1.0,
    '5_to_10m': 1.05,
    '10_to_15m': 1.1,
    '15_to_20m': 1.15,
    'over_20m': 1.2,
}

COLLECTION_EXTERNAL_STAIRS_MULTIPLIERS = {
    'none': 1.0,
    'up_to_5_steps': 1.05,
    'over_5_steps': 1.1,
}

COLLECTION_INTERNAL_ACCESS_MULTIPLIERS = {
    'stairs_only': 1.0,
    'lift_access': 1.05,
}

COLLECTION_FLOOR_MULTIPLIERS = {
    'ground_floor': 1.0,
    '1st_floor': 1.1,
    '2nd_floor': 1.2,
    '3rd_floor': 1.3,
    '4th_floor': 1.4,
}

# Delivery Property Assessment Multipliers (same structure)
DELIVERY_PARKING_MULTIPLIERS = COLLECTION_PARKING_MULTIPLIERS
DELIVERY_PARKING_DISTANCE_MULTIPLIERS = COLLECTION_PARKING_DISTANCE_MULTIPLIERS
DELIVERY_EXTERNAL_STAIRS_MULTIPLIERS = COLLECTION_EXTERNAL_STAIRS_MULTIPLIERS
DELIVERY_INTERNAL_ACCESS_MULTIPLIERS = COLLECTION_INTERNAL_ACCESS_MULTIPLIERS
DELIVERY_FLOOR_MULTIPLIERS = COLLECTION_FLOOR_MULTIPLIERS

# Move Date Multipliers
NOTICE_PERIOD_MULTIPLIERS = {
    'flexible': 0.8,  # Save 20%
    'within_3_days': 1.2,
    'within_week': 1.1,
    'within_month': 1.0,
}

MOVE_DAY_MULTIPLIERS = {
    'sun_to_thurs': 1.0,  # Save 10%
    'fri_sat': 1.1,
}

COLLECTION_TIME_MULTIPLIERS = {
    'flexible': 0.8,  # Save 20%
    '9am_to_5pm': 1.0,
    'four_hour_window': 1.1,
    'one_hour_window': 1.2,
}


# ==================== CORE CALCULATION FUNCTIONS ====================

def calculate_total_volume(pricing_data):
    """
    Calculate total volume (m³) based on property type and selections
    
    Args:
        pricing_data: dict with property_type and related selections
    
    Returns:
        float: Total volume in m³
    """
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
        
        # Add additional spaces
        for space in additional_spaces:
            base_volume += ADDITIONAL_SPACES.get(space, 0)
        
        # Apply quantity multiplier
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
        # First 25 miles
        cost_first_25 = 25 * total_volume * cost_per_mile_under_25
        # Remaining miles
        remaining_miles = distance - 25
        cost_remaining = remaining_miles * total_volume * cost_per_mile_over_25
        mileage_cost = cost_first_25 + cost_remaining
    
    return round(mileage_cost, 2)


def calculate_property_assessment_multiplier(assessment_data):
    """
    Calculate combined multiplier from property assessment
    
    Args:
        assessment_data: dict with parking, stairs, floor, etc.
    
    Returns:
        float: Combined multiplier
    """
    multiplier = 1.0
    
    # Parking
    parking = assessment_data.get('parking')
    if parking:
        multiplier *= COLLECTION_PARKING_MULTIPLIERS.get(parking, 1.0)
    
    # Parking distance
    parking_distance = assessment_data.get('parking_distance')
    if parking_distance:
        multiplier *= COLLECTION_PARKING_DISTANCE_MULTIPLIERS.get(parking_distance, 1.0)
    
    # External stairs
    external_stairs = assessment_data.get('external_stairs')
    if external_stairs:
        multiplier *= COLLECTION_EXTERNAL_STAIRS_MULTIPLIERS.get(external_stairs, 1.0)
    
    # Internal access (only for flats/offices)
    internal_access = assessment_data.get('internal_access')
    if internal_access:
        multiplier *= COLLECTION_INTERNAL_ACCESS_MULTIPLIERS.get(internal_access, 1.0)
    
    # Floor level (only for flats/offices)
    floor_level = assessment_data.get('floor_level')
    if floor_level:
        multiplier *= COLLECTION_FLOOR_MULTIPLIERS.get(floor_level, 1.0)
    
    return round(multiplier, 2)


def calculate_optional_extras(pricing_data, total_volume, company_pricing):
    """
    Calculate costs for optional extras
    
    Returns:
        dict: Breakdown of extras costs
    """
    extras = {}
    total_extras = 0
    
    # Dismantling
    if pricing_data.get('include_dismantling'):
        items_to_dismantle = int(pricing_data.get('dismantling_items', 0))
        cost = items_to_dismantle * company_pricing['disassembly_cost_per_item']
        extras['dismantling'] = round(cost, 2)
        total_extras += cost
    
    # Reassembly
    if pricing_data.get('include_reassembly'):
        items_to_assemble = int(pricing_data.get('reassembly_items', 0))
        cost = items_to_assemble * company_pricing['assembly_cost_per_item']
        extras['reassembly'] = round(cost, 2)
        total_extras += cost
    
    # Packing service
    if pricing_data.get('include_packing'):
        packing_volume = float(pricing_data.get('packing_volume_m3', total_volume))
        cost = packing_volume * company_pricing['packing_cost_per_box']
        extras['packing'] = round(cost, 2)
        total_extras += cost
    
    extras['total'] = round(total_extras, 2)
    return extras


def calculate_move_date_multiplier(move_date_data):
    """Calculate combined multiplier from move date selections"""
    multiplier = 1.0
    
    # Notice period
    notice_period = move_date_data.get('notice_period')
    if notice_period:
        multiplier *= NOTICE_PERIOD_MULTIPLIERS.get(notice_period, 1.0)
    
    # Move day
    move_day = move_date_data.get('move_day')
    if move_day:
        multiplier *= MOVE_DAY_MULTIPLIERS.get(move_day, 1.0)
    
    # Collection time
    collection_time = move_date_data.get('collection_time')
    if collection_time:
        multiplier *= COLLECTION_TIME_MULTIPLIERS.get(collection_time, 1.0)
    
    return round(multiplier, 2)


def calculate_comprehensive_price(request_data, company):
    """
    Main pricing calculation function
    
    Args:
        request_data: dict with all pricing parameters
        company: Logistics Company document
    
    Returns:
        dict: Complete price breakdown
    """
    # Get company pricing
    company_pricing = {
        'loading_cost_per_m3': float(company.get('loading_cost_per_m3', 0) or 0),
        'packing_cost_per_box': float(company.get('packing_cost_per_box', 0) or 0),
        'disassembly_cost_per_item': float(company.get('disassembly_cost_per_item', 0) or 0),
        'assembly_cost_per_item': float(company.get('assembly_cost_per_item', 0) or 0),
        'cost_per_mile_under_25': float(company.get('cost_per_mile_under_25', 0) or 0),
        'cost_per_mile_over_25': float(company.get('cost_per_mile_over_25', 0) or 0),
    }
    
    # Step 1: Calculate total volume
    total_volume = calculate_total_volume(request_data.get('pricing_data', {}))
    
    # Step 2: Calculate base loading cost
    base_loading_cost = calculate_loading_cost(total_volume, company_pricing['loading_cost_per_m3'])
    
    # Step 3: Calculate property assessment multipliers
    collection_multiplier = calculate_property_assessment_multiplier(
        request_data.get('collection_assessment', {})
    )
    delivery_multiplier = calculate_property_assessment_multiplier(
        request_data.get('delivery_assessment', {})
    )
    
    # Combined property assessment multiplier
    property_multiplier = (collection_multiplier + delivery_multiplier) / 2
    
    # Apply property assessment to loading cost
    adjusted_loading_cost = round(base_loading_cost * property_multiplier, 2)
    
    # Step 4: Calculate mileage cost
    distance_miles = float(request_data.get('distance_miles', 0))
    mileage_cost = calculate_mileage_cost(
        distance_miles,
        total_volume,
        company_pricing['cost_per_mile_under_25'],
        company_pricing['cost_per_mile_over_25']
    )
    
    # Step 5: Calculate optional extras
    extras = calculate_optional_extras(
        request_data.get('pricing_data', {}),
        total_volume,
        company_pricing
    )
    
    # Step 6: Calculate subtotal
    subtotal = adjusted_loading_cost + mileage_cost + extras['total']
    
    # Step 7: Apply move date multiplier
    move_date_multiplier = calculate_move_date_multiplier(
        request_data.get('move_date_data', {})
    )
    
    # Step 8: Calculate final total
    final_total = round(subtotal * move_date_multiplier, 2)
    
    # Return comprehensive breakdown
    return {
        'total_volume_m3': total_volume,
        'distance_miles': distance_miles,
        
        'base_loading_cost': base_loading_cost,
        'collection_multiplier': collection_multiplier,
        'delivery_multiplier': delivery_multiplier,
        'combined_property_multiplier': property_multiplier,
        'adjusted_loading_cost': adjusted_loading_cost,
        
        'mileage_cost': mileage_cost,
        
        'optional_extras': extras,
        
        'subtotal': round(subtotal, 2),
        
        'move_date_multiplier': move_date_multiplier,
        
        'final_total': final_total,
        
        'breakdown': {
            'loading': adjusted_loading_cost,
            'mileage': mileage_cost,
            'extras': extras['total'],
            'date_adjustment': round((final_total - subtotal), 2),
        }
    }


# ==================== API ENDPOINTS ====================

@frappe.whitelist(allow_guest=True)
def calculate_detailed_price():
    """
    Calculate detailed price for a move request
    
    Expected request body:
    {
        "company_name": "ABC Logistics",
        "distance_miles": 30,
        "pricing_data": {
            "property_type": "house",  // a_few_items, house, flat, office
            "house_size": "3_bed",  // for house
            "additional_spaces": ["shed", "loft"],  // for house
            "quantity": "everything",  // some_things, half_contents, three_quarter, everything
            "vehicle_type": "mwb_van",  // for a_few_items
            "space_usage": "half_van",  // for a_few_items
            "flat_size": "2_bed",  // for flat
            "office_size": "8_workstations",  // for office
            "include_dismantling": true,
            "dismantling_items": 5,
            "include_reassembly": true,
            "reassembly_items": 5,
            "include_packing": true,
            "packing_volume_m3": 10
        },
        "collection_assessment": {
            "parking": "driveway",
            "parking_distance": "less_than_5m",
            "external_stairs": "none",
            "internal_access": "lift_access",  // for flat/office
            "floor_level": "2nd_floor"  // for flat/office
        },
        "delivery_assessment": {
            "parking": "roadside",
            "parking_distance": "10_to_15m",
            "external_stairs": "up_to_5_steps",
            "internal_access": "stairs_only",
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
        data = frappe.request.get_json() or {}
        
        company_name = data.get('company_name')
        if not company_name:
            return {"success": False, "message": "company_name is required"}
        
        if not frappe.db.exists("Logistics Company", company_name):
            return {"success": False, "message": "Company not found"}
        
        company = frappe.get_doc("Logistics Company", company_name)
        
        # Calculate comprehensive price
        price_breakdown = calculate_comprehensive_price(data, company)
        
        return {
            "success": True,
            "company_name": company_name,
            "company_pricing": {
                "loading_per_m3": float(company.loading_cost_per_m3 or 0),
                "packing_per_box": float(company.packing_cost_per_box or 0),
                "disassembly_per_item": float(company.disassembly_cost_per_item or 0),
                "assembly_per_item": float(company.assembly_cost_per_item or 0),
                "cost_per_mile_under_25": float(company.cost_per_mile_under_25 or 0),
                "cost_per_mile_over_25": float(company.cost_per_mile_over_25 or 0),
            },
            "calculation": price_breakdown,
            "currency": "GBP"
        }
        
    except Exception as e:
        frappe.log_error(f"Detailed Price Calculation Error: {str(e)}")
        return {"success": False, "message": f"Calculation failed: {str(e)}"}


@frappe.whitelist(allow_guest=True)
def get_pricing_options():
    """
    Get all available options for pricing calculations
    Useful for frontend to build dynamic forms
    """
    return {
        "success": True,
        "options": {
            "property_types": ["a_few_items", "house", "flat", "office"],
            
            "vehicle_types": list(PROPERTY_VOLUMES['a_few_items'].keys()),
            "space_usage_options": list(VEHICLE_SPACE_MULTIPLIERS.keys()),
            
            "house_sizes": list(PROPERTY_VOLUMES['house'].keys()),
            "additional_spaces": list(ADDITIONAL_SPACES.keys()),
            
            "flat_sizes": list(PROPERTY_VOLUMES['flat'].keys()),
            
            "office_sizes": list(PROPERTY_VOLUMES['office'].keys()),
            
            "quantity_options": list(QUANTITY_MULTIPLIERS.keys()),
            
            "parking_options": list(COLLECTION_PARKING_MULTIPLIERS.keys()),
            "parking_distance_options": list(COLLECTION_PARKING_DISTANCE_MULTIPLIERS.keys()),
            "external_stairs_options": list(COLLECTION_EXTERNAL_STAIRS_MULTIPLIERS.keys()),
            "internal_access_options": list(COLLECTION_INTERNAL_ACCESS_MULTIPLIERS.keys()),
            "floor_level_options": list(COLLECTION_FLOOR_MULTIPLIERS.keys()),
            
            "notice_period_options": list(NOTICE_PERIOD_MULTIPLIERS.keys()),
            "move_day_options": list(MOVE_DAY_MULTIPLIERS.keys()),
            "collection_time_options": list(COLLECTION_TIME_MULTIPLIERS.keys()),
        },
        "multipliers": {
            "quantity": QUANTITY_MULTIPLIERS,
            "vehicle_space": VEHICLE_SPACE_MULTIPLIERS,
            "notice_period": NOTICE_PERIOD_MULTIPLIERS,
            "move_day": MOVE_DAY_MULTIPLIERS,
            "collection_time": COLLECTION_TIME_MULTIPLIERS,
        }
    }