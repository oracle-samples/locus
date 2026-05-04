# Tutorial 40: OCI Dedicated AI Cluster (DAC) endpoints

This tutorial covers locus's DAC support. A DAC is OCI's
provisioned-capacity serving mode for OCI GenAI: instead of pay-per-token
inference against a shared model id, you address a dedicated endpoint
by its OCID (``ocid1.generativeaiendpoint.oc1.<region>....``) and
inference is routed to your cluster.

Locus auto-detects DAC OCIDs and routes them through the SDK
transport (``OCIModel``) — the V1 OpenAI-compatible transport can't
speak ``DedicatedServingMode``. Both non-streaming ``complete()`` and
real SSE ``stream()`` work end-to-end against a DAC.

This tutorial covers:

- Part 1: how DAC routing is decided (``ocid1.generativeaiendpoint.``
  prefix → ``OCIModel``).
- Part 2: configure an ``Agent`` against a DAC endpoint.
- Part 3: drive ``complete()`` against the DAC with one prompt.
- Part 4: drive ``stream()`` and watch SSE deltas come back.
- Part 5: wire the DAC into a tool-using ``Agent`` so the model sitting
  on dedicated capacity can call your @tool functions.

Prerequisites:

- ``oci`` SDK installed (``pip install -e ".[oci]"``).
- An OCI profile with permission to invoke the DAC endpoint.
- The DAC endpoint OCID, the compartment OCID, and the region.

Set these env vars (kept out of the source so the tutorial works for
any DAC):

  export OCI_DAC_ENDPOINT_OCID=ocid1.generativeaiendpoint.oc1.uk-london-1....
  export OCI_DAC_COMPARTMENT_ID=ocid1.compartment.oc1....
  export OCI_DAC_REGION=uk-london-1
  export OCI_PROFILE=MY_DAC_PROFILE

Without those env vars Parts 2-5 print the wiring snippet and skip.

Difficulty: Intermediate

## Source

```python
--8<-- "examples/tutorial_40_oci_dac.py"
```
