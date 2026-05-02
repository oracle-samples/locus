# locus-agent Helm chart

Deploys a [locus](https://github.com/oracle-samples/locus) `AgentServer`
on Kubernetes / OKE. Wraps any `locus.Agent` in a FastAPI app exposing
`/invoke`, `/stream` (SSE), `/threads/{id}`, and `/health`.

## Quick start

```bash
helm install locus-agent ./deploy/helm/locus-agent \
  --set image.repository=ghcr.io/your-org/locus-agent \
  --set image.tag=v0.1.0 \
  --set auth.apiKey=$(openssl rand -hex 16) \
  --set ociBucket.enabled=true \
  --set ociBucket.bucketName=locus-threads \
  --set ociBucket.namespace=<your-tenancy-namespace>
```

## Values

See `values.yaml` for the full set. Notable knobs:

| Key | Default | Purpose |
|---|---|---|
| `replicaCount` | `2` | Replicas (scale via HPA when enabled). |
| `auth.apiKey` | `""` | Bearer-token API key. Use `auth.existingSecret` instead in prod. |
| `serviceAccount.annotations` | `{}` | Add OCI workload-identity annotations here. |
| `probes.liveness.path` | `/health` | Liveness endpoint. |
| `ociBucket.enabled` | `false` | Wire OCI Object Storage as the checkpointer backend. |
| `autoscaling.enabled` | `false` | Render an HPA. |
| `ingress.enabled` | `false` | Render an Ingress. |

## Auth

The chart expects a bearer-token secret named in
`auth.existingSecret` or auto-created from `auth.apiKey`. The
container reads it from `LOCUS_SERVER_API_KEY` and passes it to
`AgentServer(api_key=...)`. Per-principal thread namespacing is
enforced server-side — two API keys can't read each other's threads.

## OCI workload identity

Preferred over static `apiKey`: enable workload identity on the OKE
node pool, then add the IAM role annotation to the chart's service
account:

```yaml
serviceAccount:
  annotations:
    workload.identity.oci.oraclecloud.com/role: arn:oci:...
```

The `OCIBucketBackend` will pick up `instance_principal` /
`resource_principal` automatically — no static credentials needed.

## What you still own

- The `app.py` module the container runs (see the `Dockerfile`'s `CMD`).
  This is where you instantiate your `Agent` + `AgentServer`.
- The image build + registry push.
- Network policy, monitoring (Prometheus scrape configs, Grafana
  dashboards), and observability (OTLP exporter env vars).

## See also

- [`docs/how-to/deploy.md`](../../../docs/how-to/deploy.md) — full
  deployment walkthrough.
- [`docs/concepts/server.md`](../../../docs/concepts/server.md) —
  the `AgentServer` API.
