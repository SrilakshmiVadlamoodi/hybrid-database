# Hybrid Database (VoltKart)

A small learning project for exploring core **database management system (DBMS)
concepts** hands-on, using a fictional D2C electronics store ("VoltKart") as the
example domain.

This is not a database engine — it's a set of scripts and a schema built on top of two
real database systems (**PostgreSQL** and **MongoDB**) to demonstrate, in a runnable
and observable way:

- Relational schema design and normalization (BCNF)
- Indexing (B-trees) and how they change query plans
- Concurrency control / locking (two-phase locking, the lost-update anomaly)
- Query optimization (`EXPLAIN ANALYZE`)
- Document modeling and polyglot persistence (SQL + NoSQL together)

See [`docs/OVERVIEW.md`](docs/OVERVIEW.md) for a full explanation of what the project
does and the DBMS concepts each script demonstrates.

## Prerequisites

- Python 3.10+
- PostgreSQL running locally (or reachable)
- MongoDB running locally (or reachable)

## Setup

1. **Create a virtual environment and install dependencies**
   ```bash
   cd voltkart
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   # source .venv/bin/activate   # macOS/Linux
   pip install -r requirements.txt
   ```

2. **Configure environment variables**

   Create a `voltkart/.env` file (it's gitignored, so it won't be committed):
   ```
   PGHOST=localhost
   PGPORT=5432
   PGUSER=postgres
   PGPASSWORD=your_password
   PGDATABASE=voltkart

   MONGO_URI=mongodb://localhost:27017
   MONGO_DB=voltkart
   ```

3. **Create the Postgres database**
   ```bash
   psql -U postgres -h localhost -c "CREATE DATABASE voltkart;"
   ```

4. **Load the schema**
   ```bash
   psql -U postgres -h localhost -d voltkart -f schema.sql
   ```

5. **Make sure MongoDB is running** — no manual setup needed; collections are created
   automatically on first write.

## Running

From inside `voltkart/` with the virtual environment activated:

```bash
python seed.py               # populate Postgres with ~300 synthetic rows
python indexing_demo.py      # query plan before/after adding a B-tree index
python concurrency_demo.py   # lost-update race, then the fix via row locking
python mongo_demo.py         # seed and query MongoDB chat transcripts
```

Each script prints its output directly to the terminal.

## Project structure

```
voltkart/
  schema.sql            PostgreSQL DDL: tables, keys, constraints
  normalization.md       Functional-dependency / BCNF proof for the schema
  seed.py                 Populates Postgres with synthetic data
  indexing_demo.py        B-tree indexing + query plan demo
  concurrency_demo.py     Locking / lost-update demo
  mongo_demo.py            MongoDB document modeling demo
  requirements.txt        Python dependencies
docs/
  OVERVIEW.md            Full explanation of the project and DBMS concepts used
```

## Why this project exists

This is a learning project for practicing and demonstrating fundamental DBMS concepts
— normalization, indexing, transactions/locking, query planning, and relational vs.
document data modeling — using real database engines rather than theory alone.
