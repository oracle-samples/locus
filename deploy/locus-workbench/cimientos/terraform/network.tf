# Minimal VCN for the workbench: one public subnet that hosts both
# the workers (so kubelet can reach the public OKE API endpoint
# without a NAT hop) and the LoadBalancer service. Free-tier
# topology — no NAT GW, no private subnet. Production deployments
# should use a NAT GW with workers in a private subnet for a tighter blast radius.

resource "oci_core_vcn" "workbench" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "${local.name}-vcn"
  dns_label      = "lwb${local.region_suffix}"
  freeform_tags  = local.common_tags
}

resource "oci_core_internet_gateway" "workbench" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.workbench.id
  display_name   = "${local.name}-igw"
  enabled        = true
  freeform_tags  = local.common_tags
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.workbench.id
  display_name   = "${local.name}-rt-public"
  route_rules {
    network_entity_id = oci_core_internet_gateway.workbench.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
  freeform_tags = local.common_tags
}

# Workers + LoadBalancer share one /24 — fine for a single-node
# free-tier cluster. The OKE control plane is fully managed; it
# doesn't consume an IP in this VCN.
resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.workbench.id
  cidr_block                 = "10.42.0.0/24"
  display_name               = "${local.name}-subnet-public"
  dns_label                  = "pub"
  route_table_id             = oci_core_route_table.public.id
  prohibit_public_ip_on_vnic = false
  freeform_tags              = local.common_tags
}

# Pod CNI subnet — pods get IPs from here under OCI_VCN_IP_NATIVE.
resource "oci_core_subnet" "pods" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.workbench.id
  cidr_block                 = "10.42.1.0/24"
  display_name               = "${local.name}-subnet-pods"
  dns_label                  = "pods"
  route_table_id             = oci_core_route_table.public.id
  prohibit_public_ip_on_vnic = true
  freeform_tags              = local.common_tags
}

# Dedicated worker-node subnet — kept separate from the LB subnet
# because OCI rejects the same subnet appearing in both
# `service_lb_subnet_ids` and node_pool placement_configs ("service
# subnets cannot be used by node pools"). Workers are public so the
# kubelet can reach the OKE API endpoint without a NAT hop.
resource "oci_core_subnet" "workers" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.workbench.id
  cidr_block                 = "10.42.2.0/24"
  display_name               = "${local.name}-subnet-workers"
  dns_label                  = "workers"
  route_table_id             = oci_core_route_table.public.id
  prohibit_public_ip_on_vnic = false
  freeform_tags              = local.common_tags
}

# -------------------------------------------------------------------
# Network Security Groups — minimal allow-lists. Tight by default;
# loosen only when the workbench needs to expose more than :5173.
# -------------------------------------------------------------------

resource "oci_core_network_security_group" "oke_api" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.workbench.id
  display_name   = "${local.name}-nsg-oke-api"
  freeform_tags  = local.common_tags
}

resource "oci_core_network_security_group_security_rule" "oke_api_ingress" {
  network_security_group_id = oci_core_network_security_group.oke_api.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"
  tcp_options {
    destination_port_range {
      min = 6443
      max = 6443
    }
  }
}

resource "oci_core_network_security_group" "workers" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.workbench.id
  display_name   = "${local.name}-nsg-workers"
  freeform_tags  = local.common_tags
}

# Workers: full egress.
resource "oci_core_network_security_group_security_rule" "workers_egress" {
  network_security_group_id = oci_core_network_security_group.workers.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
}

# Workers: allow LB → NodePort range so the OCI LB service can
# health-check + forward to the workbench container's port 5173.
resource "oci_core_network_security_group_security_rule" "workers_nodeport_ingress" {
  network_security_group_id = oci_core_network_security_group.workers.id
  direction                 = "INGRESS"
  protocol                  = "6"            # TCP
  source                    = "10.42.0.0/24" # public subnet (LB lives here)
  source_type               = "CIDR_BLOCK"
  tcp_options {
    destination_port_range {
      min = 30000
      max = 32767
    }
  }
}

# Workers: pod CNI requires intra-VCN reachability.
resource "oci_core_network_security_group_security_rule" "workers_vcn_ingress" {
  network_security_group_id = oci_core_network_security_group.workers.id
  direction                 = "INGRESS"
  protocol                  = "all"
  source                    = var.vcn_cidr
  source_type               = "CIDR_BLOCK"
}

# SSH for emergency debugging. Tighten the source CIDR to your
# office IP if you don't want the world knocking on port 22.
resource "oci_core_network_security_group_security_rule" "workers_ssh_ingress" {
  network_security_group_id = oci_core_network_security_group.workers.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"
  tcp_options {
    destination_port_range {
      min = 22
      max = 22
    }
  }
}

# Workers: TCP 10250 ingress from anywhere — the OKE control plane
# reaches back to the kubelet on this port for node registration,
# `kubectl logs`, `kubectl exec`, metrics. Without this rule the
# node never moves to Ready and node-pool create eventually fails
# with "1 nodes(s) register timeout". OKE's control plane lives on
# Oracle's network (not in the VCN), so the source must be 0.0.0.0/0
# — restricting to the VCN CIDR breaks registration. This matches the
# OCI-recommended OKE worker NSG topology.
resource "oci_core_network_security_group_security_rule" "workers_kubelet_ingress" {
  network_security_group_id = oci_core_network_security_group.workers.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"
  tcp_options {
    destination_port_range {
      min = 10250
      max = 10250
    }
  }
}

# Workers: ICMP type 3 code 4 — Path MTU Discovery (Fragmentation
# Needed). Without this PMTUD breaks and large packets get black-
# holed. Standard OKE worker-NSG requirement.
resource "oci_core_network_security_group_security_rule" "workers_pmtud_ingress" {
  network_security_group_id = oci_core_network_security_group.workers.id
  direction                 = "INGRESS"
  protocol                  = "1" # ICMP
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"
  icmp_options {
    type = 3
    code = 4
  }
}
