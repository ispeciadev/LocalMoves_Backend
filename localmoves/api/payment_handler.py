import json
import frappe
from frappe import _
from datetime import datetime



def get_email_template(template_name, variables=None, default_subject="", default_body=""):
    """
    Get email template from database, or use default if not found.
    Replaces variables in template if provided.
    """
    try:
        # Query custom template from database
        result = frappe.db.sql("""
            SELECT email_subject, email_body
            FROM `tabEmail Template Config`
            WHERE template_name = %s
            LIMIT 1
        """, template_name, as_dict=True)
       
        if result:
            subject = result[0]['email_subject']
            body = result[0]['email_body']
        else:
            subject = default_subject
            body = default_body
       
        # Replace variables if provided
        if variables and isinstance(variables, dict):
            for var_name, var_value in variables.items():
                placeholder = "{" + var_name + "}"
                subject = subject.replace(placeholder, str(var_value))
                body = body.replace(placeholder, str(var_value))
       
        return subject, body
    except Exception as e:
        frappe.log_error(f"Email Template Error: {str(e)}")
        return default_subject, default_body



def safe_get_dict_value(dictionary, key, default=None):
    """Safely get value from dictionary"""
    if not dictionary or not isinstance(dictionary, dict):
        return default
    return dictionary.get(key, default)


def get_user_from_token():
    """Extract user from JWT token"""
    from localmoves.utils.jwt_handler import get_current_user
    
    try:
        token = frappe.get_request_header("Authorization")
        if not token:
            frappe.throw(_("No token provided"))
        
        if token.startswith("Bearer "):
            token = token[7:]
        
        user_info = get_current_user(token)
        
        if not user_info:
            frappe.throw(_("Invalid token"))
            
        return user_info
        
    except Exception as e:
        frappe.log_error(f"get_user_from_token error: {str(e)}")
        frappe.throw(_("Authentication failed"))


# ==================== VERIFY PAYMENT ====================

@frappe.whitelist(allow_guest=True)
def verify_payment():
    """
    Verify payment and activate request
    
    Request Body:
    {
        "payment_id": "PAY-00001",
        "external_payment_id": "pi_xxx or pay_xxx or txn_xxx",
        "payment_gateway": "Stripe" or "Razorpay" or "PayPal"
    }
    """
    try:
        user_info = get_user_from_token()
        data = frappe.request.get_json() or {}
        
        payment_id = data.get('payment_id')
        external_payment_id = data.get('external_payment_id')
        payment_gateway = data.get('payment_gateway')
        
        if not payment_id:
            return {"success": False, "message": "Payment ID is required"}
        
        if not external_payment_id:
            return {"success": False, "message": "External payment ID is required"}
        
        # Get payment record
        if not frappe.db.exists("Payment Transaction", payment_id):
            return {"success": False, "message": "Payment record not found"}
        
        payment_doc = frappe.get_doc("Payment Transaction", payment_id)
        
        # Check if already verified
        if payment_doc.payment_status == "Verified":
            return {"success": False, "message": "Payment already verified"}
        
        # Update payment record
        payment_doc.payment_status = "Verified"
        payment_doc.external_payment_id = external_payment_id
        if payment_gateway:
            payment_doc.payment_gateway = payment_gateway
        payment_doc.paid_at = datetime.now()
        payment_doc.verified_at = datetime.now()
        payment_doc.updated_at = datetime.now()
        payment_doc.save(ignore_permissions=True)
        
        # Get linked request and update
        if payment_doc.request_id:
            request_doc = frappe.get_doc("Logistics Request", payment_doc.request_id)
            request_doc.payment_status = "Deposit Paid"
            request_doc.payment_verified_at = datetime.now()
            request_doc.save(ignore_permissions=True)
            
            frappe.db.commit()
            
            # Send confirmation email
            send_payment_confirmation_email(payment_doc, request_doc)
            
            return {
                "success": True,
                "message": "Payment verified successfully!",
                "payment_id": payment_doc.name,
                "request_id": request_doc.name,
                "deposit_paid": payment_doc.deposit_amount,
                "remaining_amount": payment_doc.remaining_amount
            }
        else:
            frappe.db.commit()
            return {
                "success": True,
                "message": "Payment verified but no request linked",
                "payment_id": payment_doc.name
            }
        
    except Exception as e:
        frappe.log_error(f"Verify Payment Error: {str(e)}")
        frappe.db.rollback()
        return {"success": False, "message": f"Verification failed: {str(e)}"}


# ==================== GET PAYMENT STATUS ====================

