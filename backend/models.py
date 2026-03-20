from datetime import date, datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = "category"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Expense(db.Model):
    __tablename__ = "expense"
    id = db.Column(db.Integer, primary_key=True)
    # BUG FIX: nullable=True so expenses can be orphaned when category is deleted
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=True)
    amount = db.Column(db.String(32), nullable=False)
    description = db.Column(db.String(512), default="")
    expense_date = db.Column(db.Date, nullable=False)
    is_deleted = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.relationship("Category", backref="expenses")
