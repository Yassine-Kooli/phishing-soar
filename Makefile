.PHONY: up down test reset scenario evaluate

up:
	docker compose up -d --build

down:
	docker compose down

# runs in the analyzer image: no Python test setup needed on the host
test:
	docker run --rm -v "$(CURDIR)/analyzer:/src" -w /src phish-soar-analyzer \
	  sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"

# one replayable run: approve | reject | timeout (timeout takes 10 minutes)
scenario:
	set -a; . ./.env; set +a; python3 demo/scenario.py --decision approve

evaluate:
	set -a; . ./.env; set +a; python3 eval/evaluate.py --runs 5

reset:
	curl -s -X DELETE localhost:$${MAILPIT_UI_PORT:-8025}/api/v1/messages > /dev/null
	curl -s -X DELETE localhost:8000/blocklist/secure-login.corp-verify.test > /dev/null || true
	curl -s -X DELETE localhost:8000/blocklist/corp-verify.test > /dev/null || true
