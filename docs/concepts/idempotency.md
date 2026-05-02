# Idempotency

The single most important word in production agents is **once**. The
model is allowed to retry; the side-effect isn't. locus makes that a
one-keyword decision on the tool.

```python
from locus.tools.decorator import tool

@tool(idempotent=True)
def transfer(from_acct: str, to_acct: str, amount: float) -> dict:
    """Transfer funds. Re-fires within a run return the cached receipt."""
    return ledger.transfer(from_acct, to_acct, amount)
```

Inside a single agent run, locus hashes the tool's `(name, kwargs)`
tuple. The first call hits the body and the result is cached. Every
subsequent call with identical arguments — whether the model retried,
got confused, or asked again on a later turn — short-circuits to the
cached response.

## Why this matters

- **Booking, billing, payments.** The model that calls `book_flight`
  twice is more common than you think. Without idempotency you have a
  duplicate charge and an angry customer.
- **Outbound side-effects.** `email_cfo`, `page_oncall`, `submit_po` —
  one and done.
- **Database writes you can't easily roll back.**

The argument hash is the trust boundary: if the model re-issues the
*same* call, you fire once. If it changes any argument, that's a new
call and the body runs.

## When to use it

| Situation | `idempotent=True`? |
|---|---|
| Side-effecting tool with a real-world cost (charge, email, page) | **yes** |
| Read-only catalogue lookup | no — caching the model's reads is its problem, not yours |
| Tool that *intentionally* generates a new entity each call (e.g. `mint_uuid`) | no |
| External service that's already idempotent | yes anyway — locus dedupes the round-trip too |

## What it is not

- It's not idempotency *across runs*. Restart the agent and the cache
  is gone — that's what your **checkpointer** is for.
- It's not retry. If the body raises, the exception propagates.
- It's not a network-layer cache. Two different agents calling
  `transfer(a, b, 100)` each fire once.

## Source and tutorials

- `src/locus/tools/decorator.py` — the `@tool` decorator and idempotency hook.
- Tutorial: [`tutorial_03_tools_and_state.py`](https://github.com/oracle-samples/locus/blob/main/examples/tutorial_03_tools_and_state.py)
  walks through `@tool(idempotent=True)` end-to-end.
