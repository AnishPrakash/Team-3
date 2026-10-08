# Team 3 Backend Handbook — Modules D, E, F and K

**Project:** Flutter Wars (GDG on Campus VIT Chennai) · backend `server/` for `github.com/gdg-vitc/flutter-wars`
**Modules owned by Team 3:**
- **D** Widget Catalog (teammate)
- **E** Credit Ledger & Wallet (Anish)
- **F** Team Widget Inventory (Anish)
- **K** Organizer/Admin Control Plane (Anish)

**Spec:** *GDG Flutter Workshop — Final Modular Backend Architecture* v1.0
**Stack (spec §1, FINAL):** Python 3.11+ · FastAPI · SQLModel · PostgreSQL (Neon in production) · Alembic migrations

> **Status of the folder `Team3_DEFK_server/`**
> - **158 tests pass** on PostgreSQL 16: D 26 · E 37 · F 24 · K 71. All 8 of your teammate's original Module D tests are ported and still pass. The archive test was split in two, so 9 tests carry the `(teammate)` mark.
> - All parallel-request ("race") tests passed **20 runs in a row**.
> - Migrations `0001 → 0005` go up and down cleanly. There is exactly one Alembic head (`0005_admin`).
> - `ruff check` and `ruff format --check` are clean (74 files).
> - The 3-PR split in §2.6 was rehearsed with the exact commands in that section:
>   - PR 1 (D) → 26 tests pass
>   - PR 2 (D+E+F) → 87 tests pass
>   - PR 3 (D+E+F+K) → 158 tests pass, and its tree is identical to this folder
> - Tested from a **fresh** `pip install -e ".[dev]"`: Python 3.13, FastAPI 0.142, SQLModel 0.0.48, SQLAlchemy 2.1 and 2.0, psycopg 3.3, Pydantic 2.13, Alembic 1.20, pytest 9.1, ruff 0.16.
>
> **This handbook replaces the earlier `Modules_E_F_Complete_Build_Guide.md` and `Module_K_Admin_Control_Plane_Build_Guide.md` wherever they differ:**
> - Migrations were renumbered so the catalog comes first: `0002_catalog`, `0003_ledger`, `0004_inventory`, `0005_admin`.
> - The temporary `widget` table is gone (Module D owns the real one).
> - `pyproject.toml` gained a build section. The old `pip install -e` step failed.
> - The K guide's event-day runbook still applies unchanged; the routes are the same.

---

## Contents

