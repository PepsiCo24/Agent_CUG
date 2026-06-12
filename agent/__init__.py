"""
Agent Workflow 鈥?LangGraph + ReAct 瀹炵幇

宸ヤ綔娴侊細
User Input 鈫?Router 鈫?Memory Retrieval 鈫?RAG Retrieval 鈫?
Tool Planning 鈫?Tool Execution 鈫?Prompt Builder 鈫?LLM 鈫?Final Answer
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncIterator, Literal

from langgraph.graph import END, StateGraph

from agent.state import AgentState
from config import get_settings
from core import Message, MemoryItem
from llm import create_llm
from memory import MemoryManager
from prompt import (
    RAG_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)
from rag import RAGPipeline
from tools import ToolRegistry, create_tool_registry

logger = logging.getLogger(__name__)



def _clean_answer(text: str) -> str:
    """Clean up LLM output: fix spacing, normalization artifacts"""
    if not text:
        return text
    # Remove spaces between digits (tokenizer artifact: "4 053" -> "4053")
    text = re.sub(r"(?<=\d) (?=\d)", "", text)
    # Add space between CJK and Latin/numbers
    text = re.sub(r"([\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef])([a-zA-Z0-9])", r"\1 \2", text)
    text = re.sub(r"([a-zA-Z0-9])([\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef])", r"\1 \2", text)
    # Remove single newlines between CJK characters (tokenizer artifact)
    text = re.sub(r"([\u4e00-\u9fff\u3400-\u4dbf])\n([\u4e00-\u9fff\u3400-\u4dbf])", r"\1\2", text)
    text = re.sub(r"([a-zA-Z])\n([a-zA-Z])", r"\1\2", text)
    # Collapse multiple spaces
    text = re.sub(r"  +", " ", text)
    # Trim each line
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text

class AgentWorkflow:
    """Agent 宸ヤ綔娴佸紩鎿?""

    def __init__(self) -> None:
        self._llm = create_llm()
        self._memory = MemoryManager()
        self._rag = RAGPipeline()
        self._tool_registry = create_tool_registry()
        self._settings = get_settings()
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """鏋勫缓 LangGraph 鐘舵€佸浘"""
        workflow = StateGraph(AgentState)

        # 娣诲姞鑺傜偣
        workflow.add_node("router", self._router)
        workflow.add_node("memory_retrieval", self._memory_retrieval)
        workflow.add_node("rag_retrieval", self._rag_retrieval)
        workflow.add_node("tool_planning", self._tool_planning)
        workflow.add_node("tool_execution", self._tool_execution)
        workflow.add_node("prompt_builder", self._prompt_builder)
        workflow.add_node("llm_generate", self._llm_generate)

        # 鍏ュ彛
        workflow.set_entry_point("router")

        # 璺敱鍒嗘敮
        workflow.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "rag": "rag_retrieval",
                "tool": "tool_planning",
                "chat": "memory_retrieval",
            },
        )

        # 璁板繂妫€绱?鈫?涓嬩竴璺?
        workflow.add_conditional_edges(
            "memory_retrieval",
            self._after_memory,
            {
                "rag": "rag_retrieval",
                "tool": "tool_planning",
                "chat": "prompt_builder",
            },
        )

        # RAG 鈫?Prompt Builder
        workflow.add_edge("rag_retrieval", "prompt_builder")

        # 宸ュ叿瑙勫垝 鈫?宸ュ叿鎵ц
        workflow.add_conditional_edges(
            "tool_planning",
            self._after_tool_planning,
            {
                "execute": "tool_execution",
                "skip": "prompt_builder",
            },
        )

        # 宸ュ叿鎵ц 鈫?Prompt Builder
        workflow.add_edge("tool_execution", "prompt_builder")

        # Prompt Builder 鈫?LLM
        workflow.add_edge("prompt_builder", "llm_generate")

        # LLM 鈫?END
        workflow.add_edge("llm_generate", END)

        return workflow.compile()

    # ---- 鑺傜偣瀹炵幇 ----

    async def _router(self, state: AgentState) -> dict[str, Any]:
        """璺敱鍣細鍒嗘瀽鐢ㄦ埛鎰忓浘"""
        user_input = state["user_input"]
        logger.info(f"[Router] 鍒嗘瀽鐢ㄦ埛杈撳叆: {user_input[:50]}...")

        # 绠€鍗曡鍒欒矾鐢?
        input_lower = user_input.lower().strip()

        # If documents exist in knowledge base, always try RAG
        if self._rag.document_count > 0:
            state["next_action"] = "rag"
            return state

        # RAG keywords (fallback when no documents)
        rag_keywords = ["鏂囨。", "璧勬枡", "鐭ヨ瘑搴?, "鏂囦欢", "妫€绱?, "鎼滅储璧勬枡", "rag", "RAG"]
        if any(kw in input_lower for kw in rag_keywords):
            state["next_action"] = "rag"
            return state

        # Tool 
        tool_keywords = ["璁＄畻", "绠?, "=", "+", "-", "*", "/", "鏃堕棿", "鍑犵偣", "鏃ユ湡"]
        if any(kw in input_lower for kw in tool_keywords):
            state["next_action"] = "tool"
            return state

        # 榛樿锛氱洿鎺ュ璇?
        state["next_action"] = "chat"
        return state

    async def _memory_retrieval(self, state: AgentState) -> dict[str, Any]:
        """璁板繂妫€绱?""
        logger.info("[Memory] 妫€绱㈢浉鍏宠蹇?..")
        user_input = state["user_input"]

        # 妫€绱㈤暱鏈熻蹇?
        mem_items = await self._memory.retrieve(user_input, top_k=3)

        # 鑾峰彇杩戞湡瀵硅瘽
        recent = await self._memory.get_recent(limit=10)

        state["retrieved_memory"] = mem_items

        # 鏋勫缓璁板繂涓婁笅鏂?
        parts: list[str] = []
        if mem_items:
            parts.append("### 鐩稿叧璁板繂")
            for item in mem_items:
                parts.append(f"- [{item.role}]: {item.content[:200]}")

        if recent:
            parts.append("\n### 杩戞湡瀵硅瘽")
            for item in recent:
                parts.append(f"- [{item.role}]: {item.content[:200]}")

        state["memory_context"] = "\n".join(parts) if parts else ""
        return state

    async def _rag_retrieval(self, state: AgentState) -> dict[str, Any]:
        """RAG 妫€绱?""
        logger.info("[RAG] 妫€绱㈡枃妗?..")
        user_input = state["user_input"]
        doc_ids = state.get("doc_ids") or None

        if doc_ids:
            docs = await self._rag.query_with_doc_ids(user_input, doc_ids=doc_ids)
            context = "\n\n---\n\n".join(
                f"[鏂囨。 {i+1}] (鏉ユ簮: {d.metadata.get('source', '鏈煡')})\n{d.content}"
                for i, d in enumerate(docs)
            ) if docs else ""
        else:
            context, docs = await self._rag.query_with_context(user_input)

        state["retrieved_docs"] = docs
        state["rag_context"] = context

        logger.info(f"[RAG] 妫€绱㈠埌 {len(docs)} 绡囨枃妗?)
        return state

    async def _tool_planning(self, state: AgentState) -> dict[str, Any]:
        """宸ュ叿瑙勫垝"""
        logger.info("[Tool] 瑙勫垝宸ュ叿璋冪敤...")
        user_input = state["user_input"]

        # 绠€鍗曡鍒欙細妫€娴嬭绠楀拰鏃堕棿鐨勭簿纭渶姹?
        tool_calls: list[dict[str, Any]] = []

        if any(c in user_input for c in "+-*/%0123456789") and any(
            kw in user_input.lower() for kw in ["绠?, "=", "澶氬皯", "绛変簬", "璁＄畻"]
        ):
            tool_calls.append({
                "name": "calculate",
                "arguments": {"expression": user_input},
            })

        if any(kw in user_input.lower() for kw in ["鏃堕棿", "鍑犵偣", "鏃ユ湡", "鏄熸湡"]):
            tool_calls.append({
                "name": "get_current_time",
                "arguments": {},
            })

        state["tool_calls"] = tool_calls
        return state

    async def _tool_execution(self, state: AgentState) -> dict[str, Any]:
        """宸ュ叿鎵ц"""
        logger.info("[Tool] 鎵ц宸ュ叿...")
        observations: list[str] = []

        for tc in state.get("tool_calls", []):
            result = await self._tool_registry.execute(
                tc["name"], **tc.get("arguments", {})
            )
            if result.success:
                observations.append(f"[{tc['name']}]: {result.output}")
            else:
                observations.append(f"[{tc['name']}] 閿欒: {result.error}")

        state["observations"] = observations
        return state

    async def _prompt_builder(self, state: AgentState) -> dict[str, Any]:
        """鏋勫缓 Prompt"""
        # 姝よ妭鐐逛富瑕佹槸缁勮涓婁笅鏂囷紝瀹為檯 prompt 鍦?_llm_generate 涓瀯寤?
        return state

    async def _llm_generate(self, state: AgentState) -> dict[str, Any]:
        """LLM 鐢熸垚鏈€缁堝洖绛?""
        logger.info("[LLM] 鐢熸垚鍥炵瓟...")

        # 鏋勫缓娑堟伅
        messages: list[Message] = [
            Message(role="system", content=SYSTEM_PROMPT),
        ]

        # 娣诲姞 RAG 涓婁笅鏂?
        user_prompt = state["user_input"]
        rag_context = state.get("rag_context", "")
        memory_context = state.get("memory_context", "")
        observations = state.get("observations", [])

        extra_context: list[str] = []

        if rag_context:
            extra_context.append(f"## 鍙傝€冩枃妗n{rag_context}")

        if memory_context:
            extra_context.append(f"## 鍘嗗彶璁板繂\n{memory_context}")

        if observations:
            extra_context.append(f"## 宸ュ叿缁撴灉\n" + "\n".join(observations))

        if extra_context:
            user_prompt = (
                "\n\n".join(extra_context)
                + f"\n\n## 鐢ㄦ埛闂\n{user_prompt}"
            )

        messages.append(Message(role="user", content=user_prompt))

        # 鑾峰彇宸ュ叿瀹氫箟锛堝鏋滄湁宸ュ叿闇€姹傦級
        tools = None
        if state.get("tool_calls") or state.get("next_action") == "tool":
            tools = self._tool_registry.get_definitions()

        # 璋冪敤 LLM
        response = await self._llm.chat(messages, tools=tools)
        state["final_answer"] = response.content

        # 淇濆瓨鍒拌蹇?
        await self._memory.add(MemoryItem(
            id="",
            content=state["user_input"],
            role="user",
        ))
        await self._memory.add(MemoryItem(
            id="",
            content=response.content,
            role="assistant",
        ))

        return state

    # ---- 鏉′欢璺敱 ----

    def _route_decision(
        self, state: AgentState
    ) -> Literal["rag", "tool", "chat"]:
        return state["next_action"]  # type: ignore

    def _after_memory(
        self, state: AgentState
    ) -> Literal["rag", "tool", "chat"]:
        return state["next_action"]  # type: ignore

    def _after_tool_planning(
        self, state: AgentState
    ) -> Literal["execute", "skip"]:
        if state.get("tool_calls"):
            return "execute"
        return "skip"

    # ---- 鍏叡鎺ュ彛 ----

    async def run(self, user_input: str, conversation_id: str | None = None, doc_ids: list[str] | None = None) -> AgentState:
        """杩愯宸ヤ綔娴?""
        initial_state: AgentState = {
            "user_input": user_input,
            "conversation_id": conversation_id,
            "chat_history": [],
            "retrieved_docs": [],
            "retrieved_memory": [],
            "tool_calls": [],
            "observations": [],
            "rag_context": "",
            "memory_context": "",
            "final_answer": "",
            "next_action": "chat",
            "iteration": 0,
            "doc_ids": doc_ids,
        }

        result = await self._graph.ainvoke(initial_state)
        return result

    async def run_stream(
        self, user_input: str, conversation_id: str | None = None, doc_ids: list[str] | None = None
    ) -> AsyncIterator[str]:
        """娴佸紡杩愯宸ヤ綔娴?""
        # 鍏堢敤鍚屾妯″紡鎵ц妫€绱㈠拰宸ュ叿
        initial_state: AgentState = {
            "user_input": user_input,
            "conversation_id": conversation_id,
            "chat_history": [],
            "retrieved_docs": [],
            "retrieved_memory": [],
            "tool_calls": [],
            "observations": [],
            "rag_context": "",
            "memory_context": "",
            "final_answer": "",
            "next_action": "chat",
            "iteration": 0,
            "doc_ids": doc_ids,
        }

        # 鎵ц璺敱鍜屾绱?
        state = await self._router(initial_state)
        state = await self._memory_retrieval(state)

        if state["next_action"] == "rag" or self._rag.document_count > 0:
            state = await self._rag_retrieval(state)
        if state["next_action"] == "tool":
            state = await self._tool_planning(state)
            if state.get("tool_calls"):
                state = await self._tool_execution(state)

        # 鏋勫缓 prompt 骞舵祦寮忚緭鍑?
        messages: list[Message] = [
            Message(role="system", content=SYSTEM_PROMPT),
        ]

        user_prompt = state["user_input"]
        rag_context = state.get("rag_context", "")
        memory_context = state.get("memory_context", "")
        observations = state.get("observations", [])

        extra_context: list[str] = []
        if rag_context:
            extra_context.append(f"## 鍙傝€冩枃妗n{rag_context}")
        if memory_context:
            extra_context.append(f"## 鍘嗗彶璁板繂\n{memory_context}")
        if observations:
            extra_context.append(f"## 宸ュ叿缁撴灉\n" + "\n".join(observations))
        if extra_context:
            user_prompt = "\n\n".join(extra_context) + f"\n\n## 鐢ㄦ埛闂\n{user_prompt}"

        messages.append(Message(role="user", content=user_prompt))

        # Yield RAG document info for frontend display
        retrieved_docs = state.get("retrieved_docs", [])
        if retrieved_docs:
            import json as _json
            rag_docs_info = []
            for d in retrieved_docs:
                rag_docs_info.append({
                    "source": d.metadata.get("source", "unknown") if hasattr(d, "metadata") else "unknown",
                    "score": round(d.score, 4) if hasattr(d, "score") else 0,
                    "content_snippet": d.content[:200] if hasattr(d, "content") else ""
                })
            yield _json.dumps({"type": "rag_docs", "documents": rag_docs_info})

        # Store retrieved docs in memory system
        if retrieved_docs:
            for d in retrieved_docs:
                src = d.metadata.get("source", "unknown") if hasattr(d, "metadata") else "unknown"
                doc_content = d.content if hasattr(d, "content") else ""
                await self._memory.add(MemoryItem(
                    id="",
                    content=f"[RAG检索召回] 文档来源: {src} | 内容摘要: {doc_content[:500]}",
                    role="system",
                    metadata={"source": src, "type": "rag_retrieval", "score": d.score if hasattr(d, "score") else 0}
                ))

        # 娴佸紡杈撳嚭锛堝厛鍙戦€佸伐鍏疯皟鐢ㄤ俊鎭級
        if observations:
            import json as _json
            for obs in observations:
                if "]: " in obs:
                    parts = obs.split("]: ", 1)
                    tool_name = parts[0].replace("[", "")
                    tool_result = parts[1]
                    yield _json.dumps({"type": "tool_call", "name": tool_name, "result": tool_result})

        full_answer: str = ""
        async for token in self._llm.chat_stream(messages):
            full_answer += token
            yield token

        # Clean text formatting artifacts (number spacing, CJK breaks, etc.)
        full_answer = _clean_answer(full_answer)

        # 淇濆瓨璁板繂
        await self._memory.add(MemoryItem(
            id="", content=state["user_input"], role="user",
        ))
        await self._memory.add(MemoryItem(
            id="", content=full_answer, role="assistant",
        ))


# 鍏ㄥ眬鍗曚緥
_agent_instance: AgentWorkflow | None = None


def get_agent() -> AgentWorkflow:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AgentWorkflow()
    return _agent_instance

