
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
7. Ensure email failures produce controlled user-facing behavior and useful server logs. 
8. Verify production emails do not contain localhost, staging, or development links.

PHASE 9 — DATABASE INTEGRITY AND MIGRATION CERTIFICATION 
1. Create a completely empty PostgreSQL database using the production PostgreSQL major version. 
2. Run alembic upgrade head from zero and verify every migration completes successfully. 
3. Boot the API against the newly migrated database. 
4. Seed or create representative users, sets, listings, portfolio positions, snapshots, and watchlist data. 
5. Verify foreign-key delete and cascade behavior for user-owned and marketplace data. 
6. Audit monetary values, prices, quantities, and calculations for appropriate Decimal/numeric storage instead of unsafe floating-point persistence. 
7. Verify required indexes exist for common search, lookup, portfolio, marketplace, and snapshot queries. 
8. Test forward migration using a copy of representative populated data. 
9. Document backup/restore expectations and the handling of migrations that intentionally cannot be downgraded.

PHASE 10 — SECRETS AND PRODUCTION CONFIGURATION 
1. Define the complete production environment-variable contract in one documented location. 
2. Generate a strong production JWT secret and ensure no development/default secret is accepted. 
3. Configure the production PostgreSQL connection with required SSL. 
4. Configure production Redis and external-provider credentials. 
5. Set explicit production frontend URL and CORS origins with no wildcard origins. 
6. Configure release/version identifiers used by logs and error reporting. 
7. Store all production secrets in the deployment platform or GitHub Environment secret store. 
8. Scan the repository and Git history for accidentally committed secrets or credentials and rotate anything exposed. 
9. Validate the complete production configuration in CI or staging without exposing secret values.

======================================================================
MILESTONE 3 — BUILD THE RELEASE MACHINE Priority: HIGH Goal: Establish
staging, observability, production-equivalent containers, and a
controlled deployment path.
======================================================================

PHASE 11 — PRODUCTION CONTAINER CERTIFICATION 
1. Build the backend using the actual production Dockerfile target rather than development Compose behavior. 
2. Build the frontend using the actual production nginx/static build target. 
3. Run both production images locally or in CI without source-code bind mounts. 
4. Boot the backend with production-like environment validation enabled. 
5. Verify /health/live and /health/ready correctly distinguish process health from dependency readiness. 
6. Verify frontend routing, static assets, and /api proxy behavior using the production container. 
7. Verify graceful startup and shutdown behavior for the API container. 
8. Record final container ports, required environment variables, volumes, and service dependencies.

PHASE 12 — STAGING ENVIRONMENT 
1. Provision a staging frontend, API service, PostgreSQL database, and Redis instance. 
2. Configure staging with separate credentials, secrets, databases, and provider configuration from production. 
3. Deploy the exact production Docker images to staging. 
4. Run Alembic migrations as an explicit staging release step. 
5. Configure staging frontend/API URLs, CORS, HTTPS, and proxy behavior. 
6. Connect staging to safe but realistic marketplace/provider services or credentials. 
7. Perform account creation, authentication, catalog lookup, marketplace lookup, and portfolio operations in staging. 
8. Keep staging configuration structurally equivalent to production so deployment differences are minimal.

PHASE 13 — OBSERVABILITY AND FAILURE VISIBILITY 
1. Configure backend Sentry/error reporting for staging. 
2. Configure frontend error reporting for staging. 
3. Set APP_RELEASE and equivalent frontend release identifiers during builds/deployments. 
4. Trigger a controlled backend exception and verify it reaches the error-reporting system. 
5. Trigger a controlled frontend exception and verify it reaches the error-reporting system. 
6. Verify logs contain useful request/release context without leaking passwords, tokens, or secrets. 
7. Add basic alerting for repeated server errors and service-health failures. 
8. Repeat the configuration for production only after staging verification succeeds.

