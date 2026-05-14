# locus-workbench — full free-tier deploy on OCI Always-Free OKE.
#
# One-shot from a clean tenancy:
#   1. cp terraform/terraform.tfvars.example terraform/terraform.tfvars
#      then fill in tenancy_ocid + compartment_ocid + node_pool_image_id
#   2. make tf-apply       (provisions VCN + OKE + OCIR repo)
#   3. make kubeconfig     (writes ~/.kube/locus-workbench.kubeconfig)
#   4. make ocir-login     (paste an auth token from the OCI Console)
#   5. make docker-push    (builds + pushes the workbench image)
#   6. make ocir-secret    (creates the pull secret in the cluster)
#   7. make helm-install   (deploys the chart)
#   8. make url            (prints the public IP — open in a browser)
#
# Tear down with `make destroy` when done.

SHELL := /usr/bin/env bash

# === Where things live =======================================================
REPO_ROOT       := $(abspath ../..)
TF_DIR          := terraform
HELM_DIR        := helm/locus-workbench
KUBECONFIG_PATH := $(HOME)/.kube/locus-workbench.kubeconfig
RELEASE_NAME    := locus-workbench
NAMESPACE       := default

# === Helpers — let make discover terraform outputs lazily ====================
TF_OUTPUT := cd $(TF_DIR) && terraform output -raw
CLUSTER_ID = $(shell $(TF_OUTPUT) cluster_id 2>/dev/null)
OCIR_REF   = $(shell $(TF_OUTPUT) ocir_image_ref 2>/dev/null)
OCIR_NS    = $(shell $(TF_OUTPUT) ocir_namespace 2>/dev/null)
KUBE_CMD   = $(shell $(TF_OUTPUT) kubeconfig_command 2>/dev/null)
KUBECTL    := kubectl --kubeconfig $(KUBECONFIG_PATH) --namespace $(NAMESPACE)
IMAGE_TAG  ?= 0.2.0b9

# === Terraform ===============================================================

.PHONY: tf-init
tf-init:
	cd $(TF_DIR) && terraform init

.PHONY: tf-plan
tf-plan: tf-init
	cd $(TF_DIR) && terraform plan -out=tfplan

.PHONY: tf-apply
tf-apply: tf-init
	cd $(TF_DIR) && terraform apply -auto-approve

.PHONY: tf-output
tf-output:
	cd $(TF_DIR) && terraform output

.PHONY: destroy
destroy:
	@echo "WARNING: this destroys the OKE cluster, VCN, and OCIR repo."
	@read -p "Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
	-helm uninstall $(RELEASE_NAME) --kubeconfig $(KUBECONFIG_PATH) --namespace $(NAMESPACE) || true
	cd $(TF_DIR) && terraform destroy -auto-approve

# === kubeconfig ==============================================================

.PHONY: kubeconfig
kubeconfig:
	mkdir -p $(HOME)/.kube
	@echo "Running: $(KUBE_CMD)"
	@$(KUBE_CMD)
	@echo "Wrote $(KUBECONFIG_PATH)"
	@$(KUBECTL) get nodes

# === OCIR / Docker ===========================================================

# OCIR auth uses your OCI username + an auth token (NOT the password).
# Generate the token at OCI Console → User → Auth Tokens.
.PHONY: ocir-login
ocir-login:
	@echo "OCIR namespace: $(OCIR_NS)"
	@echo "When prompted, username is '<namespace>/<your-oci-username>'."
	@echo "Password is an Auth Token from User → Auth Tokens (NOT your console password)."
	docker login $$(echo $(OCIR_REF) | cut -d/ -f1)

.PHONY: docker-build
docker-build:
	docker build \
	  -t $(OCIR_REF):$(IMAGE_TAG) \
	  -t $(OCIR_REF):latest \
	  -f $(REPO_ROOT)/workbench/Dockerfile \
	  $(REPO_ROOT)

.PHONY: docker-push
docker-push: docker-build
	docker push $(OCIR_REF):$(IMAGE_TAG)
	docker push $(OCIR_REF):latest

# === Cluster secrets =========================================================

# Creates the pull secret the Deployment references. Reuses the
# docker login credentials in ~/.docker/config.json.
.PHONY: ocir-secret
ocir-secret:
	$(KUBECTL) delete secret ocir-pull-secret --ignore-not-found
	$(KUBECTL) create secret generic ocir-pull-secret \
	  --from-file=.dockerconfigjson=$(HOME)/.docker/config.json \
	  --type=kubernetes.io/dockerconfigjson

# Optional: bake API keys into a secret the Helm chart can mount.
# Override OPENAI_API_KEY / ANTHROPIC_API_KEY in your shell first.
.PHONY: api-keys-secret
api-keys-secret:
	$(KUBECTL) delete secret locus-workbench-keys --ignore-not-found
	$(KUBECTL) create secret generic locus-workbench-keys \
	  $(if $(OPENAI_API_KEY),--from-literal=OPENAI_API_KEY=$(OPENAI_API_KEY)) \
	  $(if $(ANTHROPIC_API_KEY),--from-literal=ANTHROPIC_API_KEY=$(ANTHROPIC_API_KEY))

# === Helm ====================================================================

.PHONY: helm-install
helm-install:
	helm upgrade --install $(RELEASE_NAME) $(HELM_DIR) \
	  --kubeconfig $(KUBECONFIG_PATH) \
	  --namespace $(NAMESPACE) \
	  --set image.repository=$(OCIR_REF) \
	  --set image.tag=$(IMAGE_TAG) \
	  --wait --timeout=10m

.PHONY: helm-uninstall
helm-uninstall:
	helm uninstall $(RELEASE_NAME) \
	  --kubeconfig $(KUBECONFIG_PATH) --namespace $(NAMESPACE)

# === Inspection ==============================================================

.PHONY: status
status:
	@echo "--- Nodes ---"
	@$(KUBECTL) get nodes
	@echo "--- Pods ---"
	@$(KUBECTL) get pods -l app.kubernetes.io/name=locus-workbench
	@echo "--- Service ---"
	@$(KUBECTL) get svc -l app.kubernetes.io/name=locus-workbench

.PHONY: logs
logs:
	$(KUBECTL) logs -l app.kubernetes.io/name=locus-workbench --tail=200 -f

.PHONY: url
url:
	@ip=$$($(KUBECTL) get svc $(RELEASE_NAME) -o jsonpath='{.status.loadBalancer.ingress[0].ip}'); \
	if [ -z "$$ip" ]; then \
	  echo "LoadBalancer not ready yet — re-run in a minute."; \
	  $(KUBECTL) describe svc $(RELEASE_NAME) | tail -20; \
	else \
	  echo "http://$$ip"; \
	fi

# === One-shot deploy (after Terraform + Docker login) ========================

.PHONY: deploy
deploy: kubeconfig docker-push ocir-secret helm-install
	@$(MAKE) --no-print-directory url
