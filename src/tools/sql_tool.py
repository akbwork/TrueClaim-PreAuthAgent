from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool

def get_sqltool(db, llm):
    """
    LLM Based Self Correcting Query Tool
    """
    return SQLDatabaseToolkit(db=db, llm=llm).get_tools()