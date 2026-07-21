# VoltKart — Hybrid Database Project

## What this project does

VoltKart is a case-study project for a fictional D2C (direct-to-consumer) electronics
store. It is not a database engine — it doesn't implement its own storage layer, query
planner, or transaction manager. Instead, it demonstrates **polyglot persistence**: using
two different, purpose-built database systems together in one application, and it
contains a set of scripts that exercise and explain core database-management-system
(DBMS) concepts against those systems.

The two systems used are:

- **PostgreSQL** — a relational (SQL) database, used for the store's core transactional
  data: customers, products, orders, order items, payments, and support tickets.
- **MongoDB** — a document (NoSQL) database, used for support-chat transcripts, which
  are naturally nested, variable-length, and don't fit a fixed relational schema well.

The two stores are linked logically (a Mongo `support_chats` document references a
Postgres `customer_id` / `order_id`), but not physically federated — the application
layer is responsible for joining data across them when needed.

## Why "hybrid"

Relational databases enforce a rigid schema, which is exactly what you want for
structured business records like orders and payments — you want guarantees like "every
order has a valid customer" and "stock can never go negative." But that same rigidity is
a poor fit for data like a support chat transcript, where each conversation has a
different number of messages, and each message is a small nested object. Forcing that
into relational tables would mean either a rigid `messages` table (fine, but requires a
join per conversation) or awkward workarounds.

VoltKart's answer is to use the right tool for each kind of data: relational storage for
structured, constraint-heavy records, and document storage for nested, schema-flexible
records. This pattern — combining a SQL and a NoSQL database in one system — is called
**polyglot persistence**.

## Project layout

```
voltkart/
  schema.sql            PostgreSQL DDL: 6 relational tables with keys and constraints
  normalization.md       Functional-dependency analysis and BCNF proof for the schema
  seed.py                 Populates Postgres with ~300 synthetic rows (via Faker)
  indexing_demo.py        Shows query plans before/after adding a B-tree index
  concurrency_demo.py     Demonstrates a lost-update race and its fix via row locking
  mongo_demo.py            Seeds/queries a MongoDB collection of chat transcripts
  requirements.txt        psycopg2-binary, pymongo, faker, python-dotenv
  .env                    Database connection settings (not committed)
```

## DBMS concepts demonstrated

### 1. Schema design and normalization
`schema.sql` defines six relational tables — `customers`, `products`, `orders`,
`order_items`, `payments`, `support_tickets` — using:

- **Primary keys** (`SERIAL`) to uniquely identify each row.
- **Foreign keys** (`REFERENCES ... ON DELETE CASCADE`) to enforce referential
  integrity between related tables (e.g. an `order_items` row cannot reference a
  nonexistent order).
- **Check constraints** to restrict columns to valid enumerated values (e.g. order
  status) or to non-negative numbers (e.g. price, stock).
- **Unique constraints** to prevent duplicate data (e.g. one account per email, one
  line item per product per order).

`normalization.md` walks through the functional dependencies of each table and proves
the schema satisfies **BCNF (Boyce-Codd Normal Form)** — the point at which every
determinant is a candidate key, so the schema is free of redundancy-causing anomalies.
It also explains specific design choices in normalization terms:

- `order_items` is a separate table from `orders` because an order can contain many
  products — keeping them in one table would create a repeating group, violating First
  Normal Form (1NF).
- `unit_price` is copied onto `order_items` at purchase time rather than looked up from
  `products.price`, because `products.price` can change later; storing it separately
  avoids a transitive dependency on a mutable value and preserves the historical price
  actually paid.
- `payments` is kept separate from `orders` since payment facts (method, status, time)
  depend on the payment, not on the order itself.

### 2. Indexing
`indexing_demo.py` demonstrates how a **B-tree index** changes query execution. It:

1. Runs a query filtering on `orders.customer_id` and captures the query plan with
   `EXPLAIN ANALYZE`, showing a **sequential scan** (the database reads every row).
2. Creates a B-tree index on that column.
3. Re-runs the same query, showing the planner now uses an **index scan** instead of
   scanning the whole table, run after `ANALYZE` — which refreshes the table statistics
   the query planner uses to make that choice.

The schema deliberately omits these indexes so the script can show the before/after
difference. `mongo_demo.py` similarly creates MongoDB indexes on `customer_id` and
`started_at` (MongoDB's default index type is also B-tree-based) to speed up point
lookups and range queries over chat transcripts.

**Why indexes matter:** without one, finding a customer's orders means scanning the
entire orders table; with a B-tree index, the database can navigate directly to the
matching rows in roughly logarithmic time.

### 3. Concurrency control and locking
`concurrency_demo.py` demonstrates a classic problem in concurrent transaction
processing — the **lost-update anomaly** — and how to fix it with locking.

- `buy_without_lock()` runs two purchases against the same product concurrently. Both
  transactions read the current stock value before either writes back, so the second
  write silently overwrites the first, and one decrement is lost. A `threading.Barrier`
  is used to force both reads to happen before either write, making the race reliably
  reproducible instead of a rare, timing-dependent bug.
- `buy_with_lock()` fixes the same scenario using `SELECT ... FOR UPDATE`, which takes
  an exclusive row lock at read time. This is an example of **two-phase locking (2PL)**:
  the lock is acquired during a growing phase (the read) and released only at commit
  (the shrinking phase), so a second transaction trying to read-and-update the same row
  blocks until the first transaction finishes.

This illustrates why database transactions need isolation guarantees beyond "run the
statements" — without locking (or an equivalent mechanism like MVCC-based conflict
detection), concurrent transactions can silently corrupt data even though each one looks
correct in isolation.

### 4. Query planning
The `EXPLAIN ANALYZE` usage in `indexing_demo.py` also serves as a small tour of how a
relational database's **query optimizer** works: it doesn't just execute SQL literally,
it chooses among multiple possible execution strategies (sequential scan vs. index
scan) based on cost estimates derived from table statistics, and those choices can be
inspected and reasoned about.

### 5. Document modeling
`mongo_demo.py` builds documents shaped like:

```json
{
  "customer_id": 42,
  "order_id": 108,
  "channel": "chat",
  "started_at": "...",
  "messages": [
    { "sender": "customer", "text": "...", "timestamp": "..." },
    { "sender": "agent", "text": "...", "timestamp": "..." }
  ]
}
```

and queries them by exact match (`customer_id`) and by range (`started_at`, sorted).
This is a direct contrast to the relational schema: instead of a `messages` table joined
to `support_tickets`, each conversation is stored as a single self-contained document
with its messages nested inline — appropriate because messages are always accessed
together with their parent conversation and vary in number per conversation.

### 6. Data seeding
`seed.py` populates the Postgres tables with deterministic synthetic data (seeded
random generation via Faker), including values that must stay consistent with the
schema's constraints — e.g. `orders.total_amount` is computed by summing the
associated `order_items`, and payments/tickets always reference customers and orders
that were just created, respecting the foreign-key relationships.

## What this project intentionally does not implement

To be clear about scope: VoltKart uses PostgreSQL and MongoDB as-is. It does not
implement any of the following itself — they're provided by the underlying database
engines and are outside this project's code:

- A custom storage engine or on-disk file format
- A buffer pool / page cache
- Write-ahead logging (WAL) or crash recovery
- Replication
- A network protocol or wire-level client/server layer
- A SQL parser or query planner
- Hash or LSM-tree indexing

The project's contribution is schema design, a normalization proof, and small,
targeted scripts that make three specific DBMS concepts (indexing, locking/concurrency,
and polyglot persistence) observable and reproducible against real database engines.