PHASE 14 — SECURITY HEADERS AND EDGE CONFIGURATION 
1. Ensure all staging and production traffic is HTTPS-only. 
2. Add X-Content-Type-Options and appropriate frame-embedding protection. 
3. Add an appropriate Referrer-Policy. 
4. Define and test a Content-Security-Policy compatible with the frontend and required external services. 
5. Enable HSTS only after HTTPS and domain configuration are confirmed correct. 
6. Configure sensible API request/body-size and proxy timeout limits. 
7. Configure caching/compression for versioned frontend static assets. 
8. Run a final browser/network inspection to verify headers are actually present on deployed responses.

PHASE 15 — POST-DEPLOYMENT SMOKE TESTS 
1. Create an automated check for the deployed frontend root page. 
2. Check backend /health/live. 
3. Check backend /health/ready and database connectivity. 
4. Authenticate using a dedicated staging smoke-test account. 
5. Call /users/me or another simple protected endpoint. 
6. Perform one representative catalog/set lookup. 
7. Perform one protected portfolio read/write operation. 
8. Exercise one real marketplace/provider request without mock fallback. 
9. Make the smoke suite return a non-zero exit status when any critical check fails.

PHASE 16 — CONTINUOUS DEPLOYMENT WORKFLOW 
1. Create a deployment workflow separate from CI. 
2. Require the complete CI workflow to succeed before deployment is eligible. 
3. Build/tag immutable release images using commit SHA or another unique release identifier. 
4. Deploy the release to staging first. 
5. Run database migrations as an explicit controlled release step. 
6. Run the automated staging smoke suite after deployment. 
7. Require manual approval through a protected production GitHub Environment before production promotion. 
8. Promote the same tested release/image artifact to production rather than rebuilding it.
9. Run production health checks and a safe production smoke suite immediately after promotion. 
10. Document the rollback procedure for a failed application release.

======================================================================
MILESTONE 4 — PRODUCTION LAUNCH Priority: RELEASE GATE Goal: Deploy the
smallest reliable FlipRadar production footprint and verify it before
opening access.
======================================================================

PHASE 17 — MINIMUM PRODUCTION INFRASTRUCTURE 1. Provision the production
frontend hosting/runtime. 2. Provision the production FastAPI service.
3. Provision managed production PostgreSQL with backups enabled. 4.
Provision managed Redis if required by rate limiting or active runtime
features. 5. Configure production domains, DNS, HTTPS certificates, and
API routing. 6. Install production secrets and environment
configuration. 7. Verify network access rules allow only required
service-to-service communication. 8. Confirm database backup retention
and basic restore capability before user data is accepted.

PHASE 18 — WORKER AND BACKGROUND-JOB DECISION 1. Inventory every feature
that requires Celery, Redis queues, scheduled jobs, or watchlist
workers. 2. Separate launch-critical background functionality from
features that can remain disabled. 3. Keep nonessential workers disabled
for the initial production release. 4. If a worker is launch-critical,
deploy it using the same release/version as the API. 5. Configure worker
concurrency, retry behavior, timeouts, and queue names conservatively.
6. Verify failed jobs cannot create duplicate listings, snapshots,
notifications, or portfolio mutations. 7. Add worker health/error
monitoring before enabling automated schedules. 8. Document which
background features are intentionally disabled at launch.

PHASE 19 — RELEASE CANDIDATE 1. Stop merging non-release changes while
the release candidate is being certified. 2. Run the entire CI suite
from a clean environment. 3. Deploy the exact release candidate to
staging. 4. Run all Alembic migrations and the complete staging smoke
suite. 5. Manually test registration, login, verification, reset,
marketplace lookup, catalog data, and portfolio functionality. 6. Verify
production mock-data guards, internal-route protections, rate limits,
and security headers. 7. Verify Sentry/logging receives release-tagged
events correctly. 8. Record the approved release commit/image
identifiers. 9. Approve the release only when no unresolved P0 or P1
launch blockers remain.

