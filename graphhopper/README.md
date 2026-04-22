# GraphHopper Runtime

This directory owns the stage-01 GraphHopper runtime scaffold.

- `Dockerfile` downloads the official GraphHopper 8.0 web jar during image build.
- `config.yaml` keeps the import source rooted at `etl/data/raw/busan.osm.pbf`.
- `custom_models/` fixes the four profile names that the backend will target.

Stage 01 intentionally keeps the runtime on the stock GraphHopper application so `docker compose up` can validate the container contract early. Custom encoded values and SPI wiring are deferred to `graphhopper-plugin/` and workstream `04-graphhopper-routing-profiles.md`.
