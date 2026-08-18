# Live marketplace providers

FlipRadar no longer has mock marketplace clients or deterministic marketplace fixtures in runtime code.

| Former mock path | Production feature | Live provider operation |
| --- | --- | --- |
| `ebay_mock_client.adapter.fetch_listings` | Marketplace refresh and price snapshots | eBay Browse `GET /buy/browse/v1/item_summary/search` with an OAuth application token |
| `bricklink_mock_client.adapter.fetch_listings` | Marketplace refresh and price snapshots | BrickLink `GET /items/SET/{number}/price` for sold new and used price guides |
| `bricklink_mock_client.fetch_set_metadata` | Set-detail fallback and catalog hydration | BrickLink `GET /items/SET/{number}` |
| `bricklink_mock_client.fetch_set_price_snapshot` | Set-detail fallback valuation | BrickLink sold price-guide statistics |
| `bricklink_mock_client.fetch_part_catalog_records` | Part-catalog hydration | BrickLink exact part lookup `GET /items/PART/{number}`, plus its new-condition sold price guide |

## Configuration

Set the following secrets in `backend/.env` or the deployment secret store. The adapters are enabled by default but are usable only when every required credential is present; they never fall back to generated data.

```dotenv
EBAY_API_KEY=your-production-client-id
EBAY_API_SECRET=your-production-client-secret
BRICKLINK_CONSUMER_KEY=your-consumer-key
BRICKLINK_CONSUMER_SECRET=your-consumer-secret
BRICKLINK_TOKEN_VALUE=your-access-token
BRICKLINK_TOKEN_SECRET=your-token-secret
```

eBay uses the OAuth client-credentials grant and caches the returned application token. BrickLink requires OAuth 1.0 request signing; BrickLink access tokens are tied to registered client IP addresses.

BrickLink exposes item/catalog and aggregated price-guide operations, but not a public global marketplace-listing search. Its adapter therefore emits price-guide detail records as valuation evidence, with stable derived identifiers, rather than inventing sellers, shipping costs, or listings.
