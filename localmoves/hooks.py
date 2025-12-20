from __future__ import unicode_literals



app_name = "localmoves"
app_title = "Localmoves"
app_publisher = "megha aadi"
app_description = "local moves"
app_email = "megha250903@gmail.com"
app_license = "mit"


# ✅ JWT validation before Frappe auth
before_request = ["localmoves.utils.jwt_auth.validate_jwt_before_request"]


# ✅ Scheduler
scheduler_events = {
    "cron": {
        "1 0 1 * *": [
            "localmoves.api.request.reset_monthly_view_counts"
        ]
    },
    "daily": [
        "localmoves.localmoves.doctype.payment.payment.check_subscription_expiry",
    ],
    "monthly": [
        "localmoves.api.request.reset_monthly_view_counts",
        "localmoves.localmoves.doctype.payment.payment.auto_generate_monthly_invoices"
    ]
}


# ✅ CSRF bypass for REST APIs
ignore_csrf_check_for = [
    "localmoves.api.auth.*",
    "localmoves.api.company.*",
    "localmoves.api.request.*",
    "localmoves.api.dashboard.*",
    "localmoves.api.payment.*",
    "localmoves.api.inventory.*",  # Add inventory
    "localmoves.api.payment_handler.*",
    "localmoves.api.request_payment.*"  # NEW
]


