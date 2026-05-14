# How-to: Deploy the workbench on OCI Always-Free OKE

Stand up the workbench as a Kubernetes pod inside your OCI
Always-Free tenancy in ~15 minutes. Single ARM A1.Flex worker, free
Flex 10 Mbps load balancer, free OCIR repository. Everything stays
within the Always-Free envelope so you pay $0/month.

## What you'll have when this is done

```text
Internet
  │
  ▼
Flex 10 Mbps LoadBalancer (free)
  │
  ▼ port 80 → 5173
ARM A1.Flex worker node (2 OCPU, 12 GB, free)
  └── pod: locus-workbench-<hash>
      ├── tier 1 : Vite dev server      :5173 ← public
      ├── tier 2 : Express BFF          :3101 ← internal
      └── tier 3 : FastAPI runner       :8100 ← internal
```

One Deployment, one Service, one image — the workbench's existing
`Dockerfile` already bundles all three tiers into a single CMD.

## Prerequisites

- An OCI tenancy with the **Always-Free** allocation available
  (4 ARM OCPU + 24 GB RAM unspent, one Flex LB free, one OKE cluster free).
- `terraform` (≥ 1.6), `kubectl`, `helm`, `docker`, and `oci` CLI on
  your laptop.
- An OCI config profile pointing at the free tenancy. The repo's
  Makefile defaults to `~/.oci/config` profile `API_FREE_TIER`.
- An OCI Auth Token for OCIR — generate at
  *User → Auth Tokens → Generate Token* in the Console.

## Stack contents

| Path | What it provisions |
|---|---|
| [`deploy/locus-workbench/terraform/`](https://github.com/oracle-samples/locus/tree/main/deploy/locus-workbench/terraform) | VCN (`10.42.0.0/16`), IGW, public + pod subnets, NSGs for OKE API and workers, BASIC OKE cluster, ARM A1.Flex node pool, OCIR repo |
| [`deploy/locus-workbench/helm/locus-workbench/`](https://github.com/oracle-samples/locus/tree/main/deploy/locus-workbench/helm/locus-workbench) | Deployment (one container, all three tiers), LoadBalancer Service annotated for Flex 10 Mbps, ServiceAccount, optional Ingress |
| [`deploy/locus-workbench/Makefile`](https://github.com/oracle-samples/locus/tree/main/deploy/locus-workbench/Makefile) | `tf-apply`, `kubeconfig`, `ocir-login`, `docker-push`, `ocir-secret`, `helm-install`, `url`, `destroy` |

## Step 1 — Fill in the two OCIDs

```bash
cd deploy/locus-workbench
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform/terraform.tfvars` and replace the placeholders:

- `tenancy_ocid` — your Free-Tier tenancy OCID
- `compartment_ocid` — same as tenancy for the simplest setup (no
  IAM policy required), or a dedicated compartment if you want to
  scope billing
- `node_pool_image_id` — Oracle Linux 8 ARM image OCID for the
  current OKE version. Pull it with:

```bash
oci ce node-pool-options get --node-pool-option-id all \
  --profile API_FREE_TIER --region ca-toronto-1 \
  --query 'data.sources[?contains("source-name", `OKE-1.31`) && contains("source-name", `aarch64`)] | [0]."image-id"' \
  --raw-output
```

## Step 2 — Provision the cluster

```bash
make tf-apply
```

Takes ~10 minutes on a clean tenancy. When done:

```bash
make tf-output
# Lists cluster_id, ocir_image_ref, ocir_namespace, vcn_id.
```

## Step 3 — Wire kubectl

```bash
make kubeconfig
```

Writes `~/.kube/locus-workbench.kubeconfig` and prints the node
list to confirm the API endpoint is reachable.

## Step 4 — Push the image to OCIR

```bash
make ocir-login
# Prompts for username and password:
#   username: <ocir_namespace>/<your-oci-username>
#   password: the Auth Token from Step 0 (NOT your console password)

make docker-push
# Builds workbench/Dockerfile, tags it as
# <region>.ocir.io/<namespace>/locus-workbench:0.2.0b9, pushes both
# the version tag and `latest`.
```

First build is ~5 minutes (~1.3 GB image). Subsequent pushes only
ship changed layers.

## Step 5 — Deploy the Helm chart

```bash
make ocir-secret      # creates the cluster-side image-pull secret
make helm-install     # rolls out the Deployment + LoadBalancer
```

`helm-install` runs `--wait --timeout=10m`, so it blocks until the
pod is Ready.

## Step 6 — Open it

```bash
make url
# http://203.0.113.42
```

Hit that URL in your browser. The workbench lands on the Tutorials
tab. Click **Provider settings** in the header, paste an OpenAI or
Anthropic key (or your free-tier OCI profile), pick a tutorial, hit
Run.

## Iterating

```bash
# After changing anything under workbench/ on your laptop:
make docker-push                    # rebuilds + pushes
make IMAGE_TAG=0.2.0b10 deploy      # rolls the cluster onto the new tag
make logs                           # tail the pod
```

## Tearing it all down

```bash
make destroy
```

Type `yes` at the confirm prompt. Removes the Helm release first,
then `terraform destroy` removes the cluster, node pool, OCIR repo,
VCN, and all subnets. State file stays in
`terraform/terraform.tfstate` until you delete it.

## Cost

| Resource | Free allowance | This stack uses | $/month |
|---|---|---|---|
| OKE BASIC cluster control plane | 1 cluster | 1 | $0 |
| Worker compute (ARM A1.Flex) | 4 OCPU + 24 GB | 2 OCPU + 12 GB | $0 |
| Flex 10 Mbps load balancer | 1 | 1 | $0 |
| OCIR storage | 1 GB | ~600 MB | $0 |
| Egress | 10 TB | well under | $0 |

The Terraform stack pins every billable knob to the Always-Free
allocation. The Helm chart annotates the Service with
`oci-load-balancer-shape-flex-min: 10` and `-max: 10` so the LB
stays on the free shape — without those annotations the OCI CCM
silently provisions a paid Flex LB.

## Troubleshooting

| Symptom | Cause + fix |
|---|---|
| `terraform apply` fails at `oci_containerengine_cluster` with "ServiceLimitExceeded" | You already have an OKE cluster. Delete it or pick a different tenancy. |
| `make docker-push` returns "denied: requested access to the resource is denied" | OCIR Auth Token expired or wrong username format. Re-run `make ocir-login` with `<namespace>/<oci-username>`. |
| Pod stuck in `ImagePullBackOff` | The pull secret references the wrong registry. Re-run `make ocir-secret` after `make ocir-login`. |
| LoadBalancer Service stays at `<pending>` IP | Free-tier Flex LB quota exhausted (1 per region). Delete an old LB or wait. |
| Workbench UI loads but `/api/*` calls return 502 | Backend tier crashed inside the pod. `make logs` to read uvicorn's traceback. |

## See also

- [Workbench guide](../workbench.md) — every pattern + tab the UI ships with
- [Cognitive routing pattern](../workbench.md#cognitive-routing-pattern) — the new opt-in LLM picker toggle, live in this deploy
