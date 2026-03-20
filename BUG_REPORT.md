# Deep Bug Investigation Report
## Expense Tracker — Full Bug Analysis (15 Bugs Found)
**Date:** 2026-03-20 | **Method:** Systematic scientific audit (gsd-debugger approach)  
**Assignment requirement:** Find 5+ bugs. **Total found: 15**

---

## Bug Summary Table

| # | Severity | Location | Bug | Status |
|---|---|---|---|---|
| 1 | 🔴 HIGH | `backend/app.py` | Pagination offset skips page 1 entirely | ✅ Fixed |
| 2 | 🔴 HIGH | `backend/app.py` | Expense list shows soft-deleted rows | ✅ Fixed |
| 3 | 🟡 MEDIUM | `backend/app.py` | No numeric validation for `amount` | ✅ Fixed |
| 4 | 🔴 HIGH | `backend/app.py` + `models.py` | Category delete crashes with FK constraint | ✅ Fixed |
| 5 | 🔴 HIGH | `frontend/App.jsx` | `loadTrend` reads wrong API key (crashes) | ✅ Fixed |
| 6 | 🟡 MEDIUM | `frontend/App.jsx` | `pageTotal` concatenates strings not numbers | ✅ Fixed |
| 7 | 🟡 MEDIUM | `frontend/App.jsx` | `totalPages` uses floor — last page unreachable | ✅ Fixed |
| 8 | 🔴 HIGH | `frontend/App.jsx` | Monthly chart `dataKey="value"` — bars invisible | ✅ Fixed |
| 9 | 🟡 MEDIUM | `frontend/App.jsx` | Trend XAxis `dataKey="month"` — labels blank | ✅ Fixed |
| 10 | 🔴 HIGH | `frontend/App.jsx` | Trend Bar `dataKey="total"` — bars invisible | ✅ Fixed |
| 11 | 🔴 HIGH | `backend/schema.sql` | FK still `NOT NULL` — DB-level constraint mismatch | ✅ Fixed |
| 12 | 🟡 MEDIUM | `frontend/App.jsx` | No client-side guard when category not selected | ✅ Fixed |
| 13 | 🟢 LOW | `frontend/App.jsx` | Form only partially resets after expense added | ✅ Fixed |
| 14 | 🟡 MEDIUM | `backend/app.py` | Orphaned expenses (deleted category) appear in chart | ✅ Fixed |
| 15 | 🟡 MEDIUM | `backend/app.py` | Double-delete returns 200 OK silently | ✅ Fixed |

---

## Part 1: Original 10 Bugs

### BUG 1 — Wrong Pagination Offset
- **File:** `backend/app.py:55`
- **Expected:** Page 1 returns first 10 records
- **Actual:** Page 1 skips first 10 records (offset=10), first page is always blank
- **Root cause:** `offset = page * per_page` — with 1-indexed pages, page=1 gives offset=10
- **Fix:** `offset = (page - 1) * per_page`
- **Hypothesis tested:** Traced offset arithmetic with page=1 → 1×10=10, proved skip

---

### BUG 2 — Soft-Deleted Expenses Still Listed
- **File:** `backend/app.py:57,59`
- **Expected:** Deleted expenses disappear from list
- **Actual:** Deleted expenses still show, total count includes them
- **Root cause:** `Expense.query` with no `is_deleted` filter
- **Fix:** Added `filter(Expense.is_deleted == 0)` to both list query and count

---

### BUG 3 — No Amount Validation
- **File:** `backend/app.py:85`
- **Expected:** Submitting `amount="abc"` returns 400 error
- **Actual:** Stores `"abc"` as string amount; downstream `float()` calls crash
- **Root cause:** No type coercion or validation before storing
- **Fix:** `float(amount)` with positivity check inside `try/except`, returns 400

---

### BUG 4 — Category Delete FK Crash
- **File:** `backend/app.py:46`, `backend/models.py:17`
- **Expected:** Deleting a category soft-deletes its expenses cleanly
- **Actual:** MySQL IntegrityError (FK violation) — category row deleted while expenses still reference it
- **Root cause:** `nullable=False` on `Expense.category_id` + hard FK means nulling category_id fails before category delete
- **Fix:** Set `nullable=True` in models.py; bulk-set `category_id=None` before deleting category

---

### BUG 5 — `loadTrend` Reads Wrong API Key (Runtime Crash)
- **File:** `frontend/App.jsx:62`
- **Expected:** 6-month trend chart renders
- **Actual:** `TypeError: Cannot read properties of undefined (reading 'map')` — chart always errors
- **Root cause:** Code reads `data.monthly_series` but backend sends `data.trend_rows`
- **Fix:** Changed to `(data.trend_rows || []).map(...)` with safe fallback

---

### BUG 6 — `pageTotal` String Concatenation
- **File:** `frontend/App.jsx:136`
- **Expected:** Total shows `34.50`
- **Actual:** Total shows `"034.50"` or `"12.5022.00"` (string concat)
- **Root cause:** `e.amount` is a string from API; `reduce((a,e) => a + e.amount, 0)` coerces 0 to string
- **Fix:** `parseFloat(e.amount || 0)` inside reduce + `.toFixed(2)`

