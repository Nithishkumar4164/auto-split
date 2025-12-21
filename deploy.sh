#!/bin/bash

# AutoSplit Deployment Script for Google Cloud Run
# Usage: ./deploy.sh [project-id] [region]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${1:-$GOOGLE_CLOUD_PROJECT}
REGION=${2:-us-central1}
SERVICE_ACCOUNT=${3:-""}  # Optional: existing service account email (e.g., auto-split-sa@PROJECT_ID.iam.gserviceaccount.com)
SERVICE_NAME="autosplit"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo -e "${GREEN}AutoSplit Deployment Script${NC}"
echo "================================"
echo ""

# Check if project ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID not set${NC}"
    echo "Usage: ./deploy.sh [project-id] [region] [service-account-email]"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh your-project-id us-central1"
    echo "  ./deploy.sh your-project-id us-central1 auto-split-sa@your-project-id.iam.gserviceaccount.com"
    exit 1
fi

echo -e "${YELLOW}Project ID:${NC} $PROJECT_ID"
echo -e "${YELLOW}Region:${NC} $REGION"
echo -e "${YELLOW}Service Name:${NC} $SERVICE_NAME"
if [ -n "$SERVICE_ACCOUNT" ]; then
    echo -e "${YELLOW}Service Account:${NC} $SERVICE_ACCOUNT"
fi
echo ""

# Set the project
echo -e "${GREEN}Setting project...${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "${GREEN}Enabling required APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable drive.googleapis.com
gcloud services enable eventarc.googleapis.com

# Build the container
echo -e "${GREEN}Building container image...${NC}"
gcloud builds submit --tag $IMAGE_NAME

# Get or create service account for Cloud Run
echo -e "${GREEN}Setting up service account...${NC}"

# Use provided service account or create a new one
if [ -n "$SERVICE_ACCOUNT" ]; then
    SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT"
    echo -e "${YELLOW}Using provided service account:${NC} $SERVICE_ACCOUNT_EMAIL"
    
    # Verify service account exists
    if ! gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL --project=$PROJECT_ID &>/dev/null; then
        echo -e "${RED}Error: Service account $SERVICE_ACCOUNT_EMAIL does not exist${NC}"
        exit 1
    fi
else
    SERVICE_ACCOUNT_EMAIL="autosplit-service@${PROJECT_ID}.iam.gserviceaccount.com"
    
    # Check if service account exists, create if not
    if ! gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL --project=$PROJECT_ID &>/dev/null; then
        echo -e "${YELLOW}Creating service account...${NC}"
        gcloud iam service-accounts create autosplit-service \
            --display-name="AutoSplit Service Account" \
            --project=$PROJECT_ID
    else
        echo -e "${GREEN}Service account already exists${NC}"
    fi
fi

# Grant necessary permissions (idempotent - safe to run multiple times)
echo -e "${YELLOW}Granting permissions to service account...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/storage.objectViewer" \
    --condition=None 2>/dev/null || echo "Storage permission already granted"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/drive.readonly" \
    --condition=None 2>/dev/null || echo "Drive permission already granted"

echo -e "${GREEN}Service account configured:${NC} $SERVICE_ACCOUNT_EMAIL"

# Deploy to Cloud Run
echo -e "${GREEN}Deploying to Cloud Run...${NC}"
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --service-account $SERVICE_ACCOUNT_EMAIL \
    --set-env-vars "LOG_LEVEL=INFO,TESSERACT_CMD=/usr/bin/tesseract,GOOGLE_CLOUD_PROJECT=$PROJECT_ID"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

echo ""
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${YELLOW}Service URL:${NC} $SERVICE_URL"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Set up Google Drive event trigger:"
echo "   gcloud eventarc triggers create drive-autosplit-trigger \\"
echo "     --destination-run-service=$SERVICE_NAME \\"
echo "     --destination-run-region=$REGION \\"
echo "     --event-filters=\"type=google.cloud.storage.object.v1.finalized\" \\"
echo "     --service-account=PROJECT_NUMBER-compute@developer.gserviceaccount.com"
echo ""
echo "2. Upload aliases.json to your Google Drive Splitwise folder"
echo "3. Test the service with: curl $SERVICE_URL/health"
echo ""

