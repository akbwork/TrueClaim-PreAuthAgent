from langgraph.graph import StateGraph, END
from src.graph.states import PreAuthState


from src.graph.node import data_loader_node, ocr_validation_node, policy_eligibility_node, waiting_period_and_exclusion_node, cost_check_node, sop_compliance_node, supervisor_node

def route_after_policy_check(state: PreAuthState) -> str:
    return "supervisor_node" if state["policy_check"]["hard_fail"] else "waiting_period_and_exclusion_node"

def route_after_waiting_period(state: PreAuthState) -> str:
    return "supervisor_node" if state["waiting_period_check"]["hard_fail"] else "cost_check_node"

graph = StateGraph(PreAuthState)

graph.add_node("data_loader_node",  data_loader_node)
graph.add_node("ocr_validation_node", ocr_validation_node)
graph.add_node("policy_eligibility_node", policy_eligibility_node)
graph.add_node("waiting_period_and_exclusion_node", waiting_period_and_exclusion_node)
graph.add_node("cost_check_node", cost_check_node)
graph.add_node("sop_compliance_node", sop_compliance_node)
graph.add_node("supervisor_node", supervisor_node)

graph.set_entry_point("data_loader_node")
graph.add_edge("data_loader_node", "ocr_validation_node")
graph.add_edge("ocr_validation_node", "policy_eligibility_node")
graph.add_conditional_edges("policy_eligibility_node",           route_after_policy_check)
graph.add_conditional_edges("waiting_period_and_exclusion_node", route_after_waiting_period)
graph.add_edge("cost_check_node", "sop_compliance_node")
graph.add_edge("sop_compliance_node", "supervisor_node")
graph.add_edge("supervisor_node", END)


app = graph.compile()

if __name__ == "__main__":
    result = app.invoke({"preauth_id": "b759d258-5e32-4fc2-91d1-e44f08f08510"})
    print(result["final_decision"])