# Google Cloud SDK Setup Guide

## Install Google Cloud SDK on macOS

### Option 1: Using Homebrew (Recommended)

```bash
# Install Google Cloud SDK
brew install --cask google-cloud-sdk

# Add gcloud to PATH (add to ~/.zshrc or ~/.bash_profile)
source "$(brew --prefix)/share/google-cloud-sdk/path.zsh.inc"
source "$(brew --prefix)/share/google-cloud-sdk/completion.zsh.inc"

# Reload shell
source ~/.zshrc
```

### Option 2: Manual Installation

```bash
# Download the SDK
curl https://sdk.cloud.google.com | bash

# Restart your shell
exec -l $SHELL

# Initialize the SDK
gcloud init
```

### Option 3: Using Python pip

```bash
# Install gcloud CLI
pip install gcloud
```

## Verify Installation

```bash
# Check if gcloud is installed
gcloud --version

# Expected output:
# Google Cloud SDK 456.0.0
# bq 2.0.101
# core 2024.01.01
# gcloud-crc32c 1.0.0
# gsutil 5.27
```

## Initial Configuration

### 1. Authenticate with Google Cloud

```bash
gcloud auth login
```

This will:
- Open a browser window
- Ask you to sign in with your Google account
- Grant access to gcloud

### 2. Set Your Project

```bash
gcloud config set project your-project-id
```

### 3. Set Default Region

```bash
gcloud config set compute/region us-central1
```

### 4. Enable Application Default Credentials

```bash
gcloud auth application-default login
```

## Enable Required APIs

```bash
# Enable all required APIs for AutoSplit
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable eventarc.googleapis.com
gcloud services enable drive.googleapis.com
```

## Verify Setup

```bash
# Check current configuration
gcloud config list

# Expected output:
# [compute]
# region = us-central1
# [core]
# account = your-email@gmail.com
# project = your-project-id
```

## Create Service Account (Optional but Recommended)

```bash
# Create service account
gcloud iam service-accounts create autosplit-sa \
    --display-name="AutoSplit Service Account"

# Get service account email
SA_EMAIL="autosplit-sa@your-project-id.iam.gserviceaccount.com"

# Grant necessary permissions
gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding your-project-id \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.invoker"

# Create and download key
gcloud iam service-accounts keys create service-account-key.json \
    --iam-account="${SA_EMAIL}"
```

## Now Try Deployment Again

```bash
# Make sure you're in the autosplit directory
cd /path/to/autosplit

# Run deployment script
./deploy.sh your-project-id us-central1
```

## Troubleshooting

### "gcloud: command not found"
- Make sure you added gcloud to your PATH
- Restart your terminal
- Run: `source ~/.zshrc` (or `source ~/.bash_profile`)

### "Permission denied"
- Make sure you're authenticated: `gcloud auth login`
- Check your project: `gcloud config get-value project`

### "API not enabled"
- Enable required APIs (see above)
- Wait a few minutes for APIs to activate

### "Insufficient permissions"
- Make sure your Google account has Owner or Editor role
- Check IAM permissions in Cloud Console

## Quick Setup Script

Create a file `setup-gcloud.sh`:

```bash
#!/bin/bash

echo "Installing Google Cloud SDK..."
brew install --cask google-cloud-sdk

echo "Adding to PATH..."
echo 'source "$(brew --prefix)/share/google-cloud-sdk/path.zsh.inc"' >> ~/.zshrc
echo 'source "$(brew --prefix)/share/google-cloud-sdk/completion.zsh.inc"' >> ~/.zshrc

echo "Reloading shell..."
source ~/.zshrc

echo "Authenticating..."
gcloud auth login

echo "Setting project..."
gcloud config set project your-project-id
gcloud config set compute/region us-central1

echo "Enabling APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable eventarc.googleapis.com

echo "✅ Setup complete!"
gcloud config list
```

Then run:
```bash
chmod +x setup-gcloud.sh
./setup-gcloud.sh
```

## Alternative: Use Cloud Console

If you prefer not to use gcloud CLI, you can:

1. Build Docker image locally:
   ```bash
   docker build -t gcr.io/your-project-id/autosplit .
   ```

2. Push to Container Registry (requires Docker authentication):
   ```bash
   gcloud auth configure-docker
   docker push gcr.io/your-project-id/autosplit
   ```

3. Deploy via Cloud Console:
   - Go to https://console.cloud.google.com/run
   - Click "Create Service"
   - Select your container image
   - Configure settings manually

## Resources

- [Google Cloud SDK Documentation](https://cloud.google.com/sdk/docs)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [gcloud CLI Reference](https://cloud.google.com/sdk/gcloud/reference)

