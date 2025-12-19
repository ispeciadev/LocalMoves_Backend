"""
Moving Inventory API
File: localmoves/localmoves/api/inventory.py

Complete CRUD operations for inventory items
"""

import frappe
from frappe import _

@frappe.whitelist()
def create_item(category, item_name, average_volume):
    """Create a new inventory item"""
    try:
        doc = frappe.get_doc({
            "doctype": "Moving Inventory Item",
            "category": category,
            "item_name": item_name,
            "average_volume": float(average_volume),
            "unit": "m³"
        })
        doc.insert()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Item created successfully",
            "data": doc.as_dict()
        }
    except Exception as e:
        frappe.db.rollback()
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def get_item(item_name):
    """Get a single inventory item"""
    try:
        doc = frappe.get_doc("Moving Inventory Item", item_name)
        return {
            "success": True,
            "data": doc.as_dict()
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def get_all_items(category=None):
    """Get all inventory items, optionally filtered by category"""
    try:
        filters = {}
        if category:
            filters["category"] = category
        
        items = frappe.get_all(
            "Moving Inventory Item",
            filters=filters,
            fields=["name", "category", "item_name", "average_volume", "unit"]
        )
        
        return {
            "success": True,
            "data": items,
            "count": len(items)
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def update_item(item_name, category=None, new_item_name=None, average_volume=None):
    """Update an existing inventory item"""
    try:
        doc = frappe.get_doc("Moving Inventory Item", item_name)
        
        if category:
            doc.category = category
        if new_item_name:
            doc.item_name = new_item_name
        if average_volume:
            doc.average_volume = float(average_volume)
        
        doc.save()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Item updated successfully",
            "data": doc.as_dict()
        }
    except Exception as e:
        frappe.db.rollback()
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def delete_item(item_name):
    """Delete an inventory item"""
    try:
        frappe.delete_doc("Moving Inventory Item", item_name)
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Item deleted successfully"
        }
    except Exception as e:
        frappe.db.rollback()
        return {
            "success": False,
            "message": str(e)
        }


@frappe.whitelist()
def bulk_upload(items):
    """
    Bulk upload inventory items
    items should be a JSON string or list of dicts:
    [
        {"category": "Living Room", "item_name": "Sofa", "average_volume": 2.0},
        {"category": "Bedroom", "item_name": "Bed", "average_volume": 1.5}
    ]
    """
    try:
        import json
        if isinstance(items, str):
            items = json.loads(items)
        
        created = 0
        errors = []
        
        for item in items:
            try:
                doc = frappe.get_doc({
                    "doctype": "Moving Inventory Item",
                    "category": item.get("category"),
                    "item_name": item.get("item_name"),
                    "average_volume": float(item.get("average_volume")),
                    "unit": "m³"
                })
                doc.insert()
                created += 1
            except Exception as e:
                errors.append({
                    "item": item.get("item_name"),
                    "error": str(e)
                })
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"Uploaded {created} items",
            "created": created,
            "errors": errors
        }
    except Exception as e:
        frappe.db.rollback()
        return {
            "success": False,
            "message": str(e)
        }


# @frappe.whitelist()
# def upload_all_inventory():
#     """Upload all predefined inventory items including Office and Gym categories"""
    
#     inventory_data = [
#         # Living Room Items
        
#         # Office Items - Desks & Tables
#         {"category": "Office", "item_name": "Standing Desk (adjustable)", "average_volume": 1.18},
#         {"category": "Office", "item_name": "Corner Desk (L-shape)", "average_volume": 1.44},
#         {"category": "Office", "item_name": "Reception Desk (small)", "average_volume": 0.79},
#         {"category": "Office", "item_name": "Reception Desk (large counter)", "average_volume": 1.94},
#         {"category": "Office", "item_name": "Coffee Table (round)", "average_volume": 0.20},
#         {"category": "Office", "item_name": "Side Table", "average_volume": 0.12},
#         {"category": "Office", "item_name": "Training Table (folding)", "average_volume": 0.41},
#         {"category": "Office", "item_name": "High Bar Table", "average_volume": 0.40},
        
#         # Office Items - Seating
#         {"category": "Office", "item_name": "Ergonomic Chair", "average_volume": 0.59},
#         {"category": "Office", "item_name": "Conference Chair (stackable)", "average_volume": 0.23},
#         {"category": "Office", "item_name": "Bar Stool", "average_volume": 0.22},
#         {"category": "Office", "item_name": "Reception Waiting Chair", "average_volume": 0.41},
#         {"category": "Office", "item_name": "Lounge Armchair", "average_volume": 0.65},
#         {"category": "Office", "item_name": "Bean Bag", "average_volume": 0.34},
        
#         # Office Items - Storage & Shelving
#         {"category": "Office", "item_name": "Metal Storage Locker", "average_volume": 0.31},
#         {"category": "Office", "item_name": "Large Metal Cabinet (2-door)", "average_volume": 0.73},
#         {"category": "Office", "item_name": "Mobile Pedestal (wheels)", "average_volume": 0.12},
#         {"category": "Office", "item_name": "Compact Rolling File Rack", "average_volume": 0.61},
#         {"category": "Office", "item_name": "Open Shelf Unit (wide)", "average_volume": 0.84},
#         {"category": "Office", "item_name": "Desk Hutch", "average_volume": 0.30},
#         {"category": "Office", "item_name": "Document Sorter (multi-level)", "average_volume": 0.05},
        
#         # Office Items - Electronics & IT Equipment
#         {"category": "Office", "item_name": "Laptop (boxed)", "average_volume": 0.01},
#         {"category": "Office", "item_name": "Dual Monitor Arm", "average_volume": 0.04},
#         {"category": "Office", "item_name": "UPS Battery Unit", "average_volume": 0.03},
#         {"category": "Office", "item_name": "Server (rack-mounted)", "average_volume": 0.09},
#         {"category": "Office", "item_name": "Desk Phone", "average_volume": 0.005},
#         {"category": "Office", "item_name": "Projector", "average_volume": 0.0075},
#         {"category": "Office", "item_name": "Projector Screen (rolled)", "average_volume": 0.03},
#         {"category": "Office", "item_name": "Router / Switch (boxed)", "average_volume": 0.006},
        
