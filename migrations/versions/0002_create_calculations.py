"""Add application calculations without changing the Module 9 exercise tables."""

from alembic import op
import sqlalchemy as sa


revision = "0002_create_calculations"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "calculations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("a", sa.Float(), nullable=False),
        sa.Column("b", sa.Float(), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("result", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "type IN ('add', 'subtract', 'multiply', 'divide')",
            name="ck_calculations_type",
        ),
        sa.CheckConstraint(
            "a > '-Infinity'::double precision AND a < 'Infinity'::double precision",
            name="ck_calculations_a_finite",
        ),
        sa.CheckConstraint(
            "b > '-Infinity'::double precision AND b < 'Infinity'::double precision",
            name="ck_calculations_b_finite",
        ),
        sa.CheckConstraint(
            "result > '-Infinity'::double precision AND result < 'Infinity'::double precision",
            name="ck_calculations_result_finite",
        ),
        sa.CheckConstraint("type <> 'divide' OR b <> 0", name="ck_calculations_divisor"),
        schema="calculator",
    )


def downgrade():
    op.drop_table("calculations", schema="calculator")
