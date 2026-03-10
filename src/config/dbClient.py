from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, text
from src.config.settings import DATABASE_URL

def get_sql_database() -> SQLDatabase:
    """
    Returns a LangChain SQLDatabase scoped to the tables
    the PreAuth agent actually needs.
    """
    return SQLDatabase.from_uri(
        DATABASE_URL,
        include_tables=[
            "policies",
            "policy_members",
            "policy_exclusions",
            "disease_waiting_periods",
            "pre_authorizations",
            "pre_auth_documents",
            "patients",
            "hospitals",
            "insurance_agencies",
            "procedure_coverage_rules",
        ],
        sample_rows_in_table_info=2,
    )


_engine = create_engine(DATABASE_URL, pool_pre_ping=True)

def run_query(sql: str, params: dict | None = None) -> list[dict]:
    with _engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        
        # Only fetch rows for SELECT queries — UPDATE/INSERT return no rows
        if result.returns_rows:
            cols = result.keys()
            rows = [dict(zip(cols, row)) for row in result.fetchall()]
            conn.commit()
            return rows
        
        conn.commit()
        return []