#         # Office Items - Décor & Boards
#         {"category": "Office", "item_name": "Large Whiteboard", "average_volume": 0.108},
#         {"category": "Office", "item_name": "Corkboard", "average_volume": 0.054},
#         {"category": "Office", "item_name": "Wall Clock", "average_volume": 0.009},
#         {"category": "Office", "item_name": "Artificial Plant (tall)", "average_volume": 0.24},
#         {"category": "Office", "item_name": "Plant (medium pot)", "average_volume": 0.04},
#         {"category": "Office", "item_name": "Coat Stand", "average_volume": 0.45},
#         {"category": "Office", "item_name": "Floor Lamp", "average_volume": 0.14},
        
#         # Office Items - Kitchen / Break Area
#         {"category": "Office", "item_name": "Fridge (under-counter)", "average_volume": 0.26},
#         {"category": "Office", "item_name": "Full-Size Fridge", "average_volume": 0.88},
#         {"category": "Office", "item_name": "Microwave", "average_volume": 0.04},
#         {"category": "Office", "item_name": "Kettle (boxed)", "average_volume": 0.02},
#         {"category": "Office", "item_name": "Water Cooler Dispenser", "average_volume": 0.12},
#         {"category": "Office", "item_name": "Dining Table", "average_volume": 0.84},
#         {"category": "Office", "item_name": "Dining Chair", "average_volume": 0.18},
        
#         # Office Items - Boxes & Crates
#         {"category": "Office", "item_name": "Small Moving Box (Books / Tools)", "average_volume": 0.036},
#         {"category": "Office", "item_name": "Medium Moving Box (General Use)", "average_volume": 0.097},
#         {"category": "Office", "item_name": "Large Moving Box (Bulky Items)", "average_volume": 0.129},
#         {"category": "Office", "item_name": "Extra-Large Moving Box", "average_volume": 0.226},
#         {"category": "Office", "item_name": "Archive Document Box (A4 Files)", "average_volume": 0.032},
#         {"category": "Office", "item_name": "Heavy-Duty Crate (Plastic, Stackable)", "average_volume": 0.072},
#         {"category": "Office", "item_name": "Industrial Crate (Large Plastic Tote)", "average_volume": 0.140},
#         {"category": "Office", "item_name": "IT Equipment Crate (Padded)", "average_volume": 0.240},
#         {"category": "Office", "item_name": "File Storage Crate (Long)", "average_volume": 0.126},
#         {"category": "Office", "item_name": "Wardrobe Box (with hanging rail)", "average_volume": 0.330},
#         {"category": "Office", "item_name": "Pallet Crate (Wooden)", "average_volume": 1.200},
#         {"category": "Office", "item_name": "Euro Pallet Box (Large Foldable)", "average_volume": 0.960},
#         {"category": "Office", "item_name": "Half-Size Pallet Box", "average_volume": 0.288},
        
#         # Office Items - Miscellaneous
#         {"category": "Office", "item_name": "Shredder (small)", "average_volume": 0.04},
#         {"category": "Office", "item_name": "Shredder (large)", "average_volume": 0.18},
#         {"category": "Office", "item_name": "Cardboard Archive Box", "average_volume": 0.03},
#         {"category": "Office", "item_name": "Coat Hanger Rail", "average_volume": 0.75},
#         {"category": "Office", "item_name": "Cleaning Cart", "average_volume": 0.45},
#         {"category": "Office", "item_name": "Vacuum Cleaner", "average_volume": 0.14},
#         {"category": "Office", "item_name": "Portable Partition Panel", "average_volume": 0.135},
#         {"category": "Office", "item_name": "Mobile Whiteboard (on wheels)", "average_volume": 1.40},
        
#         # Gym Items - Cardio Equipment
#         {"category": "Gym", "item_name": "Treadmill (commercial)", "average_volume": 2.70},
#         {"category": "Gym", "item_name": "Elliptical Trainer", "average_volume": 2.86},
#         {"category": "Gym", "item_name": "Spin Bike", "average_volume": 0.94},
#         {"category": "Gym", "item_name": "Upright Exercise Bike", "average_volume": 0.72},
#         {"category": "Gym", "item_name": "Rowing Machine", "average_volume": 0.83},
#         {"category": "Gym", "item_name": "Stair Climber / Step Machine", "average_volume": 2.46},
        
#         # Gym Items - Strength Equipment
#         {"category": "Gym", "item_name": "Smith Machine", "average_volume": 6.00},
#         {"category": "Gym", "item_name": "Cable Crossover", "average_volume": 0.70},
#         {"category": "Gym", "item_name": "Lat Pulldown Machine", "average_volume": 3.96},
#         {"category": "Gym", "item_name": "Seated Row Machine", "average_volume": 2.64},
#         {"category": "Gym", "item_name": "Chest Press Machine", "average_volume": 2.52},
#         {"category": "Gym", "item_name": "Leg Press (45°)", "average_volume": 3.28},
#         {"category": "Gym", "item_name": "Leg Extension / Curl Combo", "average_volume": 1.96},
        
#         # Gym Items - Free Weights & Racks
#         {"category": "Gym", "item_name": "Dumbbell Rack (2-tier)", "average_volume": 1.20},
#         {"category": "Gym", "item_name": "Dumbbell Set (pair, average footprint)", "average_volume": 0.025},
#         {"category": "Gym", "item_name": "Barbell Rack", "average_volume": 1.44},
#         {"category": "Gym", "item_name": "Weight Plates (stacked, 100kg set)", "average_volume": 0.11},
#         {"category": "Gym", "item_name": "Power Rack / Squat Rack", "average_volume": 0.50},
        
