import requests
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from config import Config
from services.settings_service import get_effective_zapi_config

# Configure logger
logger.add("logs/app.log", rotation="10 MB", retention="30 days", level="INFO")

class ZAPIClient:
    """Client for Z-API WhatsApp integration."""
    
    def __init__(self):
        # URL and tokens will be resolved at send time from DB settings or env
        self.send_text_url = None
    
    def _effective(self):
        return get_effective_zapi_config()
    
    def _base_url(self) -> str:
        cfg = self._effective()
        send_url = cfg.get('send_text_url') or ''
        if send_url.endswith('/send-text'):
            return send_url[: -len('/send-text')]
        iid = cfg.get('instance_id')
        tok = cfg.get('instance_token')
        if iid and tok:
            return f"https://api.z-api.io/instances/{iid}/token/{tok}"
        return ''
    
    def _headers(self):
        cfg = self._effective()
        h = {"Accept": "application/json"}
        if cfg.get('client_token'):
            h["Client-Token"] = cfg['client_token']
            h["client-token"] = cfg['client_token']
        return h
    
    def get_overview(self, timeout=10):
        """Aggregate basic dashboard info from Z-API. Best-effort; degrades gracefully."""
        base = self._base_url()
        cfg = self._effective()
        result = {
            "success": True,
            "configured": bool(base),
            "config": {
                "instance_id": (cfg.get('instance_id') or '')[:4] + '...' + (cfg.get('instance_id') or '')[-4:] if cfg.get('instance_id') else None,
                "send_text_url_set": bool(cfg.get('send_text_url')),
            },
            "status": None,
            "device": None,
            "webhook": None,
            "qrcode": None,
            "errors": {}
        }
        if not base:
            result["success"] = False
            result["errors"]["base"] = "Z-API não configurada"
            return result
        sesh = requests.Session()
        headers = self._headers()
        def safe_get(path):
            try:
                r = sesh.get(base + path, headers=headers, timeout=timeout)
                try:
                    data = r.json()
                except Exception:
                    data = {"raw_text": r.text}
                return {"ok": r.status_code in range(200,300), "status": r.status_code, "data": data}
            except Exception as e:
                return {"ok": False, "status": 0, "error": str(e)}
        # Try endpoints
        status = safe_get('/status')
        if status.get('ok'):
            result['status'] = status['data']
        else:
            result['errors']['status'] = status.get('error') or status.get('status')
        device = safe_get('/device')
        if device.get('ok'):
            result['device'] = device['data']
        else:
            result['errors']['device'] = device.get('error') or device.get('status')
        webhook = safe_get('/webhook')
        if webhook.get('ok'):
            result['webhook'] = webhook['data']
        else:
            result['errors']['webhook'] = webhook.get('error') or webhook.get('status')
        qrcode = safe_get('/qrcode')
        if qrcode.get('ok'):
            # Different keys across providers – try to normalize
            data = qrcode['data']
            qr = data.get('qrcode') or data.get('qrCode') or data.get('image') or data.get('data')
            result['qrcode'] = qr
        else:
            result['errors']['qrcode'] = qrcode.get('error') or qrcode.get('status')
        return result
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout))
    )
    def send_text(self, phone_e164, message, timeout=30):
        """
        Send a text message via Z-API.
        
        Args:
            phone_e164: Phone number in E.164 format without + (e.g., '5511999999999')
            message: Message content
            timeout: Request timeout in seconds
        
        Returns:
            Dictionary with:
                - success: bool
                - status: str (sent, failed, error)
                - provider_message_id: str (optional)
                - http_status: int
                - error: str (optional)
                - raw: dict (optional, raw response)
        """
        try:
            # Resolve effective configuration
            cfg = get_effective_zapi_config()
            send_url = cfg.get('send_text_url')
            if not send_url:
                return {
                    "success": False,
                    "status": "failed",
                    "http_status": 0,
                    "error": "Z-API não configurada. Informe as credenciais em Configurações."
                }

            # Prepare the payload
            payload = {
                "phone": phone_e164,
                "message": message
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            # Optional client token header
            if cfg.get('client_token'):
                # Some servers may look for lowercase header keys; send both just in case
                headers["Client-Token"] = cfg['client_token']
                headers["client-token"] = cfg['client_token']
            
            logger.info(f"Sending message to {phone_e164[:4]}...{phone_e164[-4:]}")
            
            # Make the request
            response = requests.post(
                send_url,
                json=payload,
                headers=headers,
                timeout=timeout
            )
            
            # Parse response
            http_status = response.status_code
            
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"raw_text": response.text}
            
            # Handle success (2xx status codes)
            if 200 <= http_status < 300:
                logger.info(f"Message sent successfully to {phone_e164[:4]}...{phone_e164[-4:]}")
                return {
                    "success": True,
                    "status": "sent",
                    "provider_message_id": response_data.get("messageId") or response_data.get("id"),
                    "http_status": http_status,
                    "raw": response_data
                }
            
            # Handle client errors (4xx)
            elif 400 <= http_status < 500:
                error_msg = response_data.get("error") or response_data.get("message") or f"Client error: {http_status}"
                logger.warning(f"Client error sending message: {error_msg}")
                return {
                    "success": False,
                    "status": "failed",
                    "http_status": http_status,
                    "error": error_msg,
                    "raw": response_data
                }
            
            # Handle server errors (5xx)
            else:
                error_msg = f"Server error: {http_status}"
                logger.error(f"Server error sending message: {error_msg}")
                return {
                    "success": False,
                    "status": "error",
                    "http_status": http_status,
                    "error": error_msg,
                    "raw": response_data
                }
                
        except requests.Timeout:
            error_msg = "Request timeout"
            logger.error(f"Timeout sending message to {phone_e164[:4]}...{phone_e164[-4:]}")
            return {
                "success": False,
                "status": "error",
                "http_status": 0,
                "error": error_msg
            }
            
        except requests.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            logger.error(f"Connection error sending message: {error_msg}")
            return {
                "success": False,
                "status": "error",
                "http_status": 0,
                "error": error_msg
            }
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(f"Unexpected error sending message")
            return {
                "success": False,
                "status": "error",
                "http_status": 0,
                "error": error_msg
            }

# Singleton instance
_client = None

def get_client():
    """Get or create the Z-API client singleton."""
    global _client
    if _client is None:
        _client = ZAPIClient()
    return _client