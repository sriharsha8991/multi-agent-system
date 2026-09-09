# Multi-Agent Industrial Asset Analytics — data layer.
# Reviewer path (Docker only):  make up && make seed && make validate
#
# All Python runs inside the `app` container so no host Python is required.
# For host-based development instead, see README (pip install -e . and run
# `python scripts/<name>.py` against the exposed DB ports).

COMPOSE := docker compose
RUN     := $(COMPOSE) run --rm app python

.PHONY: help up down seed init validate data-dict test shell logs clean

help:
	@echo "Targets:"
	@echo "  up         Build the app image and start postgres + neo4j"
	@echo "  seed       Spin up schemas, then populate both databases"
	@echo "  validate   Run the 22 quality gates (fails on any red)"
	@echo "  data-dict  Regenerate docs/03-data-dictionary.md from sensor_catalog"
	@echo "  test       Run the pytest suite"
	@echo "  down       Stop and remove containers"
	@echo "  clean      down + remove data volumes (destroys seeded data)"

# Create .env from the template on first use so compose has values to read.
.env:
	cp .env.example .env

up: .env
	$(COMPOSE) up -d --build postgres neo4j
	$(COMPOSE) build app

init: .env
	$(RUN) scripts/init_databases.py

seed: .env
	$(RUN) scripts/init_databases.py
	$(RUN) scripts/seed_all.py

validate: .env
	$(RUN) scripts/validate.py

data-dict: .env
	$(RUN) scripts/gen_data_dictionary.py

test: .env
	$(COMPOSE) run --rm app pytest -q

shell: .env
	$(COMPOSE) run --rm app bash

logs:
	$(COMPOSE) logs -f postgres neo4j

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v
