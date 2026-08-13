# Portfolio CSV import format

Each CSV file creates one new portfolio. The first row must use these exact headers, in this exact order:

```csv
portfolio_name,portfolio_description,portfolio_currency,set_number,quantity,purchase_price,currency,condition,purchase_date,notes
```

Every purchase row repeats the portfolio fields, so exports can be imported without extra metadata. Those first three fields must be identical on every row.

| Field | Format | Required |
| --- | --- | --- |
| `portfolio_name` | 1–120 characters | Yes |
| `portfolio_description` | Up to 2,000 characters | No |
| `portfolio_currency` | Three uppercase letters, such as `USD` | Yes |
| `set_number` | Existing FlipRadar catalog set number | Yes |
| `quantity` | Positive whole number | Yes |
| `purchase_price` | Non-negative monetary amount | Yes |
| `currency` | Three uppercase letters, such as `USD` | Yes |
| `condition` | `new`, `used`, `sealed`, or `unknown` | Yes |
| `purchase_date` | ISO date (`YYYY-MM-DD`) or ISO timestamp; blank is allowed | No |
| `notes` | Up to 2,000 characters | No |

The importer stops at the first invalid or unknown row and makes no changes. Before creation it previews the rows that will become holdings. Duplicate rows can be kept as separate purchases, merged when all purchase details match, or rejected.
