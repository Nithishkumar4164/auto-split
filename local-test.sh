#!/bin/bash

# Local testing script for AutoSplit
# Usage: ./local-test.sh [image-path] [group-name]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

IMAGE_PATH=${1}
GROUP_NAME=${2}

echo -e "${GREEN}AutoSplit Local Testing${NC}"
echo "================================"
echo ""

# Check if image path is provided
if [ -z "$IMAGE_PATH" ]; then
    echo -e "${RED}Error: Image path not provided${NC}"
    echo "Usage: ./local-test.sh [image-path] [group-name]"
    exit 1
fi

# Check if image file exists
if [ ! -f "$IMAGE_PATH" ]; then
    echo -e "${RED}Error: Image file not found: $IMAGE_PATH${NC}"
    exit 1
fi

echo -e "${YELLOW}Image Path:${NC} $IMAGE_PATH"
if [ -n "$GROUP_NAME" ]; then
    echo -e "${YELLOW}Group Name:${NC} $GROUP_NAME"
fi
echo ""

# Check if Flask app is running
if ! curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${RED}Error: AutoSplit service is not running${NC}"
    echo "Start the service first with: python main.py"
    exit 1
fi

# Prepare JSON payload
if [ -n "$GROUP_NAME" ]; then
    PAYLOAD=$(cat <<EOF
{
  "image_path": "$IMAGE_PATH",
  "group_name": "$GROUP_NAME"
}
EOF
)
else
    PAYLOAD=$(cat <<EOF
{
  "image_path": "$IMAGE_PATH"
}
EOF
)
fi

# Send request to process image
echo -e "${GREEN}Processing image...${NC}"
echo ""

RESPONSE=$(curl -s -X POST http://localhost:8080/process-image \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

echo "$RESPONSE" | python3 -m json.tool

echo ""

# Check if successful
if echo "$RESPONSE" | grep -q '"success": true'; then
    echo -e "${GREEN}✓ Image processed successfully!${NC}"
else
    echo -e "${RED}✗ Image processing failed${NC}"
fi

