"""
Tools for the OpenAI Agent SDK Demo.

This file contains tool implementations that can be used by agents.
"""

import os
import pickle
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
from datetime import datetime
import json
import logging
import shutil
from typing import List, Dict, Any, Optional
from agents import function_tool
from openai import OpenAI
import urllib.parse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
from datetime import timedelta
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"The weather in {city} is sunny."

# Gmail Service for Email Tool
class GmailService:
    def __init__(self, credentials_file='credentials.json'):
        self.credentials_file = credentials_file
        self.creds = None
        self.service = None
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
        # Get root directory for token storage
        self.root_dir = Path(credentials_file).parent

    def authenticate(self):
        """Authenticates with Gmail API using OAuth2."""
        token_path = self.root_dir / 'token.pickle'
        
        if token_path.exists():
            with open(token_path, 'rb') as token:
                self.creds = pickle.load(token)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES)
                self.creds = flow.run_local_server(port=0)

            with open(token_path, 'wb') as token:
                pickle.dump(self.creds, token)

        self.service = build('gmail', 'v1', credentials=self.creds)
        return True

    def get_message_content(self, payload):
        """Extract message content from payload recursively."""
        if 'body' in payload and payload['body'].get('data'):
            return base64.urlsafe_b64decode(payload['body']['data']).decode()
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        return base64.urlsafe_b64decode(part['body']['data']).decode()
                elif part['mimeType'] == 'multipart/alternative':
                    return self.get_message_content(part)
        return ""

    def save_attachment(self, message_id, part, email_folder):
        """Saves email attachments."""
        if 'filename' not in part:
            return None

        filename = part['filename']
        if not filename:
            return None

        attachment_path = email_folder / 'attachments' / filename
        attachment = self.service.users().messages().attachments().get(
            userId='me', messageId=message_id, id=part['body']['attachmentId']
        ).execute()

        file_data = base64.urlsafe_b64decode(attachment['data'])
        with open(attachment_path, 'wb') as f:
            f.write(file_data)

        return attachment_path

    def fetch_inbox_emails(self, max_results=10):
        """Fetch emails from the inbox."""
        try:
            if not self.service:
                self.authenticate()

            # Get messages from inbox
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            if not messages:
                return []

            # Create emails directory if it doesn't exist
            emails_dir = Path(self.root_dir) / 'emails'
            if emails_dir.exists():
                shutil.rmtree(emails_dir)
            emails_dir.mkdir(exist_ok=True)
            
            processed_messages = []
            
            # Process each message
            for message in messages:
                # Get the full message details
                msg = self.service.users().messages().get(
                    userId='me', 
                    id=message['id'],
                    format='full'
                ).execute()
                
                # Create email folder
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                email_folder = emails_dir / f'email_{timestamp}'
                email_folder.mkdir(parents=True, exist_ok=True)
                (email_folder / 'attachments').mkdir(exist_ok=True)

                # Process email content
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                date = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')

                # Extract content
                content = self.get_message_content(msg['payload'])

                # Save email content
                email_data = {
                    'subject': subject,
                    'from': sender,
                    'date': date,
                    'content': content,
                    'attachments': []
                }

                # Process attachments
                def process_parts(payload):
                    if 'parts' in payload:
                        for part in payload['parts']:
                            if 'filename' in part and part['filename']:
                                attachment_path = self.save_attachment(
                                    message['id'], part, email_folder)
                                if attachment_path:
                                    email_data['attachments'].append(str(attachment_path))
                            if 'parts' in part:
                                process_parts(part)
                    elif 'filename' in payload and payload['filename']:
                        attachment_path = self.save_attachment(
                            message['id'], payload, email_folder)
                        if attachment_path:
                            email_data['attachments'].append(str(attachment_path))

                process_parts(msg['payload'])

                # Save content to file
                content_file = email_folder / 'content.txt'
                with open(content_file, 'w', encoding='utf-8') as f:
                    json.dump(email_data, f, indent=2, ensure_ascii=False)

                processed_messages.append({
                    'subject': subject,
                    'sender': sender,
                    'saved_path': str(email_folder),
                    'content_preview': content[:100] + '...' if len(content) > 100 else content
                })

                # Mark as read (optional)
                # self.service.users().messages().modify(
                #     userId='me',
                #     id=message['id'],
                #     body={'removeLabelIds': ['UNREAD']}
                # ).execute()

            return processed_messages

        except Exception as e:
            logging.error(f"Error fetching emails: {str(e)}")
            raise

