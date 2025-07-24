from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv
import requests
import httpx
import json
import os
import datetime
import re
import hashlib
import hmac

load_dotenv(override=True)

# Get environment variables
VOGENT_API_KEY = os.environ.get('VOGENT_API_KEY')
VOGENT_AGENT_ID = os.environ.get('VOGENT_AGENT_ID')
VOGENT_PHONE_NUMBER_ID = os.environ.get('VOGENT_PHONE_NUMBER_ID')
VOGENT_VOICE_ID = os.environ.get('VOGENT_VOICE_ID')
VOGENT_WEBHOOK_SECRET = os.environ.get('VOGENT_WEBHOOK_SECRET', 'inDYZbs7BXHC59w')
N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL')
PORT = int(os.environ.get('PORT', '8000'))

app = FastAPI()

def verify_webhook_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """
    Verify webhook signature from Vogent using HMAC-SHA256
    """
    try:
        # Create HMAC with secret
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures using timing-safe comparison
        return hmac.compare_digest(signature, expected_signature)
    except Exception as e:
        print(f"❌ Error verifying webhook signature: {e}")
        return False

@app.get("/")
async def root():
    return {"message": "Vogent Integration Server is running!"}

@app.post("/outgoing-call")
async def outgoing_call(request: Request):
    """
    Initiate an outbound call via Vogent API
    """
    try:
        # Get request data
        data = await request.json()
        phone_number = data.get('phoneNumber')
        lead_id = data.get('leadId')
        batch_id = data.get('batchId')
        resume_url = data.get('resumeUrl')
        
        if not phone_number:
            return {"error": "Phone number is required"}
        
        # Standardize phone number to E.164 format
        phone_number = standardize_phone_number(phone_number)
        if not phone_number:
            return {"error": "Invalid phone number format"}
        
        print('\n===== 📞 INITIATING OUTBOUND CALL =====')
        print(f"   To: {phone_number}")
        print(f"   Lead ID: {lead_id}")
        print(f"   Batch ID: {batch_id}")
        
        # Create outbound call via Vogent API
        call_data = await create_vogent_call(
            phone_number=phone_number,
            lead_id=lead_id,
            batch_id=batch_id,
            resume_url=resume_url
        )
        
        # Check if call creation failed
        if not call_data or "id" not in call_data:
            print("❌ Failed to create call with Vogent")
            print("===== END CALL INITIATION =====\n")
            return {
                "lead_id": lead_id,
                "batch_id": batch_id
            }

        print(f"   Vogent call ID: {call_data['id']}")
        print("===== END CALL INITIATION =====\n")
        return {
            "success": True,
            "callId": call_data["id"]
        }

    except Exception as error:
        print('\n❌ ERROR CREATING CALL:')
        print(f"   Error: {str(error)}")
        import traceback
        traceback.print_exc()
        print("===== END ERROR =====\n")
        return {"error": str(error)}

@app.post("/vogent-webhook")
async def vogent_webhook(request: Request):
    """
    Handle webhooks from Vogent (call events, transcripts, extractor results)
    """
    try:
        print(f"\n===== 📥 VOGENT WEBHOOK RECEIVED =====")
        print(f"Timestamp: {datetime.datetime.now().isoformat()}")
        
        # Get the raw body for signature verification
        raw_body = await request.body()
        
        # Verify webhook signature
        signature = request.headers.get('X-Elto-Signature', '')
        if not signature:
            print("❌ Missing X-Elto-Signature header")
            return {"error": "Missing signature header"}, 401
        
        if not verify_webhook_signature(raw_body, signature, VOGENT_WEBHOOK_SECRET):
            print("❌ Invalid webhook signature")
            return {"error": "Invalid signature"}, 401
        
        print("✅ Webhook signature verified successfully")
        
        # Parse JSON data after signature verification
        data = json.loads(raw_body.decode('utf-8'))
        event_type = data.get('event')
        payload = data.get('payload', {})
        
        print(f"Event type: {event_type}")
        
        # Extract metadata from top level of webhook data (not from payload)
        webhook_metadata = data.get('metadata', {})
        extracted_lead_id = webhook_metadata.get('leadId')
        extracted_batch_id = webhook_metadata.get('batchId')
        
        if extracted_lead_id or extracted_batch_id:
            print(f"🎯 Found metadata in webhook - leadId: {extracted_lead_id}, batchId: {extracted_batch_id}")
        
        # Only process the extractor event - that's when we send to N8N
        if event_type == "dial.extractor":
            # We have the AI extraction results
            dial_id = payload.get('dial_id')
            ai_result = payload.get('ai_result', {})
            
            print(f"🤖 Received AI extraction for call {dial_id}")
            print(f"   Lead ID: {extracted_lead_id}")
            print(f"   Batch ID: {extracted_batch_id}")
            
            # Send simplified data to N8N
            webhook_payload = {
                "data": json.dumps(ai_result),
                "leadId": extracted_lead_id,
                "batchId": extracted_batch_id,
                "dialId": dial_id
            }
            
            print(f"   Sending simplified payload to N8N")
            response = await send_to_webhook(webhook_payload)
            print(f"   N8N response: {response}")
            
        else:
            # Log other events but don't process them
            dial_id = payload.get('dial_id')
            print(f"📌 Event {event_type} for call {dial_id} - logging only")
        
        print("===== END WEBHOOK PROCESSING =====\n")
        # Return success to Vogent
        return {"success": True}
            
    except Exception as error:
        print('\n❌ ERROR HANDLING VOGENT WEBHOOK:')
        print(f"   Error: {str(error)}")
        import traceback
        traceback.print_exc()
        print("===== END ERROR =====\n")
        return {"error": str(error)}

