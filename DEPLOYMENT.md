# Deployment Guide for AutoSplit

This guide covers deploying AutoSplit to Google Cloud Run and setting up Google Drive event triggers.

## Prerequisites

1. **Google Cloud Project**
   - Active GCP project with billing enabled
   - Project ID (e.g., `my-autosplit-project`)

2. **Required Tools**
   - [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed
   - Docker installed (for local testing)
   - Python 3.11+ (for local development)

3. **Required Permissions**
   - `Cloud Run Admin`
   - `Cloud Build Editor`
   - `Storage Admin`
   - `Service Account User`
   - `Eventarc Admin`

## Step 1: Initial Setup

### 1.1 Install Google Cloud SDK

```bash
# macOS
brew install google-cloud-sdk

# Or download from: https://cloud.google.com/sdk/docs/install
```

### 1.2 Authenticate with Google Cloud

```bash
gcloud auth login
gcloud auth application-default login
```

### 1.3 Set Your Project

```bash
gcloud config set project YOUR_PROJECT_ID
```

### 1.4 Enable Required APIs

```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable drive.googleapis.com
gcloud services enable eventarc.googleapis.com
gcloud services enable storage.googleapis.com
```

## Step 2: Configure Service Account

### 2.1 Create Service Account

```bash
gcloud iam service-accounts create autosplit-sa \
    --display-name="AutoSplit Service Account"
```

### 2.2 Grant Permissions

```bash
PROJECT_ID=$(gcloud config get-value project)
SA_EMAIL="autosplit-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant Drive access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/drive.readonly"

# Grant Storage access
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.objectViewer"

# Grant Cloud Run invoker
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.invoker"
```

### 2.3 Create and Download Key

```bash
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account="${SA_EMAIL}"
```

⚠️ **Important**: Keep this key secure and never commit it to version control!

## Step 3: Set Up Google Cloud Storage

### 3.1 Create Storage Bucket

```bash
BUCKET_NAME="${PROJECT_ID}-autosplit-images"
REGION="us-central1"

gsutil mb -l $REGION gs://${BUCKET_NAME}
```

### 3.2 Create Folder Structure

```bash
# Create Splitwise root folder
gsutil mkdir gs://${BUCKET_NAME}/Splitwise/

# Create group folders
gsutil mkdir gs://${BUCKET_NAME}/Splitwise/Roommates/
gsutil mkdir gs://${BUCKET_NAME}/Splitwise/Friends/
```

### 3.3 Upload Aliases Configuration

Create `aliases.json` with your participants:

```json
{
  "Alex Boops": ["alex", "alexboops", "alex boops"],
  "Your Name": ["your", "yourname", "name"]
}
```

Upload to bucket:

```bash
gsutil cp aliases.json gs://${BUCKET_NAME}/Splitwise/aliases.json
```

## Step 4: Deploy to Cloud Run

### 4.1 Using the Deployment Script

```bash
./deploy.sh YOUR_PROJECT_ID us-central1
```

### 4.2 Manual Deployment

```bash
# Build and submit
gcloud builds submit --tag gcr.io/$PROJECT_ID/autosplit

# Deploy to Cloud Run
gcloud run deploy autosplit \
    --image gcr.io/$PROJECT_ID/autosplit \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --service-account="${SA_EMAIL}" \
    --set-env-vars "LOG_LEVEL=INFO,TESSERACT_CMD=/usr/bin/tesseract"
```

### 4.3 Verify Deployment

```bash
SERVICE_URL=$(gcloud run services describe autosplit \
    --platform managed \
    --region us-central1 \
    --format 'value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "autosplit",
  "version": "1.0.0"
}
```

## Step 5: Set Up Event Triggers

### 5.1 Using the Setup Script

```bash
./setup-eventarc.sh YOUR_PROJECT_ID us-central1 YOUR_BUCKET_NAME
```

### 5.2 Manual Setup

```bash
# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID \
    --format="value(projectNumber)")

# Create Eventarc trigger
gcloud eventarc triggers create drive-autosplit-trigger \
    --location=us-central1 \
    --destination-run-service=autosplit \
    --destination-run-region=us-central1 \
    --destination-run-path="/process-drive-event" \
    --event-filters="type=google.cloud.storage.object.v1.finalized" \
    --event-filters="bucket=${BUCKET_NAME}" \
    --service-account="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
```

### 5.3 Verify Trigger

```bash
gcloud eventarc triggers describe drive-autosplit-trigger \
    --location=us-central1
```

## Step 6: Configure Zapier MCP for Splitwise

### 6.1 Set Up Zapier Integration

1. Create a Zapier account if you don't have one
2. Connect your Splitwise account to Zapier
3. Create a Zap with:
   - Trigger: Webhook (to receive from Cloud Run)
   - Action: Splitwise - Create Expense

### 6.2 Configure MCP Tools

The application uses Zapier MCP tools for Splitwise integration. Ensure you have:

1. Splitwise API credentials
2. Zapier webhook URL configured
3. MCP server properly configured

## Step 7: Testing

### 7.1 Upload Test Image

```bash
# Upload a transaction image to trigger processing
gsutil cp your-transaction.jpeg \
    gs://${BUCKET_NAME}/Splitwise/Roommates/transaction_$(date +%s).jpeg
```

### 7.2 Check Logs

```bash
# View recent logs
gcloud logging read \
    "resource.type=cloud_run_revision AND resource.labels.service_name=autosplit" \
    --limit 50 \
    --format json

# Follow logs in real-time
gcloud alpha logging tail \
    "resource.type=cloud_run_revision AND resource.labels.service_name=autosplit"
```

### 7.3 Manual Testing

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe autosplit \
    --platform managed \
    --region us-central1 \
    --format 'value(status.url)')

