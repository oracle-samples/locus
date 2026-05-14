# OCI Vault — runtime secret store. Terraform creates the vault,
# master key, and 6 secret containers (placeholders). Actual values
# are populated post-apply via `oci vault secret update-base64` so
# rotations don't drift Terraform state.
#
# Free-tier allowance:
#   1 vault (DEFAULT type)
#   20 key versions
#   150 secret versions
# We use 1 vault + 1 key + 6 secrets — well within budget.

resource "oci_kms_vault" "workbench" {
  compartment_id = var.compartment_ocid
  display_name   = "${local.name}-vault"
  vault_type     = "DEFAULT"
  freeform_tags  = local.common_tags
}

resource "oci_kms_key" "workbench_master" {
  compartment_id      = var.compartment_ocid
  display_name        = "${local.name}-master-key"
  protection_mode     = "SOFTWARE"
  management_endpoint = oci_kms_vault.workbench.management_endpoint

  key_shape {
    algorithm = "AES"
    length    = 32
  }
  freeform_tags = local.common_tags
}

# The six secrets the GitHub Actions workflow needs at deploy time.
# Names match the env vars the workflow expects so the lookup loop
# is trivial.
locals {
  workbench_secret_names = [
    "ocir-auth-token",     # password for docker login to OCIR
    "ocir-username",       # OCI Console username (no namespace prefix)
    "s3compat-access-key", # Customer Secret Key access part — TF state backend
    "s3compat-secret-key", # Customer Secret Key secret part — TF state backend
    "openai-api-key",      # injected into workbench pods (optional)
    "anthropic-api-key",   # injected into workbench pods (optional)
  ]
}

resource "oci_vault_secret" "workbench" {
  for_each       = toset(local.workbench_secret_names)
  compartment_id = var.compartment_ocid
  vault_id       = oci_kms_vault.workbench.id
  key_id         = oci_kms_key.workbench_master.id
  secret_name    = "${local.name}-${each.key}"
  description    = "locus-workbench runtime secret: ${each.key}"

  # Initial content is a base64 sentinel — real values land via:
  #   oci vault secret update-base64 \
  #     --secret-id <ocid> --secret-content-content "$(printf 'real-value' | base64)"
  secret_content {
    content_type = "BASE64"
    content      = base64encode("placeholder-set-me-with-update-base64")
  }

  lifecycle {
    # Once a real value lands, Terraform must NOT overwrite it on
    # the next apply. Rotation flows through `oci vault secret
    # update-base64` directly, not through state.
    ignore_changes = [secret_content]
  }

  freeform_tags = local.common_tags
}
