# FlipRadar Frontend

The frontend is a React, TypeScript, Vite, and Tailwind application.

For the complete Docker stack, see [local development](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/local-development.md). For the seeded account, walkthrough data, and reset procedure, see [demo data](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/demo-data.md).

## Install

```bash
cd frontend
npm install
```

## Environment

The current Vite configuration proxies `/api/*` requests to `http://127.0.0.1:8000` during local development.

Supported frontend variables are listed in `.env.example`:

- `VITE_API_BASE_URL`: browser-facing API base URL, default `/api`.
- `VITE_API_PROXY_TARGET`: Vite dev-server proxy target, default `http://127.0.0.1:8000`.

When running in Docker Compose, `VITE_API_PROXY_TARGET` points the Vite proxy at `http://backend:8000`.

## Run

```bash
cd frontend
npm run dev
```

The app runs at `http://127.0.0.1:5173` by default.

## Demo Walkthrough

Sign in with `demo@flipradar.com` / `DemoPass1!` after starting the Docker
stack. The demo portfolio, watchlist, listings, and saved portfolio analysis are
already available. Portfolio screens include contextual guidance for cost basis,
estimated value, stale data, and empty/filter-result states; the supporting
definitions live in [the docs index](/Users/rbbla1/Documents/dev/building_side/FlipRadar/docs/README.md).

## Build

```bash
cd frontend
npm run build
```

Preview the production build:

```bash
cd frontend
npm run preview
```

## Docker

`frontend/Dockerfile` contains:

- `development`: Vite dev server on port `5173`.
- `build`: TypeScript and Vite production build.
- `production`: Nginx static server with `/api` proxied to the backend service.

## Tests

```bash
cd frontend
npm run test
npm run test:coverage
```

Vitest uses jsdom and React Testing Library. Coverage currently targets API helpers, reusable components, and formatting/business display utilities.

## Quality

```bash
cd frontend
npm run lint
npm run typecheck
npm run format:check
npm run build
```

From the repository root, `make frontend-quality` runs ESLint, TypeScript checks, Vitest coverage, and the production build.
