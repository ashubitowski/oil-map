#!/bin/sh
# Upload data files to Cloudflare R2.
# Run this after regenerating any state's bin files.
#
# Setup (one-time):
#   1. Create an R2 bucket named "oil-map-data" in the Cloudflare dashboard
#   2. Create an S3 API token (R2 → Manage R2 API tokens) with write access
#   3. Add to ~/.aws/credentials:
#        [r2]
#        aws_access_key_id = <your-key-id>
#        aws_secret_access_key = <your-secret>
#   4. Set ACCOUNT_ID below (find it on R2 → Overview in Cloudflare dashboard)
#
# Usage: sh scripts/upload-data.sh

ACCOUNT_ID="${CF_ACCOUNT_ID:-YOUR_ACCOUNT_ID_HERE}"
BUCKET="oil-map-data"
ENDPOINT="https://${ACCOUNT_ID}.r2.cloudflarestorage.com"
PROFILE="${AWS_PROFILE:-r2}"

aws s3 sync public/data/ "s3://${BUCKET}/data/" \
  --endpoint-url "${ENDPOINT}" \
  --profile "${PROFILE}" \
  --exclude "production-basins.json" \
  --exclude "production-history.json" \
  --cache-control "public, max-age=3600" \
  --no-progress

echo "Upload complete."
