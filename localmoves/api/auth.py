import frappe
from frappe import _
from localmoves.utils.password_utils import hash_password, verify_password
from localmoves.utils.jwt_handler import generate_token, verify_token
from datetime import datetime, timedelta
from twilio.rest import Client
import re
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


def get_frontend_url():
    """Get frontend URL from environment variable or default"""
    return os.getenv("FRONTEND_URL", "http://localhost:5173")


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

# Twilio Configuration - Read from site_config for security
def get_twilio_credentials():
    """Get Twilio credentials from site config"""
    return {
        "account_sid": frappe.conf.get("twilio_account_sid") or "AC322e375ec4f6137d8125cf9c22be8854",
        "auth_token": frappe.conf.get("twilio_auth_token"),
        "verify_service_sid": frappe.conf.get("twilio_verify_service_sid") or "VA76730c198975898d00989888f6ca6443"
    }

def get_twilio_client():
    """Initialize and return Twilio client"""
    creds = get_twilio_credentials()
    if not creds["auth_token"]:
        frappe.throw("Twilio Auth Token not configured. Please add it to site_config.json")
    return Client(creds["account_sid"], creds["auth_token"])


@frappe.whitelist(allow_guest=True)
def send_otp(phone=None):
    """Send OTP via Twilio Verify before signup"""
    try:
        data = frappe.local.form_dict
        phone = phone or data.get("phone")

        if not phone:
            return {"success": False, "message": "Phone number is required"}

        # Ensure phone number is in E.164 format (+[country code][number])
        if not phone.startswith('+'):
            # Default to India if no country code provided
            phone = '+91' + phone.lstrip('0')

        # Prevent sending OTP to already registered number
        if frappe.db.exists("LocalMoves User", {"phone": phone}):
            return {"success": False, "message": "Phone number is already registered. Please login instead."}

        # Send OTP via Twilio Verify
        try:
            creds = get_twilio_credentials()
            client = get_twilio_client()
            verification = client.verify.v2.services(creds["verify_service_sid"]).verifications.create(
                to=phone,
                channel='sms'
            )

            # Log verification status
            frappe.log_error(f"Twilio Verification Status: {verification.status} for {phone}", "Twilio OTP Sent")

            return {
                "success": True,
                "message": f"OTP sent to {phone}",
                "data": {
                    "verification_sid": verification.sid,
                    "status": verification.status
                }
            }

        except Exception as twilio_error:
            frappe.log_error(f"Twilio Error: {str(twilio_error)}", "Twilio Send OTP Failed")
            return {"success": False, "message": f"Failed to send OTP: {str(twilio_error)}"}

    except Exception as e:
        frappe.log_error(f"Send OTP Error: {str(e)}")
        return {"success": False, "message": f"Failed to send OTP: {str(e)}"}


# def send_logistics_manager_welcome_email(user_email, full_name, phone, password):
#     """Send welcome email to newly registered Logistics Manager with credentials"""
#     try:
#         # Professional welcome email template
#         email_content = f"""
#         <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
#             <div style="text-align: center; margin-bottom: 30px;">
#                 <h1 style="color: #2c3e50; margin: 0;">🚚 Welcome to LocalMoves</h1>
#                 <p style="color: #7f8c8d; font-size: 16px;">Logistics Manager Account</p>
#             </div>
            
#             <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 8px; color: white; text-align: center; margin-bottom: 30px;">
#                 <h2 style="margin: 0 0 10px 0;">🎉 Account Created Successfully!</h2>
#                 <p style="margin: 0; font-size: 14px; opacity: 0.9;">Your Logistics Manager account is now active</p>
#             </div>
            
#             <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
#                 <h3 style="color: #2c3e50; margin-top: 0;">Your Account Details</h3>
#                 <table style="width: 100%; border-collapse: collapse;">
#                     <tr>
#                         <td style="padding: 10px 0; font-weight: bold; width: 40%;">Full Name:</td>
#                         <td style="padding: 10px 0;">{full_name}</td>
#                     </tr>
#                     <tr style="background-color: white;">
#                         <td style="padding: 10px 0; font-weight: bold;">Email:</td>
#                         <td style="padding: 10px 0;">{user_email}</td>
#                     </tr>
#                     <tr>
#                         <td style="padding: 10px 0; font-weight: bold;">Phone:</td>
#                         <td style="padding: 10px 0;">{phone}</td>
#                     </tr>
#                     <tr style="background-color: white;">
#                         <td style="padding: 10px 0; font-weight: bold;">Role:</td>
#                         <td style="padding: 10px 0;"><span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-size: 12px;">Logistics Manager</span></td>
#                     </tr>
#                     <tr>
#                         <td style="padding: 10px 0; font-weight: bold;">Account Status:</td>
#                         <td style="padding: 10px 0;"><span style="color: #28a745;">✅ Active & Verified</span></td>
#                     </tr>
#                 </table>
#             </div>
            
