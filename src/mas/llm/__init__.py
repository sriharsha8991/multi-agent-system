"""LLM layer: the shared typed contracts stamped onto artifacts.

The Gemini call itself now goes through ``langchain_google_genai.ChatGoogleGenerativeAI``
in ``agents.base.build_model`` — the hand-rolled ``google-genai`` client this package used
to own was superseded by the LangGraph migration and has been removed.
"""

from .schemas import Provenance, ValidationVerdict

__all__ = ["Provenance", "ValidationVerdict"]