# ✅ Whitelisted method overrides
override_whitelisted_methods = {
    # Auth
    "localmoves.api.auth.signup": "localmoves.api.auth.signup",
    "localmoves.api.auth.login": "localmoves.api.auth.login",
    "localmoves.api.auth.get_current_user_info": "localmoves.api.auth.get_current_user_info",
    "localmoves.api.auth.change_password": "localmoves.api.auth.change_password",
    "localmoves.api.auth.reset_password": "localmoves.api.auth.reset_password",
    "localmoves.api.auth.update_profile": "localmoves.api.auth.update_profile",


    # Company
    "localmoves.api.company.create_company": "localmoves.api.company.create_company",
    "localmoves.api.company.update_company": "localmoves.api.company.update_company",
    "localmoves.api.company.delete_company": "localmoves.api.company.delete_company",
    "localmoves.api.company.get_my_company": "localmoves.api.company.get_my_company",
    "localmoves.api.company.get_all_companies": "localmoves.api.company.get_all_companies",
    "localmoves.api.company.search_companies_by_pincode": "localmoves.api.company.search_companies_by_pincode",
   
    # ✅ NEW: Distance calculation and enhanced search
    "localmoves.api.company.calculate_distance": "localmoves.api.company.calculate_distance",
    "localmoves.api.company.validate_postcode": "localmoves.api.company.validate_postcode",
    "localmoves.api.company.search_companies_with_auto_distance": "localmoves.api.company.search_companies_with_auto_distance",
    "localmoves.api.company.get_inventory_categories": "localmoves.api.company.get_inventory_categories",
    "localmoves.api.company.get_items_by_category": "localmoves.api.company.get_items_by_category",


    # ✅ NEW: Inventory API
    "localmoves.api.inventory.create_item": "localmoves.api.inventory.create_item",
    "localmoves.api.inventory.get_item": "localmoves.api.inventory.get_item",
    "localmoves.api.inventory.get_all_items": "localmoves.api.inventory.get_all_items",
    "localmoves.api.inventory.update_item": "localmoves.api.inventory.update_item",
    "localmoves.api.inventory.delete_item": "localmoves.api.inventory.delete_item",
    "localmoves.api.inventory.bulk_upload": "localmoves.api.inventory.bulk_upload",
    "localmoves.api.inventory.upload_all_inventory": "localmoves.api.inventory.upload_all_inventory",
    "localmoves.api.inventory.calculate_move_cost": "localmoves.api.inventory.calculate_move_cost",


    # Dashboard
    "localmoves.api.dashboard.get_admin_dashboard": "localmoves.api.dashboard.get_admin_dashboard",
    "localmoves.api.dashboard.get_manager_dashboard": "localmoves.api.dashboard.get_manager_dashboard",
    "localmoves.api.dashboard.get_user_dashboard": "localmoves.api.dashboard.get_user_dashboard",
    "localmoves.api.dashboard.get_system_configuration": "localmoves.api.dashboard.get_system_configuration",
    "localmoves.api.dashboard.update_system_configuration": "localmoves.api.dashboard.update_system_configuration",
    "localmoves.api.dashboard.get_pricing_configuration": "localmoves.api.dashboard.get_pricing_configuration",
    "localmoves.api.dashboard.update_pricing_configuration": "localmoves.api.dashboard.update_pricing_configuration",
    "localmoves.api.dashboard.get_vehicle_configuration": "localmoves.api.dashboard.get_vehicle_configuration",
    "localmoves.api.dashboard.update_vehicle_configuration": "localmoves.api.dashboard.update_vehicle_configuration",
    "localmoves.api.dashboard.get_multiplier_configuration": "localmoves.api.dashboard.get_multiplier_configuration",
    "localmoves.api.dashboard.update_multiplier_configuration": "localmoves.api.dashboard.update_multiplier_configuration",


    # Requests
    "localmoves.api.request.create_request": "localmoves.api.request.create_request",
    "localmoves.api.request.get_my_requests": "localmoves.api.request.get_my_requests",
    "localmoves.api.request.get_request_detail": "localmoves.api.request.get_request_detail",
    "localmoves.api.request.get_manager_requests": "localmoves.api.request.get_manager_requests",
    "localmoves.api.request.accept_available_request": "localmoves.api.request.accept_available_request",
    "localmoves.api.request.assign_request_to_company": "localmoves.api.request.assign_request_to_company",
    "localmoves.api.request.update_request_status": "localmoves.api.request.update_request_status",
    "localmoves.api.request.cancel_request": "localmoves.api.request.cancel_request",
    "localmoves.api.request.get_all_requests": "localmoves.api.request.get_all_requests",
    "localmoves.api.request.get_pending_requests": "localmoves.api.request.get_pending_requests",
    "localmoves.api.request.search_requests_by_pincode": "localmoves.api.request.search_requests_by_pincode",
    "localmoves.api.request.get_quick_subscription_info": "localmoves.api.request.get_quick_subscription_info",


    #category
    "localmoves.api.dashboard.get_all_inventory_categories": "localmoves.api.dashboard.get_all_inventory_categories",
    "localmoves.api.dashboard.create_inventory_category": "localmoves.api.dashboard.create_inventory_category",
    "localmoves.api.dashboard.rename_inventory_category": "localmoves.api.dashboard.rename_inventory_category",
    "localmoves.api.dashboard.delete_inventory_category": "localmoves.api.dashboard.delete_inventory_category",
    "localmoves.api.dashboard.merge_inventory_categories": "localmoves.api.dashboard.merge_inventory_categories",
    "localmoves.api.dashboard.get_category_details": "localmoves.api.dashboard.get_category_details",
    "localmoves.api.dashboard.create_inventory_item_v2": "localmoves.api.dashboard.create_inventory_item_v2",


 # NEW: Request Payment APIs
    "localmoves.api.request_payment.create_request_with_payment": "localmoves.api.request_payment.create_request_with_payment",
    "localmoves.api.request_payment.process_deposit_payment": "localmoves.api.request_payment.process_deposit_payment",
    "localmoves.api.request_payment.process_full_payment": "localmoves.api.request_payment.process_full_payment",
    "localmoves.api.request_payment.get_payment_status": "localmoves.api.request_payment.get_payment_status",
    "localmoves.api.request_payment.get_my_request_payments": "localmoves.api.request_payment.get_my_request_payments",




    "localmoves.api.payment_handler.verify_payment": "localmoves.api.payment_handler.verify_payment",
    "localmoves.api.payment_handler.get_payment_status": "localmoves.api.payment_handler.get_payment_status",
    "localmoves.api.payment_handler.get_payment_history": "localmoves.api.payment_handler.get_payment_history",
    "localmoves.api.payment_handler.admin_get_all_payments": "localmoves.api.payment_handler.admin_get_all_payments",


    # Payments
    "localmoves.api.payment.get_subscription_plans": "localmoves.api.payment.get_subscription_plans",
    "localmoves.api.payment.create_payment": "localmoves.api.payment.create_payment",
    "localmoves.api.payment.mark_payment_paid": "localmoves.api.payment.mark_payment_paid",
    "localmoves.api.payment.get_my_payments": "localmoves.api.payment.get_my_payments",
    "localmoves.api.payment.get_payment_detail": "localmoves.api.payment.get_payment_detail",
    "localmoves.api.payment.get_all_payments": "localmoves.api.payment.get_all_payments",
    "localmoves.api.payment.cancel_payment": "localmoves.api.payment.cancel_payment",
    "localmoves.api.payment.get_subscription_status": "localmoves.api.payment.get_subscription_status",
    "localmoves.api.payment.process_payment": "localmoves.api.payment.process_payment",
}


# ✅ Override Frappe auth
override_methods = {
    "frappe.api.validate_auth": "localmoves.utils.overrides.custom_validate_auth"
}


# ✅ FIX FOR 417 Expectation Failed
# Prevent Frappe from blocking POST with hidden Expect header
website_route_rules = [
    {"from_route": "/api/method/*", "to_route": "api/method/*", "condition": "no_csrf"}
]