#             <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
#                 <h3 style="color: #856404; margin-top: 0;">🔐 Your Login Credentials</h3>
#                 <table style="width: 100%; border-collapse: collapse; background-color: white; padding: 15px; border-radius: 5px;">
#                     <tr>
#                         <td style="padding: 12px; font-weight: bold; width: 35%; border-bottom: 1px solid #e0e0e0;">Email/Username:</td>
#                         <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-family: 'Courier New', monospace; color: #2c3e50;">{user_email}</td>
#                     </tr>
#                     <tr>
#                         <td style="padding: 12px; font-weight: bold;">Password:</td>
#                         <td style="padding: 12px; font-family: 'Courier New', monospace; color: #d32f2f; font-weight: bold;">{password}</td>
#                     </tr>
#                 </table>
#                 <div style="margin-top: 15px; padding: 12px; background-color: #fff; border-radius: 5px; border: 1px solid #ffc107;">
#                     <p style="margin: 0; color: #856404; font-size: 13px;">
#                         <strong>⚠️ Security Notice:</strong> For your security, please change your password immediately after your first login. Delete this email after saving your credentials securely.
#                     </p>
#                 </div>
#             </div>
            
            
#             <div style="text-align: center; margin: 30px 0; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
#                 <p style="margin: 0 0 15px 0; color: #666;">Ready to get started?</p>
#                 <a href="https://your-app-url.com/login" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
#                     Login to Dashboard
#                 </a>
#             </div>
            
            
#             <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center;">
#                 <p style="color: #666; font-size: 14px; margin: 5px 0;">Need help? Contact our support team</p>
#                 <p style="color: #666; font-size: 14px; margin: 5px 0;">
#                     📧 <a href="mailto:support@localmoves.com" style="color: #667eea;">support@localmoves.com</a> | 
#                     📱 <a href="tel:+911234567890" style="color: #667eea;">+91 123 456 7890</a>
#                 </p>
#             </div>
            
#             <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
#                 <p style="color: #999; font-size: 12px; margin: 5px 0;">
#                     This email was sent to {user_email} because you registered as a Logistics Manager on LocalMoves.
#                 </p>
#                 <p style="color: #999; font-size: 12px; margin: 5px 0;">
#                     © 2025 LocalMoves - All Rights Reserved
#                 </p>
#             </div>
#         </div>
#         """
        
#         # Send email using Frappe's email system
#         frappe.sendmail(
#             recipients=[user_email],
#             sender="megha250903@gmail.com",  # Your configured sender email
#             subject="🎉 Welcome to LocalMoves - Logistics Manager Account Created",
#             message=email_content,
#             delayed=False,
#             now=True
#         )
        
#         frappe.logger().info(f"Welcome email sent successfully to Logistics Manager: {user_email}")
#         return True
        
#     except Exception as e:
#         frappe.log_error(f"Failed to send welcome email to {user_email}: {str(e)}", "Logistics Manager Welcome Email Error")
#         # Don't fail the signup if email fails
#         return False


