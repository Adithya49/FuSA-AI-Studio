from __future__ import annotations

import pandas as pd
import streamlit as st


def data_table(rows: list[dict], empty: str) -> None:
    if not rows:
        st.info(empty)
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def source_list(sources: list[dict]) -> None:
    if not sources:
        st.caption("No retrieved sources were available.")
        return
    with st.expander("Retrieved RAG sources", expanded=False):
        for source in sources:
            meta = source.get("metadata", {})
            st.markdown(f"**{meta.get('title', source.get('id', 'Source'))}** · score `{source.get('score', 0)}`")
            st.caption(source.get("content", "")[:500])


def asil_badge(asil: str) -> str:
    return {"QM": "QM", "A": "ASIL A", "B": "ASIL B", "C": "ASIL C", "D": "ASIL D"}.get(asil, asil)
