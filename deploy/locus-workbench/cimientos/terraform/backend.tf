# Remote state in OCI Object Storage via the S3-compat endpoint.
# The bucket itself is provisioned out-of-band by
# scripts/bootstrap-bucket.sh (chicken-and-egg — can't store this
# state IN this state).
#
# Required env vars for the S3-compat creds:
#   AWS_ACCESS_KEY_ID         OCI Customer Secret Key access key
#   AWS_SECRET_ACCESS_KEY     OCI Customer Secret Key secret
#
# Generate the Customer Secret Key in the OCI Console:
#   User → Customer Secret Keys → Generate

terraform {
  backend "s3" {
    region = "ca-toronto-1"
    bucket = "locus-workbench-tfstate"
    key    = "terraform.tfstate"

    # The endpoint is namespace-scoped. bootstrap-bucket.sh prints
    # the right URL; pass it on init:
    #   terraform init -backend-config=endpoints='{"s3":"<url>"}'

    # OCI S3 compatibility quirks — these flags make Terraform play
    # nicely with Oracle's S3-compat API. The names differ between
    # terraform 1.5.x (use_path_style) and 1.6+ (use_path_style);
    # the 1.5.x names are kept here for compatibility with the
    # widely-shipped Homebrew terraform 1.5.7. CI runs 1.9.8 and
    # silently accepts either spelling.
    use_path_style              = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    # OCI S3-compat returns 501 NotImplemented on chunked uploads;
    # skipping the per-chunk SHA256 checksum keeps the SDK on the
    # single-PUT path. Without this, state writes fail with
    # "AWS chunked encoding not supported".
    skip_s3_checksum = true
  }
}
