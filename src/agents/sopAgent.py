from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langchain_core.tools import Tool
from langchain_tavily import TavilySearch
from langchain_community.vectorstores import SupabaseVectorStore
# from langchain_openai import OpenAIEmbeddings
from supabase import create_client

# from src.config.settings import SUPABASE_URL, SUPABASE_KEY

from src.config.settings import TAVILY_API
from src.config.llmClients import get_OpenAIClient

# embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
# supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# # Treatment SOP vector store — documents like clinical protocols,
# # CGHS treatment guidelines, NMC circulars
# treatment_sop_store = SupabaseVectorStore(
#     client=supabase_client,
#     embedding=embeddings,
#     table_name="treatment_sop_embeddings",
#     query_name="match_treatment_sop",
# )

# # Billing SOP vector store — documents like billing norms,
# # package rate circulars, itemised billing rules
# billing_sop_store = SupabaseVectorStore(
#     client=supabase_client,
#     embedding=embeddings,
#     table_name="billing_sop_embeddings",
#     query_name="match_billing_sop",
# )

# treatment_sop_tool = Tool(
#     name="treatment_sop_search",
#     func=lambda q: treatment_sop_store.similarity_search(q, k=4),
#     description=(
#         "Search treatment SOPs and clinical guidelines. Use this to check if "
#         "the proposed treatment, duration, and specialty are aligned with "
#         "standard treatment protocols for the diagnosed condition."
#     )
# )

# billing_sop_tool = Tool(
#     name="billing_sop_search",
#     func=lambda q: billing_sop_store.similarity_search(q, k=4),
#     description=(
#         "Search billing SOPs and package rate norms. Use this to verify if "
#         "the estimated cost, itemised charges, and billing structure comply "
#         "with standard billing guidelines."
#     )
# )

web_search_tool = TavilySearch(
    max_results=3,
    tavily_api_key=TAVILY_API,
    description=(
        "Search the internet for clinical guidelines, drug interactions, "
        "or treatment protocols not found in internal SOPs."
    )
)

SOP_AGENT_SYSTEM_PROMPT = """You are a medical insurance SOP compliance analyst.

You will receive a pre-authorization request with proposed treatment, estimated cost,
duration, and all prior validation findings.

Your job is to check:
1. TREATMENT SOP: Is the proposed treatment, expected duration, and required specialty
   aligned with standard clinical guidelines for this condition?
2. BILLING SOP: Is the estimated cost reasonable? Does the billing structure comply
   with standard norms (no unbundling, no upcoding)?
3. DOCUMENTATION: Are the submitted documents (prescription, policy card, patient ID)
   sufficient per SOP requirements for this type of treatment?

Use treatment_sop_search and billing_sop_search first.
Only use web search if internal SOPs don't have enough information.

Return a JSON object with this exact structure:
{
  "treatment_sop_compliant": true/false,
  "treatment_findings": ["finding 1", "finding 2"],
  "billing_sop_compliant": true/false,
  "billing_findings": ["finding 1", "finding 2"],
  "documentation_adequate": true/false,
  "documentation_findings": ["finding 1"],
  "flags": ["FLAG_1", "FLAG_2"],
  "passed": true/false,
  "summary": "2-3 line summary for claim processor"
}
"""

# try:
#     treatment_sop_store = SupabaseVectorStore(...)
#     billing_sop_store = SupabaseVectorStore(...)
#     sop_tools = [treatment_sop_tool, billing_sop_tool, web_search_tool]
# except Exception as e:
#     print(f"Warning: Vector stores not available - {e}. SOP agent will use web search only.")
#     sop_tools = [web_search_tool]

sop_tools = [web_search_tool]

sop_agent = create_agent(
    model=get_OpenAIClient(),
    tools=sop_tools,
    system_prompt=SOP_AGENT_SYSTEM_PROMPT,
    name="sop_compliance_agent"
)
