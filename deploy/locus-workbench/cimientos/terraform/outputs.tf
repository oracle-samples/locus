output "cluster_id" {
  description = "OKE cluster OCID — feed to `oci ce cluster create-kubeconfig`."
  value       = oci_containerengine_cluster.workbench.id
}

output "cluster_name" {
  value = oci_containerengine_cluster.workbench.name
}

output "kubeconfig_command" {
  description = "One-shot command to wire kubectl to the new cluster."
  value = format(
    "oci ce cluster create-kubeconfig --cluster-id %s --file ~/.kube/locus-workbench.kubeconfig --region %s --token-version 2.0.0 --kube-endpoint PUBLIC_ENDPOINT --profile %s",
    oci_containerengine_cluster.workbench.id,
    var.region,
    var.oci_profile,
  )
}

output "ocir_namespace" {
  description = "Tenancy namespace prefix for OCIR image refs."
  value       = data.oci_objectstorage_namespace.ns.namespace
}

output "ocir_image_ref" {
  description = "Fully-qualified image name to use in the Helm values.yaml."
  value = format(
    "%s.ocir.io/%s/locus-workbench",
    local.region_code,
    data.oci_objectstorage_namespace.ns.namespace,
  )
}

output "vcn_id" {
  value = oci_core_vcn.workbench.id
}

# Vault — the GitHub Actions workflow looks up secrets by name:
#   oci secrets secret-bundle get-secret-bundle-by-name \
#     --vault-id <vault_id> --secret-name locus-workbench-ocir-auth-token
# So all the workflow needs at runtime is the vault OCID.
output "vault_id" {
  description = "OCI Vault holding the workbench runtime secrets."
  value       = oci_kms_vault.workbench.id
}

output "vault_secret_names" {
  description = "Names of the secrets the workflow expects to read from the vault."
  value       = [for s in oci_vault_secret.workbench : s.secret_name]
}

# Set each secret post-apply with:
#   oci vault secret update-base64 --secret-id <ocid> --secret-content-content "$(printf 'real-value' | base64)"
output "vault_secret_set_commands" {
  description = "Per-secret one-liners to set the real value after first apply."
  value = {
    for k, s in oci_vault_secret.workbench :
    k => "oci vault secret update-base64 --secret-id ${s.id} --secret-content-content \"$(printf 'YOUR_VALUE' | base64)\""
  }
  sensitive = false
}

# Region-to-OCIR-prefix map for the few regions Free Tier commonly
# lands in. Extend as needed.
locals {
  region_code_by_region = {
    "ca-toronto-1"   = "yyz"
    "us-phoenix-1"   = "phx"
    "us-ashburn-1"   = "iad"
    "us-chicago-1"   = "ord"
    "eu-frankfurt-1" = "fra"
    "uk-london-1"    = "lhr"
    "sa-saopaulo-1"  = "gru"
  }
  region_code = lookup(local.region_code_by_region, var.region, var.region)
}
