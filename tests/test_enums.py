import re

import pytest

from dataforge.domain.enums import OrderStatus, PaymentMethod, PaymentStatus


@pytest.mark.parametrize(
    ("sql_enum_name", "python_enum"),
    [
        ("payment_method_enum", PaymentMethod),
        ("payment_status_enum", PaymentStatus),
        ("order_status_enum", OrderStatus),
    ],
)
def test_enum_mapping_to_sql(project_root, sql_enum_name, python_enum):
    sql_create_tables_path = project_root / "sql" / "init" / "01-create-tables.sql"
    sql_create_tables_content = sql_create_tables_path.read_text(encoding="utf-8")
    # Extract the enum values from the SQL create table content for the given enum name
    line_pattern = rf"CREATE\s+TYPE\s+{sql_enum_name}\s+AS\s+ENUM\s*\(([^)]*)\)"
    found_line = re.search(line_pattern, sql_create_tables_content, re.IGNORECASE)
    assert found_line is not None
    found_enum_value_string = found_line.group(1)
    enum_value_pattern = r"\'([^']*)\'"
    found_enum_values = re.findall(enum_value_pattern, found_enum_value_string)
    # Extract python enum values
    python_enum_values = [member.value for member in python_enum]
    assert found_enum_values == python_enum_values
