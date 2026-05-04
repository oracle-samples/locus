# locus sandbox — full stack: locus python A2A peers, Node BFF, vanilla TS web,
# Playwright e2e. Each `make` target runs in the foreground so you can chain
# them across panes / terminals.

.PHONY: install backend-research backend-finance bff web e2e clean

# === Backend (locus python A2A peers) ========================================
# Reuses the merged a2a-mesh project under examples/projects/a2a-mesh/src.
# Pass LOCUS_MODEL_PROVIDER=oci + the BOAT-OC1 env block from your shell to
# run against real OCI GenAI; defaults to MockModel.
BACKEND_PYTHONPATH = ../examples/projects/a2a-mesh/src:../examples:../src
RESEARCH_PORT ?= 8001
FINANCE_PORT  ?= 8012

backend-research:
	cd .. && PYTHONPATH=$(BACKEND_PYTHONPATH:..%=%) hatch -e default run python -m a2a_mesh.research --port $(RESEARCH_PORT)

backend-finance:
	cd .. && PYTHONPATH=$(BACKEND_PYTHONPATH:..%=%) hatch -e default run python -m a2a_mesh.finance --port $(FINANCE_PORT)

# === BFF (Node Express) =====================================================
bff:
	cd bff && npm run dev

# === Web (vanilla TypeScript via Vite) ======================================
web:
	cd web && npm run dev

# === E2E (Playwright) =======================================================
e2e:
	cd e2e && npm test

install:
	cd bff && npm install
	cd web && npm install
	cd e2e && npm install && npx playwright install chromium

clean:
	rm -rf bff/node_modules bff/dist web/node_modules web/dist e2e/node_modules e2e/test-results
