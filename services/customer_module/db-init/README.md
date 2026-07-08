Drop .sql files here (e.g. `01_schema.sql`, `02_seed.sql`) and Postgres will
run them automatically, in filename order, the first time the `postgres`
container starts with an empty data volume.

This is where you'd put the actual Kiotel DDL (CREATE TABLE statements for
the 45 tables) plus any seed data, so `docker compose up` gives you a fully
populated database to test against.
