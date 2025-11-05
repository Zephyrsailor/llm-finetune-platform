DOCKER_COMPOSE ?= docker compose
COMPOSE_FILE ?= docker/docker-compose.yml

.PHONY: build up down logs ps backend-shell db-shell

build:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) build

up:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) up -d

down:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) down --remove-orphans

logs:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) logs -f

ps:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) ps

backend-shell:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) exec backend bash

db-shell:
	$(DOCKER_COMPOSE) -f $(COMPOSE_FILE) exec db psql -U llmft -d llmft
