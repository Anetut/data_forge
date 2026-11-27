"""Rules the database itself enforces, checked against the migrated test database."""

from datetime import timedelta

SET_UPDATED_AT = "EXECUTE FUNCTION set_updated_at()"


def _insert_manager(conn, updated_at):
    row = conn.execute(
        "INSERT INTO manager (name, email, hire_date, updated_at) "
        "VALUES ('Trigger Test', 'trigger-test@example.com', current_date, %s) "
        "RETURNING id",
        (updated_at,),
    ).fetchone()
    assert row is not None
    return row[0]


def test_insert_ignores_client_supplied_updated_at(conn, now):
    last_week = now - timedelta(days=7)
    manager_id = _insert_manager(conn, updated_at=last_week)
    # The whole test is one transaction, so now() is the exact value the trigger wrote.
    row = conn.execute(
        "SELECT updated_at, now() FROM manager WHERE id = %s", (manager_id,)
    ).fetchone()
    assert row is not None
    updated_at, transaction_time = row
    assert updated_at != last_week
    assert updated_at == transaction_time


def test_update_ignores_client_supplied_updated_at(conn, now):
    manager_id = _insert_manager(conn, updated_at=now)
    last_week = now - timedelta(days=7)
    row = conn.execute(
        "UPDATE manager SET name = 'Renamed', updated_at = %s WHERE id = %s "
        "RETURNING updated_at, now()",
        (last_week, manager_id),
    ).fetchone()
    assert row is not None
    updated_at, transaction_time = row
    assert updated_at != last_week
    assert updated_at == transaction_time


def test_every_table_with_updated_at_sets_it_on_insert_and_update(conn):
    """Guards future migrations: a new table with `updated_at` but no trigger fails here."""
    tables = {
        table
        for (table,) in conn.execute(
            "SELECT table_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'updated_at'"
        )
    }
    # One row per trigger and event: a correct trigger shows up once for INSERT, once for UPDATE.
    covered = set(
        conn.execute(
            "SELECT event_object_table, event_manipulation FROM information_schema.triggers "
            "WHERE trigger_schema = 'public' AND action_timing = 'BEFORE' "
            "AND action_orientation = 'ROW' AND action_statement = %s",
            (SET_UPDATED_AT,),
        )
    )
    required = {(table, event) for table in tables for event in ("INSERT", "UPDATE")}
    missing = sorted(required - covered)
    assert tables, "no table with an updated_at column found"
    assert missing == [], f"missing set_updated_at triggers: {missing}"
