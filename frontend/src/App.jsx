import { useCallback, useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

const API = "/api";

function App() {
  const [categories, setCategories] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [page, setPage] = useState(1);
  const [perPage] = useState(10);
  const [total, setTotal] = useState(0);
  const [monthlyByCat, setMonthlyByCat] = useState([]);
  const [trendData, setTrendData] = useState([]);
  const [chartError, setChartError] = useState(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [form, setForm] = useState({
    category_id: "",
    amount: "",
    description: "",
    expense_date: "",
  });
  const [catName, setCatName] = useState("");
  const [msg, setMsg] = useState("");

  const loadCategories = useCallback(async () => {
    const r = await fetch(`${API}/categories`);
    const data = await r.json();
    setCategories(Array.isArray(data) ? data : []);
  }, []);

  const loadExpenses = useCallback(async () => {
    const r = await fetch(
      `${API}/expenses?page=${page}&per_page=${perPage}`
    );
    const data = await r.json();
    setExpenses(data.items || []);
    setTotal(data.total || 0);
  }, [page, perPage]);

  const loadMonthlyReport = useCallback(async () => {
    const r = await fetch(
      `${API}/reports/monthly?year=${year}&month=${month}`
    );
    const data = await r.json();
    setMonthlyByCat(data.category_totals_for_chart || []);
  }, [year, month]);

  const loadTrend = useCallback(async () => {
    setChartError(null);
    try {
      const r = await fetch(`${API}/reports/monthly-trend`);
      const data = await r.json();
      const series = (data.trend_rows || []).map((row) => ({
        month: row.period,
        total: row.spend,
      }));
      setTrendData(series);
    } catch (e) {
      setChartError(String(e.message || e));
    }
  }, []);

  useEffect(() => {
    loadCategories();
  }, [loadCategories]);
  useEffect(() => {
    loadExpenses();
  }, [loadExpenses]);
  useEffect(() => {
    loadMonthlyReport();
  }, [loadMonthlyReport]);
  useEffect(() => {
    loadTrend();
  }, [loadTrend]);

  const addCategory = async (e) => {
    e.preventDefault();
    setMsg("");
    const r = await fetch(`${API}/categories`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: catName }),
    });
    if (r.ok) {
      setCatName("");
      loadCategories();
    } else {
      const j = await r.json().catch(() => ({}));
      setMsg(j.error || "Failed");
    }
  };

  const addExpense = async (e) => {
    e.preventDefault();
    setMsg("");
    const dateStr =
      form.expense_date ||
      new Date().toISOString().slice(0, 10);
    const r = await fetch(`${API}/expenses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category_id: Number(form.category_id),
        amount: form.amount,
        description: form.description,
        expense_date: dateStr,
      }),
    });
    if (r.ok) {
      setForm((f) => ({ ...f, amount: "", description: "" }));
      loadExpenses();
      loadMonthlyReport();
      loadTrend();
    } else {
      const j = await r.json().catch(() => ({}));
      setMsg(j.error || "Failed");
    }
  };

  const removeExpense = async (id) => {
    await fetch(`${API}/expenses/${id}`, { method: "DELETE" });
    loadExpenses();
    loadMonthlyReport();
    loadTrend();
  };

  const pageTotal = expenses.reduce((a, e) => a + parseFloat(e.amount || 0), 0);
  const totalPages = Math.ceil(total / perPage) || 1;

  return (
    <>
      <h1>Personal expense tracker</h1>

      <div className="card">
        <h2>Categories</h2>
        <form onSubmit={addCategory} className="row">
          <div>
            <label>Name</label>
            <input
              value={catName}
              onChange={(e) => setCatName(e.target.value)}
              placeholder="Food"
            />
          </div>
          <button type="submit">Add category</button>
        </form>
        <p className="muted">
          {categories.map((c) => c.name).join(", ") || "No categories yet."}
        </p>
      </div>

      <div className="card">
        <h2>Add expense</h2>
        <form onSubmit={addExpense}>
          <div className="row">
            <div>
              <label>Category</label>
              <select
                value={form.category_id}
                onChange={(e) =>
                  setForm((f) => ({ ...f, category_id: e.target.value }))
                }
              >
                <option value="">—</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label>Amount</label>
              <input
                type="text"
                inputMode="decimal"
                value={form.amount}
                onChange={(e) =>
                  setForm((f) => ({ ...f, amount: e.target.value }))
                }
                placeholder="12.50"
              />
            </div>
            <div>
              <label>Date</label>
              <input
                type="date"
                value={form.expense_date}
                onChange={(e) =>
                  setForm((f) => ({ ...f, expense_date: e.target.value }))
                }
              />
            </div>
          </div>
          <div className="row">
            <div style={{ flex: 1, maxWidth: "100%" }}>
              <label>Description</label>
              <input
                style={{ maxWidth: "100%" }}
                value={form.description}
                onChange={(e) =>
                  setForm((f) => ({ ...f, description: e.target.value }))
                }
                placeholder="Optional"
              />
            </div>
            <button type="submit">Add expense</button>
          </div>
        </form>
        {msg && <div className="error">{msg}</div>}
      </div>

      <div className="card">
        <h2>Reporting — {year}-{String(month).padStart(2, "0")}</h2>
        <div className="row">
          <div>
            <label>Year</label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </div>
          <div>
            <label>Month</label>
            <input
              type="number"
              min={1}
              max={12}
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            />
          </div>
        </div>
        <p className="muted">
          Sum on this page (strings): <strong>{String(pageTotal)}</strong>
        </p>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={monthlyByCat} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#38444d" />
              <XAxis dataKey="name" stroke="#8b98a5" />
              <YAxis stroke="#8b98a5" />
              <Tooltip
                contentStyle={{ background: "#1a1f26", border: "1px solid #38444d" }}
              />
              <Bar dataKey="amt" fill="#1d9bf0" name="Total" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <h2>Monthly trend (6 months)</h2>
        {chartError && <div className="error">{chartError}</div>}
        {!chartError && (
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trendData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#38444d" />
                <XAxis dataKey="month" stroke="#8b98a5" />
                <YAxis stroke="#8b98a5" />
                <Tooltip
                  contentStyle={{ background: "#1a1f26", border: "1px solid #38444d" }}
                />
                <Bar dataKey="total" fill="#7856ff" name="Spend" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Expenses (paginated)</h2>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Category</th>
              <th>Amount</th>
              <th>Note</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {expenses.map((e) => (
              <tr key={e.id}>
                <td>{e.expense_date}</td>
                <td>{e.category_name}</td>
                <td>{e.amount}</td>
                <td>{e.description}</td>
                <td>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => removeExpense(e.id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="pager">
          <button
            type="button"
            className="ghost"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Prev
          </button>
          <span className="muted">
            Page {page} / {totalPages} (total {total})
          </span>
          <button
            type="button"
            className="ghost"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </>
  );
}

export default App;
