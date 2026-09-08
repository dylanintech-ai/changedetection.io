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

`transitions.py` now persists stock states and creates one event per observed out-of-stock → in-stock transition. Startup in-stock is a silent baseline; repeated in-stock remains silent even across restart. Unknown/error results never rearm alerts. Returning out of stock cancels queued mail when the bridge runs before delivery. `bridge.py` reads changedetection watch files and passes only fresh, exact-SKU, verified-seller, verified-MSRP, USD, recent-product events to the existing email queue.

Live test on September 7, 2026: the upstream basic HTTP fetcher received HTTP 200 for Target SKU 92076617, but found no price/availability metadata and returned an extraction error. It was not treated as in stock. Browser inspection of Pitch Black SKU 1011483414 showed out of stock. Target then presented a human-verification challenge on its category page. No successful live Target restock alert has been sent. The old repost listener is intentionally stopped because reposts cannot establish a true out/in transition.

Not activated yet: full pagination, automatic daily catalog refresh, current live availability extraction, exact MSRP mapping, and seller verification. No claim of full Target coverage or verified Target stock alerts is made. The existing email queue remains a separate project in `../pokemon-restock-alerts` relative to the repository directory.
