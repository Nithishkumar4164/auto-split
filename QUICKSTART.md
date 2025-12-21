# AutoSplit - Quick Start Guide

Get started with AutoSplit in minutes!

## Prerequisites

- Python 3.11+
- Google Cloud account with billing enabled
- Splitwise account
- Zapier account (for MCP integration)

## Local Development Setup

### 1. Clone and Install

```bash
cd autosplit
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Tesseract OCR

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

### 3. Configure Environment

Create `.env` file:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```env
GOOGLE_CLOUD_PROJECT=your-project-id
LOG_LEVEL=INFO
PORT=8090
```

### 4. Set Up Aliases

Create `aliases.json`:
```json
{
  "Your Name": ["yourname", "your", "you"],
  "Friend Name": ["friend", "buddy"]
}
```

### 5. Run Locally

```bash
python main.py
```

Test it:
```bash
# In another terminal
curl http://localhost:8090/health
```

### 6. Test with Sample Image

```bash
./local-test.sh path/to/transaction.jpeg GroupName
```

## Cloud Deployment (5 Minutes)

### 1. Set Up Google Cloud

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com
```

### 2. Deploy

```bash
./deploy.sh YOUR_PROJECT_ID us-central1
```

### 3. Create Storage Bucket

```bash
BUCKET_NAME="YOUR_PROJECT_ID-autosplit"
gsutil mb -l us-central1 gs://${BUCKET_NAME}
gsutil mkdir gs://${BUCKET_NAME}/Splitwise/
```

### 4. Upload Aliases

```bash
gsutil cp aliases.json gs://${BUCKET_NAME}/Splitwise/
```

### 5. Set Up Event Trigger

```bash
./setup-eventarc.sh YOUR_PROJECT_ID us-central1 ${BUCKET_NAME}
```

## Usage

### Upload Transaction Image

**Via gsutil:**
```bash
gsutil cp transaction.jpeg gs://${BUCKET_NAME}/Splitwise/Roommates/
```

**Via Google Cloud Console:**
1. Go to Cloud Storage
2. Navigate to your bucket
3. Upload to `Splitwise/GroupName/`

### Check Processing Status

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe autosplit \
  --platform managed --region us-central1 \
  --format 'value(status.url)')

# Check processed UTRs
curl $SERVICE_URL/utrs

# Check aliases
curl $SERVICE_URL/aliases
```

### View Logs

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=autosplit" \
  --limit 20
```

## Directory Structure

```
Splitwise/
├── aliases.json              # Your aliases file
├── GroupName1/              # Group expenses
│   └── transaction1.jpeg
├── GroupName2/              # Another group
│   └── transaction2.jpeg
└── transaction3.jpeg        # Non-group expense
```

## Zapier MCP Setup

### 1. Connect Splitwise to Zapier

1. Log in to Zapier
2. Go to "My Apps"
3. Add Splitwise connection
4. Authorize access

### 2. Configure MCP

The AutoSplit application will use Zapier MCP tools to create expenses. Ensure you have:

- Splitwise app connected in Zapier
- API credentials configured
- MCP server properly set up

### 3. Test Integration

The application will call `mcp_Zapier_splitwise_create_expense` with:
- Description from transaction message
- Cost from OCR extraction
- Participants from aliases
- Group ID (optional)

## Testing

### Run All Tests

```bash
./run-tests.sh
```

### Run with Coverage

```bash
./run-tests.sh --coverage
```

### Test Specific Module

```bash
pytest tests/test_image_parser.py -v
```

## Common Commands

### Local Development

```bash
# Start server
python main.py

# Run tests
./run-tests.sh

# Test with image
./local-test.sh image.jpeg GroupName
```

### Cloud Operations

```bash
# Deploy
./deploy.sh PROJECT_ID REGION

# View logs
gcloud logging read "resource.labels.service_name=autosplit" --limit 50

# Update service
gcloud run services update autosplit --memory 2Gi

# Delete service
gcloud run services delete autosplit
```

### Alias Management

```bash
# View aliases
curl $SERVICE_URL/aliases

# Add alias
curl -X POST $SERVICE_URL/aliases \
  -H "Content-Type: application/json" \
  -d '{"canonical_name": "John", "alias": "johnny"}'
```

## Troubleshooting

### "Tesseract not found"
```bash
# Set path in .env
TESSERACT_CMD=/usr/local/bin/tesseract
```

### "Service not receiving events"
```bash
# Check trigger
gcloud eventarc triggers list --location=us-central1

# Check service account permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID
```

### "OCR extraction failed"
- Ensure image is clear and well-lit
- Check image format (JPEG/PNG)
- Review preprocessing settings

### "Participant not matched"
- Update aliases.json
- Check fuzzy matching threshold
- Verify canonical names

## Next Steps

1. **Upload your aliases** to the Splitwise folder
2. **Create group folders** for your expense groups
3. **Upload transaction images** and watch them process automatically
4. **Check Splitwise** to see expenses created
5. **Monitor logs** for any issues

## Support

- 📖 Full documentation: [README.md](README.md)
- 🚀 Deployment guide: [DEPLOYMENT.md](DEPLOYMENT.md)
- 📋 Project details: [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- 🔧 MCP examples: [mcp_integration_example.py](mcp_integration_example.py)

## Example Workflow

```bash
# 1. Deploy to Cloud
./deploy.sh my-project us-central1

# 2. Set up storage
gsutil mb gs://my-project-autosplit
gsutil cp aliases.json gs://my-project-autosplit/Splitwise/

# 3. Set up trigger
./setup-eventarc.sh my-project us-central1 my-project-autosplit

# 4. Upload transaction
gsutil cp transaction.jpeg gs://my-project-autosplit/Splitwise/Friends/

# 5. Check result
SERVICE_URL=$(gcloud run services describe autosplit --format 'value(status.url)')
curl $SERVICE_URL/utrs | jq .
```

That's it! Your AutoSplit is now running and will automatically process transaction images. 🎉

