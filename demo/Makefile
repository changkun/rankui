# Build, check, and publish the interactive demo.
#   make build     build dist/
#   make dev       rebuild on change and serve at http://localhost:4410
#   make check     run the tests, type-check, and drive every interface in a
#                  headless browser
#   make deploy    check, then publish to https://changkun.de/research/rankui/

HOST ?= changkunde
DEST ?= /www/changkun.de/research/rankui/

build: node_modules
	npm run build

dev: node_modules
	npm run dev

check: build
	npm test
	npm run typecheck
	node tools/shots.ts

deploy: check
	rsync -az --delete dist/ $(HOST):$(DEST)
	@echo "published to https://changkun.de/research/rankui/"

node_modules: package.json
	npm install --no-audit --no-fund
	@touch node_modules

.PHONY: build dev check deploy
