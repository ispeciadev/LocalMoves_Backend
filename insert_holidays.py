#!/usr/bin/env python
"""
Bulk insert Bank Holidays and School Holidays into LocalMoves database
Run from frappe-bench root: python insert_holidays.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Initialize Frappe
import frappe
frappe.init('localmoves.local')
frappe.connect()
frappe.set_user('Administrator')

# Bank Holidays Data (multiplier 1.6)
BANK_HOLIDAYS = [
    # 2026
    ('2026-01-01', "New Year's Day", 1.6),
    ('2026-04-03', 'Good Friday', 1.6),
    ('2026-04-06', 'Easter Monday', 1.6),
    ('2026-05-04', 'Early May Bank Holiday', 1.6),
    ('2026-05-25', 'Spring Bank Holiday', 1.6),
    ('2026-08-31', 'Summer Bank Holiday', 1.6),
    ('2026-12-25', 'Christmas Day', 1.6),
    ('2026-12-28', 'Boxing Day (substitute)', 1.6),
    # 2027
    ('2027-01-01', "New Year's Day", 1.6),
    ('2027-03-26', 'Good Friday', 1.6),
    ('2027-03-29', 'Easter Monday', 1.6),
    ('2027-05-03', 'Early May Bank Holiday', 1.6),
    ('2027-05-31', 'Spring Bank Holiday', 1.6),
    ('2027-08-30', 'Summer Bank Holiday', 1.6),
    ('2027-12-27', 'Christmas Day (substitute)', 1.6),
    ('2027-12-28', 'Boxing Day (substitute)', 1.6),
    # 2028
    ('2028-01-03', "New Year's Day (substitute)", 1.6),
    ('2028-04-14', 'Good Friday', 1.6),
    ('2028-04-17', 'Easter Monday', 1.6),
    ('2028-05-01', 'Early May Bank Holiday', 1.6),
    ('2028-05-29', 'Spring Bank Holiday', 1.6),
    ('2028-08-28', 'Summer Bank Holiday', 1.6),
    ('2028-12-25', 'Christmas Day', 1.6),
    ('2028-12-26', 'Boxing Day', 1.6),
    # 2029
    ('2029-01-01', "New Year's Day", 1.6),
    ('2029-03-30', 'Good Friday', 1.6),
    ('2029-04-02', 'Easter Monday', 1.6),
    ('2029-05-07', 'Early May Bank Holiday', 1.6),
    ('2029-05-28', 'Spring Bank Holiday', 1.6),
    ('2029-08-27', 'Summer Bank Holiday', 1.6),
    ('2029-12-25', 'Christmas Day', 1.6),
    ('2029-12-26', 'Boxing Day', 1.6),
    # 2030
    ('2030-01-01', "New Year's Day", 1.6),
    ('2030-04-19', 'Good Friday', 1.6),
    ('2030-04-22', 'Easter Monday', 1.6),
    ('2030-05-06', 'Early May Bank Holiday', 1.6),
    ('2030-05-27', 'Spring Bank Holiday', 1.6),
    ('2030-08-26', 'Summer Bank Holiday', 1.6),
    ('2030-12-25', 'Christmas Day', 1.6),
    ('2030-12-26', 'Boxing Day', 1.6),
    # 2031
    ('2031-01-01', "New Year's Day", 1.6),
    ('2031-04-11', 'Good Friday', 1.6),
    ('2031-04-14', 'Easter Monday', 1.6),
    ('2031-05-05', 'Early May Bank Holiday', 1.6),
    ('2031-05-26', 'Spring Bank Holiday', 1.6),
    ('2031-08-25', 'Summer Bank Holiday', 1.6),
    ('2031-12-25', 'Christmas Day', 1.6),
    ('2031-12-26', 'Boxing Day', 1.6),
]

# School Holidays Data (multiplier 1.10)
SCHOOL_HOLIDAYS = [
    # 2026
    ('2026', 'Spring Half Term', '2026-02-16', '2026-02-20', 1.10),
    ('2026', 'Easter Holiday', '2026-03-30', '2026-04-10', 1.10),
    ('2026', 'Summer Half Term', '2026-05-25', '2026-05-29', 1.10),
    ('2026', 'Summer Holiday', '2026-07-23', '2026-08-31', 1.10),
    ('2026', 'Autumn Half Term', '2026-10-26', '2026-10-30', 1.10),
    ('2026', 'Christmas Holiday', '2026-12-21', '2027-01-01', 1.10),
    # 2027
    ('2027', 'Spring Half Term', '2027-02-15', '2027-02-19', 1.10),
    ('2027', 'Easter Holiday', '2027-03-29', '2027-04-09', 1.10),
    ('2027', 'Summer Half Term', '2027-05-31', '2027-06-04', 1.10),
    ('2027', 'Summer Holiday', '2027-07-23', '2027-08-31', 1.10),
    ('2027', 'Autumn Half Term', '2027-10-25', '2027-10-29', 1.10),
    ('2027', 'Christmas Holiday', '2027-12-20', '2028-01-03', 1.10),
    # 2028
    ('2028', 'Spring Half Term', '2028-02-14', '2028-02-18', 1.10),
    ('2028', 'Easter Holiday', '2028-04-03', '2028-04-14', 1.10),
    ('2028', 'Summer Half Term', '2028-05-29', '2028-06-02', 1.10),
    ('2028', 'Summer Holiday', '2028-07-24', '2028-08-31', 1.10),
    ('2028', 'Autumn Half Term', '2028-10-23', '2028-10-27', 1.10),
    ('2028', 'Christmas Holiday', '2028-12-18', '2029-01-02', 1.10),
    # 2029
    ('2029', 'Spring Half Term', '2029-02-12', '2029-02-16', 1.10),
    ('2029', 'Easter Holiday', '2029-04-02', '2029-04-13', 1.10),
    ('2029', 'Summer Half Term', '2029-05-28', '2029-06-01', 1.10),
    ('2029', 'Summer Holiday', '2029-07-23', '2029-08-31', 1.10),
    ('2029', 'Autumn Half Term', '2029-10-22', '2029-10-26', 1.10),
    ('2029', 'Christmas Holiday', '2029-12-17', '2030-01-01', 1.10),
    # 2030
    ('2030', 'Spring Half Term', '2030-02-11', '2030-02-15', 1.10),
    ('2030', 'Easter Holiday', '2030-04-01', '2030-04-12', 1.10),
    ('2030', 'Summer Half Term', '2030-05-27', '2030-05-31', 1.10),
    ('2030', 'Summer Holiday', '2030-07-22', '2030-08-31', 1.10),
    ('2030', 'Autumn Half Term', '2030-10-21', '2030-10-25', 1.10),
    ('2030', 'Christmas Holiday', '2030-12-16', '2031-01-01', 1.10),
    # 2031
    ('2031', 'Spring Half Term', '2031-02-10', '2031-02-14', 1.10),
    ('2031', 'Easter Holiday', '2031-03-31', '2031-04-11', 1.10),
    ('2031', 'Summer Half Term', '2031-05-26', '2031-05-30', 1.10),
    ('2031', 'Summer Holiday', '2031-07-21', '2031-08-31', 1.10),
    ('2031', 'Autumn Half Term', '2031-10-20', '2031-10-24', 1.10),
    ('2031', 'Christmas Holiday', '2031-12-15', '2031-12-31', 1.10),
]

def insert_bank_holidays():
    """Insert all bank holidays"""
    print("\n📅 Inserting Bank Holidays...")
    count = 0
    for date, name, multiplier in BANK_HOLIDAYS:
        try:
            # Check if already exists
            if frappe.db.exists('Bank Holiday', date):
                print(f"  ⏭️  {date} - {name} (already exists)")
                continue
            
            # Extract year from date (YYYY-MM-DD format)
            year = int(date.split('-')[0])
            
            holiday = frappe.new_doc('Bank Holiday')
            holiday.year = year
            holiday.date = date
            holiday.holiday_name = name
            holiday.multiplier = multiplier
            holiday.is_active = 1
            
            holiday.flags.ignore_version = True
            holiday.insert(ignore_permissions=True)
            count += 1
            print(f"  ✅ {date} - {name}")
        except Exception as e:
            print(f"  ❌ {date} - {name}: {str(e)}")
    
    frappe.db.commit()
    print(f"\n✓ Bank Holidays: {count} inserted")
    return count

def insert_school_holidays():
    """Insert all school holidays"""
    print("\n🏫 Inserting School Holidays...")
    count = 0
    for year, holiday_type, start_date, end_date, multiplier in SCHOOL_HOLIDAYS:
        try:
            # Create unique name
            holiday_id = f"{year}_{holiday_type.replace(' ', '_')}"
            
            # Check if already exists
            if frappe.db.exists('School Holiday', holiday_id):
                print(f"  ⏭️  {holiday_type} ({start_date} to {end_date}) - already exists")
                continue
            
            holiday = frappe.new_doc('School Holiday')
            holiday.name = holiday_id
            holiday.year = int(year)
            holiday.holiday_type = holiday_type
            holiday.start_date = start_date
            holiday.end_date = end_date
            holiday.multiplier = multiplier
            holiday.is_active = 1
            
            holiday.flags.ignore_version = True
            holiday.insert(ignore_permissions=True)
            count += 1
            print(f"  ✅ {holiday_type} ({start_date} to {end_date})")
        except Exception as e:
            print(f"  ❌ {holiday_type}: {str(e)}")
    
    frappe.db.commit()
    print(f"\n✓ School Holidays: {count} inserted")
    return count

if __name__ == '__main__':
    try:
        print("=" * 60)
        print("🚀 Starting Holiday Data Import")
        print("=" * 60)
        
        bank_count = insert_bank_holidays()
        school_count = insert_school_holidays()
        
        print("\n" + "=" * 60)
        print(f"✅ IMPORT COMPLETE!")
        print(f"   Bank Holidays: {bank_count}")
        print(f"   School Holidays: {school_count}")
        print(f"   Total: {bank_count + school_count}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        frappe.log_error(f"Holiday Import Error: {str(e)}")
    finally:
        frappe.close()
