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

BUCKET="oil-map-data"
PROFILE="${AWS_PROFILE:-r2}"
# Use endpoint_url from ~/.aws/config [profile r2] if CF_ACCOUNT_ID not set
if [ -n "${CF_ACCOUNT_ID:-}" ]; then
  ENDPOINT="https://${CF_ACCOUNT_ID}.r2.cloudflarestorage.com"
else
  ENDPOINT=""
fi

python3 scripts/wells/freshness.py

ENDPOINT_ARG=""
[ -n "${ENDPOINT}" ] && ENDPOINT_ARG="--endpoint-url ${ENDPOINT}"

aws s3 sync public/data/ "s3://${BUCKET}/data/" \
  ${ENDPOINT_ARG} \
  --profile "${PROFILE}" \
  --exclude "production-basins.json" \
  --exclude "production-history.json" \
  --cache-control "public, max-age=3600" \
  --no-progress

echo "Upload complete."