# Initialize the Gmail service
gmail_service = GmailService()

@function_tool
def fetch_gmail_emails(max_results: int, credentials_path: str) -> List[Dict[str, Any]]:
    """
    Fetch emails from Gmail inbox and save them to the emails directory.
    
    Args:
        max_results: Maximum number of emails to fetch
        credentials_path: Path to the Google API credentials file
        
    Returns:
        List of dictionaries containing email information (subject, sender, saved_path, content_preview)
    """
    # Initialize Gmail service with the specified credentials
    service = GmailService(credentials_file=credentials_path)
    
    # Authenticate with Gmail
    logging.info("Authenticating with Gmail...")
    service.authenticate()
    
    # Fetch emails
    logging.info(f"Fetching up to {max_results} emails from inbox...")
    emails = service.fetch_inbox_emails(max_results=max_results)
    
    # Log results
    if emails:
        logging.info(f"Successfully fetched {len(emails)} emails")
        for i, email in enumerate(emails):
            logging.info(f"Email {i+1}: {email['subject']} from {email['sender']}")
    else:
        logging.warning("No emails found in the inbox")
    
    return emails 

@function_tool
def send_gmail_email(to: str, subject: str, body: str, credentials_path: str) -> Dict[str, Any]:
    """
    Send an email using Gmail.
    
    Args:
        to: Email address of the recipient
        subject: Subject of the email
        body: Body content of the email (plain text)
        credentials_path: Path to the Google API credentials file
        
    Returns:
        Dictionary containing status information about the sent email
    """
    from email.mime.text import MIMEText
    
    # Initialize Gmail service with the specified credentials
    service = GmailService(credentials_file=credentials_path)
    
    # Authenticate with Gmail
    logging.info("Authenticating with Gmail...")
    service.authenticate()
    
    try:
        # Create the email message
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        
        # Encode the message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send the email
        logging.info(f"Sending email to {to} with subject: {subject}")
        sent_message = service.service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        message_id = sent_message['id']
        logging.info(f"Email sent successfully. Message ID: {message_id}")
        
        return {
            'status': 'success',
            'message_id': message_id,
            'to': to,
            'subject': subject
        }
        
    except Exception as e:
        error_message = f"Error sending email: {str(e)}"
        logging.error(error_message)
        return {
            'status': 'error',
            'error': error_message
        } 