#         # Gym Items - Benches
#         {"category": "Gym", "item_name": "Incline Bench", "average_volume": 1.01},
#         {"category": "Gym", "item_name": "Flat Bench", "average_volume": 0.32},
#         {"category": "Gym", "item_name": "Adjustable Bench (folding)", "average_volume": 0.39},
        
#         # Gym Items - Accessories & Other
#         {"category": "Gym", "item_name": "Kettlebell (each, typical 12–20kg)", "average_volume": 0.019},
#         {"category": "Gym", "item_name": "Medicine Ball", "average_volume": 0.043},
#         {"category": "Gym", "item_name": "Plyometric Box (large)", "average_volume": 0.34},
#         {"category": "Gym", "item_name": "Punching Bag (standing)", "average_volume": 0.65},
#         {"category": "Gym", "item_name": "Punching Bag (hanging)", "average_volume": 0.19},
#         {"category": "Gym", "item_name": "Yoga Mat (rolled)", "average_volume": 0.028},
#         {"category": "Gym", "item_name": "Foam Roller", "average_volume": 0.010},
#         {"category": "Gym", "item_name": "Balance Ball / Swiss Ball", "average_volume": 0.27},

#         {"category": "Living Room", "item_name": "TV up to 45\"", "average_volume": 0.10},
#         {"category": "Living Room", "item_name": "TV up to 75\"", "average_volume": 0.20},
#         {"category": "Living Room", "item_name": "TV Stand", "average_volume": 0.30},
#         {"category": "Living Room", "item_name": "Desk Standard", "average_volume": 0.50},
#         {"category": "Living Room", "item_name": "Desk Large", "average_volume": 0.75},
#         {"category": "Living Room", "item_name": "Armchair", "average_volume": 1.00},
#         {"category": "Living Room", "item_name": "2 Seater Sofa", "average_volume": 1.50},
#         {"category": "Living Room", "item_name": "3 Seater Sofa", "average_volume": 2.00},
#         {"category": "Living Room", "item_name": "4 Seater Sofa", "average_volume": 2.50},
#         {"category": "Living Room", "item_name": "Corner Sofa", "average_volume": 3.50},
#         {"category": "Living Room", "item_name": "Cabinet Large", "average_volume": 1.00},
#         {"category": "Living Room", "item_name": "Bookcase Large", "average_volume": 0.80},
#         {"category": "Living Room", "item_name": "Grandfather Clock", "average_volume": 0.60},
#         {"category": "Living Room", "item_name": "Other Medium Item ", "average_volume": 0.50},
#         {"category": "Living Room", "item_name": "Other Large Item ", "average_volume": 1.00},
#         {"category": "Living Room", "item_name": "Dining Table 4 Seater", "average_volume": 1.00},
#         {"category": "Living Room", "item_name": "Dining Table 6 Seater", "average_volume": 1.50},
#         {"category": "Living Room", "item_name": "Dining Table 8 Seater", "average_volume": 2.00},
#         {"category": "Living Room", "item_name": "Dining Chair", "average_volume": 0.15},
#         {"category": "Living Room", "item_name": "Misc Chairs ", "average_volume": 0.25},
#         {"category": "Living Room", "item_name": "Sideboard ", "average_volume": 1.20},
#         {"category": "Living Room", "item_name": "Coffee Table", "average_volume": 0.30},
#         {"category": "Living Room", "item_name": "Cabinet Small", "average_volume": 0.40},
#         {"category": "Living Room", "item_name": "Bookcase Small ", "average_volume": 0.50},
#         {"category": "Living Room", "item_name": "Shelves Contents Only", "average_volume": 0.10},
#         {"category": "Living Room", "item_name": "Ornaments Fragile ", "average_volume": 0.10},
#         {"category": "Living Room", "item_name": "Plant Small ", "average_volume": 0.05},
#         {"category": "Living Room", "item_name": "Plant Tall ", "average_volume": 0.15},
#         {"category": "Living Room", "item_name": "Piano Upright", "average_volume": 2.00},
#         {"category": "Living Room", "item_name": "Boxes ", "average_volume": 0.07},
        
#         # Kitchen Items
#         {"category": "Kitchen", "item_name": "Fridge Under Counter", "average_volume": 0.40},
#         {"category": "Kitchen", "item_name": "Fridge Freezer Upright", "average_volume": 0.70},
#         {"category": "Kitchen", "item_name": "Fridge Freezer American", "average_volume": 1.20},
#         {"category": "Kitchen", "item_name": "Freezer Under Counter", "average_volume": 0.40},
#         {"category": "Kitchen", "item_name": "Freezer Chest", "average_volume": 0.80},
#         {"category": "Kitchen", "item_name": "Washing Machine", "average_volume": 0.60},
#         {"category": "Kitchen", "item_name": "Tumble Dryer", "average_volume": 0.60},
#         {"category": "Kitchen", "item_name": "Cooker Standard", "average_volume": 0.50},
#         {"category": "Kitchen", "item_name": "Dishwasher", "average_volume": 0.60},
#         {"category": "Kitchen", "item_name": "Other Medium Item ", "average_volume": 0.50},
#         {"category": "Kitchen", "item_name": "Other Large Item", "average_volume": 1.00},
#         {"category": "Kitchen", "item_name": "Dining Table 4 Seater", "average_volume": 1.00},
#         {"category": "Kitchen", "item_name": "Dining Table 6 Seater", "average_volume": 1.50},
#         {"category": "Kitchen", "item_name": "Dining Table 8 Seater", "average_volume": 2.00},
#         {"category": "Kitchen", "item_name": "Dining Chair", "average_volume": 0.15},
#         {"category": "Kitchen", "item_name": "Misc Chairs ", "average_volume": 0.25},
#         {"category": "Kitchen", "item_name": "Ornaments ", "average_volume": 0.10},
#         {"category": "Kitchen", "item_name": "Plant Small ", "average_volume": 0.05},
#         {"category": "Kitchen", "item_name": "Plant Tall ", "average_volume": 0.15},
#         {"category": "Kitchen", "item_name": "Kitchen Bin", "average_volume": 0.10},
#         {"category": "Kitchen", "item_name": "General Small Medium ", "average_volume": 0.20},
#         {"category": "Kitchen", "item_name": "Boxes", "average_volume": 0.07},
        
