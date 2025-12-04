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


@frappe.whitelist()
def upload_all_inventory():
    """Upload all 118 predefined inventory items"""
    
    inventory_data = [
        # Living Room Items
        {"category": "Living Room", "item_name": "TV up to 45\"", "average_volume": 0.10},
        {"category": "Living Room", "item_name": "TV up to 75\"", "average_volume": 0.20},
        {"category": "Living Room", "item_name": "TV Stand", "average_volume": 0.30},
        {"category": "Living Room", "item_name": "Desk Standard", "average_volume": 0.50},
        {"category": "Living Room", "item_name": "Desk Large", "average_volume": 0.75},
        {"category": "Living Room", "item_name": "Armchair", "average_volume": 1.00},
        {"category": "Living Room", "item_name": "2 Seater Sofa", "average_volume": 1.50},
        {"category": "Living Room", "item_name": "3 Seater Sofa", "average_volume": 2.00},
        {"category": "Living Room", "item_name": "4 Seater Sofa", "average_volume": 2.50},
        {"category": "Living Room", "item_name": "Corner Sofa", "average_volume": 3.50},
        {"category": "Living Room", "item_name": "Cabinet Large", "average_volume": 1.00},
        {"category": "Living Room", "item_name": "Bookcase Large", "average_volume": 0.80},
        {"category": "Living Room", "item_name": "Grandfather Clock", "average_volume": 0.60},
        {"category": "Living Room", "item_name": "Other Medium Item LR", "average_volume": 0.50},
        {"category": "Living Room", "item_name": "Other Large Item LR", "average_volume": 1.00},
        {"category": "Living Room", "item_name": "Dining Table 4 Seater", "average_volume": 1.00},
        {"category": "Living Room", "item_name": "Dining Table 6 Seater", "average_volume": 1.50},
        {"category": "Living Room", "item_name": "Dining Table 8 Seater", "average_volume": 2.00},
        {"category": "Living Room", "item_name": "Dining Chair", "average_volume": 0.15},
        {"category": "Living Room", "item_name": "Misc Chairs LR", "average_volume": 0.25},
        {"category": "Living Room", "item_name": "Sideboard LR", "average_volume": 1.20},
        {"category": "Living Room", "item_name": "Coffee Table", "average_volume": 0.30},
        {"category": "Living Room", "item_name": "Cabinet Small", "average_volume": 0.40},
        {"category": "Living Room", "item_name": "Bookcase Small LR", "average_volume": 0.50},
        {"category": "Living Room", "item_name": "Shelves Contents Only", "average_volume": 0.10},
        {"category": "Living Room", "item_name": "Ornaments Fragile LR", "average_volume": 0.10},
        {"category": "Living Room", "item_name": "Plant Small LR", "average_volume": 0.05},
        {"category": "Living Room", "item_name": "Plant Tall LR", "average_volume": 0.15},
        {"category": "Living Room", "item_name": "Piano Upright", "average_volume": 2.00},
        {"category": "Living Room", "item_name": "Boxes LR", "average_volume": 0.07},
        
        # Kitchen Items
        {"category": "Kitchen", "item_name": "Fridge Under Counter", "average_volume": 0.40},
        {"category": "Kitchen", "item_name": "Fridge Freezer Upright", "average_volume": 0.70},
        {"category": "Kitchen", "item_name": "Fridge Freezer American", "average_volume": 1.20},
        {"category": "Kitchen", "item_name": "Freezer Under Counter", "average_volume": 0.40},
        {"category": "Kitchen", "item_name": "Freezer Chest", "average_volume": 0.80},
        {"category": "Kitchen", "item_name": "Washing Machine", "average_volume": 0.60},
        {"category": "Kitchen", "item_name": "Tumble Dryer", "average_volume": 0.60},
        {"category": "Kitchen", "item_name": "Cooker Standard", "average_volume": 0.50},
        {"category": "Kitchen", "item_name": "Dishwasher", "average_volume": 0.60},
        {"category": "Kitchen", "item_name": "Other Medium Item Kitchen", "average_volume": 0.50},
        {"category": "Kitchen", "item_name": "Other Large Item Kitchen", "average_volume": 1.00},
        {"category": "Kitchen", "item_name": "Kitchen Dining Table 4 Seater", "average_volume": 1.00},
        {"category": "Kitchen", "item_name": "Kitchen Dining Table 6 Seater", "average_volume": 1.50},
        {"category": "Kitchen", "item_name": "Kitchen Dining Table 8 Seater", "average_volume": 2.00},
        {"category": "Kitchen", "item_name": "Kitchen Dining Chair", "average_volume": 0.15},
        {"category": "Kitchen", "item_name": "Misc Chairs Kitchen", "average_volume": 0.25},
        {"category": "Kitchen", "item_name": "Ornaments Kitchen", "average_volume": 0.10},
        {"category": "Kitchen", "item_name": "Plant Small Kitchen", "average_volume": 0.05},
        {"category": "Kitchen", "item_name": "Plant Tall Kitchen", "average_volume": 0.15},
        {"category": "Kitchen", "item_name": "Kitchen Bin", "average_volume": 0.10},
        {"category": "Kitchen", "item_name": "General Small Medium Kitchen", "average_volume": 0.20},
        {"category": "Kitchen", "item_name": "Boxes Kitchen", "average_volume": 0.07},
        
        # Bathroom/Hallway Items
        {"category": "Other / Bathroom / Hallway", "item_name": "Sideboard Bathroom", "average_volume": 1.20},
        {"category": "Other / Bathroom / Hallway", "item_name": "Other Medium Bathroom", "average_volume": 0.50},
        {"category": "Other / Bathroom / Hallway", "item_name": "Other Large Bathroom", "average_volume": 1.00},
        {"category": "Other / Bathroom / Hallway", "item_name": "Bookcase Large Bathroom", "average_volume": 0.80},
        {"category": "Other / Bathroom / Hallway", "item_name": "Exercise Bike Hallway", "average_volume": 0.80},
        {"category": "Other / Bathroom / Hallway", "item_name": "Piano Upright Hallway", "average_volume": 2.00},
        {"category": "Other / Bathroom / Hallway", "item_name": "Cross Trainer Hallway", "average_volume": 1.50},
        {"category": "Other / Bathroom / Hallway", "item_name": "Treadmill Hallway", "average_volume": 1.50},
        {"category": "Other / Bathroom / Hallway", "item_name": "Bookcase Small Bathroom", "average_volume": 0.50},
        {"category": "Other / Bathroom / Hallway", "item_name": "Ornaments Bathroom", "average_volume": 0.10},
        {"category": "Other / Bathroom / Hallway", "item_name": "Plant Small Bathroom", "average_volume": 0.05},
        {"category": "Other / Bathroom / Hallway", "item_name": "Plant Tall Bathroom", "average_volume": 0.15},
        {"category": "Other / Bathroom / Hallway", "item_name": "General Small Bathroom", "average_volume": 0.20},
        {"category": "Other / Bathroom / Hallway", "item_name": "Boxes Bathroom", "average_volume": 0.07},
        
        # Garden/Garage Items
        {"category": "Garden / Garage / Loft", "item_name": "Garden Table", "average_volume": 0.80},
        {"category": "Garden / Garage / Loft", "item_name": "Garden Storage Box", "average_volume": 1.00},
        {"category": "Garden / Garage / Loft", "item_name": "Other Medium Garden", "average_volume": 0.50},
        {"category": "Garden / Garage / Loft", "item_name": "Other Large Garden", "average_volume": 1.00},
        {"category": "Garden / Garage / Loft", "item_name": "Shelving Unit Large", "average_volume": 0.70},
        {"category": "Garden / Garage / Loft", "item_name": "Exercise Bike Garden", "average_volume": 0.80},
        {"category": "Garden / Garage / Loft", "item_name": "Cross Trainer Garden", "average_volume": 1.50},
        {"category": "Garden / Garage / Loft", "item_name": "Treadmill Garden", "average_volume": 1.50},
        {"category": "Garden / Garage / Loft", "item_name": "Lawnmower", "average_volume": 0.40},
        {"category": "Garden / Garage / Loft", "item_name": "Fridge Freezer Garden", "average_volume": 0.70},
        {"category": "Garden / Garage / Loft", "item_name": "Freezer Chest Garden", "average_volume": 0.80},
        {"category": "Garden / Garage / Loft", "item_name": "BBQ Standard", "average_volume": 0.60},
        {"category": "Garden / Garage / Loft", "item_name": "Garden Tools Small", "average_volume": 0.10},
        {"category": "Garden / Garage / Loft", "item_name": "Garden Tools Large", "average_volume": 0.25},
        {"category": "Garden / Garage / Loft", "item_name": "Bookcase Small Garden", "average_volume": 0.50},
        {"category": "Garden / Garage / Loft", "item_name": "Garden Ornaments", "average_volume": 0.15},
        {"category": "Garden / Garage / Loft", "item_name": "Plant Small Garden", "average_volume": 0.05},
        {"category": "Garden / Garage / Loft", "item_name": "Plant Tall Garden", "average_volume": 0.15},
        {"category": "Garden / Garage / Loft", "item_name": "General Small Garden", "average_volume": 0.20},
        {"category": "Garden / Garage / Loft", "item_name": "Garden Shed Dismantled", "average_volume": 5.00},
        {"category": "Garden / Garage / Loft", "item_name": "Boxes Garden", "average_volume": 0.07},
        
        # Bedroom Items
        {"category": "Bedroom", "item_name": "Single Bed", "average_volume": 1.00},
        {"category": "Bedroom", "item_name": "Double Bed", "average_volume": 1.50},
        {"category": "Bedroom", "item_name": "KingSize Bed", "average_volume": 2.00},
        {"category": "Bedroom", "item_name": "Mattress Single", "average_volume": 0.60},
        {"category": "Bedroom", "item_name": "Mattress Double", "average_volume": 0.80},
        {"category": "Bedroom", "item_name": "Mattress KingSize", "average_volume": 1.00},
        {"category": "Bedroom", "item_name": "Cot", "average_volume": 0.40},
        {"category": "Bedroom", "item_name": "Bunk Bed", "average_volume": 2.50},
        {"category": "Bedroom", "item_name": "Bedside Table", "average_volume": 0.30},
        {"category": "Bedroom", "item_name": "TV 45 Bedroom", "average_volume": 0.10},
        {"category": "Bedroom", "item_name": "TV 75 Bedroom", "average_volume": 0.20},
        {"category": "Bedroom", "item_name": "Misc Chairs Bedroom", "average_volume": 0.25},
        {"category": "Bedroom", "item_name": "Desk Standard Bedroom", "average_volume": 0.50},
        {"category": "Bedroom", "item_name": "Desk Large Bedroom", "average_volume": 0.75},
        {"category": "Bedroom", "item_name": "Chest Of 4 Drawers", "average_volume": 0.70},
        {"category": "Bedroom", "item_name": "Chest Of 6 Drawers", "average_volume": 0.90},
        {"category": "Bedroom", "item_name": "Chest Drawers Double", "average_volume": 1.20},
        {"category": "Bedroom", "item_name": "Wardrobe Single", "average_volume": 1.00},
        {"category": "Bedroom", "item_name": "Wardrobe Double", "average_volume": 1.50},
        {"category": "Bedroom", "item_name": "Wardrobe Triple", "average_volume": 2.00},
        {"category": "Bedroom", "item_name": "Wardrobe Quad", "average_volume": 2.50},
        {"category": "Bedroom", "item_name": "Sideboard Bedroom", "average_volume": 1.20},
        {"category": "Bedroom", "item_name": "Other Medium Bedroom", "average_volume": 0.50},
        {"category": "Bedroom", "item_name": "Other Large Bedroom", "average_volume": 1.00},
        {"category": "Bedroom", "item_name": "Bookcase Large Bedroom", "average_volume": 0.80},
        {"category": "Bedroom", "item_name": "Bookcase Small Bedroom", "average_volume": 0.50},
        {"category": "Bedroom", "item_name": "Suitcases", "average_volume": 0.20},
        {"category": "Bedroom", "item_name": "Ornaments Bedroom", "average_volume": 0.10},
        {"category": "Bedroom", "item_name": "Other Bedroom", "average_volume": 0.20},
        {"category": "Bedroom", "item_name": "Boxes Bedroom", "average_volume": 0.07},
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