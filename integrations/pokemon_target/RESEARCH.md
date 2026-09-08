# Collection research — September 8, 2026

Verified GitHub metadata: changedetection.io 33,717 stars (Apache-2.0),
streetmerchant 5,400 (MIT), nearyou/pokemon-stock-monitor 25 (no license
reported), pranavtallapaka/pokemon-restock 1 (no license reported).

## Best Buy: official API is the next route to validate

https://bestbuyapis.github.io/api-documentation/#availability
Documents onlineAvailability, onlineAvailabilityUpdateDate, inStoreAvailability,
releaseDate, salePrice and product links. Do not interpret inStoreAvailability
as online stock; documentation says it can merely indicate an item is sold in
stores. regularPrice is a retailer selling price, not verified MSRP.
https://developer.bestbuy.com/ offers API-key registration. Opening its login
redirected to Best Buy account sign-in; no authenticated API request performed.
API coverage and latency for current Pokémon SKUs remain unverified.

## Repository audit

https://github.com/jef/streetmerchant/blob/main/src/store/model/bestbuy.ts
https://github.com/jef/streetmerchant/blob/main/src/store/model/walmart.ts
Both use page selectors; no magic inventory feed. Walmart uses old prod-ProductCTA
and price-characteristic selectors. Best Buy SOLD_OUT selector appears malformed
(missing closing quote). Must validate against today's pages before adoption.

https://github.com/pranavtallapaka/pokemon-restock/blob/main/scrapers/bestbuy.js
Uses official API when keyed, HTML otherwise. Its status helper ORs online and
in-store availability, which fails our shipping-only requirement.
https://github.com/pranavtallapaka/pokemon-restock/blob/main/scrapers/walmart.js
Extracts embedded __NEXT_DATA__, checks sellerName/sellerId, then stock fields.
Unknown status falls back to out_of_stock: unacceptable for our transition logic.
Its README admits bot blocking. No license detected; study the approach rather
than importing its implementation. README example runs are not live validation.

https://github.com/dgtlmoon/changedetection.io/wiki/Playwright-content-fetcher
Our existing highly starred fork already has a documented real-browser collector
integration. This is the next standalone Walmart route to test, with precise
current-offer seller/shipping extraction and unknown-state preservation.

## Decision

Keep the existing changedetection fork. Validate the official Best Buy API after
account access is available; implement local browser collection for Walmart.
Do not switch to a low-star repository on the strength of a README. The live
Walmart email control has succeeded, but continuous recent-SKU monitoring and a
real restock event remain unfinished.
