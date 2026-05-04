# Locus workbench — single-image build of the three-tier playground.
#
# Layout (mirrors optic + webapp Dockerfiles in observai):
#   • Oracle Linux 9-slim base, microdnf for installs.
#   • Python 3.12 hosts the FastAPI runner (sandbox/backend).
#   • Node 20 runs the Express BFF (sandbox/bff) and Vite UI (sandbox/web).
#   • All three tiers boot via one CMD; the container exposes 5173/3101/8100.
#
# Build (from repo root):
#   docker build -t locus-workbench -f sandbox/Dockerfile .
#
# Run (BYO model key — paste it in the UI's Provider settings):
#   docker run --rm -p 5173:5173 -p 3101:3101 -p 8100:8100 locus-workbench
#   open http://localhost:5173

FROM container-registry.oracle.com/os/oraclelinux:9-slim

ARG http_proxy
ARG https_proxy
ARG no_proxy
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

WORKDIR /app

# Toolchain + Python 3.12 + Node 20.
RUN microdnf install -y \
        gcc gcc-c++ make \
        wget tar gzip xz findutils \
        openssl-devel bzip2-devel libffi-devel \
        zlib-devel readline-devel sqlite-devel \
        xz-devel ncurses-devel \
        python3.12 python3.12-pip \
    && microdnf module enable nodejs:20 -y \
    && microdnf install -y nodejs \
    && microdnf clean all

# Install locus via hatch wheel (same pattern optic uses), then drop hatch.
COPY pyproject.toml README.md /app/
COPY src/ /app/src/
RUN python3.12 -m pip install --no-cache-dir hatch \
    && hatch build -t wheel \
    && python3.12 -m pip install --no-cache-dir ./dist/*.whl \
    && rm -rf dist build *.egg-info \
    && python3.12 -m pip uninstall -y hatch

# Workbench source. .dockerignore keeps node_modules / dist / .vite out
# of the COPY context so we install fresh inside the image.
COPY sandbox/ /app/sandbox/

# Node dependency install for both BFF and web.
RUN cd sandbox/bff && npm ci --no-audit --no-fund \
    && cd ../web   && npm ci --no-audit --no-fund

EXPOSE 5173 3101 8100

# Entrypoint runs all three tiers and blocks on `wait`. Container exits
# when any of the three dies, surfacing failures to `docker logs`.
# Hosts are bound to 0.0.0.0 so the published ports are reachable from
# outside the container.
CMD ["bash", "-c", "\
set -e; \
python3.12 -m uvicorn --app-dir sandbox/backend runner:app --host 0.0.0.0 --port 8100 & \
( cd sandbox/bff && npm run dev ) & \
( cd sandbox/web && npx vite --host 0.0.0.0 --port 5173 ) & \
wait -n"]
