import sys
import types
import importlib
from types import SimpleNamespace


def main():
    # Create a minimal fake `streamlit` module to exercise genai UI logic
    Fake = types.ModuleType("streamlit")
    Fake.session_state = {}
    Fake._buttons = {}

    def markdown(*args, **kwargs):
        return None

    def caption(*args, **kwargs):
        return None

    def expander(label, expanded=False):
        class Exp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        return Exp()

    def selectbox(label, options, key=None, **kwargs):
        val = Fake.session_state.get(key)
        if val in options:
            return val
        Fake.session_state[key] = options[0]
        return Fake.session_state[key]

    def text_area(label, value="", key=None, height=None):
        if key in Fake.session_state:
            return Fake.session_state[key]
        Fake.session_state[key] = value
        return value

    def chat_message(role):
        class CM:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def markdown(self, content):
                return None

        return CM()

    def columns(widths):
        class Col:
            def button(self, label, key=None):
                return Fake._buttons.pop(key, False)
        count = widths if isinstance(widths, int) else len(widths)
        return tuple(Col() for _ in range(count))

    def button(label, key=None):
        return Fake._buttons.pop(key, False)

    def rerun():
        raise RuntimeError("RERUN")

    Fake.markdown = markdown
    Fake.caption = caption
    Fake.expander = expander
    Fake.selectbox = selectbox
    Fake.text_area = text_area
    Fake.chat_message = chat_message
    Fake.columns = columns
    Fake.button = button
    Fake.rerun = rerun

    # Install fake into sys.modules before importing genai
    sys.modules["streamlit"] = Fake

    # Stub out UI components (they import pandas/streamlit in real code)
    comp = types.ModuleType("fusa_ai_studio.ui.components")
    def source_list(sources):
        return None
    comp.source_list = source_list
    sys.modules["fusa_ai_studio.ui.components"] = comp

    # Import the genai module (will pick up fake streamlit and stubbed components)
    importlib.invalidate_caches()
    genai = importlib.import_module("fusa_ai_studio.ui.genai")

    # Create fake services with an LLM that returns a revised text
    class FakeLLM:
        def generate(self, prompt, provider, model):
            return SimpleNamespace(provider="Local", model="local", text="REVISED: " + prompt[:80])

    class FakeRAG:
        def __init__(self):
            self.llm = FakeLLM()

    class FakeRepo:
        def get_setting(self, key, default=None):
            return default

        def store_ai_interaction(self, *args, **kwargs):
            return None

        def add_memory(self, *args, **kwargs):
            return None

    services = SimpleNamespace(rag=FakeRAG(), repo=FakeRepo(), knowledge=SimpleNamespace(index_artifacts=lambda *a, **k: None))

    # Prepare inputs
    answer = SimpleNamespace(text="Original answer", provider="Local", model="local", sources=[])
    panel_key = "testpanel"
    Fake.session_state.clear()
    # Simulate entering a chat question and pressing Send
    Fake.session_state[f"{panel_key}_chat_input"] = "Please suggest improvements"
    Fake._buttons[f"{panel_key}_send"] = True

    # First run: send chat message; draft should NOT be changed, but chat should contain assistant response
    try:
        genai.render_ai_response_with_chat(services, "proj", "feature", answer, panel_key)
    except RuntimeError as exc:
        if str(exc) != "RERUN":
            raise

    draft_key = f"{panel_key}_draft"
    messages_key = f"{panel_key}_messages"
    draft = Fake.session_state.get(draft_key)
    if draft != "Original answer":
        print("TEST FAILED: draft was unexpectedly modified")
        raise SystemExit(1)

    assistant_msgs = [m for m in Fake.session_state.get(messages_key, []) if m.get("role") == "assistant"]
    if not assistant_msgs or not assistant_msgs[-1].get("content", "").startswith("REVISED:"):
        print("TEST FAILED: assistant response not present in chat")
        raise SystemExit(1)

    # Simulate rerun (no button press). This should NOT reset draft back to original.
    try:
        genai.render_ai_response_with_chat(services, "proj", "feature", answer, panel_key)
    except RuntimeError as exc:
        if str(exc) != "RERUN":
            raise

    final = Fake.session_state.get(draft_key)
    if final != draft:
        print("TEST FAILED: draft was reset on rerun")
        raise SystemExit(1)

    print("TEST PASSED")


if __name__ == "__main__":
    main()