def send_logistics_manager_welcome_email(user_email, full_name, phone, password):
    """Send welcome email to newly registered Logistics Manager with credentials"""
    try:
        # Professional welcome email template
        email_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #2c3e50; margin: 0;">🚚 Welcome to LocalMoves</h1>
                <p style="color: #7f8c8d; font-size: 16px;">Logistics Manager Account</p>
            </div>
           
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 8px; color: white; text-align: center; margin-bottom: 30px;">
                <h2 style="margin: 0 0 10px 0;">🎉 Account Created Successfully!</h2>
                <p style="margin: 0; font-size: 14px; opacity: 0.9;">Your Logistics Manager account is now active</p>
            </div>
           
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-top: 0;">Your Account Details</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold; width: 40%;">Full Name:</td>
                        <td style="padding: 10px 0;">{full_name}</td>
                    </tr>
                    <tr style="background-color: white;">
                        <td style="padding: 10px 0; font-weight: bold;">Email:</td>
                        <td style="padding: 10px 0;">{user_email}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Phone:</td>
                        <td style="padding: 10px 0;">{phone}</td>
                    </tr>
                    <tr style="background-color: white;">
                        <td style="padding: 10px 0; font-weight: bold;">Role:</td>
                        <td style="padding: 10px 0;"><span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-size: 12px;">Logistics Manager</span></td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0; font-weight: bold;">Account Status:</td>
                        <td style="padding: 10px 0;"><span style="color: #28a745;">✅ Active & Verified</span></td>
                    </tr>
                </table>
            </div>
           
            <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <h3 style="color: #856404; margin-top: 0;">🔐 Your Login Credentials</h3>
                <table style="width: 100%; border-collapse: collapse; background-color: white; padding: 15px; border-radius: 5px;">
                    <tr>
                        <td style="padding: 12px; font-weight: bold; width: 35%; border-bottom: 1px solid #e0e0e0;">Email/Username:</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e0e0e0; font-family: 'Courier New', monospace; color: #2c3e50;">{user_email}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; font-weight: bold;">Password:</td>
                        <td style="padding: 12px; font-family: 'Courier New', monospace; color: #d32f2f; font-weight: bold;">{password}</td>
                    </tr>
                </table>
                <div style="margin-top: 15px; padding: 12px; background-color: #fff; border-radius: 5px; border: 1px solid #ffc107;">
                    <p style="margin: 0; color: #856404; font-size: 13px;">
                        <strong>⚠️ Security Notice:</strong> For your security, please change your password immediately after your first login. Delete this email after saving your credentials securely.
                    </p>
                </div>
            </div>
           
           
            <div style="text-align: center; margin: 30px 0; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
                <p style="margin: 0 0 15px 0; color: #666;">Ready to get started?</p>
                <a href="https://your-app-url.com/login" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Login to Dashboard
                </a>
            </div>
           
           
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center;">
                <p style="color: #666; font-size: 14px; margin: 5px 0;">Need help? Contact our support team</p>
                <p style="color: #666; font-size: 14px; margin: 5px 0;">
                    📧 <a href="mailto:support@localmoves.com" style="color: #667eea;">support@localmoves.com</a> |
                    📱 <a href="tel:+911234567890" style="color: #667eea;">+91 123 456 7890</a>
                </p>
            </div>
           
            <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                <p style="color: #999; font-size: 12px; margin: 5px 0;">
                    This email was sent to {user_email} because you registered as a Logistics Manager on LocalMoves.
                </p>
                <p style="color: #999; font-size: 12px; margin: 5px 0;">
                    © 2025 LocalMoves - All Rights Reserved
                </p>
            </div>
        </div>
        """
       
        # Get custom template or use default
        default_subject = "🎉 Welcome to LocalMoves - Logistics Manager Account Created"
        template_vars = {
            "user_name": full_name,
            "user_email": user_email,
            "phone": phone,
            "password": password
        }
        subject, message = get_email_template("signup_verification", template_vars, default_subject, email_content)
       
        # Send email using Frappe's email system
        frappe.sendmail(
            recipients=[user_email],
            sender="megha250903@gmail.com",
            subject=subject,
            message=message,
            delayed=False,
            now=True
        )
       
        frappe.logger().info(f"Welcome email sent successfully to Logistics Manager: {user_email}")
        return True
       
    except Exception as e:
        frappe.log_error(f"Failed to send welcome email to {user_email}: {str(e)}", "Logistics Manager Welcome Email Error")
        # Don't fail the signup if email fails
        return False


@frappe.whitelist(allow_guest=True)
def signup(full_name=None, email=None, password=None, phone=None, otp=None, role=None,
           pincode=None, address=None, city=None, state=None):
    """User signup with Twilio OTP verification and email for Logistics Managers"""
    try:
        data = frappe.local.form_dict

        full_name = full_name or data.get("full_name")
        email = email or data.get("email")
        password = password or data.get("password")
        phone = phone or data.get("phone")
        otp = otp or data.get("otp")
        role = role or data.get("role")
        pincode = pincode or data.get("pincode")
        address = address or data.get("address")
        city = city or data.get("city")
        state = state or data.get("state")

        if not all([full_name, email, password, phone, otp, role]):
            return {"success": False, "message": "All fields and OTP are required"}

        # Ensure phone number is in E.164 format
        if not phone.startswith('+'):
            phone = '+91' + phone.lstrip('0')

        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return {"success": False, "message": "Invalid email format"}

        if frappe.db.exists("LocalMoves User", email):
            return {"success": False, "message": "User with this email already exists"}

        valid_roles = ["Admin", "Logistics Manager", "User"]
        if role not in valid_roles:
            return {"success": False, "message": f"Invalid role. Must be one of: {', '.join(valid_roles)}"}

        # Verify OTP via Twilio Verify
        try:
            creds = get_twilio_credentials()
            client = get_twilio_client()
            verification_check = client.verify.v2.services(creds["verify_service_sid"]).verification_checks.create(
                to=phone,
                code=str(otp)
            )

            if verification_check.status != "approved":
                return {"success": False, "message": "Invalid or expired OTP"}

        except Exception as twilio_error:
            frappe.log_error(f"Twilio Verification Error: {str(twilio_error)}", "Twilio OTP Verification Failed")
            return {"success": False, "message": "Invalid or expired OTP"}

        # Create active user (OTP verified)
        user_doc = frappe.get_doc({
            "doctype": "LocalMoves User",
            "full_name": full_name,
            "email": email,
            "password": password,
            "phone": phone,
            "role": role,
            "pincode": pincode,
            "address": address,
            "city": city,
            "state": state,
            "is_active": 1,
            "is_phone_verified": 1,
            "otp_code": None,
            "otp_expiry": None
        })
        user_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        # 🔥 SEND WELCOME EMAIL FOR LOGISTICS MANAGERS ONLY
        email_sent = False
        if role == "Logistics Manager":
            try:
                email_sent = send_logistics_manager_welcome_email(email, full_name, phone,password)
            except Exception as email_error:
                frappe.log_error(f"Email sending failed for {email}: {str(email_error)}", "Welcome Email Failed")
                # Continue even if email fails

        # Generate JWT token after signup
        token = generate_token(user_doc.name, email, role)

        response_message = "Signup successful. Phone verified."
        if role == "Logistics Manager" and email_sent:
            response_message += " Welcome email sent to your account."

        return {
            "success": True,
            "message": response_message,
            "data": {
                "user_id": user_doc.name,
                "email": email,
                "full_name": full_name,
                "role": role,
                "token": token,
                "email_sent": email_sent if role == "Logistics Manager" else None
            }
        }

    except Exception as e:
        frappe.log_error(f"Signup with OTP Error: {str(e)}", "Signup Failed")
        frappe.db.rollback()
        return {"success": False, "message": f"Signup failed: {str(e)}"}

@frappe.whitelist(allow_guest=True)
def login(email=None, password=None):
    """User Login API"""
    try:
        # Get parameters
        if not email or not password:
            data = frappe.local.form_dict
            email = data.get("email")
            password = data.get("password")
        
        if not email or not password:
            return {"success": False, "message": "email and password are required"}
        
        if not frappe.db.exists("LocalMoves User", email):
            return {"success": False, "message": "Invalid email or password"}

        user_doc = frappe.get_doc("LocalMoves User", email)

        if not user_doc.is_active:
            return {"success": False, "message": "Account is inactive. Please contact administrator."}

        if not verify_password(password, user_doc.password):
            return {"success": False, "message": "Invalid email or password"}

        # Update last login time
        user_doc.last_login = datetime.now()
        user_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Generate JWT
        token = generate_token(user_doc.name, email, user_doc.role)

        # ✅ Check if this logistics manager already has a company
        company_exists = False
        company_name = None

        if user_doc.role == "Logistics Manager":
            company = frappe.db.get_value("Logistics Company", {"manager_email": email}, "company_name")
            if company:
                company_exists = True
                company_name = company

        return {
            "success": True,
            "message": "Login successful",
            "data": {
                "user_id": user_doc.name,
                "email": email,
                "full_name": user_doc.full_name,
                "role": user_doc.role,
                "phone": user_doc.phone,
                "pincode": user_doc.pincode,
                "token": token,
                "last_login": str(user_doc.last_login),
                # ✅ Add company check result here
                "company_registered": company_exists,
                "company_name": company_name if company_exists else None
            }
        }

    except Exception as e:
        frappe.log_error(f"Login Error: {str(e)}", "Login Exception")
        return {"success": False, "message": "Login failed. Please try again."}

@frappe.whitelist()
def logout():
    """Logout API (JWT handled client-side)"""
    return {"success": True, "message": "Logged out successfully"}


@frappe.whitelist(allow_guest=True)
def get_current_user_info():
    """Get current user info from JWT token"""
    try:
        user_info = None
        
        # Check if JWT was pre-validated by hook
        if (hasattr(frappe.local, 'jwt_authenticated') and 
            frappe.local.jwt_authenticated and 
            hasattr(frappe.local, 'jwt_user')):
            user_info = frappe.local.jwt_user
        else:
            # Fallback: Manual token validation
            auth_header = frappe.get_request_header("Authorization")
            if not auth_header:
                return {"success": False, "message": "Missing Authorization header"}

            token = auth_header.replace("Bearer ", "").strip()
            if not token:
                return {"success": False, "message": "Invalid or empty token"}

            user_info = verify_token(token)
        
        # Get user document
        user_doc = frappe.get_doc("LocalMoves User", user_info["email"])

        return {
            "success": True,
            "data": {
                "user_id": user_doc.name,
                "email": user_doc.email,
                "full_name": user_doc.full_name,
                "role": user_doc.role,
                "phone": user_doc.phone,
                "pincode": user_doc.pincode,
                "address": user_doc.address,
                "city": user_doc.city,
                "state": user_doc.state,
                "is_active": user_doc.is_active,
                "last_login": str(user_doc.last_login) if user_doc.last_login else None
            }
        }

    except Exception as e:
        frappe.log_error(f"JWT User Info Error: {str(e)}")
        return {"success": False, "message": "Failed to get user info or invalid token"}


# @frappe.whitelist(allow_guest=True)
# def forgot_password(email=None):
#     """Forgot Password API with Email Sending"""
#     try:
#         # Get email from JSON body if not provided
#         if not email:
#             email = frappe.local.form_dict.get("email")
        
#         if not email:
#             return {"success": False, "message": "email is required"}
        
#         # Check if user exists
#         if not frappe.db.exists("LocalMoves User", email):
#             # Don't reveal if email doesn't exist (security best practice)
#             return {"success": True, "message": "If the email exists, a reset link has been sent."}

#         user_doc = frappe.get_doc("LocalMoves User", email)
        
#         # Generate reset token (JWT - valid for duration set in jwt_handler)
#         reset_token = generate_token(user_doc.name, email, user_doc.role)
        
#         # 🔥 BUILD RESET LINK - Update with your actual frontend URL
#         reset_link = f"http://localhost:5173/reset-password?token={reset_token}"
        
#         # 🔥 SEND PASSWORD RESET EMAIL
#         try:
#             email_content = f"""
#             <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
#                 <div style="text-align: center; margin-bottom: 30px;">
#                     <h1 style="color: #2c3e50; margin: 0;">🔐 Password Reset Request</h1>
#                     <p style="color: #7f8c8d; font-size: 16px;">LocalMoves Account Security</p>
#                 </div>
                