#         # Bathroom/Hallway Items
#         {"category": "Other / Bathroom / Hallway", "item_name": "Sideboard ", "average_volume": 1.20},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Other Medium ", "average_volume": 0.50},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Other Large ", "average_volume": 1.00},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Bookcase Large ", "average_volume": 0.80},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Exercise Bike Hallway", "average_volume": 0.80},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Piano Upright Hallway", "average_volume": 2.00},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Cross Trainer Hallway", "average_volume": 1.50},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Treadmill Hallway", "average_volume": 1.50},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Bookcase Small ", "average_volume": 0.50},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Ornaments ", "average_volume": 0.10},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Plant Small ", "average_volume": 0.05},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Plant Tall ", "average_volume": 0.15},
#         {"category": "Other / Bathroom / Hallway", "item_name": "General Small ", "average_volume": 0.20},
#         {"category": "Other / Bathroom / Hallway", "item_name": "Boxes ", "average_volume": 0.07},
        
#         # Garden/Garage Items
#         {"category": "Garden / Garage / Loft", "item_name": " Table", "average_volume": 0.80},
#         {"category": "Garden / Garage / Loft", "item_name": " Storage Box", "average_volume": 1.00},
#         {"category": "Garden / Garage / Loft", "item_name": "Other Medium ", "average_volume": 0.50},
#         {"category": "Garden / Garage / Loft", "item_name": "Other Large ", "average_volume": 1.00},
#         {"category": "Garden / Garage / Loft", "item_name": "Shelving Unit Large", "average_volume": 0.70},
#         {"category": "Garden / Garage / Loft", "item_name": "Exercise Bike ", "average_volume": 0.80},
#         {"category": "Garden / Garage / Loft", "item_name": "Cross Trainer ", "average_volume": 1.50},
#         {"category": "Garden / Garage / Loft", "item_name": "Treadmill ", "average_volume": 1.50},
#         {"category": "Garden / Garage / Loft", "item_name": "Lawnmower", "average_volume": 0.40},
#         {"category": "Garden / Garage / Loft", "item_name": "Fridge Freezer ", "average_volume": 0.70},
#         {"category": "Garden / Garage / Loft", "item_name": "Freezer Chest ", "average_volume": 0.80},
#         {"category": "Garden / Garage / Loft", "item_name": "BBQ Standard", "average_volume": 0.60},
#         {"category": "Garden / Garage / Loft", "item_name": " Tools Small", "average_volume": 0.10},
#         {"category": "Garden / Garage / Loft", "item_name": " Tools Large", "average_volume": 0.25},
#         {"category": "Garden / Garage / Loft", "item_name": "Bookcase Small ", "average_volume": 0.50},
#         {"category": "Garden / Garage / Loft", "item_name": " Ornaments", "average_volume": 0.15},
#         {"category": "Garden / Garage / Loft", "item_name": "Plant Small ", "average_volume": 0.05},
#         {"category": "Garden / Garage / Loft", "item_name": "Plant Tall ", "average_volume": 0.15},
#         {"category": "Garden / Garage / Loft", "item_name": "General Small ", "average_volume": 0.20},
#         {"category": "Garden / Garage / Loft", "item_name": " Shed Dismantled", "average_volume": 5.00},
#         {"category": "Garden / Garage / Loft", "item_name": "Boxes ", "average_volume": 0.07},
        
#         # Bedroom Items
#         {"category": "Bedroom", "item_name": "Single Bed", "average_volume": 1.00},
#         {"category": "Bedroom", "item_name": "Double Bed", "average_volume": 1.50},
#         {"category": "Bedroom", "item_name": "KingSize Bed", "average_volume": 2.00},
#         {"category": "Bedroom", "item_name": "Mattress Single", "average_volume": 0.60},
#         {"category": "Bedroom", "item_name": "Mattress Double", "average_volume": 0.80},
#         {"category": "Bedroom", "item_name": "Mattress KingSize", "average_volume": 1.00},
#         {"category": "Bedroom", "item_name": "Cot", "average_volume": 0.40},
#         {"category": "Bedroom", "item_name": "Bunk Bed", "average_volume": 2.50},
#         {"category": "Bedroom", "item_name": "Bedside Table", "average_volume": 0.30},
#         {"category": "Bedroom", "item_name": "TV 45 ", "average_volume": 0.10},
#         {"category": "Bedroom", "item_name": "TV 75 ", "average_volume": 0.20},
#         {"category": "Bedroom", "item_name": "Misc Chairs ", "average_volume": 0.25},
#         {"category": "Bedroom", "item_name": "Desk Standard ", "average_volume": 0.50},
#         {"category": "Bedroom", "item_name": "Desk Large ", "average_volume": 0.75},
#         {"category": "Bedroom", "item_name": "Chest Of 4 Drawers", "average_volume": 0.70},
#         {"category": "Bedroom", "item_name": "Chest Of 6 Drawers", "average_volume": 0.90},
#         {"category": "Bedroom", "item_name": "Chest Drawers Double", "average_volume": 1.20},
#         {"category": "Bedroom", "item_name": "Wardrobe Single", "average_volume": 1.00},
#         {"category": "Bedroom", "item_name": "Wardrobe Double", "average_volume": 1.50},
#         {"category": "Bedroom", "item_name": "Wardrobe Triple", "average_volume": 2.00},
#         {"category": "Bedroom", "item_name": "Wardrobe Quad", "average_volume": 2.50},
#         {"category": "Bedroom", "item_name": "Sideboard ", "average_volume": 1.20},
#         {"category": "Bedroom", "item_name": "Other Medium ", "average_volume": 0.50},
#         {"category": "Bedroom", "item_name": "Other Large ", "average_volume": 1.00},
#         {"category": "Bedroom", "item_name": "Bookcase Large ", "average_volume": 0.80},
#         {"category": "Bedroom", "item_name": "Bookcase Small ", "average_volume": 0.50},
#         {"category": "Bedroom", "item_name": "Suitcases", "average_volume": 0.20},
#         {"category": "Bedroom", "item_name": "Ornaments", "average_volume": 0.10},
#         {"category": "Bedroom", "item_name": "Other", "average_volume": 0.20},
#         {"category": "Bedroom", "item_name": "Boxes", "average_volume": 0.07},
#     ]
    
