# Architecture Overview

This document serves as a critical, living overview of the `instagram-toolkit` codebase architecture, enabling efficient navigation, clear understanding of core boundaries, and effective contributions.

---

## 1. Project Structure

The project follows a modular, single-package architecture separating CLI interface handlers, core domain services, storage persistence, caching, and OSINT integrations.

```
[Project Root]/
├── instagram_toolkit/            # Main application package
│   ├── cli/                      # Command-Line Interface layer
│   │   ├── handlers.py           # MenuHandlers controller for 16 interactive CLI operations
│   │   ├── menu.py               # CLI menu renderer & user selection loop
│   │   └── watch.py              # Follower/following monitoring watcher loop
│   ├── actions.py                # Batch management actions (mass unfollow, auto follow-back)
│   ├── auth.py                   # AuthService with 4-tier fallback authentication chain
│   ├── cache.py                  # RelationsCache with TTL and full/partial cache policies
│   ├── config.py                 # Config dataclass and environment variable resolution
│   ├── models.py                 # Domain dataclasses (User, RelationSnapshot, RelationDiff)
│   ├── rate_limiter.py           # RateLimiter with dynamic delays and jitter
│   ├── relations.py              # RelationsService for follower/following analysis
│   ├── storage.py                # HistoryStorage for JSON persistence & backup rotation
│   └── tracker.py                # FollowTracker for diff detection across historical snapshots
├── tests/                        # Offline pytest test suite (56 tests)
│   ├── test_actions.py           # Unit tests for batch management actions
│   ├── test_auth.py              # Unit tests for AuthService fallback chain
│   ├── test_cache.py             # Unit tests for RelationsCache TTL & invalidation
│   ├── test_config.py            # Unit tests for Config environment parsing
│   ├── test_osint_handler.py     # Unit tests for CLI OSINT handler & Toutatis integration
│   ├── test_relations_cache_policy.py   # Tests for partial vs complete relation caching
│   ├── test_relations_complete_fetch.py # Tests for sequential complete relations fetching
│   └── test_storage_rotate.py    # Tests for HistoryStorage backup rotation
├── plans/                        # Feature and refactoring implementation plans
├── docs/                         # Project documentation and Docusaurus website assets
├── .github/                      # GitHub Actions CI configurations
│   └── workflows/
│       └── tests.yml             # Test execution workflow (pytest via uv)
├── main.py                       # CLI entry point, argument parsing & dependency wiring
├── toutatis_integration.py       # Toutatis OSINT integration (obfuscated contact data)
├── pyproject.toml                # Project metadata, dependencies, and pytest configuration
├── uv.lock                       # Lockfile for reproducible dependency resolution
├── AGENTS.md                     # Agent skills configuration & project guidelines
├── README.md                     # Project overview and quick start guide
└── ARCHITECTURE.md               # Architecture documentation (this file)
```

---

## 2. High-Level System Diagram

```
                       ┌─────────────────────────┐
                       │   User (Terminal CLI)   │
                       └────────────┬────────────┘
                                    │
                                    ▼
                         ┌────────────────────┐
                         │      main.py       │
                         │ (CLI Entry Point)  │
                         └──────────┬─────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
┌──────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│   AuthService    │    │     MenuHandlers     │    │   Config / Env  │
│ (4-tier fallback)│    │  (16 Menu Operations)│    │  (config.py)    │
└──────────┬───────┘    └───────────┬──────────┘    └─────────────────┘
           │                        │
           ▼                        ├──────────────────────┐
┌──────────────────┐                ▼                      ▼
│ instagrapi Client│    ┌──────────────────────┐   ┌─────────────────┐
└──────────┬───────┘    │   RelationsService   │   │  FollowTracker  │
           │            └───────────┬──────────┘   └────────┬────────┘
           │                        │                       │
           │                        ▼                       ▼
           │            ┌──────────────────────┐   ┌─────────────────┐
           │            │    RelationsCache    │   │ HistoryStorage  │
           │            │  (In-Memory TTL)     │   │ (JSON Files &   │
           │            └──────────────────────┘   │  Rotation)      │
           │                                       └─────────────────┘
           ├────────────────────────┐
           ▼                        ▼
┌────────────────────┐    ┌────────────────────┐
│   Batch Actions    │    │toutatis_integration│
│ (Unfollow / Follow)│    │  (OSINT Endpoint)  │
└──────────┬─────────┘    └─────────┬──────────┘
           │                        │
           ▼                        │
┌────────────────────┐              │
│    RateLimiter     │              │
│  (Delay & Jitter)  │              │
└────────────────────┘              │
           │                        │
           ▼                        ▼
┌──────────────────────────────────────────────┐
│       Instagram Internal & Mobile API        │
└──────────────────────────────────────────────┘
```

---

## 3. Core Components

### 3.1. CLI Layer & Entry Point
* **Name**: CLI Engine (`main.py`, `instagram_toolkit/cli/`)
* **Description**: Parses command-line arguments, instantiates core services, displays the 16-option interactive menu (`menu.py`), routes user selections to handler methods (`handlers.py`), and executes monitoring loops (`watch.py`).
* **Technologies**: Python 3.12 standard library (`argparse`, `sys`, `time`).
* **Key Files**:
  * [main.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/main.py)
  * [handlers.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/instagram_toolkit/cli/handlers.py)
  * [menu.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/instagram_toolkit/cli/menu.py)

### 3.2. Authentication Service
* **Name**: `AuthService`
* **Description**: Handles Instagram authentication using a 4-tier fallback chain:
  1. Session ID (`INSTAGRAM_SESSION_ID`)
  2. Browser Cookies JSON file (`cookies.json`)
  3. Saved session file (`instagrapi.json`)
  4. Username / Password credentials (`INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD`)
