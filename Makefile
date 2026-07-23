.PHONY: setup install run docker

# Full setup på ny dator: venv + CLI-verktyg + Python-paket
setup:
	python3 -m venv .venv && \
	.venv/bin/pip install -q -e "agents/[all]" && \
	.venv/bin/python3 agents/harness.py setup

# Minimal setup (bara bas)
setup-minimal:
	python3 -m venv .venv && \
	.venv/bin/pip install -q -e agents/ && \
	.venv/bin/python3 agents/harness.py setup

# Installera valfria extra-paket (crawler, memory, mcp, tracer, file)
setup-extra:
	.venv/bin/pip install -q -e "agents/[all]"
	@echo "✅ Extra-paket installerade: crawl4ai, chromadb, mcp, langfuse, PyMuPDF, python-docx"

# Installera dependencies för alla agenter
install:
	.venv/bin/python3 agents/harness.py install

# Starta dashboard (utveckling)
run:
	.venv/bin/python3 agents/dashboard/app.py

# Starta overlord (utveckling)
overlord:
	.venv/bin/python3 agents/.overlord/overlord.py

# Docker: bygg och starta
docker:
	docker compose up --build

# Diagnos
doctor:
	.venv/bin/python3 agents/harness.py doctor

# Tester
test:
	.venv/bin/python3 -m pytest agents/tests/ -v
