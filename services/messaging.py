import time
import threading
import uuid
from datetime import datetime
from typing import Optional, Union, Dict, List
from loguru import logger
from flask import current_app
from models import db, Contact, Message, Group
from utils.phone import normalize_to_e164
from services.zapi_client import get_client

# In-memory job storage (for demo purposes)
# In production, use Redis or a database
jobs_status = {}

class MessagingService:
    """Service for handling message sending operations."""
    
    def __init__(self):
        self.zapi_client = get_client()
    
    def send_to_contact(self, contact_or_phone: Union[int, str, Contact], message: str) -> Dict:
        """
        Send a message to a contact or phone number.
        
        Args:
            contact_or_phone: Contact ID, Contact object, or phone number string
            message: Message content
        
        Returns:
            Dictionary with send result
        """
        contact = None
        phone_number = None
        
        # Determine the recipient
        if isinstance(contact_or_phone, Contact):
            contact = contact_or_phone
            phone_number = contact.whatsapp_number
        elif isinstance(contact_or_phone, int):
            contact = Contact.query.get(contact_or_phone)
            if not contact:
                return {
                    "success": False,
                    "error": f"Contact with ID {contact_or_phone} not found"
                }
            phone_number = contact.whatsapp_number
        else:
            # It's a phone number string
            try:
                phone_number = normalize_to_e164(str(contact_or_phone))
            except ValueError as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Send the message via Z-API
        result = self.zapi_client.send_text(phone_number, message)
        
        # Create message record
        msg_record = Message(
            contact_id=contact.id if contact else None,
            phone_number=phone_number if not contact else None,
            content=message,
            status=result["status"],
            provider="z-api",
            provider_message_id=result.get("provider_message_id"),
            error=result.get("error"),
            created_at=datetime.utcnow()
        )
        
        db.session.add(msg_record)
        db.session.commit()
        
        return {
            "success": result["success"],
            "message_id": msg_record.id,
            "status": result["status"],
            "error": result.get("error"),
            "provider_message_id": result.get("provider_message_id")
        }
    
    def send_bulk_by_group(self, group_id: int, message: str, sleep_between_secs: float = 2.0) -> List[Dict]:
        """
        Send a message to all contacts in a group.
        
        Args:
            group_id: Group ID
            message: Message content
            sleep_between_secs: Seconds to wait between messages (rate limiting)
        
        Returns:
            List of send results for each contact
        """
        group = Group.query.get(group_id)
        if not group:
            return [{"success": False, "error": f"Group with ID {group_id} not found"}]
        
        contacts = group.contacts.all()
        if not contacts:
            return [{"success": False, "error": "No contacts in group"}]
        
        results = []
        total = len(contacts)
        
        for idx, contact in enumerate(contacts, 1):
            logger.info(f"Sending message {idx}/{total} to {contact.name}")
            
            # Send message
            result = self.send_to_contact(contact, message)
            result["contact_name"] = contact.name
            result["contact_id"] = contact.id
            results.append(result)
            
            # Rate limiting: wait between messages (except for the last one)
            if idx < total:
                time.sleep(sleep_between_secs)
        
        return results
    
    def send_bulk_async(self, group_id: int, message: str, sleep_between_secs: float = 2.0) -> str:
        """
        Send bulk messages asynchronously in a background thread.
        
        Args:
            group_id: Group ID
            message: Message content  
            sleep_between_secs: Seconds to wait between messages
        
        Returns:
            Job ID for status tracking
        """
        job_id = str(uuid.uuid4())
        
        # Initialize job status
        jobs_status[job_id] = {
            "id": job_id,
            "status": "pending",
            "progress": 0,
            "total": 0,
            "sent": 0,
            "failed": 0,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "results": []
        }
        
        def run_bulk_send():
            with current_app.app_context():
                try:
                    # Update status to running
                    jobs_status[job_id]["status"] = "running"
                    
                    # Get group and contacts
                    group = Group.query.get(group_id)
                    if not group:
                        jobs_status[job_id]["status"] = "failed"
                        jobs_status[job_id]["error"] = f"Group with ID {group_id} not found"
                        return
                    
                    contacts = group.contacts.all()
                    total = len(contacts)
                    jobs_status[job_id]["total"] = total
                    
                    if not contacts:
                        jobs_status[job_id]["status"] = "failed"
                        jobs_status[job_id]["error"] = "No contacts in group"
                        return
                    
                    # Send messages
                    for idx, contact in enumerate(contacts, 1):
                        result = self.send_to_contact(contact, message)
                        
                        # Update progress
                        jobs_status[job_id]["progress"] = idx
                        if result["success"]:
                            jobs_status[job_id]["sent"] += 1
                        else:
                            jobs_status[job_id]["failed"] += 1
                        
                        # Store result
                        jobs_status[job_id]["results"].append({
                            "contact_name": contact.name,
                            "contact_id": contact.id,
                            "success": result["success"],
                            "error": result.get("error")
                        })
                        
                        # Rate limiting
                        if idx < total:
                            time.sleep(sleep_between_secs)
                    
                    # Mark as completed
                    jobs_status[job_id]["status"] = "completed"
                    jobs_status[job_id]["completed_at"] = datetime.utcnow().isoformat()
                    
                except Exception as e:
                    logger.exception(f"Error in bulk send job {job_id}")
                    jobs_status[job_id]["status"] = "failed"
                    jobs_status[job_id]["error"] = str(e)
                    jobs_status[job_id]["completed_at"] = datetime.utcnow().isoformat()
        
        # Start background thread
        thread = threading.Thread(target=run_bulk_send)
        thread.daemon = True
        thread.start()
        
        return job_id
    
    @staticmethod
    def get_job_status(job_id: str) -> Optional[Dict]:
        """Get the status of a bulk send job."""
        return jobs_status.get(job_id)

# Singleton instance
_service = None

def get_messaging_service():
    """Get or create the messaging service singleton."""
    global _service
    if _service is None:
        _service = MessagingService()
    return _service