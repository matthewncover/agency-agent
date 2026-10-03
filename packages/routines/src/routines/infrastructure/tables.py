"""SQLAlchemy Core mirrors of the `routines` schema (migration 0010).
Migrations own the DDL; these only describe the tables for queries."""

from sqlalchemy import BigInteger, Boolean, Column, Date, Integer, MetaData, Table, Text

metadata = MetaData(schema="routines")

item = Table(
    "item",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("person_id", BigInteger, nullable=False),
    Column("parent_id", BigInteger),
    Column("position", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("checked", Boolean, nullable=False),
)

person_state = Table(
    "person_state",
    metadata,
    Column("person_id", BigInteger, primary_key=True),
    Column("state_date", Date),
    Column("sent_date", Date),
)
