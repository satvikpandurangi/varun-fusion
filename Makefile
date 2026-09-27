.PHONY: help install backfill test dev blend evaluate demo clean

help:
	@echo "VARUN-FUSION CLI Commands:"
	@echo "  make backfill START=2025-08-01 END=2025-08-15  Download/cache past forecast cycles"
	@echo "  make test                                      Run all unit and integration tests"
	@echo "  make dev                                       Start backend development server"
	@echo "  make blend CYCLE=2025-08-05                   Run multi-model blending pipeline"
	@echo "  make evaluate                                  Run model verification & baseline evaluation"
	@echo "  make demo                                      Initialize sample data and start services"

install:
	pip install -r backend/requirements.txt

backfill:
	python -m backend.app.jobs.backfill --start $(or $(START),2025-08-01) --end $(or $(END),2025-08-15)

test:
	python -m pytest backend/tests -v

dev:
	python -m uvicorn app.api.main:app --app-dir backend --reload --port 8000

blend:
	python -m backend.app.jobs.run_pipeline --cycle $(or $(CYCLE),2025-08-05)

evaluate:
	python -m backend.app.skill.evaluate --start 2025-08-01 --end 2025-08-15

demo: backfill test
	@echo "Demo data ready. Start backend with 'make dev' and frontend with 'cd frontend && npm run dev'"

clean:
	rm -rf data/harmonized/*.zarr data/varun_fusion.db .pytest_cache
