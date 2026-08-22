
FLIPRADAR — PRODUCTION READINESS PHASE PLAN

Purpose: Replace TODOs.md as the active execution plan. Primary
objective: Stop feature development, clean up production risks,
establish a reliable release pipeline, and deploy FlipRadar safely.
Rule: Do not begin new product features until Milestone 4 is complete
and production is stable.

======================================================================
MILESTONE 0 — STOP THE BLEEDING Priority: CRITICAL Goal: Freeze feature
development and eliminate anything that could make a production
deployment unsafe or misleading.
======================================================================

PHASE 0 — DEVELOPMENT FREEZE AND RELEASE BASELINE 
1. Freeze new featuredevelopment until the production-readiness milestones in this plan are complete. -
2. Create a dedicated production-readiness branch from the current known-good main branch. -
3. Archive TODOs.md as historical reference and remove it as the source of development direction. -
4. Make this production-readiness plan the active execution checklist for the project. -
5. Record the current Python, Node.js, npm, PostgreSQL, and Redis versions used locally. 
6. Run and record every currently available backend and frontend quality check before making cleanup changes. -
7. Create a short list of known failures, skipped tests, warnings, and environment-specific behavior found during the baseline run. - 
8. Commit the untouched baseline state so cleanup changes can always be compared against it. -

PHASE 1 — CI PIPELINE 
1. Create .github/workflows/ci.yml with triggers for pull requests and pushes to main. - 
2. Add a backend CI job that installs dependencies in a clean environment. - 
3. Run Ruff, Black check, Pyright, and the complete backend pytest suite. 
4. Start a clean PostgreSQL service in CI and run Alembic migrations from an empty database through head. -
5. Add a frontend CI job using npm ci followed by ESLint, Prettier check, TypeScript checking, Vitest, and the production build. -
6. Add Docker build jobs for the production backend and frontend images. -
7. Ensure every CI job fails immediately when its corresponding quality gate fails.  - 
8. Add caching only after the clean pipeline is stable and reproducible.  - 
9. Make the full pipeline green from a completely clean GitHub runner before continuing. - 

PHASE 2 — BRANCH PROTECTION AND RELEASE GATES 
1. Protect the main branch from direct pushes. 
2. Require pull requests for all production-readiness changes.  - 
3. Require successful backend CI checks before merge.  - 
4. Require successful frontend CI checks before merge.  - 
5. Require successful migration and Docker image build checks before merge. - 
6. Prevent merging when the branch is behind main if GitHub reports conflicting or stale checks.  - 
7. Document the minimum merge requirements in the repository README or contributor documentation. - 

======================================================================
MILESTONE 1 — REMOVE PRODUCTION LANDMINES Priority: CRITICAL Goal: Make
it impossible for production to serve fake data, expose internal
controls, or behave differently because of accidental development
configuration.
======================================================================

PHASE 3 — REMOVE MOCK MARKETPLACE DATA FROM PRODUCTION PATHS 
1. Inventory every import and runtime reference to ebay_mock_client and bricklink_mock_client.  - 
2. Map each mock-backed code path to the production feature that currently depends on it.  - 
3. Implement or connect real provider adapters for the required eBay and BrickLink marketplace/catalog operations.  - 
4. Refactor marketplace_service.py so provider selection is configuration-driven rather than hardwired to mock clients.  - 
5. Replace direct mock-client imports in part_catalog_service.py, set_catalog_service.py, and set_detail_service.py.  - 
6. Define explicit behavior for unavailable providers: return a controlled unavailable/error state rather than generated substitute data.  - 
7. Add tests proving production configuration never selects a mock provider.  - 
8. Add integration tests covering at least one successful and one failed real-provider request path.  - 
9. Remove or clearly isolate remaining mock clients so they are available only to tests/development. - 