#                 <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 8px; color: white; text-align: center; margin-bottom: 30px;">
#                     <h2 style="margin: 0 0 10px 0;">Reset Your Password</h2>
#                     <p style="margin: 0; font-size: 14px; opacity: 0.9;">We received a request to reset your password</p>
#                 </div>
                
#                 <div style="padding: 20px 0;">
#                     <p style="color: #2c3e50; font-size: 16px;">Hello <strong>{user_doc.full_name}</strong>,</p>
#                     <p style="color: #555; line-height: 1.6;">
#                         We received a request to reset the password for your LocalMoves account (<strong>{email}</strong>).
#                     </p>
#                     <p style="color: #555; line-height: 1.6;">
#                         Click the button below to create a new password:
#                     </p>
#                 </div>
                
#                 <div style="text-align: center; margin: 30px 0;">
#                     <a href="{reset_link}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">
#                         Reset My Password
#                     </a>
#                 </div>
                
#                 <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
#                     <p style="margin: 0 0 10px 0; color: #856404; font-weight: bold;">
#                         ⚠️ Security Notice:
#                     </p>
#                     <ul style="margin: 0; padding-left: 20px; color: #856404;">
#                         <li>This link will expire in <strong>1 hour</strong></li>
#                         <li>If you didn't request this reset, please ignore this email</li>
#                         <li>Your password will remain unchanged if you don't click the link</li>
#                     </ul>
#                 </div>
                
