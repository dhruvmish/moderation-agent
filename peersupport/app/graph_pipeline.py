from __future__ import annotations
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from quickstart import SarcasmModel, ToxicityModel6, craft_serious_reply, craft_crisis_reply, PATH_SARCASM, PATH_TOX_BASE, PATH_TOX_LORA
from app.policy import seriousness_score, is_crisis

class MsgState(TypedDict):
    text: str
    user_id: str
    channel_id: str
    sarcasm: float
    tox_max: float
    seriousness: float
    action: Literal["none","serious","crisis"]
    reply: str

sarcasm_model = SarcasmModel(PATH_SARCASM)
tox_model = ToxicityModel6(PATH_TOX_BASE, PATH_TOX_LORA or None)


def node_sentinel(state: MsgState) -> MsgState:
    s = sarcasm_model.score(state["text"])
    tox = tox_model.scores(state["text"])  # dict of jigsaw labels
    tox_max = max(tox.values()) if tox else 0.0
    state.update({"sarcasm": s, "tox_max": tox_max, "seriousness": seriousness_score(tox_max, s)})
    return state


def node_triage(state: MsgState) -> MsgState:
    text = state["text"]
    if is_crisis(text):
        state["action"] = "crisis"
    else:
        # Only act on SERIOUS toxicity – ignore sarcasm-only cases
        state["action"] = "serious" if state["seriousness"] >= 0.60 and state["tox_max"] >= 0.85 and state["sarcasm"] <= 0.40 else "none"
    return state


def node_responder(state: MsgState) -> MsgState:
    if state["action"] == "serious":
        state["reply"] = craft_serious_reply(state["text"], state["sarcasm"], state["tox_max"], state["seriousness"]) or "Please keep our space safe and respectful."
    elif state["action"] == "crisis":
        state["reply"] = craft_crisis_reply(state["text"]) or "You're not alone. Consider reaching out to campus support — help is available."
    else:
        state["reply"] = ""
    return state


def node_archivist(state: MsgState) -> MsgState:
    # storage handled in bot after we redact + send; keep node simple
    return state

workflow = StateGraph(MsgState)
workflow.add_node("sentinel", node_sentinel)
workflow.add_node("triage", node_triage)
workflow.add_node("responder", node_responder)
workflow.add_node("archivist", node_archivist)
workflow.set_entry_point("sentinel")
workflow.add_edge("sentinel", "triage")
workflow.add_edge("triage", "responder")
workflow.add_edge("responder", "archivist")
workflow.add_edge("archivist", END)

app_graph = workflow.compile()