async def create_vogent_call(phone_number, lead_id=None, batch_id=None, resume_url=None):
    """
    Create an outbound call using the Vogent API with async HTTP client
    """
    url = "https://api.vogent.ai/api/dials"
    
    headers = {
        "Authorization": f"Bearer {VOGENT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "callAgentId": VOGENT_AGENT_ID,
        "aiVoiceId": VOGENT_VOICE_ID,
        "toNumber": phone_number,
        "fromNumberId": VOGENT_PHONE_NUMBER_ID,
        "browserCall": False,
        "timeoutMinutes": 10
    }
    
    # Add callAgentInput with leadId and batchId if provided
    if lead_id or batch_id:
        payload["callAgentInput"] = {}
        if lead_id:
            payload["callAgentInput"]["leadId"] = lead_id
        if batch_id:
            payload["callAgentInput"]["batchId"] = batch_id
        if resume_url:
            payload["callAgentInput"]["resumeUrl"] = resume_url
    
    # Add metadata if leadId is provided
    if lead_id:
        payload["metadata"] = {
            "leadId": lead_id
        }
        # Add batchId to metadata if provided
        if batch_id:
            payload["metadata"]["batchId"] = batch_id
    elif batch_id:
        # If only batchId is provided without leadId
        payload["metadata"] = {
            "batchId": batch_id
        }
    
    try:
        # Use async httpx client with proper timeout
        timeout = httpx.Timeout(60.0, connect=15.0)  # 60s total, 15s connect for API calls
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
        
        if not response.is_success:
            print(f"Error creating Vogent call: {response.status_code} {response.text}")
            return None
        
        return response.json()
        
    except httpx.TimeoutException as e:
        print(f"Timeout creating Vogent call: {str(e)}")
        return None
    except httpx.RequestError as e:
        print(f"Request error creating Vogent call: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error creating Vogent call: {str(e)}")
        return None

async def send_to_webhook(payload):
    """
    Send data to N8N webhook using async HTTP client
    """
    if not N8N_WEBHOOK_URL:
        print("Error: N8N_WEBHOOK_URL is not set")
        return json.dumps({"error": "N8N_WEBHOOK_URL not configured"})
        
    try:
        print(f"Sending to N8N webhook: {N8N_WEBHOOK_URL}")
        print(f"Payload: {json.dumps(payload)}")
        
        # Use async httpx client with proper timeout and error handling
        timeout = httpx.Timeout(30.0, connect=10.0)  # 30s total, 10s connect
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                N8N_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
        
        if response.status_code != 200:
            print(f"⚠️ N8N webhook returned status code {response.status_code}")
            print(f"Response: {response.text}")
            return json.dumps({"error": f"N8N webhook returned status {response.status_code}"})
        
        # Truncate long responses in logs
        response_text = response.text
        if len(response_text) > 500:
            print(f"N8N response (truncated): {response_text[:500]}... [truncated]")
        else:
            print(f"N8N response: {response_text}")
            
        return response.text
        
    except httpx.TimeoutException as e:
        error_msg = f"Timeout sending data to N8N webhook: {str(e)}"
        print(f"❌ {error_msg}")
        return json.dumps({"error": error_msg})
    except httpx.RequestError as e:
        error_msg = f"Request error sending data to N8N webhook: {str(e)}"
        print(f"❌ {error_msg}")
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Unexpected error sending data to N8N webhook: {str(e)}"
        print(f"❌ {error_msg}")
        return json.dumps({"error": error_msg})

def standardize_phone_number(phone_number):
    """
    Standardize phone number to E.164 format (+[country code][number])
    """
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone_number)
    
    # If the number starts with country code
    if phone_number.startswith('+'):
        return f"+{digits_only}"
    
    # If US/Canada number (10 digits)
    if len(digits_only) == 10:
        return f"+1{digits_only}"
    
    # If US/Canada number with country code (11 digits starting with 1)
    if len(digits_only) == 11 and digits_only.startswith('1'):
        return f"+{digits_only}"
    
    # Otherwise, return as is with + prefix
    if len(digits_only) > 7:  # Basic validation to ensure it's a plausible number
        return f"+{digits_only}"
    
    return None  # Invalid number

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)