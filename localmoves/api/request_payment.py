import frappe
from frappe import _
from datetime import datetime
import json
import traceback

# Import existing functions from request.py
from localmoves.api.request import (
    get_user_from_token,
    get_json_data,
    safe_get_dict_value,
    check_subscription_active,
    check_view_limit,
    increment_view_count,
    send_request_confirmation_email,
    generate_item_description
)
from localmoves.api.request_pricing import calculate_comprehensive_price


# ==================== REQUEST PAYMENT CONFIGURATION ====================

REQUEST_PAYMENT_CONFIG = {
    "deposit_percentage": 10,
    "currency": "GBP",
    "payment_methods": ["Stripe", "Razorpay", "PayPal", "Bank Transfer"],
    "refund_policy_days": 7
}


# ==================== HELPER FUNCTIONS ====================

def calculate_payment_amounts(total_amount):
    """Calculate deposit and remaining amounts"""
    deposit = round(total_amount * (REQUEST_PAYMENT_CONFIG["deposit_percentage"] / 100), 2)
    remaining = round(total_amount - deposit, 2)
    
    return {
        "total_amount": total_amount,
        "deposit_amount": deposit,
        "remaining_amount": remaining,
        "deposit_percentage": REQUEST_PAYMENT_CONFIG["deposit_percentage"]
    }


def create_payment_transaction(request_id, company_name, payment_amounts, user_info):
    """Create a Payment Transaction record for the logistics request"""
    try:
        payment_doc = frappe.get_doc({
            "doctype": "Payment Transaction",
            "request_id": request_id,
            "company_name": company_name,
            "user_email": user_info.get("email"),
            
            # Payment amounts
            "total_amount": payment_amounts["total_amount"],
            "deposit_amount": payment_amounts["deposit_amount"],
            "remaining_amount": payment_amounts["remaining_amount"],
            
            # Status
            "payment_status": "Pending",
            "deposit_status": "Unpaid",
            "balance_status": "Unpaid",
            
            # Metadata
            "currency": REQUEST_PAYMENT_CONFIG["currency"],
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        })
        
        payment_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return payment_doc
        
    except Exception as e:
        print(f"Create Payment Transaction Error: {str(e)}")
        raise


def update_request_with_payment(request_doc, payment_doc):
    """Link payment transaction to request"""
    try:
        request_doc.db_set('payment_id', payment_doc.name, update_modified=False)
        request_doc.db_set('payment_status', "Pending", update_modified=False)
        request_doc.db_set('total_amount', payment_doc.total_amount, update_modified=False)
        request_doc.db_set('deposit_paid', 0, update_modified=False)
        request_doc.db_set('remaining_amount', payment_doc.total_amount, update_modified=False)
        
        frappe.db.commit()
        
    except Exception as e:
        print(f"Update Request with Payment Error: {str(e)}")
        raise