#     return bulk_upload(inventory_data)


# Replace the upload_all_inventory() function in inventory.py with this:

@frappe.whitelist()
def upload_all_inventory():
    """Upload all predefined inventory items - now supports duplicate names across categories"""
    
    inventory_data = [
        # Living Room
        {"category": "Living Room", "item_name": "TV up to 45\"", "average_volume": 0.1},
        {"category": "Living Room", "item_name": "TV up to 75\"", "average_volume": 0.2},
        {"category": "Living Room", "item_name": "TV Stand", "average_volume": 0.3},
        {"category": "Living Room", "item_name": "Desk Standard", "average_volume": 0.5},
        {"category": "Living Room", "item_name": "Desk Large", "average_volume": 0.75},
        {"category": "Living Room", "item_name": "Armchair", "average_volume": 1.0},
        {"category": "Living Room", "item_name": "2 Seater Sofa", "average_volume": 1.5},
        {"category": "Living Room", "item_name": "3 Seater Sofa", "average_volume": 2.0},
        {"category": "Living Room", "item_name": "4 Seater Sofa", "average_volume": 2.5},
        {"category": "Living Room", "item_name": "Corner Sofa", "average_volume": 3.5},
        {"category": "Living Room", "item_name": "Cabinet Large", "average_volume": 1.0},
        {"category": "Living Room", "item_name": "Bookcase Large", "average_volume": 0.8},
        {"category": "Living Room", "item_name": "Grandfather Clock", "average_volume": 0.6},
        {"category": "Living Room", "item_name": "Other Medium Item", "average_volume": 0.5},
        {"category": "Living Room", "item_name": "Other Large Item", "average_volume": 1.0},
        {"category": "Living Room", "item_name": "Dining Table 4 Seater", "average_volume": 1.0},
        {"category": "Living Room", "item_name": "Dining Table 6 Seater", "average_volume": 1.5},
        {"category": "Living Room", "item_name": "Dining Table 8 Seater", "average_volume": 2.0},
        {"category": "Living Room", "item_name": "Dining Chair", "average_volume": 0.15},
        {"category": "Living Room", "item_name": "Misc Chairs", "average_volume": 0.25},
        {"category": "Living Room", "item_name": "Sideboard", "average_volume": 1.2},
        {"category": "Living Room", "item_name": "Coffee Table", "average_volume": 0.3},
        {"category": "Living Room", "item_name": "Cabinet Small", "average_volume": 0.4},
        {"category": "Living Room", "item_name": "Bookcase Small", "average_volume": 0.5},
        {"category": "Living Room", "item_name": "Shelves Contents Only", "average_volume": 0.1},
        {"category": "Living Room", "item_name": "Ornaments Fragile", "average_volume": 0.1},
        {"category": "Living Room", "item_name": "Plant Small", "average_volume": 0.05},
        {"category": "Living Room", "item_name": "Plant Tall", "average_volume": 0.15},
        {"category": "Living Room", "item_name": "Piano Upright", "average_volume": 2.0},
        {"category": "Living Room", "item_name": "Boxes", "average_volume": 0.07},

        # Kitchen
        {"category": "Kitchen", "item_name": "Fridge Under Counter", "average_volume": 0.4},
        {"category": "Kitchen", "item_name": "Fridge Freezer Upright", "average_volume": 0.7},
        {"category": "Kitchen", "item_name": "Fridge Freezer American", "average_volume": 1.2},
        {"category": "Kitchen", "item_name": "Freezer Under Counter", "average_volume": 0.4},
        {"category": "Kitchen", "item_name": "Freezer Chest", "average_volume": 0.8},
        {"category": "Kitchen", "item_name": "Washing Machine", "average_volume": 0.6},
        {"category": "Kitchen", "item_name": "Tumble Dryer", "average_volume": 0.6},
        {"category": "Kitchen", "item_name": "Cooker Standard", "average_volume": 0.5},
        {"category": "Kitchen", "item_name": "Dishwasher", "average_volume": 0.6},
        {"category": "Kitchen", "item_name": "Other Medium Item", "average_volume": 0.5},
        {"category": "Kitchen", "item_name": "Other Large Item", "average_volume": 1.0},
        {"category": "Kitchen", "item_name": "Dining Table 4 Seater", "average_volume": 1.0},
        {"category": "Kitchen", "item_name": "Dining Table 6 Seater", "average_volume": 1.5},
        {"category": "Kitchen", "item_name": "Dining Table 8 Seater", "average_volume": 2.0},
        {"category": "Kitchen", "item_name": "Dining Chair", "average_volume": 0.15},
        {"category": "Kitchen", "item_name": "Misc Chairs", "average_volume": 0.25},
        {"category": "Kitchen", "item_name": "Ornaments", "average_volume": 0.1},
        {"category": "Kitchen", "item_name": "Plant Small", "average_volume": 0.05},
        {"category": "Kitchen", "item_name": "Plant Tall", "average_volume": 0.15},
        {"category": "Kitchen", "item_name": "Kitchen Bin", "average_volume": 0.1},
        {"category": "Kitchen", "item_name": "General Small Medium", "average_volume": 0.2},
        {"category": "Kitchen", "item_name": "Boxes", "average_volume": 0.07},

        # Bathroom/Hallway
        {"category": "Other / Bathroom / Hallway", "item_name": "Sideboard", "average_volume": 1.2},
        {"category": "Other / Bathroom / Hallway", "item_name": "Other Medium", "average_volume": 0.5},
        {"category": "Other / Bathroom / Hallway", "item_name": "Other Large", "average_volume": 1.0},
        {"category": "Other / Bathroom / Hallway", "item_name": "Bookcase Large", "average_volume": 0.8},
        {"category": "Other / Bathroom / Hallway", "item_name": "Exercise Bike", "average_volume": 0.8},
        {"category": "Other / Bathroom / Hallway", "item_name": "Piano Upright", "average_volume": 2.0},
        {"category": "Other / Bathroom / Hallway", "item_name": "Cross Trainer", "average_volume": 1.5},
        {"category": "Other / Bathroom / Hallway", "item_name": "Treadmill", "average_volume": 1.5},
        {"category": "Other / Bathroom / Hallway", "item_name": "Bookcase Small", "average_volume": 0.5},
        {"category": "Other / Bathroom / Hallway", "item_name": "Ornaments", "average_volume": 0.1},
        {"category": "Other / Bathroom / Hallway", "item_name": "Plant Small", "average_volume": 0.05},
        {"category": "Other / Bathroom / Hallway", "item_name": "Plant Tall", "average_volume": 0.15},
        {"category": "Other / Bathroom / Hallway", "item_name": "General Small", "average_volume": 0.2},
        {"category": "Other / Bathroom / Hallway", "item_name": "Boxes", "average_volume": 0.07},

        # Garden/Garage/Loft
        {"category": "Garden / Garage / Loft", "item_name": "Table", "average_volume": 0.8},
        {"category": "Garden / Garage / Loft", "item_name": "Storage Box", "average_volume": 1.0},
        {"category": "Garden / Garage / Loft", "item_name": "Other Medium", "average_volume": 0.5},
        {"category": "Garden / Garage / Loft", "item_name": "Other Large", "average_volume": 1.0},
        {"category": "Garden / Garage / Loft", "item_name": "Shelving Unit Large", "average_volume": 0.7},
        {"category": "Garden / Garage / Loft", "item_name": "Exercise Bike", "average_volume": 0.8},
        {"category": "Garden / Garage / Loft", "item_name": "Cross Trainer", "average_volume": 1.5},
        {"category": "Garden / Garage / Loft", "item_name": "Treadmill", "average_volume": 1.5},
        {"category": "Garden / Garage / Loft", "item_name": "Lawnmower", "average_volume": 0.4},
        {"category": "Garden / Garage / Loft", "item_name": "Fridge Freezer", "average_volume": 0.7},
        {"category": "Garden / Garage / Loft", "item_name": "Freezer Chest", "average_volume": 0.8},
        {"category": "Garden / Garage / Loft", "item_name": "BBQ Standard", "average_volume": 0.6},
        {"category": "Garden / Garage / Loft", "item_name": "Tools Small", "average_volume": 0.1},
        {"category": "Garden / Garage / Loft", "item_name": "Tools Large", "average_volume": 0.25},
        {"category": "Garden / Garage / Loft", "item_name": "Bookcase Small", "average_volume": 0.5},
        {"category": "Garden / Garage / Loft", "item_name": "Ornaments", "average_volume": 0.15},
        {"category": "Garden / Garage / Loft", "item_name": "Plant Small", "average_volume": 0.05},
        {"category": "Garden / Garage / Loft", "item_name": "Plant Tall", "average_volume": 0.15},
        {"category": "Garden / Garage / Loft", "item_name": "General Small", "average_volume": 0.2},
        {"category": "Garden / Garage / Loft", "item_name": "Shed Dismantled", "average_volume": 5.0},
        {"category": "Garden / Garage / Loft", "item_name": "Boxes", "average_volume": 0.07},

        # Bedroom
        {"category": "Bedroom", "item_name": "Single Bed", "average_volume": 1.0},
        {"category": "Bedroom", "item_name": "Double Bed", "average_volume": 1.5},
        {"category": "Bedroom", "item_name": "KingSize Bed", "average_volume": 2.0},
        {"category": "Bedroom", "item_name": "Mattress Single", "average_volume": 0.6},
        {"category": "Bedroom", "item_name": "Mattress Double", "average_volume": 0.8},
        {"category": "Bedroom", "item_name": "Mattress KingSize", "average_volume": 1.0},
        {"category": "Bedroom", "item_name": "Cot", "average_volume": 0.4},
        {"category": "Bedroom", "item_name": "Bunk Bed", "average_volume": 2.5},
        {"category": "Bedroom", "item_name": "Bedside Table", "average_volume": 0.3},
        {"category": "Bedroom", "item_name": "TV 45\"", "average_volume": 0.1},
        {"category": "Bedroom", "item_name": "TV 75\"", "average_volume": 0.2},
        {"category": "Bedroom", "item_name": "Misc Chairs", "average_volume": 0.25},
        {"category": "Bedroom", "item_name": "Desk Standard", "average_volume": 0.5},
        {"category": "Bedroom", "item_name": "Desk Large", "average_volume": 0.75},
        {"category": "Bedroom", "item_name": "Chest Of 4 Drawers", "average_volume": 0.7},
        {"category": "Bedroom", "item_name": "Chest Of 6 Drawers", "average_volume": 0.9},
        {"category": "Bedroom", "item_name": "Chest Drawers Double", "average_volume": 1.2},
        {"category": "Bedroom", "item_name": "Wardrobe Single", "average_volume": 1.0},
        {"category": "Bedroom", "item_name": "Wardrobe Double", "average_volume": 1.5},
        {"category": "Bedroom", "item_name": "Wardrobe Triple", "average_volume": 2.0},
        {"category": "Bedroom", "item_name": "Wardrobe Quad", "average_volume": 2.5},
        {"category": "Bedroom", "item_name": "Sideboard", "average_volume": 1.2},
        {"category": "Bedroom", "item_name": "Other Medium", "average_volume": 0.5},
        {"category": "Bedroom", "item_name": "Other Large", "average_volume": 1.0},
        {"category": "Bedroom", "item_name": "Bookcase Large", "average_volume": 0.8},
        {"category": "Bedroom", "item_name": "Bookcase Small", "average_volume": 0.5},
        {"category": "Bedroom", "item_name": "Suitcases", "average_volume": 0.2},
        {"category": "Bedroom", "item_name": "Ornaments", "average_volume": 0.1},
        {"category": "Bedroom", "item_name": "Other", "average_volume": 0.2},
        {"category": "Bedroom", "item_name": "Boxes", "average_volume": 0.07},
        
        # Office
        {"category": "Office", "item_name": "Standing Desk (adjustable)", "average_volume": 1.18},
        {"category": "Office", "item_name": "Corner Desk (L-shape)", "average_volume": 1.44},
        {"category": "Office", "item_name": "Reception Desk (small)", "average_volume": 0.79},
        {"category": "Office", "item_name": "Reception Desk (large counter)", "average_volume": 1.94},
        {"category": "Office", "item_name": "Coffee Table (round)", "average_volume": 0.2},
        {"category": "Office", "item_name": "Side Table", "average_volume": 0.12},
        {"category": "Office", "item_name": "Training Table (folding)", "average_volume": 0.41},
        {"category": "Office", "item_name": "High Bar Table", "average_volume": 0.4},
        {"category": "Office", "item_name": "Ergonomic Chair", "average_volume": 0.59},
        {"category": "Office", "item_name": "Conference Chair (stackable)", "average_volume": 0.23},
        {"category": "Office", "item_name": "Bar Stool", "average_volume": 0.22},
        {"category": "Office", "item_name": "Reception Waiting Chair", "average_volume": 0.41},
        {"category": "Office", "item_name": "Lounge Armchair", "average_volume": 0.65},
        {"category": "Office", "item_name": "Bean Bag", "average_volume": 0.34},
        {"category": "Office", "item_name": "Metal Storage Locker", "average_volume": 0.31},
        {"category": "Office", "item_name": "Large Metal Cabinet (2-door)", "average_volume": 0.73},
        {"category": "Office", "item_name": "Mobile Pedestal (wheels)", "average_volume": 0.12},
        {"category": "Office", "item_name": "Compact Rolling File Rack", "average_volume": 0.61},
        {"category": "Office", "item_name": "Open Shelf Unit (wide)", "average_volume": 0.84},
        {"category": "Office", "item_name": "Desk Hutch", "average_volume": 0.3},
        {"category": "Office", "item_name": "Document Sorter (multi-level)", "average_volume": 0.05},
        {"category": "Office", "item_name": "Laptop (boxed)", "average_volume": 0.01},
        {"category": "Office", "item_name": "Dual Monitor Arm", "average_volume": 0.04},
        {"category": "Office", "item_name": "UPS Battery Unit", "average_volume": 0.03},
        {"category": "Office", "item_name": "Server (rack-mounted)", "average_volume": 0.09},
        {"category": "Office", "item_name": "Desk Phone", "average_volume": 0.005},
        {"category": "Office", "item_name": "Projector", "average_volume": 0.0075},
        {"category": "Office", "item_name": "Projector Screen (rolled)", "average_volume": 0.03},
        {"category": "Office", "item_name": "Router / Switch (boxed)", "average_volume": 0.006},
        {"category": "Office", "item_name": "Large Whiteboard", "average_volume": 0.108},
        {"category": "Office", "item_name": "Corkboard", "average_volume": 0.054},
        {"category": "Office", "item_name": "Wall Clock", "average_volume": 0.009},
        {"category": "Office", "item_name": "Artificial Plant (tall)", "average_volume": 0.24},
        {"category": "Office", "item_name": "Plant (medium pot)", "average_volume": 0.04},
        {"category": "Office", "item_name": "Coat Stand", "average_volume": 0.45},
        {"category": "Office", "item_name": "Floor Lamp", "average_volume": 0.14},
        {"category": "Office", "item_name": "Fridge (under-counter)", "average_volume": 0.26},
        {"category": "Office", "item_name": "Full-Size Fridge", "average_volume": 0.88},
        {"category": "Office", "item_name": "Microwave", "average_volume": 0.04},
        {"category": "Office", "item_name": "Kettle (boxed)", "average_volume": 0.02},
        {"category": "Office", "item_name": "Water Cooler Dispenser", "average_volume": 0.12},
        {"category": "Office", "item_name": "Dining Table", "average_volume": 0.84},
        {"category": "Office", "item_name": "Dining Chair", "average_volume": 0.18},
        {"category": "Office", "item_name": "Small Moving Box (Books / Tools)", "average_volume": 0.036},
        {"category": "Office", "item_name": "Medium Moving Box (General Use)", "average_volume": 0.097},
        {"category": "Office", "item_name": "Large Moving Box (Bulky Items)", "average_volume": 0.129},
        {"category": "Office", "item_name": "Extra-Large Moving Box", "average_volume": 0.226},
        {"category": "Office", "item_name": "Archive Document Box (A4 Files)", "average_volume": 0.032},
        {"category": "Office", "item_name": "Heavy-Duty Crate (Plastic, Stackable)", "average_volume": 0.072},
        {"category": "Office", "item_name": "Industrial Crate (Large Plastic Tote)", "average_volume": 0.14},
        {"category": "Office", "item_name": "IT Equipment Crate (Padded)", "average_volume": 0.24},
        {"category": "Office", "item_name": "File Storage Crate (Long)", "average_volume": 0.126},
        {"category": "Office", "item_name": "Wardrobe Box (with hanging rail)", "average_volume": 0.33},
        {"category": "Office", "item_name": "Pallet Crate (Wooden)", "average_volume": 1.2},
        {"category": "Office", "item_name": "Euro Pallet Box (Large Foldable)", "average_volume": 0.96},
        {"category": "Office", "item_name": "Half-Size Pallet Box", "average_volume": 0.288},
        {"category": "Office", "item_name": "Shredder (small)", "average_volume": 0.04},
        {"category": "Office", "item_name": "Shredder (large)", "average_volume": 0.18},
        {"category": "Office", "item_name": "Cardboard Archive Box", "average_volume": 0.03},
        {"category": "Office", "item_name": "Coat Hanger Rail", "average_volume": 0.75},
        {"category": "Office", "item_name": "Cleaning Cart", "average_volume": 0.45},
        {"category": "Office", "item_name": "Vacuum Cleaner", "average_volume": 0.14},
        {"category": "Office", "item_name": "Portable Partition Panel", "average_volume": 0.135},
        {"category": "Office", "item_name": "Mobile Whiteboard (on wheels)", "average_volume": 1.4},
        
        # Gym
        {"category": "Gym", "item_name": "Treadmill (commercial)", "average_volume": 2.7},
        {"category": "Gym", "item_name": "Elliptical Trainer", "average_volume": 2.86},
        {"category": "Gym", "item_name": "Spin Bike", "average_volume": 0.94},
        {"category": "Gym", "item_name": "Upright Exercise Bike", "average_volume": 0.72},
        {"category": "Gym", "item_name": "Rowing Machine", "average_volume": 0.83},
        {"category": "Gym", "item_name": "Stair Climber / Step Machine", "average_volume": 2.46},
        {"category": "Gym", "item_name": "Smith Machine", "average_volume": 6.0},
        {"category": "Gym", "item_name": "Cable Crossover", "average_volume": 0.7},
        {"category": "Gym", "item_name": "Lat Pulldown Machine", "average_volume": 3.96},
        {"category": "Gym", "item_name": "Seated Row Machine", "average_volume": 2.64},
        {"category": "Gym", "item_name": "Chest Press Machine", "average_volume": 2.52},
        {"category": "Gym", "item_name": "Leg Press (45°)", "average_volume": 3.28},
        {"category": "Gym", "item_name": "Leg Extension / Curl Combo", "average_volume": 1.96},
        {"category": "Gym", "item_name": "Dumbbell Rack (2-tier)", "average_volume": 1.2},
        {"category": "Gym", "item_name": "Dumbbell Set (pair, average footprint)", "average_volume": 0.025},
        {"category": "Gym", "item_name": "Barbell Rack", "average_volume": 1.44},
        {"category": "Gym", "item_name": "Weight Plates (stacked, 100kg set)", "average_volume": 0.11},
        {"category": "Gym", "item_name": "Incline Bench", "average_volume": 1.01},
        {"category": "Gym", "item_name": "Flat Bench", "average_volume": 0.32},
        {"category": "Gym", "item_name": "Adjustable Bench (folding)", "average_volume": 0.39},
        {"category": "Gym", "item_name": "Power Rack / Squat Rack", "average_volume": 0.5},
        {"category": "Gym", "item_name": "Kettlebell (each, typical 12–20kg)", "average_volume": 0.019},
        {"category": "Gym", "item_name": "Medicine Ball", "average_volume": 0.043},
        {"category": "Gym", "item_name": "Plyometric Box (large)", "average_volume": 0.34},
        {"category": "Gym", "item_name": "Punching Bag (standing)", "average_volume": 0.65},
        {"category": "Gym", "item_name": "Punching Bag (hanging)", "average_volume": 0.19},
        {"category": "Gym", "item_name": "Yoga Mat (rolled)", "average_volume": 0.028},
        {"category": "Gym", "item_name": "Foam Roller", "average_volume": 0.01},
        {"category": "Gym", "item_name": "Balance Ball / Swiss Ball", "average_volume": 0.27},
    ]
    
    return bulk_upload(inventory_data)

