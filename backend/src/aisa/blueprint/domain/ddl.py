from aisa.blueprint.domain.schemas import DbSchema


def render_ddl(schema: DbSchema) -> str:
    """Render PostgreSQL CREATE TABLE statements from a structured schema.

    We render DDL ourselves rather than trusting model-authored SQL, so the
    output is always syntactically valid."""
    statements: list[str] = []
    for table in schema.tables:
        if not table.name:
            continue
        lines = [
            f'  "{col.name}" {col.type or "TEXT"}{"" if col.nullable else " NOT NULL"}'
            for col in table.columns
            if col.name
        ]
        if table.primary_key:
            pk = ", ".join(f'"{c}"' for c in table.primary_key)
            lines.append(f"  PRIMARY KEY ({pk})")
        body = ",\n".join(lines)
        statements.append(f'CREATE TABLE "{table.name}" (\n{body}\n);')
    return "\n\n".join(statements)