# Helper functions for order identification
def _encode_image(image_path):
    """Encode an image to base64 string."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image {image_path}: {str(e)}")
        return None

def _get_product_pictures():
    """Get all product pictures and their details."""
    product_pictures_dir = Path.cwd() / 'product_pictures'
    product_pictures = []
    
    if product_pictures_dir.exists():
        # Look for both PNG and JPG files
        for pic_file in product_pictures_dir.glob('*.*'):
            if pic_file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                try:
                    # Extract item number and description from filename
                    # Handle different filename formats
                    name = pic_file.stem
                    
                    # Format: "1996-S (ATLANTA-kovalevy, perus).png"
                    if '(' in name and ')' in name:
                        item_number = name.split(' ')[0]
                        description = name[name.find('(')+1:name.find(')')]
                    # Format: "1925-W (Jabra speaker - sensitive microphone.jpg" (missing closing parenthesis)
                    elif '(' in name:
                        item_number = name.split(' ')[0]
                        description = name[name.find('(')+1:]
                    # Other formats
                    else:
                        parts = name.split(' ', 1)
                        item_number = parts[0]
                        description = parts[1] if len(parts) > 1 else item_number
                    
                    product_pictures.append({
                        "file_path": str(pic_file),
                        "item_number": item_number,
                        "description": description,
                        "file_extension": pic_file.suffix.lower()[1:]  # Store extension without the dot
                    })
                    logging.info(f"Found product image: {item_number} - {description} ({pic_file.name})")
                except Exception as e:
                    logging.error(f"Error parsing product image filename {pic_file.name}: {str(e)}")
    
    return product_pictures

def _process_single_email(email_folder_path):
    """Process a single email folder and identify orders."""
    try:
        logging.info(f"Identifying orders from email folder: {email_folder_path}")
        
        # Initialize OpenAI client
        client = OpenAI()
        model = "gpt-4o"
        
        # Get the email folder path
        email_folder = Path(email_folder_path)
        if not email_folder.exists():
            logging.error(f"Email folder does not exist: {email_folder}")
            return {"order_details": None, "confidence_score": 0}
        
        # Read email content
        content_file = email_folder / 'content.txt'
        if not content_file.exists():
            logging.error(f"Content file does not exist: {content_file}")
            return {"order_details": None, "confidence_score": 0}
            
        # Read the raw email content
        with open(content_file, 'r', encoding='utf-8') as f:
            email_data = json.load(f)
            raw_content = email_data.get('content', '')
            logging.info(f"Email content loaded: {len(raw_content)} characters")
        
        # Check for attachments in the folder
        attachments_dir = email_folder / 'attachments'
        attachments = []
        if attachments_dir.exists():
            attachments = [f for f in attachments_dir.iterdir() if f.is_file()]
            logging.info(f"Found {len(attachments)} attachments: {[att.name for att in attachments]}")
        
        # Get product pictures
        product_pictures = _get_product_pictures()
        logging.info(f"Found {len(product_pictures)} product pictures")
        
        # Calculate default delivery date (current date + 14 days)
        current_date = datetime.now()
        default_delivery_date = (current_date + timedelta(days=14)).strftime("%Y-%m-%d")
        
        # Format the email content
        formatted_email = f"""
Please analyze this email and any attached images to extract sales order information.

Email Content:
-------------
{raw_content}

Attachments Found:
----------------
{chr(10).join('- ' + att.name for att in attachments) if attachments else 'No attachments'}

Product Catalog Images Available:
-------------------------------
{chr(10).join(f"- {pic['item_number']} - {pic['description']}" for pic in product_pictures)}

IMPORTANT INSTRUCTIONS:
1. Extract all order details including customer information, dates, and items ordered.
2. If the order details are in an attached image, please analyze the image carefully.
3. COMPARE ANY ATTACHED IMAGES WITH ALL PRODUCT CATALOG IMAGES to identify what product is being ordered.
4. The customer may have sent a photo of the exact product they want to order.
5. Look for visual similarities in shape, color, and features between the attachment and catalog images.
6. If you identify a match, use the item number and description from the matching product's filename.
7. If the email mentions a quantity (e.g., "3 pieces"), use that quantity.
8. If no quantity is specified, default to 1.
9. DELIVERY DATE MUST BE IN THE FUTURE - if no date is specified or the date is in the past, use current date + 14 days.
10. Today's date is {current_date.strftime("%Y-%m-%d")} and the default delivery date should be {default_delivery_date}.
11. Always explain your reasoning for the delivery date in the data_repair_notes.

