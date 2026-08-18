# QuantPilot AI — Phase 1 Report (SDE Foundation)

## 1. Objective
Build the core SDE infrastructure for authentication, including user registration, secure password hashing, JWT-based login, protected routes, database migrations (Alembic), and repository/service patterns with Pydantic schemas. 

## 2. Implementation Summary
- **User Model**: Mapped via SQLAlchemy to the `users` table with fields `id` (UUID), `email` (indexed, unique), `hashed_password`, and `created_at`.
- **Database Migrations**: Created Alembic migration `create_users_table`.
- **Security Logic**: Integrated `passlib[bcrypt]` and `PyJWT` to securely hash passwords and generate/validate JWTs.
- **Hexagonal Architecture**: 
  - `UserRepository` created to handle isolated persistence interactions.
  - `AuthService` created to handle business logic (duplicate checks, hashing, verification).
- **API Endpoints**: 
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me` (Protected)

## 3. Database Changes
- Migrated and created the `users` table exactly matching the approved `DATABASE_DESIGN.md`. We ensured that `updated_at` was excluded as strictly mandated by the instruction.

## 4. Testing Strategy
- Implemented `pytest-asyncio` configured with a separate isolated database `quantpilot_test` using `NullPool` to prevent connection leaks.
- Fixtures create and drop tables freshly per test to prevent side-effects from failed transactions.
- Tested duplicate emails, invalid passwords, expired/invalid JWTs, and successful authentication flows.
- Automated API validation tested via `curl` against running `api` docker container.
- Proved PostgreSQL persistence: A registered user remained active after restarting the `api` container.

## 5. Security
- Plaintext passwords are never stored. Passwords are intentionally hashed via bcrypt.
- JWT algorithm configuration uses strict verification matching `jwt_algorithm` set via environment variables.

## 6. CI Verification
- **Pytest**: `8 passed` out of 8 tests.
- **Ruff**: `All checks passed!` after configuring formatting on newly introduced schemas, dependencies, and imports.
- **Docker**: The Docker build succeeded and containers successfully executed endpoints via cURL.

## 7. Known Issues / Technical Debt
- Due to a known compatibility bug between passlib and newer versions of `bcrypt`, we temporarily pinned `bcrypt<4.0.0` in `pyproject.toml`.

## 8. Interview Concepts Demonstrated
- **Hexagonal / Clean Architecture**: Demonstrated separation of API endpoints, business logic (`AuthService`), and persistence bounds (`UserRepository`).
- **Secure Password Hashing & JWT**: Showcased real-world Auth implementation that doesn't rely on massive third-party packages, highlighting core web-security concepts (JWT encoding/decoding, secure HTTP responses).
- **Database Testing Strategies**: Explored and implemented robust fixture-based automated tests on a secondary PostgreSQL DB without blowing up the main dev DB, mitigating dirty state `InterfaceError`s.

## 9. Next Phase Prerequisites
- All components for Phase 1 are tested and integrated.
- We are ready for **Phase 2 (Market Data + OHLCV + Indicators)**.
