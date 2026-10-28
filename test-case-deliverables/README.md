# Kitchen Quest test cases

**Branch reviewed:** backend-setup; commit 94014cfbb546b08c37fec251bc9be65ef54615af.

**Execution status:** Source review only. No backend API requests or database tests executed. All Actual Result and Status cells are Not run.

**Using your existing Excel template:** Core cases has the same B7:L7 headers and B8:L19 case range as the screenshot. Copy B8:L19 into your template at B8, replacing the two login rows and filling ten remaining rows. Or paste core-test-cases.tsv into B8; it has no header.

**Base URL:** http://localhost:8000; use Swagger at /docs, Postman, or another HTTP client.

**Test environment:** Use an isolated PostgreSQL test database configured in backend/.env. Follow README setup; run alembic upgrade head and start uvicorn from backend/.

**User fixture:** Before case 1, POST /api/auth/register JSON {"username":"qa_user","password":"QApass123!"}. Confirm 201 and role=user. Ensure student2 and missing_qa_user do not exist. Use fresh fixtures for repeat runs.

**Admin fixture:** From backend/, run python -m app.create_admin; enter qa_admin and Adminpass123!. POST /api/auth/login as form-urlencoded username=qa_admin, password=Adminpass123!; save access_token as ADMIN_TOKEN.

**Tokens:** USER_TOKEN comes from core case 1. Send Authorization: Bearer <token> on protected endpoints. Replace all angle-bracket placeholders with actual returned values. Tokens default to 60-minute expiry; renew when needed.

**Request formats:** Login uses application/x-www-form-urlencoded username and password. Register and create-recipe requests use application/json. No JSON body on GET or DELETE.

**Order:** Execute core cases 1-12 in order in a clean test database. Case 7 creates soup; case 10 setup creates salad; case 11 checks shared salt; case 12 deletes soup. Additional cases have their own prerequisites and should run separately.

**Generated values:** Never assume database IDs. Save id and ingredient.id values from successful responses. Compare ingredient contents by name/id; ingredient ordering within a recipe is not specified.

**Spreadsheet metadata:** Project: Kitchen Quest; Prepared by: Callahan Bonifant (copied from screenshot); Date of creation: 10/20/2026; Date of review: leave blank until actual review; Group: Group 8.

**Actual Result:** Replace Not run with the observed HTTP status, response details, persistence checks, and execution evidence. A source-code prediction is not an actual test result.

**Status:** Set Passed only after every expected assertion in a row passes. If a row has multiple input variants/endpoints, test every one; split rows for separate tracking if desired. Set Failed for a mismatch, or Blocked if execution cannot proceed.

**Welcome screen:** This branch contains backend code only. Login returns a token; a welcome screen cannot be verified from this branch. Existing welcome-screen wording in the screenshot should be replaced by core cases 1 and 2.

**Potential gap: blank text:** Recipe titles and ingredient names have no minimum-length checks; registration validates username length before trimming. Empty/whitespace recipe titles, ingredient names, and all-space usernames need a product rule before defining rejection tests. Do not claim the current code rejects them.

**Potential gap: numeric bounds:** No positive-value constraints exist for servings or ingredient quantity. Decide whether zero/negative values should be rejected before adding such acceptance criteria.

**Potential gap: database string limits:** Database limits are title=200, ingredient name=100, unit=30 characters, but corresponding request schemas have no max_length. Oversize values may cause unhandled database errors; treat graceful rejection as a proposed requirement, not a verified behavior.

**Scope:** No edit-recipe, logout, password-reset, search, or standalone ingredient-create endpoint exists in this branch. Cases avoid inventing those features.

**Source links:** https://github.com/Jonathan510T/Kitchen-Quest/tree/94014cfbb546b08c37fec251bc9be65ef54615af/backend/app