Return null if no valid order information can be found.
"""
        
        # Prepare message content with both text and images
        message_content = [
            {"type": "text", "text": formatted_email}
        ]
        
        # Add email attachments if present
        attachment_count = 0
        for attachment in attachments:
            if attachment.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                base64_image = _encode_image(str(attachment))
                if base64_image:
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{attachment.suffix.lower()[1:]};base64,{base64_image}"
                        }
                    })
                    attachment_count += 1
                    logging.info(f"Added attachment image: {attachment.name}")
                else:
                    logging.error(f"Failed to encode attachment: {attachment.name}")
        
        # Add product catalog images
        product_count = 0
        for product in product_pictures:
            base64_image = _encode_image(product["file_path"])
            if base64_image:
                # Use the correct MIME type based on the file extension
                file_ext = product.get("file_extension", "png")
                message_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/{file_ext};base64,{base64_image}"
                    }
                })
                product_count += 1
                logging.info(f"Added product image: {product['item_number']} - {product['description']}")
            else:
                logging.error(f"Failed to encode product image: {product['item_number']}")
        
        logging.info(f"Sending request to OpenAI with {len(message_content)} content items ({attachment_count} attachments, {product_count} product images)")
        
        # Get order information using GPT-4o with structured output
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": f"""You are an expert at identifying sales orders from emails and images.
You must validate and repair order information using the existing master data records.

Valid Customers (Customer Name - Customer Number):
- Adatum Corporation - 10000
- Trey Research - 20000
- School of Fine Art - 30000
- Alpine Ski House - 40000
- Relecloud - 50000

Valid Items (Item Number - Description):
- 1896-S - ATHENS-työpöytä
- 1900-S - PARIS-vierastuoli, musta
- 1906-S - ATHENS liikkuva jalusta
- 1908-S - LONDON-toimistotuoli, sin.
- 1920-S - ANTWERP-kokouspöytä
- 1925-W - Kokouspaketti 1–6
- 1928-S - AMSTERDAM-lamppu
- 1929-W - Jabra speaker - sensitive microphone
- 1936-S - BERLIN-vierastuoli, keltainen
- 1953-W - Vierasosio 1
- 1960-S - ROME-vierastuoli, vihreä
- 1964-S - TOKYO-vierastuoli, sininen
- 1965-W - Kokouspaketti 2–8
- 1968-S - MEXICO-toimistotuoli, musta
- 1969-W - Kokouspaketti 1
- 1972-S - MUNICH-toimistotuoli, kelt.
- 1980-S - MOSKOW-toimistotuoli, pun.
- 1988-S - SEOUL-vierastuoli, pun.
- 1996-S - ATLANTA-kovalevy, perus
- 2000-S - SYDNEY-toimistotuoli, vihreä

IMAGE MATCHING INSTRUCTIONS:
- You will receive email attachments and product catalog images
- CAREFULLY COMPARE any email attachment images with ALL product catalog images
- Look for visual similarities in shape, color, and features
- If an email attachment shows a product, identify which catalog product it matches
- Pay special attention to distinctive features like:
  * For furniture: shape, color, material, legs, armrests
  * For electronics: overall shape, buttons, connectors, displays
- Even if the email text doesn't mention a specific product, the attachment may show the product being ordered
- The customer may have attached a photo of the exact product they want to order

Data Repair Instructions:
1. Customer Names:
   - If a customer name is slightly misspelled or has different capitalization, match it to the closest valid customer
   - Example: "Adatum Corp" or "ADATUM CORPORATION" should be corrected to "Adatum Corporation"
   - If the email signature mentions a company name, use that as the customer

2. Item Numbers and Descriptions:
   - If an item number is found without a description, add the correct description from the master data
   - If a description is found without an item number, try to match it with the correct item number
   - Match partial item numbers (e.g., "1896" should be matched to "1896-S")
   - Handle variations in item descriptions (e.g., "Athens desk" should match to "ATHENS-työpöytä")
   - If an item is not mentioned in text but there's an image attachment, compare it with the product catalog images
   - When matching images, use the item number and description from the matching product's filename

3. Dates:
   - Today's date is {current_date.strftime("%Y-%m-%d")}
   - The default delivery date (today + 14 days) is {default_delivery_date}
   - Ensure all dates are in YYYY-MM-DD format
   - IMPORTANT: The requested delivery date must ALWAYS be in the future
   - If a delivery date is mentioned but it's in the past, use {default_delivery_date} instead
   - If only a partial date is provided, use reasonable defaults (e.g., first day of mentioned month)
   - If no delivery date is specified at all, set it to {default_delivery_date}
   - ALWAYS include your reasoning for the delivery date in the data_repair_notes
   - Example note: "Delivery date set to {default_delivery_date} because no date was specified in the email"
   - Example note: "Delivery date in email (2023-01-01) was in the past, corrected to {default_delivery_date}"

