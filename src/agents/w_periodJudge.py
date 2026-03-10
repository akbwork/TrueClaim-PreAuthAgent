import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.config.llmClients import get_OpenAIClient
from src.prompts.w_period_p import WAITING_P_SYSTEM_PROMPT, WATING_P_USER_PROMPT

# OUTPUT SCHEMA
class ExclusionMatch(BaseModel):
    exclusion_name: str
    exclusion_category: str
    is_permanent: bool
    reasoning: str                      # why LLM thinks it matches

class WaitingPeriodMatch(BaseModel):
    disease_name: str
    icd10_code: str
    period_type: str                    # initialwaiting | pedwaiting | specificailment
    waiting_period_days: int
    days_elapsed: int
    days_remaining: int
    is_active: bool                     # True = still in waiting period
    reasoning: str

class ProcedureCoverageMatch(BaseModel):
    procedure_name: str
    is_covered: bool
    requires_pre_auth: bool
    waiting_period_days: int
    reasoning: str

class WaitingPeriodExclusionResult(BaseModel):
    exclusion_matches: list[ExclusionMatch]
    waiting_period_matches: list[WaitingPeriodMatch]
    procedure_coverage_matches: list[ProcedureCoverageMatch]
    hard_fail: bool                     # True if permanent exclusion OR active waiting period
    flags: list[str]
    findings: list[str]
    summary: str

# BRAIN
llm = get_OpenAIClient()
structured_llm = llm.with_structured_output(WaitingPeriodExclusionResult)

prompt = ChatPromptTemplate.from_messages([
    ("system", WAITING_P_SYSTEM_PROMPT),
    ("human", WATING_P_USER_PROMPT),
])

waiting_period_exclusion_chain = prompt | structured_llm