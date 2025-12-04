import frappe
from frappe.model.document import Document
from datetime import datetime
import json

class LogisticsCompany(Document):
    
    def before_insert(self):
        """Set created timestamp"""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def before_save(self):
        """Auto-calculate fields before saving"""
        self.updated_at = datetime.now()
        
        # Auto-calculate total carrying capacity (quantity × fixed capacity)
        self.total_carrying_capacity = self.calculate_total_capacity()
        
        # Auto-calculate dismantling cost (50% of assembly cost) if not provided
        if self.assembly_cost_per_item and self.assembly_cost_per_item > 0:
            if not self.disassembly_cost_per_item or self.disassembly_cost_per_item == 0:
                self.disassembly_cost_per_item = round(self.assembly_cost_per_item * 0.5, 2)
    
    def validate(self):
        """Validate company data"""
        # Validate manager is a Logistics Manager
        if self.manager_email:
            if not frappe.db.exists("LocalMoves User", self.manager_email):
                frappe.throw("Manager email does not exist in LocalMoves Users")
            
            user = frappe.get_doc("LocalMoves User", self.manager_email)
            if user.role != "Logistics Manager":
                frappe.throw("Manager must have 'Logistics Manager' role")
        
        # Validate phone number format
        if self.phone:
            self.validate_phone_number()
        
        # Validate pincode format
        if self.pincode:
            self.validate_pincode()
        
        # Ensure at least one vehicle if company is active
        if self.is_active and self.total_carrying_capacity == 0:
            frappe.msgprint("Warning: Company is active but has no vehicles in fleet", 
                          indicator='orange', alert=True)
        
        # Validate pricing fields are non-negative
        self.validate_pricing()
        
        # Validate JSON array fields
        self.validate_json_fields()
    
    def calculate_total_capacity(self):
        """Calculate total carrying capacity: sum of (quantity × fixed capacity)"""
        # FIXED capacities per vehicle type (in m³)
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
            quantity = getattr(self, field, 0) or 0
            total_capacity += capacity_per_vehicle * quantity
        
        return float(total_capacity)
    
    def validate_phone_number(self):
        """Basic phone number validation"""
        phone = str(self.phone).strip()
        phone_digits = ''.join(filter(str.isdigit, phone))
        
        if len(phone_digits) < 10:
            frappe.throw("Phone number must contain at least 10 digits")
    
    def validate_pincode(self):
        """Validate pincode format"""
        pincode = str(self.pincode).strip().upper()
        pincode_no_space = pincode.replace(" ", "")
        
        if len(pincode_no_space) < 4:
            frappe.throw("Invalid pincode format")
        
        self.pincode = pincode
    
    def validate_pricing(self):
        """Ensure pricing fields are non-negative"""
        pricing_fields = [
            'loading_cost_per_m3',
            'packing_cost_per_box',
            'assembly_cost_per_item',
            'disassembly_cost_per_item',
            'cost_per_mile_under_25',
            'cost_per_mile_over_25'
        ]
        
        for field in pricing_fields:
            value = getattr(self, field, 0) or 0
            if value < 0:
                frappe.throw(f"{field.replace('_', ' ').title()} cannot be negative")
    
    def validate_json_fields(self):
        """Validate and ensure JSON array fields are properly formatted"""
        json_array_fields = [
            'areas_covered',
            'company_gallery',
            'includes',
            'material',
            'protection',
            'furniture',
            'appliances',
            'swb_van_images', 'mwb_van_images', 'lwb_van_images', 'xlwb_van_images',
            'mwb_luton_van_images', 'lwb_luton_van_images', 'tonne_7_5_lorry_images',
            'tonne_12_lorry_images', 'tonne_18_lorry_images'
        ]
        
        for field in json_array_fields:
            value = getattr(self, field, None)
            
            if not value:
                setattr(self, field, "[]")
                continue
            
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if not isinstance(parsed, list):
                        frappe.throw(f"{field} must be a JSON array")
                except json.JSONDecodeError:
                    frappe.throw(f"{field} contains invalid JSON")
            
            elif isinstance(value, list):
                setattr(self, field, json.dumps(value))
            
            else:
                frappe.throw(f"{field} must be a JSON array or list")
    
    def get_fleet_summary(self):
        """Return a summary of the fleet with vehicle types and quantities"""
        vehicle_info = {
            'swb_van_quantity': {'name': 'SWB Van', 'capacity': 5},
            'mwb_van_quantity': {'name': 'MWB Van', 'capacity': 8},
            'lwb_van_quantity': {'name': 'LWB Van', 'capacity': 11},
            'xlwb_van_quantity': {'name': 'XLWB Van', 'capacity': 13},
            'mwb_luton_van_quantity': {'name': 'MWB Luton Van', 'capacity': 17},
            'lwb_luton_van_quantity': {'name': 'LWB Luton Van', 'capacity': 19},
            'tonne_7_5_lorry_quantity': {'name': '7.5 Tonne Lorry', 'capacity': 30},
            'tonne_12_lorry_quantity': {'name': '12 Tonne Lorry', 'capacity': 45},
            'tonne_18_lorry_quantity': {'name': '18 Tonne Lorry', 'capacity': 55}
        }
        
        fleet_summary = []
        for field, info in vehicle_info.items():
            quantity = getattr(self, field, 0) or 0
            if quantity > 0:
                fleet_summary.append({
                    'vehicle_type': info['name'],
                    'quantity': quantity,
                    'capacity_per_vehicle': info['capacity'],
                    'total_capacity': quantity * info['capacity'],
                    'images': self.get_vehicle_images(field)
                })
        
        return fleet_summary
    
    def get_vehicle_images(self, vehicle_field):
        """Parse and return vehicle images for a specific vehicle type"""
        image_field = vehicle_field.replace('_quantity', '_images')
        images_json = getattr(self, image_field, None)
        
        if not images_json:
            return []
        
        try:
            if isinstance(images_json, str):
                return json.loads(images_json)
            elif isinstance(images_json, list):
                return images_json
        except:
            return []
        
        return []
    
    def get_all_areas_covered(self):
        """Return list of all pincodes covered (including primary)"""
        areas = [self.pincode] if self.pincode else []
        
        if self.areas_covered:
            try:
                if isinstance(self.areas_covered, str):
                    areas_list = json.loads(self.areas_covered)
                elif isinstance(self.areas_covered, list):
                    areas_list = self.areas_covered
                else:
                    areas_list = []
                
                for pincode in areas_list:
                    if pincode and pincode not in areas:
                        areas.append(pincode)
            except:
                pass
        
        return areas
    
    def get_company_gallery(self):
        """Return parsed company gallery array"""
        if not self.company_gallery:
            return []
        
        try:
            if isinstance(self.company_gallery, str):
                return json.loads(self.company_gallery)
            elif isinstance(self.company_gallery, list):
                return self.company_gallery
        except:
            return []
        
        return []
    
    def get_pricing_summary(self):
        """Return a summary of all pricing information"""
        return {
            'loading_cost_per_m3': self.loading_cost_per_m3 or 0,
            'packing_cost_per_box': self.packing_cost_per_box or 0,
            'assembly_cost_per_item': self.assembly_cost_per_item or 0,
            'disassembly_cost_per_item': self.disassembly_cost_per_item or 0,
            'cost_per_mile_under_25': self.cost_per_mile_under_25 or 0,
            'cost_per_mile_over_25': self.cost_per_mile_over_25 or 0
        }
    
    def reset_monthly_request_counter(self):
        """Reset the monthly request view counter"""
        self.requests_viewed_this_month = 0
        self.save(ignore_permissions=True)
        frappe.db.commit()
    
    def increment_request_view(self):
        """Increment the request view counter"""
        self.requests_viewed_this_month = (self.requests_viewed_this_month or 0) + 1
        self.save(ignore_permissions=True)
        frappe.db.commit()
    
    def can_view_more_requests(self):
        """Check if company can view more requests based on subscription plan"""
        plan_limits = {
            'Free': 10,
            'Basic': 50,
            'Standard': 200,
            'Premium': -1  # Unlimited
        }
        
        limit = plan_limits.get(self.subscription_plan, 0)
        
        if limit == -1:
            return True
        
        return (self.requests_viewed_this_month or 0) < limit
    
    def get_remaining_requests(self):
        """Get remaining request views for current month"""
        plan_limits = {
            'Free': 10,
            'Basic': 50,
            'Standard': 200,
            'Premium': -1
        }
        
        limit = plan_limits.get(self.subscription_plan, 0)
        
        if limit == -1:
            return "Unlimited"
        
        viewed = self.requests_viewed_this_month or 0
        remaining = max(0, limit - viewed)
        
        return remaining
    
    def is_subscription_active(self):
        """Check if subscription is currently active"""
        if not self.subscription_end_date:
            return self.subscription_plan == "Free"
        
        from datetime import date
        return date.today() <= self.subscription_end_date
    
    def on_update(self):
        """After update hook"""
        if self.has_value_changed('is_active'):
            status = "activated" if self.is_active else "deactivated"
            frappe.logger().info(f"Company {self.company_name} has been {status}")
        
        if self.has_value_changed('subscription_plan'):
            frappe.logger().info(
                f"Company {self.company_name} subscription changed to {self.subscription_plan}"
            )
    
    def on_trash(self):
        """Before delete hook"""
        frappe.logger().info(f"Company {self.company_name} is being deleted")


# ==================== Scheduled Task ====================

def reset_all_monthly_counters():
    """Reset monthly request view counters - runs on 1st of every month"""
    try:
        companies = frappe.get_all("Logistics Company", 
                                   filters={"is_active": 1},
                                   pluck="name")
        
        for company_name in companies:
            company = frappe.get_doc("Logistics Company", company_name)
            company.requests_viewed_this_month = 0
            company.save(ignore_permissions=True)
        
        frappe.db.commit()
        frappe.logger().info(f"Reset monthly counters for {len(companies)} companies")
        
    except Exception as e:
        frappe.log_error(f"Error resetting monthly counters: {str(e)}", 
                        "Monthly Counter Reset")