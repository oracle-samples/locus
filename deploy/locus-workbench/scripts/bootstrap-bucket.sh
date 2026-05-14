#!/usr/bin/env bash
# One-time bootstrap for the Terraform state bucket. Creates an OCI
# Object Storage bucket and prints the namespace-scoped S3-compat
# endpoint you'll pass to `terraform init`.
#
# Usage:
#   ./scripts/bootstrap-bucket.sh
#
# Idempotent — re-runs are safe; it skips create if the bucket
# already exists.

set -euo pipefail

PROFILE="${OCI_PROFILE:-API_FREE_TIER}"
REGION="${OCI_REGION:-ca-toronto-1}"
COMPARTMENT_ID="${OCI_COMPARTMENT_OCID:?must set OCI_COMPARTMENT_OCID}"
BUCKET_NAME="${BUCKET_NAME:-locus-workbench-tfstate}"

echo "Resolving namespace..."
NAMESPACE=$(
  oci os ns get \
    --profile "$PROFILE" --region "$REGION" \
    --auth api_key \
    --query 'data' --raw-output
)
echo "Namespace: $NAMESPACE"

ENDPOINT="https://$NAMESPACE.compat.objectstorage.$REGION.oraclecloud.com"
echo "S3-compat endpoint: $ENDPOINT"

if oci os bucket get \
    --profile "$PROFILE" --region "$REGION" --auth api_key \
    --bucket-name "$BUCKET_NAME" \
    --namespace-name "$NAMESPACE" \
    >/dev/null 2>&1; then
  echo "Bucket $BUCKET_NAME already exists — skipping create."
else
  echo "Creating bucket $BUCKET_NAME..."
  oci os bucket create \
    --profile "$PROFILE" --region "$REGION" --auth api_key \
    --compartment-id "$COMPARTMENT_ID" \
    --namespace-name "$NAMESPACE" \
    --name "$BUCKET_NAME" \
    --versioning Enabled \
    --public-access-type NoPublicAccess
fi

cat <<EOF

Bootstrap complete. To initialize Terraform against this bucket:

  terraform init \\
    -backend-config="endpoints={\"s3\":\"$ENDPOINT\"}" \\
    -reconfigure

Required env vars (NOT the OCI API key — Customer Secret Key):
  export AWS_ACCESS_KEY_ID='<your-oci-customer-secret-key>'
  export AWS_SECRET_ACCESS_KEY='<your-oci-customer-secret-key-secret>'

Generate the Customer Secret Key in the OCI Console:
  User → Customer Secret Keys → Generate
EOF
