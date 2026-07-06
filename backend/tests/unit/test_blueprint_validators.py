from aisa.blueprint.domain.ddl import render_ddl
from aisa.blueprint.domain.schemas import (
    ApiSpec,
    Column,
    DbSchema,
    DiagramEdge,
    DiagramNode,
    DiagramSpec,
    Endpoint,
    Table,
)
from aisa.blueprint.domain.validators import (
    validate_api_spec,
    validate_db_schema,
    validate_diagram,
)


def test_valid_diagram_has_no_problems() -> None:
    spec = DiagramSpec(
        nodes=[
            DiagramNode(id="api", label="API"),
            DiagramNode(id="db", label="DB", type="datastore"),
        ],
        edges=[DiagramEdge(source="api", target="db", label="reads/writes")],
    )
    assert validate_diagram(spec) == []


def test_diagram_dangling_edge_is_flagged() -> None:
    spec = DiagramSpec(
        nodes=[DiagramNode(id="api", label="API")],
        edges=[DiagramEdge(source="api", target="ghost")],
    )
    problems = validate_diagram(spec)
    assert any("ghost" in p for p in problems)


def test_api_spec_validation() -> None:
    good = ApiSpec(endpoints=[Endpoint(method="GET", path="/orders", summary="list")])
    assert validate_api_spec(good) == []
    bad = ApiSpec(
        endpoints=[
            Endpoint(method="FETCH", path="/orders", summary="x"),
            Endpoint(method="GET", path="orders", summary="y"),
        ]
    )
    assert len(validate_api_spec(bad)) == 2


def test_db_schema_renders_and_parses() -> None:
    schema = DbSchema(
        tables=[
            Table(
                name="orders",
                columns=[
                    Column(name="id", type="UUID", nullable=False),
                    Column(name="total", type="NUMERIC"),
                ],
                primary_key=["id"],
            )
        ]
    )
    ddl = render_ddl(schema)
    assert 'CREATE TABLE "orders"' in ddl
    assert '"id" UUID NOT NULL' in ddl
    assert 'PRIMARY KEY ("id")' in ddl
    assert validate_db_schema(schema) == []


def test_empty_db_schema_is_valid() -> None:
    assert validate_db_schema(DbSchema()) == []
