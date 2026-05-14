# Inputs. Set in terraform.tfvars (see terraform.tfvars.example) or
# pass with -var on the CLI. All have sensible Always-Free defaults
# for ca-toronto-1 so a fresh apply works with zero overrides on a
# blank free-tier tenancy.

variable "tenancy_ocid" {
  description = "Tenancy OCID. The free-tier home tenancy."
  type        = string
}

variable "compartment_ocid" {
  description = "Compartment OCID to provision into. Tenancy root works on free tier."
  type        = string
}

variable "oci_profile" {
  description = "Profile name in ~/.oci/config. Default API_FREE_TIER."
  type        = string
  default     = "API_FREE_TIER"
}

variable "region" {
  description = "Home region of the free-tier tenancy. Default ca-toronto-1."
  type        = string
  default     = "ca-toronto-1"
}

variable "name_prefix" {
  description = "Prefix for every resource name."
  type        = string
  default     = "locus-workbench"
}

variable "vcn_cidr" {
  description = "CIDR for the workbench VCN."
  type        = string
  default     = "10.42.0.0/16"
}

variable "k8s_version" {
  description = "OKE Kubernetes version. Defaults to a current LTS line."
  type        = string
  default     = "v1.32.10"
}

variable "node_pool_shape" {
  description = "Worker node shape. ARM A1.Flex is the only Always-Free shape."
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "node_pool_ocpus" {
  description = "OCPUs per worker. Free-tier budget is 4 OCPU total across A1.Flex."
  type        = number
  default     = 2
}

variable "node_pool_memory_gb" {
  description = "Memory per worker in GB. Free-tier budget is 24 GB total."
  type        = number
  default     = 12
}

variable "node_pool_size" {
  description = "Number of worker nodes. 1 fits everything within free-tier limits."
  type        = number
  default     = 1
}

variable "node_pool_image_id" {
  description = <<-EOT
    Oracle Linux 8 ARM image OCID for the OKE node pool. Region-specific.
    Pull the latest with:
      oci ce node-pool-options get --node-pool-option-id all \
        --profile API_FREE_TIER --region ca-toronto-1 \
        --query 'data.sources[?contains(\"source-name\", `OKE-1.31.10`) && contains(\"source-name\", `aarch64`)]'
  EOT
  type        = string
  default     = ""
}