1. [What we have built](#1-what-we-have-built)
   - [1.1 The big picture](#11-the-big-picture)
   - [1.2 Folder map](#12-folder-map)
   - [1.3 Rules every file follows](#13-rules-every-file-follows)
   - [1.4 Every file explained](#14-every-file-explained)
   - [1.5 How Module D was merged (what changed from the teammate's version, and why)](#15-how-module-d-was-merged)
   - [1.6 All 34 HTTP routes](#16-all-34-http-routes)
   - [1.7 Internal contracts other teams call](#17-internal-contracts-other-teams-call)
   - [1.8 Error codes](#18-error-codes)
2. [Terminal commands: test, run, and merge into the main repo](#2-terminal-commands)
3. [What we need from other teams, and what changes in our code](#3-what-we-need-from-other-teams)
4. [Anything extra you may have missed](#4-anything-extra-you-may-have-missed)
5. [Comparison with the specification document](#5-comparison-with-the-specification-document)

---

## 1. What we have built

### 1.1 The big picture

The backend is the **single source of truth** (spec §1.1). The Flutter app and the AppDev IDE only send *intents* ("buy listing X", "show my wallet"). The server decides everything and stores it in PostgreSQL.

| Module | Question it answers | Tables it owns | Who calls it |
|---|---|---|---|
| **D Catalog** | "Which widgets exist, and what are they called?" | `widget` | F, G, H, I, J, C, K |
| **E Ledger** | "How many credits does team T have, and where did each credit come from?" | `team_wallet`, `credit_ledger_entry`, `credit_reservation` | I, J, K |
| **F Inventory** | "How many of widget W does team T own?" | `team_widget_inventory`, `inventory_event` | I, J, C, K |
| **K Admin** | "Who is an organizer, what may they do, what did they do, is trading paused?" | `organizer`, `admin_action_log`, `operational_control` | organizers; I and J (freeze check); every module's admin routes |

**Who imports whom.** Arrows point at what a module uses. There are no cycles, which is what makes the 3-PR plan in §2.6 possible:
```
                    app/core   (TEMP stand-ins for Module A + B)
                  ↑     ↑     ↑
   D catalog ─────┘     │     │          D imports nothing from E, F or K
       ↑                │     │
   F inventory ─────────┘     │          F imports D (widget names), nothing else
                              │
   E ledger ──────────────────┘          E imports nothing from D, F or K
       ↑      ↑      ↑
       └──── K admin ┘──→ ports ← B registers TeamDirectory, G market status, I transaction feed
             ↑     ↑
   I, J call ensure_not_frozen()    C, G, H, J admin routes call require_permission() + audit()
```

**One purchase, as Module I (Team 2) will write it, using our contracts:**
```
1. admin.ensure_not_frozen(s, "TRADING")      K  shared lock on the pause switch; 423 if paused
2. market.lock_listing(...)                    G  (Team 2)
3. catalog.require_active_widget(s, wid)       D  409 if the widget is archived
4. ledger.debit(s, team, price*qty, ref)       E  conditional UPDATE; 409 if not enough credits
5. inventory.increment(s, team, wid, qty, ref) F  upsert + event row
6. s.commit()                                  ONE commit: everything or nothing
```

**One organizer action, end to end** (`POST /admin/teams/{id}/credits`):
```
Module B identity (Google-verified email)
  → K require_permission(CREDITS_ADJUST): organizer row looked up on THIS request, role checked
  → strict body validation (int amount, reason, idempotency key)
  → E ledger.admin_adjust(...)  (E's rules: duplicate check, locked UPDATE, ledger row)
  → K audit(...)                (append-only audit row)
  → COMMIT                      (ledger row + audit row together, or neither)
```

### 1.2 Folder map

```
Team3_DEFK_server/
├── Team3_Modules_D_E_F_K_Handbook.md     this file
├── pr_stage_mains/                       app/main.py for each stacked PR (see §2.6)
│   ├── main_stage1_D.py
│   ├── main_stage2_DEF.py
│   └── main_stage3_DEFK.py               (= server/app/main.py)
└── server/
    ├── pyproject.toml · alembic.ini · .env.example · .gitignore
    ├── app/
    │   ├── main.py                       TEMP local app (Module A will own the real one)
    │   ├── core/                         TEMP stand-ins for Module A and Module B
    │   │   ├── db.py  errors.py  auth.py  _temp_models.py  _temp_team_directory.py
    │   └── modules/
    │       ├── catalog/                  MODULE D  (7 files)
    │       ├── ledger/                   MODULE E  (7 files)
    │       ├── inventory/                MODULE F  (7 files)
    │       └── admin/                    MODULE K  (13 files)
    ├── migrations/
    │   ├── env.py  script.py.mako
    │   └── versions/
    │       ├── 0001_temp_team_stub.py    TEMP  team table (Module B's)
    │       ├── 0002_catalog.py           D     widget
    │       ├── 0003_ledger.py            E     team_wallet, credit_ledger_entry, credit_reservation
    │       ├── 0004_inventory.py         F     team_widget_inventory, inventory_event
    │       └── 0005_admin.py             K     organizer, admin_action_log, operational_control
    └── tests/
        ├── conftest.py                   shared fixtures (real Postgres, fresh teams/widgets, fake login)
        ├── catalog/    3 files, 26 tests (D)
        ├── ledger/     3 files, 37 tests (E)
        ├── inventory/  4 files, 24 tests (F, incl. 1 D×E×F history test)
        └── admin/      conftest + 8 files, 71 tests (K, incl. D/E/F organizer routes)
```

Every module folder has the **same 7 files**:

| File | Job | Allowed to |
|---|---|---|
| `models.py` | SQLModel tables (mirror the migration exactly) | declare columns/constraints |
| `errors.py` | error classes with stable codes | — |
| `repository.py` | SQL only | read/write its **own** tables; never commit |
| `service.py` | business rules = the **internal contract** | call its repository and other modules' `__init__` contracts; never commit |
| `schemas.py` | request/response shapes (Pydantic) | validate, never touch the DB |
| `router.py` | HTTP: auth + validation + 1 service call + commit | commit once |
| `__init__.py` | the only names other modules may import | — |

### 1.3 Rules every file follows

1. **Layers:** routes are thin, rules live in `service.py`, SQL lives in `repository.py`.
2. **Internal functions never commit.** They `flush()`. Whoever opened the transaction commits it once: our routes, or Module I/J. If anything raises, the caller rolls back **everything**.
3. **Money and quantities are `int`.** `True`, `10.0` and `"10"` are rejected (422).
4. **The team always comes from the login token** (`principal.team_id`), never from the URL or body on participant routes.
5. **One owner per table** (spec §2). Other modules go through the owner's `__init__.py` contract, or a port (K).
6. **Lock order** inside any transaction: `operational_control → market_listing → team_wallet → team_widget_inventory`. Same order everywhere means no deadlocks.
7. **Duplicates are stopped by the database:**
   - ledger: `UNIQUE(team, ref_type, ref_id, kind)`
   - inventory: `UNIQUE(team, widget, ref_type, ref_id, kind)`
   - organizer edits: an `idempotency_key` UUID
   - widget edits and organizer changes: an `expected_version`
8. **History is append-only:** a DB trigger blocks UPDATE/DELETE/TRUNCATE on the ledger, inventory events and the audit log. Widgets can never be deleted (only archived), and their `id`/`appdev_key` can never change.
9. **One error shape everywhere** (spec §2.2): `{"error": {"code", "message", "details"}}`. That includes request-validation errors (`VALIDATION_ERROR`), which never echo the submitted input back.

### 1.4 Every file explained

#### Project configuration

| File | What it does |
|---|---|
| `pyproject.toml` | Dependencies (fastapi, sqlmodel, psycopg 3, alembic; dev: pytest, httpx, ruff). Pytest finds `tests/`. Ruff: line length 120, rules E/F/I/B/UP; `B008` is ignored because `Depends()` in defaults is FastAPI's normal pattern. Python ≥ 3.11 (your teammate used 3.14, which works too). |
| `alembic.ini` | Points Alembic at `migrations/`. The database URL is **not** in this file; it comes from the `DATABASE_URL` environment variable. |
| `.env.example` | Template for `DATABASE_URL` (dev DB) and `TEST_DATABASE_URL` (test DB). Copy it to `.env`, which is git-ignored. Nothing loads `.env` automatically: `export` the variables (§2.2). |
| `.gitignore` | Ignores `.env*` (except `.env.example`), caches, `.venv/`, and `*.db` / `*.sqlite3`. That last pair is so the old SQLite `catalog.db` can never be committed. |

#### `app/main.py` (TEMP)
- The local FastAPI app. Registers the shared error handlers and **7 routers**:
  - D: `/widgets`
  - E: `/wallet`
  - F: `/inventory`
  - K: `/controls`, `/admin/...`, `/admin/teams/{id}/wallet|credits|inventory`, `/admin/widgets`
- Plugs the TEMP team directory into K's port.
- When Module A merges, this file is deleted and the same routers and port line are registered through A's mechanism.

#### `app/core/` (TEMP, all replaced by Modules A and B)

| File | Stands in for | What it does |
|---|---|---|
| `db.py` | Module A | `engine` from `DATABASE_URL` (pool 10 + overflow 20, `pool_pre_ping`). `get_db()` yields one `Session` per request and rolls back on any exception. |
| `errors.py` | Module A | `AppError(code, message, status_code, details)` plus two handlers: one for `AppError`, and one turning FastAPI validation errors into the same envelope with code `VALIDATION_ERROR` (only `loc`, `msg`, `type`; never the input). |
| `auth.py` | Module B | `Principal(user_id, email, team_id)`: **identity only**. `get_principal()` refuses every request (501) until B lands; tests replace it. `require_participant` → 403 `NOT_A_TEAM_MEMBER` if there is no team. **No organizer logic here**; K owns that. |
| `_temp_models.py` | Module B | Minimal `Team` model (id, unique name, status ACTIVE/DISABLED, created_at), so foreign keys resolve. |
| `_temp_team_directory.py` | Module B | Implements K's `TeamDirectory` port (list/get/find/create/set_status) over the temp `team` table. |

#### `migrations/`

| File | What it does |
|---|---|
| `env.py` | Runs migrations using `DATABASE_URL`. **Auto-discovers** every `app/modules/*/models.py`, so a new module needs no edit here. A real import error inside a `models.py` is still raised, not hidden. |
| `script.py.mako` | Template for future `alembic revision` files. |
| `0001_temp_team_stub.py` | **TEMP.** Creates `team`. Delete when Module B's migration exists; then point `0002_catalog`'s `down_revision` at B's head. |
| `0002_catalog.py` | **D.** `widget` table. See "Module D" below for every constraint. Triggers `trg_widget_identity_immutable` (id/appdev_key can't change), `trg_widget_no_delete` and `trg_widget_no_truncate`, backed by the functions `fw_widget_identity_immutable()` and `fw_widget_no_delete()`. |
| `0003_ledger.py` | **E.** Creates the shared `fw_forbid_mutation()` trigger function plus `team_wallet`, `credit_ledger_entry` (append-only) and `credit_reservation`. |
| `0004_inventory.py` | **F.** `team_widget_inventory` (`quantity ≥ 0`) and `inventory_event` (append-only). FKs to `team` and `widget` with `ON DELETE RESTRICT`. |
| `0005_admin.py` | **K.** `organizer`, `admin_action_log` (append-only, non-blank reason, `details` must be a JSON object) and `operational_control`. That last table is seeded with `ALL`/`TRADING`/`BIDDING` rows, which can't be deleted. |

#### Module D — `app/modules/catalog/` (Widget Catalog)

| File | What it does |
|---|---|
| `models.py` | `Widget` table. Columns: `id` (slug `^[a-z][a-z0-9_]{1,39}$`), `appdev_key` (unique, max 80), `display_name` (≤60), `description` (≤500), `category` (≤30), `flutter_classes` (JSONB array), `is_free`, `free_quantity` (only when free, 0–10,000), `status` (ACTIVE/ARCHIVED), `internal_notes` (≤1000), `version`, `created_at`/`updated_at`/`archived_at` (DB clock). DB CHECKs: id format; status values; `archived_at` set **iff** archived; free-quantity rule; JSON is an array; version ≥ 1. Property `archived`. |
| `errors.py` | `WIDGET_NOT_FOUND` 404 · `WIDGET_ARCHIVED` 409 · `WIDGET_NOT_ARCHIVED` 409 · `WIDGET_DUPLICATE` 409 (`details.field` = id or appdev_key) · `FIELD_IMMUTABLE` 422 · `VERSION_CONFLICT` 409 (`details.current_version`) · `INVALID_WIDGET_DATA` 422. |
| `repository.py` | `get` · `get_for_update` (row lock, so two organizers editing one widget are serialized) · `get_many` (batch, **one query** for any number of ids) · `id_exists` · `appdev_key_exists` · `list_widgets` (sorted category → name → id) · `insert` (inside a SAVEPOINT, so a duplicate race becomes a clean 409) · `save` (version + 1, DB timestamp) · `now`. |
| `service.py` | **The contract.** Reads: `get_widget` (any status, for resolving **history**), `require_active_widget` (for **selling**: G/I/J), `get_widgets` (batch), `widget_exists`, `list_widgets`. Changes: `create_widget`, `update_widget(changes, expected_version)` → `(widget, diff)`, `archive_widget`, `restore_widget`. Rules: id/appdev_key immutable; required fields can't be nulled; unknown fields rejected; free-quantity rule; archived widgets can't be edited until restored; a no-op edit doesn't bump the version. Catalog never stores price, stock or ownership. |
| `schemas.py` | `WidgetPublicOut` (participant-safe: no notes, no version, no timestamps; has an `archived` flag). `WidgetAdminOut` (everything). `WidgetCreateIn`: strict, unknown fields rejected. Display name/description are trimmed and refuse `<`, `>` and control characters. `flutter_classes` must be Dart class names (`Row`, `IconButton`), max 20, de-duplicated. `WidgetUpdateIn`: `expected_version` required; accepts `id`/`appdev_key` **only** to answer `FIELD_IMMUTABLE` clearly. `WidgetArchiveIn` (`expected_version`, `reason`, `confirm` = the widget id typed). `WidgetRestoreIn`. |
| `router.py` | Participant routes. `GET /widgets` returns active widgets only. `GET /widgets/{id}` also resolves archived widgets (`archived: true`), so a team that owns one can still see what it is. Both need a login (any user, participant or organizer). |
| `__init__.py` | Exports `Widget`, `WidgetStatus`, `get_widget`, `get_widgets`, `require_active_widget`, `widget_exists`, `list_widgets`, `create_widget`, `update_widget`, `archive_widget`, `restore_widget`. |

#### Module E — `app/modules/ledger/` (Credit Ledger & Wallet)

| File | What it does |
|---|---|
| `models.py` | `TeamWallet(balance, held)` with CHECKs `balance ≥ 0`, `held ≥ 0`, `held ≤ balance`; **available = balance − held**. `CreditLedgerEntry`: one immutable row per credit movement. It has `kind` (GRANT/CREDIT/DEBIT/CAPTURE/ADJUST), signed `amount` (≠0, within ±1,000,000), `balance_after`, `ref_type`/`ref_id`, `reason` and `actor`, and `UNIQUE(team, ref_type, ref_id, kind)`. `CreditReservation`: auction holds; a partial unique index allows only one ACTIVE hold per bid. `MAX_AMOUNT = 1_000_000`. |
| `errors.py` | `INVALID_AMOUNT`, `INVALID_REFERENCE` (422) · `TEAM_NOT_FOUND`, `WALLET_NOT_FOUND`, `RESERVATION_NOT_FOUND` (404) · `INSUFFICIENT_CREDITS` (409, with `available`/`requested`) · `DUPLICATE_REFERENCE`, `RESERVATION_NOT_ACTIVE` (409) · `LEDGER_INVARIANT_BROKEN` (500). |
| `repository.py` | Every balance change is **one conditional UPDATE**. For example, `UPDATE … SET balance = balance − n WHERE balance − held ≥ n RETURNING …`. Postgres row-locks the wallet, so 20 simultaneous taps can't overspend. Also: `ensure_wallet` (insert-if-missing), `get_wallets` (batch), `insert_entry` (unique violation → `DUPLICATE_REFERENCE`), `ledger_sum` and `active_reserved_sum` for verification. |
| `service.py` | **The contract.** `get_wallet`, `get_wallets`, `list_ledger` (cursor paging), `verify_wallet` (ledger sum = balance and active holds = held). `credit`, `debit`, `grant_initial` (once per team), `admin_adjust` (± with idempotency key). `reserve`/`release`/`capture` for auctions; `capture` can charge less than the hold and release the rest. Every change goes through one private `_apply()`: duplicate check → locked conditional update → ledger row. |
| `schemas.py` | `WalletOut`. `LedgerEntryOut` (participant, **no actor**). `LedgerEntryAdminOut` (+ team_id, actor). `LedgerPage`. `AdminCreditIn` (strict signed nonzero int, reason 3–500 chars, idempotency_key UUID). `InitialGrantIn`. `WalletVerifyOut`. The admin shapes are reused by K's routes. |
| `router.py` | `GET /wallet` and `GET /wallet/ledger` for the **caller's own team only**; there is no team parameter at all. |
| `__init__.py` | Exports the contract above. |

#### Module F — `app/modules/inventory/` (Team Widget Inventory)

| File | What it does |
|---|---|
| `models.py` | `TeamWidgetInventory` (PK team+widget, `quantity ≥ 0`). `InventoryEvent`: append-only. It has `kind` INCREMENT/DECREMENT/ADJUST, `delta ≠ 0`, `quantity_after ≥ 0`, ref/reason/actor, and `UNIQUE(team, widget, ref_type, ref_id, kind)`. `MAX_QUANTITY_STEP = 10_000`. |
| `errors.py` | `INVALID_QUANTITY`, `INVALID_REFERENCE` (422) · `TEAM_NOT_FOUND`, `WIDGET_NOT_FOUND` (404) · `INSUFFICIENT_QUANTITY` (409, with `owned`/`requested`) · `DUPLICATE_REFERENCE` (409). |
| `repository.py` | `add_quantity` is an **upsert**, so even 20 simultaneous "first purchases" of a widget are safe. `subtract_if_enough` is the conditional-UPDATE pattern. Also: events, `event_sums`/`quantities` (verification), `unit_counts` (batch for K). It **no longer reads the widget table**. |
| `service.py` | **The contract.** `get_quantity`, `get_team_inventory` (2 queries for any team size: our rows + one batch call to D's `get_widgets`; archived widgets still listed with `archived=true`), `unit_counts`, `verify_inventory`, `increment`, `decrement`, `admin_adjust`. Widget existence is checked through D's `widget_exists`. |
| `schemas.py` | `InventoryItemOut` (widget_id, appdev_key, display_name, quantity, archived), `InventoryOut`, `InventoryAdjustIn` (strict ±int, reason, idempotency key), event/verify shapes. |
| `router.py` | `GET /inventory` for the caller's own team only. |
| `__init__.py` | Exports the contract. |

#### Module K — `app/modules/admin/` (Organizer / Admin Control Plane)

| File | What it does |
|---|---|
| `permissions.py` | **Roles** OWNER / OPERATOR / VIEWER. **10 permissions**: `view`, `audit.read`, `teams.manage`, `credits.adjust`, `inventory.adjust`, `catalog.manage`, `market.manage`, `api_keys.manage`, `controls.freeze`, `organizers.manage`. VIEWER = view + audit.read; OPERATOR = all except organizers.manage; OWNER = all. `AuditAction` names (`credits.adjust`, `catalog.widget_archive`, …). |
| `models.py` | `Organizer` (lowercase unique email, role, active, version). `AdminActionLog` (actor, role, action, target, reason, redacted JSON details; append-only). `OperationalControl` (scope ALL/TRADING/BIDDING, frozen, reason, changed_by, version). |
| `errors.py` | `FORBIDDEN` (same answer for unknown, deactivated and participant: reveals nothing) · `MISSING_PERMISSION` (names the permission) · `ORGANIZER_EXISTS` / `ORGANIZER_NOT_FOUND` · `LAST_OWNER` · `SELF_LOCKOUT` · `VERSION_CONFLICT` · `CONFIRMATION_REQUIRED` · **`OPERATION_FROZEN` (423)** · `TEAM_NOT_FOUND` · `TEAM_NAME_TAKEN` · `TEAM_IMPORT_INVALID` · `DEPENDENCY_NOT_AVAILABLE` (503). |
| `ports.py` | Plug-in points for modules owned by **other teams**: `set_team_directory` (B), `set_market_status_provider` (G), `set_transaction_feed` (I). Until they register, those admin views answer 503 instead of crashing. K never reads their tables. |
| `repository.py` | Organizer lookups. `lock_active_owners` (FOR UPDATE, so two owners can't demote each other at once). Audit insert/list. Controls: `get_control_for_update` (freeze) and `frozen_controls_for_share` (purchase/bid check: FOR SHARE, so purchases run in parallel but a freeze waits for them). |
| `authz.py` | `require_organizer` looks up `principal.email` in `organizer` on **every request**, so deactivation is instant. `require_permission(Permission.X)` checks the role. Denied attempts are logged without secrets. `OrganizerPrincipal.actor` = email. |
| `service.py` | `audit()`: same transaction as the change; redacts secret-looking keys; caps sizes; other modules may log `"module.verb"` actions. Organizer CRUD: version check, no self-demotion, last-owner guard, actor re-checked under lock. Controls: `set_frozen` (typed `FREEZE ALL`), **`ensure_not_frozen(s, "TRADING"\|"BIDDING")`**, `public_controls`. Teams: overview in 3 queries, `create_team` (+ 120 starting credits through E), all-or-nothing `import_teams`, `set_team_status` (typed team name to disable). Market status / transactions through ports. `bootstrap_owner` for the CLI. |
| `schemas.py` | Strict request/response shapes for organizers, audit, controls and teams. Emails are normalized. Team names are trimmed and refuse `<`, `>` and control characters. |
| `router.py` | `/admin/me`, `/admin/organizers`, `/admin/audit`, `/admin/controls`, `/admin/teams…`, `/admin/market/status`, `/admin/transactions`, and the participant-visible `GET /controls`. |
| `team_assets_router.py` | Organizer routes for E and F data: `/admin/teams/{id}/wallet`, `/credits`, `/credits/initial-grant`, `/wallet/ledger`, `/wallet/verify`, `/inventory`, `/inventory/adjust`, `/inventory/verify`. Each change: permission → E/F rules → audit → one commit. |
| `catalog_router.py` | Organizer routes for D data: `GET/POST /admin/widgets`, `GET/PATCH /admin/widgets/{id}`, `POST …/archive` (reason + typed id), `POST …/restore`. Same pattern, with audit rows `catalog.widget_*`. |
| `cli.py` | `python -m app.modules.admin.cli add-owner --email … --name …` and `list`. The **only** way to create the first OWNER. There is deliberately no HTTP route for it. |
| `__init__.py` | Exports `require_organizer`, `require_permission`, `OrganizerPrincipal`, `Permission`, `Role`, `AuditAction`, `audit`, `ensure_not_frozen`. |

#### Tests — `tests/`

| File | Tests | What it proves |
|---|---|---|
| `conftest.py` | — | Forces `TEST_DATABASE_URL` and **refuses any DB without "test" in its name**. Wipes and migrates once per run. Fixtures: `db`, `make_team`, `make_widget`, `client`, `login(team_id=…)` / `login(email=…)`. |
| `catalog/test_catalog_service.py` | 18 | The teammate's 4 service tests (ported) + duplicate appdev_key, archived still resolvable, id/appdev_key immutable (code **and** raw SQL), never deletable, notes preserved, no-op edits, nulls rejected, free-quantity rules, restore, DB CHECKs. |
| `catalog/test_catalog_concurrency.py` | 3 | Two organizers editing with the same version → exactly one wins. 10 parallel creates of one id → 1 widget. 8 parallel creates of one appdev_key → 1 widget. |
| `catalog/test_catalog_api.py` | 5 | Public list hides internal fields, and archived hidden from the list but resolvable (both from the teammate's tests, adapted). 404/422 shapes. Login required. Organizers can read the catalog. |
| `ledger/test_ledger_service.py` | 29 | Grants, debits, duplicates, bad amounts (8 parametrised), admin adjust, compensating entries, holds/capture/release, append-only, DB refuses negative balance, rollback. |
| `ledger/test_ledger_concurrency.py` | 3 | 20 parallel debits never overspend. Parallel retries charge once. Bids and purchases racing never exceed the balance. |
| `ledger/test_ledger_api.py` | 5 | Own wallet only. A `?team_id=` in the URL is ignored. Login required. No-team login refused. Paging hides `actor`. |
| `inventory/test_inventory_service.py` | 18 | Increment/decrement, never negative, duplicates, bad quantities (6 parametrised), archived widgets still listed, verify, append-only, widgets with history can't be deleted, **purchase rollback/commit across E+F**. |
| `inventory/test_inventory_concurrency.py` | 2 | Parallel sales never go negative. Parallel first purchases add up exactly. |
| `inventory/test_inventory_api.py` | 3 | Own inventory only. Empty list. Team login required. |
| `inventory/test_inventory_catalog_history.py` | 1 | **D×E×F:** renaming and archiving a widget after a purchase leaves ledger and inventory history byte-for-byte unchanged. |
| `admin/conftest.py` | — | `make_organizer`, `login_organizer(role)`, `org_principal`, `count_queries`. Resets the freeze switches around every K test. |
| `admin/test_admin_authz.py` | 9 | **Every `/admin` route (auto-discovered from OpenAPI) rejects participants.** Unknown email = participant answer. Case-insensitive email. Deactivation instant. Viewer/operator limits. Role table nesting. |
| `admin/test_admin_organizers.py` | 10 | Add/normalize. Version conflicts. No self-lockout. **Two owners demoting each other at once → exactly one owner left (threads).** CLI bootstrap. DB lowercase check. |
| `admin/test_admin_controls.py` | 10 | Typed `FREEZE ALL`. Scope behaviour. Participant view. No-op freeze. Version guard. **Freeze waits for an in-flight purchase; a purchase started during a freeze is refused; 10 purchases don't block each other (threads).** |
| `admin/test_admin_audit.py` | 11 | Audit rows for E/F changes. Failed action → no audit row. Double click → one row. Append-only (3 parametrised). Control rows undeletable. Redaction/size caps. Paging/filters. Other modules' action names. |
| `admin/test_admin_teams.py` | 12 | Create with 120 credits **through E's ledger**. Duplicate names. Validation. Import all-or-nothing. In-file repeats. Disable needs the typed name. Detail view. **Dashboard query count doesn't grow with teams**. 503 without a directory. |
| `admin/test_admin_wallet_inventory.py` | 6 | Organizer credit/inventory routes, validation, viewer blocked. |
| `admin/test_admin_catalog.py` | 10 | The teammate's 3 router tests (ported) + duplicates, immutable fields, archive confirmation + restore with audit trail, organizer list incl. archived/notes, validation (12 bad bodies), PATCH needs a version, permissions, 404s. |
| `admin/test_admin_ports.py` | 3 | Market status / transaction feed: 503 until registered, then passed through with clamped limits. |

### 1.5 How Module D was merged

Your teammate's design was kept:
- the fields
- ACTIVE/ARCHIVED with archive-instead-of-delete
- optimistic `version` and `expected_version`
- the public/admin response split
- the 5 spec routes

What changed is what was needed to fit the shared codebase and the spec, and to fix real bugs. **Please share this table with your teammate** so they agree before the PR.

| # | Teammate's version | Merged version | Why |
|---|---|---|---|
| 1 | Flat `app/` package (`app/models.py`, `app/router.py`…), two copies of `main.py` | `app/modules/catalog/` with the same 7-file layout as E/F/K | Our `app/main.py` and `app/modules/*` layout would collide; spec §2 handoff layout |
| 2 | SQLite file `catalog.db`, `SQLModel.metadata.create_all` at startup | PostgreSQL + Alembic migration `0002_catalog` | Spec FINAL: Neon PostgreSQL. SQLite lacks row locks, and `create_all` can't evolve a production schema. Also, the temp `widget` table in our old 0001 is now D's real table. |
| 3 | `widget` columns unbounded; status as an SQL enum; Python `datetime.now()` timestamps | Bounded VARCHARs, JSONB, VARCHAR+CHECK status, DB `now()` timestamps, 6 CHECK constraints | Garbage can't enter even through raw SQL; one clock for every module |
| 4 | Nothing stopped `id`/`appdev_key` changes (`FieldImmutableError` existed but was never raised; unknown fields silently ignored) | 422 `FIELD_IMMUTABLE`, plus a DB trigger | Spec: "Widget ID must be stable once referenced"; AppDev identifiers unique |
| 5 | Nothing stopped deleting a widget | DB trigger: widgets are never deleted (plus FK `RESTRICT` from inventory) | Spec: archiving must preserve history |
| 6 | **Admin routes open to everyone** (`DummyPrincipal` = always organizer) | K's `require_permission(CATALOG_MANAGE)`; `VIEW` for organizer reads; participant routes need login | Spec: "Admin module authorizes organizer actions" |
| 7 | **Routes never committed** (only `flush`) — writes would be lost in production | Each admin route commits once, together with its audit row | Data loss bug |
| 8 | `internal_notes` overwritten with "Created by …" / "Updated by …" | Notes are the organizer's own text; **who** did what goes to K's audit log | Organizers' notes were being destroyed |
| 9 | Version check without a lock (lost-update race); duplicate-create race → 500 | `SELECT … FOR UPDATE` on edit; SAVEPOINT + unique violation → 409 | Proven by 3 thread tests |
| 10 | `expected_version` optional | Required on PATCH, archive and restore | Spec edge case: two organizers edit the same widget |
| 11 | Errors as `HTTPException` → `{"detail": …}`; `status.FIELD_IMMUTABLE` doesn't exist; `except Exception` swallowing | `AppError` subclasses → shared `{"error": …}` envelope | Spec §2.2; same shape as every other module |
| 12 | Explicit `null` for a required field → database error 500; no length/format limits | 422 `INVALID_WIDGET_DATA` / `VALIDATION_ERROR`; strict types; Dart class-name check; no `<`/`>` | Input safety |
| 13 | `GET /widgets/{id}` for an archived widget → 400 | 200 with `archived: true` (the list still hides it) | Spec DoD: "Archived widget remains resolvable"; edge case: archived widget still owned by teams |
| 14 | Service took Pydantic request objects | Service takes plain values; schemas only in routes | Modules G/I/K can call the service without HTTP shapes |
| 15 | No organizer list, no undo | `GET /admin/widgets[/{id}]`, `POST …/restore`, archive needs reason + typed id | Spec K edge case: "Accidental widget/archive operation" |
| 16 | Admin routes in D's router | Served by K's `catalog_router.py` (same URLs) | Same as E/F: K owns all `/admin`, so D never imports K and can merge first |
| 17 | Tests on in-memory SQLite (8 tests) | All 8 ported to PostgreSQL (9 tests marked `(teammate)`, because the archive test was split in two) + 27 new + 1 cross-module history test | Spec DoD tests; SQLite would pass tests that should fail |
| 18 | `.gitignore` contained only a newline; `__pycache__` and `catalog.db` sitting in the folder | Real `.gitignore` including `*.db` | Never commit the SQLite file or caches |

**Module F changed too:** it no longer joins D's `widget` table. It calls D's `get_widgets()` (one batch query), because spec §2 "Explicit ownership" says table access goes through the owner's contract.

### 1.6 All 34 HTTP routes

**Participant-side (6).** Login is required everywhere; the team comes from the token.

| Method | Path | Module | Who | Returns |
|---|---|---|---|---|
| GET | `/widgets` | D | any login | active widgets (public shape) |
| GET | `/widgets/{widget_id}` | D | any login | one widget, archived included (`archived` flag) |
| GET | `/wallet` | E | participant | `{team_id, balance, held, available}` |
| GET | `/wallet/ledger?cursor=&limit=` | E | participant | own history, no `actor`, cursor paging |
| GET | `/inventory` | F | participant | own widgets + quantities (+ archived flag) |
| GET | `/controls` | K | participant | `{trading_open, bidding_open, message}` |

**Organizer side (28), all in Module K.** Every one returns 403 `FORBIDDEN` for non-organizers, and 403 `MISSING_PERMISSION` if the role lacks the permission.

| Method | Path | Permission | Notes |
|---|---|---|---|
| GET | `/admin/me` | any organizer | role + permissions |
| GET / POST | `/admin/organizers` | organizers.manage | add organizer (reason) |
| PATCH | `/admin/organizers/{id}` | organizers.manage | `expected_version`; no self-demotion; last owner protected |
| GET | `/admin/audit` | audit.read | filters: action, actor_email, target_type, target_id; cursor |
| GET | `/admin/controls` | view | the 3 switches |
| PUT | `/admin/controls/{ALL\|TRADING\|BIDDING}` | controls.freeze | `ALL` needs `"confirm": "FREEZE ALL"` |
| GET | `/admin/teams` | view | dashboard: balance, held, available, units (3 queries) |
| POST | `/admin/teams` | teams.manage | + starting credits (default 120) |
| POST | `/admin/teams/import` | teams.manage | ≤200 teams, all-or-nothing |
| GET | `/admin/teams/{id}` | view | team + wallet + inventory |
| POST | `/admin/teams/{id}/status` | teams.manage | DISABLED needs the typed team name |
| GET | `/admin/market/status` | view | from Module G (503 until registered) |
| GET | `/admin/transactions` | view | from Module I (503 until registered) |
| GET | `/admin/teams/{id}/wallet` | view | E |
| POST | `/admin/teams/{id}/credits` | credits.adjust | E; ±amount, reason, idempotency_key; audited |
| POST | `/admin/teams/{id}/credits/initial-grant` | credits.adjust | E; once per team; audited |
| GET | `/admin/teams/{id}/wallet/ledger` | view | E; with actor |
| GET | `/admin/teams/{id}/wallet/verify` | view | E; ledger sum = balance |
| GET | `/admin/teams/{id}/inventory` | view | F; `?include_zero=` |
| POST | `/admin/teams/{id}/inventory/adjust` | inventory.adjust | F; ±delta, reason, idempotency_key; audited |
| GET | `/admin/teams/{id}/inventory/verify` | view | F; event sums = quantities |
| GET | `/admin/widgets` | view | D; `?include_archived=` (default true), with notes |
| POST | `/admin/widgets` | catalog.manage | D; create; audited |
| GET | `/admin/widgets/{id}` | view | D |
| PATCH | `/admin/widgets/{id}` | catalog.manage | D; `expected_version`; audited diff |
| POST | `/admin/widgets/{id}/archive` | catalog.manage | D; `expected_version`, reason, `confirm` = id |
| POST | `/admin/widgets/{id}/restore` | catalog.manage | D; undo an archive |

### 1.7 Internal contracts other teams call

```python
from app.modules import catalog, ledger, inventory
from app.modules.admin import require_permission, Permission, OrganizerPrincipal, audit, ensure_not_frozen

# D — Catalog
catalog.require_active_widget(s, widget_id) -> Widget       # before selling/listing (G, I, J); 409 if archived
catalog.get_widget(s, widget_id) -> Widget                  # resolve history, any status
catalog.get_widgets(s, [ids]) -> {id: Widget}               # batch (C's IDE sync, G's market view)
catalog.widget_exists(s, widget_id) -> bool

# E — Ledger (caller owns the transaction; we only flush)
ledger.get_wallet(s, team_id) / ledger.get_wallets(s, [team_ids])
ledger.debit (s, team_id, amount, ref_type=, ref_id=, reason=, actor=)   # INSUFFICIENT_CREDITS / DUPLICATE_REFERENCE
ledger.credit(s, team_id, amount, ref_type=, ref_id=, reason=, actor=)
ledger.reserve(s, team_id, amount, ref_type=, ref_id=) -> reservation    # auction bid hold
ledger.release(s, reservation_id)                                         # outbid
ledger.capture(s, reservation_id, ref_type=, ref_id=, reason=, actor=, amount=None)   # auction won
ledger.grant_initial(s, team_id, amount, actor=)                          # once per team

# F — Inventory
inventory.get_team_inventory(s, team_id) -> [InventoryItem(widget_id, appdev_key, display_name, quantity, archived)]
inventory.get_quantity(s, team_id, widget_id) -> int
inventory.increment(s, team_id, widget_id, qty, ref_type=, ref_id=, reason=, actor=)
inventory.decrement(s, team_id, widget_id, qty, ref_type=, ref_id=, reason=, actor=)   # INSUFFICIENT_QUANTITY

# K — Admin
ensure_not_frozen(s, "TRADING")   # Module I: FIRST line of a purchase/resale transaction
ensure_not_frozen(s, "BIDDING")   # Module J: FIRST line of a bid transaction
org: OrganizerPrincipal = Depends(require_permission(Permission.MARKET_MANAGE))   # their admin routes
audit(s, org, "market.round_open", target_type="round", target_id=str(rid), reason=body.reason)
```

### 1.8 Error codes

| Module | Codes |
|---|---|
| shared | `VALIDATION_ERROR` 422 · `AUTH_NOT_AVAILABLE` 501 (TEMP) · `NOT_A_TEAM_MEMBER` 403 |
| D | `WIDGET_NOT_FOUND` · `WIDGET_ARCHIVED` · `WIDGET_NOT_ARCHIVED` · `WIDGET_DUPLICATE` · `FIELD_IMMUTABLE` · `VERSION_CONFLICT` · `INVALID_WIDGET_DATA` |
| E | `INSUFFICIENT_CREDITS` · `DUPLICATE_REFERENCE` · `INVALID_AMOUNT` · `INVALID_REFERENCE` · `TEAM_NOT_FOUND` · `WALLET_NOT_FOUND` · `RESERVATION_NOT_FOUND` · `RESERVATION_NOT_ACTIVE` · `LEDGER_INVARIANT_BROKEN` |
| F | `INSUFFICIENT_QUANTITY` · `DUPLICATE_REFERENCE` · `INVALID_QUANTITY` · `INVALID_REFERENCE` · `TEAM_NOT_FOUND` · `WIDGET_NOT_FOUND` |
| K | `FORBIDDEN` · `MISSING_PERMISSION` · `OPERATION_FROZEN` (423) · `CONFIRMATION_REQUIRED` · `VERSION_CONFLICT` · `LAST_OWNER` · `SELF_LOCKOUT` · `ORGANIZER_EXISTS` · `ORGANIZER_NOT_FOUND` · `TEAM_NOT_FOUND` · `TEAM_NAME_TAKEN` · `TEAM_IMPORT_INVALID` · `DEPENDENCY_NOT_AVAILABLE` (503) |

---

## 2. Terminal commands

> Run everything in **WSL (Ubuntu)**, not PowerShell.
> - Your `T:` drive is `/mnt/t` in WSL. If `ls /mnt/t` is empty, mount it: `sudo mkdir -p /mnt/t && sudo mount -t drvfs T: /mnt/t`.
> - Work from a copy in your Linux home (`~/dev/...`). Python virtual environments and tests are much slower, and sometimes break, on `/mnt/t`.

### 2.1 One-time setup
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
python3 --version                                   # 3.11 or newer
docker --version                                    # Docker Desktop with WSL integration enabled

# PostgreSQL 16 with two databases (dev + test)
docker run -d --name fw-postgres -p 5432:5432 -e POSTGRES_PASSWORD=pw postgres:16
sleep 3
docker exec -it fw-postgres psql -U postgres -c "CREATE DATABASE flutterwars_dev;" -c "CREATE DATABASE flutterwars_test;"
# next time: docker start fw-postgres
```

### 2.2 Get the merged folder running
```bash
mkdir -p ~/dev && cp -r "/mnt/t/GDG/Flutter Wars/Team3_DEFK_server" ~/dev/
cd ~/dev/Team3_DEFK_server/server
python3 -m venv .venv && source .venv/bin/activate        # "source" again in every new terminal
pip install -U pip && pip install -e ".[dev]"

cp .env.example .env                                       # local only, git-ignored
set -a && source .env && set +a                            # loads DATABASE_URL and TEST_DATABASE_URL
```

### 2.3 Test
```bash
pytest                                   # everything → 158 passed
pytest tests/catalog                     # Module D → 26 passed
pytest tests/ledger                      # Module E → 37 passed
pytest tests/inventory                   # Module F → 24 passed
pytest tests/admin                       # Module K → 71 passed (incl. D/E/F organizer routes)
pytest tests/admin/test_admin_catalog.py -v                         # one file, verbose
pytest -k "archive" -v                                              # tests whose name contains "archive"

# Race tests: run them 20 times; every line must end in "passed"
for i in $(seq 1 20); do
  pytest -q -p no:warnings tests/catalog/test_catalog_concurrency.py tests/ledger/test_ledger_concurrency.py \
    tests/inventory/test_inventory_concurrency.py tests/admin/test_admin_controls.py \
    tests/admin/test_admin_organizers.py::test_two_owners_demoting_each_other_at_once_leaves_one_owner | tail -1
done

ruff check .                             # → All checks passed!
ruff format --check .                    # → 74 files already formatted   (fix with: ruff format .)
```
The tests **wipe and re-create the test database** on every run. They refuse to run against any database without `test` in its name, so they can never touch dev or Neon.

### 2.4 Migrations and the running API
```bash
alembic upgrade head                     # creates 11 tables in flutterwars_dev
alembic heads                            # → 0005_admin (head)   exactly one
alembic downgrade base && alembic upgrade head      # proves every downgrade works
docker exec -it fw-postgres psql -U postgres -d flutterwars_dev -c "\dt"

# Prove the protections: insert one widget (works), then the next two commands must FAIL
docker exec -it fw-postgres psql -U postgres -d flutterwars_dev -c \
  "INSERT INTO widget (id,appdev_key,display_name,category) VALUES ('row','flutter.row','Row','layout');"
docker exec -it fw-postgres psql -U postgres -d flutterwars_dev -c "DELETE FROM widget;"            # never deleted
docker exec -it fw-postgres psql -U postgres -d flutterwars_dev -c "UPDATE widget SET id='rowx';"   # immutable
alembic downgrade base && alembic upgrade head      # wipes that test row again

# First organizer (OWNER) on your dev DB
python -m app.modules.admin.cli add-owner --email you@gmail.com --name "Your Name"
python -m app.modules.admin.cli list

uvicorn app.main:app --reload
# http://127.0.0.1:8000/docs → 34 operations. Calls answer 501 AUTH_NOT_AVAILABLE until Module B lands (by design).
```

### 2.5 Fork and clone (once)
```bash
cd ~/dev
git clone https://github.com/AnishPrakash/flutter-wars.git        # your fork of gdg-vitc/flutter-wars
cd flutter-wars
git remote add upstream https://github.com/gdg-vitc/flutter-wars.git
git fetch upstream
```

### 2.6 Put the code into 3 stacked PRs (D → E+F → K)
Why three PRs:
- The spec's contract freeze order (§16.1) is Catalog → Ledger+Inventory → Admin.
- Our import graph allows exactly that.
- Small PRs get reviewed faster.

Each step below was rehearsed; the counts are what you should see.

```bash
cd ~/dev/flutter-wars
SRC=~/dev/Team3_DEFK_server/server
STAGES=~/dev/Team3_DEFK_server/pr_stage_mains

# ---------- PR 1: Module D (Catalog)
git checkout -b feat/catalog upstream/main
mkdir -p server && cd server
cp "$SRC"/{pyproject.toml,alembic.ini,.env.example,.gitignore} .
mkdir -p app/core app/modules migrations/versions tests
cp "$SRC"/app/__init__.py app/
cp "$SRC"/app/core/{__init__,db,errors,auth,_temp_models}.py app/core/
cp "$SRC"/app/modules/__init__.py app/modules/
cp -r "$SRC"/app/modules/catalog app/modules/
cp "$SRC"/migrations/{env.py,script.py.mako} migrations/
cp "$SRC"/migrations/versions/{0001_temp_team_stub,0002_catalog}.py migrations/versions/
cp "$SRC"/tests/{__init__,conftest}.py tests/
cp -r "$SRC"/tests/catalog tests/
cp "$STAGES"/main_stage1_D.py app/main.py
find . -name __pycache__ -prune -exec rm -rf {} +
pytest && ruff check .                                   # → 26 passed
git add -A .
git commit -m "feat(catalog): Module D widget catalog (PostgreSQL, migrations, tests)

Co-authored-by: <Teammate Name> <teammate-email@example.com>"
git push -u origin feat/catalog

# ---------- PR 2: Modules E + F (branch from PR 1)
git checkout -b feat/ledger-inventory
cp -r "$SRC"/app/modules/{ledger,inventory} app/modules/
cp "$SRC"/migrations/versions/{0003_ledger,0004_inventory}.py migrations/versions/
cp -r "$SRC"/tests/{ledger,inventory} tests/
cp "$STAGES"/main_stage2_DEF.py app/main.py
find . -name __pycache__ -prune -exec rm -rf {} +
pytest && ruff check .                                   # → 87 passed
git add -A . && git commit -m "feat(ledger,inventory): Modules E and F with concurrency tests"
git push -u origin feat/ledger-inventory

# ---------- PR 3: Module K (branch from PR 2)
git checkout -b feat/admin-control-plane
cp -r "$SRC"/app/modules/admin app/modules/
cp "$SRC"/app/core/_temp_team_directory.py app/core/
cp "$SRC"/migrations/versions/0005_admin.py migrations/versions/
cp -r "$SRC"/tests/admin tests/
cp "$STAGES"/main_stage3_DEFK.py app/main.py
find . -name __pycache__ -prune -exec rm -rf {} +
pytest && ruff check .                                   # → 158 passed
git add -A . && git commit -m "feat(admin): Module K organizer control plane"
git push -u origin feat/admin-control-plane
```
Put the teammate's real name and email in the `Co-authored-by:` line. Or let the teammate push PR 1 from their own fork, so the history credits them.

**Open the PRs on GitHub** (your fork → *Compare & pull request*, base `gdg-vitc/flutter-wars:main`):
1. **PR 1** `feat/catalog` → `main`. Title `[DRAFT – waiting on Modules A/B] Module D: Widget Catalog`.
2. **PR 2** `feat/ledger-inventory`. Write "**stacked on #PR1**" at the top, so reviewers ignore PR 1's commits.
3. **PR 3** `feat/admin-control-plane`. Write "stacked on #PR2".
4. Open all three as **draft**. When PR 1 merges, rebase PR 2 onto `upstream/main` (below); when PR 2 merges, rebase PR 3. Mark each **Ready for review** after §2.8 is done.

Each PR description should follow spec §2.1: owned tables, migrations, public API, internal contract, calls/called-by, tests, decisions taken, open decisions, security. Sections 1.6, 1.7, 3 and 5 of this handbook have all of that, ready to paste.

### 2.7 Keep up with the main repo
```bash
git fetch upstream
git checkout feat/catalog && git rebase upstream/main      # fix conflicts, then: git add <file> && git rebase --continue
pytest && git push --force-with-lease
git checkout feat/ledger-inventory && git rebase feat/catalog && pytest && git push --force-with-lease
git checkout feat/admin-control-plane && git rebase feat/ledger-inventory && pytest && git push --force-with-lease
# after PR 1 is merged upstream:
git checkout feat/ledger-inventory && git rebase --onto upstream/main feat/catalog && pytest && git push --force-with-lease
```

### 2.8 When Modules A and B are merged (do this the same day)
```bash
git fetch upstream && git rebase upstream/main     # keep THEIR app/core, main.py and pyproject.toml on conflicts
grep -rn "app.core" app tests migrations           # every place listed in §3 that needs re-pointing
```
1. Delete our TEMP files:
   - `app/core/db.py`, `errors.py`, `auth.py`, `_temp_models.py`, `_temp_team_directory.py`
   - `app/main.py`
   - `migrations/versions/0001_temp_team_stub.py`

   Don't delete files Module A created with the same names.
2. Re-point imports (table in §3).
3. Set `down_revision` in `0002_catalog.py` to Module B's latest revision, then run `alembic heads` (exactly one head) and `alembic downgrade base && alembic upgrade head`.
4. Register the routers and the port line from `pr_stage_mains/main_stage3_DEFK.py` using Module A's mechanism.
5. Update `tests/conftest.py`: B's principal dependency in `login()`, and `make_team` inserting into B's real `team` table.
6. `pytest`, `ruff check .` → then mark the PRs ready.

### 2.9 Production first OWNER (Module M / tech lead, once)
```bash
read -s DATABASE_URL && export DATABASE_URL        # paste the Neon URL; nothing is shown or saved
alembic upgrade head
python -m app.modules.admin.cli add-owner --email lead@example.com --name "Event Lead"
unset DATABASE_URL
```

---

## 3. What we need from other teams

| From | What we need | What changes in our code when it arrives |
|---|---|---|
| **Team 6 – Module A** (Foundation) | 1. DB session dependency + engine. 2. Base error class + handler with the spec §2.2 shape (incl. validation errors). 3. Router registration mechanism. 4. Settings/env loading. 5. Rate limiting (suggest stricter for `/admin/*`). 6. CORS. | Delete `app/core/db.py`, `errors.py`, `app/main.py`. Every `from app.core.db import get_db, engine` and `from app.core.errors import AppError` (all 4 modules, tests, `admin/cli.py`) points at A's names. Our error subclasses stay. Register our 7 routers + `ports.set_team_directory(...)` with A's mechanism. If A chooses **async** sessions: functions become `async def`/`await`; SQL, constraints and tests stay. |
| **Team 6 – Module B** (Auth & Team) | 1. A principal with `user_id`, **Google-verified `email`** and `team_id`. 2. A `get_principal` dependency (401 if not logged in). 3. The `team` model + migration (`id` UUID?). 4. An implementation of K's `TeamDirectory` port (list/get/find_by_name/create_team/set_status). 5. DISABLED teams refused at login. | Delete `app/core/auth.py`, `_temp_models.py`, `_temp_team_directory.py`, migration `0001_temp_team_stub.py`. Ledger + inventory repositories import B's `Team`. `0002_catalog.down_revision` = B's head. If `team.id` isn't UUID, change `team_id` columns in 0003/0004 + models. `admin/authz.py` reads `principal.email` (one line if B names it differently). `tests/conftest.py` `login()` + `make_team`. |
| **Team 6 – Module C** (API keys & IDE sync) | Their IDE sync endpoint calls our contract. Their key routes use our permission. Their test proves "rotation immediately changes IDE auth" (spec K DoD). | Nothing in our code. They call `inventory.get_team_inventory(s, team_id)` (already has `appdev_key` + `archived`) and use `require_permission(Permission.API_KEYS_MANAGE)` + `audit(s, org, "api_keys.rotate", …)`. |
| **Team 2 – Module G** (Market & Rounds) | Market status provider. Their round/listing admin routes use `MARKET_MANAGE` + `audit()` + `expected_version`. Listings reference `widget.id` and call `catalog.require_active_widget`. | One line at startup: `ports.set_market_status_provider(fn)`, which turns `/admin/market/status` from 503 into live data. |
| **Team 2 – Module H** (Pricing) | Price lives in H/G only. Agreement on what `is_free`/`free_quantity` in the catalog mean (§4). | Nothing, unless the lead decides to move `is_free`/`free_quantity` out of D. |
| **Team 2 – Module I** (Purchase) | Calls `ensure_not_frozen(s, "TRADING")` **first**, then lock order; uses `ledger.debit` + `inventory.increment` in one transaction; `catalog.require_active_widget`. Registers the transaction feed port. | One line at startup: `ports.set_transaction_feed(fn)`, which makes `/admin/transactions` live. |
| **Team 2 – Module J** (Auction) | `ensure_not_frozen(s, "BIDDING")` on bids; `ledger.reserve/release/capture`; `inventory.increment` at settlement; decision on whether settlement ignores the freeze (we suggest it should, so closed auctions finish). | Nothing. |
| **Module L** (Observability) | Logging conventions, request IDs. Reads `admin_action_log` (K owns it; L must not write to it). | Our `logging.getLogger("flutterwars.admin")` lines follow their format. |
| **Module M** (Infra) | Neon URL, connection path (see Hyperdrive in §4), migrations in CI/CD, running the first-owner CLI in production. | Nothing in code; `DATABASE_URL` from the environment. |
| **AppDev team** | The real **21-widget list** with `appdev_key` per widget, and which metadata fields the IDE wants (spec D TBD). | Seed the catalog through `POST /admin/widgets` (or a seed script). Add fields to D if needed. |

---

## 4. Anything extra you may have missed

**Must handle before the event**
1. **Seed the catalog.**
   - The event needs the 21 widgets in `widget`, with the exact `appdev_key` the IDE expects. Nothing seeds them yet.
   - Get the list from AppDev and create them via `POST /admin/widgets`, or a short seed script that calls `catalog.create_widget`. Then run `GET /admin/widgets` to check.
2. **`is_free` / `free_quantity` (teammate's fields) need a lead decision.**
   - Spec §6 says "Catalog data must not directly own price or stock".
   - "Free" is arguably a **price** (Module H), and "free quantity" a **starting allocation** (granted through Module F's `increment`).
   - Kept as plain catalog flags for now (constrained, never used for charging). Ask the lead whether H/G should read them or own them.
3. **Starting credits are one-time and team-level** (120 by default via `POST /admin/teams`). The earlier "credits per member" idea is not implemented, matching the final decision of 120 per team.
4. **Hyperdrive (spec §1 FINAL) is a Cloudflare Workers binding.** A Python FastAPI server running elsewhere (Cloud Run / VM) can't use it directly. It connects to Neon's **pooled** URL instead. Raise this with Module M.
5. **Neon pooler + psycopg 3.** If you see `prepared statement "_pg3_x" does not exist` against Neon's pooled URL, disable server-side prepares: `create_engine(url, connect_args={"prepare_threshold": None})` in Module A's engine.
6. **Pool size vs Neon limits:** our TEMP engine uses up to 30 connections per process (10 + 20 overflow). Multiply by the number of server processes and compare with the Neon plan's limit. Module A/M should set this.
7. **Load test for 500 users.** Nothing in the repo measures it yet. A 10-minute Locust/k6 run is suggested, mostly `GET /wallet`, `/inventory`, `/widgets` plus purchases once Module I exists, against a Neon branch.

**Security / operations**
8. **Protect or disable `/docs` and `/openapi.json` in production** (Module A). They list every admin route.
9. **Rate limits** on login and `/admin/*` (Module A). Our code doesn't do rate limiting.
10. **Organizer roster:** decide the first 2 OWNERs (lead + backup) and the OPERATOR/VIEWER list before the event.
11. **Backups:** Neon point-in-time restore must be enabled (Module M). Our append-only history makes a restore auditable.
12. **Never commit** `.env`, Neon URLs or `catalog.db`. The `.gitignore` covers them; check with `git status` before every commit.

**Two problems found and fixed while merging (worth knowing)**
- **`pip install -e ".[dev]"` failed** (the earlier guide's command). Setuptools refused a project with both `app/` and `migrations/` at the top. Fixed in `pyproject.toml` (`[build-system]` + `[tool.setuptools.packages.find] include = ["app*"]`).
- **SQLAlchemy 2.1 exposed an ordering bug.** Reading the DB clock *after* changing a row auto-flushed a half-updated widget, and the database (correctly) rejected "ARCHIVED without `archived_at`". All `save` helpers now read the clock first, inside `no_autoflush`. The suite passes on SQLAlchemy 2.0 **and** 2.1.
  - Lesson: **pin versions** for the event (`pip freeze > requirements.lock` after a green run, and deploy from that).

**Code-level follow-ups (optional, small)**
13. **CI:** a GitHub Actions job with a `postgres:16` service running `pytest` and `ruff` on every PR. Ask Module M for the repo-level workflow. Our tests already read `TEST_DATABASE_URL`.
14. **Catalog versions of the same widget** (spec D TBD): we chose *no variants*. One row per widget, with `version` counting edits.
15. **Pagination for `/admin/widgets`:** not needed for about 21 widgets. Add a cursor if the catalog grows into the hundreds.
16. **Spec §17.5 pause boundary** (TBD for Market/Transaction teams): **K already implements it**. In-flight purchases finish, purchases that start during a freeze are refused, proven by thread tests. Team 2 must agree and call `ensure_not_frozen` first.

---

## 5. Comparison with the specification document

Legend: ✅ done and tested · 🟡 done on our side, needs another team or a lead decision · ⬜ owned by another team (we provide the hook) · ➖ optional in the spec, deliberately not built

### 5.1 Module D — Widget Catalog (spec §6)

| Spec item | Status | Where |
|---|---|---|
| Entity `widget` (stable id, name, display name, description, category/status, AppDev identifier) | ✅ | `catalog/models.py`, `0002_catalog.py` (the separate "internal name" is the slug `id`) |
| `widget_metadata` (optional) | ➖ | `flutter_classes` (JSONB) covers the IDE's needs; add a table if AppDev asks for more |
| Availability flags independent of a round | 🟡 | `status`, `is_free`, `free_quantity`. The free fields need a lead decision (§4.2) |
| Create/update/archive through organizer controls | ✅ | K `catalog_router.py` + `catalog/service.py` |
| Stable identifiers for Market, Inventory, IDE sync | ✅ | id + appdev_key immutable (code + trigger) — `test_id_and_appdev_key_are_immutable`, `test_identity_fields_are_immutable` |
| Participant-safe metadata | ✅ | `WidgetPublicOut` — `test_public_list_hides_internal_fields` |
| No delete that destroys history | ✅ | no-delete trigger + FK RESTRICT — `test_widget_can_never_be_deleted` |
| Future widget types without financial changes | ✅ | catalog holds no price/credits; free-form `category` |
| API: `GET /widgets`, `GET /widgets/{id}`, `POST /admin/widgets`, `PATCH /admin/widgets/{id}`, `POST …/archive` | ✅ | all 5 (+ organizer GETs and restore) |
| Rule: id stable once referenced | ✅ | trigger `trg_widget_identity_immutable` |
| Rule: archiving stops future use but keeps history | ✅ | `require_active_widget` vs `get_widget` — `test_archived_widget_remains_resolvable` |
| Rule: no price/stock in catalog | 🟡 | none stored; `is_free`/`free_quantity` flagged (§4.2) |
| Rule: AppDev identifiers unique | ✅ | `UNIQUE(appdev_key)` — `test_duplicate_appdev_key_rejected`, `test_parallel_creates_with_same_appdev_key_make_one_widget` |
| Edge: edit while actively listed | ✅ | row lock + `expected_version`; G snapshots price itself — `test_two_organizers_edit_same_widget_one_wins` |
| Edge: duplicate AppDev identifier | ✅ | see above |
| Edge: archived widget still owned | ✅ | `test_archived_widget_still_listed_for_owner`, `test_catalog_changes_do_not_mutate_past_transactions` |
| Edge: widget reused across rounds | ✅ | catalog has no round fields; G's listings reference `widget.id` |
| Edge: name change after purchases | ✅ | `test_catalog_changes_do_not_mutate_past_transactions` |
| Deliverables: entities, participant reads, organizer CRUD/archive, unique/stable validation, integration tests | ✅ | 26 D tests + 10 organizer-route tests + 1 cross-module test |
| **DoD:** duplicate identifiers rejected | ✅ | `test_duplicate_widget_id_rejected`, `test_duplicate_appdev_key_rejected`, `test_duplicates_rejected` |
| **DoD:** archived widget resolvable for history | ✅ | `test_archived_widget_remains_resolvable`, `test_archived_widget_hidden_from_list_but_resolvable` |
| **DoD:** participant API hides internal metadata | ✅ | `test_public_list_hides_internal_fields` |
| **DoD:** catalog changes don't mutate past transactions | ✅ | `test_catalog_changes_do_not_mutate_past_transactions` |
| TBD: metadata fields AppDev wants | 🟡 | ask AppDev (§3) |
| TBD: versions of the same widget | ✅ decided | no variants; `version` counts edits |
| TBD: archived widgets visible to IDE sync when owned | ✅ decided | yes, with `archived: true` (F + D) |

### 5.2 Module E — Credit Ledger & Wallet (spec §7)

| Spec item | Status | Where |
|---|---|---|
| `credit_ledger_entry` immutable, with team, amount, kind, reference, timestamp | ✅ | `ledger/models.py`, append-only trigger — `test_ledger_rows_cannot_be_updated_or_deleted` |
| `team_wallet` cached balance | ✅ | balance + held; `verify_wallet` proves = ledger sum |
| `credit_reservation` for auctions | ✅ | reserve/release/capture |
| Initial grants · debits · credits · auction holds · manual adjustments | ✅ | `service.py` |
| Balance + participant-safe history | ✅ | `GET /wallet`, `/wallet/ledger` (no actor) — `test_ledger_pagination_hides_actor` |
| Internal atomic debit/credit | ✅ | never commits; caller owns transaction — `test_rollback_after_debit_leaves_no_trace` |
| No negative balance | ✅ | conditional UPDATE + CHECK — `test_database_refuses_negative_balance_even_if_code_is_wrong` |
| Duplicates can't charge twice | ✅ | UNIQUE business reference — `test_same_reference_cannot_charge_twice`, `test_parallel_retries_of_same_operation_charge_once` |
| API `POST /admin/teams/{id}/credits` with mandatory reason | ✅ | served by K, audited — `test_initial_grant_and_adjust` |
| Rules: immutable + compensating entries · traceable reason · exact ints · insufficient → fail · shown = committed | ✅ | `test_compensating_entry_keeps_history`, `test_invalid_amounts_rejected`, `test_debit_insufficient_changes_nothing` |
| Edge: 2 simultaneous purchases | ✅ | `test_twenty_parallel_debits_never_overspend` |
| Edge: retry after timeout | ✅ | `test_parallel_retries_of_same_operation_charge_once` |
| Edge: organizer grants twice | ✅ | idempotency key — `test_admin_adjust_double_click_blocked`, `test_initial_grant_only_once` |
| Edge: auction hold + purchase | ✅ | `test_bids_and_purchases_racing_never_exceed_balance` |
| Edge: refund after partial operation | ✅ | rollback test; refunds are `credit()` with their own reference |
| Edge: overflow | ✅ | ±1,000,000 per call, BIGINT columns |
| **DoD** (all 5) | ✅ | concurrency, duplicate, sum consistency, compensating entry, other team's wallet (`test_participant_sees_only_own_wallet`, `test_team_cannot_be_chosen_by_the_client`) |
| TBDs (isolation, cached balance, reservations, idempotency format/retention) | ✅ decided | READ COMMITTED + conditional UPDATE; cached + verify; ledger-owned reservations; UNIQUE(team, ref_type, ref_id, kind), kept forever |

### 5.3 Module F — Team Widget Inventory (spec §8)

| Spec item | Status | Where |
|---|---|---|
| `team_widget_inventory` + `inventory_event` | ✅ | `inventory/models.py`, append-only events — `test_events_are_append_only` |
| Current quantity per widget · increments after purchase/auction · decrements on approved sales | ✅ | `increment`/`decrement` (only via business transactions or audited organizer adjust) |
| Internal read optimized for IDE sync | ✅ | `get_team_inventory` (2 queries, `appdev_key` + `archived`) |
| History to reconcile | ✅ | events + `verify_inventory` — `test_admin_adjust_and_verify` |
| `GET /inventory` | ✅ | own team only — `test_participant_sees_only_own_inventory` |
| Rule: never negative | ✅ | `test_decrement_never_negative`, `test_parallel_sales_never_go_negative`, CHECK |
| Rule: inventory changes only after credit/stock succeeds | ✅ | same transaction — `test_purchase_failure_rolls_back_credits_and_inventory_together` |
| Rule: not a validation engine | ✅ | stores quantities only |
| Rule: an infinite widget that is limited per use: each purchase adds the purchased amount | ✅ | `increment(qty)` adds exactly `qty`; "infinite supply" is Module G's listing setting, not an inventory concept — `test_increment_creates_and_adds` |
| Rule: manual organizer edits auditable | ✅ | actor + reason + idempotency key + K audit row — `test_inventory_adjust_writes_audit_row` |
| Edge cases (concurrent purchase, oversell, archived, auction+purchase close together, rollback) | ✅ | `test_parallel_first_purchases_of_same_widget`, `test_decrement_never_negative`, `test_archived_widget_still_listed_for_owner`, rollback tests |
| Deliverable: integration with IDE sync | ⬜ | contract ready; Module C (Team 6) calls it |
| Deliverable: atomic tests with Ledger/Market | 🟡 | with Ledger ✅; with Market once Module G exists |
| **DoD:** never negative · failed purchase unchanged · team isolation · archived documented | ✅ | tests above |
| **DoD:** committed purchase visible through IDE sync | 🟡 | `test_purchase_success_commits_both` + `get_team_inventory`; end-to-end needs C's endpoint |
| TBDs (aggregate vs lots, manual policy, pending auctions) | ✅ decided | aggregate + events; organizer adjust with reason/key/audit; no pending quantity (changes only at settlement) |

### 5.4 Module K — Organizer / Admin Control Plane (spec §13)

| Spec item | Status | Where |
|---|---|---|
| Organizer identity/role records | ✅ | `organizer` table, per-request lookup |
| `admin_action_log` | ✅ | append-only, redacted |
| Config objects not owned elsewhere | ✅ | `operational_control` (freeze switches) |
| Authorize organizer-only actions | ✅ | `require_permission` — `test_every_admin_route_rejects_participants` |
| Manage teams and eligibility | ✅ | create/import/disable via B's port |
| Manage widgets through Catalog APIs | ✅ | `catalog_router.py` → D's contract |
| Grant/adjust credits through Ledger | ✅ | `team_assets_router.py` → E's contract |
| Create/configure rounds & listings · open/pause/close rounds · pricing parameters · auctions | ⬜ | owner modules (G/H/J) implement them with our `require_permission(MARKET_MANAGE)` + `audit()` (spec allows: "may be implemented in owner module routers but must use shared organizer authorization") |
| Generate/revoke team API keys | ⬜ | Module C with `API_KEYS_MANAGE` |
| Operational views: balances, inventory, transactions | ✅ / 🟡 | balances + inventory ✅; transactions via port (503 until Module I registers) |
| Emergency controls (pause trading) | ✅ | ALL/TRADING/BIDDING + `ensure_not_frozen` |
| API: `GET /admin/teams` · POST/PATCH teams · `GET /admin/transactions` · `GET /admin/market/status` | ✅ | (`/admin/teams/{id}/status` is the disable/enable "PATCH") |
| Rule: participant JWT can't access organizer functions | ✅ | authz tests; no role inside the JWT |
| Rule: actor + reason recorded | ✅ | audit tests |
| Rule: go through owner contracts, not raw SQL | ✅ | K imports only `catalog`, `ledger`, `inventory` contracts + ports |
| Rule: dangerous operations explicit | ✅ | typed confirmations, all-or-nothing import, nothing deleted |
| Edges: disable active team · pause during spike · mistyped adjustment · accidental archive | ✅ | `test_disable_needs_team_name_typed`, `test_freeze_waits_for_in_flight_purchase`, idempotency + compensating entries, `test_archive_needs_typed_id_and_can_be_restored` |
| Edge: two organizers edit the same thing | ✅ / ⬜ | organizers, widgets, controls: `test_update_needs_current_version`, `test_two_organizers_edit_same_widget_one_wins`, `test_expected_version_guards_double_clicks`. **Rounds** belong to Module G, which should use the same `expected_version` pattern |
| Edge: emergency key revocation | ⬜ | Module C, with `API_KEYS_MANAGE` + `audit()` |
| Deliverables: authorization dependency · dashboard API · overview endpoints · audit integration · docs of high-impact operations | ✅ | this handbook + the event-day runbook in the earlier Module K guide (§17 there) |
| **DoD:** participant denied on every admin route | ✅ | loops over every `/admin` operation found in OpenAPI (28 today; the test fails if fewer) |
| **DoD:** admin changes go through owner rules | ✅ | E/F/D errors pass through unchanged — `test_failed_action_leaves_no_audit_row` |
| **DoD:** manual credit adjustment creates ledger history | ✅ | `test_initial_grant_and_adjust`, `test_create_team_grants_starting_credits` |
| **DoD:** API-key rotation changes IDE auth immediately | ⬜ | Module C's test |
| **DoD:** market pause enforced by purchase/bid modules | 🟡 | K side proven by thread tests; I/J must call `ensure_not_frozen` + test it |
| TBDs: roles · reasons/confirmations · freeze scope · audit immutability · bulk import format | ✅ decided | OWNER/OPERATOR/VIEWER. Reason on every change; typed confirmation for freeze ALL, disable team, archive widget; idempotency key on credit/widget adjustments; `expected_version` on organizer/widget/control edits. Scopes ALL/TRADING/BIDDING. Audit immutable via trigger, all organizer mutations captured. Import: JSON list, all-or-nothing. |

### 5.5 Rules that apply to every module

| Spec section | Status | Notes |
|---|---|---|
| §1 Python + FastAPI + SQLModel + PostgreSQL | ✅ | |
| §1 Neon via Cloudflare Hyperdrive | 🟡 | code is driver-agnostic; Hyperdrive caveat in §4.4 |
| §1 Google Sign-In → backend JWT | ⬜ | Module B; we only consume the principal |
| §1 Credits = immutable ledger + current balance | ✅ | |
| §1.1 Backend is the source of truth; IDE only mirrors | ✅ | no client-chosen team, price or quantity anywhere |
| §2 Single responsibility · explicit ownership | ✅ | F reads widgets through D's contract; K uses ports for B/G/I |
| §2 Atomic financial/state changes | ✅ | never-commit contracts + rollback tests |
| §2 Idempotent mutations | ✅ | DB unique references, idempotency keys, versions |
| §2 Auditability | ✅ | ledger, inventory events, admin log — all append-only |
| §2 Versioned contracts | 🟡 | spec TBD (Module A); our contracts are listed in §1.7 |
| §2 Extensibility | ✅ | ports, `audit("module.verb")`, permission enum, auto-discovered migrations |
| §2.1 Handoff contract (entities, migrations, routers, service, repository, auth, tests, API docs, integration note, open decisions) | ✅ | all 4 modules; this handbook = docs + integration note |
| §2.2 Shared error contract | ✅ | including validation errors |
| §16.1 Contract freeze order | ✅ | PR plan D → E+F → K matches it |
| §17.3 Normal purchase flow | 🟡 | our steps 19 and 21 are ready; Module I orchestrates |
| §17.4 Auction settlement (no double charge/award) | ✅ / 🟡 | `capture` + unique references proven; Module J orchestrates |
| §17.5 Emergency pause, in-flight boundary | ✅ | decided and proven in K; I/J must adopt |
| §18.1 No second balance / no second quantity table / stable IDs in history | ✅ | |
| §19.1 JWT vs team API key vs organizer role | ✅ | our routes accept only the JWT principal; organizer role is server-side |

**Scoreboard**
- Every spec item that belongs to D, E, F or K is ✅ or decided.
- The 🟡 items each wait on a named team (B, C, G, I, J, M, AppDev) or on one lead decision (`is_free`/`free_quantity`).
- The ⬜ items belong to other modules, and our hooks for them are already built and tested.
