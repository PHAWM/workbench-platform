#!/usr/bin/env python3
"""
Create the target Postgres database if it does not already exist.
Reads connection details from environment variables.
Called by the prestart container before running Alembic.
"""
import os
import psycopg2

conn = psycopg2.connect(
    host=os.environ["POSTGRES_HOST"],
    port=os.environ["POSTGRES_PORT"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
    dbname="postgres",
)
conn.autocommit = True
cur = conn.cursor()

db = os.environ["POSTGRES_DB"]
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db,))
if not cur.fetchone():
    cur.execute(f'CREATE DATABASE "{db}"')
    print(f"Database '{db}' created.")
else:
    print(f"Database '{db}' already exists.")

conn.close()