PHASE 4 — PRODUCTION FAIL-CLOSED SAFETY CONTROLS 
1. Add an explicit configuration setting controlling whether mock marketplace providers are allowed.  - 
2. Default mock-provider access to disabled outside local development/test environments.  - 
3. Make application startup fail when APP_ENV=production and a mock provider is selected or enabled.  - 
4. Audit production startup validation for debug mode, JWT secrets, database SSL, CORS, provider credentials, and unsafe defaults. -
5. Ensure production cannot silently substitute development credentials or localhost URLs. -
6. Add automated tests for every production startup rejection condition.  - 
7. Add one positive test proving a valid production configuration can boot successfully. - 

PHASE 5 — INTERNAL AND DEVELOPMENT ENDPOINT LOCKDOWN 
1. Inventory routes marked internal, development, debug, administrative, refresh, seed, or maintenance. - 
2. Remove /marketplace/update/{set_number} from public production access or require privileged service/admin authorization. - 
3. Verify no seed, reset, debug, mock-data, or test routes are exposed in production. - 
4. Add environment guards around routes that should exist only during development. - 
5. Add authorization tests for every privileged production endpoint that remains. - 
6. Verify unauthorized requests cannot trigger provider calls, background work, or database writes. -
7. Document the remaining administrative endpoints and their intended authentication model.-

PHASE 6 — REPRODUCIBLE DEPENDENCIES AND RUNTIME VERSIONS 
1. Choose one supported Python runtime version for local development, CI, and Docker. -
2. Align Docker, Black, Ruff, Pyright, documentation, and CI with that Python version.  -
3. Pin or lock all backend production dependencies to reproducible versions.  -
4. Verify frontend builds exclusively from package-lock.json using npm ci.  - 
5. Rebuild backend and frontend from clean dependency caches.  - 
6. Run the full test suite against the locked dependency set.  - 
7. Build both production Docker images twice from clean environments and verify reproducible successful builds. - 
8. Add dependency update procedures so version upgrades happen intentionally rather than during deployments. -

====================================================================== 
MILESTONE 2 — PROTECT USERS AND DATA Priority: HIGH Goal: Harden
authentication, database behavior, secrets, and external-service
handling before real users touch the system.
======================================================================

PHASE 7 — AUTHENTICATION AND ABUSE PROTECTION 
1. Inventory authentication, registration, password-reset, MFA, provider, evaluation, and other expensive public endpoints.  - 
2. Replace or supplement the per-process in-memory limiter with Redis-backed rate limiting for security-sensitive endpoints.  - 
3. Apply strict endpoint-specific limits to login, registration, password reset, verification, and MFA flows.  - 
4. Add reasonable protection to expensive marketplace/provider and LLM-backed operations.  - 
5. Configure trusted proxy handling so client IP detection cannot be trivially spoofed with X-Forwarded-For.  - 
6. Add tests for rate-limit enforcement, expiration, and behavior across shared Redis state.  - 
7. Verify normal user activity does not trigger the new abuse limits. - 

PHASE 8 — EMAIL AND ACCOUNT LIFECYCLE 
1. Select and configure the production transactional email provider. 
2. Store email credentials only in deployment/environment secret storage. 
3. Test registration and email-verification delivery end-to-end.  - 
4. Decide and enforce whether unverified accounts may authenticate or access protected application functionality.  - 
5. Test password-reset requests and reset completion against the deployed frontend URL.  - 
6. Test MFA, email-change, account-deletion, and security-notification email flows that are currently implemented.  - 
7. Ensure email failures produce controlled user-facing behavior and useful server logs. -
8. Verify production emails do not contain localhost, staging, or development links.-

PHASE 9 — DATABASE INTEGRITY AND MIGRATION CERTIFICATION 
1. Create a completely empty PostgreSQL database using the production PostgreSQL major version. -
2. Run alembic upgrade head from zero and verify every migration completes successfully. -
3. Boot the API against the newly migrated database. - 
4. Seed or create representative users, sets, listings, portfolio positions, snapshots, and watchlist data. - 
5. Verify foreign-key delete and cascade behavior for user-owned and marketplace data. - 
6. Audit monetary values, prices, quantities, and calculations for appropriate Decimal/numeric storage instead of unsafe floating-point persistence. - 
7. Verify required indexes exist for common search, lookup, portfolio, marketplace, and snapshot queries. - 
8. Test forward migration using a copy of representative populated data. -

