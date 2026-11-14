.PHONY: up down test reset

up:
	docker compose up -d --build

down:
	docker compose down

test:
	cd analyzer && python3 -m pytest -q

reset:
	curl -s -X DELETE localhost:8025/api/v1/messages > /dev/null
	curl -s -X DELETE localhost:8000/blocklist/secure-login.corp-verify.test > /dev/null || true
