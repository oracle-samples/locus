# `locus-workbench` — Always-Free OKE deployment

Terraform stack + Helm chart that puts the locus workbench on a
managed Kubernetes pod inside your OCI Always-Free tenancy. Single
ARM A1.Flex worker, free Flex 10 Mbps load balancer, free OCIR
repository. Nothing in this stack bills outside the Always-Free
envelope.

## Layout

| Path | What it does |
|---|---|
| `cimientos/terraform/` | VCN + IGW + 2 subnets + NSGs + BASIC OKE cluster + ARM node pool + OCIR repo |
| `helm/locus-workbench/` | Single-pod Deployment running all three workbench tiers, plus LoadBalancer Service |
| `Makefile` | One-shot targets — `tf-apply`, `kubeconfig`, `docker-push`, `helm-install`, `url`, `destroy` |

## One-shot deploy

```bash
cd deploy/locus-workbench

# 1. Fill in the two required OCIDs (tenancy + compartment) +
#    the worker image OCID.
cp cimientos/terraform/terraform.tfvars.example cimientos/terraform/terraform.tfvars
$EDITOR cimientos/terraform/terraform.tfvars

# 2. Provision the network + cluster + registry (~10 min on first apply).
make tf-apply

# 3. Wire kubectl to the new cluster.
make kubeconfig

# 4. Log in to OCIR (paste an Auth Token, not your console password).
make ocir-login

# 5. Build + push the workbench image + deploy.
make deploy
```

`make deploy` runs `docker-push → ocir-secret → helm-install` end
to end. When it finishes, `make url` prints the public URL.

## What you pay

| Resource | Free-tier allowance | This stack uses |
|---|---|---|
| OKE BASIC cluster (control plane) | 1 cluster, free | 1 cluster |
| Worker compute (ARM A1.Flex) | 4 OCPU + 24 GB total | 2 OCPU + 12 GB |
| Flex 10 Mbps load balancer | 1, free | 1 |
| OCIR storage | 1 GB | ~600 MB (workbench image) |
| Egress | 10 TB/month | well under |

Everything bills **$0** as long as you stay on the Always-Free
allocation. The Terraform stack only provisions Always-Free SKUs by
default; override only if you intentionally want to pay.

## Iterating on the workbench

```bash
# After changing workbench/ source:
make docker-push                # rebuild + push a new image tag
$(MAKE) IMAGE_TAG=0.2.0b10 deploy  # roll the cluster onto the new tag
```

## Tearing it all down

```bash
make destroy
```

Confirms with a `yes` prompt, then removes the Helm release, OKE
cluster, node pool, OCIR repo, VCN, and all subnets. State file
stays in `cimientos/terraform/terraform.tfstate` until you delete it.

## Further reading

- [Deploy how-to with full walkthrough](../../docs/how-to/deploy-workbench-free-tier.md)
- [Workbench guide](../../docs/workbench.md)
- [Reference infrastructure pattern](<https://github.com/fede-kamel/the> team's production) — production-grade equivalent this stack borrows from
