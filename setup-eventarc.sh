#!/bin/bash

# Setup Eventarc trigger for Google Drive events
# Usage: ./setup-eventarc.sh [project-id] [region] [bucket-name]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${1:-$GOOGLE_CLOUD_PROJECT}
REGION=${2:-us-central1}
BUCKET_NAME=${3}
SERVICE_NAME="autosplit"
TRIGGER_NAME="drive-autosplit-trigger"

echo -e "${GREEN}AutoSplit Eventarc Setup${NC}"
echo "================================"
echo ""

# Check if parameters are set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID not set${NC}"
    echo "Usage: ./setup-eventarc.sh [project-id] [region] [bucket-name]"
    exit 1
fi

if [ -z "$BUCKET_NAME" ]; then
    echo -e "${RED}Error: BUCKET_NAME not set${NC}"
    echo "Usage: ./setup-eventarc.sh [project-id] [region] [bucket-name]"
    exit 1
fi

echo -e "${YELLOW}Project ID:${NC} $PROJECT_ID"
echo -e "${YELLOW}Region:${NC} $REGION"
echo -e "${YELLOW}Bucket Name:${NC} $BUCKET_NAME"
echo -e "${YELLOW}Service Name:${NC} $SERVICE_NAME"
echo ""

# Set the project
gcloud config set project $PROJECT_ID

# Get project number
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SERVICE_ACCOUNT="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

echo -e "${YELLOW}Service Account:${NC} $SERVICE_ACCOUNT"
echo ""

# Enable Eventarc API
echo -e "${GREEN}Enabling Eventarc API...${NC}"
gcloud services enable eventarc.googleapis.com

# Grant necessary permissions to the service account
echo -e "${GREEN}Granting permissions...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/eventarc.eventReceiver"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/run.invoker"

# Create Eventarc trigger for Google Cloud Storage
echo -e "${GREEN}Creating Eventarc trigger...${NC}"
gcloud eventarc triggers create $TRIGGER_NAME \
    --location=$REGION \
    --destination-run-service=$SERVICE_NAME \
    --destination-run-region=$REGION \
    --destination-run-path="/process-drive-event" \
    --event-filters="type=google.cloud.storage.object.v1.finalized" \
    --event-filters="bucket=$BUCKET_NAME" \
    --service-account=$SERVICE_ACCOUNT

echo ""
echo -e "${GREEN}Eventarc trigger created successfully!${NC}"
echo ""
echo -e "${YELLOW}Trigger Details:${NC}"
gcloud eventarc triggers describe $TRIGGER_NAME --location=$REGION
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Upload transaction images to gs://$BUCKET_NAME/Splitwise/GroupName/"
echo "2. The trigger will automatically invoke the AutoSplit service"
echo "3. Check logs: gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME\" --limit 50"
echo ""