#                 <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
#                     <p style="margin: 0 0 10px 0; color: #666; font-size: 13px; font-weight: bold;">
#                         Button not working? Copy and paste this link into your browser:
#                     </p>
#                     <p style="margin: 0; word-break: break-all;">
#                         <code style="background: #e9ecef; padding: 8px; display: block; border-radius: 3px; color: #495057; font-size: 12px;">{reset_link}</code>
#                     </p>
#                 </div>
                
#                 <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #2196f3;">
#                     <p style="margin: 0; color: #1565c0; font-size: 14px;">
#                         <strong>💡 Tip:</strong> After resetting your password, make sure to use a strong password that includes uppercase letters, lowercase letters, numbers, and special characters.
#                     </p>
#                 </div>
                
#                 <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center;">
#                     <p style="color: #666; font-size: 14px; margin: 5px 0;">Need help? Contact our support team</p>
#                     <p style="color: #666; font-size: 14px; margin: 5px 0;">
#                         📧 <a href="mailto:support@localmoves.com" style="color: #667eea;">support@localmoves.com</a> | 
#                         📱 <a href="tel:+911234567890" style="color: #667eea;">+91 123 456 7890</a>
#                     </p>
#                 </div>
                
#                 <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
#                     <p style="color: #999; font-size: 12px; margin: 5px 0;">
#                         This email was sent to {email} because a password reset was requested for this account.
#                     </p>
#                     <p style="color: #999; font-size: 12px; margin: 5px 0;">
#                         © 2025 LocalMoves - All Rights Reserved
#                     </p>
#                 </div>
#             </div>
#             """
            
#             frappe.sendmail(
#                 recipients=[email],
#                 sender="megha250903@gmail.com",
#                 subject="🔐 Password Reset Request - LocalMoves",
#                 message=email_content,
#                 delayed=False,
#                 now=True
#             )
            
#             frappe.logger().info(f"Password reset email sent successfully to: {email}")
            
#         except Exception as email_error:
#             frappe.log_error(f"Failed to send password reset email to {email}: {str(email_error)}", "Password Reset Email Error")
#             return {"success": False, "message": "Failed to send password reset email. Please try again later."}

#         return {
#             "success": True,
#             "message": "Password reset link has been sent to your email address. Please check your inbox.",
#             "data": {
#                 "email": email,
#                 "reset_token": reset_token  # Optional: Include for testing/development only
#             }
#         }

