locals {
  name = var.name_prefix
  common_tags = {
    "Project"    = "locus-workbench"
    "ManagedBy"  = "terraform"
    "FreeTier"   = "true"
    "DeployedAt" = timestamp()
  }
  # Strip "ca-toronto-1" → "tor1" etc. for VCN DNS labels (max 15
  # chars, alphanum only).
  region_suffix = lower(replace(replace(var.region, "-", ""), "[^a-z0-9]", ""))
}
