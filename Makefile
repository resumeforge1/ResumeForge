.PHONY: run test qa

run:
	uvicorn app.main:app --reload

test:
	python -m pytest tests -q

qa:
	python -m compileall app tests
	python -m pytest tests -q
