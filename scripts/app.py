"""Streamlit chat UI for the CTI Attribution Agent (M4.14).

Launch::

    cd cti-agent
    streamlit run scripts/app.py
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(page_title="CTI Attribution Agent", layout="wide")
st.title("CTI Attribution Agent")
st.caption("M4.14 — Natural language interface to the agentic attribution system")

# ---------------------------------------------------------------------------
# Agent initialisation (cached across reruns)
# ---------------------------------------------------------------------------


@st.cache_resource
def _get_checkpointer():
    return MemorySaver()


@st.cache_resource
def _init_agent(_checkpointer):
    from cti_agent.agent.orchestrator import create_orchestrator_agent

    return create_orchestrator_agent(checkpointer=_checkpointer)


checkpointer = _get_checkpointer()
agent = _init_agent(checkpointer)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "last_meta" not in st.session_state:
    st.session_state.last_meta = {}

# ---------------------------------------------------------------------------
# Sidebar — attribution metadata + controls
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Last Attribution")
    meta = st.session_state.last_meta
    if meta:
        col1, col2 = st.columns(2)
        col1.metric("Confidence", meta.get("confidence", "—"))
        col2.metric("Iterations", meta.get("iterations", "—"))
        if meta.get("shared_infrastructure") == "true":
            st.warning("Shared infrastructure detected")
        if meta.get("enrichment_suggested") == "true":
            st.info("Domain required enrichment")
    else:
        st.caption("No attribution performed yet.")

    st.divider()
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.last_meta = {}
        st.rerun()

# ---------------------------------------------------------------------------
# Display chat history
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("tool_calls"):
            with st.expander("Tool Calls"):
                for tc in msg["tool_calls"]:
                    st.code(tc, language="json")
        if msg.get("evidence"):
            with st.expander("Evidence Chain"):
                for ev in msg["evidence"]:
                    st.text(ev)

# ---------------------------------------------------------------------------
# Chat input handler
# ---------------------------------------------------------------------------

if user_input := st.chat_input("Ask about a domain, threat actor, or CTI topic..."):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                config = {"configurable": {"thread_id": st.session_state.thread_id}}

                prior_state = agent.get_state(config)
                prior_count = len(prior_state.values.get("messages", [])) if prior_state.values else 0

                result = agent.invoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config,
                )

                all_msgs = result["messages"]
                new_msgs = all_msgs[prior_count + 1:]

                response_text = ""
                tool_calls_display: list[str] = []
                evidence: list[str] = []

                for msg in new_msgs:
                    if isinstance(msg, AIMessage):
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                args_str = json.dumps(
                                    tc.get("args", {}),
                                    ensure_ascii=False,
                                    indent=2,
                                )
                                tool_calls_display.append(
                                    f"{tc['name']}({args_str})"
                                )
                        if msg.content:
                            response_text = msg.content

                    elif isinstance(msg, ToolMessage):
                        preview = msg.content[:500]
                        if len(msg.content) > 500:
                            preview += "..."
                        evidence.append(f"[{msg.name}]\n{preview}")

                        if (
                            msg.name == "attribute_domain"
                            and "Metadata:" in msg.content
                        ):
                            meta_str = msg.content.split("Metadata:")[-1].strip()
                            parsed: dict[str, str] = {}
                            for item in meta_str.split(","):
                                if "=" in item:
                                    k, v = item.strip().split("=", 1)
                                    parsed[k.strip()] = v.strip()
                            st.session_state.last_meta = parsed

                if not response_text:
                    response_text = (
                        "Analysis complete. Expand the sections below for details."
                    )

                st.markdown(response_text)

                if tool_calls_display:
                    with st.expander("Tool Calls"):
                        for tc in tool_calls_display:
                            st.code(tc, language="json")

                if evidence:
                    with st.expander("Evidence Chain"):
                        for ev in evidence:
                            st.text(ev)

                sources_md = ""
                for ev_text in evidence:
                    if "## Sources" in ev_text:
                        idx = ev_text.index("## Sources")
                        sources_md = ev_text[idx:]
                        end = sources_md.find("\n## ", 3)
                        if end != -1:
                            sources_md = sources_md[:end]
                        break
                if sources_md:
                    with st.expander("Source References"):
                        st.markdown(sources_md)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response_text,
                        "tool_calls": tool_calls_display or None,
                        "evidence": evidence or None,
                    }
                )

            except Exception as exc:
                error_msg = f"Error: {exc}"
                st.error(error_msg)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
