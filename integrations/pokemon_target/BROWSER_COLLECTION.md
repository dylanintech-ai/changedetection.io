# Best Buy and Walmart browser integration

Status September 8, 2026: the ingestion adapter is implemented and tested. Both
retailers load in the connected browser. There is no standalone browser collector
running, no complete catalog, and no verified live stock email yet. Walmart's
plain HTTP response is a robot challenge. Best Buy first-party recent TCG offers
checked so far are store-only or coming soon.

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
price ceilings, and demonstrate a qualifying live email. A clearly labeled
one-time existing-stock test is authorized, but must use a real recent Pokémon
TCG product with first-party shipping at or below verified MSRP; do not fabricate
an out-of-stock baseline to trigger it.