* **Technologies**: `instagrapi.Client`, `json`.
* **Key Files**:
  * [auth.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/instagram_toolkit/auth.py)

### 3.3. Relations & Tracking Engine
* **Name**: `RelationsService`, `FollowTracker`, `RelationsCache`
* **Description**: Queries followers and followings (supporting both complete and partial limit fetches), compares profile lists to identify non-followers and mutual connections, computes diffs between historical snapshots, and caches relation lists in memory with TTL expiration.
* **Technologies**: Python dataclasses, `datetime`, `math`.
* **Key Files**:
  * [relations.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/instagram_toolkit/relations.py)
  * [cache.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/instagram_toolkit/cache.py)
  * [tracker.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/instagram_toolkit/tracker.py)

### 3.4. Batch Actions & Rate Limiting
* **Name**: Batch Actions Engine & `RateLimiter`
* **Description**: Executes automated bulk operations (mass unfollow, auto follow-back) with user confirmation gates, enforced delays with random jitter (1.8s–3.8s default), and automatic invalidation of cached relation lists when mutations occur.
* **Technologies**: Python standard library (`random`, `time`).
* **Key Files**:
  * [actions.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/instagram_toolkit/actions.py)
  * [rate_limiter.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/instagram_toolkit/rate_limiter.py)

### 3.5. OSINT Integration
* **Name**: `toutatis_integration`
* **Description**: Queries internal Instagram web and GraphQL endpoints using authenticated session tokens to retrieve partially masked contact information (email, phone number), WhatsApp link status, and creation metadata.
* **Technologies**: `requests.Session`, `phonenumbers`, `pycountry`.
* **Key Files**:
  * [toutatis_integration.py](file:///Users/gabrielramos/Developer/github/instagram-toolkit/toutatis_integration.py)

---

## 4. Data Stores

### 4.1. In-Memory Cache
* **Name**: `RelationsCache`
* **Type**: In-memory dictionary with TTL.
* **Purpose**: Avoids redundant network requests during an active CLI session. Supports independent tracking of `full` vs `partial` completeness and invalidation upon mutation.
* **Configuration**: `INSTAGRAM_CACHE_TTL` (default `300.0` seconds).

### 4.2. Local Storage & History
* **Name**: `HistoryStorage`
* **Type**: Local JSON files (`followers_history.json`, `instagrapi.json`, `cookies.json`, `history_backups/`).
* **Purpose**: Persists historical follower/following snapshots for diff analysis. Enforces automatic backup rotation when total snapshots exceed `MAX_SNAPSHOTS` (default 10).

---

## 5. External Integrations / APIs

* **Instagram Private Mobile API**:
  * **Provider**: Instagram / Meta
  * **Integration Method**: `instagrapi` Python library (`instagrapi.Client`)
  * **Purpose**: Primary profile queries, fetching followers/following, performing follow/unfollow actions.
* **Instagram Web API (Toutatis)**:
  * **Provider**: Instagram / Meta
  * **Integration Method**: Direct HTTP requests via `requests.Session` with custom Web App headers (`IG_APP_ID_WEB`, `IG_APP_ID_LOOKUP`)
  * **Purpose**: Querying OSINT profile metadata and masked contact details.

---

## 6. Deployment & Infrastructure

* **Runtime Environment**: Local CLI (Python 3.12+).
* **Dependency & Environment Manager**: `uv` (`pyproject.toml`, `uv.lock`).
* **CI/CD Pipeline**: GitHub Actions ([.github/workflows/tests.yml](file:///Users/gabrielramos/Developer/github/instagram-toolkit/.github/workflows/tests.yml)).
  * Triggers on `push` to `main` and `pull_request`.
  * Executes `uv sync && uv run pytest -q`.
* **Documentation Site**: Docusaurus site under `website/` (hosted on GitHub Pages).

---

## 7. Security Considerations

* **Credential Management**: Environment variables via `.env` (`INSTAGRAM_USERNAME`, `INSTAGRAM_PASSWORD`, `INSTAGRAM_SESSION_ID`). Session IDs are preferred over raw credentials to minimize challenge triggers.
* **Session Persistence**: Session tokens and settings are cached locally in `instagrapi.json` and `cookies.json` to prevent unnecessary re-authentication.
* **Rate Limiting & Account Safety**: Enforces conservative request pacing (`RateLimiter`) with randomized jitter to mitigate Instagram anti-automation flags and HTTP 429 errors.

---

## 8. Development & Testing Environment

* **Local Environment Setup**:
  ```bash
  uv sync
  ```
* **Testing Framework**: `pytest`
  ```bash
  uv run pytest -v
  ```
  *(56 offline unit and integration tests covering authentication, caching, relations, batch actions, and OSINT handlers).*

---

## 9. Future Considerations / Roadmap

* **Async / Concurrent Processing**: Potential migration of independent network calls to `asyncio`.
* **Multi-Account Management**: Support for switching between multiple stored credentials/sessions.
* **Resilient Rate Limiting**: Exponential backoff and challenge detection handling.

---

## 10. Project Identification

* **Project Name**: `instagram-toolkit`
* **Repository URL**: `https://github.com/prof-ramos/instagram-toolkit`
* **Primary Contact / Maintainer**: `prof-ramos`
* **Date of Last Update**: `2026-07-21`

---

## 11. Glossary / Acronyms

* **OSINT**: Open Source Intelligence (gathering publicly or internally accessible profile metadata).
* **TTL**: Time To Live (expiration duration in seconds for cached entries).
* **instagrapi**: Python library for interacting with Instagram's Private API.
* **Toutatis**: Open-source OSINT tool mechanism for extracting hidden contact details from Instagram accounts.
