
"""
Calendar Pricing API
Dynamic pricing based on move date, notice period, and demand


Implements flight-booking style calendar with color-coded pricing
"""


import frappe
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar as cal
from localmoves.utils.config_manager import get_config




# ==================== HELPER FUNCTIONS ====================


def get_notice_period_multiplier(current_date, move_date):
    """
    Calculate notice period multiplier based on days between current and move date
   
    Returns: (multiplier, tier_name)
    """
    try:
        if isinstance(current_date, str):
            current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
        if isinstance(move_date, str):
            move_date = datetime.strptime(move_date, "%Y-%m-%d").date()
       
        days_notice = (move_date - current_date).days
       
        # Hardcoded multipliers (not from config to avoid issues)
        NOTICE_PERIOD_MULTIPLIERS = {
            "same_day": 1.5,
            "within_1_day": 1.5,
            "within_2_days": 1.4,
            "within_3_days": 1.3,
            "within_a_week": 1.2,
            "within_2_weeks": 1.1,
            "within_a_month": 1.0,
            "over_month": 0.9,
            "flexible": 0.8
        }
       
        # Notice period tiers (from spreadsheet)
        if days_notice < 0:
            return 1.5, "Same Day"
        elif days_notice == 0:
            return 1.5, "Same Day"
        elif days_notice == 1:
            return 1.5, "Within 1 Day"
        elif days_notice == 2:
            return 1.4, "Within 2 Days"
        elif days_notice <= 3:
            return 1.3, "Within 3 Days"
        elif days_notice <= 7:
            return 1.2, "Within a Week"
        elif days_notice <= 14:
            return 1.1, "Within 2 Weeks"
        elif days_notice <= 30:
            return 1.0, "Within a Month"
        elif days_notice > 30:
            return 0.9, "Over 1 Month"
        else:
            return 0.8, "Flexible"
    except Exception as e:
        frappe.log_error(f"Notice period multiplier error: current_date={current_date}, move_date={move_date}, error={str(e)}", "Notice Period")
        return 1.0, "Error - Default"




