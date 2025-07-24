# Vogent Voice AI Agent Integration

This FastAPI application integrates Vogent AI voice platform with N8N workflow automation for automated outbound voice calls with AI-powered conversation handling.

## Overview

The application provides a webhook-based service that:
- Initiates outbound voice calls through Vogent AI
- Handles webhook events from Vogent (call events, transcripts, AI extractions)
- Forwards AI-extracted data to N8N for workflow automation
- Verifies webhook signatures for security

## Prerequisites

- Python 3.11
- Vogent AI account with API access
- N8N instance for webhook processing
- Public URL for receiving webhooks (ngrok for local development)

## Environment Variables Required

Create a `.env` file with the following variables:

```env
# Vogent Configuration
VOGENT_API_KEY=your_vogent_api_key
VOGENT_AGENT_ID=your_agent_id
VOGENT_PHONE_NUMBER_ID=your_phone_number_id
VOGENT_VOICE_ID=your_voice_id
VOGENT_WEBHOOK_SECRET=your_webhook_secret

# N8N Configuration
N8N_WEBHOOK_URL=your_n8n_webhook_url

# Optional
PORT=8000  # Defaults to 8000 if not specified
```

## Installation

1. Verify Python version (should be 3.11):
```bash
python3 --version
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip3 install -r requirements.txt
```

4. If you encounter SSL certificate errors on macOS:
```bash
python install_certificates.py
```

## Local Development with Ngrok

For local testing, you'll need a public URL for webhooks:

1. Install ngrok:
```bash
# macOS with Homebrew
brew install ngrok

# Or download from https://ngrok.com/download
```

2. Start ngrok tunnel:
```bash
ngrok http 8000
```

3. Copy the HTTPS URL (e.g., `https://xxxx-xx-xx-xxx-xx.ngrok.io`) and configure it in Vogent's webhook settings

## Running the Application

Start the FastAPI server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The application will be available at `http://localhost:8000`

## API Endpoints

### Health Check
- **GET** `/`
- Returns server status

### Initiate Outbound Call
- **POST** `/outgoing-call`
- Request body:
```json
{
  "phoneNumber": "+1234567890",
  "leadId": "optional_lead_id",
  "batchId": "optional_batch_id",
  "resumeUrl": "optional_resume_url"
}
```
- Response:
```json
{
  "success": true,
  "callId": "vogent_call_id"
}
```

### Vogent Webhook Handler
- **POST** `/vogent-webhook`
- Receives and processes Vogent webhook events
- Verifies webhook signature using HMAC-SHA256
- Forwards AI extraction results to N8N

## How It Works

1. **Outbound Call Flow:**
   - External system sends POST request to `/outgoing-call` with phone number
   - Application standardizes phone number to E.164 format
   - Creates call via Vogent API with specified agent and voice
   - Returns call ID to caller

2. **Webhook Processing:**
   - Vogent sends events to `/vogent-webhook`
   - Application verifies webhook signature for security
   - For `dial.extractor` events (AI extraction results):
     - Extracts AI results and metadata
     - Forwards to N8N webhook for processing

3. **Metadata Tracking:**
   - `leadId`, `batchId`, and `resumeUrl` are passed through the entire flow
   - Metadata is preserved from call initiation to AI extraction results

## Security Features

- HMAC-SHA256 webhook signature verification
- Environment-based configuration (no hardcoded secrets)
- Async request handling with proper timeouts
- Input validation and error handling

## Testing Approach

Currently no automated tests are implemented. For testing:
1. Use the health check endpoint to verify the service is running
2. Test webhook signature verification with invalid signatures
3. Use ngrok for local webhook testing
4. Monitor logs for debugging (extensive logging is implemented)

## Deployment

### Currently depolyed on Railway

1. Push code to GitHub
2. Connect repository to deployment platform
3. Set environment variables
4. Deploy (uses `Procfile` configuration)

### Logging

The application logs detailed information for debugging:
- Call initiation details
- Webhook events received
- AI extraction results
- Error messages with stack traces

## Important Implementation Notes

1. **Phone Number Formatting**: The application automatically converts phone numbers to E.164 format. It assumes US numbers if no country code is provided.

2. **Webhook Signature Verification**: All incoming webhooks from Vogent are verified using HMAC-SHA256. The signature is expected in the `X-Vogent-Signature` header.

3. **Metadata Handling**: The application supports passing custom metadata (leadId, batchId, resumeUrl) through the entire call flow, from initiation to AI extraction results.

4. **Error Handling**: Uses FastAPI's HTTPException for error responses. All external API calls have proper error handling with descriptive messages.

5. **Async Operations**: All external API calls use httpx with a 30-second timeout to prevent hanging requests.

**Note:** Ensure compliance with all relevant terms of service when using third-party APIs (Vogent, N8N).