PHASE 20 — CONTROLLED PRODUCTION DEPLOYMENT 1. Create or verify the
production database backup immediately before the release. 2. Promote
the approved release candidate to production. 3. Run production database
migrations before routing normal application traffic when required by
the deployment model. 4. Verify /health/live and /health/ready
immediately after API startup. 5. Verify the frontend loads correctly
over the production domain and communicates with the production API. 6.
Run the safe production smoke-test suite. 7. Verify real marketplace
data is returned and no mock provider can execute. 8. Verify
authentication, email, rate limiting, logs, and error reporting are
functioning. 9. Keep the initial release controlled/private until the
verification pass is complete. 10. Record the deployed release
identifier and deployment outcome.

======================================================================
MILESTONE 5 — STABILIZE BEFORE RESUMING DEVELOPMENT Priority:
POST-LAUNCH Goal: Prove production is boring before feature development
starts again.
======================================================================

PHASE 21 — FIRST-WEEK PRODUCTION STABILIZATION 1. Review backend errors,
frontend errors, failed requests, and provider failures daily. 2. Review
database performance and identify obviously slow or repeatedly executed
queries. 3. Review authentication failures and rate-limit activity for
abuse or false positives. 4. Verify marketplace data quality against the
upstream providers using representative sets/items. 5. Verify portfolio
valuation results using known manual calculations and representative
user scenarios. 6. Review email delivery failures, bounces, and broken
account-lifecycle links. 7. Fix production defects before accepting
feature work into main. 8. Keep a short production-issues log with
severity, root cause, fix, and release version.

PHASE 22 — CI/CD AND OPERATIONS HARDENING 1. Add automated dependency
vulnerability scanning for Python and npm dependencies. 2. Enable
automated dependency-update pull requests with CI validation. 3. Add
repository secret scanning and review any detected historical exposure.
4. Add container-image vulnerability scanning to the release pipeline.
5. Add database backup/restore drills on a reasonable recurring
schedule. 6. Review deployment duration, failure points, and manual
steps from the first production releases. 7. Automate safe repetitive
release steps without removing the production approval gate prematurely.
8. Update deployment/runbook documentation to reflect what actually
worked in production.

PHASE 23 — REPOSITORY AND DOCUMENTATION CLEANUP 1. Replace
machine-specific absolute paths in README files with repository-relative
links. 2. Remove stale setup instructions and development commands that
no longer match the production-ready toolchain. 3. Clearly mark TODOs.md
as archived historical planning material or move it into an archive
directory. 4. Document local development, testing, CI, staging, and
production workflows separately. 5. Document marketplace provider
architecture and the rule prohibiting mock providers in production. 6.
Document required services, environment variables, migrations, and
release procedures. 7. Remove dead code, obsolete configuration, unused
mock wiring, and abandoned deployment experiments only after confirming
they are unused. 8. Run the complete CI suite after repository cleanup
to ensure documentation/code cleanup did not disturb release behavior.

PHASE 24 — DEVELOPMENT REOPENING GATE 1. Require production to remain
stable through the agreed stabilization window. 2. Require no unresolved
critical security, data-integrity, authentication, or deployment
defects. 3. Confirm CI and staging deployments are consistently
reproducible. 4. Confirm production backups, monitoring, email, provider
integrations, and rate limits are operating normally. 5. Review deferred
work from the old TODOs.md and discard items that are no longer
strategically useful. 6. Create a new post-launch product roadmap based
on actual production usage rather than the old implementation sequence.
7. Separate technical-debt work from new product features in the new
roadmap. 8. Resume feature development only after the
production-readiness gate is formally considered complete.

======================================================================
EXECUTION ORDER — DO NOT SKIP AHEAD
======================================================================

Milestone 0: Phase 0 -> Phase 1 -> Phase 2

Milestone 1: Phase 3 -> Phase 4 -> Phase 5 -> Phase 6

Milestone 2: Phase 7 -> Phase 8 -> Phase 9 -> Phase 10

Milestone 3: Phase 11 -> Phase 12 -> Phase 13 -> Phase 14 -> Phase 15 ->
Phase 16

Milestone 4: Phase 17 -> Phase 18 -> Phase 19 -> Phase 20

Milestone 5: Phase 21 -> Phase 22 -> Phase 23 -> Phase 24

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
