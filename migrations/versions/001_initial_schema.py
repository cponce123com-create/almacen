"""Migración inicial con todos los modelos.

Revision ID: 001
Revises: 
Create Date: 2026-05-13 15:56:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Modelos: User, Producto, Entrada, Salida, AuditLog, Familia, Almacen, OrdenCompra ###
    
    op.create_table(
        "almacenes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("direccion", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    
    op.create_table(
        "familias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
    )
    op.create_index(op.f("ix_familias_nombre"), "familias", ["nombre"])
    
    op.create_table(
        "ordenes_compra",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.String(length=50), nullable=False),
        sa.Column("proveedor", sa.String(length=200), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("numero"),
    )
    
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tabla", sa.String(length=50), nullable=False),
        sa.Column("registro_id", sa.Integer(), nullable=False),
        sa.Column("campo", sa.String(length=50), nullable=False),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_nuevo", sa.Text(), nullable=True),
        sa.Column("usuario", sa.String(length=80), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_tabla"), "audit_log", ["tabla"])
    op.create_index(op.f("ix_audit_log_timestamp"), "audit_log", ["timestamp"])
    
    op.create_table(
        "productos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("cod_catalogo", sa.String(length=50), nullable=True),
        sa.Column("descripcion", sa.String(length=300), nullable=False),
        sa.Column("um", sa.String(length=20), nullable=False),
        sa.Column("familia", sa.String(length=100), nullable=True),
        sa.Column("familia_id", sa.Integer(), nullable=True),
        sa.Column("almacen_id", sa.Integer(), nullable=True),
        sa.Column("stock_actual", sa.Float(), nullable=False),
        sa.Column("stock_minimo", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["almacen_id"], ["almacenes.id"], ),
        sa.ForeignKeyConstraint(["familia_id"], ["familias.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo"),
    )
    op.create_index(op.f("ix_productos_codigo"), "productos", ["codigo"])
    op.create_index(op.f("ix_productos_familia_id"), "productos", ["familia_id"])
    
    op.create_table(
        "entradas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Float(), nullable=False),
        sa.Column("um", sa.String(length=20), nullable=True),
        sa.Column("zona", sa.String(length=50), nullable=True),
        sa.Column("ubicacion", sa.String(length=100), nullable=True),
        sa.Column("alm", sa.String(length=50), nullable=True),
        sa.Column("fecha_ingreso", sa.DateTime(), nullable=True),
        sa.Column("oc", sa.String(length=50), nullable=True),
        sa.Column("guia_remision", sa.String(length=50), nullable=True),
        sa.Column("familia", sa.String(length=100), nullable=True),
        sa.Column("oc_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["oc_id"], ["ordenes_compra.id"], ),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    
    op.create_table(
        "salidas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Float(), nullable=False),
        sa.Column("um", sa.String(length=20), nullable=True),
        sa.Column("fecha_salida", sa.DateTime(), nullable=True),
        sa.Column("nro_vale", sa.String(length=50), nullable=True),
        sa.Column("oi", sa.String(length=50), nullable=True),
        sa.Column("c_costo", sa.String(length=100), nullable=True),
        sa.Column("maquina", sa.String(length=100), nullable=True),
        sa.Column("categoria", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### Eliminar tablas en orden inverso ###
    op.drop_table("salidas")
    op.drop_table("entradas")
    op.drop_table("productos")
    op.drop_index(op.f("ix_audit_log_timestamp"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_tabla"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_table("ordenes_compra")
    op.drop_index(op.f("ix_familias_nombre"), table_name="familias")
    op.drop_table("familias")
    op.drop_table("almacenes")
    # ### end Alembic commands ###
