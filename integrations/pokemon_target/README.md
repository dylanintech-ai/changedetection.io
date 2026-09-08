# Target US Pokémon integration

This fork uses changedetection.io as the monitoring base, selected over small Pokémon-specific repos for its established community. Upstream: https://github.com/dgtlmoon/changedetection.io (33,701 stars when checked September 8, 2026).

Scope: Pokémon TCG products at Target US, released in the trailing two calendar years, with email notifications at or below verified MSRP. Upcoming products are collected separately for future eligibility. Unknown dates need review. Target street dates are a proxy for the individual retail product release, not the expansion launch date.

`catalog.py` imports saved Target RedSky category response pages. It preserves exact TCINs, direct Target URLs, street dates, price observations, and explicit completeness information. It emits paused changedetection restock-watch payloads. Watches must stay paused until seller, actual availability extraction, and MSRP are validated.

Example:

```sh
python3 integrations/pokemon_target/catalog.py /tmp/target-category.json --output /tmp/target-catalog-report.json
python3 -m unittest discover -s integrations/pokemon_target -v
```

Verified findings: Pokémon category `6llsh` returned 641 products and 27 pages of 24. Only the first page was captured. Target's former `pdp_fulfillment_v1` endpoint returned HTTP 410. A subsequent request adding a seller facet returned HTTP 403. Do not interpret these as sold out or complete coverage. The 641 count includes items that will not qualify after date/seller filters.

Not activated yet: full pagination, automatic daily catalog refresh, current availability endpoint, exact MSRP mapping, seller verification, and a changedetection-to-existing-email-queue bridge. No claim of full Target coverage or verified Target stock alerts is made. Existing email fallback service remains a separate project in `../pokemon-restock-alerts` relative to the repository directory.