4. Quantities:
   - If a quantity is mentioned in the email (e.g., "3 pieces", "5 units"), use that quantity
   - If no quantity is specified, default to 1
   - The unit of measurement should be "KPL" (Finnish for piece) unless otherwise specified

Extract all order information and return it in a structured JSON format. Always try to repair and match data before rejecting it.

Structure:
{{
    "order_details": {{
        "customer_info": {{
            "name": "string",  // Must match one of the valid customer names exactly after repair
            "contact_person": "string",  // Name of the contact person
            "customer_number": "string",  // The corresponding customer number (e.g., "10000")
            "original_customer_name": "string"  // The original customer name before repair (if different)
        }},
        "dates": {{
            "requested_delivery_date": "YYYY-MM-DD"  // When the customer wants the items delivered (MUST be in the future)
        }},
        "items": [
            {{
                "item_number": "string",  // Must match one of the valid item numbers exactly after repair
                "description": "string",  // The corresponding item description from master data
                "quantity": number,  // Number of units ordered
                "unit": "string",  // Unit of measurement (e.g., KPL, PCS)
                "original_item_info": "string",  // The original item info before repair (if different)
                "matched_from_image": boolean  // True if item was matched from an image
            }}
        ],
        "data_repair_notes": [
            "string"  // List of any corrections made to the original data, MUST include reasoning for delivery date
        ]
    }},
    "confidence_score": number  // Confidence level in the order identification and repair (0-1)
}}

If no valid order information can be found, or if the data cannot be repaired to match the master data, return {{"order_details": null, "confidence_score": 0}}"""},
                {"role": "user", "content": message_content}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract the structured result
        result = json.loads(response.choices[0].message.content)
        logging.info(f"Received response from OpenAI: {json.dumps(result, indent=2)}")
        
        # Save the results
        output_file = email_folder / 'identified_order.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        return result
        
    except Exception as e:
        logging.error(f"Error identifying orders: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return {"order_details": None, "confidence_score": 0, "error": str(e)}

@function_tool
def identify_orders_from_emails(email_folder_path: str, credentials_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Identify sales orders from a SINGLE email folder and its attachments using GPT-4o.
    This tool is for targeted processing of one specific email folder.
    
    Args:
        email_folder_path: Path to the email folder containing content.txt and attachments
        credentials_path: Optional path to OpenAI API credentials file
        
    Returns:
        Dictionary containing identified order details or null if no order is found
        
    Note:
        Use this tool when you need to process just one specific email folder.
        For batch processing of all emails, use identify_orders_from_all_emails instead.
    """
    # Simply call the helper function
    return _process_single_email(email_folder_path)

