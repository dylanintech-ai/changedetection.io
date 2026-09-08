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

Best Buy standalone experiment: both catalog decks loaded in ordinary visible
Chrome without an API key. `bestbuy_browser.py` selects the exact SKU's JSON-LD
offer and purchase buttons. Both live offers said schema.org/InStock while showing
disabled SKU-specific In Store Only controls, so both correctly remained unknown
for online shipping. Fifteen tests pass, including this live counterexample and
rejection of unrelated recommendation purchase buttons. Positive shipping
detection still needs validation against a real available Best Buy offer; do not
claim the synthetic positive test proves live restock coverage. Mega Lucario's
$29.99 MSRP is now corroborated by PokeGuardian and ICv2 in the catalog.

Positive Best Buy validation: SKU 6611691 (a mouse pad, excluded from TCG watches)
has an enabled `pdp-add-to-cart-6611691` control and `availableDeliveryMethod`
containing the literal `SHIPPING`. This revealed and fixed an unsupported value
in the collector. Running the actual collector on that live page now returns
in_stock, shipping_available true, seller Best Buy and price $29.99. No email was
sent for this validation. Sixteen tests pass. This proves parsing of a live
shippable offer, not that any recent TCG SKU is available or has restocked.

Online baseline correction: a disabled, exact-SKU In Store Only purchase control
now establishes online out_of_stock, rather than unknown. This is directly
observed online unavailability; if a later observation confirms shipping and an
enabled matching purchase control, it can legitimately trigger a transition.
Coming-soon/preorder controls and ambiguous data still stay unknown. Earlier
experiment descriptions above reflect the classification at the time of testing.

Search discovery is not complete. A ten-page exploratory run found only 43
Pokémon candidates because later pages yielded four product cards each. The
revised `discover_bestbuy.py` records expected and actual counts per page, but
still encountered incomplete loading and was stopped. Mouse-wheel scrolling
loaded additional cards in one diagnostic run but did not reliably resolve the
problem. `bestbuy_discovered.json` is explicitly unverified discovery output and
must not replace the production catalog or be counted as full two-year coverage.

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
