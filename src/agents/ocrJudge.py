from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
import json

from src.prompts.ocrvalidation_p import OCR_JUDGE_SYSTEM_PROMPT, OCR_JUDGE_USER_PROMPT
from src.config.llmClients import get_OpenAIClient

# OUTPUT SCHEMA
class DocumentCheck(BaseModel):
    document_type: str
    found: bool
    issues: list[str]
    observations: list[str]

class OCRValidationResult(BaseModel):
    policy_card_check: DocumentCheck
    patient_id_check: DocumentCheck
    prescription_check: DocumentCheck
    cross_document_consistency: list[str]  # e.g. name matches across all 3
    ai_misclassification_warnings: list[str]
    low_confidence_warnings: list[str]
    passed: bool
    summary: str  # 2-3 line human-readable summary for claim processor


# BRAIN
llm = get_OpenAIClient()
structured_llm = llm.with_structured_output(OCRValidationResult)

# Prompt Chain
prompt = ChatPromptTemplate.from_messages([
    ("system", OCR_JUDGE_SYSTEM_PROMPT),
    ("human", OCR_JUDGE_USER_PROMPT)
])

ocr_validation_chain = prompt | structured_llm

