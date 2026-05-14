# Terraform provider configuration for the locus-workbench
# free-tier stack. Defaults to the OCI Always-Free home region in
# Toronto; override `region` in terraform.tfvars to retarget.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.45.0"
    }
  }
}

provider "oci" {
  config_file_profile = var.oci_profile
  region              = var.region
}