#     except Exception as e:
#         frappe.log_error(f"Forgot Password Error: {str(e)}", "Forgot Password Failed")
#         return {"success": False, "message": "Failed to process password reset request"}
@frappe.whitelist(allow_guest=True)
def forgot_password(email=None):
    """Forgot Password API with Email Sending"""
    try:
        # Get email from JSON body if not provided
        if not email:
            email = frappe.local.form_dict.get("email")
       
        if not email:
            return {"success": False, "message": "email is required"}
       
        # Check if user exists
        if not frappe.db.exists("LocalMoves User", email):
            # Don't reveal if email doesn't exist (security best practice)
            return {"success": True, "message": "If the email exists, a reset link has been sent."}

        user_doc = frappe.get_doc("LocalMoves User", email)
       
        # Generate reset token (JWT - valid for duration set in jwt_handler)
        reset_token = generate_token(user_doc.name, email, user_doc.role)
       
        # 🔥 BUILD RESET LINK - Using frontend URL from .env
        frontend_url = get_frontend_url()
        reset_link = f"{frontend_url}/reset-password?token={reset_token}"
       
        # 🔥 SEND PASSWORD RESET EMAIL
        try:
            # Default email content - NO user_name variable
            default_email_content = """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #2c3e50; margin: 0;">🔐 Password Reset Request</h1>
                    <p style="color: #7f8c8d; font-size: 16px;">LocalMoves Account Security</p>
                </div>
               
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 8px; color: white; text-align: center; margin-bottom: 30px;">
                    <h2 style="margin: 0 0 10px 0;">Reset Your Password</h2>
                    <p style="margin: 0; font-size: 14px; opacity: 0.9;">We received a request to reset your password</p>
                </div>
               
                <div style="padding: 20px 0;">
                    <p style="color: #2c3e50; font-size: 16px;">Hello,</p>
                    <p style="color: #555; line-height: 1.6;">
                        We received a request to reset the password for your LocalMoves account (<strong>{user_email}</strong>).
                    </p>
                    <p style="color: #555; line-height: 1.6;">
                        Click the button below to create a new password:
                    </p>
                </div>
               
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">
                        Reset My Password
                    </a>
                </div>
               
                <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
                    <p style="margin: 0 0 10px 0; color: #856404; font-weight: bold;">
                        ⚠️ Security Notice:
                    </p>
                    <ul style="margin: 0; padding-left: 20px; color: #856404;">
                        <li>This link will expire in <strong>{expiry_time}</strong></li>
                        <li>If you didn't request this reset, please ignore this email</li>
                        <li>Your password will remain unchanged if you don't click the link</li>
                    </ul>
                </div>
               
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p style="margin: 0 0 10px 0; color: #666; font-size: 13px; font-weight: bold;">
                        Button not working? Copy and paste this link into your browser:
                    </p>
                    <p style="margin: 0; word-break: break-all;">
                        <code style="background: #e9ecef; padding: 8px; display: block; border-radius: 3px; color: #495057; font-size: 12px;">{reset_link}</code>
                    </p>
                </div>
               
                <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #2196f3;">
                    <p style="margin: 0; color: #1565c0; font-size: 14px;">
                        <strong>💡 Tip:</strong> After resetting your password, make sure to use a strong password that includes uppercase letters, lowercase letters, numbers, and special characters.
                    </p>
                </div>
               
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center;">
                    <p style="color: #666; font-size: 14px; margin: 5px 0;">Need help? Contact our support team</p>
                    <p style="color: #666; font-size: 14px; margin: 5px 0;">
                        📧 <a href="mailto:support@localmoves.com" style="color: #667eea;">support@localmoves.com</a> |
                        📱 <a href="tel:+911234567890" style="color: #667eea;">+91 123 456 7890</a>
                    </p>
                </div>
               
                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                    <p style="color: #999; font-size: 12px; margin: 5px 0;">
                        This email was sent to {user_email} because a password reset was requested for this account.
                    </p>
                    <p style="color: #999; font-size: 12px; margin: 5px 0;">
                        © 2025 LocalMoves - All Rights Reserved
                    </p>
                </div>
            </div>
            """
           
            # Get custom template or use default (with variable replacement)
            # ✅ REMOVED user_name from template_vars
            default_subject = "🔐 Password Reset Request - LocalMoves"
            template_vars = {
                "user_email": email,
                "reset_link": reset_link,
                "expiry_time": "1 hour"
            }
            subject, message = get_email_template("password_reset", template_vars, default_subject, default_email_content)
           
            frappe.sendmail(
                recipients=[email],
                sender="megha250903@gmail.com",
                subject=subject,
                message=message,
                delayed=False,
                now=True
            )
           
            frappe.logger().info(f"Password reset email sent successfully to: {email}")
           
        except Exception as email_error:
            frappe.log_error(f"Failed to send password reset email to {email}: {str(email_error)}", "Password Reset Email Error")
            return {"success": False, "message": "Failed to send password reset email. Please try again later."}

        return {
            "success": True,
            "message": "Password reset link has been sent to your email address. Please check your inbox.",
            "data": {
                "email": email,
                "reset_token": reset_token
            }
        }

    except Exception as e:
        frappe.log_error(f"Forgot Password Error: {str(e)}", "Forgot Password Failed")
        return {"success": False, "message": "Failed to process password reset request"}
    

# @frappe.whitelist(allow_guest=True)
# def forgot_password(email=None):
#     """Forgot Password API with Email Sending"""
#     try:
#         # Get email from JSON body if not provided
#         if not email:
#             email = frappe.local.form_dict.get("email")
       
#         if not email:
#             return {"success": False, "message": "email is required"}
       
#         # Check if user exists
#         if not frappe.db.exists("LocalMoves User", email):
#             # Don't reveal if email doesn't exist (security best practice)
#             return {"success": True, "message": "If the email exists, a reset link has been sent."}


#         user_doc = frappe.get_doc("LocalMoves User", email)
       
#         # Generate reset token (JWT - valid for duration set in jwt_handler)
#         reset_token = generate_token(user_doc.name, email, user_doc.role)
       
#         # 🔥 BUILD RESET LINK - Update with your actual frontend URL
#         reset_link = f"http://localhost:5173/reset-password?token={reset_token}"
       
#         # 🔥 SEND PASSWORD RESET EMAIL
#         try:
#             email_content = f"""
#             <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
#                 <div style="text-align: center; margin-bottom: 30px;">
#                     <h1 style="color: #2c3e50; margin: 0;">🔐 Password Reset Request</h1>
#                     <p style="color: #7f8c8d; font-size: 16px;">LocalMoves Account Security</p>
#                 </div>
               
