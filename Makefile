placeholder:
	@echo "Please do not run make by itself, run it with `make build` or `make copy-assets`

build:
	cd travis-table-render;npm run build --verbose

copy-assets:
	rm -rf static
	cp -r travis-table-render/build static

deploy:
	git push heroku master

