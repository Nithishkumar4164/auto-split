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
SERVICE_NAME="autosplit"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo -e "${GREEN}AutoSplit Deployment Script${NC}"
echo "================================"
echo ""

# Check if project ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: PROJECT_ID not set${NC}"
    echo "Usage: ./deploy.sh [project-id] [region]"
    exit 1
fi

echo -e "${YELLOW}Project ID:${NC} $PROJECT_ID"
echo -e "${YELLOW}Region:${NC} $REGION"
echo -e "${YELLOW}Service Name:${NC} $SERVICE_NAME"
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
    --set-env-vars "LOG_LEVEL=INFO,TESSERACT_CMD=/usr/bin/tesseract"

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