@function_tool
def identify_orders_from_all_emails(emails_dir_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Process ALL email folders in the emails directory and identify orders.
    This tool is for batch processing of multiple email folders at once.
    
    Args:
        emails_dir_path: Optional path to the directory containing email folders
        
    Returns:
        List of dictionaries containing identified order details
        
    Note:
        This is the preferred tool for the orchestration workflow as it processes
        all emails in a single operation. Use this when you need to batch process
        multiple email folders rather than targeting a specific email.
    """
    try:
        # Use default emails directory if not specified
        if emails_dir_path is None:
            emails_dir = Path.cwd() / 'emails'
        else:
            emails_dir = Path(emails_dir_path)

        if not emails_dir.exists():
            return [{"order_details": None, "confidence_score": 0, "error": f"Emails directory not found: {emails_dir}"}]
        
        logging.info(f"Processing emails from directory: {emails_dir}")
        
        results = []
        for email_folder in emails_dir.iterdir():
            if email_folder.is_dir():
                logging.info(f"Processing email folder: {email_folder.name}")
                result = _process_single_email(str(email_folder))
                if result and result.get('order_details'):
                    results.append(result)
        
        return results
        
    except Exception as e:
        logging.error(f"Error processing all emails: {str(e)}")
        return [{"order_details": None, "confidence_score": 0, "error": str(e)}] 

# Business Central integration
class BusinessCentralService:
    """Service for interacting with Business Central API."""
    
    def __init__(self):
        """Initialize the Business Central service with credentials from environment variables."""
        # Load configuration from environment variables
        self.tenant_id = os.getenv('BC_TENANT_ID')
        self.client_id = os.getenv('BC_CLIENT_ID')
        self.client_secret = os.getenv('BC_CLIENT_SECRET')
        self.company_name = os.getenv('BC_COMPANY_NAME')
        
        if not all([self.tenant_id, self.client_id, self.client_secret, self.company_name]):
            raise ValueError("Missing required Business Central environment variables")
        
        self.access_token = None
        # Properly encode the company name for the URL
        encoded_company = urllib.parse.quote(self.company_name)
        self.base_url = f"https://api.businesscentral.dynamics.com/v2.0/{self.tenant_id}/Production/ODataV4/Company('{encoded_company}')"
        logging.info(f"Using Business Central base URL: {self.base_url}")
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[408, 429, 500, 502, 503, 504],
        )
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
    
    def get_access_token(self):
        """Get access token from Azure AD with retry logic."""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
                data = {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://api.businesscentral.dynamics.com/.default"
                }
                
                response = self.session.post(url, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                self.access_token = token_data["access_token"]
                return self.access_token
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:  # Last attempt
                    logging.error(f"Failed to get access token after {max_retries} attempts: {str(e)}")
                    raise
                else:
                    logging.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

    def get_headers(self):
        """Get headers for BC API calls."""
        if not self.access_token:
            self.get_access_token()
            
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def make_request(self, method, url, **kwargs):
        """Make HTTP request with retry logic and token refresh."""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                
                # If token expired, refresh and retry
                if response.status_code == 401:
                    logging.info("Token expired, refreshing...")
                    self.access_token = None
                    kwargs['headers'] = self.get_headers()
                    continue
                
                # Log the complete response for debugging on error
                if not response.ok:
                    logging.error(f"Request failed with status {response.status_code}")
                    logging.error(f"Response headers: {dict(response.headers)}")
                    try:
                        error_json = response.json()
                        logging.error(f"Response body: {json.dumps(error_json, indent=2)}")
                    except:
                        logging.error(f"Response text: {response.text}")
                
                response.raise_for_status()
                return response
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    logging.error(f"Request failed after {max_retries} attempts: {str(e)}")
                    if hasattr(e, 'response'):
                        try:
                            error_json = e.response.json()
                            logging.error(f"Error details: {json.dumps(error_json, indent=2)}")
                        except:
                            logging.error(f"Error response text: {e.response.text}")
                    raise
                else:
                    logging.warning(f"Attempt {attempt + 1} failed, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2

    def create_sales_order(self, order_data):
        """Create a sales order in Business Central."""
        try:
            # Get current timestamp for all date fields
            current_date = datetime.now()
            current_date_str = current_date.strftime("%Y-%m-%d")
            
            # Calculate default due date (1 week from now)
            default_due_date = (current_date + timedelta(days=7)).strftime("%Y-%m-%d")
            
            # Get the requested delivery date or default to 14 days ahead
            requested_delivery_date = order_data["order_details"]["dates"]["requested_delivery_date"]
            
            # Set due date to one week in future if not provided
            due_date = order_data["order_details"]["dates"].get("due_date", default_due_date)
            
            # Prepare sales order header with constants and system dates
            sales_header = {
                "Document_Type": "Order",
                "Sell_to_Customer_No": order_data["order_details"]["customer_info"]["customer_number"],
                "Sell_to_Customer_Name": order_data["order_details"]["customer_info"]["name"],
                "Sell_to_Contact": order_data["order_details"]["customer_info"]["contact_person"],
                "External_Document_No": "APA_FROM_EMAIL",  # Fixed constant
                "Document_Date": current_date_str,
                "Posting_Date": current_date_str,
                "VAT_Reporting_Date": current_date_str,
                "Order_Date": current_date_str,
                "Due_Date": due_date,
                "Requested_Delivery_Date": requested_delivery_date,
                "Status": "Open"
            }

            # Log the request payload for debugging
            logging.info(f"Creating sales order with data: {json.dumps(sales_header, indent=2)}")

            # Create sales order header
            response = self.make_request(
                'post',
                f"{self.base_url}/SalesOrder",
                headers=self.get_headers(),
                json=sales_header
            )
            
            order = response.json()
            logging.info(f"Created sales order header: {json.dumps(order, indent=2)}")
            
            # Add order lines
            self.add_order_lines(order, order_data["order_details"]["items"])
            
            logging.info(f"Successfully created sales order {order['No']}")
            return {
                "order_number": order["No"],
                "customer": order_data["order_details"]["customer_info"]["name"],
                "items": len(order_data["order_details"]["items"]),
                "delivery_date": order_data["order_details"]["dates"]["requested_delivery_date"]
            }
            
        except Exception as e:
            logging.error(f"Error creating sales order: {str(e)}")
            raise

    def add_order_lines(self, order, items):
        """Add order lines to an existing sales order."""
        line_no = 10000
        for item in items:
            line_data = {
                'Document_Type': 'Order',
                'Document_No': order['No'],
                'Line_No': line_no,
                'Type': 'Item',
                'No': item['item_number'],
                'Quantity': float(item['quantity']),
                'Location_Code': ''  # Required field but can be empty
            }
            
            # Use the correct endpoint for sales order lines
            url = f"{self.base_url}/SalesOrderSalesLines"
            
            try:
                response = self.make_request('post', url, headers=self.get_headers(), json=line_data)
                created_line = response.json()
                
                # Log the entire response for debugging
                logging.info(f"Sales line response: {json.dumps(created_line, indent=2)}")
                
                # Get the calculated unit price from the response
                unit_price = created_line.get('Unit_Price', 0)
                logging.info(f"Created order line {line_no} for item {item['item_number']} with BC-calculated price {unit_price}")
                line_no += 10000
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Error creating order line: {str(e)}")
                if hasattr(e.response, 'text'):
                    logging.error(f"Response: {e.response.text}")
                raise

    def process_order_file(self, order_file_path):
        """Process a single order file and create it in Business Central."""
        try:
            logging.info(f"Processing order file: {order_file_path}")
            
            with open(order_file_path, 'r') as f:
                order_data = json.load(f)
            
            if not order_data.get("order_details"):
                logging.warning(f"No valid order details found in {order_file_path}")
                return None
                
            return self.create_sales_order(order_data)
            
        except Exception as e:
            logging.error(f"Error processing {order_file_path}: {str(e)}")
            return None

# Initialize the Business Central service
try:
    bc_service = BusinessCentralService()
    bc_service_available = True
except Exception as e:
    logging.error(f"Failed to initialize Business Central service: {str(e)}")
    bc_service_available = False

# Helper function for processing a single order
def _process_single_order(order_file_path: str) -> Dict[str, Any]:
    """Helper function to process a single order file."""
    try:
        # Check if Business Central service is available
        if not bc_service_available:
            return {
                "success": False,
                "error": "Business Central service is not available. Check environment variables."
            }
            
        # Check if the file exists
        if not os.path.exists(order_file_path):
            return {
                "success": False,
                "error": f"Order file not found: {order_file_path}"
            }
        
        # Load the order data
        with open(order_file_path, 'r', encoding='utf-8') as f:
            order_data = json.load(f)
        
        # Extract order details
        order_details = order_data.get("order_details", {})
        customer_info = order_details.get("customer_info", {})
        
        # Log the order being processed
        customer_name = customer_info.get("name", "Unknown")
        logging.info(f"Processing order for customer: {customer_name}")
        
        # Use the Business Central service to create the sales order
        try:
            result = bc_service.process_order_file(order_file_path)
            
            if result:
                # Create a response with the order details and assigned order number
                response = {
                    "success": True,
                    "order_number": result["order_number"],
                    "customer": customer_info,
                    "items": order_details.get("items", []),
                    "delivery_date": order_details.get("dates", {}).get("requested_delivery_date", ""),
                    "message": f"Order successfully posted to Business Central with order number: {result['order_number']}"
                }
                
                # Save the response to a file in the same directory as the order
                response_file_path = os.path.join(os.path.dirname(order_file_path), "bc_response.json")
                with open(response_file_path, 'w', encoding='utf-8') as f:
                    json.dump(response, f, indent=2, ensure_ascii=False)
                
                logging.info(f"Order posted successfully: {result['order_number']}")
                return response
            else:
                return {
                    "success": False,
                    "error": "Failed to create sales order in Business Central. Check logs for details."
                }
        except Exception as e:
            error_message = f"Error creating sales order in Business Central: {str(e)}"
            logging.error(error_message)
            return {
                "success": False,
                "error": error_message
            }
        
    except Exception as e:
        error_message = f"Error posting order to Business Central: {str(e)}"
        logging.error(error_message)
        return {
            "success": False,
            "error": error_message
        }

@function_tool
def post_order_to_business_central(order_file_path: str) -> Dict[str, Any]:
    """
    Post a single identified order to Business Central.
    
    Args:
        order_file_path: Path to the identified_order.json file
        
    Returns:
        A dictionary with the result of the operation, including:
        - success: Boolean indicating if the operation was successful
        - order_number: The order number assigned by Business Central (if successful)
        - customer: Customer information
        - items: List of items in the order
        - delivery_date: The requested delivery date
        - error: Error message (if any)
    """
    return _process_single_order(order_file_path)

@function_tool
def post_all_orders_to_business_central(emails_dir_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Post all identified orders to Business Central.
    
    Args:
        emails_dir_path: Optional path to the emails directory. If not provided, defaults to 'emails'.
        
    Returns:
        A list of dictionaries with the results of each operation.
    """
    try:
        # Check if Business Central service is available
        if not bc_service_available:
            return [{
                "success": False,
                "error": "Business Central service is not available. Check environment variables."
            }]
            
        # Set default emails directory if not provided
        if not emails_dir_path:
            emails_dir_path = "emails"
        
        # Check if the directory exists
        if not os.path.exists(emails_dir_path):
            return [{
                "success": False,
                "error": f"Emails directory not found: {emails_dir_path}"
            }]
        
        # Find all identified_order.json files
        order_files = []
        for root, _, files in os.walk(emails_dir_path):
            if "identified_order.json" in files:
                order_files.append(os.path.join(root, "identified_order.json"))
        
        if not order_files:
            return [{
                "success": False,
                "error": f"No identified orders found in {emails_dir_path}"
            }]
        
        logging.info(f"Found {len(order_files)} order files to process")
        
        # Process each order file
        results = []
        for order_file in order_files:
            logging.info(f"Processing order file: {order_file}")
            try:
                result = _process_single_order(order_file)
                results.append(result)
            except Exception as e:
                error_message = f"Error processing {order_file}: {str(e)}"
                logging.error(error_message)
                results.append({
                    "success": False,
                    "error": error_message,
                    "file": order_file
                })
        
        # Create a summary
        success_count = sum(1 for r in results if r.get("success", False))
        logging.info(f"Posted {success_count} of {len(results)} orders to Business Central")
        
        return results
        
    except Exception as e:
        error_message = f"Error posting orders to Business Central: {str(e)}"
        logging.error(error_message)
        return [{
            "success": False,
            "error": error_message
        }] 