def send_payment_confirmation_email(user_email, user_name, request_id, payment_data, request_data, price_breakdown):
    """
    Send payment confirmation email to user
    
    Args:
        user_email: User's email
        user_name: User's full name
        request_id: Request ID
        payment_data: Payment information dict
        request_data: Request details dict
        price_breakdown: Pricing breakdown dict
    """
    try:
        # Format amounts
        total_amount = f"£{payment_data['total_amount']:.2f}"
        deposit_amount = f"£{payment_data['deposit_amount']:.2f}"
        remaining_amount = f"£{payment_data['remaining_amount']:.2f}"
        
        # Build email subject
        subject = f"Payment Confirmation - Request #{request_id}"
        
        # Build email message
        message = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                Payment Confirmation
            </h2>
            
            <p>Dear {user_name},</p>
            
            <p>Thank you for creating your move request with us! Your payment details have been recorded successfully.</p>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-top: 0;">Request Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Request ID:</td>
                        <td style="padding: 8px 0;">{request_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Status:</td>
                        <td style="padding: 8px 0;">{request_data.get('status', 'Pending')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Company:</td>
                        <td style="padding: 8px 0;">{request_data.get('company_name', 'To be assigned')}</td>
                    </tr>
                </table>
            </div>
            
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-top: 0;">Move Information</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Pickup:</td>
                        <td style="padding: 8px 0;">{request_data.get('pickup_address', '')}, {request_data.get('pickup_city', '')}, {request_data.get('pickup_pincode', '')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Delivery:</td>
                        <td style="padding: 8px 0;">{request_data.get('delivery_address', '')}, {request_data.get('delivery_city', '')}, {request_data.get('delivery_pincode', '')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Distance:</td>
                        <td style="padding: 8px 0;">{request_data.get('distance_miles', 0)} miles</td>
                    </tr>
                </table>
            </div>
            
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-top: 0;">Payment Summary</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Payment ID:</td>
                        <td style="padding: 8px 0;">{payment_data['payment_id']}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Total Amount:</td>
                        <td style="padding: 8px 0; font-size: 18px; color: #2c3e50;">{total_amount}</td>
                    </tr>
                    <tr style="background-color: rgba(52, 152, 219, 0.1);">
                        <td style="padding: 8px 0; font-weight: bold;">Deposit Required (10%):</td>
                        <td style="padding: 8px 0; font-size: 16px; color: #3498db;">{deposit_amount}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Remaining Balance:</td>
                        <td style="padding: 8px 0;">{remaining_amount}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-weight: bold;">Deposit Status:</td>
                        <td style="padding: 8px 0;">
                            {'<div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745;"><p style="margin: 0; color: #155724;"><strong>✓ Deposit Paid:</strong> Your 10% deposit has been successfully processed. The remaining balance will be due before the move.</p></div>' if payment_data.get('deposit_paid') else '<div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;"><p style="margin: 0; color: #856404;"><strong>⚠ Action Required:</strong> Please pay the 10% deposit of ' + deposit_amount + ' to confirm your booking. You can pay through your account dashboard.</p></div>'}
                                         color: white; 
                                         padding: 4px 12px; 
                                         border-radius: 12px; 
                                         font-size: 12px;">
                                {payment_data['deposit_status']}
                            </span>
                        </td>
                    </tr>
                </table>
            </div>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-top: 0;">Price Breakdown</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0;">Loading Cost:</td>
                        <td style="padding: 8px 0; text-align: right;">£{price_breakdown.get('adjusted_loading_cost', 0):.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Mileage Cost ({request_data.get('distance_miles', 0)} miles):</td>
                        <td style="padding: 8px 0; text-align: right;">£{price_breakdown.get('mileage_cost', 0):.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0;">Optional Extras:</td>
                        <td style="padding: 8px 0; text-align: right;">£{price_breakdown.get('optional_extras', {}).get('total', 0):.2f}</td>
                    </tr>
                    <tr style="border-top: 2px solid #dee2e6; font-weight: bold; font-size: 16px;">
                        <td style="padding: 12px 0;">Total:</td>
                        <td style="padding: 12px 0; text-align: right; color: #2c3e50;">{total_amount}</td>
                    </tr>
                </table>
            </div>
            
            {'<div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745;"><p style="margin: 0; color: #155724;"><strong>✓ Deposit Paid:</strong> Your 10% deposit has been successfully processed. The remaining balance will be due before the move.</p></div>' if payment_data.get('deposit_paid') else '<div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;"><p style="margin: 0; color: #856404;"><strong>⚠ Action Required:</strong> Please pay the 10% deposit of ' + deposit_amount + ' to confirm your booking. You can pay through your account dashboard.</p></div>'}
            
            <div style="margin: 30px 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; text-align: center;">
                <p style="color: white; margin: 0; font-size: 14px;">Track your request and manage payments from your dashboard</p>
            </div>
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; font-size: 12px; color: #6c757d;">
                <p><strong>Need help?</strong> Contact us at support@localmoves.com</p>
                <p>This is an automated confirmation email. Please do not reply to this message.</p>
            </div>
        </div>
        """
        
        # Send email
        frappe.sendmail(
            recipients=[user_email],
            subject=subject,
            message=message,
            now=True
        )
        
        print(f"Payment confirmation email sent to {user_email}")
        
    except Exception as e:
        print(f"Failed to send payment confirmation email: {str(e)}\n{traceback.format_exc()}")


# ==================== MAIN API: CREATE REQUEST WITH PAYMENT ====================

@frappe.whitelist(allow_guest=True)
def create_request_with_payment():
    """
    Create logistics request with integrated payment system
    """
    try:
        # Step 1: Authenticate user
        user_info = get_user_from_token()
        
        if not user_info or not isinstance(user_info, dict):
            return {"success": False, "message": "Authentication failed"}
        
        if user_info.get("role") not in ["User", "Admin"]:
            return {"success": False, "message": "Only Users can create requests"}
        
        # Step 2: Parse request data
        data = frappe.request.get_json() or {}
        
        # Extract user details
        user_details = data.get('user_details', {})
        full_name = user_details.get('full_name')
        email = user_details.get('email')
        phone = user_details.get('phone')
        
        # Extract addresses
        addresses = data.get('addresses', {})
        pickup_address = addresses.get('pickup_address')
        pickup_city = addresses.get('pickup_city')
        pickup_pincode = addresses.get('pickup_pincode')
        delivery_address = addresses.get('delivery_address')
        delivery_city = addresses.get('delivery_city')
        delivery_pincode = addresses.get('delivery_pincode')
        
        # Validate required fields
        if not all([full_name, email, phone, pickup_address, pickup_city, pickup_pincode,
                   delivery_address, delivery_city, delivery_pincode]):
            return {"success": False, "message": "Missing required fields"}
        
        # Get optional fields
        delivery_date = data.get('delivery_date')
        special_instructions = data.get('special_instructions')
        requested_company_name = data.get('company_name')
        distance_miles = float(data.get('distance_miles', 0))
        
        # Payment fields
        payment_method = data.get('payment_method', 'Stripe')
        process_deposit = data.get('process_deposit', False)
        transaction_ref = data.get('transaction_ref')
        gateway_response = data.get('payment_gateway_response', {})
        
        # Get pricing data
        pricing_data = data.get('pricing_data', {})
        collection_assessment = data.get('collection_assessment', {})
        delivery_assessment = data.get('delivery_assessment', {})
        move_date_data = data.get('move_date_data', {})
        
        # Generate item description
        item_description = generate_item_description(pricing_data)
        
        # Step 3: Validate company and calculate pricing
        if not requested_company_name:
            return {
                "success": False,
                "message": "Company selection required for pricing calculation"
            }
        
        # Validate company exists
        if not frappe.db.exists("Logistics Company", requested_company_name):
            return {"success": False, "message": f"Company '{requested_company_name}' does not exist"}
        
        # Check subscription
        sub_check = check_subscription_active(requested_company_name)
        if not sub_check.get("active", False):
            return {
                "success": False,
                "message": f"Cannot assign to {requested_company_name}. {sub_check.get('message')}"
            }
        
        # Get company document
        company = frappe.get_doc("Logistics Company", requested_company_name)
        
        # Calculate detailed pricing
        try:
            price_breakdown = calculate_comprehensive_price({
                'pricing_data': pricing_data,
                'collection_assessment': collection_assessment,
                'delivery_assessment': delivery_assessment,
                'move_date_data': move_date_data,
                'distance_miles': distance_miles
            }, company)
            
            if not price_breakdown:
                return {"success": False, "message": "Pricing calculation returned None"}
                
        except Exception as price_error:
            return {"success": False, "message": f"Pricing calculation failed: {str(price_error)}"}
        
        # Check capacity
        limit_check = check_view_limit(requested_company_name)
        
        # Determine assignment status
        if limit_check.get("allowed", False):
            final_company_name = requested_company_name
            initial_status = "Assigned"
            assigned_date_value = datetime.now()
            previously_assigned_to = None
            assignment_message = f" and assigned to {requested_company_name}"
        else:
            final_company_name = None
            initial_status = "Pending"
            assigned_date_value = None
            previously_assigned_to = requested_company_name
            assignment_message = f" but {requested_company_name} is at capacity. Will appear in blurred requests."
        
        # Step 4: Create logistics request
        request_doc = frappe.get_doc({
            "doctype": "Logistics Request",
            "user_email": user_info.get("email"),
            "full_name": full_name,
            "email": email,
            "phone": phone,
            
            # Addresses
            "pickup_pincode": pickup_pincode,
            "pickup_address": pickup_address,
            "pickup_city": pickup_city,
            "delivery_pincode": delivery_pincode,
            "delivery_address": delivery_address,
            "delivery_city": delivery_city,
            
            # Move details
            "item_description": item_description,
            "delivery_date": delivery_date,
            "special_instructions": special_instructions,
            
            # Assignment
            "company_name": final_company_name,
            "status": initial_status,
            "priority": "Medium",
            
            # Pricing (store as JSON)
            "pricing_data": json.dumps(pricing_data),
            "collection_assessment": json.dumps(collection_assessment),
            "delivery_assessment": json.dumps(delivery_assessment),
            "move_date_data": json.dumps(move_date_data),
            "distance_miles": distance_miles,
            
            # Price breakdown
            "estimated_cost": price_breakdown['final_total'],
            "price_breakdown": json.dumps(price_breakdown),
            
            # Payment fields
            "payment_gateway": payment_method,
            "payment_status": "Pending",
            
            # Timestamps
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "assigned_date": assigned_date_value,
        })
        
        # Set previously_assigned_to if needed
        if previously_assigned_to and frappe.db.has_column("Logistics Request", "previously_assigned_to"):
            request_doc.previously_assigned_to = previously_assigned_to
        
        # Insert request
        request_doc.insert(ignore_permissions=True)
        
        # Step 5: Create Payment Transaction
        payment_amounts = calculate_payment_amounts(price_breakdown['final_total'])
        
        payment_doc = create_payment_transaction(
            request_id=request_doc.name,
            company_name=requested_company_name,
            payment_amounts=payment_amounts,
            user_info=user_info
        )
        
        # Step 6: Process deposit if requested
        if process_deposit and transaction_ref:
            payment_doc.db_set('deposit_status', "Paid", update_modified=False)
            payment_doc.db_set('deposit_paid_at', datetime.now(), update_modified=False)
            payment_doc.db_set('deposit_transaction_ref', transaction_ref, update_modified=False)
            payment_doc.db_set('payment_method', payment_method, update_modified=False)
            payment_doc.db_set('payment_status', "Paid", update_modified=False)  # CHANGED: Was "Deposit Paid"
            
            if gateway_response:
                payment_doc.db_set('gateway_response', json.dumps(gateway_response), update_modified=False)
            
            # Update request
            request_doc.db_set('payment_status', "Paid", update_modified=False)  # CHANGED: Was "Deposit Paid"
            request_doc.db_set('deposit_paid', payment_doc.deposit_amount, update_modified=False)
            request_doc.db_set('remaining_amount', payment_doc.remaining_amount, update_modified=False)
            request_doc.db_set('payment_verified_at', datetime.now(), update_modified=False)


        # Step 7: Link payment to request
        if not process_deposit:
            update_request_with_payment(request_doc, payment_doc)
        
        # Increment view count if assigned
        if final_company_name and initial_status == "Assigned":
            increment_view_count(final_company_name)
        
        frappe.db.commit()
        
        # Step 8: Send confirmation emails
        try:
            # Send standard request confirmation email
            send_request_confirmation_email(
                user_email=email,
                user_name=full_name,
                request_id=request_doc.name,
                pickup_address=pickup_address,
                pickup_city=pickup_city,
                pickup_pincode=pickup_pincode,
                delivery_address=delivery_address,
                delivery_city=delivery_city,
                delivery_pincode=delivery_pincode,
                item_description=item_description,
                delivery_date=delivery_date,
                company_name=final_company_name,
                status=initial_status,
                property_size=pricing_data.get('house_size') or pricing_data.get('flat_size') or pricing_data.get('property_type'),
                service_type="Standard"
            )
        except Exception as email_error:
            print(f"Standard confirmation email failed for {request_doc.name}: {str(email_error)}")
        
        # Send payment confirmation email with pricing details
        try:
            send_payment_confirmation_email(
                user_email=email,
                user_name=full_name,
                request_id=request_doc.name,
                payment_data={
                    'payment_id': payment_doc.name,
                    'total_amount': payment_amounts["total_amount"],
                    'deposit_amount': payment_amounts["deposit_amount"],
                    'remaining_amount': payment_amounts["remaining_amount"],
                    'payment_status': "Paid",
                    'deposit_status': "Paid",
                    'deposit_paid': process_deposit
                },
                request_data={
                    'status': initial_status,
                    'company_name': final_company_name or 'To be assigned',
                    'pickup_address': pickup_address,
                    'pickup_city': pickup_city,
                    'pickup_pincode': pickup_pincode,
                    'delivery_address': delivery_address,
                    'delivery_city': delivery_city,
                    'delivery_pincode': delivery_pincode,
                    'distance_miles': distance_miles
                },
                price_breakdown=price_breakdown
            )
        except Exception as email_error:
            print(f"Payment confirmation email failed for {request_doc.name}: {str(email_error)}")
        
        # Step 9: Return response
        deposit_processed_msg = " Deposit payment processed." if process_deposit else ""
        
        return {
            "success": True,
            "message": f"Request created successfully{assignment_message}.{deposit_processed_msg}",
            "data": {
                "request_id": request_doc.name,
                "status": request_doc.status,
                "company_name": final_company_name,
                "will_appear_in_blurred": previously_assigned_to is not None,
                
                # Payment information
                "payment": {
                    "payment_id": payment_doc.name,
                    "total_amount": payment_amounts["total_amount"],
                    "deposit_amount": payment_amounts["deposit_amount"],
                    "remaining_amount": payment_amounts["remaining_amount"],
                    "payment_status": payment_doc.payment_status,
                    "deposit_status": payment_doc.deposit_status,
                    "payment_method": payment_method,
                    "currency": REQUEST_PAYMENT_CONFIG["currency"],
                    "deposit_paid": process_deposit
                },
                
                # Pricing breakdown
                "price_breakdown": price_breakdown
            }
        }
        
    except frappe.AuthenticationError as e:
        return {"success": False, "message": f"Authentication error: {str(e)}"}
    except Exception as e:
        print(f"Create Request with Payment Error: {str(e)}\n{traceback.format_exc()}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to create request: {str(e)}"}


# ==================== PROCESS FULL PAYMENT ====================

@frappe.whitelist(allow_guest=True)
def process_full_payment():
    """Process remaining balance payment for a logistics request"""
    try:
        user_info = get_user_from_token()
        data = get_json_data()
        
        payment_id = data.get("payment_id")
        payment_method = data.get("payment_method")
        transaction_ref = data.get("transaction_ref")
        gateway_response = data.get("payment_gateway_response", {})
        
        if not payment_id:
            return {"success": False, "message": "payment_id is required"}
        
        if not frappe.db.exists("Payment Transaction", payment_id):
            return {"success": False, "message": "Payment not found"}
        
        payment_doc = frappe.get_doc("Payment Transaction", payment_id)
        
        # Verify user owns this payment
        if payment_doc.user_email != user_info.get("email"):
            return {"success": False, "message": "Unauthorized access"}
        
        # Check deposit paid
        if payment_doc.deposit_status != "Paid":
            return {"success": False, "message": "Deposit must be paid first"}
        
        # Check if already fully paid
        if payment_doc.balance_status == "Paid":
            return {"success": False, "message": "Balance already paid"}
        
        # Update payment transaction using db_set to avoid version tracking
        payment_doc.db_set('balance_status', "Paid", update_modified=False)
        payment_doc.db_set('balance_paid_at', datetime.now(), update_modified=False)
        payment_doc.db_set('balance_transaction_ref', transaction_ref, update_modified=False)
        payment_doc.db_set('payment_method', payment_method, update_modified=False)
        payment_doc.db_set('updated_at', datetime.now(), update_modified=False)
        
        if gateway_response:
            current_response = json.loads(payment_doc.gateway_response or "{}")
            current_response["balance_payment"] = gateway_response
            payment_doc.db_set('gateway_response', json.dumps(current_response), update_modified=False)
        
        # Update overall status
        payment_doc.db_set('payment_status', "Fully Paid", update_modified=False)
        payment_doc.db_set('fully_paid_at', datetime.now(), update_modified=False)
        
        # Update linked request
        if payment_doc.request_id:
            request_doc = frappe.get_doc("Logistics Request", payment_doc.request_id)
            request_doc.db_set('payment_status', "Fully Paid", update_modified=False)
            request_doc.db_set('remaining_amount', 0, update_modified=False)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "message": "Full payment processed successfully",
            "data": {
                "payment_id": payment_doc.name,
                "total_paid": payment_doc.total_amount,
                "payment_status": "Fully Paid",
                "fully_paid_at": str(payment_doc.fully_paid_at)
            }
        }
        
    except Exception as e:
        print(f"Process Full Payment Error: {str(e)}\n{traceback.format_exc()}")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to process payment: {str(e)}"}


# ==================== GET PAYMENT STATUS ====================

@frappe.whitelist(allow_guest=True)
def get_payment_status():
    """Get payment status for a request"""
    try:
        user_info = get_user_from_token()
        data = get_json_data()
        
        payment_id = data.get("payment_id")
        
        if not payment_id:
            return {"success": False, "message": "payment_id is required"}
        
        if not frappe.db.exists("Payment Transaction", payment_id):
            return {"success": False, "message": "Payment not found"}
        
        payment_doc = frappe.get_doc("Payment Transaction", payment_id)
        
        # Check permissions
        user_email = user_info.get("email")
        is_owner = payment_doc.user_email == user_email
        is_admin = user_info.get("role") == "Admin"
        
        # Check if user is company manager
        is_manager = False
        if payment_doc.company_name:
            company = frappe.get_doc("Logistics Company", payment_doc.company_name)
            is_manager = company.manager_email == user_email
        
        if not (is_owner or is_manager or is_admin):
            return {"success": False, "message": "Unauthorized access"}
        
        return {
            "success": True,
            "data": {
                "payment_id": payment_doc.name,
                "request_id": payment_doc.request_id,
                "total_amount": payment_doc.total_amount,
                "deposit_amount": payment_doc.deposit_amount,
                "remaining_amount": payment_doc.remaining_amount,
                "payment_status": payment_doc.payment_status,
                "deposit_status": payment_doc.deposit_status,
                "balance_status": payment_doc.balance_status,
                "currency": payment_doc.currency,
                "payment_method": payment_doc.payment_method,
                "created_at": str(payment_doc.created_at),
                "deposit_paid_at": str(payment_doc.deposit_paid_at) if payment_doc.deposit_paid_at else None,
                "balance_paid_at": str(payment_doc.balance_paid_at) if payment_doc.balance_paid_at else None,
                "fully_paid_at": str(payment_doc.fully_paid_at) if payment_doc.fully_paid_at else None
            }
        }
        
    except Exception as e:
        print(f"Get Payment Status Error: {str(e)}")
        return {"success": False, "message": f"Failed to fetch status: {str(e)}"}


# ==================== GET MY PAYMENTS ====================

@frappe.whitelist(allow_guest=True)
def get_my_request_payments():
    """Get all payments for current user's requests"""
    try:
        user_info = get_user_from_token()
        user_email = user_info.get("email")
        
        payments = frappe.get_all(
            "Payment Transaction",
            filters={"user_email": user_email},
            fields=[
                "name", "request_id", "company_name", "total_amount",
                "deposit_amount", "remaining_amount", "payment_status",
                "deposit_status", "balance_status", "currency",
                "created_at", "deposit_paid_at", "fully_paid_at"
            ],
            order_by="created_at desc"
        )
        
        return {
            "success": True,
            "count": len(payments),
            "data": payments
        }
        
    except Exception as e:
        print(f"Get My Payments Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch payments"}