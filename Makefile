.PHONY: install generate-types start-dev start-prod clean test dev

install:
	cd backend && (test -d venv || python3 -m venv venv) && ./venv/bin/pip install -e .
	cd rewrite-engine && npm install
	cd frontend && npm install

generate-types:
	# Backend: Generate Pydantic models from JSON Schema
	# Ensure datamodel-codegen is installed
	datamodel-codegen --input schemas/refactor-ir.schema.json --output backend/rpc/generated/models.py --input-file-type jsonschema --output-model-type pydantic_v2.BaseModel
	
	# Frontend/Node: Generate TS types from JSON Schema
	cd rewrite-engine && npx json-schema-to-typescript ../schemas/refactor-ir.schema.json --output src/generated/types.ts

start-dev:
	docker compose up -d db redis

dev: start-dev install
	npx concurrently -k -p "[{name}]" -n "Backend,Rewrite,Frontend" -c "bgBlue.bold,bgGreen.bold,bgMagenta.bold" \
	"cd backend && ./venv/bin/python main.py" \
	"cd rewrite-engine && npm run dev" \
	"cd frontend && npm run dev"

dev-backend:
	cd backend && ./venv/bin/python main.py

dev-rewrite-engine:
	cd rewrite-engine && npm run dev



start-prod:
	docker compose up -d

clean:
	docker compose down -v
	rm -rf .refactor-workspaces
	rm -rf rewrite-engine/node_modules
	rm -rf frontend/node_modules

test:
	cd backend && pytest
	cd rewrite-engine && npm test