#                 <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 8px; color: white; text-align: center; margin-bottom: 30px;">
#                     <h2 style="margin: 0 0 10px 0;">Reset Your Password</h2>
#                     <p style="margin: 0; font-size: 14px; opacity: 0.9;">We received a request to reset your password</p>
#                 </div>
               
#                 <div style="padding: 20px 0;">
#                     <p style="color: #2c3e50; font-size: 16px;">Hello <strong>{user_doc.full_name}</strong>,</p>
#                     <p style="color: #555; line-height: 1.6;">
#                         We received a request to reset the password for your LocalMoves account (<strong>{email}</strong>).
#                     </p>
#                     <p style="color: #555; line-height: 1.6;">
#                         Click the button below to create a new password:
#                     </p>
#                 </div>
               
#                 <div style="text-align: center; margin: 30px 0;">
#                     <a href="{reset_link}" style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 40px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">
#                         Reset My Password
#                     </a>
#                 </div>
               
#                 <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107;">
#                     <p style="margin: 0 0 10px 0; color: #856404; font-weight: bold;">
#                         ⚠️ Security Notice:
#                     </p>
#                     <ul style="margin: 0; padding-left: 20px; color: #856404;">
#                         <li>This link will expire in <strong>1 hour</strong></li>
#                         <li>If you didn't request this reset, please ignore this email</li>
#                         <li>Your password will remain unchanged if you don't click the link</li>
#                     </ul>
#                 </div>
               
#                 <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
#                     <p style="margin: 0 0 10px 0; color: #666; font-size: 13px; font-weight: bold;">
#                         Button not working? Copy and paste this link into your browser:
#                     </p>
#                     <p style="margin: 0; word-break: break-all;">
#                         <code style="background: #e9ecef; padding: 8px; display: block; border-radius: 3px; color: #495057; font-size: 12px;">{reset_link}</code>
#                     </p>
#                 </div>
               
#                 <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #2196f3;">
#                     <p style="margin: 0; color: #1565c0; font-size: 14px;">
#                         <strong>💡 Tip:</strong> After resetting your password, make sure to use a strong password that includes uppercase letters, lowercase letters, numbers, and special characters.
#                     </p>
#                 </div>
               
#                 <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center;">
#                     <p style="color: #666; font-size: 14px; margin: 5px 0;">Need help? Contact our support team</p>
#                     <p style="color: #666; font-size: 14px; margin: 5px 0;">
#                         📧 <a href="mailto:support@localmoves.com" style="color: #667eea;">support@localmoves.com</a> |
#                         📱 <a href="tel:+911234567890" style="color: #667eea;">+91 123 456 7890</a>
#                     </p>
#                 </div>
               
#                 <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
#                     <p style="color: #999; font-size: 12px; margin: 5px 0;">
#                         This email was sent to {email} because a password reset was requested for this account.
#                     </p>
#                     <p style="color: #999; font-size: 12px; margin: 5px 0;">
#                         © 2025 LocalMoves - All Rights Reserved
#                     </p>
#                 </div>
#             </div>
#             """
           
#             # Get custom template or use default
#             default_subject = "🔐 Password Reset Request - LocalMoves"
#             template_vars = {
#                 "user_name": user_name,
#                 "user_email": email,
#                 "reset_link": reset_link,
#                 "expiry_time": "30 minutes"
#             }
#             subject, message = get_email_template("password_reset", template_vars, default_subject, email_content)
           
#             try:
#                 frappe.sendmail(
#                     recipients=[email],
#                     sender="megha250903@gmail.com",
#                     subject=subject,
#                     message=message,
#                     delayed=False,
#                     now=True
#                 )
#             except Exception as email_error:
#                 error_msg = str(email_error)
#                 if "Email Account" in error_msg or "OutgoingEmailError" in str(type(email_error)):
#                     frappe.log_error(f"Email configuration missing: {error_msg}", "Email Configuration Error")
#                     return {"success": False, "message": "Email service not configured. Please contact support."}
#                 else:
#                     raise
           
#             frappe.logger().info(f"Password reset email sent successfully to: {email}")
           
#         except Exception as email_error:
#             frappe.log_error(f"Failed to send password reset email to {email}: {str(email_error)}", "Password Reset Email Error")
#             return {"success": False, "message": "Failed to send password reset email. Please try again later."}


#         return {
#             "success": True,
#             "message": "Password reset link has been sent to your email address. Please check your inbox.",
#             "data": {
#                 "email": email,
#                 "reset_token": reset_token  # Optional: Include for testing/development only
#             }
#         }


#     except Exception as e:
#         frappe.log_error(f"Forgot Password Error: {str(e)}", "Forgot Password Failed")
#         return {"success": False, "message": "Failed to process password reset request"}





