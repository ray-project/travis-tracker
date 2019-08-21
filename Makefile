placeholder:
	@echo "Please do not run make by itself, run it with `make build` or `make copy-assets`

build:
	cd travis-table-render;npm run build

copy-assets:
	rm -rf heroku-version/static
	cp -r travis-table-render/build heroku-version/static