@frappe.whitelist()
def calculate_move_cost(items):
    """
    Calculate total cost for a move
    items format: {"item_name": quantity, "item_name2": quantity2}
    """
    try:
        import json
        if isinstance(items, str):
            items = json.loads(items)
        
        total_volume = 0
        item_details = []
        
        for item_name, quantity in items.items():
            item = frappe.get_doc("Moving Inventory Item", item_name)
            volume = item.average_volume * int(quantity)
            total_volume += volume
            
            item_details.append({
                "item_name": item_name,
                "quantity": quantity,
                "volume_per_item": item.average_volume,
                "total_volume": volume
            })
        
        # Fixed rates
        dismantle_rate = 25
        assembly_rate = 50
        
        return {
            "success": True,
            "total_volume": round(total_volume, 2),
            "dismantle_cost": round(total_volume * dismantle_rate, 2),
            "assembly_cost": round(total_volume * assembly_rate, 2),
            "total_cost": round(total_volume * (dismantle_rate + assembly_rate), 2),
            "item_details": item_details
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }
    
@frappe.whitelist()
def migrate_inventory_items():
    """
    Migrate existing inventory items to new naming structure.
    This will delete all existing items and re-upload with composite keys.
    """
    try:
        if not check_admin_permission():
            return {'success': False, 'message': 'Access Denied'}
        
        # Step 1: Delete all existing items
        existing_items = frappe.get_all("Moving Inventory Item", pluck="name")
        for item_name in existing_items:
            frappe.delete_doc("Moving Inventory Item", item_name, force=True, ignore_permissions=True)
        
        frappe.db.commit()
        
        # Step 2: Upload all items with new naming
        result = upload_all_inventory()
        
        return {
            'success': True,
            'message': f'Migration complete. Deleted {len(existing_items)} old items.',
            'upload_result': result
        }
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(f"Migration Error: {str(e)}")
        return {'success': False, 'message': str(e)}