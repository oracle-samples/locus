# OKE cluster — defaults to BASIC_CLUSTER which is the $0/hour
# control-plane SKU on Always-Free. Switch ``type`` to
# ``ENHANCED_CLUSTER`` if your tenancy already has the one BASIC slot
# consumed by another cluster — the free-tier quota is one BASIC
# cluster but up to 15 ENHANCED clusters (which cost $0.10/hr each
# for the control plane). Use ``oci limits resource-availability get
# --service-name container-engine --limit-name cluster-count`` to
# check before applying.
#
# Public endpoint so kubectl works from anywhere with the cluster's
# kubeconfig. Single ARM A1.Flex node provides the entire compute
# envelope for the workbench's 3 tiers.

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

resource "oci_containerengine_cluster" "workbench" {
  compartment_id     = var.compartment_ocid
  vcn_id             = oci_core_vcn.workbench.id
  kubernetes_version = var.k8s_version
  name               = "${local.name}-oke"
  type               = "BASIC_CLUSTER"

  endpoint_config {
    is_public_ip_enabled = true
    subnet_id            = oci_core_subnet.public.id
    nsg_ids              = [oci_core_network_security_group.oke_api.id]
  }

  cluster_pod_network_options {
    cni_type = "OCI_VCN_IP_NATIVE"
  }

  options {
    service_lb_subnet_ids = [oci_core_subnet.public.id]
    add_ons {
      is_kubernetes_dashboard_enabled = false
      is_tiller_enabled               = false
    }
  }

  freeform_tags = local.common_tags

  # OKE clusters cannot be moved between compartments — the OCI API
  # has no /clusters/{id}/actions/changeCompartment endpoint. Pin
  # the compartment forever or accept a destroy + recreate.
  lifecycle {
    ignore_changes = [compartment_id]
  }
}

resource "oci_containerengine_node_pool" "workbench" {
  cluster_id         = oci_containerengine_cluster.workbench.id
  compartment_id     = var.compartment_ocid
  kubernetes_version = var.k8s_version
  name               = "${local.name}-pool-default"

  node_shape = var.node_pool_shape
  node_shape_config {
    ocpus         = var.node_pool_ocpus
    memory_in_gbs = var.node_pool_memory_gb
  }

  node_source_details {
    source_type             = "IMAGE"
    image_id                = var.node_pool_image_id
    boot_volume_size_in_gbs = 50
  }

  node_config_details {
    size = var.node_pool_size
    placement_configs {
      availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
      # Dedicated workers subnet — must be different from the LB subnet
      # listed in `options.service_lb_subnet_ids`. OCI rejects subnets
      # that appear in both with "service subnets cannot be used by
      # node pools".
      subnet_id = oci_core_subnet.workers.id
    }
    nsg_ids = [oci_core_network_security_group.workers.id]
    node_pool_pod_network_option_details {
      cni_type       = "OCI_VCN_IP_NATIVE"
      pod_subnet_ids = [oci_core_subnet.pods.id]
    }
  }

  freeform_tags = local.common_tags

  lifecycle {
    ignore_changes = [compartment_id]
  }
}
