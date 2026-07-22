# FlipRadar Frontend

The frontend is a React, TypeScript, Vite, and Tailwind application.

## Install

```bash
cd frontend
npm install
```

## Environment

The current Vite configuration proxies `/api/*` requests to `http://127.0.0.1:8000` during local development. Add frontend-specific `.env` files in `frontend/` when environment variables are introduced.

## Run

```bash
cd frontend
npm run dev
```

The app runs at `http://127.0.0.1:5173` by default.

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

## Tests

No frontend test runner is configured yet. When frontend tests are added, keep test commands in `frontend/package.json` and document them here.