---

### BUG 7 — Last Page Unreachable (Math.floor)
- **File:** `frontend/App.jsx:137`
- **Expected:** 11 records with perPage=10 → 2 pages
- **Actual:** `floor(11/10) = 1` → only 1 page, last record unreachable
- **Root cause:** `Math.floor` instead of `Math.ceil`
- **Fix:** `Math.ceil(total / perPage)`

---

### BUG 8 — Monthly Chart Bars Invisible
- **File:** `frontend/App.jsx:256`
- **Expected:** Category spending chart shows colored bars
- **Actual:** Bars all have zero height — chart appears empty
- **Root cause:** `<Bar dataKey="value">` — backend sends `{ name, amt }` objects, not `value`
- **Fix:** `<Bar dataKey="amt">`

---

### BUG 9 — Trend XAxis Labels Blank
- **File:** `frontend/App.jsx:270`
- **Expected:** X-axis shows period labels like "2026-03"
- **Actual:** All X-axis labels are blank
- **Root cause:** `<XAxis dataKey="month">` — backend sends `period` not `month`
- **Fix:** `<XAxis dataKey="period">`

---

### BUG 10 — Trend Bars Invisible
- **File:** `frontend/App.jsx:275`
- **Expected:** 6-month trend shows spend bars
- **Actual:** All bars invisible (zero height)
- **Root cause:** `<Bar dataKey="total">` — backend sends `spend` not `total`
- **Fix:** `<Bar dataKey="spend">`

---

## Part 2: Deep Investigation — 5 Additional Bugs

> These were found via second-pass scientific audit: tracing data contracts between DB schema → models → API → UI.

---

### BUG 11 — schema.sql FK Constraint Mismatch (CRITICAL)
- **File:** `backend/schema.sql:12,18`
- **Expected:** Database allows `category_id` to be NULL after models.py fix
- **Actual:** Raw SQL schema still has `category_id INT NOT NULL` + hard `FOREIGN KEY (category_id) REFERENCES category(id)` with no `ON DELETE SET NULL`. If user drops and recreates the DB, the fix in models.py is overridden at DB level.
- **Root cause:** models.py was fixed but the source-of-truth SQL schema was not — classic split-brain
- **Evidence:** `db.create_all()` only creates missing tables, won't alter existing ones → real MySQL table stays `NOT NULL`
- **Fix:** Changed to `category_id INT NULL` + `FOREIGN KEY ... ON DELETE SET NULL`

---

### BUG 12 — Submitting Expense With No Category Selected
- **File:** `frontend/App.jsx:113`
- **Expected:** If no category selected, show inline error before sending API request
- **Actual:** `Number("") === 0` is sent as `category_id` → backend returns generic "invalid category" 400
- **Root cause:** No client-side guard for empty `form.category_id`
- **Evidence:** `form.category_id` initializes to `""`, `Number("") = 0`, not a valid category id
- **Fix:** Added `if (!form.category_id) { setMsg("Please select a category"); return; }` before fetch

---

### BUG 13 — Form Only Partially Resets After Adding Expense
- **File:** `frontend/App.jsx:120`
- **Expected:** After successful expense creation, full form resets so user can add another cleanly
- **Actual:** `category_id` and `expense_date` retained from previous entry — user must manually clear them
- **Root cause:** `setForm((f) => ({ ...f, amount: "", description: "" }))` spreads current form and only clears 2 of 4 fields
- **Fix:** `setForm({ category_id: "", amount: "", description: "", expense_date: "" })`

---

### BUG 14 — Orphaned Expenses Appear as Blank Category in Chart
- **File:** `backend/app.py:146-149`
- **Expected:** After category delete, orphaned expenses don't appear in the monthly chart
- **Actual:** Orphaned expenses (category_id=None) group under key `None`, creating a blank-name entry in the chart
- **Root cause:** `key = e.category_id` where `key` can be `None` after category deletion; the `by_cat` dict then has a `None` key entry with empty `category_name`
- **Evidence:** `e.category.name if e.category else ""` returns `""`, so chart shows a mysterious empty bar
- **Fix:** `if key is None: continue` — skip orphaned expenses from chart aggregation

---

### BUG 15 — Double-Delete Returns 200 OK Silently
- **File:** `backend/app.py:120-125`
- **Expected:** Attempting to delete an already-deleted expense should return 404
- **Actual:** Returns `{"ok": True}` with 200 — no-op operation is indistinguishable from a real delete
- **Root cause:** Soft-delete check only does `Expense.query.get(eid)` (finds the row), then sets `is_deleted=1` unconditionally — no check if already `is_deleted==1`
- **Evidence:** A race condition (or UI double-click) can trigger two delete calls; both return 200 with no indication of the second being a no-op
- **Fix:** Added `if e.is_deleted == 1: return jsonify({"error": "already deleted"}), 404`

---

## Files Changed

| File | Bugs Fixed |
|---|---|
| `backend/app.py` | 1, 2, 3, 4, 14, 15 |
| `backend/models.py` | 4 |
| `backend/schema.sql` | 11 |
| `frontend/src/App.jsx` | 5, 6, 7, 8, 9, 10, 12, 13 + UI label |
