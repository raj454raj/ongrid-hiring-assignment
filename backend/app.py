"""
Expense Tracker API — Flask + MySQL.
"""
from datetime import datetime, date
from calendar import monthrange

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import Config
from models import db, Category, Expense


def _parse_pagination_args():
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=10, type=int)
    if page is None or per_page is None:
        return None, None, (jsonify({"error": "page and per_page must be integers"}), 400)
    if page < 1:
        return None, None, (jsonify({"error": "page must be >= 1"}), 400)
    if per_page < 1 or per_page > 50:
        return None, None, (jsonify({"error": "per_page must be between 1 and 50"}), 400)
    return page, per_page, None


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    CORS(app)

    with app.app_context():
        db.create_all()

    @app.route("/api/categories", methods=["GET"])
    def list_categories():
        rows = Category.query.order_by(Category.name).all()
        return jsonify([{"id": c.id, "name": c.name} for c in rows])

    @app.route("/api/categories", methods=["POST"])
    def create_category():
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name required"}), 400
        if Category.query.filter_by(name=name).first():
            return jsonify({"error": "exists"}), 409
        c = Category(name=name)
        db.session.add(c)
        db.session.commit()
        return jsonify({"id": c.id, "name": c.name}), 201

    @app.route("/api/categories/<int:cid>", methods=["DELETE"])
    def delete_category(cid):
        c = Category.query.get(cid)
        if not c:
            return jsonify({"error": "not found"}), 404
        Expense.query.filter_by(category_id=cid).update(
            {"is_deleted": 1, "category_id": None},
            synchronize_session=False,
        )
        db.session.delete(c)
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/api/expenses", methods=["GET"])
    def list_expenses():
        page, per_page, err = _parse_pagination_args()
        if err:
            return err
        offset = (page - 1) * per_page
        q = Expense.query.filter(Expense.is_deleted == 0)
        rows = q.order_by(Expense.expense_date.desc(), Expense.id.desc()).offset(offset).limit(per_page).all()
        total = q.count()
        return jsonify(
            {
                "items": [
                    {
                        "id": e.id,
                        "category_id": e.category_id,
                        "category_name": e.category.name if e.category else "",
                        "amount": str(e.amount),
                        "description": e.description or "",
                        "expense_date": e.expense_date.isoformat() if e.expense_date else None,
                    }
                    for e in rows
                ],
                "page": page,
                "per_page": per_page,
                "total": total,
            }
        )

    @app.route("/api/expenses", methods=["POST"])
    def create_expense():
        data = request.get_json() or {}
        category_id = data.get("category_id")
        amount = data.get("amount")
        description = data.get("description") or ""
        expense_date = data.get("expense_date")
        if category_id is None or amount is None or not expense_date:
            return jsonify({"error": "category_id, amount, expense_date required"}), 400
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid category"}), 400
        if not Category.query.get(category_id):
            return jsonify({"error": "invalid category"}), 400
        try:
            amount_num = float(amount)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid amount"}), 400
        if amount_num <= 0:
            return jsonify({"error": "amount must be > 0"}), 400
        try:
            parsed_date = datetime.strptime(str(expense_date)[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return jsonify({"error": "invalid expense_date"}), 400
        e = Expense(
            category_id=category_id,
            amount=f"{amount_num:.2f}",
            description=str(description)[:512],
            expense_date=parsed_date,
        )
        db.session.add(e)
        db.session.commit()
        return (
            jsonify(
                {
                    "id": e.id,
                    "category_id": e.category_id,
                    "amount": str(e.amount),
                    "description": e.description,
                    "expense_date": e.expense_date.isoformat(),
                }
            ),
            201,
        )

    @app.route("/api/expenses/<int:eid>", methods=["DELETE"])
    def delete_expense(eid):
        e = Expense.query.get(eid)
        if not e or e.is_deleted == 1:
            return jsonify({"error": "not found"}), 404
        e.is_deleted = 1
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/api/reports/monthly", methods=["GET"])
    def report_monthly():
        year = request.args.get("year", type=int)
        month = request.args.get("month", type=int)
        today = datetime.utcnow().date()
        if year is None:
            year = today.year
        if month is None:
            month = today.month
        if month < 1 or month > 12:
            return jsonify({"error": "month must be between 1 and 12"}), 400
        if year < 1900 or year > 3000:
            return jsonify({"error": "year out of allowed range"}), 400
        start = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        end = date(year, month, last_day)
        active = Expense.query.filter(
            Expense.expense_date >= start,
            Expense.expense_date <= end,
            Expense.is_deleted == 0,
        ).all()
        by_cat = {}
        for e in active:
            key = e.category_id
            if key is None:
                continue
            if key not in by_cat:
                by_cat[key] = {"category_id": key, "category_name": e.category.name if e.category else "", "total": 0.0}
            by_cat[key]["total"] += float(e.amount)
        series = [
            {"category_name": v["category_name"], "total": v["total"]}
            for v in by_cat.values()
        ]
        return jsonify(
            {
                "year": year,
                "month": month,
                "by_category": series,
                "category_totals_for_chart": [{"name": x["category_name"], "amt": x["total"]} for x in series],
            }
        )

    @app.route("/api/reports/monthly-trend", methods=["GET"])
    def report_monthly_trend():
        now = datetime.utcnow().date()
        buckets = []
        for i in range(5, -1, -1):
            total_months = now.year * 12 + now.month - 1 - i
            y, m = total_months // 12, total_months % 12 + 1
            start = date(y, m, 1)
            last = monthrange(y, m)[1]
            ed = date(y, m, last)
            rows = Expense.query.filter(
                Expense.expense_date >= start,
                Expense.expense_date <= ed,
                Expense.is_deleted == 0,
            ).all()
            s = sum(float(x.amount) for x in rows)
            buckets.append({"period": f"{y}-{m:02d}", "spend": s})
        return jsonify({"trend_rows": buckets})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
