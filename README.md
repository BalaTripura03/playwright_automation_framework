# Playwright Automation Framework

A modular, multi-layer test automation framework built on **Playwright** (UI), **requests** (API),
and **SQLite/DB-API** (database), orchestrated with **pytest** and reported via **Allure**.

## Folder structure & purpose

```
playwright_framework/
│
├── core/                     # Playwright engine plumbing + Page Object base class
│   ├── browser_manager.py    # Launches/closes the Playwright browser (chromium/firefox/webkit)
│   ├── base_page.py          # BasePage: click/fill/navigate helpers all page objects inherit
│   └── context_manager.py    # Creates/closes isolated BrowserContext per test (viewport, base_url)
│
├── config/                   # Environment-aware configuration
│   ├── config_reader.py      # Merges config.yaml + environments/<ENV>.yaml + .env/OS vars
│   ├── config.yaml           # Default settings (browser, timeouts, base_url, etc.)
│   └── environments/
│       ├── qa.yaml           # QA overrides
│       └── uat.yaml          # UAT overrides
│
├── pages/                    # Page Object Model classes (one file per screen), see pages/README.md
│
├── api/                      # API testing layer
│   ├── api_client.py         # requests.Session wrapper: get/post/put/patch/delete + logging
│   ├── api_request.py        # Fluent builder for reusable request definitions
│   └── api_response.py       # Wraps a Response with assert_status/json_path helpers
│
├── database/                 # DB validation layer
│   ├── db_connection.py      # Opens/closes a DB-API connection (SQLite by default)
│   └── db_helper.py          # execute/fetch_one/fetch_all query helpers
│
├── utils/                    # Cross-cutting helpers
│   ├── logger.py             # Console + rotating file logger factory
│   ├── waits.py              # Explicit wait wrappers around Playwright's `expect`
│   ├── screenshot_manager.py # Captures screenshots into reports/screenshots
│   ├── trace_manager.py      # Starts/stops Playwright tracing into reports/traces
│   └── data_reader.py        # Reads JSON/CSV fixtures from test_data/
│
├── tests/                    # Test suites
│   ├── framework/            # Sanity tests validating the framework itself
│   ├── ui/                   # UI tests (use the `page` fixture + pages/)
│   ├── api/                  # API tests (use APIClient)
│   └── db/                   # DB tests (use DBHelper)
│
├── test_data/                # JSON/CSV test data fixtures
│
├── reports/                  # Test run artifacts
│   ├── screenshots/          # Failure screenshots
│   ├── traces/               # Playwright trace .zip files
│   └── allure-results/       # Raw Allure results consumed by `allure serve`/`allure generate`
│
├── conftest.py                # Shared pytest fixtures: browser_manager, context, page + auto screenshot-on-fail
├── pytest.ini                 # pytest markers, testpaths, Allure results dir, logging
├── requirements.txt           # Pinned Python dependencies
├── .env                       # Local environment overrides (ENV, BASE_URL, HEADLESS, ...)
├── .gitignore                 # Excludes venvs, caches, generated reports, secrets
├── Jenkinsfile                # CI pipeline: install deps, install browsers, run tests, publish Allure report
└── README.md                  # This file
```

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m playwright install
```

## Configuration

Set the target environment via `.env` or an OS environment variable:

```
ENV=qa            # loads config/environments/qa.yaml on top of config/config.yaml
BASE_URL=...
HEADLESS=true
```

`ConfigReader.get("key")` is used everywhere in the framework to read merged config values.

## Running tests

```powershell
# All tests
.venv\Scripts\python -m pytest

# Only UI smoke tests
.venv\Scripts\python -m pytest -m "ui and smoke"

# Generate/view the Allure report after a run
allure serve reports/allure-results
```

## Writing new tests

- **UI**: add a Page Object under `pages/` (extends `core.base_page.BasePage`), then a test under
  `tests/ui/` that uses the `page` fixture from `conftest.py`.
- **API**: instantiate `api.api_client.APIClient` in a test under `tests/api/` and assert with
  `APIResponse.assert_status(...)` / `assert_json_contains(...)`.
- **DB**: use `database.db_helper.DBHelper` in a test under `tests/db/` to run queries and assert
  on the returned rows.

## Reporting

- Screenshots are captured automatically on test failure (see the `pytest_runtest_makereport` hook
  in `conftest.py`) and saved to `reports/screenshots/`.
- Playwright traces are recorded for every test and saved to `reports/traces/`.
- Allure results are written to `reports/allure-results/` on every run (`pytest.ini` sets
  `--alluredir` by default).

## CI/CD

The `Jenkinsfile` defines a declarative pipeline that checks out the repo, creates a virtualenv,
installs dependencies and Playwright browsers, runs the pytest suite, and publishes the Allure
report as a build artifact.