@frappe.whitelist(allow_guest=True)
def reset_password(token=None, new_password=None):
    """Reset Password API"""
    try:
        # Get parameters from JSON body if not provided
        if not token or not new_password:
            data = frappe.local.form_dict
            token = data.get("token")
            new_password = data.get("new_password")
        
        if not token or not new_password:
            return {"success": False, "message": "token and new_password are required"}
        
        token = token.replace("Bearer ", "").strip()
        user_info = verify_token(token)
        user_doc = frappe.get_doc("LocalMoves User", user_info["email"])

        user_doc.password = new_password
        user_doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "message": "Password reset successfully"}

    except Exception as e:
        frappe.log_error(f"Reset Password Error: {str(e)}")
        return {"success": False, "message": "Failed to reset password"}

# update user account
@frappe.whitelist(allow_guest=True)
def update_profile():
    """Update user profile (name and phone only)"""
    try:
        # Read JSON body safely - exactly like change_password()
        if frappe.request and frappe.request.data:
            try:
                data = json.loads(frappe.request.data)
            except Exception:
                data = {}
        else:
            data = {}

        # Get params from data
        full_name = data.get("full_name") if data else None
        phone = data.get("phone") if data else None
        
        # At least one field must be provided
        if not full_name and not phone:
            return {"success": False, "message": "At least one field (full_name or phone) is required"}
        
        # Get user info from JWT
        user_info = None
        if (hasattr(frappe.local, 'jwt_authenticated') and 
            frappe.local.jwt_authenticated and 
            hasattr(frappe.local, 'jwt_user')):
            user_info = frappe.local.jwt_user
        else:
            # Fallback: Manual token validation
            auth_header = frappe.get_request_header("Authorization")
            if not auth_header:
                return {"success": False, "message": "Missing Authorization header"}
            
            token = auth_header.replace("Bearer ", "").strip()
            if not token:
                return {"success": False, "message": "Invalid or empty token"}
            
            user_info = verify_token(token)
        
        if not user_info:
            return {"success": False, "message": "Unable to authenticate user"}
        
        # Get user document
        user_doc = frappe.get_doc("LocalMoves User", user_info["email"])
        
        # Track what's being updated
        updated_fields = []
        
        # Validate and prepare updates
        full_name_stripped = None
        phone_stripped = None
        
        # Update full name if provided
        if full_name:
            full_name_stripped = str(full_name).strip()
            if not full_name_stripped:
                return {"success": False, "message": "Full name cannot be empty"}
        
        # Update phone if provided
        if phone:
            phone_stripped = str(phone).strip()
            if not phone_stripped:
                return {"success": False, "message": "Phone number cannot be empty"}
            
            # Check if phone number is already used by another user
            existing_user = frappe.db.get_value("LocalMoves User", 
                                                {"phone": phone_stripped, "name": ["!=", user_doc.name]}, 
                                                "name")
            if existing_user:
                return {"success": False, "message": "Phone number is already registered to another account"}
        
        # Save the document - use db_set to bypass version tracking
        if full_name_stripped:
            frappe.db.set_value("LocalMoves User", user_doc.name, "full_name", full_name_stripped)
            updated_fields.append("full_name")
        
        if phone_stripped:
            frappe.db.set_value("LocalMoves User", user_doc.name, "phone", phone_stripped)
            updated_fields.append("phone")
        
        frappe.db.commit()
        
        # Reload to get updated values
        user_doc.reload()
        
        return {
            "success": True,
            "message": f"Profile updated successfully ({', '.join(updated_fields)})",
            "data": {
                "user_id": user_doc.name,
                "email": user_doc.email,
                "full_name": user_doc.full_name,
                "phone": user_doc.phone,
                "role": user_doc.role
            }
        }
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        frappe.log_error(f"Update Profile Error: {str(e)}\n{error_traceback}", "Update Profile Failed")
        frappe.db.rollback()
        return {"success": False, "message": f"Failed to update profile: {str(e)}"}


@frappe.whitelist(allow_guest=True)
def change_password(old_password=None, new_password=None):
    """Change Password API"""
    try:
        # Read JSON body safely
        if frappe.request and frappe.request.data:
            try:
                data = json.loads(frappe.request.data)
            except Exception:
                data = {}
        else:
            data = {}

        # Get params
        old_password = old_password or data.get("old_password")
        new_password = new_password or data.get("new_password")

        if not old_password or not new_password:
            return {"success": False, "message": "old_password and new_password are required"}

        # Get user info from JWT
        if (hasattr(frappe.local, 'jwt_authenticated') and 
            frappe.local.jwt_authenticated and 
            hasattr(frappe.local, 'jwt_user')):
            user_info = frappe.local.jwt_user
        else:
            # Fallback: Manual token validation
            auth_header = frappe.get_request_header("Authorization")
            if not auth_header:
                return {"success": False, "message": "No token provided"}
            
            token = auth_header.replace("Bearer ", "").strip()
            user_info = verify_token(token)
        
        user_doc = frappe.get_doc("LocalMoves User", user_info["email"])

        # Verify and update password
        if not verify_password(old_password, user_doc.password):
            return {"success": False, "message": "Current password is incorrect"}

        user_doc.password = new_password
        user_doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {"success": True, "message": "Password changed successfully"}

    except Exception as e:
        frappe.log_error(f"Change Password Error: {str(e)}")
        return {"success": True, "message": "Password changed successfully"}
