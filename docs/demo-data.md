# Demo Data

The local development stack seeds a stable demo account and representative market
data on startup. It is designed for a preemptive demo, UI review, and repeatable
manual testing—not for real pricing decisions.

## Start The Demo

From the repository root:

```bash
./scripts/run_local_app.sh
```

Open `http://127.0.0.1:5173` and sign in with:

- Email: `demo@flipradar.com`
- Password: `DemoPass1!`

## Included Scenarios

- Eight catalog sets across Star Wars, Icons, Ideas, Technic, Horizon, and Super
  Mario, with current and retired sets.
- New and used-complete price snapshots from eBay and BrickLink over three dates,
  including rising and falling price trends.
- Active, sold, and ended listings with shipping, seller, condition, verification,
  and matching variations.
- A five-holding portfolio with sealed, new, and used entries, varied quantities,
  purchase dates, and a saved analysis.
- A set watch and a listing watch, each with observations; the listing watch is
  intentionally below its target threshold.

The script is idempotent: rerunning it finds each seeded record by its stable key
and does not duplicate it.

## Refresh Or Reset

To run migrations and make sure all demo records are present without deleting
local data:

```bash
./scripts/migrate_and_seed.sh
```

To return the local stack to the complete baseline, run:

```bash
make reset-demo-data
```

This command asks you to type `RESET`, then deletes the local Docker volumes for
PostgreSQL, Redis, and frontend dependencies before recreating the database and
seeding it. It only affects the local Docker environment; treat any data in that
environment as disposable.

For live price refresh behavior and limits, see
[Confidence, Freshness, and Data Limits](confidence-freshness-and-data-limits.md).
