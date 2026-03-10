from langchain.agents import create_agent
from src.config.llmClients import get_OpenAIClient
from src.tools.sql_tool import get_sqltool
from src.config.dbClient import get_sql_database
from src.prompts.costagent_p import COST_AGENT_SYSTEM_PROMPT
from pydantic import BaseModel


class CostCheckResult(BaseModel):
    line_items: list[dict]          # each procedure with CGHS rate
    subtotal: float
    ward_adjustment_applied: str    # general / semi-pvt / private
    room_rent_admissible: float
    deductible_applied: float
    co_pay_applied: float
    recommended_approved_amount: float
    within_sum_insured: bool
    notes: list[str]


# Brain
llm_openai = get_OpenAIClient()

_SQL_TOOLS = None

def get_sql_tools():
    global _SQL_TOOLS
    if _SQL_TOOLS is None:
        _SQL_TOOLS = get_sqltool(db=get_sql_database(), llm=get_OpenAIClient())
    return _SQL_TOOLS

# SQL_TOOLS = get_sqltool(db=get_sql_database(), llm=get_OpenAIClient())

tools_list = _SQL_TOOLS

# Agent
cost_agent = create_agent(
    model=llm_openai,
    tools=tools_list,
    system_prompt=COST_AGENT_SYSTEM_PROMPT,
    name="cost_estimator"
)