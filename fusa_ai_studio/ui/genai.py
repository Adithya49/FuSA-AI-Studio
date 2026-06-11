from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import streamlit as st


T = TypeVar("T")


def run_genai_action(label: str, action: Callable[[], T]) -> T:
    with st.status(f"{label}: preparing request", expanded=True) as status:
        status.write("Collecting project context and building prompt.")
        status.update(label=f"{label}: sending request", state="running")
        status.write("Request sent. Waiting for GenAI response.")
        try:
            result = action()
        except Exception as exc:
            status.update(label=f"{label}: error", state="error")
            status.write(f"Error: {exc}")
            raise

        warning = getattr(result, "warning", "") or ""
        if warning:
            status.update(label=f"{label}: provider error", state="error")
            status.write(warning)
        else:
            status.update(label=f"{label}: response received", state="complete")
            status.write("GenAI response received successfully.")
        return result