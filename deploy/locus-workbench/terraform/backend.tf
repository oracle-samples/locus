# Local state for the workbench stack. This is a single-tenant
# free-tier deployment — no team needs remote state.
#
# To upgrade to OCI Object Storage remote state later, replace the
# `local` block with:
#
#   terraform {
#     backend "s3" {
#       endpoint = "https://<namespace>.compat.objectstorage.<region>.oraclecloud.com"
#       bucket   = "locus-workbench-tfstate"
#       key      = "terraform.tfstate"
#       region   = "<region>"
#       shared_credentials_files = ["~/.aws/credentials"]
#       # ... see almariel/cimientos/terraform/backend.tf for the full pattern.
#     }
#   }

terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
