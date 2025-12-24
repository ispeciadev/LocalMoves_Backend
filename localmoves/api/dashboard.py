


import frappe
from frappe import _
from localmoves.utils.jwt_handler import get_current_user
from localmoves.utils.config_manager import get_config, update_config
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
from functools import wraps


DEFAULT_SYSTEM_CONFIG = {
    "deposit_percentage": 10,
    "currency": "GBP",
    "refund_policy_days": 7
}

def ignore_csrf(fn):
    """Decorator to bypass CSRF check for API endpoints"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        frappe.flags.ignore_csrf_check = True
        return fn(*args, **kwargs)
    return wrapper

# ===== HELPER FUNCTIONS =====

def ensure_session_data():
    """Ensure frappe.session.data exists to prevent AttributeError during save operations"""
    if not hasattr(frappe.session, 'data') or frappe.session.data is None:
        frappe.session.data = {}


def check_admin_permission():
    """Check if current user has admin permissions"""
    user = frappe.session.user
    if user == "Administrator":
        return True
    
    user_roles = frappe.get_roles(user)
    
    if "System User" in user_roles:
        return True
    
    if frappe.db.exists("LocalMoves User", {"role": "Admin"}):
        return True
    
    has_permission = frappe.has_permission(
        doctype="LocalMoves User",
        ptype="write",
        user=user
    )
    
    if has_permission:
        return True
    
    return False


def get_request_data():
    """Helper function to get request data from either JSON or form_dict"""
    try:
        if not frappe.request:
            return frappe.local.form_dict or {}
        
        content_type = frappe.get_request_header("Content-Type") or ""
        
        if "application/json" in content_type:
            try:
                json_data = frappe.request.get_json()
                if json_data:
                    return json_data
            except Exception as e:
                frappe.log_error(title="JSON Parse Error", message=str(e))
        
        return frappe.local.form_dict or {}
    
    except Exception as e:
        frappe.log_error(title="Request Data Error", message=str(e))
        return {}

# ===== USER CRUD OPERATIONS =====

@frappe.whitelist()
def create_request():
    """Create a new logistics request"""
    try:
        ensure_session_data()
        
        data = get_request_data()
        
        request_doc = frappe.new_doc('Logistics Request')
        request_doc.user_email = data.get('user_email')
        request_doc.user_name = data.get('user_name')
        request_doc.company_name = data.get('company_name')
        request_doc.user_phone = data.get('user_phone')
        request_doc.full_name = data.get('full_name')
        request_doc.email = data.get('email')
        request_doc.phone = data.get('phone')
        request_doc.pickup_address = data.get('pickup_address')
        request_doc.pickup_city = data.get('pickup_city')
        request_doc.pickup_pincode = data.get('pickup_pincode')
        request_doc.delivery_address = data.get('delivery_address')
        request_doc.delivery_city = data.get('delivery_city')
        request_doc.delivery_pincode = data.get('delivery_pincode')
        request_doc.goods_type = data.get('goods_type')
        request_doc.goods_weight = data.get('goods_weight')
        request_doc.vehicle_type = data.get('vehicle_type')
        request_doc.estimated_cost = data.get('estimated_cost')
        request_doc.actual_cost = data.get('actual_cost')
        request_doc.status = data.get('status', 'Pending')
        request_doc.delivery_date = data.get('delivery_date')
        
        request_doc.flags.ignore_version = True
        request_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {'success': True, 'message': 'Request created successfully', 'data': request_doc.as_dict()}
    except Exception as e:
        frappe.log_error(f"Create Request Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}

# @frappe.whitelist()
# def update_request():
#     """Update request details"""
#     try:
#         ensure_session_data()
        
#         data = get_request_data()
#         request_id = data.get('request_id')
        
#         if not request_id:
#             return {'success': False, 'message': 'request_id is required'}
        
#         if not frappe.db.exists('Logistics Request', request_id):
#             return {'success': False, 'message': 'Request not found'}
        
#         # Get the request document
#         request_doc = frappe.get_doc('Logistics Request', request_id)
        
#         # HANDLE STATUS CHANGES
#         new_status = data.get('status')
#         if new_status:
#             # If changing to Pending, clear company assignment
#             if new_status == 'Pending' and request_doc.company_name:
#                 # Store previous assignment
#                 request_doc.previously_assigned_to = request_doc.company_name
#                 request_doc.company_name = None
#                 request_doc.company_email = None
#                 request_doc.assigned_date = None
#                 request_doc.status = 'Pending'
            
#             # If changing to Assigned, require company_name
#             elif new_status == 'Assigned' and not data.get('company_name'):
#                 if not request_doc.company_name:
#                     return {
#                         'success': False,
#                         'message': 'company_name is required when status is "Assigned"'
#                     }
        
#         # VALIDATE COMPANY NAME IF PROVIDED
#         if data.get('company_name'):
#             company_name = data.get('company_name')
            
#             # Allow empty string to clear assignment
#             if company_name == "":
#                 request_doc.company_name = None
#                 request_doc.company_email = None
#                 if request_doc.status == 'Assigned':
#                     request_doc.status = 'Pending'
#             else:
#                 # Check if company exists
#                 if not frappe.db.exists('Logistics Company', company_name):
#                     available_companies = frappe.get_all('Logistics Company',
#                         fields=['company_name'],
#                         filters={'is_active': 1},
#                         pluck='company_name'
#                     )
                    
#                     return {
#                         'success': False, 
#                         'message': f'Company "{company_name}" not found',
#                         'available_companies': available_companies
#                     }
                
#                 # Check if company is active
#                 company_doc = frappe.get_doc('Logistics Company', company_name)
#                 if not company_doc.is_active:
#                     return {
#                         'success': False,
#                         'message': f'Company "{company_name}" is not active'
#                     }
                
#                 # Set company and update status
#                 request_doc.company_name = company_name
#                 request_doc.company_email = company_doc.manager_email
#                 if not request_doc.assigned_date:
#                     request_doc.assigned_date = frappe.utils.now()
#                 if request_doc.status == 'Pending':
#                     request_doc.status = 'Assigned'
        
#         # Update other fields
#         for field in ['user_name', 'user_phone', 'pickup_address', 'pickup_city', 'pickup_pincode',
#                       'delivery_address', 'delivery_city', 'delivery_pincode', 'service_type',
#                       'item_description', 'item_weight', 'special_instructions',
#                       'estimated_cost', 'actual_cost', 'priority', 'notes', 'delivery_date']:
#             if field in data:
#                 setattr(request_doc, field, data.get(field))
        
#         # Explicitly set status if provided and not already handled
#         if 'status' in data and not data.get('company_name'):
#             request_doc.status = data.get('status')
        
#         request_doc.flags.ignore_version = True
#         request_doc.save(ignore_permissions=True)
#         frappe.db.commit()
        
#         return {
#             'success': True, 
#             'message': 'Request updated successfully', 
#             'data': request_doc.as_dict()
#         }
        
#     except Exception as e:
#         frappe.log_error(f"Update Request Error: {str(e)}")
#         frappe.db.rollback()
#         return {'success': False, 'error': str(e)} 


@frappe.whitelist()
def update_request():
    """Update request details"""
    try:
        ensure_session_data()
        
        data = get_request_data()
        request_id = data.get('request_id')
        
        if not request_id:
            return {'success': False, 'message': 'request_id is required'}
        
        if not frappe.db.exists('Logistics Request', request_id):
            return {'success': False, 'message': 'Request not found'}
        
        # Get the request document
        request_doc = frappe.get_doc('Logistics Request', request_id)
        
        # Track what we're updating for debugging
        updated_fields = {}
        
        # EXPLICIT PAYMENT_STATUS HANDLING (FIRST PRIORITY)
        if 'payment_status' in data:
            old_value = request_doc.payment_status
            new_value = data.get('payment_status')
            request_doc.payment_status = new_value
            updated_fields['payment_status'] = {'old': old_value, 'new': new_value}
        
        # HANDLE STATUS CHANGES
        new_status = data.get('status')
        if new_status:
            # If changing to Pending, clear company assignment
            if new_status == 'Pending' and request_doc.company_name:
                # Store previous assignment
                request_doc.previously_assigned_to = request_doc.company_name
                request_doc.company_name = None
                request_doc.company_email = None
                request_doc.assigned_date = None
                request_doc.status = 'Pending'
                updated_fields['status'] = {'old': request_doc.status, 'new': 'Pending'}
            
            # If changing to Assigned, require company_name
            elif new_status == 'Assigned' and not data.get('company_name'):
                if not request_doc.company_name:
                    return {
                        'success': False,
                        'message': 'company_name is required when status is "Assigned"'
                    }
        
        # VALIDATE COMPANY NAME IF PROVIDED
        if data.get('company_name'):
            company_name = data.get('company_name')
            
            # Allow empty string to clear assignment
            if company_name == "":
                request_doc.company_name = None
                request_doc.company_email = None
                if request_doc.status == 'Assigned':
                    request_doc.status = 'Pending'
                updated_fields['company_name'] = {'old': request_doc.company_name, 'new': None}
            else:
                # Check if company exists
                if not frappe.db.exists('Logistics Company', company_name):
                    available_companies = frappe.get_all('Logistics Company',
                        fields=['company_name'],
                        filters={'is_active': 1},
                        pluck='company_name'
                    )
                    
                    return {
                        'success': False, 
                        'message': f'Company "{company_name}" not found',
                        'available_companies': available_companies
                    }
                
                # Check if company is active
                company_doc = frappe.get_doc('Logistics Company', company_name)
                if not company_doc.is_active:
                    return {
                        'success': False,
                        'message': f'Company "{company_name}" is not active'
                    }
                
                # Set company and update status
                old_company = request_doc.company_name
                request_doc.company_name = company_name
                request_doc.company_email = company_doc.manager_email
                updated_fields['company_name'] = {'old': old_company, 'new': company_name}
                
                if not request_doc.assigned_date:
                    request_doc.assigned_date = frappe.utils.now()
                if request_doc.status == 'Pending':
                    request_doc.status = 'Assigned'
        
        # Update other fields
        updatable_fields = [
            'user_name', 'user_phone', 'pickup_address', 'pickup_city', 'pickup_pincode',
            'delivery_address', 'delivery_city', 'delivery_pincode', 'service_type',
            'item_description', 'item_weight', 'special_instructions',
            'estimated_cost', 'actual_cost', 'priority', 'notes', 'delivery_date',
            'total_amount', 'deposit_paid', 'remaining_amount'
        ]
        
        for field in updatable_fields:
            if field in data and field != 'payment_status':  # Skip payment_status as we already handled it
                old_value = getattr(request_doc, field, None)
                new_value = data.get(field)
                setattr(request_doc, field, new_value)
                updated_fields[field] = {'old': old_value, 'new': new_value}
        
        # Explicitly set status if provided and not already handled
        if 'status' in data and not data.get('company_name'):
            old_status = request_doc.status
            request_doc.status = data.get('status')
            updated_fields['status'] = {'old': old_status, 'new': data.get('status')}
        
        # Save with explicit flags
        request_doc.flags.ignore_version = True
        request_doc.flags.ignore_validate = False  # We want validation
        request_doc.flags.ignore_permissions = True
        
        # Save the document
        request_doc.save(ignore_permissions=True)
        
        # Commit to database
        frappe.db.commit()
        
        # Verify the update by fetching fresh data
        fresh_doc = frappe.get_doc('Logistics Request', request_id)
        
        return {
            'success': True, 
            'message': 'Request updated successfully',
            'updated_fields': updated_fields,
            'verification': {
                'payment_status_before': data.get('payment_status', 'N/A'),
                'payment_status_after': fresh_doc.payment_status,
                'updated_correctly': fresh_doc.payment_status == data.get('payment_status') if 'payment_status' in data else True
            },
            'data': fresh_doc.as_dict()
        }
        
    except Exception as e:
        frappe.log_error(f"Update Request Error: {str(e)}")
        frappe.db.rollback()
        return {
            'success': False, 
            'error': str(e),
            'traceback': frappe.get_traceback()
        }
# @frappe.whitelist()
# def delete_request():
#     """Delete a request"""
#     try:
#         data = get_request_data()
#         request_id = data.get('request_id')
#         if not frappe.db.exists('Logistics Request', request_id):
#             return {'success': False, 'message': 'Request not found'}
        
#         frappe.delete_doc('Logistics Request', request_id, ignore_permissions=True)
#         frappe.db.commit()
        
#         return {'success': True, 'message': 'Request deleted successfully'}
#     except Exception as e:
#         frappe.log_error(f"Delete Request Error: {str(e)}")
#         frappe.db.rollback()
#         return {'success': False, 'error': str(e)}

# ===== PAYMENT CRUD OPERATIONS =====

@frappe.whitelist()
def delete_request():
    """Delete a request and its linked payment transactions"""
    try:
        import json
        
        request_id = None
        
        # Parse raw request data
        if frappe.request:
            raw_data = frappe.request.get_data(as_text=True)
            if raw_data:
                try:
                    parsed = json.loads(raw_data)
                    request_id = parsed.get('request_id')
                except:
                    pass
        
        # Fallback: Check form_dict
        if not request_id:
            request_id = frappe.local.form_dict.get('request_id')
        
        if not request_id:
            return {
                'success': False, 
                'message': 'request_id is required'
            }
        
        # Check if request exists
        if not frappe.db.exists('Logistics Request', request_id):
            return {
                'success': False, 
                'message': f'Request not found: {request_id}'
            }
        
        # Get cascade delete option (default: false)
        cascade = parsed.get('cascade', False) if 'parsed' in locals() else False
        
        # Check for linked Payment Transactions
        linked_payments = frappe.get_all('Payment Transaction',
            filters={'request_id': request_id},
            fields=['name', 'payment_status', 'total_amount']
        )
        
        if linked_payments:
            if not cascade:
                # Return error with option to cascade delete
                return {
                    'success': False,
                    'message': f'Cannot delete request {request_id} because it has {len(linked_payments)} linked payment transaction(s)',
                    'linked_payments': linked_payments,
                    'suggestion': 'Set "cascade": true in your request to delete linked records, or delete them manually first'
                }
            else:
                # CASCADE DELETE: Delete linked payments first
                deleted_payments = []
                for payment in linked_payments:
                    try:
                        frappe.delete_doc('Payment Transaction', payment['name'], 
                                        ignore_permissions=True, force=True)
                        deleted_payments.append(payment['name'])
                    except Exception as e:
                        frappe.log_error(f"Failed to delete payment {payment['name']}: {str(e)}")
        
        # Now delete the request
        frappe.delete_doc('Logistics Request', request_id, 
                         ignore_permissions=True, force=True)
        frappe.db.commit()
        
        result = {
            'success': True, 
            'message': 'Request deleted successfully',
            'request_id': request_id
        }
        
        if cascade and linked_payments:
            result['cascade_deleted'] = {
                'payment_transactions': deleted_payments if 'deleted_payments' in locals() else [],
                'count': len(deleted_payments) if 'deleted_payments' in locals() else 0
            }
        
        return result
        
    except frappe.LinkExistsError as e:
        # Catch the specific link exists error
        error_msg = str(e)
        frappe.db.rollback()
        return {
            'success': False,
            'error': 'Link exists',
            'message': error_msg,
            'suggestion': 'Use "cascade": true to delete linked records automatically'
        }
        
    except Exception as e:
        frappe.log_error(title="Delete Request Error", message=str(e))
        frappe.db.rollback()
        return {
            'success': False, 
            'error': str(e)
        }    

@frappe.whitelist()    
def get_all_payments():
    """Get all payments"""
    try:
        payments = frappe.get_all('Payment',
            fields=['*'],
            order_by='created_at desc'
        )
        return {'success': True, 'data': payments, 'count': len(payments)}
    except Exception as e:
        frappe.log_error(f"Get Payments Error: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def get_payment():
    """Get a single payment by ID"""
    try:
        payment_id = frappe.local.form_dict.get('payment_id')
        if not payment_id:
            return {'success': False, 'message': 'Payment ID is required'}

        if not frappe.db.exists('Payment', payment_id):
            return {'success': False, 'message': 'Payment not found'}
        
        payment = frappe.get_doc('Payment', payment_id)
        return {'success': True, 'data': payment.as_dict()}
    except Exception as e:
        frappe.log_error(f"Get Payment Error: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def create_payment():
    """Create a new payment"""
    try:
        ensure_session_data()
        
        data = get_request_data()
        
        payment_doc = frappe.new_doc('Payment')
        payment_doc.company_name = data.get('company_name')
        payment_doc.invoice_number = data.get('invoice_number')
        payment_doc.subscription_plan = data.get('subscription_plan')
        payment_doc.amount = data.get('amount')
        payment_doc.payment_status = data.get('payment_status', 'Pending')
        payment_doc.paid_date = data.get('paid_date')
        payment_doc.notes = data.get('notes')
        
        payment_doc.flags.ignore_version = True
        payment_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {'success': True, 'message': 'Payment created successfully', 'data': payment_doc.as_dict()}
    except Exception as e:
        frappe.log_error(f"Create Payment Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def update_payment():
    """Update payment status"""
    try:
        ensure_session_data()
        
        data = get_request_data()
        payment_id = data.get('payment_id')
        
        if not frappe.db.exists('Payment', payment_id):
            return {'success': False, 'message': 'Payment not found'}
        
        payment_doc = frappe.get_doc('Payment', payment_id)
        
        if data.get('payment_status'):
            payment_doc.payment_status = data.get('payment_status')
            if data.get('payment_status') == 'Paid' and not payment_doc.paid_date:
                payment_doc.paid_date = datetime.now()
        
        if data.get('notes'):
            payment_doc.notes = data.get('notes')
        
        payment_doc.flags.ignore_version = True
        payment_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {'success': True, 'message': 'Payment updated successfully', 'data': payment_doc.as_dict()}
    except Exception as e:
        frappe.log_error(f"Update Payment Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def delete_payment():
    """Delete a payment"""
    try:
        data = get_request_data()
        payment_id = data.get('payment_id')
        
        if not frappe.db.exists('Payment', payment_id):
            return {'success': False, 'message': 'Payment not found'}
        
        frappe.delete_doc('Payment', payment_id, ignore_permissions=True)
        frappe.db.commit()
        
        return {'success': True, 'message': 'Payment deleted successfully'}
    except Exception as e:
        frappe.log_error(f"Delete Payment Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}

# ===== DIAGNOSTIC ENDPOINTS (FOR DEBUGGING) =====

@frappe.whitelist()
def debug_request_data():
    """Debug endpoint to see what data is being received"""
    debug_info = {
        'success': True,
        'tests': {}
    }
    
    try:
        # Test 1: Check if frappe.request exists
        debug_info['tests']['1_frappe_request_exists'] = bool(frappe.request)
        
        # Test 2: Check Content-Type
        if frappe.request:
            debug_info['tests']['2_content_type'] = frappe.get_request_header("Content-Type")
            debug_info['tests']['2_method'] = frappe.request.method
        else:
            debug_info['tests']['2_no_request'] = "frappe.request is None"
        
        # Test 3: Try frappe.request.get_json()
        try:
            if frappe.request and hasattr(frappe.request, 'get_json'):
                json_data = frappe.request.get_json()
                debug_info['tests']['3_request_get_json'] = {
                    'success': True,
                    'type': type(json_data).__name__,
                    'is_none': json_data is None,
                    'data': json_data if json_data else 'None'
                }
            else:
                debug_info['tests']['3_request_get_json'] = 'Method not available'
        except Exception as e:
            debug_info['tests']['3_request_get_json'] = {
                'success': False,
                'error': str(e)
            }
        
        # Test 4: Check frappe.local.form_dict
        try:
            debug_info['tests']['4_form_dict'] = {
                'exists': hasattr(frappe.local, 'form_dict'),
                'is_none': frappe.local.form_dict is None if hasattr(frappe.local, 'form_dict') else 'N/A',
                'type': type(frappe.local.form_dict).__name__ if hasattr(frappe.local, 'form_dict') else 'N/A',
                'data': dict(frappe.local.form_dict) if hasattr(frappe.local, 'form_dict') and frappe.local.form_dict else None
            }
        except Exception as e:
            debug_info['tests']['4_form_dict'] = {
                'success': False,
                'error': str(e)
            }
        
        # Test 5: Try get_request_data()
        try:
            data = get_request_data()
            debug_info['tests']['5_get_request_data'] = {
                'success': True,
                'type': type(data).__name__,
                'is_none': data is None,
                'is_dict': isinstance(data, dict),
                'data': data if isinstance(data, dict) else str(data)[:200]
            }
        except Exception as e:
            debug_info['tests']['5_get_request_data'] = {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
        
        # Test 6: Session data
        debug_info['tests']['6_session_data'] = {
            'exists': hasattr(frappe.session, 'data'),
            'is_none': frappe.session.data is None if hasattr(frappe.session, 'data') else 'N/A',
            'user': frappe.session.user
        }
        
        return debug_info
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }

@frappe.whitelist()
def list_users_for_update():
    """List all users with their correct IDs for update operations"""
    try:
        users = frappe.db.sql("""
            SELECT 
                name as user_id,
                email,
                full_name,
                phone,
                role,
                city,
                state,
                is_active
            FROM `tabLocalMoves User`
            ORDER BY creation DESC
            LIMIT 20
        """, as_dict=True)
        
        return {
            'success': True,
            'count': len(users),
            'users': users,
            'instructions': {
                'note': 'Use the "user_id" field (not email) when calling update_user',
                'example': {
                    'user_id': users[0]['user_id'] if users else 'example-id',
                    'full_name': 'New Name',
                    'city': 'New City'
                }
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }()

@frappe.whitelist(allow_guest=False)
def create_user():
    """Create a new user - Admin/System Manager only"""
    try:
        # Ensure session data exists
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to create users'
            }
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['email', 'full_name', 'password', 'phone', 'role']
        for field in required_fields:
            if not data.get(field):
                return {'success': False, 'message': f'{field} is required'}
        
        # Check if user already exists
        if frappe.db.exists('LocalMoves User', {'email': data.get('email')}):
            return {'success': False, 'message': 'User with this email already exists'}
        
        # Check if phone already exists
        if frappe.db.exists('LocalMoves User', {'phone': data.get('phone')}):
            return {'success': False, 'message': 'User with this phone number already exists'}
        
        # Validate role
        valid_roles = ['Admin', 'Logistics Manager', 'User']
        if data.get('role') not in valid_roles:
            return {'success': False, 'message': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}
        
        # Create new user
        user_doc = frappe.new_doc('LocalMoves User')
        user_doc.email = data.get('email')
        user_doc.full_name = data.get('full_name')
        user_doc.phone = data.get('phone')
        user_doc.password = data.get('password')  # Will be hashed in before_insert hook
        user_doc.role = data.get('role')
        
        # Optional fields
        user_doc.pincode = data.get('pincode', '')
        user_doc.address = data.get('address', '')
        user_doc.city = data.get('city', '')
        user_doc.state = data.get('state', '')
        user_doc.is_active = 1
        user_doc.is_phone_verified = data.get('is_phone_verified', 0)
        
        # Disable version tracking
        user_doc.flags.ignore_version = True
        user_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            'success': True, 
            'message': 'User created successfully', 
            'data': {
                'user_id': user_doc.name,
                'email': user_doc.email,
                'full_name': user_doc.full_name,
                'phone': user_doc.phone,
                'role': user_doc.role,
                'is_active': user_doc.is_active
            }
        }
    except Exception as e:
        frappe.log_error(f"Create User Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'message': str(e)}

@frappe.whitelist()
def update_user():
    """Update user details - Admin/System Manager only"""
    try:
        # Ensure session data exists FIRST
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            frappe.local.response['http_status_code'] = 403
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to update users'
            }
        
        # Get request data
        data = get_request_data()
        
        # Validate data is not None
        if data is None:
            frappe.local.response['http_status_code'] = 400
            return {'success': False, 'message': 'No data provided in request'}
        
        # Validate data is a dict
        if not isinstance(data, dict):
            frappe.local.response['http_status_code'] = 400
            return {'success': False, 'message': f'Invalid data type: {type(data).__name__}'}
        
        # Get user_id
        user_id = data.get('user_id')
        
        if not user_id:
            frappe.local.response['http_status_code'] = 400
            return {'success': False, 'message': 'user_id is required'}
        
        # Check if user exists - Use SQL instead of db.exists with dict
        user_exists = frappe.db.sql("""
            SELECT name FROM `tabLocalMoves User`
            WHERE name = %s OR email = %s
            LIMIT 1
        """, (user_id, user_id), as_dict=True)
        
        if not user_exists:
            frappe.local.response['http_status_code'] = 404
            return {'success': False, 'message': f'User not found: {user_id}'}
        
        # Get actual user ID
        actual_user_id = user_exists[0]['name']
        
        # Get the user document
        user_doc = frappe.get_doc('LocalMoves User', actual_user_id)
        
        # Track what we're updating
        updated_fields = []
        
        # Update full_name if provided
        if 'full_name' in data and data.get('full_name'):
            user_doc.full_name = data.get('full_name')
            updated_fields.append('full_name')
        
        # Update phone if provided
        if 'phone' in data and data.get('phone'):
            new_phone = data.get('phone')
            # Only check if phone is actually changing
            if new_phone != user_doc.phone:
                # Use SQL instead of db.exists with dict
                phone_exists = frappe.db.sql("""
                    SELECT name FROM `tabLocalMoves User`
                    WHERE phone = %s AND name != %s
                    LIMIT 1
                """, (new_phone, actual_user_id))
                
                if phone_exists:
                    frappe.local.response['http_status_code'] = 409
                    return {
                        'success': False, 
                        'message': f'Phone number already exists for user: {phone_exists[0][0]}'
                    }
                
                user_doc.phone = new_phone
                updated_fields.append('phone')
        
        # Update role if provided
        if 'role' in data and data.get('role'):
            valid_roles = ['Admin', 'Logistics Manager', 'User']
            new_role = data.get('role')
            if new_role not in valid_roles:
                frappe.local.response['http_status_code'] = 400
                return {
                    'success': False, 
                    'message': f'Invalid role. Must be one of: {", ".join(valid_roles)}'
                }
            user_doc.role = new_role
            updated_fields.append('role')
        
        # Update optional text fields
        if 'pincode' in data:
            user_doc.pincode = data.get('pincode') or ''
            updated_fields.append('pincode')
        
        if 'address' in data:
            user_doc.address = data.get('address') or ''
            updated_fields.append('address')
        
        if 'city' in data:
            user_doc.city = data.get('city') or ''
            updated_fields.append('city')
        
        if 'state' in data:
            user_doc.state = data.get('state') or ''
            updated_fields.append('state')
        
        # Update boolean fields
        if 'is_active' in data:
            try:
                user_doc.is_active = int(data.get('is_active'))
                updated_fields.append('is_active')
            except (ValueError, TypeError):
                frappe.local.response['http_status_code'] = 400
                return {'success': False, 'message': 'is_active must be 0 or 1'}
        
        if 'is_phone_verified' in data:
            try:
                user_doc.is_phone_verified = int(data.get('is_phone_verified'))
                updated_fields.append('is_phone_verified')
            except (ValueError, TypeError):
                frappe.local.response['http_status_code'] = 400
                return {'success': False, 'message': 'is_phone_verified must be 0 or 1'}
        
        # Update password if provided
        if 'password' in data and data.get('password'):
            user_doc.password = data.get('password')
            updated_fields.append('password')
        
        # Check if anything needs to be updated
        if not updated_fields:
            return {
                'success': True, 
                'message': 'No fields to update',
                'data': {
                    'user_id': user_doc.name,
                    'email': user_doc.email,
                    'full_name': user_doc.full_name,
                    'phone': user_doc.phone,
                    'role': user_doc.role,
                    'is_active': user_doc.is_active
                }
            }
        
        # CRITICAL FIX: Disable version tracking before save
        user_doc.flags.ignore_version = True
        
        # Save the document
        user_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            'success': True, 
            'message': f'User updated successfully. Updated fields: {", ".join(updated_fields)}',
            'data': {
                'user_id': user_doc.name,
                'email': user_doc.email,
                'full_name': user_doc.full_name,
                'phone': user_doc.phone,
                'role': user_doc.role,
                'city': user_doc.city or '',
                'state': user_doc.state or '',
                'is_active': user_doc.is_active,
                'updated_fields': updated_fields
            }
        }
        
    except frappe.ValidationError as ve:
        error_msg = str(ve)
        frappe.local.response['http_status_code'] = 422
        frappe.log_error(title="User Update Validation", message=error_msg)
        frappe.db.rollback()
        return {'success': False, 'message': f'Validation error: {error_msg}'}
        
    except frappe.DoesNotExistError as de:
        error_msg = str(de)
        frappe.local.response['http_status_code'] = 404
        frappe.log_error(title="User Not Found", message=error_msg)
        frappe.db.rollback()
        return {'success': False, 'message': f'User does not exist'}
    
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        frappe.local.response['http_status_code'] = 500
        
        # Log full error details
        import traceback
        frappe.log_error(
            title="User Update Error",
            message=f"Error Type: {error_type}\nError: {error_msg}\n\nTraceback:\n{traceback.format_exc()}"
        )
        frappe.db.rollback()
        
        return {
            'success': False, 
            'message': f'Error: {error_msg}',
            'error_type': error_type
        }

@frappe.whitelist()
def delete_user():
    """Delete a user - Admin/System Manager only"""
    try:
        # Ensure session data exists
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to delete users'
            }
        
        data = get_request_data()
        user_id = data.get('user_id')
        
        if not user_id:
            return {'success': False, 'message': 'user_id is required'}
        
        if not frappe.db.exists('LocalMoves User', user_id):
            return {'success': False, 'message': 'User not found'}
        
        # Prevent deleting yourself
        current_user_email = frappe.session.user
        user_to_delete = frappe.get_doc('LocalMoves User', user_id)
        
        if user_to_delete.email == current_user_email:
            return {'success': False, 'message': 'You cannot delete your own account'}
        
        frappe.delete_doc('LocalMoves User', user_id, ignore_permissions=True)
        frappe.db.commit()
        
        return {'success': True, 'message': 'User deleted successfully'}
    except Exception as e:
        frappe.log_error(f"Delete User Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'message': str(e)}

@frappe.whitelist()
def get_all_users():
    """Get all users with filters - Admin/System Manager only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view users'
            }
        
        # Get filter parameters
        data = get_request_data()
        filters = {}
        
        if data.get('role'):
            filters['role'] = data.get('role')
        
        if data.get('is_active') is not None:
            filters['is_active'] = int(data.get('is_active'))
        
        users = frappe.get_all('LocalMoves User',
            fields=['name', 'full_name', 'email', 'phone', 'role', 'is_active', 'city', 'state', 'creation', 'last_login'],
            filters=filters,
            order_by='creation desc'
        )
        
        return {'success': True, 'data': users, 'count': len(users)}
    except Exception as e:
        frappe.log_error(f"Get Users Error: {str(e)}")
        return {'success': False, 'message': str(e)}

