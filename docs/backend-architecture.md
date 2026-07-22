# Backend Architecture

FlipRadar backend code lives under the `flipradar` package namespace.

## Layers

- `flipradar.main` builds the FastAPI application and wires routers.
- `flipradar.api.routes` owns HTTP routes, request dependencies, response models, logging around requests, and HTTP error translation.
- `flipradar.api.schemas` owns request and response schemas plus shared API validation types.
- `flipradar.api.dependencies` owns authentication and FastAPI dependency functions.
- `flipradar.services` owns application workflows and use-case logic.
- `flipradar.integrations` owns provider clients and external-system adapters.
- `flipradar.domain.models` owns SQLAlchemy ORM models.
- `flipradar.domain.engines` owns deterministic business decision engines.
- `flipradar.database` owns engine/session setup, repositories, custom SQLAlchemy types, and Alembic migrations.
- `flipradar.core` owns settings, logging, exceptions, constants, and cross-cutting utilities.

## Allowed Dependency Directions

- API routes may depend on API schemas, API dependencies, services, and domain types needed for response annotations.
- API routes should not issue SQLAlchemy queries directly; route handlers call services.
- Services may depend on repositories, database sessions, domain models, domain engines, integrations, API schemas, and core utilities.
- Integrations may depend on API validation helpers and core settings/logging, but not on API routes.
- Domain engines should stay deterministic and independent from FastAPI, SQLAlchemy sessions, and provider clients.
- Domain models may depend on database base/types, but not on services, routes, or integrations.
- Database repositories may depend on domain models, API validation helpers, and SQLAlchemy.
- Core modules should not depend on API routes, services, integrations, domain engines, or repositories.

When adding new code, keep dependencies moving from outer orchestration layers toward inner domain/data layers, not the reverse.