def get_day_of_week_multiplier(date):
    """
    Calculate day of week multiplier
    Friday & Saturday = premium
    Sunday - Thursday = standard
   
    Returns: (multiplier, day_name)
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()
   
    day_name = date.strftime("%A")
    weekday = date.weekday()  # Monday=0, Sunday=6
   
    # Get multipliers from config
    MOVE_DAY_MULTIPLIERS = get_config().get('move_day_multipliers', {
        "sun_to_thurs": 1.0,
        "friday_saturday": 1.15
    })
   
    # Friday (4) and Saturday (5) are premium
    if weekday in [4, 5]:
        return MOVE_DAY_MULTIPLIERS['friday_saturday'], day_name
    else:
        return MOVE_DAY_MULTIPLIERS['sun_to_thurs'], day_name




def is_bank_holiday(date):
    """
    Check if date is a bank holiday
   
    Returns: (is_holiday, multiplier, holiday_name)
    """
    if isinstance(date, str):
        date_str = date
    else:
        date_str = date.strftime("%Y-%m-%d")
   
    holiday = frappe.db.get_value(
        "Bank Holiday",
        filters={"date": date_str, "is_active": 1},
        fieldname=["holiday_name", "multiplier"],
        as_dict=True
    )
   
    # Get default bank holiday multiplier from config
    default_bank_holiday_mult = get_config().get('pricing', {}).get('bank_holiday_multiplier', 1.6)
   
    if holiday:
        return True, holiday.get("multiplier", default_bank_holiday_mult), holiday.get("holiday_name")
    return False, 1.0, None




def is_school_holiday(date):
    """
    Check if date falls within a school holiday period
   
    Returns: (is_holiday, multiplier, holiday_type)
    """
    if isinstance(date, str):
        date_str = date
    else:
        date_str = date.strftime("%Y-%m-%d")
   
    # Find school holidays that include this date
    holidays = frappe.db.sql("""
        SELECT holiday_type, multiplier
        FROM `tabSchool Holiday`
        WHERE is_active = 1
        AND %(date)s BETWEEN start_date AND end_date
        LIMIT 1
    """, {"date": date_str}, as_dict=True)
   
    # Get default school holiday multiplier from config
    default_school_holiday_mult = get_config().get('pricing', {}).get('school_holiday_multiplier', 1.10)
   
    if holidays:
        holiday = holidays[0]
        return True, holiday.get("multiplier", default_school_holiday_mult), holiday.get("holiday_type")
    return False, 1.0, None




def is_last_friday_of_month(date):
    """
    Check if date is the last Friday of the month (excluding bank holidays)
   
    Returns: (is_last_friday, multiplier)
    """
    if isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()
   
    # Check if it's a Friday
    if date.weekday() != 4:  # Friday = 4
        return False, 1.0
   
    # Check if it's a bank holiday (exclude if yes)
    is_bank, _, _ = is_bank_holiday(date)
    if is_bank:
        return False, 1.0
   
    # Check if it's the last Friday of the month
    year = date.year
    month = date.month
    last_day = cal.monthrange(year, month)[1]
   
    # Find all Fridays in the month
    fridays = []
    for day in range(1, last_day + 1):
        check_date = datetime(year, month, day).date()
        if check_date.weekday() == 4:
            fridays.append(check_date)
   
    # Get last Friday multiplier from config
    last_friday_mult = get_config().get('pricing', {}).get('last_friday_multiplier', 1.10)
   
    # Check if current date is the last Friday
    if fridays and date == fridays[-1]:
        return True, last_friday_mult
   
    return False, 1.0




def get_demand_multiplier(date):
    """
    Get demand multiplier based on booking count for the date
   
    Returns: (multiplier, booking_count, is_high_demand)
    """
    if isinstance(date, str):
        date_str = date
    else:
        date_str = date.strftime("%Y-%m-%d")
   
    if frappe.db.exists("Daily Booking Count", date_str):
        booking_data = frappe.db.get_value(
            "Daily Booking Count",
            date_str,
            ["booking_count", "demand_multiplier_active", "demand_multiplier"],
            as_dict=True
        )
       
        if booking_data and booking_data.get("demand_multiplier_active"):
            return (
                booking_data.get("demand_multiplier", 1.1),
                booking_data.get("booking_count", 0),
                True
            )
        return 1.0, booking_data.get("booking_count", 0), False
   
    return 1.0, 0, False




def calculate_final_price_for_date(base_price, move_date, current_date=None):
    """
    Calculate final price for a specific move date
   
    Args:
        base_price: Base price without any multipliers
        move_date: Date of the move
        current_date: Current date (for notice period calculation)
   
    Returns: dict with price breakdown
    """
    if current_date is None:
        current_date = datetime.now().date()
   
    if isinstance(move_date, str):
        move_date = datetime.strptime(move_date, "%Y-%m-%d").date()
    if isinstance(current_date, str):
        current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
   
    # Get all multipliers
    notice_mult, notice_tier = get_notice_period_multiplier(current_date, move_date)
    day_mult, day_name = get_day_of_week_multiplier(move_date)
    is_bank, bank_mult, bank_name = is_bank_holiday(move_date)
    is_school, school_mult, school_type = is_school_holiday(move_date)
    is_last_fri, last_fri_mult = is_last_friday_of_month(move_date)
    demand_mult, booking_count, is_high_demand = get_demand_multiplier(move_date)
   
    # Calculate total multiplier
    total_multiplier = notice_mult * day_mult * bank_mult * school_mult * last_fri_mult * demand_mult
   
    # Calculate final price
    final_price = base_price * total_multiplier
   
    # Calculate uplift percentage
    uplift_percentage = ((final_price - base_price) / base_price) * 100
   
    # Determine color
    if uplift_percentage < 10:
        color = "green"
    elif uplift_percentage <= 20:
        color = "amber"
    else:
        color = "red"
   
    # Build reasons list
    reasons = []
    if notice_mult != 1.0:
        change = ((notice_mult - 1.0) * 100)
        if change > 0:
            reasons.append(f"{notice_tier} - +{change:.0f}%")
        else:
            reasons.append(f"{notice_tier} - Save {abs(change):.0f}%")
   
    if day_mult != 1.0:
        reasons.append(f"Weekend ({day_name}) - +{((day_mult - 1.0) * 100):.0f}%")
   
    if is_bank:
        reasons.append(f"Bank Holiday ({bank_name}) - +{((bank_mult - 1.0) * 100):.0f}%")
   
    if is_school:
        reasons.append(f"School Holiday ({school_type}) - +{((school_mult - 1.0) * 100):.0f}%")
   
    if is_last_fri:
        reasons.append(f"Last Friday of Month - +{((last_fri_mult - 1.0) * 100):.0f}%")
   
    if is_high_demand:
        reasons.append(f"High Demand ({booking_count} bookings) - +{((demand_mult - 1.0) * 100):.0f}%")
   
    if not reasons:
        reasons.append("Standard pricing")
   
    return {
        "date": move_date.strftime("%Y-%m-%d"),
        "day_of_week": day_name,
        "price": round(final_price, 2),
        "notice_days": (move_date - current_date).days,
        "multipliers": {
            "notice_period": notice_mult,
            "day_of_week": day_mult,
            "bank_holiday": bank_mult,
            "school_holiday": school_mult,
            "last_friday": last_fri_mult,
            "demand": demand_mult,
            "total": round(total_multiplier, 3)
        },
        "color": color,
        "uplift_percentage": round(uplift_percentage, 1),
        "reasons": reasons,
        "booking_count": booking_count,
        "special_days": {
            "is_bank_holiday": is_bank,
            "bank_holiday_name": bank_name,
            "is_school_holiday": is_school,
            "school_holiday_type": school_type,
            "is_last_friday": is_last_fri,
            "is_high_demand": is_high_demand
        }
    }




# ==================== API ENDPOINTS ====================


@frappe.whitelist(allow_guest=True)
def get_price_calendar(company_name=None, base_price=None, month=None, year=None, current_date=None, selected_items=None,
                      collection_parking=None, collection_parking_distance=None, collection_house_type=None, 
                      collection_internal_access=None, collection_floor_level=None,
                      delivery_parking=None, delivery_parking_distance=None, delivery_house_type=None, 
                      delivery_internal_access=None, delivery_floor_level=None):
    """
    Get price calendar for a specific month
   
    Args:
        company_name: Name of the logistics company
        base_price: Base price for the move (optional if selected_items provided)
        month: Month (1-12)
        year: Year (e.g., 2026)
        current_date: Current date for notice period calculation (optional)
        selected_items: Dict of item names and quantities to calculate base_price dynamically
        collection_parking/delivery_parking: Property assessment fields for multiplier calculation
   
    Returns: Calendar with prices for each day
    """
    try:
        import json
        # Get parameters from request body ONLY if actually called via HTTP
        # If parameters were passed to function, use them directly (allows internal calls)
        try:
            if frappe.request and frappe.request.method == "POST":
                data = frappe.request.get_json() or {}
                base_price = base_price or data.get("base_price")
                month = month or data.get("month")
                year = year or data.get("year")
                current_date = current_date or data.get("current_date")
                company_name = company_name or data.get("company_name")
                selected_items = selected_items or data.get("selected_items")
                collection_parking = collection_parking or data.get("collection_parking")
                collection_parking_distance = collection_parking_distance or data.get("collection_parking_distance")
                collection_house_type = collection_house_type or data.get("collection_house_type")
                collection_internal_access = collection_internal_access or data.get("collection_internal_access")
                collection_floor_level = collection_floor_level or data.get("collection_floor_level")
                delivery_parking = delivery_parking or data.get("delivery_parking")
                delivery_parking_distance = delivery_parking_distance or data.get("delivery_parking_distance")
                delivery_house_type = delivery_house_type or data.get("delivery_house_type")
                delivery_internal_access = delivery_internal_access or data.get("delivery_internal_access")
                delivery_floor_level = delivery_floor_level or data.get("delivery_floor_level")
        except (AttributeError, RuntimeError):
            # frappe.request doesn't exist when called internally (not via HTTP)
            # This is OK - just use the parameters passed to the function
            pass
       
        # Parse selected_items if provided as JSON string
        if isinstance(selected_items, str):
            try:
                selected_items = json.loads(selected_items)
            except:
                selected_items = None
       
        # If selected_items provided, calculate base_price from volume and rates
        if selected_items and isinstance(selected_items, dict) and len(selected_items) > 0:
            # Calculate total volume from selected items
            total_volume = 0
            for item_name, quantity in selected_items.items():
                try:
                    if frappe.db.exists("Moving Inventory Item", item_name):
                        item = frappe.get_doc("Moving Inventory Item", item_name)
                        volume_per_item = item.average_volume
                        total_volume += volume_per_item * int(quantity)
                except:
                    continue
            
            if total_volume > 0:
                # Get default company rates
                from localmoves.utils.config_manager import get_config
                config = get_config()
                loading_cost_per_m3 = config.get('pricing', {}).get('loading_cost_per_m3', 35.0)
                
                # Calculate base_price as subtotal before date multipliers
                # This is inventory cost only (no extras, no multipliers)
                base_price = total_volume * loading_cost_per_m3
        
        # Parse parameters - base_price is required
        if base_price is None:
            return {
                "success": False,
                "message": "base_price or selected_items is required"
            }
       
        base_price = float(base_price)
        month = int(month or datetime.now().month)
        year = int(year or datetime.now().year)
       
        if current_date is None:
            current_date = datetime.now().date()
        elif isinstance(current_date, str):
            current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
       
        # Calculate property assessment multiplier from parameters
        from localmoves.api.company import get_property_assessment_multiplier
        property_multiplier = get_property_assessment_multiplier(
            collection_parking=collection_parking,
            collection_parking_distance=collection_parking_distance,
            collection_house_type=collection_house_type,
            collection_internal_access=collection_internal_access,
            collection_floor_level=collection_floor_level,
            delivery_parking=delivery_parking,
            delivery_parking_distance=delivery_parking_distance,
            delivery_house_type=delivery_house_type,
            delivery_internal_access=delivery_internal_access,
            delivery_floor_level=delivery_floor_level
        )
        
        # Apply property assessment multiplier to base_price
        adjusted_base_price = base_price * property_multiplier if property_multiplier else base_price
       
        # Get number of days in month
        num_days = cal.monthrange(year, month)[1]
       
        # Calculate price for each day using adjusted base price
        calendar_data = []
        cheapest_day = None
        most_expensive_day = None
       
        for day in range(1, num_days + 1):
            move_date = datetime(year, month, day).date()
            day_data = calculate_final_price_for_date(adjusted_base_price, move_date, current_date)
            calendar_data.append(day_data)
           
            # Track cheapest and most expensive
            if cheapest_day is None or day_data["price"] < cheapest_day["price"]:
                cheapest_day = day_data
            if most_expensive_day is None or day_data["price"] > most_expensive_day["price"]:
                most_expensive_day = day_data
       
        return {
            "success": True,
            "company_name": company_name,
            "base_price": adjusted_base_price,
            "base_price_note": f"Adjusted with property assessment multiplier {property_multiplier:.3f}x" if property_multiplier != 1.0 else None,
            "month": month,
            "year": year,
            "current_date": current_date.strftime("%Y-%m-%d"),
            "calendar": calendar_data,
            "cheapest_day": {
                "date": cheapest_day["date"],
                "price": cheapest_day["price"],
                "savings": round(adjusted_base_price - cheapest_day["price"], 2)
            },
            "most_expensive_day": {
                "date": most_expensive_day["date"],
                "price": most_expensive_day["price"],
                "premium": round(most_expensive_day["price"] - adjusted_base_price, 2)
            }
        }
   
    except Exception as e:
        frappe.log_error(f"Calendar Pricing Error: {str(e)}", "Calendar Pricing")
        return {
            "success": False,
            "message": f"Failed to generate calendar: {str(e)}"
        }




@frappe.whitelist(allow_guest=True)
def get_calendar_pricing_for_company(company_name=None, company_exact_pricing=None, month=None, year=None, current_date=None):
    """
    Get price calendar for a company using its exact pricing as the base
    
    This function ensures the calendar always shows the company's actual price
    as the base (guaranteed on at least one date), similar to flight booking systems.
   
    Args:
        company_name: Name of the logistics company
        company_exact_pricing: Company's exact pricing total (final_total from search_companies_with_cost)
        month: Month (1-12)
        year: Year (e.g., 2026)
        current_date: Current date for notice period calculation (optional)
   
    Returns: Calendar with prices for each day using company's exact pricing
    """
    try:
        # Parse parameters - company_exact_pricing is required
        if company_exact_pricing is None:
            return {
                "success": False,
                "message": "company_exact_pricing is required"
            }
       
        company_exact_pricing = float(company_exact_pricing)
        month = int(month or datetime.now().month)
        year = int(year or datetime.now().year)
       
        if current_date is None:
            current_date = datetime.now().date()
        elif isinstance(current_date, str):
            current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
       
        # Get number of days in month
        num_days = cal.monthrange(year, month)[1]
       
        # Calculate price for each day using company's exact pricing as base
        calendar_data = []
        cheapest_day = None
        most_expensive_day = None
       
        for day in range(1, num_days + 1):
            move_date = datetime(year, month, day).date()
            day_data = calculate_final_price_for_date(company_exact_pricing, move_date, current_date)
            calendar_data.append(day_data)
           
            # Track cheapest and most expensive
            if cheapest_day is None or day_data["price"] < cheapest_day["price"]:
                cheapest_day = day_data
            if most_expensive_day is None or day_data["price"] > most_expensive_day["price"]:
                most_expensive_day = day_data
       
        return {
            "success": True,
            "company_name": company_name,
            "base_price": company_exact_pricing,
            "base_price_note": "This is the company's exact pricing - calendar multipliers apply from this base",
            "month": month,
            "year": year,
            "current_date": current_date.strftime("%Y-%m-%d"),
            "calendar": calendar_data,
            "cheapest_day": {
                "date": cheapest_day["date"],
                "price": cheapest_day["price"],
                "savings": round(company_exact_pricing - cheapest_day["price"], 2)
            },
            "most_expensive_day": {
                "date": most_expensive_day["date"],
                "price": most_expensive_day["price"],
                "premium": round(most_expensive_day["price"] - company_exact_pricing, 2)
            }
        }
   
    except Exception as e:
        frappe.log_error(f"Company Calendar Pricing Error: {str(e)}", "Calendar Pricing")
        return {
            "success": False,
            "message": f"Failed to generate company calendar: {str(e)}"
        }




@frappe.whitelist(allow_guest=True)
def get_cheapest_dates(company_name=None, base_price=None, start_date=None, end_date=None, top_n=5, current_date=None):
    """
    Get the cheapest dates within a date range
   
    Args:
        company_name: Name of the logistics company
        base_price: Base price for the move
        start_date: Start of date range
        end_date: End of date range
        top_n: Number of cheapest dates to return
        current_date: Current date for notice period calculation
   
    Returns: List of cheapest dates
    """
    try:
        base_price = float(base_price or 1000)
        top_n = int(top_n or 5)
       
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        if current_date is None:
            current_date = datetime.now().date()
        elif isinstance(current_date, str):
            current_date = datetime.strptime(current_date, "%Y-%m-%d").date()
       
        # Calculate prices for all dates in range
        all_dates = []
        current = start_date
        while current <= end_date:
            day_data = calculate_final_price_for_date(base_price, current, current_date)
            all_dates.append(day_data)
            current += timedelta(days=1)
       
        # Sort by price and get top N
        all_dates.sort(key=lambda x: x["price"])
        cheapest_dates = all_dates[:top_n]
       
        # Add savings to each
        for date_data in cheapest_dates:
            date_data["savings"] = round(base_price - date_data["price"], 2)
       
        return {
            "success": True,
            "company_name": company_name,
            "base_price": base_price,
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "cheapest_dates": cheapest_dates
        }
   
    except Exception as e:
        frappe.log_error(f"Cheapest Dates Error: {str(e)}", "Calendar Pricing")
        return {
            "success": False,
            "message": f"Failed to find cheapest dates: {str(e)}"
        }

