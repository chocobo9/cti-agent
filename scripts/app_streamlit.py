"""Streamlit chat UI for the CTI Attribution Agent.

Launch::

    cd cti-agent
    streamlit run scripts/app_streamlit.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="CTI Attribution Agent", page_icon="\U0001f50d", layout="wide")

# ---------------------------------------------------------------------------
# Warmup RAG pipeline (once per process)
# ---------------------------------------------------------------------------

@st.cache_resource
def _warmup():
    logger.info("Warming up RAG pipeline...")
    try:
        from rag_cti import _default_pipeline
        _default_pipeline()
        logger.info("RAG pipeline ready.")
    except Exception:
        logger.exception("RAG pipeline warmup failed")

    logger.info("Compiling attribution graph...")
    from cti_agent.agent.graph import compile_attribution_graph
    graph = compile_attribution_graph()
    logger.info("Graph ready.")
    return graph


graph = _warmup()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("CTI Attribution Agent")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Enter a query (e.g. Who is behind hamadryas.online?)")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                state = asyncio.run(graph.ainvoke({"query": user_input}))
            except Exception as exc:
                logger.exception("Attribution pipeline failed")
                st.error(f"Pipeline error: {type(exc).__name__}: {exc}")
                st.stop()

            report_data = state.get("attribution_report")
            if not report_data:
                st.warning("Pipeline returned no report.")
                st.stop()

            from cti_agent.agent.nodes.report import AttributionReport, render_report_markdown
            report = AttributionReport(**report_data)
            md = render_report_markdown(report)
            st.markdown(md)

            st.session_state.messages.append({"role": "assistant", "content": md})

            with st.expander("Evidence Chain"):
                for entry in state.get("evidence_chain", []):
                    st.text(entry)
