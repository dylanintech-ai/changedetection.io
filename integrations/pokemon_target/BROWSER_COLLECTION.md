# Best Buy and Walmart browser integration

Status September 8, 2026: the ingestion adapter is implemented and tested. Both
retailers load in the connected browser. There is no standalone browser collector
running and no complete catalog. A one-time live-stock control email was delivered
successfully to the configured recipient on September 8 (Gmail confirmed SENT
and INBOX). The control was Walmart SKU 20895014480, a $39.97 two-deck bundle,
explicitly labeled as older 2023 products outside the production watchlist and
not a newly detected restock. The product page showed sold and shipped by
Walmart.com, enabled Add to cart and free shipping September 11 to the browser's
07090 location. The durable outbox marks this test sent; never repeat it. Walmart's
plain HTTP response is a robot challenge. Best Buy first-party recent TCG offers
checked so far are store-only or coming soon.

Standalone collector experiment: `walmart_browser.py` with ordinary visible Chrome
read structured product-page data successfully. Headless Chrome was challenged.
Three visible-browser rounds 30 seconds apart yielded: round 1 Surging Sparks
out of stock and control bundle in stock; round 2 Surging Sparks challenged and
control still in stock; round 3 both challenged. This is partial, intermittent
access, not reliable continuous monitoring. Challenge observations stay unknown;
the collector now stops the round and backs off at least ten minutes. No CAPTCHA
solver, proxy service, or browser fingerprint modification is used.

The first real Surging Sparks observation was persisted as a silent out-of-stock
baseline in the local retailer state database. The older control SKU was rejected
by the production catalog. The collector can feed the transition pipeline directly
using `--state` and `--email-module`; its default one-cycle mode only writes results.
Install `requirements-browser.txt` into the existing virtual environment; Chrome
must already be installed. Twelve integration tests pass. Collector processes from
this bounded experiment have exited; no continuous collector is running yet.

`browser_bridge.py` ingests product-page observations from a browser collector.
It uses separate retailer/SKU identities in a persistent SQLite database and the
existing local email outbox. Initial in-stock observations are silent. Only an
observed out-of-stock to in-stock transition can enqueue a restock. Errors,
marketplace sellers, ambiguous availability, store-only listings and stale
observations do not rearm alerts. Events expire after three minutes; a subsequent
out-of-stock observation cancels queued delivery.

Each observation contains `retailer`, `sku`, exact canonical `url`, `observed_at`
(Unix seconds), `seller`, `status`, `shipping_available`, `price`, `currency`, and
`evidence` (the relevant current product-page text). A caller must resolve URL
query parameters to the catalog identity without discarding seller-selection
evidence. Read seller from the current offer, never customer reviews or ads.

Catalog entries require independently sourced MSRP and release dates. Null MSRP
in the initial catalog is intentional: the displayed retailer price is not proof
of the manufacturer's MSRP. Search results are discovery aids, not observations.

Run from this directory:

```sh
python3 browser_bridge.py --observations observations.json \
  --catalog retailer_catalog.json --state retailer-state.sqlite \
  --email-module /Users/dylan/projects/pokemon-restock-alerts/email_outbox.py
```

Remaining work: automate fresh browser collection, expand the catalog, verify
price ceilings, and demonstrate a qualifying recent-product restock email.
The existing-stock control test is complete; do not fabricate an out-of-stock
baseline or send additional control emails to substitute for that milestone.
