from aisa.shared.config import Settings, normalize_async_dsn


def test_heroku_style_postgres_scheme_gets_asyncpg_driver() -> None:
    assert (
        normalize_async_dsn("postgres://u:p@host:5432/db")
        == "postgresql+asyncpg://u:p@host:5432/db"
    )


def test_postgresql_scheme_gets_asyncpg_driver() -> None:
    assert normalize_async_dsn("postgresql://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"


def test_sslmode_is_stripped_because_asyncpg_rejects_it() -> None:
    # Render's external URL carries ?sslmode=require, which asyncpg does not accept.
    assert (
        normalize_async_dsn("postgresql://u:p@host/db?sslmode=require")
        == "postgresql+asyncpg://u:p@host/db"
    )


def test_other_query_params_are_preserved() -> None:
    assert normalize_async_dsn("postgresql://u@h/db?sslmode=require&application_name=aisa") == (
        "postgresql+asyncpg://u@h/db?application_name=aisa"
    )


def test_already_normalized_url_is_untouched() -> None:
    url = "postgresql+asyncpg://u:p@host/db"
    assert normalize_async_dsn(url) == url


def test_settings_normalizes_database_url() -> None:
    settings = Settings(database_url="postgres://u:p@h/db?sslmode=require")
    assert settings.database_url == "postgresql+asyncpg://u:p@h/db"