# Test with curl
curl -X POST $SERVICE_URL/process-image \
    -H "Content-Type: application/json" \
    -d '{
      "image_path": "/tmp/test_transaction.jpeg",
      "group_name": "Roommates"
    }'
```

## Step 8: Monitoring and Maintenance

### 8.1 View Service Metrics

```bash
# Open Cloud Console
gcloud run services describe autosplit \
    --platform managed \
    --region us-central1
```

Or visit: `https://console.cloud.google.com/run`

### 8.2 Update Service

```bash
# Rebuild and deploy
./deploy.sh YOUR_PROJECT_ID us-central1
```

### 8.3 View Processed UTRs

```bash
curl $SERVICE_URL/utrs
```

### 8.4 Manage Aliases

```bash
# Get all aliases
curl $SERVICE_URL/aliases

# Add new alias
curl -X POST $SERVICE_URL/aliases \
    -H "Content-Type: application/json" \
    -d '{
      "canonical_name": "John Doe",
      "alias": "john"
    }'
```

## Troubleshooting

### Issue: Service not receiving events

**Solution:**
1. Check if Eventarc trigger is active:
   ```bash
   gcloud eventarc triggers list --location=us-central1
   ```
2. Verify service account permissions
3. Check trigger logs:
   ```bash
   gcloud logging read "resource.type=eventarc.googleapis.com/trigger"
   ```

### Issue: OCR not working

**Solution:**
1. Verify Tesseract is installed in container:
   ```bash
   gcloud run services describe autosplit --format yaml
   ```
2. Check logs for OCR errors
3. Test with higher quality images

### Issue: Splitwise expense not created

**Solution:**
1. Verify Zapier MCP configuration
2. Check Splitwise API credentials
3. Review participant matching in aliases
4. Check logs for API errors

### Issue: Duplicate expenses

**Solution:**
1. Check UTR tracking:
   ```bash
   curl $SERVICE_URL/utrs
   ```
2. Verify UTR extraction from images
3. Review processed_utrs.json in logs

## Cost Optimization

### 8.1 Adjust Resource Limits

```bash
gcloud run services update autosplit \
    --memory 1Gi \
    --cpu 1 \
    --max-instances 5
```

### 8.2 Set Up Budget Alerts

1. Go to Billing in Cloud Console
2. Create budget alert for your project
3. Set threshold (e.g., $10/month)

### 8.3 Clean Up Old Images

```bash
# Delete images older than 30 days
gsutil -m rm -r \
    $(gsutil ls -l gs://${BUCKET_NAME}/Splitwise/**/*.jpeg | \
    awk '{if ($2 < "'$(date -d '30 days ago' +%Y-%m-%d)'") print $3}')
```

## Security Best Practices

1. **Never commit credentials**
   - Use Secret Manager for sensitive data
   - Keep service account keys secure

2. **Use least privilege**
   - Grant minimal necessary permissions
   - Regularly audit IAM policies

3. **Enable audit logging**
   - Monitor access patterns
   - Set up alerts for suspicious activity

4. **Keep dependencies updated**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

5. **Use VPC for private access**
   - Consider VPC connector for enhanced security
   - Restrict network access

## Support

For issues or questions:
- Check logs: `gcloud logging read`
- Review documentation: See README.md
- Open an issue on GitHub

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Eventarc Documentation](https://cloud.google.com/eventarc/docs)
- [Splitwise API Documentation](https://dev.splitwise.com)
- [Zapier MCP Documentation](https://zapier.com/help/mcp)