PHASE 10 — SECRETS AND PRODUCTION CONFIGURATION 
1. Define the complete production environment-variable contract in one documented location.  - (Complete)
2. Generate a strong production JWT secret and ensure no development/default secret is accepted.  - (Complete)
3. Configure the production PostgreSQL connection with required SSL.  - (Complete)
4. Configure production Redis and external-provider credentials.  - (Complete)
5. Set explicit production frontend URL and CORS origins with no wildcard origins.  - (Complete)
6. Configure release/version identifiers used by logs and error reporting.  - (Complete)
7. Store all production secrets in the deployment platform or GitHub Environment secret store.  - (Complete)
8. Scan the repository and Git history for accidentally committed secrets or credentials and rotate anything exposed.  - (Complete)
9. Validate the complete production configuration in CI or staging without exposing secret values. - (Complete)

======================================================================
MILESTONE 3 — BUILD THE RELEASE MACHINE Priority: HIGH Goal: Establish
staging, observability, production-equivalent containers, and a
controlled deployment path.
======================================================================

PHASE 11 — PRODUCTION CONTAINER CERTIFICATION 
1. Build the backend using the actual production Dockerfile target rather than development Compose behavior. - (Automated release certification)
2. Build the frontend using the actual production nginx/static build target. - (Automated release certification)
3. Run both production images locally or in CI without source-code bind mounts. - (Automated release certification)
4. Boot the backend with production-like environment validation enabled. - (Staging validation and release stack)
5. Verify /health/live and /health/ready correctly distinguish process health from dependency readiness. - (Automated release certification)
6. Verify frontend routing, static assets, and /api proxy behavior using the production container. - (Automated release certification)
7. Verify graceful startup and shutdown behavior for the API container. - (Automated release certification)
8. Record final container ports, required environment variables, volumes, and service dependencies. - (Production Configuration Contract)

Priority: P0 — Do this now

1. Run the complete current CI suite from the latest commit.
- Backend Black,  Backend Ruff,  Pyright, Backend pytest, PostgreSQL/Alembic migration test 
- Frontend ESLint, Frontend Prettier, Frontend TypeScript, Frontend Vitest, Frontend production build, Backend Docker build, Frontend Docker build, Release-container certification
2. Create one authoritative list of current CI failures.
- Ignore old failure counts once the new run exists.
- Group failures by root cause rather than by individual failing test.
- Mark each failure as: application bug, stale test, environment/config problem, dependency/tooling problem
3. Fix backend test failures first.
- Prioritize failures that affect auth, database behavior, marketplace/provider behavior, portfolio operations, startup configuration, or API responses.
- Do not weaken assertions merely to make CI green.
4. Fix static-analysis and formatting failures.
- Ruff, Black, Pyright, ESLint, Prettier, TypeScript
5. Fix frontend test/build failures.
- Vitest must pass.
- Production Vite build must succeed from a clean dependency install.
6. Verify migrations from an empty PostgreSQL database.
- alembic upgrade head
- No manually created tables.
- No dependency on development seed state.
7. Verify both production Docker images build cleanly.
* 8. Run release-container certification.
    * Production backend image
    * Production frontend image
    * PostgreSQL
    * Redis
    * /health/live
    * /health/ready
    * frontend/API communication

GATE 1

STOP until GitHub Actions shows full green.

Target: all CI checks green / your expected 5/5 green status.

No deployment infrastructure work should take priority over this gate.

⸻

MILESTONE 2 — LOCK THE KNOWN-GOOD BASELINE

Priority: P0

