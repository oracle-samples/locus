# OCI Container Registry — one repository for the workbench image.
# Region-specific; the registry FQDN is "<region-code>.ocir.io".
# For ca-toronto-1 that's "yyz.ocir.io".
#
# The Makefile's docker-build-push target tags the local image as:
#   yyz.ocir.io/<tenancy-namespace>/locus-workbench:<tag>
# and pushes against an auth token created via the Console for the
# IAM user that runs `make docker-build-push`.

data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.tenancy_ocid
}

resource "oci_artifacts_container_repository" "workbench" {
  compartment_id = var.compartment_ocid
  display_name   = "locus-workbench"
  is_public      = false
  freeform_tags  = local.common_tags

  # OCIR retains repositories across terraform destroy by default;
  # this lifecycle hook lets destroy clean up the repo too so the
  # tenancy resets cleanly.
  lifecycle {
    create_before_destroy = false
  }
}
