"""
Expense Tracker API — Flask + MySQL.
"""
import os
from datetime import datetime, date
from calendar import monthrange

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import Config
from models import db, Category, Expense


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
        # Instead of deleting the category, we could soft delete it if we had an is_deleted flag.
        # But since the requirement is to fix bugs, let's at least mark expenses as deleted
        # or handle the foreign key constraint. Pymysql will throw error if enforced.
        # A better approach is to prevent deletion if expenses exist OR soft delete category.
        # Let's check for active expenses.
        active_expenses = Expense.query.filter_by(category_id=cid, is_deleted=0).count()
        if active_expenses > 0:
            return jsonify({"error": "Cannot delete category with active expenses"}), 400
        
        # Soft delete related expenses just in case
        Expense.query.filter_by(category_id=cid).update({"is_deleted": 1})
        db.session.delete(c)
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/api/expenses", methods=["GET"])
    def list_expenses():
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 10)), 50)
        offset = (page - 1) * per_page
        q = Expense.query.filter_by(is_deleted=0)
        rows = q.order_by(Expense.expense_date.desc(), Expense.id.desc()).offset(offset).limit(per_page).all()
        total = Expense.query.filter_by(is_deleted=0).count()
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
            cat_id_int = int(str(category_id))
        except (ValueError, TypeError):
            return jsonify({"error": "invalid category_id"}), 400

        if not Category.query.get(cat_id_int):
            return jsonify({"error": "invalid category"}), 400

        expense_date_str = str(expense_date)
        try:
            # Use partition instead of slice to avoid IDE "Cannot index into str" errors
            date_part = expense_date_str.partition('T')[0].partition(' ')[0]
            parsed_date = datetime.strptime(date_part, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "invalid date format, use YYYY-MM-DD"}), 400

        e = Expense(
            category_id=cat_id_int,
            amount=str(amount),
            description=str(description or ""),
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
        if not e:
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
            if key not in by_cat:
                by_cat[key] = {
                    "category_id": key,
                    "category_name": e.category.name if e.category else "",
                    "total": 0.0
                }
            # Explicitly cast to float to avoid type-check confusion
            amount_val = float(e.amount or 0)
            by_cat[key]["total"] = float(by_cat[key]["total"]) + amount_val
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
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
