# Portfolio historical tracking

Historical tracking starts when the first portfolio valuation snapshot is
created. This happens after a portfolio item is added, edited, or deleted, and
after a marketplace pricing refresh affects a set the user owns.

Snapshots are deduplicated to one per user per hour. A chart needs at least two
snapshots, so a new portfolio may show: “Portfolio history is unavailable until
at least two valuation snapshots have been recorded.”

Hourly snapshots are retained for 180 days by default. Before older hourly
snapshots are removed, the latest snapshot for each user and calendar day is
stored as a daily rollup. Daily rollups are retained to provide 1-year and
all-time history.

Run `make snapshot-portfolios` from a scheduler once per hour, or run
`python scripts/snapshot_portfolio_valuations.py --interval-minutes 60` for a
long-running local scheduler.