* 9. Enable branch protection on main.
    * Do this immediately after CI reaches full green.
    * Require the relevant CI checks before merge.
    * Since this is currently a one-developer project, keep the policy lightweight.
    * Do not create unnecessary reviewer/approval bureaucracy.
* 10. Add Celery worker and scheduler coverage to release certification.
    * Determine which scheduled/background tasks are required at launch.
    * Add a Celery worker to the production-equivalent release stack.
    * Add Celery Beat if scheduled jobs remain enabled.
    * Confirm both boot successfully using production-style configuration.
    * Confirm Redis connectivity.
    * Confirm one harmless task can execute.

GATE 2

The repository now has:

Green CI + protected main + production-equivalent application components.

⸻

MILESTONE 3 — DEFINE THE REAL PRODUCTION ARCHITECTURE

Priority: P0

Target architecture:

Vercel

* React/Vite frontend

Render

* FastAPI API service
* Celery worker
* Celery Beat/scheduler if required

Supabase

* Managed PostgreSQL

Managed Redis

* Render Redis or another compatible managed Redis provider
* 11. Create the required platform projects/accounts and choose deployment regions.
    * Select the Supabase region first.
    * Place Render services geographically close to Supabase where practical.
    * Create the Vercel project.
    * Do not configure a custom domain yet unless you want to.
    * Platform-provided domains are sufficient for the first staging deployment.
* 12. Establish the environment matrix.
    At minimum define:
    Local
    * local PostgreSQL
    * local Redis
    * development credentials
    Staging
    * separate Supabase database/project or properly isolated staging database
    * separate secrets
    * separate provider configuration
    * Render staging services
    * Vercel preview/staging deployment
    Production
    * production Supabase database
    * production secrets
    * production Render services
    * Vercel production deployment
* 13. Translate the existing environment contract into platform variables.
    * Database URL
    * Alembic database URL
    * Redis URL
    * JWT secrets
    * CORS origins
    * frontend API URL
    * marketplace credentials
    * email configuration if enabled
    * Sentry if enabled
    * APP_ENV
    * APP_RELEASE
    No production secret belongs in Git.

GATE 3

Real infrastructure exists and FLIPRADAR has somewhere to deploy.

⸻

MILESTONE 4 — DEPLOY STAGING MANUALLY FIRST

Priority: P0

Do not build the CD pipeline yet.

First prove that the platforms themselves work.

* 14. Deploy PostgreSQL/Supabase and run migrations manually.
    * Connect using SSL.
    * Run Alembic through head.
    * Verify the API can connect.
    * Verify /health/ready.
* 15. Deploy the FastAPI service to Render.
    * Production configuration.
    * Production Dockerfile/runtime.
    * Platform environment variables.
    * HTTPS Render URL.
    * No localhost dependencies.
    * No development defaults.
* 16. Deploy the frontend to Vercel.
    * Set its staging API URL to the Render API.
    * Configure API CORS to allow the Vercel staging URL.
    * Verify frontend routing.
    * Verify browser → API communication.
* 17. Deploy background services.
    * Celery worker.
    * Celery Beat only if required.
    * Connect both to the same Redis/backend environment.
    * Verify task execution.
* 18. Perform the staging launch smoke test.
    * Frontend loads.
    * /health/live returns healthy.
    * /health/ready returns healthy.
    * Registration works.
    * Login works.
    * Protected user endpoint works.
    * Catalog/set lookup works.
    * Portfolio create/read/update works.
    * At least one real marketplace/provider request works.
    * Mock marketplace data cannot activate.
    * One background task executes successfully.

GATE 4

If all of those pass, FLIPRADAR is technically deployable.

That is the point where production becomes a release-management problem rather than a development problem.

⸻

MILESTONE 5 — MINIMUM PRODUCTION OPERATIONS

Priority: P1