@frappe.whitelist(allow_guest=True)
def get_payment_status():
    """
    Get payment status
    
    Request Body:
    {
        "payment_id": "PAY-00001"
    }
    """
    try:
        user_info = get_user_from_token()
        data = frappe.request.get_json() or {}
        
        payment_id = data.get('payment_id')
        
        if not payment_id:
            return {"success": False, "message": "Payment ID is required"}
        
        if not frappe.db.exists("Payment Transaction", payment_id):
            return {"success": False, "message": "Payment not found"}
        
        payment_doc = frappe.get_doc("Payment Transaction", payment_id)
        
        # Check permission
        user_role = safe_get_dict_value(user_info, "role")
        user_email = safe_get_dict_value(user_info, "email")
        
        if user_role != "Admin" and payment_doc.user_email != user_email:
            return {"success": False, "message": "Permission denied"}
        
        return {
            "success": True,
            "data": {
                "payment_id": payment_doc.name,
                "payment_status": payment_doc.payment_status,
                "payment_gateway": payment_doc.payment_gateway,
                "external_payment_id": payment_doc.external_payment_id,
                "total_amount": payment_doc.total_amount,
                "deposit_amount": payment_doc.deposit_amount,
                "remaining_amount": payment_doc.remaining_amount,
                "currency": payment_doc.currency,
                "request_id": payment_doc.request_id,
                "company_name": payment_doc.company_name,
                "created_at": str(payment_doc.created_at),
                "paid_at": str(payment_doc.paid_at) if payment_doc.paid_at else None,
                "verified_at": str(payment_doc.verified_at) if payment_doc.verified_at else None
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Get Payment Status Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch payment status"}


# ==================== GET PAYMENT HISTORY ====================

@frappe.whitelist(allow_guest=True)
def get_payment_history():
    """Get payment history for logged-in user"""
    try:
        user_info = get_user_from_token()
        user_email = safe_get_dict_value(user_info, "email")
        
        payments = frappe.get_all(
            "Payment Transaction",
            filters={"user_email": user_email},
            fields=[
                "name", "company_name", "total_amount", "deposit_amount",
                "remaining_amount", "currency", "payment_status",
                "payment_gateway", "external_payment_id", "request_id",
                "created_at", "paid_at", "verified_at"
            ],
            order_by="created_at desc"
        )
        
        return {
            "success": True,
            "count": len(payments),
            "data": payments
        }
        
    except Exception as e:
        frappe.log_error(f"Get Payment History Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch payment history"}


# ==================== ADMIN: GET ALL PAYMENTS ====================

@frappe.whitelist(allow_guest=True)
def admin_get_all_payments():
    """Admin: Get all payment transactions"""
    try:
        user_info = get_user_from_token()
        
        if safe_get_dict_value(user_info, 'role') != 'Admin':
            return {"success": False, "message": "Admin access required"}
        
        data = frappe.request.get_json() or {}
        filters = {}
        
        # Filter options
        if data.get('payment_status'):
            filters['payment_status'] = data['payment_status']
        
        if data.get('payment_gateway'):
            filters['payment_gateway'] = data['payment_gateway']
        
        if data.get('company_name'):
            filters['company_name'] = data['company_name']
        
        payments = frappe.get_all(
            "Payment Transaction",
            filters=filters,
            fields="*",
            order_by="created_at desc"
        )
        
        # Calculate totals
        total_collected = sum(p.get('deposit_amount', 0) for p in payments if p.get('payment_status') == 'Verified')
        total_pending = sum(p.get('remaining_amount', 0) for p in payments if p.get('payment_status') == 'Verified')
        
        return {
            "success": True,
            "count": len(payments),
            "data": payments,
            "summary": {
                "total_deposit_collected": total_collected,
                "total_remaining_pending": total_pending,
                "total_transactions": len(payments)
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Admin Get Payments Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch payments"}


# ==================== EMAIL NOTIFICATION ====================

# def send_payment_confirmation_email(payment_doc, request_doc):
#     """Send payment confirmation email with receipt"""
#     try:
#         user_email = payment_doc.user_email
        
#         # Parse request data
#         request_data = {}
#         try:
#             request_data = json.loads(payment_doc.request_data) if payment_doc.request_data else {}
#         except:
#             pass
        
#         user_details = request_data.get('user_details', {})
#         addresses = request_data.get('addresses', {})
        
#         user_name = user_details.get('full_name', 'Customer')
#         pickup_address = addresses.get('pickup_address', '')
#         pickup_city = addresses.get('pickup_city', '')
#         pickup_pincode = addresses.get('pickup_pincode', '')
#         delivery_address = addresses.get('delivery_address', '')
#         delivery_city = addresses.get('delivery_city', '')
#         delivery_pincode = addresses.get('delivery_pincode', '')
        
#         # Create route map URL
#         osm_map_url = f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route={pickup_pincode}%2CUK;{delivery_pincode}%2CUK"
        
#         email_content = f"""
#         <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
#             <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
#                 ✅ Payment Confirmed - Move Request Active
#             </h2>
            
#             <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745;">
#                 <p style="margin: 0; color: #155724; font-size: 16px;">
#                     <strong>Success!</strong> Your payment has been verified and your move is confirmed.
#                 </p>
#             </div>
            
#             <h3 style="color: #2c3e50;">Payment Details</h3>
#             <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
#                 <tr style="background-color: #f8f9fa;">
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Payment ID:</strong></td>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.name}</td>
#                 </tr>
#                 <tr>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Request ID:</strong></td>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;">{request_doc.name}</td>
#                 </tr>
#                 <tr style="background-color: #f8f9fa;">
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Company:</strong></td>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.company_name}</td>
#                 </tr>
#                 <tr>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Payment Gateway:</strong></td>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.payment_gateway}</td>
#                 </tr>
#                 <tr style="background-color: #f8f9fa;">
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Transaction ID:</strong></td>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.external_payment_id}</td>
#                 </tr>
#             </table>
            
#             <h3 style="color: #2c3e50; margin-top: 30px;">💳 Payment Summary</h3>
#             <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
#                 <tr>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Total Amount:</strong></td>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;">£{payment_doc.total_amount:.2f}</td>
#                 </tr>
#                 <tr style="background-color: #d4edda;">
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Deposit Paid (10%):</strong></td>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>£{payment_doc.deposit_amount:.2f} ✓</strong></td>
#                 </tr>
#                 <tr style="background-color: #fff3cd;">
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Remaining Balance:</strong></td>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>£{payment_doc.remaining_amount:.2f}</strong></td>
#                 </tr>
#                 <tr style="background-color: #f8f9fa;">
#                     <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Payment Date:</strong></td>
#                     <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.paid_at.strftime('%d %B %Y, %I:%M %p') if payment_doc.paid_at else 'N/A'}</td>
#                 </tr>
#             </table>
            
#             <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
#                 <h4 style="color: #2c3e50; margin-top: 0;">📍 Pickup Location</h4>
#                 <p style="margin: 5px 0;"><strong>{pickup_address}</strong></p>
#                 <p style="margin: 5px 0; color: #666;">{pickup_city}, {pickup_pincode}</p>
#             </div>
            
#             <div style="background-color: #ffebee; padding: 15px; border-radius: 5px; margin: 20px 0;">
#                 <h4 style="color: #2c3e50; margin-top: 0;">🎯 Delivery Location</h4>
#                 <p style="margin: 5px 0;"><strong>{delivery_address}</strong></p>
#                 <p style="margin: 5px 0; color: #666;">{delivery_city}, {delivery_pincode}</p>
#             </div>
            
#             <div style="text-align: center; margin: 30px 0;">
#                 <h3 style="color: #2c3e50;">Route Map</h3>
#                 <a href="{osm_map_url}" target="_blank" style="display: inline-block; text-decoration: none;">
#                     <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; border-radius: 8px; color: white; font-size: 16px;">
#                         🗺️ View Route Map
#                     </div>
#                 </a>
#             </div>
            
#             <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
#                 <p style="margin: 0; color: #856404;">
#                     <strong>💰 Remaining Payment:</strong> The balance of £{payment_doc.remaining_amount:.2f} will be collected upon move completion.
#                 </p>
#             </div>
            
#             <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
#                 <p style="color: #666; font-size: 12px;">
#                     Thank you for choosing LocalMoves!<br/>
#                     For support, contact us at support@localmoves.com
#                 </p>
#             </div>
#         </div>
#         """
        
#         frappe.sendmail(
#             recipients=[user_email],
#             sender="megha250903@gmail.com",
#             subject=f"✅ Payment Confirmed - {payment_doc.name}",
#             message=email_content,
#             delayed=False,
#             now=True
#         )
        
#         frappe.logger().info(f"Payment confirmation email sent to {user_email}")
        
#     except Exception as e:
#         frappe.log_error(f"Payment Email Error: {str(e)}")



def send_payment_confirmation_email(payment_doc, request_doc):
    """Send payment confirmation email with receipt"""
    try:
        user_email = payment_doc.user_email
       
        # Parse request data
        request_data = {}
        try:
            request_data = json.loads(payment_doc.request_data) if payment_doc.request_data else {}
        except:
            pass
       
        user_details = request_data.get('user_details', {})
        addresses = request_data.get('addresses', {})
       
        user_name = user_details.get('full_name', 'Customer')
        pickup_address = addresses.get('pickup_address', '')
        pickup_city = addresses.get('pickup_city', '')
        pickup_pincode = addresses.get('pickup_pincode', '')
        delivery_address = addresses.get('delivery_address', '')
        delivery_city = addresses.get('delivery_city', '')
        delivery_pincode = addresses.get('delivery_pincode', '')
       
        # Create route map URL
        osm_map_url = f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route={pickup_pincode}%2CUK;{delivery_pincode}%2CUK"
       
        email_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                ✅ Payment Confirmed - Move Request Active
            </h2>
           
            <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745;">
                <p style="margin: 0; color: #155724; font-size: 16px;">
                    <strong>Success!</strong> Your payment has been verified and your move is confirmed.
                </p>
            </div>
           
            <h3 style="color: #2c3e50;">Payment Details</h3>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Payment ID:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Request ID:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{request_doc.name}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Company:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.company_name}</td>
                </tr>
                <tr>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Payment Gateway:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.payment_gateway}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Transaction ID:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.external_payment_id}</td>
                </tr>
            </table>
           
            <h3 style="color: #2c3e50; margin-top: 30px;">💳 Payment Summary</h3>
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Total Amount:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">£{payment_doc.total_amount:.2f}</td>
                </tr>
                <tr style="background-color: #d4edda;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Deposit Paid (10%):</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>£{payment_doc.deposit_amount:.2f} ✓</strong></td>
                </tr>
                <tr style="background-color: #fff3cd;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Remaining Balance:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>£{payment_doc.remaining_amount:.2f}</strong></td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Payment Date:</strong></td>
                    <td style="padding: 10px; border: 1px solid #dee2e6;">{payment_doc.paid_at.strftime('%d %B %Y, %I:%M %p') if payment_doc.paid_at else 'N/A'}</td>
                </tr>
            </table>
           
            <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="color: #2c3e50; margin-top: 0;">📍 Pickup Location</h4>
                <p style="margin: 5px 0;"><strong>{pickup_address}</strong></p>
                <p style="margin: 5px 0; color: #666;">{pickup_city}, {pickup_pincode}</p>
            </div>
           
            <div style="background-color: #ffebee; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="color: #2c3e50; margin-top: 0;">🎯 Delivery Location</h4>
                <p style="margin: 5px 0;"><strong>{delivery_address}</strong></p>
                <p style="margin: 5px 0; color: #666;">{delivery_city}, {delivery_pincode}</p>
            </div>
           
            <div style="text-align: center; margin: 30px 0;">
                <h3 style="color: #2c3e50;">Route Map</h3>
                <a href="{osm_map_url}" target="_blank" style="display: inline-block; text-decoration: none;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; border-radius: 8px; color: white; font-size: 16px;">
                        🗺️ View Route Map
                    </div>
                </a>
            </div>
           
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <p style="margin: 0; color: #856404;">
                    <strong>💰 Remaining Payment:</strong> The balance of £{payment_doc.remaining_amount:.2f} will be collected upon move completion.
                </p>
            </div>
           
            <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                <p style="color: #666; font-size: 12px;">
                    Thank you for choosing LocalMoves!<br/>
                    For support, contact us at support@localmoves.com
                </p>
            </div>
        </div>
        """
       
        # Get custom template or use default
        default_subject = f"✅ Payment Confirmed - {payment_doc.name}"
        template_vars = {
            "user_name": user_name,
            "company_name": payment_doc.company_name or "N/A",
            "request_id": payment_doc.logistics_request or "N/A",
            "total_amount": f"{payment_doc.total_amount:.2f}",
            "deposit_amount": f"{payment_doc.deposit_amount:.2f}",
            "remaining_amount": f"{payment_doc.remaining_amount:.2f}",
            "amount": f"{payment_doc.amount_paid:.2f}",
            "transaction_id": payment_doc.external_payment_id or "N/A",
            "payment_gateway": payment_doc.payment_gateway or "N/A",
            "payment_date": payment_doc.paid_at.strftime("%d %B %Y, %I:%M %p") if payment_doc.paid_at else datetime.now().strftime("%d %B %Y"),
            "pickup_address": pickup_address,
            "pickup_city": pickup_city,
            "pickup_pincode": pickup_pincode,
            "delivery_address": delivery_address,
            "delivery_city": delivery_city,
            "delivery_pincode": delivery_pincode
        }
        subject, message = get_email_template("payment_confirmation", template_vars, default_subject, email_content)
       
        try:
            frappe.sendmail(
                recipients=[user_email],
                sender="megha250903@gmail.com",
                subject=subject,
                message=message,
                delayed=False,
                now=True
            )
        except Exception as email_error:
            error_msg = str(email_error)
            if "Email Account" in error_msg or "OutgoingEmailError" in str(type(email_error)):
                frappe.log_error(f"Email configuration missing: {error_msg}", "Email Configuration Error")
            else:
                raise
       
        frappe.logger().info(f"Payment confirmation email sent to {user_email}")
       
    except Exception as e:
        frappe.log_error(f"Payment Email Error: {str(e)}")


