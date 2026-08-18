# QuantPilot AI — Security Architecture

## 1. Authentication

### 1.1 Password Handling

| Aspect | Implementation |
|---|---|
| Library | `passlib` with bcrypt backend |
| Hash algorithm | bcrypt (adaptive cost) |
| Cost factor | 12 rounds (default) |
| Storage | `users.hashed_password` — VARCHAR(255) |

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

**Rules:**
- Plaintext passwords never stored, logged, or returned in API responses
- Password minimum length: 8 characters (Pydantic validation)

### 1.2 JWT Tokens

| Aspect | Implementation |
|---|---|
| Library | `python-jose` or `PyJWT` |
| Algorithm | HS256 |
| Secret | `JWT_SECRET_KEY` environment variable |
| Token type | Access token only (no refresh token in MVP) |
| Expiration | 30 minutes (configurable) |
| Payload | `{"sub": user_id, "exp": expiry_timestamp}` |

```python
def create_access_token(user_id: UUID) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> UUID:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return UUID(payload["sub"])
```

### 1.3 Protected Routes

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency that extracts and validates JWT."""
    try:
        user_id = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
```

All endpoints except `POST /auth/register` and `POST /auth/login` require authentication.

---

## 2. Authorization

### 2.1 Resource Ownership

Users can only access their own resources:

| Resource | Ownership Check |
|---|---|
| Strategies | `strategy.user_id == current_user.id` |
| Backtests | `backtest.strategy.user_id == current_user.id` (via strategy) |
| Documents | `document.user_id == current_user.id` |
| Conversations | `conversation.user_id == current_user.id` |

### 2.2 Implementation

Authorization checks are performed in the **service layer**, not in routes:

```python
class StrategyService:
    async def get(self, strategy_id: int, user_id: UUID) -> Strategy:
        strategy = await self.repo.get_by_id(strategy_id)
        if not strategy:
            raise NotFoundError("Strategy not found")
        if strategy.user_id != user_id:
            raise AuthorizationError("Not authorized to access this strategy")
        return strategy
```

### 2.3 Evaluation Endpoints

Evaluation questions are **system-owned** (not user-scoped). Evaluation endpoints may be unprotected or require a special admin flag. For MVP, evaluation endpoints are protected by standard JWT auth.

---

## 3. File Upload Security

### 3.1 Validation Rules

| Check | Rule |
|---|---|
| File type | MIME type must be `application/pdf` |
| Magic bytes | First bytes must match PDF signature (`%PDF`) |
| File size | Maximum 50 MB (configurable via `MAX_UPLOAD_SIZE_MB`) |
| Filename | Original filename stored for display only; never used in file path |
| Storage name | UUID-based: `{uuid4()}.pdf` |
| Storage path | Server-controlled directory; user input never influences path |

### 3.2 Path Traversal Prevention

```python
import uuid


def generate_safe_path(upload_dir: str) -> str:
    """Generate a safe storage path with no user-controlled components."""
    safe_name = f"{uuid.uuid4()}.pdf"
    return os.path.join(upload_dir, safe_name)
```

**Rules:**
- User-supplied filename is **never** used in filesystem operations
- Storage directory is a configured constant
- No relative paths, no `..`, no symlink following

### 3.3 Cleanup on Failure

If document processing fails:
1. Database records rolled back (chunks deleted)
2. Physical file deleted from filesystem
3. Document status set to FAILED

---

## 4. Secret Management

### 4.1 Environment Variables

| Secret | Env Var | Used By |
|---|---|---|
| JWT signing key | `JWT_SECRET_KEY` | API (auth) |
| Database URL | `DATABASE_URL` | API + Worker |
| Redis URL | `REDIS_URL` | API + Worker |
| Gemini API key | `GEMINI_API_KEY` | API + Worker |

### 4.2 Rules

- **No secrets in source code** — all secrets via environment variables
- **No secrets in Docker images** — use `.env` files or Docker secrets
- **`.env` in `.gitignore`** — never committed to Git
- **Example `.env.example`** — committed with placeholder values

```bash
# .env.example
JWT_SECRET_KEY=change-me-to-a-random-string
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/quantpilot
REDIS_URL=redis://redis:6379/0
GEMINI_API_KEY=your-gemini-api-key
```

### 4.3 Configuration Loading

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    jwt_secret_key: str
    jwt_expiration_minutes: int = 30
    database_url: str
    redis_url: str
    gemini_api_key: str
    gemini_model: str = "gemini-3.6-flash"
    max_upload_size_mb: int = 50
    upload_dir: str = "/app/uploads"

    class Config:
        env_file = ".env"
```

---

## 5. API Security

### 5.1 Request Validation

All request bodies are validated via Pydantic schemas:

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class CreateStrategyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    rules_json: dict  # Further validated by StrategyValidator
```

### 5.2 Safe Error Responses

```python
# Error response schema — never exposes internal details
class ErrorResponse(BaseModel):
    error: str  # Error category
    message: str  # User-safe message
    detail: dict | None  # Optional validation details


# Example: Internal error
{"error": "INTERNAL_ERROR", "message": "An unexpected error occurred", "detail": null}
# Note: stack trace logged server-side, never sent to client
```

### 5.3 Error Category Mapping

| Category | HTTP Status | When |
|---|---|---|
| `VALIDATION_ERROR` | 400 / 422 | Invalid input, bad parameters |
| `AUTHENTICATION_ERROR` | 401 | Invalid/expired token, bad credentials |
| `AUTHORIZATION_ERROR` | 403 | Accessing another user's resource |
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `CONFLICT` | 409 | Duplicate email registration |
| `DATA_PROVIDER_ERROR` | 502 | yfinance failure |
| `BACKTEST_ERROR` | 500 | Backtest execution failure |
| `AI_TOOL_ERROR` | 502 | LLM/embedding API failure |
| `DOCUMENT_PROCESSING_ERROR` | 500 | PDF extraction/embedding failure |
| `RETRIEVAL_ERROR` | 500 | Vector search failure |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## 6. Data Security

### 6.1 Sensitive Data Handling

| Data | Protection |
|---|---|
| Passwords | bcrypt hashed; never logged or returned |
| JWT tokens | Not stored server-side; not logged |
| API keys | Environment variables only; never logged |
| User documents | Stored with safe names; not publicly accessible |
| OHLCV data | Public data; no special protection |

### 6.2 Logging Security

Never log:
- Passwords (plain or hashed)
- JWT tokens
- API keys (Gemini, database credentials)
- Full document content (log filename and page count only)

Safe to log:
- User IDs
- Request IDs
- Operation names
- Error messages (sanitized)
- Durations
- Status codes

---

## 7. Arbitrary Code Execution Prevention

Since strategies use a **declarative JSON format** (not arbitrary Python code):
- No `eval()` or `exec()` on user input
- Strategy rules are parsed as structured data
- The StrategyInterpreter translates JSON to backtesting.py objects via a fixed mapping
- No user-uploaded code is executed