* 19. Configure minimum observability and recovery controls.
    * Backend error reporting.
    * Frontend error reporting.
    * Release SHA/version attached to deployments.
    * Render logs verified.
    * Database backups enabled.
    * Know how to roll Render back to the previous deployment.
    * Know how to roll Vercel back to the previous deployment.
    * Do not perform destructive database migrations without a rollback strategy.
* 20. Create the production environment from the proven staging configuration.
    * Production Supabase database.
    * Production Render API.
    * Production worker.
    * Production scheduler if enabled.
    * Production Redis.
    * Vercel production frontend.
    * Production secrets.
    * Production CORS.
    * Production marketplace credentials.
    * HTTPS everywhere.

A custom domain is not required for this milestone.

The Vercel/Render generated domains can be used for the first controlled production release.

⸻

MILESTONE 6 — CONTROLLED FIRST RELEASE

Priority: RELEASE

* 21. Create a release candidate commit.
    * CI fully green.
    * No unrelated feature changes.
    * Record the Git SHA.
* 22. Deploy that exact commit to staging one final time.
    * Run migrations.
    * Run the smoke test.
    * Confirm no P0/P1 defects.
* 23. Promote the release to production.
    * Run production migrations.
    * Deploy API.
    * Deploy worker/scheduler.
    * Deploy frontend.
    * Verify health endpoints.
    * Run safe production smoke tests.
    * Verify marketplace data is real.
    * Verify authentication.
    * Verify database writes.
    * Verify error reporting.
* 24. Keep the first release controlled.
    * Use it yourself first.
    * Avoid immediately driving meaningful public traffic.
    * Watch logs/errors.
    * Fix release-blocking issues before expanding access.

GATE 5 — FLIPRADAR IS LIVE

At this point the application is in production.

⸻

MILESTONE 7 — BUILD CD AFTER DEPLOYMENT WORKS

Priority: P1 — Post first successful deployment

Only automate a release process after the manual process has been proven.

* 25. Create the CD pipeline around the working Supabase + Render + Vercel architecture.
    * CI remains separate.
    * CI must succeed first.
    * Deploy backend to Render.
    * Run controlled Alembic migrations.
    * Deploy/update worker services.
    * Deploy frontend through Vercel.
    * Attach Git SHA/release metadata.
    * Execute post-deployment health checks.
    * Add staging-before-production promotion if the final platform architecture supports it cleanly.
    * Preserve rollback capability.

⸻

NOT BLOCKING THE FIRST DEPLOYMENT

Move these back into the production-hardening backlog unless testing proves one is currently dangerous:

* Custom domain
* Perfect DNS architecture
* Advanced security headers
* Elaborate CSP tuning
* Full automated CD
* Sophisticated alert dashboards
* Large coverage increases
* Extensive performance optimization
* Full disaster-recovery exercises
* Perfect operational documentation
* Dependency vulnerability automation
* Automated backup restore drills
* Multi-region deployment
* Autoscaling optimization
* Kubernetes
* Complex Git branching strategies
* Additional product features

These are valid engineering tasks.

They are not all prerequisites for putting the first controlled version of FLIPRADAR online.

⸻

CURRENT EXECUTION ORDER

Right now:

CI failures
→ Full green
→ Branch protection
→ Worker/Beat release certification
→ Supabase/Render/Vercel provisioning
→ Manual staging deployment
→ Staging smoke tests
→ Production configuration
→ Controlled production release
→ CD automation
→ Remaining PROD_TODOS hardening

Do not jump ahead of the gates.
======================================================================
NON-NEGOTIABLE RELEASE RULES
======================================================================

-   No new product features before production readiness is complete.
-   No production deployment unless CI is green from a clean
    environment.
-   No production mock marketplace data.
-   No publicly exposed development/internal mutation endpoints.
-   No production secrets committed to the repository.
-   No deployment that has not first succeeded in staging.
-   No database release without verified forward migrations.
-   No production promotion without health checks and smoke tests.
-   No reopening feature development while critical production defects
    remain.
