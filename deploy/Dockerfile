# Offline audit runner: rebuilds workpapers, management letter and figures from the committed,
# hash-verified evidence bundles. No lab, network or credentials needed.
#   docker build -f deploy/Dockerfile -t itgc-audit-lab .
#   docker run --rm -v "$PWD/out:/app/out" itgc-audit-lab
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY audit ./audit
COPY lab/seed ./lab/seed
COPY tests ./tests
RUN pip install --no-cache-dir --no-deps -e .
CMD ["sh", "-c", "python -m itgc verify audit/evidence/fy26-baseline && python -m itgc audit --out out/fy26-baseline --no-figures && python -m pytest -q"]