@frappe.whitelist()
def get_user():
    """Get a single user by ID - Admin/System Manager only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view users'
            }
        
        user_id = frappe.local.form_dict.get('user_id')
        if not user_id:
            return {'success': False, 'message': 'User ID is required'}

        if not frappe.db.exists('LocalMoves User', user_id):
            return {'success': False, 'message': 'User not found'}
        
        user = frappe.get_doc('LocalMoves User', user_id)
        user_dict = user.as_dict()
        
        # Remove sensitive data
        if 'password' in user_dict:
            del user_dict['password']
        if 'otp_code' in user_dict:
            del user_dict['otp_code']
        
        return {'success': True, 'data': user_dict}
    except Exception as e:
        frappe.log_error(f"Get User Error: {str(e)}")
        return {'success': False, 'message': str(e)}

# ===== CHART DATA FUNCTIONS =====

@frappe.whitelist()
def get_user_growth_chart():
    """Get user growth data for charts (7 days, 1 month, 1 year)"""
    try:
        # Last 7 days
        seven_days_data = frappe.db.sql("""
            SELECT DATE(creation) as date, COUNT(*) as count
            FROM `tabLocalMoves User`
            WHERE creation >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(creation)
            ORDER BY date ASC
        """, as_dict=True)
        
        # Last 30 days
        month_data = frappe.db.sql("""
            SELECT DATE(creation) as date, COUNT(*) as count
            FROM `tabLocalMoves User`
            WHERE creation >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(creation)
            ORDER BY date ASC
        """, as_dict=True)
        
        # Last 12 months
        year_data = frappe.db.sql("""
            SELECT DATE_FORMAT(creation, '%Y-%m') as month, COUNT(*) as count
            FROM `tabLocalMoves User`
            WHERE creation >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(creation, '%Y-%m')
            ORDER BY month ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'seven_days': seven_days_data,
                'one_month': month_data,
                'one_year': year_data
            }
        }
    except Exception as e:
        frappe.log_error(f"User Growth Chart Error: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def get_revenue_chart():
    """Get revenue data for charts"""
    try:
        # Last 7 days
        seven_days = frappe.db.sql("""
            SELECT DATE(paid_date) as date, SUM(amount) as revenue
            FROM `tabPayment`
            WHERE payment_status = 'Paid' 
            AND paid_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(paid_date)
            ORDER BY date ASC
        """, as_dict=True)
        
        # Last 30 days
        month_data = frappe.db.sql("""
            SELECT DATE(paid_date) as date, SUM(amount) as revenue
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            AND paid_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(paid_date)
            ORDER BY date ASC
        """, as_dict=True)
        
        # Last 12 months
        year_data = frappe.db.sql("""
            SELECT DATE_FORMAT(paid_date, '%Y-%m') as month, SUM(amount) as revenue
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            AND paid_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(paid_date, '%Y-%m')
            ORDER BY month ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'seven_days': seven_days,
                'one_month': month_data,
                'one_year': year_data
            }
        }
    except Exception as e:
        frappe.log_error(f"Revenue Chart Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def get_deposit_payment_chart():
    """Get 10% deposit payment data for charts"""
    try:
        # Last 7 days
        seven_days = frappe.db.sql("""
            SELECT DATE(deposit_paid_at) as date, 
                   SUM(deposit_amount) as revenue,
                   COUNT(*) as transaction_count
            FROM `tabPayment Transaction`
            WHERE deposit_status = 'Paid' 
            AND deposit_paid_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(deposit_paid_at)
            ORDER BY date ASC
        """, as_dict=True)
        
        # Last 30 days
        month_data = frappe.db.sql("""
            SELECT DATE(deposit_paid_at) as date, 
                   SUM(deposit_amount) as revenue,
                   COUNT(*) as transaction_count
            FROM `tabPayment Transaction`
            WHERE deposit_status = 'Paid'
            AND deposit_paid_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(deposit_paid_at)
            ORDER BY date ASC
        """, as_dict=True)
        
        # Last 12 months
        year_data = frappe.db.sql("""
            SELECT DATE_FORMAT(deposit_paid_at, '%Y-%m') as month, 
                   SUM(deposit_amount) as revenue,
                   COUNT(*) as transaction_count
            FROM `tabPayment Transaction`
            WHERE deposit_status = 'Paid'
            AND deposit_paid_at >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(deposit_paid_at, '%Y-%m')
            ORDER BY month ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'seven_days': seven_days,
                'one_month': month_data,
                'one_year': year_data
            }
        }
    except Exception as e:
        frappe.log_error(f"Deposit Payment Chart Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def get_dashboard_stats():
    """Get comprehensive dashboard statistics for admin INCLUDING PAYMENTS AND DEPOSIT ANALYTICS"""
    try:
        # Total counts
        total_users = frappe.db.count('LocalMoves User', {'is_active': 1})
        total_companies = frappe.db.count('Logistics Company')
        
        # PAID SUBSCRIBERS ONLY (companies with paid plans)
        paid_subscribers = frappe.db.count('Logistics Company', {
            'subscription_plan': ['in', ['Basic', 'Standard', 'Premium']]
        })
        
        total_requests = frappe.db.count('Logistics Request')
        
        # ===== PAYMENT STATISTICS =====
        
        # Total payments and revenue
        total_payments_count = frappe.db.count('Payment')
        
        # Revenue from PAID payments only
        paid_revenue = frappe.db.sql("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
        """, as_dict=True)[0].total or 0
        
        # Pending revenue
        pending_revenue = frappe.db.sql("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM `tabPayment`
            WHERE payment_status = 'Pending'
        """, as_dict=True)[0].total or 0
        
        # ===== REQUEST PAYMENT TRANSACTION STATISTICS (10% DEPOSITS) =====
        
        # Total Payment Transactions count
        total_payment_transactions = frappe.db.count('Payment Transaction')
        
        # Deposit payments (10% deposits) - PAID ONLY
        deposit_paid_count = frappe.db.count('Payment Transaction', {
            'deposit_status': 'Paid'
        })
        
        deposit_paid_revenue = frappe.db.sql("""
            SELECT COALESCE(SUM(deposit_amount), 0) as total
            FROM `tabPayment Transaction`
            WHERE deposit_status = 'Paid'
        """, as_dict=True)[0].total or 0
        
        # Deposit payments - UNPAID
        deposit_unpaid_count = frappe.db.count('Payment Transaction', {
            'deposit_status': 'Unpaid'
        })
        
        deposit_unpaid_amount = frappe.db.sql("""
            SELECT COALESCE(SUM(deposit_amount), 0) as total
            FROM `tabPayment Transaction`
            WHERE deposit_status = 'Unpaid'
        """, as_dict=True)[0].total or 0
        
        # Balance payments (remaining 90%) - PAID
        balance_paid_count = frappe.db.count('Payment Transaction', {
            'balance_status': 'Paid'
        })
        
        balance_paid_revenue = frappe.db.sql("""
            SELECT COALESCE(SUM(remaining_amount), 0) as total
            FROM `tabPayment Transaction`
            WHERE balance_status = 'Paid'
        """, as_dict=True)[0].total or 0
        
        # Balance payments - UNPAID
        balance_unpaid_count = frappe.db.count('Payment Transaction', {
            'balance_status': 'Unpaid'
        })
        
        balance_unpaid_amount = frappe.db.sql("""
            SELECT COALESCE(SUM(remaining_amount), 0) as total
            FROM `tabPayment Transaction`
            WHERE balance_status = 'Unpaid'
        """, as_dict=True)[0].total or 0
        
        # Fully paid transactions
        fully_paid_count = frappe.db.count('Payment Transaction', {
            'payment_status': 'Fully Paid'
        })
        
        fully_paid_revenue = frappe.db.sql("""
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM `tabPayment Transaction`
            WHERE payment_status = 'Fully Paid'
        """, as_dict=True)[0].total or 0
        
        # Total request payments revenue (deposits + balance)
        total_request_payments_revenue = deposit_paid_revenue + balance_paid_revenue
        
        # ===== BAR GRAPH DATA FOR DEPOSITS BY DATE (Last 30 Days) =====
        deposit_trend = frappe.db.sql("""
            SELECT 
                DATE(deposit_paid_at) as payment_date,
                COUNT(*) as transaction_count,
                SUM(deposit_amount) as daily_revenue
            FROM `tabPayment Transaction`
            WHERE deposit_status = 'Paid'
            AND deposit_paid_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(deposit_paid_at)
            ORDER BY payment_date ASC
        """, as_dict=True)
        
        # ===== BAR GRAPH DATA FOR DEPOSITS BY COMPANY =====
        deposit_by_company = frappe.db.sql("""
            SELECT 
                company_name,
                COUNT(*) as transaction_count,
                SUM(deposit_amount) as total_deposits,
                SUM(CASE WHEN deposit_status = 'Paid' THEN deposit_amount ELSE 0 END) as paid_deposits,
                SUM(CASE WHEN deposit_status = 'Unpaid' THEN deposit_amount ELSE 0 END) as unpaid_deposits
            FROM `tabPayment Transaction`
            GROUP BY company_name
            ORDER BY total_deposits DESC
            LIMIT 10
        """, as_dict=True)
        
        # ===== BAR GRAPH DATA FOR PAYMENT STATUS BREAKDOWN =====
        payment_transaction_status = frappe.db.sql("""
            SELECT 
                payment_status,
                COUNT(*) as count,
                SUM(total_amount) as total_revenue
            FROM `tabPayment Transaction`
            GROUP BY payment_status
        """, as_dict=True)
        
        # ===== MONTHLY DEPOSIT TRENDS (Last 6 Months) =====
        monthly_deposit_trend = frappe.db.sql("""
            SELECT 
                DATE_FORMAT(deposit_paid_at, '%Y-%m') as month,
                COUNT(*) as transaction_count,
                SUM(deposit_amount) as monthly_revenue
            FROM `tabPayment Transaction`
            WHERE deposit_status = 'Paid'
            AND deposit_paid_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(deposit_paid_at, '%Y-%m')
            ORDER BY month ASC
        """, as_dict=True)
        
        # ===== DEPOSIT VS BALANCE PAYMENT COMPARISON =====
        payment_type_comparison = [
            {
                'payment_type': 'Deposits (10%)',
                'paid_count': deposit_paid_count,
                'paid_amount': float(deposit_paid_revenue),
                'unpaid_count': deposit_unpaid_count,
                'unpaid_amount': float(deposit_unpaid_amount)
            },
            {
                'payment_type': 'Balance (90%)',
                'paid_count': balance_paid_count,
                'paid_amount': float(balance_paid_revenue),
                'unpaid_count': balance_unpaid_count,
                'unpaid_amount': float(balance_unpaid_amount)
            }
        ]
        
        # Combined total revenue
        total_revenue = paid_revenue + total_request_payments_revenue
        
        # Payment status breakdown
        payment_status_breakdown = frappe.db.sql("""
            SELECT payment_status, COUNT(*) as count
            FROM `tabPayment`
            GROUP BY payment_status
        """, as_dict=True)
        
        # Subscription plan revenue breakdown (PAID ONLY)
        subscription_revenue_breakdown = frappe.db.sql("""
            SELECT subscription_plan, 
                   SUM(amount) as revenue,
                   COUNT(*) as count
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            AND subscription_plan IN ('Basic', 'Standard', 'Premium')
            GROUP BY subscription_plan
        """, as_dict=True)
        
        # Active subscriptions by plan (PAID ONLY)
        subscription_breakdown = frappe.db.sql("""
            SELECT subscription_plan, COUNT(*) as count
            FROM `tabLogistics Company`
            WHERE is_active = 1
            AND subscription_plan IN ('Basic', 'Standard', 'Premium')
            GROUP BY subscription_plan
        """, as_dict=True)
        
        # Recent activity
        recent_users = frappe.get_all('LocalMoves User',
            fields=['name', 'full_name', 'email', 'role', 'creation'],
            order_by='creation desc',
            limit=10
        )
        
        recent_companies = frappe.get_all('Logistics Company',
            fields=['name', 'company_name', 'manager_email', 'subscription_plan', 'created_at'],
            order_by='created_at desc',
            limit=10
        )
        
        recent_payments = frappe.get_all('Payment',
            fields=['name', 'company_name', 'amount', 'payment_status', 'subscription_plan', 'created_at', 'paid_date'],
            order_by='created_at desc',
            limit=10
        )
        
        recent_requests = frappe.get_all('Logistics Request',
            fields=['name', 'user_email', 'pickup_city', 'delivery_city', 'status', 'created_at'],
            order_by='created_at desc',
            limit=10
        )
        
        # Recent request payments
        recent_request_payments = frappe.get_all('Payment Transaction',
            fields=['name', 'request_id', 'company_name', 'total_amount', 'deposit_amount', 
                   'remaining_amount', 'payment_status', 'deposit_status', 'balance_status', 'created_at'],
            order_by='created_at desc',
            limit=10
        )
        
        # ===== TOP DEPOSIT PAYERS (Users with most deposits paid) =====
        top_deposit_payers = frappe.db.sql("""
            SELECT 
                user_email,
                COUNT(*) as total_deposits,
                SUM(deposit_amount) as total_deposit_amount,
                COUNT(CASE WHEN deposit_status = 'Paid' THEN 1 END) as paid_deposits
            FROM `tabPayment Transaction`
            WHERE deposit_status = 'Paid'
            GROUP BY user_email
            ORDER BY total_deposit_amount DESC
            LIMIT 10
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'totals': {
                    'users': total_users,
                    'companies': total_companies,
                    'paid_subscribers': paid_subscribers,
                    'requests': total_requests,
                    'total_payments': total_payments_count,
                    'total_payment_transactions': total_payment_transactions
                },
                'revenue': {
                    'total': float(total_revenue),
                    'subscription_revenue': float(paid_revenue),
                    'request_payments_revenue': float(total_request_payments_revenue),
                    'deposit_revenue': float(deposit_paid_revenue),
                    'balance_revenue': float(balance_paid_revenue),
                    'pending': float(pending_revenue),
                    'paid_count': len([p for p in payment_status_breakdown if p['payment_status'] == 'Paid']),
                    'pending_count': len([p for p in payment_status_breakdown if p['payment_status'] == 'Pending'])
                },
                
                # ===== DEPOSIT ANALYTICS SECTION =====
                'deposit_analytics': {
                    'summary': {
                        'total_transactions': total_payment_transactions,
                        'deposits_paid': deposit_paid_count,
                        'deposits_unpaid': deposit_unpaid_count,
                        'deposits_paid_revenue': float(deposit_paid_revenue),
                        'deposits_unpaid_amount': float(deposit_unpaid_amount),
                        'balance_paid': balance_paid_count,
                        'balance_unpaid': balance_unpaid_count,
                        'balance_paid_revenue': float(balance_paid_revenue),
                        'balance_unpaid_amount': float(balance_unpaid_amount),
                        'fully_paid_transactions': fully_paid_count,
                        'fully_paid_revenue': float(fully_paid_revenue)
                    },
                    
                    # Bar graph data - Daily deposits (last 30 days)
                    'daily_deposit_trend': deposit_trend,
                    
                    # Bar graph data - Monthly deposits (last 6 months)
                    'monthly_deposit_trend': monthly_deposit_trend,
                    
                    # Bar graph data - Deposits by company
                    'deposit_by_company': deposit_by_company,
                    
                    # Bar graph data - Payment status breakdown
                    'payment_status_distribution': payment_transaction_status,
                    
                    # Bar graph data - Deposit vs Balance comparison
                    'deposit_vs_balance': payment_type_comparison,
                    
                    # Top deposit payers
                    'top_payers': top_deposit_payers
                },
                
                'payment_breakdown': {
                    'by_status': payment_status_breakdown,
                    'by_subscription': subscription_revenue_breakdown
                },
                'subscriptions': subscription_breakdown,
                'recent': {
                    'users': recent_users,
                    'companies': recent_companies,
                    'payments': recent_payments,
                    'requests': recent_requests,
                    'request_payments': recent_request_payments
                }
            }
        }
    except Exception as e:
        frappe.log_error(f"Dashboard Stats Error: {str(e)}")
        return {'success': False, 'error': str(e)}
    
# @frappe.whitelist()
# def get_dashboard_stats():
#     """Get comprehensive dashboard statistics for admin INCLUDING PAYMENTS"""
#     try:
#         # Total counts
#         total_users = frappe.db.count('LocalMoves User', {'is_active': 1})
#         total_companies = frappe.db.count('Logistics Company')
        
#         # PAID SUBSCRIBERS ONLY (companies with paid plans)
#         paid_subscribers = frappe.db.count('Logistics Company', {
#             'subscription_plan': ['in', ['Basic', 'Standard', 'Premium']]
#         })
        
#         total_requests = frappe.db.count('Logistics Request')
        
#         # ===== PAYMENT STATISTICS =====
        
#         # Total payments and revenue
#         total_payments_count = frappe.db.count('Payment')
        
#         # Revenue from PAID payments only
#         paid_revenue = frappe.db.sql("""
#             SELECT COALESCE(SUM(amount), 0) as total
#             FROM `tabPayment`
#             WHERE payment_status = 'Paid'
#         """, as_dict=True)[0].total or 0
        
#         # Pending revenue
#         pending_revenue = frappe.db.sql("""
#             SELECT COALESCE(SUM(amount), 0) as total
#             FROM `tabPayment`
#             WHERE payment_status = 'Pending'
#         """, as_dict=True)[0].total or 0
        
#         # Revenue from request payments (Payment Transaction doctype)
#         request_deposit_revenue = frappe.db.sql("""
#             SELECT COALESCE(SUM(deposit_amount), 0) as total
#             FROM `tabPayment Transaction`
#             WHERE deposit_status = 'Paid'
#         """, as_dict=True)[0].total or 0
        
#         request_balance_revenue = frappe.db.sql("""
#             SELECT COALESCE(SUM(remaining_amount), 0) as total
#             FROM `tabPayment Transaction`
#             WHERE balance_status = 'Paid'
#         """, as_dict=True)[0].total or 0
        
#         total_request_payments_revenue = request_deposit_revenue + request_balance_revenue
        
#         # Combined total revenue
#         total_revenue = paid_revenue + total_request_payments_revenue
        
#         # Payment status breakdown
#         payment_status_breakdown = frappe.db.sql("""
#             SELECT payment_status, COUNT(*) as count
#             FROM `tabPayment`
#             GROUP BY payment_status
#         """, as_dict=True)
        
#         # Subscription plan revenue breakdown (PAID ONLY)
#         subscription_revenue_breakdown = frappe.db.sql("""
#             SELECT subscription_plan, 
#                    SUM(amount) as revenue,
#                    COUNT(*) as count
#             FROM `tabPayment`
#             WHERE payment_status = 'Paid'
#             AND subscription_plan IN ('Basic', 'Standard', 'Premium')
#             GROUP BY subscription_plan
#         """, as_dict=True)
        
#         # Active subscriptions by plan (PAID ONLY)
#         subscription_breakdown = frappe.db.sql("""
#             SELECT subscription_plan, COUNT(*) as count
#             FROM `tabLogistics Company`
#             WHERE is_active = 1
#             AND subscription_plan IN ('Basic', 'Standard', 'Premium')
#             GROUP BY subscription_plan
#         """, as_dict=True)
        
#         # Recent activity
#         recent_users = frappe.get_all('LocalMoves User',
#             fields=['name', 'full_name', 'email', 'role', 'creation'],
#             order_by='creation desc',
#             limit=10
#         )
        
#         recent_companies = frappe.get_all('Logistics Company',
#             fields=['name', 'company_name', 'manager_email', 'subscription_plan', 'created_at'],
#             order_by='created_at desc',
#             limit=10
#         )
        
#         recent_payments = frappe.get_all('Payment',
#             fields=['name', 'company_name', 'amount', 'payment_status', 'subscription_plan', 'created_at', 'paid_date'],
#             order_by='created_at desc',
#             limit=10
#         )
        
#         recent_requests = frappe.get_all('Logistics Request',
#             fields=['name', 'user_email', 'pickup_city', 'delivery_city', 'status', 'created_at'],
#             order_by='created_at desc',
#             limit=10
#         )
        
#         # Recent request payments
#         recent_request_payments = frappe.get_all('Payment Transaction',
#             fields=['name', 'request_id', 'company_name', 'total_amount', 'payment_status', 'created_at'],
#             order_by='created_at desc',
#             limit=10
#         )
        
#         return {
#             'success': True,
#             'data': {
#                 'totals': {
#                     'users': total_users,
#                     'companies': total_companies,
#                     'paid_subscribers': paid_subscribers,
#                     'requests': total_requests,
#                     'total_payments': total_payments_count
#                 },
#                 'revenue': {
#                     'total': float(total_revenue),
#                     'subscription_revenue': float(paid_revenue),
#                     'request_payments_revenue': float(total_request_payments_revenue),
#                     'pending': float(pending_revenue),
#                     'paid_count': len([p for p in payment_status_breakdown if p['payment_status'] == 'Paid']),
#                     'pending_count': len([p for p in payment_status_breakdown if p['payment_status'] == 'Pending'])
#                 },
#                 'payment_breakdown': {
#                     'by_status': payment_status_breakdown,
#                     'by_subscription': subscription_revenue_breakdown
#                 },
#                 'subscriptions': subscription_breakdown,
#                 'recent': {
#                     'users': recent_users,
#                     'companies': recent_companies,
#                     'payments': recent_payments,
#                     'requests': recent_requests,
#                     'request_payments': recent_request_payments
#                 }
#             }
#         }
#     except Exception as e:
#         frappe.log_error(f"Dashboard Stats Error: {str(e)}")
#         return {'success': False, 'error': str(e)}


# ===== PAYMENT CHARTS =====

@frappe.whitelist()
def get_payment_revenue_chart():
    """Get payment revenue data for charts (7 days, 1 month, 1 year)"""
    try:
        # Last 7 days
        seven_days = frappe.db.sql("""
            SELECT DATE(paid_date) as date, 
                   SUM(amount) as revenue,
                   COUNT(*) as count
            FROM `tabPayment`
            WHERE payment_status = 'Paid' 
            AND paid_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(paid_date)
            ORDER BY date ASC
        """, as_dict=True)
        
        # Last 30 days
        month_data = frappe.db.sql("""
            SELECT DATE(paid_date) as date, 
                   SUM(amount) as revenue,
                   COUNT(*) as count
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            AND paid_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(paid_date)
            ORDER BY date ASC
        """, as_dict=True)
        
        # Last 12 months
        year_data = frappe.db.sql("""
            SELECT DATE_FORMAT(paid_date, '%Y-%m') as month, 
                   SUM(amount) as revenue,
                   COUNT(*) as count
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            AND paid_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(paid_date, '%Y-%m')
            ORDER BY month ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'seven_days': seven_days,
                'one_month': month_data,
                'one_year': year_data
            }
        }
    except Exception as e:
        frappe.log_error(f"Payment Revenue Chart Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def get_subscription_revenue_chart():
    """Get revenue breakdown by subscription plan over time"""
    try:
        # Last 12 months by plan
        monthly_plan_revenue = frappe.db.sql("""
            SELECT 
                DATE_FORMAT(paid_date, '%Y-%m') as month,
                subscription_plan,
                SUM(amount) as revenue,
                COUNT(*) as count
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            AND paid_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            AND subscription_plan IN ('Basic', 'Standard', 'Premium')
            GROUP BY DATE_FORMAT(paid_date, '%Y-%m'), subscription_plan
            ORDER BY month ASC, subscription_plan
        """, as_dict=True)
        
        # Current month breakdown
        current_month_breakdown = frappe.db.sql("""
            SELECT 
                subscription_plan,
                SUM(amount) as revenue,
                COUNT(*) as count
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            AND MONTH(paid_date) = MONTH(CURDATE())
            AND YEAR(paid_date) = YEAR(CURDATE())
            AND subscription_plan IN ('Basic', 'Standard', 'Premium')
            GROUP BY subscription_plan
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'monthly_by_plan': monthly_plan_revenue,
                'current_month': current_month_breakdown
            }
        }
    except Exception as e:
        frappe.log_error(f"Subscription Revenue Chart Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def get_payment_status_chart():
    """Get payment status distribution over time"""
    try:
        # Daily payment status for last 30 days
        daily_status = frappe.db.sql("""
            SELECT 
                DATE(created_at) as date,
                payment_status,
                COUNT(*) as count,
                SUM(amount) as total_amount
            FROM `tabPayment`
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(created_at), payment_status
            ORDER BY date ASC
        """, as_dict=True)
        
        # Overall status distribution
        overall_status = frappe.db.sql("""
            SELECT 
                payment_status,
                COUNT(*) as count,
                SUM(amount) as total_amount
            FROM `tabPayment`
            GROUP BY payment_status
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'daily_status': daily_status,
                'overall_status': overall_status
            }
        }
    except Exception as e:
        frappe.log_error(f"Payment Status Chart Error: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def get_request_payment_chart():
    """Get request payment (deposit + balance) statistics over time"""
    try:
        # Last 30 days
        daily_request_payments = frappe.db.sql("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total_transactions,
                SUM(CASE WHEN deposit_status = 'Paid' THEN deposit_amount ELSE 0 END) as deposit_revenue,
                SUM(CASE WHEN balance_status = 'Paid' THEN remaining_amount ELSE 0 END) as balance_revenue,
                SUM(CASE WHEN payment_status = 'Fully Paid' THEN total_amount ELSE 0 END) as fully_paid_revenue
            FROM `tabPayment Transaction`
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """, as_dict=True)
        
        # Last 12 months
        monthly_request_payments = frappe.db.sql("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                COUNT(*) as total_transactions,
                SUM(CASE WHEN deposit_status = 'Paid' THEN deposit_amount ELSE 0 END) as deposit_revenue,
                SUM(CASE WHEN balance_status = 'Paid' THEN remaining_amount ELSE 0 END) as balance_revenue,
                SUM(CASE WHEN payment_status = 'Fully Paid' THEN total_amount ELSE 0 END) as fully_paid_revenue
            FROM `tabPayment Transaction`
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'daily': daily_request_payments,
                'monthly': monthly_request_payments
            }
        }
    except Exception as e:
        frappe.log_error(f"Request Payment Chart Error: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def get_combined_revenue_chart():
    """Get combined revenue from subscriptions and request payments"""
    try:
        # Last 12 months combined
        monthly_combined = frappe.db.sql("""
            SELECT 
                month,
                SUM(subscription_revenue) as subscription_revenue,
                SUM(request_payment_revenue) as request_payment_revenue,
                SUM(total_revenue) as total_revenue
            FROM (
                SELECT 
                    DATE_FORMAT(paid_date, '%Y-%m') as month,
                    SUM(amount) as subscription_revenue,
                    0 as request_payment_revenue,
                    SUM(amount) as total_revenue
                FROM `tabPayment`
                WHERE payment_status = 'Paid'
                AND paid_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                GROUP BY DATE_FORMAT(paid_date, '%Y-%m')
                
                UNION ALL
                
                SELECT 
                    DATE_FORMAT(created_at, '%Y-%m') as month,
                    0 as subscription_revenue,
                    SUM(CASE WHEN deposit_status = 'Paid' THEN deposit_amount ELSE 0 END) +
                    SUM(CASE WHEN balance_status = 'Paid' THEN remaining_amount ELSE 0 END) as request_payment_revenue,
                    SUM(CASE WHEN deposit_status = 'Paid' THEN deposit_amount ELSE 0 END) +
                    SUM(CASE WHEN balance_status = 'Paid' THEN remaining_amount ELSE 0 END) as total_revenue
                FROM `tabPayment Transaction`
                WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ) combined_data
            GROUP BY month
            ORDER BY month ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'monthly_combined': monthly_combined
            }
        }
    except Exception as e:
        frappe.log_error(f"Combined Revenue Chart Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def get_payment_analytics():
    """Get detailed payment analytics"""
    try:
        # Top paying companies
        top_companies = frappe.db.sql("""
            SELECT 
                company_name,
                COUNT(*) as payment_count,
                SUM(amount) as total_paid,
                MAX(paid_date) as last_payment_date
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            GROUP BY company_name
            ORDER BY total_paid DESC
            LIMIT 10
        """, as_dict=True)
        
        # Payment method distribution
        payment_methods = frappe.db.sql("""
            SELECT 
                payment_method,
                COUNT(*) as count,
                SUM(amount) as total_amount
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            AND payment_method IS NOT NULL
            GROUP BY payment_method
        """, as_dict=True)
        
        # Average payment by plan
        avg_by_plan = frappe.db.sql("""
            SELECT 
                subscription_plan,
                AVG(amount) as avg_amount,
                MIN(amount) as min_amount,
                MAX(amount) as max_amount,
                COUNT(*) as count
            FROM `tabPayment`
            WHERE payment_status = 'Paid'
            AND subscription_plan IN ('Basic', 'Standard', 'Premium')
            GROUP BY subscription_plan
        """, as_dict=True)
        
        # MRR (Monthly Recurring Revenue) calculation
        active_subscriptions = frappe.db.sql("""
            SELECT 
                subscription_plan,
                COUNT(*) as count
            FROM `tabLogistics Company`
            WHERE is_active = 1
            AND subscription_end_date >= CURDATE()
            AND subscription_plan IN ('Basic', 'Standard', 'Premium')
            GROUP BY subscription_plan
        """, as_dict=True)
        
        # Calculate MRR based on plan pricing (from payment.py)
        plan_prices = {
            'Basic': 999,
            'Standard': 4999,
            'Premium': 14999
        }
        
        mrr = sum([
            sub['count'] * plan_prices.get(sub['subscription_plan'], 0)
            for sub in active_subscriptions
        ])
        
        return {
            'success': True,
            'analytics': {
                'top_companies': top_companies,
                'payment_methods': payment_methods,
                'average_by_plan': avg_by_plan,
                'active_subscriptions': active_subscriptions,
                'mrr': mrr,
                'arr': mrr * 12  # Annual Recurring Revenue
            }
        }
    except Exception as e:
        frappe.log_error(f"Payment Analytics Error: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def get_user_growth_chart():
    """Get user growth data for charts (7 days, 1 month, 1 year)"""
    try:
        seven_days_data = frappe.db.sql("""
            SELECT DATE(creation) as date, COUNT(*) as count
            FROM `tabLocalMoves User`
            WHERE creation >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY DATE(creation)
            ORDER BY date ASC
        """, as_dict=True)
        
        month_data = frappe.db.sql("""
            SELECT DATE(creation) as date, COUNT(*) as count
            FROM `tabLocalMoves User`
            WHERE creation >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY DATE(creation)
            ORDER BY date ASC
        """, as_dict=True)
        
        year_data = frappe.db.sql("""
            SELECT DATE_FORMAT(creation, '%Y-%m') as month, COUNT(*) as count
            FROM `tabLocalMoves User`
            WHERE creation >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(creation, '%Y-%m')
            ORDER BY month ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'data': {
                'seven_days': seven_days_data,
                'one_month': month_data,
                'one_year': year_data
            }
        }
    except Exception as e:
        frappe.log_error(f"User Growth Chart Error: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def get_revenue_chart():
    """Get revenue data for charts - ALIAS for get_payment_revenue_chart"""
    return get_payment_revenue_chart()

# ===== COMPANY CRUD OPERATIONS =====

# ===== ADMIN COMPANY CRUD OPERATIONS =====
# Add these functions to your dashboard.py file
# Replace the existing get_all_companies, get_company, create_company, update_company, delete_company

import json

def process_json_array(data, field_name):
    """Process JSON array field - returns JSON string for storage"""
    if not data:
        return "[]"
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return data
        except:
            pass
        return "[]"
    if isinstance(data, list):
        return json.dumps(data)
    return "[]"

def parse_company_json_fields(company):
    """Parse all JSON fields in company dict"""
    if not company or not isinstance(company, dict):
        return company
    
    json_fields = [
        "areas_covered", "company_gallery", "includes", "material", 
        "protection", "furniture", "appliances",
        "swb_van_images", "mwb_van_images", "lwb_van_images", "xlwb_van_images",
        "mwb_luton_van_images", "lwb_luton_van_images", "tonne_7_5_lorry_images",
        "tonne_12_lorry_images", "tonne_18_lorry_images"
    ]
    
    for field in json_fields:
        if field in company and company[field]:
            try:
                if isinstance(company[field], str):
                    company[field] = json.loads(company[field])
            except:
                company[field] = []
        else:
            company[field] = []
    
    return company


@frappe.whitelist(allow_guest=False)
def get_all_companies():
    """Get all companies with complete information including ratings - Admin only"""
    try:
        # Admin permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        # Get all companies with ALL fields
        companies = frappe.get_all('Logistics Company',
            fields=[
                # Basic Details
                'name', 'company_name', 'manager_email', 'phone', 'personal_contact_name',
                'pincode', 'location', 'address', 'description', 'services_offered',
                
                # Service Areas & Gallery
                'areas_covered', 'company_gallery',
                
                # Includes
                'includes', 'material', 'protection', 'furniture', 'appliances',
                
                # Fleet Quantities
                'swb_van_quantity', 'mwb_van_quantity', 'lwb_van_quantity', 'xlwb_van_quantity',
                'mwb_luton_van_quantity', 'lwb_luton_van_quantity', 
                'tonne_7_5_lorry_quantity', 'tonne_12_lorry_quantity', 'tonne_18_lorry_quantity',
                
                # Fleet Images
                'swb_van_images', 'mwb_van_images', 'lwb_van_images', 'xlwb_van_images',
                'mwb_luton_van_images', 'lwb_luton_van_images',
                'tonne_7_5_lorry_images', 'tonne_12_lorry_images', 'tonne_18_lorry_images',
                
                # Fleet Summary
                'total_carrying_capacity',
                
                # Pricing
                'loading_cost_per_m3', 'packing_cost_per_box', 
                'assembly_cost_per_item', 'disassembly_cost_per_item',
                'cost_per_mile_under_25', 'cost_per_mile_over_25',
                
                # Subscription
                'subscription_plan', 'subscription_start_date', 'subscription_end_date',
                'requests_viewed_this_month', 'is_active',
                
                # Ratings & Reviews
                'average_rating', 'total_ratings',
                
                # Timestamps
                'created_at', 'updated_at'
            ],
            order_by='created_at desc'
        )
        
        # Parse JSON fields and get reviews for each company
        for company in companies:
            parse_company_json_fields(company)
            
            # Get recent reviews for this company
            recent_reviews = frappe.db.sql("""
                SELECT 
                    name as request_id,
                    full_name as user_name,
                    rating,
                    review_comment,
                    rated_at
                FROM `tabLogistics Request`
                WHERE company_name = %(company_name)s
                AND rating IS NOT NULL
                AND rating > 0
                ORDER BY rated_at DESC
                LIMIT 5
            """, {"company_name": company['company_name']}, as_dict=True)
            
            company['recent_reviews'] = recent_reviews
        
        return {
            'success': True, 
            'data': companies, 
            'count': len(companies)
        }
        
    except Exception as e:
        frappe.log_error(f"Get All Companies Error: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist(allow_guest=False)
def get_company():
    """Get a single company by ID with complete information - Admin only"""
    try:
        # Admin permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        # ✅ FIX: Use get_request_data() instead of form_dict
        data = get_request_data()
        company_id = data.get('company_id')
        
        if not company_id:
            return {
                'success': False, 
                'message': 'Company ID is required',
                'debug': {
                    'received_data': data,
                    'data_type': type(data).__name__
                }
            }

        if not frappe.db.exists('Logistics Company', company_id):
            return {'success': False, 'message': 'Company not found'}
        
        # Get company document with all fields
        company = frappe.get_doc('Logistics Company', company_id)
        company_dict = company.as_dict()
        
        # Parse JSON fields
        parse_company_json_fields(company_dict)
        
        # Get ALL reviews for this company
        all_reviews = frappe.db.sql("""
            SELECT 
                name as request_id,
                user_email,
                full_name as user_name,
                rating,
                review_comment,
                service_aspects,
                rated_at,
                pickup_city,
                delivery_city,
                status
            FROM `tabLogistics Request`
            WHERE company_name = %(company_name)s
            AND rating IS NOT NULL
            AND rating > 0
            ORDER BY rated_at DESC
        """, {"company_name": company_dict['company_name']}, as_dict=True)
        
        # Parse service_aspects JSON
        for review in all_reviews:
            review['rated_at'] = str(review['rated_at'])
            if review.get('service_aspects'):
                try:
                    review['service_aspects'] = json.loads(review['service_aspects'])
                except:
                    review['service_aspects'] = {}
        
        company_dict['all_reviews'] = all_reviews
        
        # Get rating statistics
        rating_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_ratings,
                AVG(rating) as avg_rating,
                SUM(CASE WHEN rating = 5 THEN 1 ELSE 0 END) as five_star,
                SUM(CASE WHEN rating = 4 THEN 1 ELSE 0 END) as four_star,
                SUM(CASE WHEN rating = 3 THEN 1 ELSE 0 END) as three_star,
                SUM(CASE WHEN rating = 2 THEN 1 ELSE 0 END) as two_star,
                SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END) as one_star
            FROM `tabLogistics Request`
            WHERE company_name = %(company_name)s
            AND rating IS NOT NULL
            AND rating > 0
        """, {"company_name": company_dict['company_name']}, as_dict=True)
        
        company_dict['rating_statistics'] = rating_stats[0] if rating_stats else {}
        
        # Get request statistics
        request_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_requests,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_requests,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending_requests,
                SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) as cancelled_requests
            FROM `tabLogistics Request`
            WHERE company_name = %(company_name)s
        """, {"company_name": company_dict['company_name']}, as_dict=True)
        
        company_dict['request_statistics'] = request_stats[0] if request_stats else {}
        
        return {'success': True, 'data': company_dict}
        
    except Exception as e:
        frappe.log_error(f"Get Company Error: {str(e)}")
        return {'success': False, 'error': str(e)}


# @frappe.whitelist(allow_guest=False)
# def create_company():
#     """Create a new company with ALL fields - Admin only"""
#     try:
#         ensure_session_data()
        
#         # Admin permission check
#         if not check_admin_permission():
#             return {
#                 'success': False, 
#                 'message': 'Access Denied: Admin permission required'
#             }
        
#         data = get_request_data()
        
#         # Check if company already exists
#         if frappe.db.exists('Logistics Company', {'company_name': data.get('company_name')}):
#             return {'success': False, 'message': 'Company with this name already exists'}
        
#         # Validate required fields
#         required_fields = ['company_name', 'manager_email', 'phone', 'pincode', 'location', 'address']
#         for field in required_fields:
#             if not data.get(field):
#                 return {'success': False, 'message': f'{field} is required'}
        
#         # Create company document
#         company_doc = frappe.new_doc('Logistics Company')
        
#         # Basic Details
#         company_doc.company_name = data.get('company_name')
#         company_doc.manager_email = data.get('manager_email')
#         company_doc.phone = data.get('phone')
#         company_doc.personal_contact_name = data.get('personal_contact_name', '')
#         company_doc.pincode = data.get('pincode')
#         company_doc.location = data.get('location')
#         company_doc.address = data.get('address')
#         company_doc.description = data.get('description', '')
#         company_doc.services_offered = data.get('services_offered', '')
        
#         # Service Areas & Gallery (JSON)
#         company_doc.areas_covered = process_json_array(data.get('areas_covered'), 'areas_covered')
#         company_doc.company_gallery = process_json_array(data.get('company_gallery'), 'company_gallery')
        
#         # Includes (JSON)
#         company_doc.includes = process_json_array(data.get('includes'), 'includes')
#         company_doc.material = process_json_array(data.get('material'), 'material')
#         company_doc.protection = process_json_array(data.get('protection'), 'protection')
#         company_doc.furniture = process_json_array(data.get('furniture'), 'furniture')
#         company_doc.appliances = process_json_array(data.get('appliances'), 'appliances')
        
#         # Fleet Quantities
#         company_doc.swb_van_quantity = int(data.get('swb_van_quantity', 0) or 0)
#         company_doc.mwb_van_quantity = int(data.get('mwb_van_quantity', 0) or 0)
#         company_doc.lwb_van_quantity = int(data.get('lwb_van_quantity', 0) or 0)
#         company_doc.xlwb_van_quantity = int(data.get('xlwb_van_quantity', 0) or 0)
#         company_doc.mwb_luton_van_quantity = int(data.get('mwb_luton_van_quantity', 0) or 0)
#         company_doc.lwb_luton_van_quantity = int(data.get('lwb_luton_van_quantity', 0) or 0)
#         company_doc.tonne_7_5_lorry_quantity = int(data.get('tonne_7_5_lorry_quantity', 0) or 0)
#         company_doc.tonne_12_lorry_quantity = int(data.get('tonne_12_lorry_quantity', 0) or 0)
#         company_doc.tonne_18_lorry_quantity = int(data.get('tonne_18_lorry_quantity', 0) or 0)
        
#         # Fleet Images (JSON)
#         company_doc.swb_van_images = process_json_array(data.get('swb_van_images'), 'swb_van_images')
#         company_doc.mwb_van_images = process_json_array(data.get('mwb_van_images'), 'mwb_van_images')
#         company_doc.lwb_van_images = process_json_array(data.get('lwb_van_images'), 'lwb_van_images')
#         company_doc.xlwb_van_images = process_json_array(data.get('xlwb_van_images'), 'xlwb_van_images')
#         company_doc.mwb_luton_van_images = process_json_array(data.get('mwb_luton_van_images'), 'mwb_luton_van_images')
#         company_doc.lwb_luton_van_images = process_json_array(data.get('lwb_luton_van_images'), 'lwb_luton_van_images')
#         company_doc.tonne_7_5_lorry_images = process_json_array(data.get('tonne_7_5_lorry_images'), 'tonne_7_5_lorry_images')
#         company_doc.tonne_12_lorry_images = process_json_array(data.get('tonne_12_lorry_images'), 'tonne_12_lorry_images')
#         company_doc.tonne_18_lorry_images = process_json_array(data.get('tonne_18_lorry_images'), 'tonne_18_lorry_images')
        
#         # Calculate total carrying capacity
#         capacities = {
#             'swb_van_quantity': 5, 'mwb_van_quantity': 8, 'lwb_van_quantity': 11,
#             'xlwb_van_quantity': 13, 'mwb_luton_van_quantity': 17, 'lwb_luton_van_quantity': 19,
#             'tonne_7_5_lorry_quantity': 30, 'tonne_12_lorry_quantity': 45, 'tonne_18_lorry_quantity': 55
#         }
#         total_capacity = sum(int(data.get(field, 0) or 0) * capacity 
#                            for field, capacity in capacities.items())
#         company_doc.total_carrying_capacity = total_capacity
        
#         # Pricing
#         company_doc.loading_cost_per_m3 = float(data.get('loading_cost_per_m3', 0) or 0)
#         company_doc.packing_cost_per_box = float(data.get('packing_cost_per_box', 0) or 0)
#         company_doc.assembly_cost_per_item = float(data.get('assembly_cost_per_item', 0) or 0)
        
#         # Auto-calculate disassembly (50% of assembly if not provided)
#         disassembly = float(data.get('disassembly_cost_per_item', 0) or 0)
#         if not disassembly and company_doc.assembly_cost_per_item:
#             disassembly = company_doc.assembly_cost_per_item * 0.5
#         company_doc.disassembly_cost_per_item = disassembly
        
#         company_doc.cost_per_mile_under_25 = float(data.get('cost_per_mile_under_25', 0) or 0)
#         company_doc.cost_per_mile_over_25 = float(data.get('cost_per_mile_over_25', 0) or 0)
        
#         # Subscription
#         company_doc.subscription_plan = data.get('subscription_plan', 'Free')
#         company_doc.subscription_start_date = data.get('subscription_start_date')
#         company_doc.subscription_end_date = data.get('subscription_end_date')
#         company_doc.requests_viewed_this_month = 0
#         company_doc.is_active = int(data.get('is_active', 1))
        
#         # Ratings (initialized to 0)
#         company_doc.average_rating = 0
#         company_doc.total_ratings = 0
        
#         # Timestamps
#         company_doc.created_at = datetime.now()
#         company_doc.updated_at = datetime.now()
        
#         # Insert
#         company_doc.flags.ignore_version = True
#         company_doc.insert(ignore_permissions=True)
#         frappe.db.commit()
        
#         # Parse response
#         result = company_doc.as_dict()
#         parse_company_json_fields(result)
        
#         return {
#             'success': True, 
#             'message': 'Company created successfully', 
#             'data': result
#         }
        
#     except Exception as e:
#         frappe.log_error(f"Create Company Error: {str(e)}")
#         frappe.db.rollback()
#         return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def create_company():
    """
    Create a new company with ALL fields - Admin only
    
    AUTOMATIC USER CREATION:
    If manager_email doesn't exist as a user, a new Logistics Manager user will be created automatically.
    
    Required fields for NEW USER (if manager_email doesn't exist):
    - manager_email (will become user email)
    - password (for the new user)
    - phone (for the new user)
    - personal_contact_name (will become user full_name)
    
    Required fields for COMPANY:
    - company_name, pincode, location, address
    
    Optional user fields (if creating new user):
    - user_city, user_state, user_address, user_pincode
    """
    try:
        ensure_session_data()
        
        # Admin permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        data = get_request_data()
        
        # ===== VALIDATE REQUIRED COMPANY FIELDS =====
        required_company_fields = ['company_name', 'manager_email', 'pincode', 'location', 'address']
        missing_fields = [field for field in required_company_fields if not data.get(field)]
        
        if missing_fields:
            return {
                'success': False, 
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }
        
        manager_email = data.get('manager_email')
        
        # ===== CHECK IF COMPANY NAME ALREADY EXISTS =====
        if frappe.db.exists('Logistics Company', {'company_name': data.get('company_name')}):
            return {
                'success': False, 
                'message': f'Company "{data.get("company_name")}" already exists'
            }
        
        # ===== CHECK IF USER EXISTS =====
        user_exists = frappe.db.get_value('LocalMoves User', 
            {'email': manager_email}, 
            ['name', 'role', 'is_active', 'full_name', 'phone'], 
            as_dict=True)
        
        user_created = False
        user_id = None
        
        if not user_exists:
            # ===== USER DOESN'T EXIST - CREATE NEW USER =====
            
            # Validate required fields for new user
            required_user_fields = ['password', 'phone']
            missing_user_fields = [f for f in required_user_fields if not data.get(f)]
            
            if missing_user_fields:
                return {
                    'success': False,
                    'message': f'User with email "{manager_email}" does not exist. To create new user, provide: {", ".join(missing_user_fields)}'
                }
            
            # Check if phone already exists
            if frappe.db.exists('LocalMoves User', {'phone': data.get('phone')}):
                return {
                    'success': False, 
                    'message': f'User with phone "{data.get("phone")}" already exists'
                }
            
            # Create new user
            user_doc = frappe.new_doc('LocalMoves User')
            user_doc.email = manager_email
            user_doc.full_name = data.get('personal_contact_name') or data.get('company_name')
            user_doc.phone = data.get('phone')
            user_doc.password = data.get('password')
            user_doc.role = 'Logistics Manager'  # FIXED ROLE
            
            # Optional user fields
            user_doc.city = data.get('user_city', '')
            user_doc.state = data.get('user_state', '')
            user_doc.address = data.get('user_address', data.get('address', ''))
            user_doc.pincode = data.get('user_pincode', data.get('pincode', ''))
            user_doc.is_active = 1
            user_doc.is_phone_verified = 0
            
            # Insert user
            user_doc.flags.ignore_version = True
            user_doc.insert(ignore_permissions=True)
            
            user_created = True
            user_id = user_doc.name
            
            frappe.msgprint(f"New Logistics Manager user created: {manager_email}")
        
        else:
            # ===== USER EXISTS - VALIDATE =====
            
            # Check if user is active
            if not user_exists.is_active:
                return {
                    'success': False,
                    'message': f'User account "{manager_email}" is inactive'
                }
            
            # Check if user is Logistics Manager
            if user_exists.role != 'Logistics Manager':
                return {
                    'success': False,
                    'message': f'User "{manager_email}" must have role "Logistics Manager", current role is: {user_exists.role}'
                }
            
            # Check if user already has a company
            existing_company = frappe.db.get_value('Logistics Company', 
                {'manager_email': manager_email}, 
                'company_name')
            
            if existing_company:
                return {
                    'success': False,
                    'message': f'User "{manager_email}" already has a company: {existing_company}'
                }
            
            user_id = user_exists.name
        
        # ===== CREATE COMPANY =====
        
        company_doc = frappe.new_doc('Logistics Company')
        
        # Link to user
        company_doc.manager_email = manager_email
        
        # Use existing user data if available, else use provided data
        if user_exists:
            company_doc.personal_contact_name = data.get('personal_contact_name', user_exists.full_name)
            company_doc.phone = data.get('phone', user_exists.phone)
        else:
            company_doc.personal_contact_name = data.get('personal_contact_name') or data.get('company_name')
            company_doc.phone = data.get('phone')
        
        # Basic Details
        company_doc.company_name = data.get('company_name')
        company_doc.pincode = data.get('pincode')
        company_doc.location = data.get('location')
        company_doc.address = data.get('address')
        company_doc.description = data.get('description', '')
        company_doc.services_offered = data.get('services_offered', '')
        
        # Service Areas & Gallery (JSON)
        company_doc.areas_covered = process_json_array(data.get('areas_covered'), 'areas_covered')
        company_doc.company_gallery = process_json_array(data.get('company_gallery'), 'company_gallery')
        
        # Includes (JSON)
        company_doc.includes = process_json_array(data.get('includes'), 'includes')
        company_doc.material = process_json_array(data.get('material'), 'material')
        company_doc.protection = process_json_array(data.get('protection'), 'protection')
        company_doc.furniture = process_json_array(data.get('furniture'), 'furniture')
        company_doc.appliances = process_json_array(data.get('appliances'), 'appliances')
        
        # Fleet Quantities
        company_doc.swb_van_quantity = int(data.get('swb_van_quantity', 0) or 0)
        company_doc.mwb_van_quantity = int(data.get('mwb_van_quantity', 0) or 0)
        company_doc.lwb_van_quantity = int(data.get('lwb_van_quantity', 0) or 0)
        company_doc.xlwb_van_quantity = int(data.get('xlwb_van_quantity', 0) or 0)
        company_doc.mwb_luton_van_quantity = int(data.get('mwb_luton_van_quantity', 0) or 0)
        company_doc.lwb_luton_van_quantity = int(data.get('lwb_luton_van_quantity', 0) or 0)
        company_doc.tonne_7_5_lorry_quantity = int(data.get('tonne_7_5_lorry_quantity', 0) or 0)
        company_doc.tonne_12_lorry_quantity = int(data.get('tonne_12_lorry_quantity', 0) or 0)
        company_doc.tonne_18_lorry_quantity = int(data.get('tonne_18_lorry_quantity', 0) or 0)
        
        # Fleet Images (JSON)
        company_doc.swb_van_images = process_json_array(data.get('swb_van_images'), 'swb_van_images')
        company_doc.mwb_van_images = process_json_array(data.get('mwb_van_images'), 'mwb_van_images')
        company_doc.lwb_van_images = process_json_array(data.get('lwb_van_images'), 'lwb_van_images')
        company_doc.xlwb_van_images = process_json_array(data.get('xlwb_van_images'), 'xlwb_van_images')
        company_doc.mwb_luton_van_images = process_json_array(data.get('mwb_luton_van_images'), 'mwb_luton_van_images')
        company_doc.lwb_luton_van_images = process_json_array(data.get('lwb_luton_van_images'), 'lwb_luton_van_images')
        company_doc.tonne_7_5_lorry_images = process_json_array(data.get('tonne_7_5_lorry_images'), 'tonne_7_5_lorry_images')
        company_doc.tonne_12_lorry_images = process_json_array(data.get('tonne_12_lorry_images'), 'tonne_12_lorry_images')
        company_doc.tonne_18_lorry_images = process_json_array(data.get('tonne_18_lorry_images'), 'tonne_18_lorry_images')
        
        # Calculate total carrying capacity
        capacities = {
            'swb_van_quantity': 5, 'mwb_van_quantity': 8, 'lwb_van_quantity': 11,
            'xlwb_van_quantity': 13, 'mwb_luton_van_quantity': 17, 'lwb_luton_van_quantity': 19,
            'tonne_7_5_lorry_quantity': 30, 'tonne_12_lorry_quantity': 45, 'tonne_18_lorry_quantity': 55
        }
        total_capacity = sum(int(data.get(field, 0) or 0) * capacity 
                           for field, capacity in capacities.items())
        company_doc.total_carrying_capacity = total_capacity
        
        # Pricing
        company_doc.loading_cost_per_m3 = float(data.get('loading_cost_per_m3', 0) or 0)
        company_doc.packing_cost_per_box = float(data.get('packing_cost_per_box', 0) or 0)
        company_doc.assembly_cost_per_item = float(data.get('assembly_cost_per_item', 0) or 0)
        
        # Auto-calculate disassembly (50% of assembly if not provided)
        disassembly = float(data.get('disassembly_cost_per_item', 0) or 0)
        if not disassembly and company_doc.assembly_cost_per_item:
            disassembly = company_doc.assembly_cost_per_item * 0.5
        company_doc.disassembly_cost_per_item = disassembly
        
        company_doc.cost_per_mile_under_25 = float(data.get('cost_per_mile_under_25', 0) or 0)
        company_doc.cost_per_mile_over_25 = float(data.get('cost_per_mile_over_25', 0) or 0)
        
        # Subscription
        company_doc.subscription_plan = data.get('subscription_plan', 'Free')
        company_doc.subscription_start_date = data.get('subscription_start_date')
        company_doc.subscription_end_date = data.get('subscription_end_date')
        company_doc.requests_viewed_this_month = 0
        company_doc.is_active = int(data.get('is_active', 1))
        
        # Ratings (initialized to 0)
        company_doc.average_rating = 0
        company_doc.total_ratings = 0
        
        # Timestamps
        company_doc.created_at = datetime.now()
        company_doc.updated_at = datetime.now()
        
        # Insert
        company_doc.flags.ignore_version = True
        company_doc.insert(ignore_permissions=True)
        
        # Commit both in same transaction
        frappe.db.commit()
        
        # Parse response
        result = company_doc.as_dict()
        parse_company_json_fields(result)
        
        response = {
            'success': True, 
            'message': f'Company created successfully{"and new user created" if user_created else ""}',
            'data': result
        }
        
        if user_created:
            response['user_created'] = {
                'user_id': user_id,
                'email': manager_email,
                'role': 'Logistics Manager',
                'message': 'New Logistics Manager user was created automatically'
            }
        
        return response
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        frappe.log_error(
            title="Create Company Error",
            message=f"Error: {str(e)}\n\nTraceback:\n{error_trace}"
        )
        frappe.db.rollback()
        return {
            'success': False, 
            'error': str(e),
            'traceback': error_trace
        }

@frappe.whitelist(allow_guest=False)
def update_company():
    """Update company with ALL fields - Admin only"""
    try:
        ensure_session_data()
        
        # Admin permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        data = get_request_data()
        company_name = data.get('company_name')
        
        if not company_name:
            return {'success': False, 'message': 'company_name is required'}
        
        if not frappe.db.exists('Logistics Company', company_name):
            return {'success': False, 'message': 'Company not found'}
        
        company_doc = frappe.get_doc('Logistics Company', company_name)
        
        # Basic Details
        if 'phone' in data:
            company_doc.phone = data['phone']
        if 'personal_contact_name' in data:
            company_doc.personal_contact_name = data['personal_contact_name']
        if 'pincode' in data:
            company_doc.pincode = data['pincode']
        if 'location' in data:
            company_doc.location = data['location']
        if 'address' in data:
            company_doc.address = data['address']
        if 'description' in data:
            company_doc.description = data['description']
        if 'services_offered' in data:
            company_doc.services_offered = data['services_offered']
        
        # Service Areas & Gallery
        if 'areas_covered' in data:
            company_doc.areas_covered = process_json_array(data['areas_covered'], 'areas_covered')
        if 'company_gallery' in data:
            company_doc.company_gallery = process_json_array(data['company_gallery'], 'company_gallery')
        
        # Includes
        if 'includes' in data:
            company_doc.includes = process_json_array(data['includes'], 'includes')
        if 'material' in data:
            company_doc.material = process_json_array(data['material'], 'material')
        if 'protection' in data:
            company_doc.protection = process_json_array(data['protection'], 'protection')
        if 'furniture' in data:
            company_doc.furniture = process_json_array(data['furniture'], 'furniture')
        if 'appliances' in data:
            company_doc.appliances = process_json_array(data['appliances'], 'appliances')
        
        # Fleet Quantities
        fleet_fields = [
            'swb_van_quantity', 'mwb_van_quantity', 'lwb_van_quantity', 'xlwb_van_quantity',
            'mwb_luton_van_quantity', 'lwb_luton_van_quantity',
            'tonne_7_5_lorry_quantity', 'tonne_12_lorry_quantity', 'tonne_18_lorry_quantity'
        ]
        for field in fleet_fields:
            if field in data:
                setattr(company_doc, field, int(data[field] or 0))
        
        # Fleet Images
        image_fields = [
            'swb_van_images', 'mwb_van_images', 'lwb_van_images', 'xlwb_van_images',
            'mwb_luton_van_images', 'lwb_luton_van_images',
            'tonne_7_5_lorry_images', 'tonne_12_lorry_images', 'tonne_18_lorry_images'
        ]
        for field in image_fields:
            if field in data:
                setattr(company_doc, field, process_json_array(data[field], field))
        
        # Recalculate capacity if fleet changed
        if any(field in data for field in fleet_fields):
            capacities = {
                'swb_van_quantity': 5, 'mwb_van_quantity': 8, 'lwb_van_quantity': 11,
                'xlwb_van_quantity': 13, 'mwb_luton_van_quantity': 17, 'lwb_luton_van_quantity': 19,
                'tonne_7_5_lorry_quantity': 30, 'tonne_12_lorry_quantity': 45, 'tonne_18_lorry_quantity': 55
            }
            total_capacity = sum(int(getattr(company_doc, field, 0) or 0) * capacity 
                               for field, capacity in capacities.items())
            company_doc.total_carrying_capacity = total_capacity
        
        # Pricing
        pricing_fields = [
            'loading_cost_per_m3', 'packing_cost_per_box', 'assembly_cost_per_item',
            'disassembly_cost_per_item', 'cost_per_mile_under_25', 'cost_per_mile_over_25'
        ]
        for field in pricing_fields:
            if field in data:
                setattr(company_doc, field, float(data[field] or 0))
        
        # Auto-calculate disassembly if assembly changed
        if 'assembly_cost_per_item' in data:
            if 'disassembly_cost_per_item' not in data:
                company_doc.disassembly_cost_per_item = float(data['assembly_cost_per_item'] or 0) * 0.5
        
        # Subscription
        if 'subscription_plan' in data:
            company_doc.subscription_plan = data['subscription_plan']
        if 'subscription_start_date' in data:
            company_doc.subscription_start_date = data['subscription_start_date']
        if 'subscription_end_date' in data:
            company_doc.subscription_end_date = data['subscription_end_date']
        if 'is_active' in data:
            company_doc.is_active = int(data['is_active'])
        
        # Update timestamp
        company_doc.updated_at = datetime.now()
        
        # Save
        company_doc.flags.ignore_version = True
        company_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Parse response
        result = company_doc.as_dict()
        parse_company_json_fields(result)
        
        return {
            'success': True, 
            'message': 'Company updated successfully', 
            'data': result
        }
        
    except Exception as e:
        frappe.log_error(f"Update Company Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def delete_company():
    """Delete a company - Admin only with impact analysis"""
    try:
        # Admin permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        data = get_request_data()
        company_name = data.get('company_name')
        
        if not company_name:
            return {'success': False, 'message': 'company_name is required'}
        
        if not frappe.db.exists('Logistics Company', company_name):
            return {'success': False, 'message': 'Company not found'}
        
        # Check impact before deletion
        request_count = frappe.db.count('Logistics Request', {'company_name': company_name})
        payment_count = frappe.db.count('Payment Transaction', {'company_name': company_name})
        
        # Delete company
        frappe.delete_doc('Logistics Company', company_name, ignore_permissions=True)
        frappe.db.commit()
        
        return {
            'success': True, 
            'message': 'Company deleted successfully',
            'deletion_impact': {
                'requests_affected': request_count,
                'payments_affected': payment_count
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Delete Company Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}
    
# ===== REQUEST CRUD OPERATIONS =====

@frappe.whitelist()
def get_all_requests():
    """Get all logistics requests"""
    try:
        requests = frappe.get_all('Logistics Request',
            fields=['*'],
            order_by='created_at desc'
        )
        return {'success': True, 'data': requests, 'count': len(requests)}
    except Exception as e:
        frappe.log_error(f"Get Requests Error: {str(e)}")
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def get_request():
    """Get a single request by ID"""
    try:
        request_id = frappe.local.form_dict.get('request_id')
        if not request_id:
            return {'success': False, 'message': 'Request ID is required'}

        if not frappe.db.exists('Logistics Request', request_id):
            return {'success': False, 'message': 'Request not found'}
        
        request = frappe.get_doc('Logistics Request', request_id)
        return {'success': True, 'data': request.as_dict()}
    except Exception as e:
        frappe.log_error(f"Get Request Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def debug_request_data():
    """Debug endpoint to see what data is being received"""
    debug_info = {
        'success': True,
        'tests': {}
    }
    
    try:
        # Test 1: Check if frappe.request exists
        debug_info['tests']['1_frappe_request_exists'] = bool(frappe.request)
        
        # Test 2: Check Content-Type
        if frappe.request:
            debug_info['tests']['2_content_type'] = frappe.get_request_header("Content-Type")
            debug_info['tests']['2_method'] = frappe.request.method
        else:
            debug_info['tests']['2_no_request'] = "frappe.request is None"
        
        # Test 3: Try frappe.request.get_json()
        try:
            if frappe.request and hasattr(frappe.request, 'get_json'):
                json_data = frappe.request.get_json()
                debug_info['tests']['3_request_get_json'] = {
                    'success': True,
                    'type': type(json_data).__name__,
                    'is_none': json_data is None,
                    'data': json_data if json_data else 'None'
                }
            else:
                debug_info['tests']['3_request_get_json'] = 'Method not available'
        except Exception as e:
            debug_info['tests']['3_request_get_json'] = {
                'success': False,
                'error': str(e)
            }
        
        # Test 4: Check frappe.local.form_dict
        try:
            debug_info['tests']['4_form_dict'] = {
                'exists': hasattr(frappe.local, 'form_dict'),
                'is_none': frappe.local.form_dict is None if hasattr(frappe.local, 'form_dict') else 'N/A',
                'type': type(frappe.local.form_dict).__name__ if hasattr(frappe.local, 'form_dict') else 'N/A',
                'data': dict(frappe.local.form_dict) if hasattr(frappe.local, 'form_dict') and frappe.local.form_dict else None
            }
        except Exception as e:
            debug_info['tests']['4_form_dict'] = {
                'success': False,
                'error': str(e)
            }
        
        # Test 5: Try get_request_data()
        try:
            data = get_request_data()
            debug_info['tests']['5_get_request_data'] = {
                'success': True,
                'type': type(data).__name__,
                'is_none': data is None,
                'is_dict': isinstance(data, dict),
                'data': data if isinstance(data, dict) else str(data)[:200]
            }
        except Exception as e:
            debug_info['tests']['5_get_request_data'] = {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
        
        # Test 6: Check frappe.request.data
        try:
            if frappe.request and hasattr(frappe.request, 'data'):
                debug_info['tests']['6_request_data'] = {
                    'exists': True,
                    'data': frappe.request.data.decode('utf-8') if frappe.request.data else None
                }
            else:
                debug_info['tests']['6_request_data'] = 'Not available'
        except Exception as e:
            debug_info['tests']['6_request_data'] = str(e)
        
        # Test 7: Session user
        debug_info['tests']['7_session_user'] = frappe.session.user
        
        # Test 8: Admin permission
        debug_info['tests']['8_has_admin_permission'] = check_admin_permission()
        
        return debug_info
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


@frappe.whitelist()
def test_update_simple():
    """Simplest possible update test that bypasses get_request_data()"""
    try:
        # Method 1: Try direct JSON
        data = None
        if frappe.request:
            try:
                data = frappe.request.get_json()
            except:
                pass
        
        # Method 2: Try form_dict
        if not data:
            data = frappe.local.form_dict
        
        return {
            'success': True,
            'message': 'Data received',
            'data_type': type(data).__name__,
            'data_is_none': data is None,
            'data_content': data if isinstance(data, dict) else str(data)[:200],
            'data_keys': list(data.keys()) if isinstance(data, dict) else None
        }
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }


@frappe.whitelist()
def list_users_for_update():
    """List all users with their correct IDs for update operations"""
    try:
        users = frappe.db.sql("""
            SELECT 
                name as user_id,
                email,
                full_name,
                phone,
                role,
                city,
                state,
                is_active
            FROM `tabLocalMoves User`
            ORDER BY creation DESC
            LIMIT 20
        """, as_dict=True)
        
        return {
            'success': True,
            'count': len(users),
            'users': users,
            'instructions': {
                'note': 'Use the "user_id" field (not email) when calling update_user',
                'example': {
                    'user_id': users[0]['user_id'] if users else 'example-id',
                    'full_name': 'New Name',
                    'city': 'New City'
                }
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


@frappe.whitelist(allow_guest=False)
def update_user_v2():
    """Alternative update_user that uses direct request parsing"""
    try:
        # Check admin permission
        if not check_admin_permission():
            return {
                'success': False,
                'message': 'Access denied'
            }
        
        # Get data using multiple methods
        data = None
        
        # Try JSON first
        if frappe.request:
            try:
                data = frappe.request.get_json()
                if data:
                    frappe.log_error(title="Update User V2 - Data Source", message="Using request.get_json()")
            except:
                pass
        
        # Try form_dict
        if not data and hasattr(frappe.local, 'form_dict'):
            data = frappe.local.form_dict
            if data:
                frappe.log_error(title="Update User V2 - Data Source", message="Using form_dict")
        
        # Validate data
        if not data:
            return {
                'success': False,
                'message': 'No data received'
            }
        
        # Convert to dict if needed
        if not isinstance(data, dict):
            try:
                data = dict(data)
            except:
                return {
                    'success': False,
                    'message': f'Cannot convert data to dict. Type: {type(data).__name__}'
                }
        
        # Get user_id
        user_id = data.get('user_id')
        if not user_id:
            return {
                'success': False,
                'message': 'user_id is required',
                'received_keys': list(data.keys())
            }
        
        # Check if user exists
        user_exists = frappe.db.sql("""
            SELECT name FROM `tabLocalMoves User`
            WHERE name = %s OR email = %s
            LIMIT 1
        """, (user_id, user_id), as_dict=True)
        
        if not user_exists:
            return {
                'success': False,
                'message': f'User not found: {user_id}'
            }
        
        actual_id = user_exists[0]['name']
        
        # Get and update user
        user_doc = frappe.get_doc('LocalMoves User', actual_id)
        
        updated = []
        
        if 'full_name' in data and data['full_name']:
            user_doc.full_name = data['full_name']
            updated.append('full_name')
        
        if 'phone' in data and data['phone']:
            user_doc.phone = data['phone']
            updated.append('phone')
        
        if 'role' in data and data['role']:
            user_doc.role = data['role']
            updated.append('role')
        
        if 'city' in data:
            user_doc.city = data['city'] or ''
            updated.append('city')
        
        if 'state' in data:
            user_doc.state = data['state'] or ''
            updated.append('state')
        
        if 'is_active' in data:
            user_doc.is_active = int(data['is_active'])
            updated.append('is_active')
        
        if updated:
            user_doc.save(ignore_permissions=True)
            frappe.db.commit()
        
        return {
            'success': True,
            'message': f'Updated: {", ".join(updated)}' if updated else 'No changes',
            'data': {
                'user_id': user_doc.name,
                'email': user_doc.email,
                'full_name': user_doc.full_name,
                'phone': user_doc.phone,
                'role': user_doc.role,
                'updated_fields': updated
            }
        }
        
    except Exception as e:
        import traceback
        frappe.log_error(
            title="Update User V2 Error",
            message=traceback.format_exc()
        )
        frappe.db.rollback()
        return {
            'success': False,
            'message': str(e),
            'error_type': type(e).__name__
        }

"""
Add this to dashboard.py to test the exact user lookup issue
"""

@frappe.whitelist()
def test_user_lookup():
    """Test if we can find and load the user"""
    try:
        data = get_request_data()
        user_id = data.get('user_id')
        
        result = {
            'success': True,
            'steps': {}
        }
        
        # Step 1: What user_id did we receive?
        result['steps']['1_received_user_id'] = user_id
        
        # Step 2: Try frappe.db.exists
        try:
            exists_result = frappe.db.exists('LocalMoves User', user_id)
            result['steps']['2_db_exists'] = {
                'result': exists_result,
                'type': type(exists_result).__name__
            }
        except Exception as e:
            result['steps']['2_db_exists'] = {
                'error': str(e)
            }
        
        # Step 3: Try SQL by name
        try:
            by_name = frappe.db.sql("""
                SELECT name, email, full_name 
                FROM `tabLocalMoves User` 
                WHERE name = %s
            """, (user_id,), as_dict=True)
            result['steps']['3_sql_by_name'] = {
                'found': len(by_name) > 0,
                'count': len(by_name),
                'results': by_name
            }
        except Exception as e:
            result['steps']['3_sql_by_name'] = {
                'error': str(e)
            }
        
        # Step 4: Try SQL by email
        try:
            by_email = frappe.db.sql("""
                SELECT name, email, full_name 
                FROM `tabLocalMoves User` 
                WHERE email = %s
            """, (user_id,), as_dict=True)
            result['steps']['4_sql_by_email'] = {
                'found': len(by_email) > 0,
                'count': len(by_email),
                'results': by_email
            }
        except Exception as e:
            result['steps']['4_sql_by_email'] = {
                'error': str(e)
            }
        
        # Step 5: List all users (to see what IDs exist)
        try:
            all_users = frappe.db.sql("""
                SELECT name, email, full_name 
                FROM `tabLocalMoves User` 
                LIMIT 5
            """, as_dict=True)
            result['steps']['5_all_users_sample'] = {
                'count': len(all_users),
                'users': all_users,
                'note': 'Use the "name" field as user_id'
            }
        except Exception as e:
            result['steps']['5_all_users_sample'] = {
                'error': str(e)
            }
        
        # Step 6: Try to get_doc if user found
        if result['steps'].get('4_sql_by_email', {}).get('found'):
            actual_id = by_email[0]['name']
            result['steps']['6_correct_user_id'] = actual_id
            
            try:
                user_doc = frappe.get_doc('LocalMoves User', actual_id)
                result['steps']['7_get_doc'] = {
                    'success': True,
                    'name': user_doc.name,
                    'email': user_doc.email,
                    'full_name': user_doc.full_name,
                    'phone': user_doc.phone if hasattr(user_doc, 'phone') else None
                }
            except Exception as e:
                result['steps']['7_get_doc'] = {
                    'success': False,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
        
        return result
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }

# ✅ Utility: Extract and validate token safely
def get_user_from_token():
    """Extract user from JWT token with strong validation"""
    token = frappe.get_request_header("Authorization")

    if not token:
        frappe.throw(_("Missing Authorization header"), frappe.AuthenticationError)

    if token.startswith("Bearer "):
        token = token[7:].strip()

    if not token:
        frappe.throw(_("Empty or invalid Authorization token"), frappe.AuthenticationError)

    return get_current_user(token)


# ✅ ADMIN DASHBOARD
@frappe.whitelist(allow_guest=False)
def get_admin_dashboard():
    """Get admin dashboard statistics"""
    try:
        user_info = get_user_from_token()

        if user_info["role"] != "Admin":
            return {"success": False, "message": "Only Admins can access dashboard"}

        total_users = frappe.db.count("LocalMoves User")
        total_admins = frappe.db.count("LocalMoves User", {"role": "Admin"})
        total_managers = frappe.db.count("LocalMoves User", {"role": "Logistics Manager"})
        total_regular_users = frappe.db.count("LocalMoves User", {"role": "User"})

        total_companies = frappe.db.count("Logistics Company")
        active_companies = frappe.db.count("Logistics Company", {"is_active": 1})

        total_requests = frappe.db.count("Logistics Request")
        pending_requests = frappe.db.count("Logistics Request", {"status": "Pending"})
        assigned_requests = frappe.db.count("Logistics Request", {"status": "Assigned"})
        in_progress_requests = frappe.db.count("Logistics Request", {"status": "In Progress"})
        completed_requests = frappe.db.count("Logistics Request", {"status": "Completed"})
        cancelled_requests = frappe.db.count("Logistics Request", {"status": "Cancelled"})

        recent_users = frappe.get_all(
            "LocalMoves User",
            fields=["email", "full_name", "role", "created_at"],
            order_by="created_at desc",
            limit=5,
        )

        recent_requests = frappe.get_all(
            "Logistics Request",
            fields=["name", "user_name", "status", "pickup_city", "delivery_city", "created_at"],
            order_by="created_at desc",
            limit=10,
        )

        recent_companies = frappe.get_all(
            "Logistics Company",
            fields=["company_name", "manager_email", "location", "created_at"],
            order_by="created_at desc",
            limit=5,
        )

        return {
            "success": True,
            "data": {
                "users": {
                    "total": total_users,
                    "admins": total_admins,
                    "managers": total_managers,
                    "regular_users": total_regular_users,
                },
                "companies": {
                    "total": total_companies,
                    "active": active_companies,
                    "inactive": total_companies - active_companies,
                },
                "requests": {
                    "total": total_requests,
                    "pending": pending_requests,
                    "assigned": assigned_requests,
                    "in_progress": in_progress_requests,
                    "completed": completed_requests,
                    "cancelled": cancelled_requests,
                },
                "recent_activities": {
                    "users": recent_users,
                    "requests": recent_requests,
                    "companies": recent_companies,
                },
            },
        }

    except Exception as e:
        frappe.log_error(f"Get Admin Dashboard Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch dashboard data"}


# ✅ MANAGER DASHBOARD
@frappe.whitelist(allow_guest=False)
def get_manager_dashboard():
    """Get manager dashboard statistics"""
    try:
        user_info = get_user_from_token()

        if user_info["role"] != "Logistics Manager":
            return {"success": False, "message": "Only Managers can access this dashboard"}

        companies = frappe.get_all(
            "Logistics Company", filters={"manager_email": user_info["email"]}, pluck="name"
        )

        if not companies:
            return {"success": True, "data": {"message": "No company registered yet"}}

        company_details = frappe.get_all(
            "Logistics Company",
            filters={"manager_email": user_info["email"]},
            fields=["company_name", "phone", "pincode", "location", "is_active", "created_at"],
        )

        total_requests = frappe.db.count("Logistics Request", {"company_name": ["in", companies]})
        assigned_requests = frappe.db.count(
            "Logistics Request", {"company_name": ["in", companies], "status": "Assigned"}
        )
        accepted_requests = frappe.db.count(
            "Logistics Request", {"company_name": ["in", companies], "status": "Accepted"}
        )
        in_progress = frappe.db.count(
            "Logistics Request", {"company_name": ["in", companies], "status": "In Progress"}
        )
        completed = frappe.db.count(
            "Logistics Request", {"company_name": ["in", companies], "status": "Completed"}
        )

        recent_requests = frappe.get_all(
            "Logistics Request",
            filters={"company_name": ["in", companies]},
            fields=[
                "name",
                "user_name",
                "user_phone",
                "status",
                "pickup_city",
                "delivery_city",
                "estimated_cost",
                "created_at",
                "assigned_date",
            ],
            order_by="created_at desc",
            limit=10,
        )

        return {
            "success": True,
            "data": {
                "companies": company_details,
                "requests": {
                    "total": total_requests,
                    "assigned": assigned_requests,
                    "accepted": accepted_requests,
                    "in_progress": in_progress,
                    "completed": completed,
                },
                "recent_requests": recent_requests,
            },
        }

    except Exception as e:
        frappe.log_error(f"Get Manager Dashboard Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch dashboard data"}


# ✅ USER DASHBOARD (fixed)
@frappe.whitelist(allow_guest=False)
def get_user_dashboard():
    """Get user dashboard statistics"""
    try:
        user_info = get_user_from_token()

        if not user_info or "email" not in user_info:
            frappe.throw(_("Invalid or missing user information"), frappe.AuthenticationError)

        email = user_info["email"]

        total_requests = frappe.db.count("Logistics Request", {"user_email": email})
        pending_requests = frappe.db.count("Logistics Request", {"user_email": email, "status": "Pending"})
        assigned_requests = frappe.db.count("Logistics Request", {"user_email": email, "status": "Assigned"})
        in_progress = frappe.db.count("Logistics Request", {"user_email": email, "status": "In Progress"})
        completed = frappe.db.count("Logistics Request", {"user_email": email, "status": "Completed"})
        cancelled = frappe.db.count("Logistics Request", {"user_email": email, "status": "Cancelled"})

        recent_requests = frappe.get_all(
            "Logistics Request",
            filters={"user_email": email},
            fields=[
                "name",
                "pickup_city",
                "delivery_city",
                "status",
                "company_name",
                "estimated_cost",
                "actual_cost",
                "created_at",
                "delivery_date",
            ],
            order_by="created_at desc",
            limit=10,
        )

        return {
            "success": True,
            "data": {
                "requests": {
                    "total": total_requests,
                    "pending": pending_requests,
                    "assigned": assigned_requests,
                    "in_progress": in_progress,
                    "completed": completed,
                    "cancelled": cancelled,
                },
                "recent_requests": recent_requests,
            },
        }

    except frappe.AuthenticationError:
        # handled automatically, but log for clarity
        frappe.log_error("User dashboard authentication failed")
        return {"success": False, "message": "Unauthorized access"}
    except Exception as e:
        frappe.log_error(f"Get User Dashboard Error: {str(e)}")
        return {"success": False, "message": "Failed to fetch dashboard data"}



# ===== INVENTORY CATEGORY CRUD OPERATIONS (Admin Only) =====
# Add these functions to your dashboard.py file

@frappe.whitelist(allow_guest=False)
def get_all_inventory_categories():
    """Get all inventory categories including empty ones"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view categories'
            }
        
        # Get categories from items (categories with items)
        categories_with_items = frappe.db.sql("""
            SELECT 
                category,
                COUNT(*) as item_count,
                SUM(average_volume) as total_volume,
                AVG(average_volume) as avg_volume,
                MIN(creation) as first_item_created,
                MAX(modified) as last_item_modified
            FROM `tabMoving Inventory Item`
            GROUP BY category
            ORDER BY category ASC
        """, as_dict=True)
        
        # Get registered categories (may include empty ones)
        config = get_system_config_from_db()
        registered_categories = config.get('inventory_categories', [])
        
        # Merge both lists
        all_categories = {}
        
        # Add categories with items
        for cat in categories_with_items:
            all_categories[cat['category']] = cat
        
        # Add registered categories (empty ones)
        for cat_name in registered_categories:
            if cat_name not in all_categories:
                all_categories[cat_name] = {
                    'category': cat_name,
                    'item_count': 0,
                    'total_volume': 0,
                    'avg_volume': 0,
                    'first_item_created': None,
                    'last_item_modified': None
                }
        
        # Convert to sorted list
        final_list = sorted(all_categories.values(), key=lambda x: x['category'])
        
        return {
            'success': True,
            'data': final_list,
            'count': len(final_list)
        }
    except Exception as e:
        frappe.log_error(f"Get Inventory Categories Error: {str(e)}")
        return {'success': False, 'error': str(e)}

# @frappe.whitelist(allow_guest=False)
# def create_inventory_category():
#     """
#     Create a new inventory category by adding a placeholder item
#     The category will be created when the first item is added to it
    
#     Required fields:
#     - category_name: Name of the new category
#     """
#     try:
#         ensure_session_data()
        
#         # Permission check
#         if not check_admin_permission():
#             return {
#                 'success': False, 
#                 'message': 'Access Denied: You do not have permission to create categories'
#             }
        
#         data = get_request_data()
#         category_name = data.get('category_name')
        
#         if not category_name:
#             return {'success': False, 'message': 'category_name is required'}
        
#         # Check if category already exists
#         existing_category = frappe.db.sql("""
#             SELECT category 
#             FROM `tabMoving Inventory Item`
#             WHERE category = %s
#             LIMIT 1
#         """, (category_name,))
        
#         if existing_category:
#             return {
#                 'success': False, 
#                 'message': f'Category "{category_name}" already exists'
#             }
        
#         # Create a placeholder item to establish the category
#         # You can customize this or make it optional
#         placeholder_item = frappe.new_doc('Moving Inventory Item')
#         placeholder_item.category = category_name
#         placeholder_item.item_name = f"[Placeholder] {category_name} Item"
#         placeholder_item.average_volume = 0.0
#         placeholder_item.unit = 'm³'
        
#         placeholder_item.flags.ignore_version = True
#         placeholder_item.insert(ignore_permissions=True)
#         frappe.db.commit()
        
#         return {
#             'success': True,
#             'message': f'Category "{category_name}" created successfully',
#             'data': {
#                 'category_name': category_name,
#                 'placeholder_item': placeholder_item.name,
#                 'note': 'A placeholder item was created. You can now add items to this category or delete the placeholder.'
#             }
#         }
        
#     except Exception as e:
#         frappe.log_error(f"Create Inventory Category Error: {str(e)}")
#         frappe.db.rollback()
#         return {'success': False, 'error': str(e)}




# ===== REMOVE THE NEED FOR create_inventory_category ENDPOINT =====
# This function is now OPTIONAL - categories are created automatically when adding items

@frappe.whitelist(allow_guest=False)
def create_inventory_category():
    """
    Create a new inventory category WITHOUT creating any items
    Just registers the category name in the system
    
    Required fields:
    - category_name: Name of the new category
    """
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to create categories'
            }
        
        data = get_request_data()
        category_name = data.get('category_name')
        
        if not category_name:
            return {'success': False, 'message': 'category_name is required'}
        
        category_name = category_name.strip()
        
        # Check if category already exists
        existing_category = frappe.db.exists('Moving Inventory Item', {'category': category_name})
        
        if existing_category:
            item_count = frappe.db.count('Moving Inventory Item', {'category': category_name})
            return {
                'success': False, 
                'message': f'Category "{category_name}" already exists with {item_count} items'
            }
        
        # PURE CATEGORY CREATION:
        # Store category in a separate tracking table or system config
        # This allows categories to exist WITHOUT items
        
        # Option 1: Store in System Configuration
        config = get_system_config_from_db()
        if 'inventory_categories' not in config:
            config['inventory_categories'] = []
        
        if category_name not in config['inventory_categories']:
            config['inventory_categories'].append(category_name)
            
            # Update config
            frappe.db.sql("""
                UPDATE `tabSystem Configuration`
                SET config_data = %s, updated_at = %s
                WHERE name = 'admin_config'
            """, (json.dumps(config), datetime.now()))
            
            frappe.db.commit()
            
            return {
                'success': True,
                'message': f'Category "{category_name}" created successfully',
                'data': {
                    'category_name': category_name,
                    'item_count': 0,
                    'note': 'Category created without items. Add items anytime.'
                }
            }
        else:
            return {
                'success': False,
                'message': f'Category "{category_name}" already registered'
            }
        
    except Exception as e:
        frappe.log_error(f"Create Category Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}

def create_inventory_item_internal(category, item_name, average_volume, unit='m³'):
    """
    Internal function to create inventory item
    Used by other functions to avoid code duplication
    """
    try:
        item_doc = frappe.new_doc('Moving Inventory Item')
        item_doc.category = category
        item_doc.item_name = item_name
        item_doc.average_volume = float(average_volume)
        item_doc.unit = unit
        
        item_doc.flags.ignore_version = True
        item_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            'success': True,
            'data': item_doc.as_dict()
        }
    except Exception as e:
        frappe.db.rollback()
        return {
            'success': False,
            'error': str(e)
        }


# ===== SIMPLIFIED BULK UPLOAD WITH AUTO-CATEGORY =====

@frappe.whitelist(allow_guest=False)
def bulk_create_inventory_items():
    """
    Bulk create inventory items with AUTOMATIC category creation
    Categories will be created as needed - no pre-setup required!
    
    Request format:
    {
      "items": [
        {"category": "New Category", "item_name": "Item 1", "average_volume": 1.5},
        {"category": "Another New Category", "item_name": "Item 2", "average_volume": 2.0}
      ]
    }
    """
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to create inventory items'
            }
        
        data = get_request_data()
        items = data.get('items')
        
        if not items:
            return {'success': False, 'message': 'items array is required'}
        
        import json
        if isinstance(items, str):
            items = json.loads(items)
        
        created = 0
        errors = []
        created_items = []
        new_categories = set()
        
        for item in items:
            try:
                # Validate required fields
                if not item.get('category') or not item.get('item_name') or not item.get('average_volume'):
                    errors.append({
                        'item': item.get('item_name', 'Unknown'),
                        'error': 'Missing required fields (category, item_name, average_volume)'
                    })
                    continue
                
                category = item.get('category').strip()
                item_name = item.get('item_name').strip()
                
                # Check if category is new
                if not frappe.db.exists('Moving Inventory Item', {'category': category}):
                    new_categories.add(category)
                
                # Check if already exists
                if frappe.db.exists('Moving Inventory Item', {
                    'category': category,
                    'item_name': item_name
                }):
                    errors.append({
                        'item': item_name,
                        'error': f'Item already exists in category "{category}"'
                    })
                    continue
                
                # Create item
                item_doc = frappe.new_doc('Moving Inventory Item')
                item_doc.category = category
                item_doc.item_name = item_name
                item_doc.average_volume = float(item.get('average_volume'))
                item_doc.unit = item.get('unit', 'm³')
                
                item_doc.flags.ignore_version = True
                item_doc.insert(ignore_permissions=True)
                created += 1
                created_items.append(item_doc.as_dict())
                
            except Exception as e:
                errors.append({
                    'item': item.get('item_name', 'Unknown'),
                    'error': str(e)
                })
        
        frappe.db.commit()
        
        response = {
            'success': True,
            'message': f'Bulk upload completed. Created {created} items, {len(errors)} errors',
            'created_count': created,
            'error_count': len(errors),
            'created_items': created_items,
            'errors': errors
        }
        
        if new_categories:
            response['new_categories_created'] = list(new_categories)
            response['new_categories_count'] = len(new_categories)
            response['message'] += f'. {len(new_categories)} new categories created automatically.'
        
        return response
        
    except Exception as e:
        frappe.log_error(f"Bulk Create Inventory Items Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}

@frappe.whitelist(allow_guest=False)
def rename_inventory_category():
    """
    Rename an existing category by updating all items in that category
    
    Required fields:
    - old_category_name: Current category name
    - new_category_name: New category name
    """
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to rename categories'
            }
        
        data = get_request_data()
        old_category_name = data.get('old_category_name')
        new_category_name = data.get('new_category_name')
        
        if not old_category_name or not new_category_name:
            return {
                'success': False, 
                'message': 'Both old_category_name and new_category_name are required'
            }
        
        # Check if old category exists
        old_category_items = frappe.db.sql("""
            SELECT name
            FROM `tabMoving Inventory Item`
            WHERE category = %s
        """, (old_category_name,), as_dict=True)
        
        if not old_category_items:
            return {
                'success': False, 
                'message': f'Category "{old_category_name}" does not exist'
            }
        
        # Check if new category already exists
        new_category_exists = frappe.db.sql("""
            SELECT category 
            FROM `tabMoving Inventory Item`
            WHERE category = %s
            LIMIT 1
        """, (new_category_name,))
        
        if new_category_exists:
            return {
                'success': False, 
                'message': f'Category "{new_category_name}" already exists. Cannot rename to existing category.'
            }
        
        # Update all items in the old category
        updated_count = 0
        for item in old_category_items:
            item_doc = frappe.get_doc('Moving Inventory Item', item['name'])
            item_doc.category = new_category_name
            item_doc.flags.ignore_version = True
            item_doc.save(ignore_permissions=True)
            updated_count += 1
        
        frappe.db.commit()
        
        return {
            'success': True,
            'message': f'Category renamed successfully from "{old_category_name}" to "{new_category_name}"',
            'data': {
                'old_category': old_category_name,
                'new_category': new_category_name,
                'items_updated': updated_count
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Rename Inventory Category Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def delete_inventory_category():
    """
    Delete an entire category and all items in it
    Also removes empty categories from System Configuration
    
    Required fields:
    - category_name: Name of the category to delete
    - confirm: Must be true to confirm deletion
    """
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to delete categories'
            }
        
        data = get_request_data()
        category_name = data.get('category_name')
        confirm = data.get('confirm')
        
        if not category_name:
            return {'success': False, 'message': 'category_name is required'}
        
        # Get item count
        item_count = frappe.db.count('Moving Inventory Item', {'category': category_name})
        
        if not confirm or str(confirm).lower() != 'true':
            return {
                'success': False,
                'message': f'Confirmation required. This will delete {item_count} items in category "{category_name}"',
                'requires_confirmation': True,
                'item_count': item_count,
                'instruction': 'Set "confirm": true to proceed with deletion'
            }
        
        deleted_count = 0
        
        # Delete items if any exist
        if item_count > 0:
            category_items = frappe.get_all('Moving Inventory Item',
                filters={'category': category_name},
                pluck='name'
            )
            
            for item_name in category_items:
                frappe.delete_doc('Moving Inventory Item', item_name, 
                                ignore_permissions=True, force=True)
                deleted_count += 1
        
        # ALSO remove from System Configuration (for empty categories)
        try:
            config = get_system_config_from_db()
            if 'inventory_categories' in config:
                if category_name in config['inventory_categories']:
                    config['inventory_categories'].remove(category_name)
                    
                    # Update config
                    frappe.db.sql("""
                        UPDATE `tabSystem Configuration`
                        SET config_data = %s, updated_at = %s
                        WHERE name = 'admin_config'
                    """, (json.dumps(config), datetime.now()))
        except Exception as e:
            frappe.log_error(f"Error removing category from config: {str(e)}")
        
        frappe.db.commit()
        
        message = f'Category "{category_name}" deleted successfully'
        if deleted_count > 0:
            message += f' ({deleted_count} items deleted)'
        else:
            message += ' (empty category removed)'
        
        return {
            'success': True,
            'message': message,
            'data': {
                'category_name': category_name,
                'items_deleted': deleted_count
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Delete Inventory Category Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}
    
    
@frappe.whitelist(allow_guest=False)
def merge_inventory_categories():
    """
    Merge two categories by moving all items from source to target category
    
    Required fields:
    - source_category: Category to merge from (will be deleted)
    - target_category: Category to merge into (will remain)
    """
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to merge categories'
            }
        
        data = get_request_data()
        source_category = data.get('source_category')
        target_category = data.get('target_category')
        
        if not source_category or not target_category:
            return {
                'success': False, 
                'message': 'Both source_category and target_category are required'
            }
        
        if source_category == target_category:
            return {
                'success': False, 
                'message': 'Source and target categories cannot be the same'
            }
        
        # Check if source category exists
        source_items = frappe.get_all('Moving Inventory Item',
            filters={'category': source_category},
            pluck='name'
        )
        
        if not source_items:
            return {
                'success': False, 
                'message': f'Source category "{source_category}" does not exist or has no items'
            }
        
        # Check if target category exists
        target_exists = frappe.db.exists('Moving Inventory Item', {'category': target_category})
        
        if not target_exists:
            return {
                'success': False, 
                'message': f'Target category "{target_category}" does not exist. Create it first.'
            }
        
        # Move all items from source to target
        moved_count = 0
        for item_name in source_items:
            item_doc = frappe.get_doc('Moving Inventory Item', item_name)
            item_doc.category = target_category
            item_doc.flags.ignore_version = True
            item_doc.save(ignore_permissions=True)
            moved_count += 1
        
        frappe.db.commit()
        
        return {
            'success': True,
            'message': f'Successfully merged "{source_category}" into "{target_category}"',
            'data': {
                'source_category': source_category,
                'target_category': target_category,
                'items_moved': moved_count
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Merge Inventory Categories Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def get_category_details():
    """
    Get detailed information about a specific category
    
    Required fields:
    - category_name: Name of the category
    """
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view category details'
            }
        
        data = get_request_data()
        category_name = data.get('category_name')
        
        if not category_name:
            return {'success': False, 'message': 'category_name is required'}
        
        # Get category statistics
        stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as item_count,
                SUM(average_volume) as total_volume,
                AVG(average_volume) as avg_volume,
                MIN(average_volume) as min_volume,
                MAX(average_volume) as max_volume,
                MIN(creation) as first_item_created,
                MAX(modified) as last_item_modified
            FROM `tabMoving Inventory Item`
            WHERE category = %s
        """, (category_name,), as_dict=True)
        
        if not stats or stats[0]['item_count'] == 0:
            return {
                'success': False, 
                'message': f'Category "{category_name}" does not exist or has no items'
            }
        
        # Get all items in the category
        items = frappe.get_all('Moving Inventory Item',
            filters={'category': category_name},
            fields=['name', 'item_name', 'average_volume', 'unit', 'creation', 'modified'],
            order_by='item_name asc'
        )
        
        # Get top 5 largest items
        largest_items = frappe.get_all('Moving Inventory Item',
            filters={'category': category_name},
            fields=['item_name', 'average_volume'],
            order_by='average_volume desc',
            limit=5
        )
        
        # Get top 5 smallest items
        smallest_items = frappe.get_all('Moving Inventory Item',
            filters={'category': category_name},
            fields=['item_name', 'average_volume'],
            order_by='average_volume asc',
            limit=5
        )
        
        return {
            'success': True,
            'data': {
                'category_name': category_name,
                'statistics': stats[0],
                'items': items,
                'largest_items': largest_items,
                'smallest_items': smallest_items
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Get Category Details Error: {str(e)}")
        return {'success': False, 'error': str(e)}


# ===== UPDATE EXISTING INVENTORY ITEM FUNCTIONS TO SUPPORT DYNAMIC CATEGORIES =====

@frappe.whitelist(allow_guest=False)
def create_inventory_item_v2():
    """
    Create a new inventory item with dynamic category support
    If the category doesn't exist, it will be created automatically
    """
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to create inventory items'
            }
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['category', 'item_name', 'average_volume']
        for field in required_fields:
            if not data.get(field):
                return {'success': False, 'message': f'{field} is required'}
        
        # NO CATEGORY VALIDATION - Allow any category name
        category = data.get('category')
        
        # Check if item already exists
        if frappe.db.exists('Moving Inventory Item', {'item_name': data.get('item_name')}):
            return {'success': False, 'message': 'Item with this name already exists'}
        
        # Check if this is a new category
        category_exists = frappe.db.exists('Moving Inventory Item', {'category': category})
        is_new_category = not category_exists
        
        # Create new item
        item_doc = frappe.new_doc('Moving Inventory Item')
        item_doc.category = category
        item_doc.item_name = data.get('item_name')
        item_doc.average_volume = float(data.get('average_volume'))
        item_doc.unit = data.get('unit', 'm³')
        
        item_doc.flags.ignore_version = True
        item_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        response = {
            'success': True, 
            'message': 'Inventory item created successfully', 
            'data': item_doc.as_dict()
        }
        
        if is_new_category:
            response['category_created'] = True
            response['message'] += f' (New category "{category}" was created)'
        
        return response
        
    except ValueError:
        return {'success': False, 'message': 'average_volume must be a valid number'}
    except Exception as e:
        frappe.log_error(f"Create Inventory Item V2 Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


# ===== INVENTORY CRUD OPERATIONS (Admin Only) =====
# Add these functions to your dashboard.py file

@frappe.whitelist(allow_guest=False)
def get_all_inventory_items():
    """Get all inventory items with optional category filter - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view inventory items'
            }
        
        data = get_request_data()
        filters = {}
        
        # Optional category filter
        if data.get('category'):
            filters['category'] = data.get('category')
        
        items = frappe.get_all('Moving Inventory Item',
            fields=['name', 'category', 'item_name', 'average_volume', 'unit', 'creation', 'modified'],
            filters=filters,
            order_by='category asc, item_name asc'
        )
        
        # Get category summary
        category_summary = frappe.db.sql("""
            SELECT category, COUNT(*) as count, SUM(average_volume) as total_volume
            FROM `tabMoving Inventory Item`
            GROUP BY category
            ORDER BY category ASC
        """, as_dict=True)
        
        return {
            'success': True, 
            'data': items, 
            'count': len(items),
            'category_summary': category_summary
        }
    except Exception as e:
        frappe.log_error(f"Get Inventory Items Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def get_inventory_item():
    """Get a single inventory item by name - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view inventory items'
            }
        
        item_name = frappe.local.form_dict.get('item_name')
        if not item_name:
            return {'success': False, 'message': 'Item name is required'}

        if not frappe.db.exists('Moving Inventory Item', item_name):
            return {'success': False, 'message': 'Inventory item not found'}
        
        item = frappe.get_doc('Moving Inventory Item', item_name)
        return {'success': True, 'data': item.as_dict()}
    except Exception as e:
        frappe.log_error(f"Get Inventory Item Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def create_inventory_item():
    """Create a new inventory item - Admin only"""
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to create inventory items'
            }
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['category', 'item_name', 'average_volume']
# #         for field in required_fields:
# #             if not data.get(field):
# #                 return {'success': False, 'message': f'{field} is required'}
# #         
# #         # Validate category
# #         valid_categories = [
# #             'Living Room', 
# #             'Kitchen', 
# #             'Other / Bathroom / Hallway', 
# #             'Garden / Garage / Loft', 
# #             'Bedroom'
# #         ]
# #         # if data.get('category') not in valid_categories:
# #         #     return {
# #         #         'success': False, 
# #         #         'message': f'Invalid category. Must be one of: {", ".join(valid_categories)}'
# #         #     }
# #         
# #         # Check if item already exists
# #         if frappe.db.exists('Moving Inventory Item', {'item_name': data.get('item_name')}):
# #             return {'success': False, 'message': 'Item with this name already exists'}
# #         
# #         # Create new item
# #         item_doc = frappe.new_doc('Moving Inventory Item')
# #         item_doc.category = data.get('category')
# #         item_doc.item_name = data.get('item_name')
        item_doc.average_volume = float(data.get('average_volume'))
        item_doc.unit = data.get('unit', 'm³')
        
        item_doc.flags.ignore_version = True
        item_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            'success': True, 
            'message': 'Inventory item created successfully', 
            'data': item_doc.as_dict()
        }
    except ValueError:
        return {'success': False, 'message': 'average_volume must be a valid number'}
    except Exception as e:
        frappe.log_error(f"Create Inventory Item Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def update_inventory_item():
    """Update an existing inventory item - Admin only"""
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to update inventory items'
            }
        
        data = get_request_data()
        item_name = data.get('item_name')
        
        if not item_name:
            return {'success': False, 'message': 'item_name is required'}
        
        if not frappe.db.exists('Moving Inventory Item', item_name):
            return {'success': False, 'message': 'Inventory item not found'}
        
        item_doc = frappe.get_doc('Moving Inventory Item', item_name)
        
#         updated_fields = []
#         
#         # Update category
#         if 'category' in data and data.get('category'):
#             valid_categories = [
#                 'Living Room', 
#                 'Kitchen', 
#                 'Other / Bathroom / Hallway', 
#                 'Garden / Garage / Loft', 
#                 'Bedroom'
#             ]
#             if data.get('category') not in valid_categories:
#                 return {
#                     'success': False, 
#                     'message': f'Invalid category. Must be one of: {", ".join(valid_categories)}'
#                 }
#             item_doc.category = data.get('category')
#             updated_fields.append('category')
#         
#         # Update average_volume
#         if 'average_volume' in data and data.get('average_volume'):
#             try:
#                 item_doc.average_volume = float(data.get('average_volume'))
#                 updated_fields.append('average_volume')
#             except ValueError:
#                 return {'success': False, 'message': 'average_volume must be a valid number'}
        
        # Update unit
        if 'unit' in data and data.get('unit'):
            item_doc.unit = data.get('unit')
            updated_fields.append('unit')
        
        # Update new_item_name (rename)
        if 'new_item_name' in data and data.get('new_item_name'):
            new_name = data.get('new_item_name')
            if new_name != item_name:
                # Check if new name already exists
                if frappe.db.exists('Moving Inventory Item', {'item_name': new_name}):
                    return {'success': False, 'message': 'An item with this name already exists'}
                item_doc.item_name = new_name
                updated_fields.append('item_name')
        
        if not updated_fields:
            return {
                'success': True, 
                'message': 'No fields to update',
                'data': item_doc.as_dict()
            }
        
        item_doc.flags.ignore_version = True
        item_doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            'success': True, 
            'message': f'Inventory item updated successfully. Updated fields: {", ".join(updated_fields)}',
            'data': item_doc.as_dict(),
            'updated_fields': updated_fields
        }
    except Exception as e:
        frappe.log_error(f"Update Inventory Item Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def delete_inventory_item():
    """Delete an inventory item - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to delete inventory items'
            }
        
        data = get_request_data()
        item_name = data.get('item_name')
        
        if not item_name:
            return {'success': False, 'message': 'item_name is required'}
        
        if not frappe.db.exists('Moving Inventory Item', item_name):
            return {'success': False, 'message': 'Inventory item not found'}
        
        frappe.delete_doc('Moving Inventory Item', item_name, ignore_permissions=True)
        frappe.db.commit()
        
        return {'success': True, 'message': 'Inventory item deleted successfully'}
    except Exception as e:
        frappe.log_error(f"Delete Inventory Item Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def bulk_create_inventory_items():
    """Bulk create inventory items - Admin only"""
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to create inventory items'
            }
        
        data = get_request_data()
        items = data.get('items')
        
        if not items:
            return {'success': False, 'message': 'items array is required'}
        
        import json
        if isinstance(items, str):
            items = json.loads(items)
        
        created = 0
        errors = []
        created_items = []
        
        for item in items:
            try:
                # Validate required fields
                if not item.get('category') or not item.get('item_name') or not item.get('average_volume'):
                    errors.append({
                        'item': item.get('item_name', 'Unknown'),
                        'error': 'Missing required fields'
                    })
                    continue
                
                # Check if already exists
                if frappe.db.exists('Moving Inventory Item', {'item_name': item.get('item_name')}):
                    errors.append({
                        'item': item.get('item_name'),
                        'error': 'Item already exists'
                    })
                    continue
                
                item_doc = frappe.new_doc('Moving Inventory Item')
                item_doc.category = item.get('category')
                item_doc.item_name = item.get('item_name')
                item_doc.average_volume = float(item.get('average_volume'))
                item_doc.unit = item.get('unit', 'm³')
                
                item_doc.flags.ignore_version = True
                item_doc.insert(ignore_permissions=True)
                created += 1
                created_items.append(item_doc.as_dict())
                
            except Exception as e:
                errors.append({
                    'item': item.get('item_name', 'Unknown'),
                    'error': str(e)
                })
        
        frappe.db.commit()
        
        return {
            'success': True,
            'message': f'Bulk upload completed. Created {created} items, {len(errors)} errors',
            'created_count': created,
            'error_count': len(errors),
            'created_items': created_items,
            'errors': errors
        }
    except Exception as e:
        frappe.log_error(f"Bulk Create Inventory Items Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def get_inventory_categories():
    """Get all available inventory categories - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view inventory categories'
            }
        
        categories = frappe.db.sql("""
            SELECT DISTINCT category, COUNT(*) as item_count
            FROM `tabMoving Inventory Item`
            GROUP BY category
            ORDER BY category ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'data': categories,
            'count': len(categories)
        }
    except Exception as e:
        frappe.log_error(f"Get Inventory Categories Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def search_inventory_items():
    """Search inventory items by name or category - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to search inventory items'
            }
        
        data = get_request_data()
        search_term = data.get('search_term', '')
        category = data.get('category')
        
        filters = []
        filter_values = []
        
        if search_term:
            filters.append("item_name LIKE %s")
            filter_values.append(f"%{search_term}%")
        
        if category:
            filters.append("category = %s")
            filter_values.append(category)
        
        where_clause = " AND ".join(filters) if filters else "1=1"
        
        items = frappe.db.sql(f"""
            SELECT name, category, item_name, average_volume, unit
            FROM `tabMoving Inventory Item`
            WHERE {where_clause}
            ORDER BY category ASC, item_name ASC
        """, tuple(filter_values), as_dict=True)
        
        return {
            'success': True,
            'data': items,
            'count': len(items),
            'search_term': search_term,
            'category': category
        }
    except Exception as e:
        frappe.log_error(f"Search Inventory Items Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def get_inventory_statistics():
    """Get inventory statistics - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view inventory statistics'
            }
        
        total_items = frappe.db.count('Moving Inventory Item')
        
        category_stats = frappe.db.sql("""
            SELECT 
                category,
                COUNT(*) as item_count,
                AVG(average_volume) as avg_volume,
                MIN(average_volume) as min_volume,
                MAX(average_volume) as max_volume,
                SUM(average_volume) as total_volume
            FROM `tabMoving Inventory Item`
            GROUP BY category
            ORDER BY item_count DESC
        """, as_dict=True)
        
        largest_items = frappe.get_all('Moving Inventory Item',
            fields=['item_name', 'category', 'average_volume'],
            order_by='average_volume desc',
            limit=10
        )
        
        smallest_items = frappe.get_all('Moving Inventory Item',
            fields=['item_name', 'category', 'average_volume'],
            order_by='average_volume asc',
            limit=10
        )
        
        recently_added = frappe.get_all('Moving Inventory Item',
            fields=['item_name', 'category', 'average_volume', 'creation'],
            order_by='creation desc',
            limit=10
        )
        
        return {
            'success': True,
            'statistics': {
                'total_items': total_items,
                'category_breakdown': category_stats,
                'largest_items': largest_items,
                'smallest_items': smallest_items,
                'recently_added': recently_added
            }
        }
    except Exception as e:
        frappe.log_error(f"Get Inventory Statistics Error: {str(e)}")
        return {'success': False, 'error': str(e)}
    
# ===== RATING & REVIEW ADMIN CRUD OPERATIONS =====

@frappe.whitelist(allow_guest=False)
def get_all_ratings_and_reviews():
    """Get all ratings and reviews across all companies - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view all reviews'
            }
        
        data = get_request_data()
        
        # Optional filters
        company_name = data.get('company_name')
        min_rating = data.get('min_rating')
        max_rating = data.get('max_rating')
        status = data.get('status')
        limit = data.get('limit', 50)
        offset = data.get('offset', 0)
        
        # Build SQL query with filters
        filters = []
        filter_values = {'limit': limit, 'offset': offset}
        
        if company_name:
            filters.append("company_name = %(company_name)s")
            filter_values['company_name'] = company_name
        
        if min_rating:
            filters.append("rating >= %(min_rating)s")
            filter_values['min_rating'] = min_rating
        
        if max_rating:
            filters.append("rating <= %(max_rating)s")
            filter_values['max_rating'] = max_rating
        
        if status:
            filters.append("status = %(status)s")
            filter_values['status'] = status
        
        where_clause = " AND ".join(filters) if filters else "1=1"
        
        # Get all rated requests
        reviews = frappe.db.sql(f"""
            SELECT 
                name as request_id,
                company_name,
                rating,
                review_comment,
                service_aspects,
                rated_at,
                rating_updated_at,
                full_name as user_name,
                user_email,
                user_phone,
                status,
                completed_at,
                pickup_city,
                delivery_city,
                pickup_address,
                delivery_address,
                estimated_cost,
                actual_cost,
                created_at
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL
            AND rating > 0
            AND {where_clause}
            ORDER BY rated_at DESC
            LIMIT %(limit)s OFFSET %(offset)s
        """, filter_values, as_dict=True)
        
        # Get total count
        count_result = frappe.db.sql(f"""
            SELECT COUNT(*) as total
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL
            AND rating > 0
            AND {where_clause}
        """, filter_values, as_dict=True)
        
        total_count = count_result[0]['total'] if count_result else 0
        
        # Parse service aspects JSON
        for review in reviews:
            if review.get('service_aspects'):
                try:
                    review['service_aspects'] = json.loads(review['service_aspects'])
                except:
                    review['service_aspects'] = {}
        
        # Get summary statistics
        stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_reviews,
                AVG(rating) as avg_rating,
                MIN(rating) as min_rating,
                MAX(rating) as max_rating,
                COUNT(DISTINCT company_name) as companies_with_reviews,
                COUNT(DISTINCT user_email) as unique_reviewers
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
        """, as_dict=True)[0]
        
        # Rating distribution
        rating_dist = frappe.db.sql("""
            SELECT rating, COUNT(*) as count
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
            GROUP BY rating
            ORDER BY rating DESC
        """, as_dict=True)
        
        return {
            'success': True,
            'data': reviews,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'current_page': (offset // limit) + 1 if limit > 0 else 1,
                'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
            },
            'statistics': {
                'total_reviews': stats['total_reviews'],
                'average_rating': round(stats['avg_rating'], 2) if stats['avg_rating'] else 0,
                'min_rating': stats['min_rating'],
                'max_rating': stats['max_rating'],
                'companies_with_reviews': stats['companies_with_reviews'],
                'unique_reviewers': stats['unique_reviewers'],
                'rating_distribution': rating_dist
            }
        }
    except Exception as e:
        frappe.log_error(f"Get All Reviews Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def get_review_by_request_id():
    """Get a single review by request ID - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view reviews'
            }
        
        request_id = frappe.local.form_dict.get('request_id')
        if not request_id:
            return {'success': False, 'message': 'request_id is required'}
        
        if not frappe.db.exists('Logistics Request', request_id):
            return {'success': False, 'message': 'Request not found'}
        
        # Get review details
        review = frappe.db.sql("""
            SELECT 
                name as request_id,
                company_name,
                rating,
                review_comment,
                service_aspects,
                rated_at,
                rating_updated_at,
                full_name as user_name,
                user_email,
                user_phone,
                status,
                completed_at,
                pickup_city,
                delivery_city,
                pickup_address,
                delivery_address,
                estimated_cost,
                actual_cost,
                created_at,
                assigned_date
            FROM `tabLogistics Request`
            WHERE name = %s
        """, (request_id,), as_dict=True)
        
        if not review:
            return {'success': False, 'message': 'Review not found'}
        
        review = review[0]
        
        # Parse service aspects
        if review.get('service_aspects'):
            try:
                review['service_aspects'] = json.loads(review['service_aspects'])
            except:
                review['service_aspects'] = {}
        
        # Check if review exists
        has_review = bool(review.get('rating') and review.get('rating') > 0)
        
        return {
            'success': True,
            'data': review,
            'has_review': has_review
        }
    except Exception as e:
        frappe.log_error(f"Get Review Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def admin_update_review():
    """Update a review as admin - Admin only"""
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to update reviews'
            }
        
        data = get_request_data()
        request_id = data.get('request_id')
        
        if not request_id:
            return {'success': False, 'message': 'request_id is required'}
        
        if not frappe.db.exists('Logistics Request', request_id):
            return {'success': False, 'message': 'Request not found'}
        
        request_doc = frappe.get_doc('Logistics Request', request_id)
        
        updated_fields = []
        
        # Update rating
        if 'rating' in data:
            try:
                new_rating = int(data.get('rating'))
                if new_rating < 1 or new_rating > 5:
                    return {'success': False, 'message': 'Rating must be between 1 and 5'}
                request_doc.db_set('rating', new_rating, update_modified=False)
                updated_fields.append('rating')
            except (ValueError, TypeError):
                return {'success': False, 'message': 'Invalid rating format'}
        
        # Update review comment
        if 'review_comment' in data:
            review_comment = data.get('review_comment') or ''
            if len(review_comment) > 1000:
                return {'success': False, 'message': 'Review comment too long (max 1000 characters)'}
            request_doc.db_set('review_comment', review_comment, update_modified=False)
            updated_fields.append('review_comment')
        
        # Update service aspects
        if 'service_aspects' in data:
            service_aspects = data.get('service_aspects')
            if isinstance(service_aspects, dict):
                request_doc.db_set('service_aspects', json.dumps(service_aspects), update_modified=False)
                updated_fields.append('service_aspects')
            elif isinstance(service_aspects, str):
                # Already JSON string
                request_doc.db_set('service_aspects', service_aspects, update_modified=False)
                updated_fields.append('service_aspects')
        
        if updated_fields:
            request_doc.db_set('rating_updated_at', datetime.now(), update_modified=False)
            frappe.db.commit()
            
            # Recalculate company average
            if request_doc.company_name:
                from localmoves.api.rating_review import update_company_average_rating
                update_company_average_rating(request_doc.company_name)
        
        return {
            'success': True,
            'message': f'Review updated successfully. Updated fields: {", ".join(updated_fields)}',
            'updated_fields': updated_fields,
            'data': {
                'request_id': request_id,
                'rating': request_doc.rating,
                'review_comment': request_doc.review_comment
            }
        }
    except Exception as e:
        frappe.log_error(f"Admin Update Review Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def admin_delete_review():
    """Delete a review as admin - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to delete reviews'
            }
        
        data = get_request_data()
        request_id = data.get('request_id')
        
        if not request_id:
            return {'success': False, 'message': 'request_id is required'}
        
        if not frappe.db.exists('Logistics Request', request_id):
            return {'success': False, 'message': 'Request not found'}
        
        request_doc = frappe.get_doc('Logistics Request', request_id)
        
        # Check if review exists
        if not request_doc.rating or request_doc.rating == 0:
            return {'success': False, 'message': 'No review found for this request'}
        
        company_name = request_doc.company_name
        
        # Clear all review fields
        request_doc.db_set('rating', None, update_modified=False)
        request_doc.db_set('review_comment', None, update_modified=False)
        request_doc.db_set('service_aspects', None, update_modified=False)
        request_doc.db_set('rated_at', None, update_modified=False)
        request_doc.db_set('rating_updated_at', None, update_modified=False)
        
        frappe.db.commit()
        
        # Recalculate company average
        if company_name:
            from localmoves.api.rating_review import update_company_average_rating
            update_company_average_rating(company_name)
        
        return {
            'success': True,
            'message': 'Review deleted successfully',
            'request_id': request_id
        }
    except Exception as e:
        frappe.log_error(f"Admin Delete Review Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def get_reviews_by_company():
    """Get all reviews for a specific company - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view reviews'
            }
        
        data = get_request_data()
        company_name = data.get('company_name')
        
        if not company_name:
            return {'success': False, 'message': 'company_name is required'}
        
        if not frappe.db.exists('Logistics Company', company_name):
            return {'success': False, 'message': 'Company not found'}
        
        reviews = frappe.db.sql("""
            SELECT 
                name as request_id,
                rating,
                review_comment,
                service_aspects,
                rated_at,
                rating_updated_at,
                full_name as user_name,
                user_email,
                status,
                completed_at,
                pickup_city,
                delivery_city
            FROM `tabLogistics Request`
            WHERE company_name = %s
            AND rating IS NOT NULL
            AND rating > 0
            ORDER BY rated_at DESC
        """, (company_name,), as_dict=True)
        
        # Parse service aspects
        for review in reviews:
            if review.get('service_aspects'):
                try:
                    review['service_aspects'] = json.loads(review['service_aspects'])
                except:
                    review['service_aspects'] = {}
        
        # Get company rating summary
        company = frappe.get_doc('Logistics Company', company_name)
        
        return {
            'success': True,
            'company_name': company_name,
            'rating_summary': {
                'average_rating': getattr(company, 'average_rating', 0),
                'total_ratings': getattr(company, 'total_ratings', 0)
            },
            'data': reviews,
            'count': len(reviews)
        }
    except Exception as e:
        frappe.log_error(f"Get Company Reviews Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def get_reviews_by_user():
    """Get all reviews submitted by a specific user - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view reviews'
            }
        
        data = get_request_data()
        user_email = data.get('user_email')
        
        if not user_email:
            return {'success': False, 'message': 'user_email is required'}
        
        reviews = frappe.db.sql("""
            SELECT 
                name as request_id,
                company_name,
                rating,
                review_comment,
                service_aspects,
                rated_at,
                rating_updated_at,
                status,
                completed_at,
                pickup_city,
                delivery_city
            FROM `tabLogistics Request`
            WHERE user_email = %s
            AND rating IS NOT NULL
            AND rating > 0
            ORDER BY rated_at DESC
        """, (user_email,), as_dict=True)
        
        # Parse service aspects
        for review in reviews:
            if review.get('service_aspects'):
                try:
                    review['service_aspects'] = json.loads(review['service_aspects'])
                except:
                    review['service_aspects'] = {}
        
        # Get user statistics
        stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_reviews,
                AVG(rating) as avg_rating_given,
                COUNT(DISTINCT company_name) as companies_reviewed
            FROM `tabLogistics Request`
            WHERE user_email = %s
            AND rating IS NOT NULL
            AND rating > 0
        """, (user_email,), as_dict=True)[0]
        
        return {
            'success': True,
            'user_email': user_email,
            'statistics': {
                'total_reviews': stats['total_reviews'],
                'average_rating_given': round(stats['avg_rating_given'], 2) if stats['avg_rating_given'] else 0,
                'companies_reviewed': stats['companies_reviewed']
            },
            'data': reviews,
            'count': len(reviews)
        }
    except Exception as e:
        frappe.log_error(f"Get User Reviews Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def bulk_delete_reviews():
    """Bulk delete reviews - Admin only"""
    try:
        ensure_session_data()
        
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to delete reviews'
            }
        
        data = get_request_data()
        request_ids = data.get('request_ids', [])
        
        if not request_ids:
            return {'success': False, 'message': 'request_ids array is required'}
        
        if isinstance(request_ids, str):
            request_ids = json.loads(request_ids)
        
        deleted_count = 0
        errors = []
        affected_companies = set()
        
        for request_id in request_ids:
            try:
                if not frappe.db.exists('Logistics Request', request_id):
                    errors.append({'request_id': request_id, 'error': 'Request not found'})
                    continue
                
                request_doc = frappe.get_doc('Logistics Request', request_id)
                
                if not request_doc.rating or request_doc.rating == 0:
                    errors.append({'request_id': request_id, 'error': 'No review to delete'})
                    continue
                
                if request_doc.company_name:
                    affected_companies.add(request_doc.company_name)
                
                # Clear review fields
                request_doc.db_set('rating', None, update_modified=False)
                request_doc.db_set('review_comment', None, update_modified=False)
                request_doc.db_set('service_aspects', None, update_modified=False)
                request_doc.db_set('rated_at', None, update_modified=False)
                request_doc.db_set('rating_updated_at', None, update_modified=False)
                
                deleted_count += 1
                
            except Exception as e:
                errors.append({'request_id': request_id, 'error': str(e)})
        
        frappe.db.commit()
        
        # Recalculate company averages
        from localmoves.api.rating_review import update_company_average_rating
        for company_name in affected_companies:
            update_company_average_rating(company_name)
        
        return {
            'success': True,
            'message': f'Deleted {deleted_count} reviews successfully',
            'deleted_count': deleted_count,
            'error_count': len(errors),
            'errors': errors,
            'affected_companies': list(affected_companies)
        }
    except Exception as e:
        frappe.log_error(f"Bulk Delete Reviews Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def get_review_statistics():
    """Get comprehensive review statistics - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view review statistics'
            }
        
        # Overall statistics
        overall_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_reviews,
                AVG(rating) as avg_rating,
                MIN(rating) as min_rating,
                MAX(rating) as max_rating,
                COUNT(DISTINCT company_name) as companies_with_reviews,
                COUNT(DISTINCT user_email) as unique_reviewers
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
        """, as_dict=True)[0]
        
        # Rating distribution
        rating_distribution = frappe.db.sql("""
            SELECT rating, COUNT(*) as count
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
            GROUP BY rating
            ORDER BY rating DESC
        """, as_dict=True)
        
        # Top rated companies
        top_companies = frappe.db.sql("""
            SELECT 
                company_name,
                AVG(rating) as avg_rating,
                COUNT(*) as review_count
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
            AND company_name IS NOT NULL
            GROUP BY company_name
            HAVING COUNT(*) >= 3
            ORDER BY avg_rating DESC, review_count DESC
            LIMIT 10
        """, as_dict=True)
        
        # Recent reviews
        recent_reviews = frappe.db.sql("""
            SELECT 
                name as request_id,
                company_name,
                rating,
                review_comment,
                rated_at,
                user_email,
                full_name as user_name
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
            ORDER BY rated_at DESC
            LIMIT 10
        """, as_dict=True)
        
        # Reviews by status
        reviews_by_status = frappe.db.sql("""
            SELECT 
                status,
                COUNT(*) as review_count,
                AVG(rating) as avg_rating
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
            GROUP BY status
            ORDER BY review_count DESC
        """, as_dict=True)
        
        # Monthly review trends (last 12 months)
        monthly_trends = frappe.db.sql("""
            SELECT 
                DATE_FORMAT(rated_at, '%Y-%m') as month,
                COUNT(*) as review_count,
                AVG(rating) as avg_rating
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL 
            AND rating > 0
            AND rated_at >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(rated_at, '%Y-%m')
            ORDER BY month ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'statistics': {
                'overall': {
                    'total_reviews': overall_stats['total_reviews'],
                    'average_rating': round(overall_stats['avg_rating'], 2) if overall_stats['avg_rating'] else 0,
                    'min_rating': overall_stats['min_rating'],
                    'max_rating': overall_stats['max_rating'],
                    'companies_with_reviews': overall_stats['companies_with_reviews'],
                    'unique_reviewers': overall_stats['unique_reviewers']
                },
                'rating_distribution': rating_distribution,
                'top_rated_companies': top_companies,
                'recent_reviews': recent_reviews,
                'reviews_by_status': reviews_by_status,
                'monthly_trends': monthly_trends
            }
        }
    except Exception as e:
        frappe.log_error(f"Get Review Statistics Error: {str(e)}")
        return {'success': False, 'error': str(e)}


@frappe.whitelist(allow_guest=False)
def search_reviews():
    """Search reviews by various criteria - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to search reviews'
            }
        
        data = get_request_data()
        
        search_term = data.get('search_term', '')
        company_name = data.get('company_name')
        user_email = data.get('user_email')
        min_rating = data.get('min_rating')
        max_rating = data.get('max_rating')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        filters = []
        filter_values = {}
        
        if search_term:
            filters.append("(review_comment LIKE %(search_term)s OR full_name LIKE %(search_term)s)")
            filter_values['search_term'] = f"%{search_term}%"
        
        if company_name:
            filters.append("company_name = %(company_name)s")
            filter_values['company_name'] = company_name
        
        if user_email:
            filters.append("user_email = %(user_email)s")
            filter_values['user_email'] = user_email
        
        if min_rating:
            filters.append("rating >= %(min_rating)s")
            filter_values['min_rating'] = min_rating
        
        if max_rating:
            filters.append("rating <= %(max_rating)s")
            filter_values['max_rating'] = max_rating
        
        if date_from:
            filters.append("DATE(rated_at) >= %(date_from)s")
            filter_values['date_from'] = date_from
        
        if date_to:
            filters.append("DATE(rated_at) <= %(date_to)s")
            filter_values['date_to'] = date_to
        
        where_clause = " AND ".join(filters) if filters else "1=1"
        
        results = frappe.db.sql(f"""
            SELECT 
                name as request_id,
                company_name,
                rating,
                review_comment,
                service_aspects,
                rated_at,
                full_name as user_name,
                user_email,
                status,
                pickup_city,
                delivery_city
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL
            AND rating > 0
            AND {where_clause}
            ORDER BY rated_at DESC
            LIMIT 100
        """, filter_values, as_dict=True)
        
        # Parse service aspects
        for review in results:
            if review.get('service_aspects'):
                try:
                    review['service_aspects'] = json.loads(review['service_aspects'])
                except:
                    review['service_aspects'] = {}
        
        return {
            'success': True,
            'data': results,
            'count': len(results),
            'search_criteria': {
                'search_term': search_term,
                'company_name': company_name,
                'user_email': user_email,
                'min_rating': min_rating,
                'max_rating': max_rating,
                'date_from': date_from,
                'date_to': date_to
            }
        }
    except Exception as e:
        frappe.log_error(f"Search Reviews Error: {str(e)}")
        return {'success': False, 'error': str(e)}



@frappe.whitelist(allow_guest=False)
def get_review_statistics():
    """Get comprehensive review statistics - Admin only"""
    try:
        # Permission check
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: You do not have permission to view review statistics'
            }
        
        # Overall statistics
        overall_stats = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_reviews,
                AVG(rating) as avg_rating,
                MIN(rating) as min_rating,
                MAX(rating) as max_rating,
                COUNT(DISTINCT company_name) as companies_with_reviews,
                COUNT(DISTINCT user_email) as unique_reviewers
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
        """, as_dict=True)[0]
        
        # Rating distribution
        rating_distribution = frappe.db.sql("""
            SELECT rating, COUNT(*) as count
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
            GROUP BY rating
            ORDER BY rating DESC
        """, as_dict=True)
        
        # Top rated companies
        top_companies = frappe.db.sql("""
            SELECT 
                company_name,
                AVG(rating) as avg_rating,
                COUNT(*) as review_count
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
            AND company_name IS NOT NULL
            GROUP BY company_name
            HAVING COUNT(*) >= 3
            ORDER BY avg_rating DESC, review_count DESC
            LIMIT 10
        """, as_dict=True)
        
        # Recent reviews
        recent_reviews = frappe.db.sql("""
            SELECT 
                name as request_id,
                company_name,
                rating,
                review_comment,
                rated_at,
                user_email,
                full_name as user_name
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
            ORDER BY rated_at DESC
            LIMIT 10
        """, as_dict=True)
        
        # Reviews by status
        reviews_by_status = frappe.db.sql("""
            SELECT 
                status,
                COUNT(*) as review_count,
                AVG(rating) as avg_rating
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL AND rating > 0
            GROUP BY status
            ORDER BY review_count DESC
        """, as_dict=True)
        
        # Monthly review trends (last 12 months)
        monthly_trends = frappe.db.sql("""
            SELECT 
                DATE_FORMAT(rated_at, '%Y-%m') as month,
                COUNT(*) as review_count,
                AVG(rating) as avg_rating
            FROM `tabLogistics Request`
            WHERE rating IS NOT NULL 
            AND rating > 0
            AND rated_at >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(rated_at, '%Y-%m')
            ORDER BY month ASC
        """, as_dict=True)
        
        return {
            'success': True,
            'statistics': {
                'overall': {
                    'total_reviews': overall_stats['total_reviews'],
                    'average_rating': round(overall_stats['avg_rating'], 2) if overall_stats['avg_rating'] else 0,
                    'min_rating': overall_stats['min_rating'],
                    'max_rating': overall_stats['max_rating'],
                    'companies_with_reviews': overall_stats['companies_with_reviews'],
                    'unique_reviewers': overall_stats['unique_reviewers']
                },
                'rating_distribution': rating_distribution,
                'top_rated_companies': top_companies,
                'recent_reviews': recent_reviews,
                'reviews_by_status': reviews_by_status,
                'monthly_trends': monthly_trends
            }
        }
    except Exception as e:
        frappe.log_error(f"Get Review Statistics Error: {str(e)}")
        return {'success': False, 'error': str(e)}

# ===== CONTACT US API =====

@frappe.whitelist(allow_guest=True)
def submit_contact_form():
    """Public API - Anyone can submit a contact form"""
    try:
        ensure_session_data()
        
        data = get_request_data()
        
        # Validate required fields
        required_fields = ['name', 'email', 'message']
        for field in required_fields:
            if not data.get(field):
                return {'success': False, 'message': f'{field} is required'}
        
        # Validate email format
        email = data.get('email')
        if not frappe.utils.validate_email_address(email):
            return {'success': False, 'message': 'Invalid email address'}
        
        # Create contact us record
        contact_doc = frappe.new_doc('Contact Us')
        contact_doc.name_of_sender = data.get('name')
        contact_doc.email = email
        contact_doc.message = data.get('message')
        contact_doc.status = 'New'
        
        contact_doc.flags.ignore_version = True
        contact_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            'success': True, 
            'message': 'Thank you for contacting us! We will get back to you soon.',
            'data': {
                'id': contact_doc.name,
                'name': contact_doc.name_of_sender,
                'email': contact_doc.email,
                'status': contact_doc.status,
                'created_at': contact_doc.created_at
            }
        }
        
    except Exception as e:
        frappe.log_error(f"Submit Contact Form Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def get_all_contact_submissions():
    """Admin only - Get all contact form submissions"""
    try:
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        data = get_request_data()
        filters = {}
        
        if data.get('status'):
            filters['status'] = data.get('status')
        
        contacts = frappe.get_all('Contact Us',
            fields=['name', 'name_of_sender', 'email', 'message', 'status', 
                    'admin_response', 'created_at', 'responded_at'],
            filters=filters,
            order_by='created_at desc'
        )
        
        return {'success': True, 'data': contacts, 'count': len(contacts)}
        
    except Exception as e:
        frappe.log_error(f"Get Contact Submissions Error: {str(e)}")
        return {'success': False, 'error': str(e)}



@frappe.whitelist()
def get_contact_submission():
    """Admin only - Get a single contact submission by ID"""
    try:
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        # Try multiple methods to get contact_id
        contact_id = None
        
        # Method 1: form_dict
        if hasattr(frappe, 'form_dict') and frappe.form_dict:
            contact_id = frappe.form_dict.get('contact_id')
        
        # Method 2: local.form_dict
        if not contact_id and hasattr(frappe.local, 'form_dict') and frappe.local.form_dict:
            contact_id = frappe.local.form_dict.get('contact_id')
        
        # Method 3: request.args (for GET query parameters)
        if not contact_id and hasattr(frappe, 'request') and frappe.request:
            if hasattr(frappe.request, 'args'):
                contact_id = frappe.request.args.get('contact_id')
        
        # Method 4: Try get_request_data
        if not contact_id:
            try:
                data = get_request_data()
                if data and isinstance(data, dict):
                    contact_id = data.get('contact_id')
            except:
                pass
        
        if not contact_id:
            # Debug info to help troubleshoot
            debug_info = {
                'form_dict': dict(frappe.local.form_dict) if hasattr(frappe.local, 'form_dict') and frappe.local.form_dict else None,
                'request_args': dict(frappe.request.args) if hasattr(frappe, 'request') and hasattr(frappe.request, 'args') else None
            }
            return {
                'success': False, 
                'message': 'contact_id is required',
                'debug': debug_info
            }

        if not frappe.db.exists('Contact Us', contact_id):
            return {'success': False, 'message': 'Contact submission not found'}
        
        contact = frappe.get_doc('Contact Us', contact_id)
        print(contact_id)
        if contact.status == 'New':
            contact.status = 'Read'
            contact.flags.ignore_version = True
            contact.save(ignore_permissions=True)
            frappe.db.commit()
        
        return {'success': True, 'data': contact.as_dict()}
        
    except Exception as e:
        import traceback
        frappe.log_error(f"Get Contact Submission Error: {str(e)}\n{traceback.format_exc()}")
        return {'success': False, 'error': str(e)}



@frappe.whitelist()
def respond_to_contact():
    """Admin only - Respond to a contact submission and send email to user"""
    try:
        ensure_session_data()
        
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        data = get_request_data()
        contact_id = data.get('contact_id')
        admin_response = data.get('admin_response')
        
        if not contact_id:
            return {'success': False, 'message': 'contact_id is required'}
        
        if not admin_response:
            return {'success': False, 'message': 'admin_response is required'}
        
        if not frappe.db.exists('Contact Us', contact_id):
            return {'success': False, 'message': 'Contact submission not found'}
        
        contact = frappe.get_doc('Contact Us', contact_id)
        contact.admin_response = admin_response
        contact.status = 'Responded'
        contact.responded_at = frappe.utils.now()
        
        contact.flags.ignore_version = True
        contact.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Send email to the user
        try:
            send_response_email(
                recipient_email=contact.email,
                recipient_name=contact.name_of_sender,
                original_message=contact.message,
                admin_response=admin_response
            )
            email_sent = True
            email_message = 'Response saved and email sent successfully'
        except Exception as email_error:
            email_sent = False
            email_message = f'Response saved but email failed: {str(email_error)}'
            frappe.log_error(f"Email Send Error: {str(email_error)}", "Contact Response Email")
        
        return {
            'success': True, 
            'message': email_message,
            'email_sent': email_sent,
            'data': contact.as_dict()
        }
        
    except Exception as e:
        frappe.log_error(f"Respond to Contact Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


def send_response_email(recipient_email, recipient_name, original_message, admin_response):
    """Send email response to user who submitted contact form"""
    
    # Email subject
    subject = "Re: Your Message to LocalMoves - We've Responded!"
    
    # Email body with HTML formatting
    message = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9;">
        <div style="background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #2563eb; margin: 0; font-size: 28px;">LocalMoves</h1>
                <p style="color: #6b7280; margin-top: 5px;">Logistics Management System</p>
            </div>
            
            <!-- Greeting -->
            <p style="font-size: 16px; color: #374151; margin-bottom: 20px;">
                Dear {recipient_name},
            </p>
            
            <p style="font-size: 16px; color: #374151; margin-bottom: 25px;">
                Thank you for contacting us! We have reviewed your message and here is our response:
            </p>
            
            <!-- Original Message -->
            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin-bottom: 25px; border-left: 4px solid #9ca3af;">
                <p style="font-weight: bold; color: #4b5563; margin-bottom: 10px; font-size: 14px;">
                    YOUR MESSAGE:
                </p>
                <p style="color: #6b7280; font-size: 14px; line-height: 1.6; margin: 0; font-style: italic;">
                    "{original_message}"
                </p>
            </div>
            
            <!-- Admin Response -->
            <div style="background-color: #eff6ff; padding: 20px; border-radius: 8px; margin-bottom: 25px; border-left: 4px solid #2563eb;">
                <p style="font-weight: bold; color: #1e40af; margin-bottom: 10px; font-size: 14px;">
                    OUR RESPONSE:
                </p>
                <p style="color: #1e3a8a; font-size: 15px; line-height: 1.6; margin: 0;">
                    {admin_response}
                </p>
            </div>
            
            <!-- Call to Action -->
            <p style="font-size: 16px; color: #374151; margin-bottom: 20px;">
                If you have any further questions, please don't hesitate to reach out to us again.
            </p>
            
            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center;">
                <p style="font-size: 14px; color: #6b7280; margin-bottom: 10px;">
                    Best regards,<br>
                    <strong style="color: #2563eb;">LocalMoves Support Team</strong>
                </p>
                <p style="font-size: 12px; color: #9ca3af; margin-top: 15px;">
                    This is an automated response to your contact form submission.<br>
                    Please do not reply directly to this email.
                </p>
            </div>
        </div>
        
        <!-- Bottom Note -->
        <p style="text-align: center; font-size: 12px; color: #9ca3af; margin-top: 20px;">
            © 2024 LocalMoves. All rights reserved.
        </p>
    </div>
    """
    
    # Send the email
    frappe.sendmail(
        recipients=[recipient_email],
        subject=subject,
        message=message,
        now=True,  # Send immediately
        retry=3    # Retry 3 times if it fails
    )
    
    frappe.logger().info(f"Response email sent to {recipient_email}")

@frappe.whitelist()
def update_contact_status():
    """Admin only - Update contact submission status"""
    try:
        ensure_session_data()
        
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        data = get_request_data()
        contact_id = data.get('contact_id')
        status = data.get('status')
        
        if not contact_id:
            return {'success': False, 'message': 'contact_id is required'}
        
        if not status:
            return {'success': False, 'message': 'status is required'}
        
        valid_statuses = ['New', 'Read', 'Responded', 'Closed']
        if status not in valid_statuses:
            return {
                'success': False, 
                'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }
        
        if not frappe.db.exists('Contact Us', contact_id):
            return {'success': False, 'message': 'Contact submission not found'}
        
        contact = frappe.get_doc('Contact Us', contact_id)
        contact.status = status
        
        contact.flags.ignore_version = True
        contact.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {
            'success': True, 
            'message': 'Status updated successfully',
            'data': contact.as_dict()
        }
        
    except Exception as e:
        frappe.log_error(f"Update Contact Status Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def delete_contact_submission():
    """Admin only - Delete a contact submission"""
    try:
        if not check_admin_permission():
            return {
                'success': False, 
                'message': 'Access Denied: Admin permission required'
            }
        
        data = get_request_data()
        contact_id = data.get('contact_id')
        
        if not contact_id:
            return {'success': False, 'message': 'contact_id is required'}
        
        if not frappe.db.exists('Contact Us', contact_id):
            return {'success': False, 'message': 'Contact submission not found'}
        
        frappe.delete_doc('Contact Us', contact_id, ignore_permissions=True)
        frappe.db.commit()
        
        return {'success': True, 'message': 'Contact submission deleted successfully'}
        
    except Exception as e:
        frappe.log_error(f"Delete Contact Submission Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'error': str(e)}
    


# Add at the very end of dashboard.py
# REPLACE the get_system_config_from_db() function at the END of dashboard.py with this:

def get_system_config_from_db():
    """Get system config from DB, create if doesn't exist"""
    try:
        # Direct SQL check - more reliable
        exists = frappe.db.sql("""
            SELECT name FROM `tabSystem Configuration` 
            WHERE name = 'admin_config' 
            LIMIT 1
        """, as_dict=True)
        
        if not exists:
            # Create new record using SQL
            frappe.db.sql("""
                INSERT INTO `tabSystem Configuration` 
                (name, config_name, config_data, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                "admin_config",
                "admin_config", 
                json.dumps(DEFAULT_SYSTEM_CONFIG),
                1,
                datetime.now(),
                datetime.now()
            ))
            frappe.db.commit()
            frappe.logger().info("Created System Configuration via SQL")
            return DEFAULT_SYSTEM_CONFIG
        
        # Get existing record
        result = frappe.db.sql("""
            SELECT config_data 
            FROM `tabSystem Configuration` 
            WHERE name = 'admin_config'
        """, as_dict=True)
        
        if result and result[0].get('config_data'):
            config_data = json.loads(result[0]['config_data'])
            # Merge with defaults for any missing keys
            merged = DEFAULT_SYSTEM_CONFIG.copy()
            merged.update(config_data)
            return merged
        
        return DEFAULT_SYSTEM_CONFIG
        
    except Exception as e:
        frappe.log_error(f"Get System Config Error: {str(e)}")
        return DEFAULT_SYSTEM_CONFIG

def get_deposit_percentage():
    """Get current deposit percentage from config"""
    try:
        config = get_system_config_from_db()
        return config.get('deposit_percentage', 10)
    except:
        return 10

@frappe.whitelist(allow_guest=False)
def get_system_settings():
    """Get all system settings - Admin only"""
    if not check_admin_permission():
        return {'success': False, 'message': 'Admin only'}
    return {'success': True, 'data': get_system_config_from_db()}

@frappe.whitelist(allow_guest=False)
def update_deposit_percentage_quick():
    """Quick update deposit percentage - Admin only"""
    if not check_admin_permission():
        return {'success': False, 'message': 'Admin only'}
    
    data = get_request_data()
    new_pct = float(data.get('deposit_percentage', 10))
    
    if new_pct < 0 or new_pct > 100:
        return {'success': False, 'message': 'Must be 0-100'}
    
    try:
        # Get OLD value first
        old_result = frappe.db.sql("""
            SELECT config_data 
            FROM `tabSystem Configuration` 
            WHERE name = 'admin_config'
        """, as_dict=True)
        
        if old_result:
            old_config = json.loads(old_result[0]['config_data'])
            old_pct = old_config.get('deposit_percentage', 10)
        else:
            old_pct = 10
        
        # Update the value
        config = get_system_config_from_db()
        config['deposit_percentage'] = new_pct
        
        # Direct SQL update
        frappe.db.sql("""
            UPDATE `tabSystem Configuration`
            SET config_data = %s, updated_at = %s
            WHERE name = 'admin_config'
        """, (json.dumps(config), datetime.now()))
        
        frappe.db.commit()
        
        return {
            'success': True,
            'message': f'Updated from {old_pct}% to {new_pct}%',
            'old_value': old_pct,
            'new_value': new_pct
        }
    except Exception as e:
        frappe.log_error(f"Update Deposit % Error: {str(e)}")
        frappe.db.rollback()
        return {'success': False, 'message': str(e)}

@frappe.whitelist(allow_guest=True)
def get_current_deposit_percentage():
    """Public API to get current deposit percentage"""
    config = get_system_config_from_db()
    return {
        'success': True,
        'deposit_percentage': config.get('deposit_percentage', 10),
        'currency': config.get('currency', 'GBP')
    }


# ===== CONFIGURATION MANAGEMENT (ADMIN ONLY) =====

@frappe.whitelist()
def get_system_configuration():
    """Get all system configuration - Admin only"""
    if not check_admin_permission():
        frappe.throw(_("You do not have permission to access system configuration"), frappe.PermissionError)
    
    try:
        config = get_config()
        return {
            'success': True,
            'data': config
        }
    except Exception as e:
        frappe.log_error(title="Get Config Error", message=str(e))
        return {
            'success': False,
            'message': str(e)
        }


@frappe.whitelist()
@frappe.whitelist()
def update_system_configuration():
    """Update system configuration - Admin only"""
    if not check_admin_permission():
        frappe.throw(_("You do not have permission to update system configuration"), frappe.PermissionError)
    
    try:
        data = get_request_data()
        
        # Get current config and update with new values
        current_config = get_config()
        
        # Update specific config sections if provided
        if data.get('pricing'):
            current_config['pricing'].update(data['pricing'])
        if data.get('vehicle_capacities'):
            current_config['vehicle_capacities'].update(data['vehicle_capacities'])
        if data.get('property_volumes'):
            current_config['property_volumes'].update(data['property_volumes'])
        if data.get('additional_spaces'):
            current_config['additional_spaces'].update(data['additional_spaces'])
        if data.get('quantity_multipliers'):
            current_config['quantity_multipliers'].update(data['quantity_multipliers'])
        if data.get('vehicle_space_multipliers'):
            current_config['vehicle_space_multipliers'].update(data['vehicle_space_multipliers'])
        if data.get('plan_limits'):
            current_config['plan_limits'].update(data['plan_limits'])
        if data.get('collection_assessment'):
            current_config['collection_assessment'].update(data['collection_assessment'])
        if data.get('notice_period_multipliers'):
            current_config['notice_period_multipliers'].update(data['notice_period_multipliers'])
        if data.get('move_day_multipliers'):
            current_config['move_day_multipliers'].update(data['move_day_multipliers'])
        
        # Save updated config
        success, message = update_config(current_config)
        
        if success:
            return {
                'success': True,
                'message': 'Configuration updated successfully',
                'data': current_config
            }
        else:
            return {
                'success': False,
                'message': message
            }
    except Exception as e:
        frappe.log_error(title="Update Config Error", message=str(e))
        return {
            'success': False,
            'message': str(e)
        }


@frappe.whitelist()
def get_pricing_configuration():
    """Get pricing configuration"""
    if not check_admin_permission():
        frappe.throw(_("You do not have permission to access pricing configuration"), frappe.PermissionError)
    
    try:
        pricing = get_config('pricing')
        return {
            'success': True,
            'data': pricing
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}


@frappe.whitelist()
def update_pricing_configuration():
    """Update pricing configuration"""
    if not check_admin_permission():
        frappe.throw(_("You do not have permission to update pricing"), frappe.PermissionError)
    
    try:
        data = get_request_data()
        config = get_config()
        
        # Update pricing section
        config['pricing'].update(data.get('pricing', {}))
        
        if update_config(config):
            return {
                'success': True,
                'message': 'Pricing configuration updated successfully',
                'data': config['pricing']
            }
        else:
            return {'success': False, 'message': 'Failed to update pricing'}
    except Exception as e:
        frappe.log_error(title="Update Pricing Error", message=str(e))
        return {'success': False, 'message': str(e)}


@frappe.whitelist()
def get_vehicle_configuration():
    """Get vehicle and capacity configuration"""
    if not check_admin_permission():
        frappe.throw(_("You do not have permission to access vehicle configuration"), frappe.PermissionError)
    
    try:
        config_data = get_config()
        return {
            'success': True,
            'vehicle_capacities': config_data.get('vehicle_capacities', {}),
            'vehicle_space_multipliers': config_data.get('vehicle_space_multipliers', {}),
            'property_volumes': config_data.get('property_volumes', {}),
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}


@frappe.whitelist()
def update_vehicle_configuration():
    """Update vehicle configuration"""
    if not check_admin_permission():
        frappe.throw(_("You do not have permission to update vehicle configuration"), frappe.PermissionError)
    
    try:
        data = get_request_data()
        config = get_config()
        
        if data.get('vehicle_capacities'):
            config['vehicle_capacities'].update(data['vehicle_capacities'])
        if data.get('vehicle_space_multipliers'):
            config['vehicle_space_multipliers'].update(data['vehicle_space_multipliers'])
        if data.get('property_volumes'):
            config['property_volumes'].update(data['property_volumes'])
        
        if update_config(config):
            return {
                'success': True,
                'message': 'Vehicle configuration updated successfully',
                'data': {
                    'vehicle_capacities': config['vehicle_capacities'],
                    'vehicle_space_multipliers': config['vehicle_space_multipliers'],
                    'property_volumes': config['property_volumes'],
                }
            }
        else:
            return {'success': False, 'message': 'Failed to update vehicle configuration'}
    except Exception as e:
        frappe.log_error(title="Update Vehicle Config Error", message=str(e))
        return {'success': False, 'message': str(e)}


@frappe.whitelist()
def get_multiplier_configuration():
    """Get all multiplier configurations"""
    if not check_admin_permission():
        frappe.throw(_("You do not have permission to access multiplier configuration"), frappe.PermissionError)
    
    try:
        config_data = get_config()
        return {
            'success': True,
            'quantity_multipliers': config_data.get('quantity_multipliers', {}),
            'collection_assessment': config_data.get('collection_assessment', {}),
            'notice_period_multipliers': config_data.get('notice_period_multipliers', {}),
            'move_day_multipliers': config_data.get('move_day_multipliers', {}),
        }
    except Exception as e:
        return {'success': False, 'message': str(e)}


@frappe.whitelist()
def update_multiplier_configuration():
    """Update multiplier configurations"""
    if not check_admin_permission():
        frappe.throw(_("You do not have permission to update multipliers"), frappe.PermissionError)
    
    try:
        data = get_request_data()
        config = get_config()
        
        if data.get('quantity_multipliers'):
            config['quantity_multipliers'].update(data['quantity_multipliers'])
        if data.get('collection_assessment'):
            config['collection_assessment'].update(data['collection_assessment'])
        if data.get('notice_period_multipliers'):
            config['notice_period_multipliers'].update(data['notice_period_multipliers'])
        if data.get('move_day_multipliers'):
            config['move_day_multipliers'].update(data['move_day_multipliers'])
        
        if update_config(config):
            return {
                'success': True,
                'message': 'Multiplier configuration updated successfully',
                'data': {
                    'quantity_multipliers': config['quantity_multipliers'],
                    'collection_assessment': config['collection_assessment'],
                    'notice_period_multipliers': config['notice_period_multipliers'],
                    'move_day_multipliers': config['move_day_multipliers'],
                }
            }
        else:
            return {'success': False, 'message': 'Failed to update multiplier configuration'}
    except Exception as e:
        frappe.log_error(title="Update Multiplier Config Error", message=str(e))
        return {'success': False, 'message': str(e)}



# @frappe.whitelist()
# def manage_signup_verification_template():
#     """
#     Manage Signup Verification Email Template
#     Used in: auth.py line 166
   
#     Request:
#     {
#         "action": "get|update|reset|preview",
#         "email_subject": "...",  // for update action
#         "email_body": "...",     // for update action
#         "sample_variables": {}   // for preview action
#     }
#     """
#     try:
#         check_admin_permission()
       
#         data = get_request_data()
#         action = data.get("action", "get")
       
#         TEMPLATE_NAME = "signup_verification"
#         TEMPLATE_INFO = {
#             "name": "signup_verification",
#             "title": "User Signup Verification",
#             "file": "auth.py",
#             "line": 166,
#             "default_subject": "LocalMoves - Verify Your Email",
#             "default_body": """
#             <div style="font-family: Arial, sans-serif; max-width: 600px; background: #f5f5f5; padding: 20px;">
#                 <div style="background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
#                     <h2 style="color: #333; margin-top: 0;">Welcome to LocalMoves!</h2>
#                     <p style="color: #666; font-size: 16px;">Thank you for signing up. Please verify your email address by clicking the link below:</p>
#                     <div style="text-align: center; margin: 30px 0;">
#                         <a href="{verification_link}" style="background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">Verify Email</a>
#                     </div>
#                     <p style="color: #999; font-size: 14px;">This link expires in {expiry_time}.</p>
#                     <p style="color: #666;">If you didn't create this account, please ignore this email.</p>
#                     <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
#                     <p style="color: #999; font-size: 12px; margin: 0;">© LocalMoves - All Rights Reserved</p>
#                 </div>
#             </div>
#             """,
#             "variables": ["user_name", "user_email", "verification_link", "expiry_time"]
#         }
       
#         if action == "get":
#             try:
#                 # Query database directly for the template
#                 result = frappe.db.sql("""
#                     SELECT email_subject, email_body, modified
#                     FROM `tabEmail Template Config`
#                     WHERE template_name = %s
#                     LIMIT 1
#                 """, TEMPLATE_NAME, as_dict=True)
               
#                 if result:
#                     return {
#                         "success": True,
#                         "template": TEMPLATE_INFO,
#                         "email_subject": result[0]['email_subject'],
#                         "email_body": result[0]['email_body'],
#                         "is_custom": True,
#                         "last_updated": result[0]['modified']
#                     }
#                 else:
#                     return {
#                         "success": True,
#                         "template": TEMPLATE_INFO,
#                         "email_subject": TEMPLATE_INFO["default_subject"],
#                         "email_body": TEMPLATE_INFO["default_body"],
#                         "is_custom": False
#                     }
#             except Exception as get_error:
#                 return {"success": False, "message": f"Get error: {str(get_error)}"}
       
#         elif action == "update":
#             email_subject = data.get("email_subject")
#             email_body = data.get("email_body")
           
#             if not email_subject or not email_body:
#                 return {"success": False, "message": "email_subject and email_body are required"}
           
#             try:
#                 # Check if document with this template_name already exists
#                 existing = frappe.db.sql("""
#                     SELECT name FROM `tabEmail Template Config`
#                     WHERE template_name = %s
#                     LIMIT 1
#                 """, TEMPLATE_NAME, as_dict=True)
               
#                 if existing:
#                     # Update existing document directly via database
#                     frappe.db.sql("""
#                         UPDATE `tabEmail Template Config`
#                         SET email_subject = %s, email_body = %s, modified = NOW()
#                         WHERE name = %s
#                     """, (email_subject, email_body, existing[0]['name']))
#                 else:
#                     # Create new document directly via database
#                     frappe.db.sql("""
#                         INSERT INTO `tabEmail Template Config`
#                         (name, template_name, email_subject, email_body, modified, creation, owner, modified_by)
#                         VALUES (%s, %s, %s, %s, NOW(), NOW(), %s, %s)
#                     """, (TEMPLATE_NAME, TEMPLATE_NAME, email_subject, email_body, frappe.session.user, frappe.session.user))
               
#                 frappe.db.commit()
#                 frappe.clear_cache()
               
#                 return {
#                     "success": True,
#                     "message": "Signup verification email template updated",
#                     "updated_at": frappe.utils.now()
#                 }
#             except Exception as save_error:
#                 frappe.db.rollback()
#                 return {"success": False, "message": f"Save error: {str(save_error)}"}
       
#         elif action == "reset":
#             if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
#                 frappe.delete_doc("Email Template Config", TEMPLATE_NAME, ignore_permissions=True)
#                 frappe.db.commit()
           
#             return {
#                 "success": True,
#                 "message": "Signup verification email template reset to default"
#             }
       
#         elif action == "preview":
#             sample_variables = data.get("sample_variables", {})
           
#             if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
#                 template_doc = frappe.get_doc("Email Template Config", TEMPLATE_NAME)
#                 template_html = template_doc.email_body
#                 template_subject = template_doc.email_subject
#             else:
#                 template_html = TEMPLATE_INFO["default_body"]
#                 template_subject = TEMPLATE_INFO["default_subject"]
           
#             preview_html = template_html
#             preview_subject = template_subject
           
#             for var_name, var_value in sample_variables.items():
#                 placeholder = "{" + var_name + "}"
#                 preview_html = preview_html.replace(placeholder, str(var_value))
#                 preview_subject = preview_subject.replace(placeholder, str(var_value))
           
#             return {
#                 "success": True,
#                 "preview_subject": preview_subject,
#                 "preview_html": preview_html
#             }
       
#         else:
#             return {"success": False, "message": f"Invalid action: {action}"}
           
#     except Exception as e:
#         frappe.log_error(f"Signup Verification Template Error: {str(e)}")
#         return {"success": False, "message": str(e)}


@frappe.whitelist()
def manage_signup_verification_template():
    """
    Manage Signup Verification Email Template
    Used in: auth.py line 166
   
    Request:
    {
        "action": "get|update|reset|preview",
        "email_subject": "...",  // for update action
        "email_body": "...",     // for update action
        "sample_variables": {}   // for preview action
    }
    """
    try:
        check_admin_permission()
       
        data = get_request_data()
        action = data.get("action", "get")
       
        TEMPLATE_NAME = "signup_verification"
        TEMPLATE_INFO = {
            "name": "signup_verification",
            "title": "Logistics Manager Welcome Email",
            "file": "auth.py",
            "line": 200,
            "default_subject": "🎉 Welcome to LocalMoves - Logistics Manager Account Created",
            "default_body": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; background: #f5f5f5; padding: 20px;">
                <div style="background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                    <h2 style="color: #333; margin-top: 0;">Welcome to LocalMoves, {user_name}!</h2>
                    <p style="color: #666; font-size: 16px;">Your Logistics Manager account has been successfully created. Below are your login credentials:</p>
                    <div style="background: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea;">
                        <p style="margin: 0 0 10px 0;"><strong style="color: #333;">Email:</strong> <span style="color: #666;">{user_email}</span></p>
                        <p style="margin: 0 0 10px 0;"><strong style="color: #333;">Phone:</strong> <span style="color: #666;">{phone}</span></p>
                        <p style="margin: 0;"><strong style="color: #333;">Temporary Password:</strong> <span style="color: #666; font-family: monospace; font-size: 14px;">{password}</span></p>
                    </div>
                    <p style="color: #666; font-size: 16px; margin-top: 20px;"><strong>Important:</strong> Please change your password immediately upon first login for security.</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://localmoves.com/login" style="background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">Login to Dashboard</a>
                    </div>
                    <p style="color: #666;">If you have any questions, please contact our support team.</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    <p style="color: #999; font-size: 12px; margin: 0;">© LocalMoves - All Rights Reserved</p>
                </div>
            </div>
            """,
            "variables": ["user_name", "user_email", "phone", "password"]
        }
       
        if action == "get":
            try:
                # Query database directly for the template
                result = frappe.db.sql("""
                    SELECT email_subject, email_body, modified
                    FROM `tabEmail Template Config`
                    WHERE template_name = %s
                    LIMIT 1
                """, TEMPLATE_NAME, as_dict=True)
               
                if result:
                    return {
                        "success": True,
                        "template": TEMPLATE_INFO,
                        "email_subject": result[0]['email_subject'],
                        "email_body": result[0]['email_body'],
                        "is_custom": True,
                        "last_updated": result[0]['modified']
                    }
                else:
                    return {
                        "success": True,
                        "template": TEMPLATE_INFO,
                        "email_subject": TEMPLATE_INFO["default_subject"],
                        "email_body": TEMPLATE_INFO["default_body"],
                        "is_custom": False
                    }
            except Exception as get_error:
                return {"success": False, "message": f"Get error: {str(get_error)}"}
       
        elif action == "update":
            email_subject = data.get("email_subject")
            email_body = data.get("email_body")
           
            if not email_subject or not email_body:
                return {"success": False, "message": "email_subject and email_body are required"}
           
            try:
                # Check if document with this template_name already exists
                existing = frappe.db.sql("""
                    SELECT name FROM `tabEmail Template Config`
                    WHERE template_name = %s
                    LIMIT 1
                """, TEMPLATE_NAME, as_dict=True)
               
                if existing:
                    # Update existing document directly via database
                    frappe.db.sql("""
                        UPDATE `tabEmail Template Config`
                        SET email_subject = %s, email_body = %s, modified = NOW()
                        WHERE name = %s
                    """, (email_subject, email_body, existing[0]['name']))
                else:
                    # Create new document directly via database
                    frappe.db.sql("""
                        INSERT INTO `tabEmail Template Config`
                        (name, template_name, email_subject, email_body, modified, creation, owner, modified_by)
                        VALUES (%s, %s, %s, %s, NOW(), NOW(), %s, %s)
                    """, (TEMPLATE_NAME, TEMPLATE_NAME, email_subject, email_body, frappe.session.user, frappe.session.user))
               
                frappe.db.commit()
                frappe.clear_cache()
               
                return {
                    "success": True,
                    "message": "Signup verification email template updated",
                    "updated_at": frappe.utils.now()
                }
            except Exception as save_error:
                frappe.db.rollback()
                return {"success": False, "message": f"Save error: {str(save_error)}"}
       
        elif action == "reset":
            if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
                frappe.delete_doc("Email Template Config", TEMPLATE_NAME, ignore_permissions=True)
                frappe.db.commit()
           
            return {
                "success": True,
                "message": "Signup verification email template reset to default"
            }
       
        elif action == "preview":
            sample_variables = data.get("sample_variables", {})
           
            if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
                template_doc = frappe.get_doc("Email Template Config", TEMPLATE_NAME)
                template_html = template_doc.email_body
                template_subject = template_doc.email_subject
            else:
                template_html = TEMPLATE_INFO["default_body"]
                template_subject = TEMPLATE_INFO["default_subject"]
           
            preview_html = template_html
            preview_subject = template_subject
           
            for var_name, var_value in sample_variables.items():
                placeholder = "{" + var_name + "}"
                preview_html = preview_html.replace(placeholder, str(var_value))
                preview_subject = preview_subject.replace(placeholder, str(var_value))
           
            return {
                "success": True,
                "preview_subject": preview_subject,
                "preview_html": preview_html
            }
       
        else:
            return {"success": False, "message": f"Invalid action: {action}"}
           
    except Exception as e:
        frappe.log_error(f"Signup Verification Template Error: {str(e)}")
        return {"success": False, "message": str(e)}



@frappe.whitelist()
def manage_password_reset_template():
    """
    Manage Password Reset Email Template
    Used in: auth.py line 545
    """
    try:
        check_admin_permission()
       
        data = get_request_data()
        action = data.get("action", "get")
       
        TEMPLATE_NAME = "password_reset"
        TEMPLATE_INFO = {
            "name": "password_reset",
            "title": "Password Reset Request",
            "file": "auth.py",
            "line": 545,
            "default_subject": "LocalMoves - Reset Your Password",
            "default_body": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; background: #f5f5f5; padding: 20px;">
                <div style="background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                    <h2 style="color: #333; margin-top: 0;">Password Reset Request</h2>
                    <p style="color: #666; font-size: 16px;">We received a request to reset your password. Click the link below to proceed:</p>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" style="background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">Reset Password</a>
                    </div>
                    <p style="color: #999; font-size: 14px;">This link expires in {expiry_time}.</p>
                    <p style="color: #666;"><strong>Important:</strong> If you didn't request this, please ignore this email. Your account is secure and this link is for you only.</p>
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    <p style="color: #999; font-size: 12px; margin: 0;">© LocalMoves - All Rights Reserved</p>
                </div>
            </div>
            """,
            "variables": ["user_email", "reset_link", "expiry_time"]  # ✅ REMOVED "user_name"
        }
       
        if action == "get":
            result = frappe.db.sql("""
                SELECT email_subject, email_body, modified
                FROM `tabEmail Template Config`
                WHERE template_name = %s
                LIMIT 1
            """, TEMPLATE_NAME, as_dict=True)
            if result:
                return {
                    "success": True,
                    "template": TEMPLATE_INFO,
                    "email_subject": result[0]['email_subject'],
                    "email_body": result[0]['email_body'],
                    "is_custom": True,
                    "last_updated": result[0]['modified']
                }
            else:
                return {
                    "success": True,
                    "template": TEMPLATE_INFO,
                    "email_subject": TEMPLATE_INFO["default_subject"],
                    "email_body": TEMPLATE_INFO["default_body"],
                    "is_custom": False
                }
       
        elif action == "update":
            email_subject = data.get("email_subject")
            email_body = data.get("email_body")
           
            if not email_subject or not email_body:
                return {"success": False, "message": "email_subject and email_body are required"}
           
            try:
                # Check if document with this template_name already exists
                existing = frappe.db.sql("""
                    SELECT name FROM `tabEmail Template Config`
                    WHERE template_name = %s
                    LIMIT 1
                """, TEMPLATE_NAME, as_dict=True)
               
                if existing:
                    # Update existing document directly via database
                    frappe.db.sql("""
                        UPDATE `tabEmail Template Config`
                        SET email_subject = %s, email_body = %s, modified = NOW()
                        WHERE name = %s
                    """, (email_subject, email_body, existing[0]['name']))
                else:
                    # Create new document directly via database
                    frappe.db.sql("""
                        INSERT INTO `tabEmail Template Config`
                        (name, template_name, email_subject, email_body, modified, creation, owner, modified_by)
                        VALUES (%s, %s, %s, %s, NOW(), NOW(), %s, %s)
                    """, (TEMPLATE_NAME, TEMPLATE_NAME, email_subject, email_body, frappe.session.user, frappe.session.user))
               
                frappe.db.commit()
                frappe.clear_cache()
               
                return {
                    "success": True,
                    "message": "Password reset email template updated",
                    "updated_at": frappe.utils.now()
                }
            except Exception as save_error:
                frappe.db.rollback()
                return {"success": False, "message": f"Save error: {str(save_error)}"}
       
        elif action == "reset":
            if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
                frappe.delete_doc("Email Template Config", TEMPLATE_NAME, ignore_permissions=True)
                frappe.db.commit()
           
            return {
                "success": True,
                "message": "Password reset email template reset to default"
            }
       
        elif action == "preview":
            sample_variables = data.get("sample_variables", {})
           
            if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
                template_doc = frappe.get_doc("Email Template Config", TEMPLATE_NAME)
                template_html = template_doc.email_body
                template_subject = template_doc.email_subject
            else:
                template_html = TEMPLATE_INFO["default_body"]
                template_subject = TEMPLATE_INFO["default_subject"]
           
            preview_html = template_html
            preview_subject = template_subject
           
            for var_name, var_value in sample_variables.items():
                placeholder = "{" + var_name + "}"
                preview_html = preview_html.replace(placeholder, str(var_value))
                preview_subject = preview_subject.replace(placeholder, str(var_value))
           
            return {
                "success": True,
                "preview_subject": preview_subject,
                "preview_html": preview_html
            }
       
        else:
            return {"success": False, "message": f"Invalid action: {action}"}
           
    except Exception as e:
        frappe.log_error(f"Password Reset Template Error: {str(e)}")
        return {"success": False, "message": str(e)}
    
@frappe.whitelist()
def manage_property_search_template():
    """
    Manage Property Search Results Email Template
    Used in: company.py line 1082
    """
    try:
        check_admin_permission()
       
        data = get_request_data()
        action = data.get("action", "get")
       
        TEMPLATE_NAME = "property_search_results"
        TEMPLATE_INFO = {
            "name": "property_search_results",
            "title": "Property Search Results",
            "file": "company.py",
            "line": 1082,
            "default_subject": "LocalMoves - Your Moving Company Search Results",
            "default_body": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; background: #f5f5f5; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 25px; border-radius: 10px; color: white; text-align: center; margin-bottom: 30px;">
                    <h2 style="margin: 0; font-size: 24px;">Welcome to LocalMoves!</h2>
                    <p style="margin: 0; font-size: 18px;">We found {company_count} Companies for Your Move!</p>
                </div>
               
                {company_list}
               
                <div style="margin-top: 30px; padding: 25px; background-color: #f0f9ff; border-radius: 8px; text-align: center;">
                    <p style="margin: 0 0 15px 0; color: #1e40af; font-size: 16px; font-weight: 600;">
                        Ready to book your move?
                    </p>
                    <a href="{view_all_link}" style="display: inline-block; padding: 14px 35px; background-color: #667eea; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; font-size: 15px;">
                        View All Companies & Get Exact Quotes
                    </a>
                </div>
               
                <div style="margin-top: 25px; text-align: center; color: #999; font-size: 12px;">
                    <p style="margin: 0;">© LocalMoves - Your Trusted Moving Partner</p>
                </div>
            </div>
            """,
            "variables": ["user_name", "company_count", "company_list", "view_all_link"]
        }
       
        if action == "get":
            result = frappe.db.sql("""
                SELECT email_subject, email_body, modified
                FROM `tabEmail Template Config`
                WHERE template_name = %s
                LIMIT 1
            """, TEMPLATE_NAME, as_dict=True)
            if result:
                return {
                    "success": True,
                    "template": TEMPLATE_INFO,
                    "email_subject": result[0]['email_subject'],
                    "email_body": result[0]['email_body'],
                    "is_custom": True,
                    "last_updated": result[0]['modified']
                }
            else:
                return {
                    "success": True,
                    "template": TEMPLATE_INFO,
                    "email_subject": TEMPLATE_INFO["default_subject"],
                    "email_body": TEMPLATE_INFO["default_body"],
                    "is_custom": False
                }
       
        elif action == "update":
            email_subject = data.get("email_subject")
            email_body = data.get("email_body")
           
            if not email_subject or not email_body:
                return {"success": False, "message": "email_subject and email_body are required"}
           
            try:
                # Check if document with this template_name already exists
                existing = frappe.db.sql("""
                    SELECT name FROM `tabEmail Template Config`
                    WHERE template_name = %s
                    LIMIT 1
                """, TEMPLATE_NAME, as_dict=True)
               
                if existing:
                    # Update existing document directly via database
                    frappe.db.sql("""
                        UPDATE `tabEmail Template Config`
                        SET email_subject = %s, email_body = %s, modified = NOW()
                        WHERE name = %s
                    """, (email_subject, email_body, existing[0]['name']))
                else:
                    # Create new document directly via database
                    frappe.db.sql("""
                        INSERT INTO `tabEmail Template Config`
                        (name, template_name, email_subject, email_body, modified, creation, owner, modified_by)
                        VALUES (%s, %s, %s, %s, NOW(), NOW(), %s, %s)
                    """, (TEMPLATE_NAME, TEMPLATE_NAME, email_subject, email_body, frappe.session.user, frappe.session.user))
               
                frappe.db.commit()
                frappe.clear_cache()
               
                return {
                    "success": True,
                    "message": "Property search results email template updated",
                    "updated_at": frappe.utils.now()
                }
            except Exception as save_error:
                frappe.db.rollback()
                return {"success": False, "message": f"Save error: {str(save_error)}"}
       
        elif action == "reset":
            if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
                frappe.delete_doc("Email Template Config", TEMPLATE_NAME, ignore_permissions=True)
                frappe.db.commit()
           
            return {
                "success": True,
                "message": "Property search results email template reset to default"
            }
       
        elif action == "preview":
            sample_variables = data.get("sample_variables", {})
           
            if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
                template_doc = frappe.get_doc("Email Template Config", TEMPLATE_NAME)
                template_html = template_doc.email_body
                template_subject = template_doc.email_subject
            else:
                template_html = TEMPLATE_INFO["default_body"]
                template_subject = TEMPLATE_INFO["default_subject"]
           
            preview_html = template_html
            preview_subject = template_subject
           
            for var_name, var_value in sample_variables.items():
                placeholder = "{" + var_name + "}"
                preview_html = preview_html.replace(placeholder, str(var_value))
                preview_subject = preview_subject.replace(placeholder, str(var_value))
           
            return {
                "success": True,
                "preview_subject": preview_subject,
                "preview_html": preview_html
            }
       
        else:
            return {"success": False, "message": f"Invalid action: {action}"}
           
    except Exception as e:
        frappe.log_error(f"Property Search Template Error: {str(e)}")
        return {"success": False, "message": str(e)}




# @frappe.whitelist()
# def manage_payment_confirmation_template():
#     """
#     Manage Payment Confirmation Email Template
#     Used in: payment_handler.py line 382
#     """
#     try:
#         check_admin_permission()
       
#         data = get_request_data()
#         action = data.get("action", "get")
       
#         TEMPLATE_NAME = "payment_confirmation"
#         TEMPLATE_INFO = {
#             "name": "payment_confirmation",
#             "title": "Payment Confirmation",
#             "file": "payment_handler.py",
#             "line": 382,
#             "default_subject": "LocalMoves - Payment Confirmed",
#             "default_body": """
#             <div style="font-family: Arial, sans-serif; max-width: 600px; background: #f5f5f5; padding: 20px;">
#                 <div style="background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
#                     <h2 style="color: #333; margin-top: 0;">✓ Payment Confirmed</h2>
#                     <p style="color: #666; font-size: 16px;">Thank you for your payment!</p>
                   
#                     <div style="background-color: #f0f9ff; padding: 20px; border-radius: 5px; margin: 20px 0;">
#                         <p style="margin: 8px 0;"><strong>Amount:</strong> £{amount}</p>
#                         <p style="margin: 8px 0;"><strong>Transaction ID:</strong> {transaction_id}</p>
#                         <p style="margin: 8px 0;"><strong>Date:</strong> {payment_date}</p>
#                     </div>
                   
#                     <p style="color: #666;">Your booking is confirmed. A booking confirmation email will follow shortly.</p>
#                     <p style="color: #666;">If you have any questions, please contact <strong>support@localmoves.com</strong></p>
                   
#                     <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
#                     <p style="color: #999; font-size: 12px; margin: 0;">© LocalMoves - All Rights Reserved</p>
#                 </div>
#             </div>
#             """,
#             "variables": ["user_name", "amount", "transaction_id", "payment_date"]
#         }
       
#         if action == "get":
#             result = frappe.db.sql("""
#                 SELECT email_subject, email_body, modified
#                 FROM `tabEmail Template Config`
#                 WHERE template_name = %s
#                 LIMIT 1
#             """, TEMPLATE_NAME, as_dict=True)
#             if result:
#                 return {
#                     "success": True,
#                     "template": TEMPLATE_INFO,
#                     "email_subject": result[0]['email_subject'],
#                     "email_body": result[0]['email_body'],
#                     "is_custom": True,
#                     "last_updated": result[0]['modified']
#                 }
#             else:
#                 return {
#                     "success": True,
#                     "template": TEMPLATE_INFO,
#                     "email_subject": TEMPLATE_INFO["default_subject"],
#                     "email_body": TEMPLATE_INFO["default_body"],
#                     "is_custom": False
#                 }
       
#         elif action == "update":
#             email_subject = data.get("email_subject")
#             email_body = data.get("email_body")
           
#             if not email_subject or not email_body:
#                 return {"success": False, "message": "email_subject and email_body are required"}
           
#             try:
#                 # Check if document with this template_name already exists
#                 existing = frappe.db.sql("""
#                     SELECT name FROM `tabEmail Template Config`
#                     WHERE template_name = %s
#                     LIMIT 1
#                 """, TEMPLATE_NAME, as_dict=True)
               
#                 if existing:
#                     # Update existing document directly via database
#                     frappe.db.sql("""
#                         UPDATE `tabEmail Template Config`
#                         SET email_subject = %s, email_body = %s, modified = NOW()
#                         WHERE name = %s
#                     """, (email_subject, email_body, existing[0]['name']))
#                 else:
#                     # Create new document directly via database
#                     frappe.db.sql("""
#                         INSERT INTO `tabEmail Template Config`
#                         (name, template_name, email_subject, email_body, modified, creation, owner, modified_by)
#                         VALUES (%s, %s, %s, %s, NOW(), NOW(), %s, %s)
#                     """, (TEMPLATE_NAME, TEMPLATE_NAME, email_subject, email_body, frappe.session.user, frappe.session.user))
               
#                 frappe.db.commit()
#                 frappe.clear_cache()
               
#                 return {
#                     "success": True,
#                     "message": "Payment confirmation email template updated",
#                     "updated_at": frappe.utils.now()
#                 }
#             except Exception as save_error:
#                 frappe.db.rollback()
#                 return {"success": False, "message": f"Save error: {str(save_error)}"}
       
#         elif action == "reset":
#             if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
#                 frappe.delete_doc("Email Template Config", TEMPLATE_NAME, ignore_permissions=True)
#                 frappe.db.commit()
           
#             return {
#                 "success": True,
#                 "message": "Payment confirmation email template reset to default"
#             }
       
#         elif action == "preview":
#             sample_variables = data.get("sample_variables", {})
           
#             if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
#                 template_doc = frappe.get_doc("Email Template Config", TEMPLATE_NAME)
#                 template_html = template_doc.email_body
#                 template_subject = template_doc.email_subject
#             else:
#                 template_html = TEMPLATE_INFO["default_body"]
#                 template_subject = TEMPLATE_INFO["default_subject"]
           
#             preview_html = template_html
#             preview_subject = template_subject
           
#             for var_name, var_value in sample_variables.items():
#                 placeholder = "{" + var_name + "}"
#                 preview_html = preview_html.replace(placeholder, str(var_value))
#                 preview_subject = preview_subject.replace(placeholder, str(var_value))
           
#             return {
#                 "success": True,
#                 "preview_subject": preview_subject,
#                 "preview_html": preview_html
#             }
       
#         else:
#             return {"success": False, "message": f"Invalid action: {action}"}
           
#     except Exception as e:
#         frappe.log_error(f"Payment Confirmation Template Error: {str(e)}")
#         return {"success": False, "message": str(e)}

@frappe.whitelist()
def manage_payment_confirmation_template():
    """
    Manage Payment Confirmation Email Template
    Used in: request_payment.py - send_payment_confirmation_email()
    """
    try:
        check_admin_permission()
       
        data = get_request_data()
        action = data.get("action", "get")
       
        TEMPLATE_NAME = "payment_confirmation"
        TEMPLATE_INFO = {
            "name": "payment_confirmation",
            "title": "Payment Confirmation",
            "file": "request_payment.py",
            "default_subject": "✅ Payment Confirmed - {request_id}",
            "default_body": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #28a745; padding-bottom: 10px;">
                    ✅ Payment Confirmed
                </h2>
               
                <div style="background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745;">
                    <p style="margin: 0; color: #155724;"><strong>Success!</strong> Your payment has been verified and your move is confirmed.</p>
                </div>
               
                <h3 style="color: #2c3e50;">Payment Details</h3>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background-color: #f8f9fa;">
                        <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Total Amount:</strong></td>
                        <td style="padding: 10px; border: 1px solid #dee2e6;">£{total_amount}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Deposit Paid:</strong></td>
                        <td style="padding: 10px; border: 1px solid #dee2e6;">£{deposit_amount} ✓</td>
                    </tr>
                    <tr style="background-color: #f8f9fa;">
                        <td style="padding: 10px; border: 1px solid #dee2e6;"><strong>Remaining Balance:</strong></td>
                        <td style="padding: 10px; border: 1px solid #dee2e6;">£{remaining_amount}</td>
                    </tr>
                </table>
               
                <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0; color: #856404;">
                        <strong>💰 Remaining Payment:</strong> The balance will be collected upon move completion.
                    </p>
                </div>
               
                <p style="color: #666; font-size: 12px; text-align: center; margin-top: 30px;">
                    Thank you for choosing LocalMoves!<br/>For support, contact us at support@localmoves.com
                </p>
            </div>
            """,
            "variables": ["user_name", "request_id", "total_amount", "deposit_amount", "remaining_amount", "company_name"]
        }
       
        if action == "get":
            result = frappe.db.sql("""
                SELECT email_subject, email_body, modified
                FROM `tabEmail Template Config`
                WHERE template_name = %s
                LIMIT 1
            """, TEMPLATE_NAME, as_dict=True)
            if result:
                return {
                    "success": True,
                    "template": TEMPLATE_INFO,
                    "email_subject": result[0]['email_subject'],
                    "email_body": result[0]['email_body'],
                    "is_custom": True,
                    "last_updated": result[0]['modified']
                }
            else:
                return {
                    "success": True,
                    "template": TEMPLATE_INFO,
                    "email_subject": TEMPLATE_INFO["default_subject"],
                    "email_body": TEMPLATE_INFO["default_body"],
                    "is_custom": False
                }
       
        elif action == "update":
            email_subject = data.get("email_subject")
            email_body = data.get("email_body")
           
            if not email_subject or not email_body:
                return {"success": False, "message": "email_subject and email_body are required"}
           
            try:
                existing = frappe.db.sql("""
                    SELECT name FROM `tabEmail Template Config`
                    WHERE template_name = %s
                    LIMIT 1
                """, TEMPLATE_NAME, as_dict=True)
               
                if existing:
                    frappe.db.sql("""
                        UPDATE `tabEmail Template Config`
                        SET email_subject = %s, email_body = %s, modified = NOW()
                        WHERE name = %s
                    """, (email_subject, email_body, existing[0]['name']))
                else:
                    frappe.db.sql("""
                        INSERT INTO `tabEmail Template Config`
                        (name, template_name, email_subject, email_body, modified, creation, owner, modified_by)
                        VALUES (%s, %s, %s, %s, NOW(), NOW(), %s, %s)
                    """, (TEMPLATE_NAME, TEMPLATE_NAME, email_subject, email_body, frappe.session.user, frappe.session.user))
               
                frappe.db.commit()
               
                return {
                    "success": True,
                    "message": "Payment confirmation email template updated",
                    "updated_at": frappe.utils.now()
                }
            except Exception as save_error:
                frappe.db.rollback()
                return {"success": False, "message": f"Save error: {str(save_error)}"}
       
        elif action == "reset":
            frappe.db.sql("DELETE FROM `tabEmail Template Config` WHERE template_name = %s", TEMPLATE_NAME)
            frappe.db.commit()
            return {
                "success": True,
                "message": "Payment confirmation email template reset to default"
            }
       
        elif action == "preview":
            sample_variables = data.get("sample_variables", {})
           
            template = frappe.db.sql("""
                SELECT email_subject, email_body
                FROM `tabEmail Template Config`
                WHERE template_name = %s
                LIMIT 1
            """, TEMPLATE_NAME, as_dict=True)
           
            if template:
                template_html = template[0]['email_body']
                template_subject = template[0]['email_subject']
            else:
                template_html = TEMPLATE_INFO["default_body"]
                template_subject = TEMPLATE_INFO["default_subject"]
           
            preview_html = template_html
            preview_subject = template_subject
           
            for var_name, var_value in sample_variables.items():
                placeholder = "{" + var_name + "}"
                preview_html = preview_html.replace(placeholder, str(var_value))
                preview_subject = preview_subject.replace(placeholder, str(var_value))
           
            return {
                "success": True,
                "preview_subject": preview_subject,
                "preview_html": preview_html
            }
       
        else:
            return {"success": False, "message": f"Invalid action: {action}"}
           
    except Exception as e:
        frappe.log_error(f"Payment Confirmation Template Error: {str(e)}")
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def manage_payment_request_template():
    """
    Manage Payment Request Email Template
    Used in: request_payment.py line 182
    """
    try:
        check_admin_permission()
       
        data = get_request_data()
        action = data.get("action", "get")
       
        TEMPLATE_NAME = "payment_request"
        TEMPLATE_INFO = {
            "name": "payment_request",
            "title": "Payment Request",
            "file": "request_payment.py",
            "line": 182,
            "default_subject": "LocalMoves - Payment Required",
            "default_body": """
            <div style="font-family: Arial, sans-serif; max-width: 600px; background: #f5f5f5; padding: 20px;">
                <div style="background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                    <h2 style="color: #333; margin-top: 0;">Payment Required</h2>
                    <p style="color: #666; font-size: 16px;">Dear {user_name},</p>
                    <p style="color: #666;">Please complete your payment to confirm your moving booking.</p>
                   
                    <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0;">
                        <p style="margin: 8px 0;"><strong>Amount Due:</strong> £{amount}</p>
                        <p style="margin: 8px 0;"><strong>Due Date:</strong> {due_date}</p>
                        <p style="margin: 8px 0;"><strong>Reference:</strong> {reference}</p>
                    </div>
                   
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{payment_link}" style="background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-size: 16px; font-weight: bold;">Pay Now</a>
                    </div>
                   
                    <p style="color: #666;">Questions? Contact us at <strong>support@localmoves.com</strong></p>
                   
                    <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                    <p style="color: #999; font-size: 12px; margin: 0;">© LocalMoves - All Rights Reserved</p>
                </div>
            </div>
            """,
            "variables": ["user_name", "amount", "due_date", "reference", "payment_link"]
        }
       
        if action == "get":
            result = frappe.db.sql("""
                SELECT email_subject, email_body, modified
                FROM `tabEmail Template Config`
                WHERE template_name = %s
                LIMIT 1
            """, TEMPLATE_NAME, as_dict=True)
            if result:
                return {
                    "success": True,
                    "template": TEMPLATE_INFO,
                    "email_subject": result[0]['email_subject'],
                    "email_body": result[0]['email_body'],
                    "is_custom": True,
                    "last_updated": result[0]['modified']
                }
            else:
                return {
                    "success": True,
                    "template": TEMPLATE_INFO,
                    "email_subject": TEMPLATE_INFO["default_subject"],
                    "email_body": TEMPLATE_INFO["default_body"],
                    "is_custom": False
                }
       
        elif action == "update":
            email_subject = data.get("email_subject")
            email_body = data.get("email_body")
           
            if not email_subject or not email_body:
                return {"success": False, "message": "email_subject and email_body are required"}
           
            try:
                # Check if document with this template_name already exists
                existing = frappe.db.sql("""
                    SELECT name FROM `tabEmail Template Config`
                    WHERE template_name = %s
                    LIMIT 1
                """, TEMPLATE_NAME, as_dict=True)
               
                if existing:
                    # Update existing document directly via database
                    frappe.db.sql("""
                        UPDATE `tabEmail Template Config`
                        SET email_subject = %s, email_body = %s, modified = NOW()
                        WHERE name = %s
                    """, (email_subject, email_body, existing[0]['name']))
                else:
                    # Create new document directly via database
                    frappe.db.sql("""
                        INSERT INTO `tabEmail Template Config`
                        (name, template_name, email_subject, email_body, modified, creation, owner, modified_by)
                        VALUES (%s, %s, %s, %s, NOW(), NOW(), %s, %s)
                    """, (TEMPLATE_NAME, TEMPLATE_NAME, email_subject, email_body, frappe.session.user, frappe.session.user))
               
                frappe.db.commit()
                frappe.clear_cache()
               
                return {
                    "success": True,
                    "message": "Payment request email template updated",
                    "updated_at": frappe.utils.now()
                }
            except Exception as save_error:
                frappe.db.rollback()
                return {"success": False, "message": f"Save error: {str(save_error)}"}


       
        elif action == "reset":
            if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
                frappe.delete_doc("Email Template Config", TEMPLATE_NAME, ignore_permissions=True)
                frappe.db.commit()
           
            return {
                "success": True,
                "message": "Payment request email template reset to default"
            }
       
        elif action == "preview":
            sample_variables = data.get("sample_variables", {})
           
            if frappe.db.exists("Email Template Config", TEMPLATE_NAME):
                template_doc = frappe.get_doc("Email Template Config", TEMPLATE_NAME)
                template_html = template_doc.email_body
                template_subject = template_doc.email_subject
            else:
                template_html = TEMPLATE_INFO["default_body"]
                template_subject = TEMPLATE_INFO["default_subject"]
           
            preview_html = template_html
            preview_subject = template_subject
           
            for var_name, var_value in sample_variables.items():
                placeholder = "{" + var_name + "}"
                preview_html = preview_html.replace(placeholder, str(var_value))
                preview_subject = preview_subject.replace(placeholder, str(var_value))
           
            return {
                "success": True,
                "preview_subject": preview_subject,
                "preview_html": preview_html
            }
       
        else:
            return {"success": False, "message": f"Invalid action: {action}"}
           
    except Exception as e:
        frappe.log_error(f"Payment Request Template Error: {str(e)}")
        return {"success": False, "message": str(e)}




@frappe.whitelist()
def manage_request_confirmation_template(action="get", email_subject=None, email_body=None):
    """Manage request confirmation email template
   
    Actions:
    - get: Retrieve current template (custom or default)
    - update: Update template with new content
    - reset: Reset to default template
    - preview: Preview template with sample data
    """
   
    try:
        TEMPLATE_NAME = "request_confirmation"
       
        DEFAULT_SUBJECT = "🚚 Logistics Request Confirmation - {request_id}"
       
        DEFAULT_BODY = """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
    <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
        🚚 Logistics Request Confirmation
    </h2>
   
    <p>Dear <strong>{user_name}</strong>,</p>
   
    <p>Your logistics request has been created successfully!</p>
   
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <h3 style="color: #2c3e50; margin-top: 0;">Request Details</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px; font-weight: bold; width: 40%;">Request ID:</td>
                <td style="padding: 8px;">{request_id}</td>
            </tr>
            <tr style="background-color: white;">
                <td style="padding: 8px; font-weight: bold;">Status:</td>
                <td style="padding: 8px;"><span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-size: 12px;">{status}</span></td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">Item Description:</td>
                <td style="padding: 8px;">{item_description}</td>
            </tr>
            <tr style="background-color: white;">
                <td style="padding: 8px; font-weight: bold;">Service Type:</td>
                <td style="padding: 8px;">{service_type}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">Assigned Company:</td>
                <td style="padding: 8px;">{company_name}</td>
            </tr>
            <tr style="background-color: white;">
                <td style="padding: 8px; font-weight: bold;">Expected Delivery:</td>
                <td style="padding: 8px;">{delivery_date}</td>
            </tr>
        </table>
    </div>
   
    <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <h3 style="color: #2c3e50; margin-top: 0;">📍 Pickup Location</h3>
        <p style="margin: 5px 0;"><strong>{pickup_address}</strong></p>
        <p style="margin: 5px 0; color: #666;">{pickup_city}, PIN: {pickup_pincode}</p>
    </div>
   
    <div style="background-color: #ffebee; padding: 15px; border-radius: 5px; margin: 20px 0;">
        <h3 style="color: #2c3e50; margin-top: 0;">🎯 Delivery Location</h3>
        <p style="margin: 5px 0;"><strong>{delivery_address}</strong></p>
        <p style="margin: 5px 0; color: #666;">{delivery_city}, PIN: {delivery_pincode}</p>
    </div>
   
    <div style="text-align: center; margin: 30px 0;">
        <h3 style="color: #2c3e50;">Route Map</h3>
        <a href="{route_map_url}" target="_blank" style="display: inline-block; text-decoration: none;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 60px 20px; border-radius: 8px; color: white; font-size: 18px; margin: 10px 0;">
                🗺️ Click to View Route Map<br/>
                <span style="font-size: 14px; opacity: 0.9;">From {pickup_city} to {delivery_city}</span>
            </div>
        </a>
    </div>
   
    <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
        <p style="margin: 0; color: #856404;">
            <strong>📱 Track Your Request:</strong> You can track your request status anytime by logging into your account.
        </p>
    </div>
   
    <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
        <p style="color: #666; font-size: 12px;">
            This is an automated email. Please do not reply to this message.<br/>
            For support, contact us at support@localmoves.com
        </p>
    </div>
</div>"""
       
        if action == "get":
            # Get current template from database
            template = frappe.db.sql("""
                SELECT email_subject, email_body
                FROM `tabEmail Template Config`
                WHERE template_name = %s
                LIMIT 1
            """, TEMPLATE_NAME, as_dict=True)
           
            if template:
                return {
                    "success": True,
                    "template_name": TEMPLATE_NAME,
                    "email_subject": template[0]['email_subject'],
                    "email_body": template[0]['email_body'],
                    "is_custom": True
                }
            else:
                return {
                    "success": True,
                    "template_name": TEMPLATE_NAME,
                    "email_subject": DEFAULT_SUBJECT,
                    "email_body": DEFAULT_BODY,
                    "is_custom": False,
                    "message": "Using default template. Click 'Update' to create a custom template."
                }
       
        elif action == "update":
            if not email_subject or not email_body:
                return {"success": False, "message": "Subject and body are required"}
           
            # Check if template exists
            template = frappe.db.sql("""
                SELECT name FROM `tabEmail Template Config`
                WHERE template_name = %s
                LIMIT 1
            """, TEMPLATE_NAME, as_dict=True)
           
            if template:
                # Update existing template
                frappe.db.sql("""
                    UPDATE `tabEmail Template Config`
                    SET email_subject = %s, email_body = %s, modified = %s
                    WHERE template_name = %s
                """, (email_subject, email_body, frappe.utils.now(), TEMPLATE_NAME))
            else:
                # Create new template
                frappe.db.sql("""
                    INSERT INTO `tabEmail Template Config`
                    (name, template_name, email_subject, email_body, creation, modified)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (TEMPLATE_NAME, TEMPLATE_NAME, email_subject, email_body, frappe.utils.now(), frappe.utils.now()))
           
            frappe.db.commit()
           
            return {
                "success": True,
                "message": "Request confirmation template updated successfully",
                "template_name": TEMPLATE_NAME,
                "email_subject": email_subject,
                "email_body": email_body
            }
       
        elif action == "reset":
            # Delete custom template to revert to defaults
            frappe.db.sql("""
                DELETE FROM `tabEmail Template Config`
                WHERE template_name = %s
            """, TEMPLATE_NAME)
           
            frappe.db.commit()
           
            return {
                "success": True,
                "message": "Template reset to default",
                "template_name": TEMPLATE_NAME,
                "email_subject": DEFAULT_SUBJECT,
                "email_body": DEFAULT_BODY
            }
       
        elif action == "preview":
            # Get current template
            template = frappe.db.sql("""
                SELECT email_subject, email_body
                FROM `tabEmail Template Config`
                WHERE template_name = %s
                LIMIT 1
            """, TEMPLATE_NAME, as_dict=True)
           
            if template:
                template_html = template[0]['email_body']
                template_subject = template[0]['email_subject']
            else:
                template_html = DEFAULT_BODY
                template_subject = DEFAULT_SUBJECT
           
            # Sample variables for preview
            sample_variables = {
                "user_name": "John Doe",
                "request_id": "REQ-2024-001",
                "status": "Pending",
                "item_description": "3 BHK House Furniture",
                "service_type": "Full Service",
                "company_name": "Local Movers Co.",
                "delivery_date": "2024-12-20",
                "pickup_address": "123 Main St",
                "pickup_city": "Mumbai",
                "pickup_pincode": "400001",
                "delivery_address": "456 Park Ave",
                "delivery_city": "Bangalore",
                "delivery_pincode": "560001",
                "route_map_url": "https://www.openstreetmap.org/directions"
            }
           
            preview_html = template_html
            preview_subject = template_subject
           
            for var_name, var_value in sample_variables.items():
                placeholder = "{" + var_name + "}"
                preview_html = preview_html.replace(placeholder, str(var_value))
                preview_subject = preview_subject.replace(placeholder, str(var_value))
           
            return {
                "success": True,
                "preview_subject": preview_subject,
                "preview_html": preview_html
            }
       
        else:
            return {"success": False, "message": f"Invalid action: {action}"}
           
    except Exception as e:
        frappe.log_error(f"Request Confirmation Template Error: {str(e)}")
        return {"success": False, "message": str(e)}


















