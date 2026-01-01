"""
Setup script to populate Last Friday Holiday data
Run with: bench execute localmoves.setup_last_friday_holidays.populate_last_friday_holidays
"""

import frappe
from datetime import datetime
from calendar import monthcalendar

def populate_last_friday_holidays():
    """Populate Last Friday Holiday data for multiple years"""
    
    # Data extracted from your sheet - Last Friday of each month (excluding bank holidays)
    data = [
        # 2026
        (2026, "January", "30/01/2026"),
        (2026, "February", "27/02/2026"),
        (2026, "March", "27/03/2026"),
        (2026, "April", "24/04/2026"),
        (2026, "May", "29/05/2026"),
        (2026, "June", "26/06/2026"),
        (2026, "July", "31/07/2026"),
        (2026, "August", "28/08/2026"),
        (2026, "September", "25/09/2026"),
        (2026, "October", "30/10/2026"),
        (2026, "November", "27/11/2026"),
        (2026, "December", "18/12/2026"),
        # 2027
        (2027, "January", "29/01/2027"),
        (2027, "February", "26/02/2027"),
        (2027, "March", "26/03/2027"),
        (2027, "April", "30/04/2027"),
        (2027, "May", "28/05/2027"),
        (2027, "June", "25/06/2027"),
        (2027, "July", "30/07/2027"),
        (2027, "August", "27/08/2027"),
        (2027, "September", "24/09/2027"),
        (2027, "October", "29/10/2027"),
        (2027, "November", "26/11/2027"),
        (2027, "December", "31/12/2027"),
        # 2028
        (2028, "January", "28/01/2028"),
        (2028, "February", "25/02/2028"),
        (2028, "March", "31/03/2028"),
        (2028, "April", "28/04/2028"),
        (2028, "May", "26/05/2028"),
        (2028, "June", "30/06/2028"),
        (2028, "July", "28/07/2028"),
        (2028, "August", "25/08/2028"),
        (2028, "September", "29/09/2028"),
        (2028, "October", "27/10/2028"),
        (2028, "November", "24/11/2028"),
        (2028, "December", "29/12/2028"),
        # 2029
        (2029, "January", "26/01/2029"),
        (2029, "February", "23/02/2029"),
        (2029, "March", "30/03/2029"),
        (2029, "April", "27/04/2029"),
        (2029, "May", "25/05/2029"),
        (2029, "June", "29/06/2029"),
        (2029, "July", "27/07/2029"),
        (2029, "August", "31/08/2029"),
        (2029, "September", "28/09/2029"),
        (2029, "October", "26/10/2029"),
        (2029, "November", "30/11/2029"),
        (2029, "December", "28/12/2029"),
        # 2030
        (2030, "January", "25/01/2030"),
        (2030, "February", "22/02/2030"),
        (2030, "March", "29/03/2030"),
        (2030, "April", "26/04/2030"),
        (2030, "May", "31/05/2030"),
        (2030, "June", "28/06/2030"),
        (2030, "July", "26/07/2030"),
        (2030, "August", "30/08/2030"),
        (2030, "September", "27/09/2030"),
        (2030, "October", "25/10/2030"),
        (2030, "November", "29/11/2030"),
        (2030, "December", "27/12/2030"),
        # 2031
        (2031, "January", "31/01/2031"),
        (2031, "February", "28/02/2031"),
        (2031, "March", "28/03/2031"),
        (2031, "April", "25/04/2031"),
        (2031, "May", "30/05/2031"),
        (2031, "June", "27/06/2031"),
        (2031, "July", "25/07/2031"),
        (2031, "August", "29/08/2031"),
        (2031, "September", "26/09/2031"),
        (2031, "October", "31/10/2031"),
        (2031, "November", "28/11/2031"),
        (2031, "December", "19/12/2031"),
    ]
    
    month_names = {
        "January": 1, "February": 2, "March": 3, "April": 4,
        "May": 5, "June": 6, "July": 7, "August": 8,
        "September": 9, "October": 10, "November": 11, "December": 12
    }
    
    created_count = 0
    skipped_count = 0
    
    for year, month_name, date_str in data:
        try:
            # Convert date format from DD/MM/YYYY to YYYY-MM-DD
            day, month, yr = date_str.split('/')
            date_obj = datetime(int(yr), int(month), int(day))
            formatted_date = date_obj.strftime('%Y-%m-%d')
            day_of_week = date_obj.strftime('%A')
            
            # Check if already exists
            if frappe.db.exists('Last Friday Holiday', {'year': year, 'month': month_name}):
                print(f"⏭️  Skipping {month_name} {year} - already exists")
                skipped_count += 1
                continue
            
            # Create Last Friday Holiday
            holiday = frappe.new_doc('Last Friday Holiday')
            holiday.year = year
            holiday.month = month_name
            holiday.date = formatted_date
            holiday.day_of_week = day_of_week
            holiday.multiplier = 1.10
            holiday.is_active = 1
            
            holiday.flags.ignore_version = True
            holiday.insert(ignore_permissions=True)
            
            print(f"✅ Created: {month_name} {year} ({formatted_date}) - {day_of_week}")
            created_count += 1
            
        except Exception as e:
            print(f"❌ Error creating {month_name} {year}: {str(e)}")
    
    frappe.db.commit()
    
    print(f"\n📊 Summary:")
    print(f"  ✅ Created: {created_count}")
    print(f"  ⏭️  Skipped: {skipped_count}")
    print(f"  📅 Total: {created_count + skipped_count}")
