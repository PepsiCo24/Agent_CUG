"""
Agent Workflow — LangGraph + ReAct 实现

工作流：
User Input → Router → Memory Retrieval → RAG Retrieval →
Tool Planning → Tool Execution → Prompt Builder → LLM → Final Answer
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
    """Agent 工作流引擎"""

    def __init__(self) -> None:
        self._llm = create_llm()
        self._memory = MemoryManager()
        self._rag = RAGPipeline()
        self._tool_registry = create_tool_registry()
        self._settings = get_settings()
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 状态图"""
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("router", self._router)
        workflow.add_node("memory_retrieval", self._memory_retrieval)
        workflow.add_node("rag_retrieval", self._rag_retrieval)
        workflow.add_node("tool_planning", self._tool_planning)
        workflow.add_node("tool_execution", self._tool_execution)
        workflow.add_node("prompt_builder", self._prompt_builder)
        workflow.add_node("llm_generate", self._llm_generate)

        # 入口
        workflow.set_entry_point("router")

        # 路由分支
        workflow.add_conditional_edges(
            "router",
            self._route_decision,
            {
                "rag": "rag_retrieval",
                "tool": "tool_planning",
                "chat": "memory_retrieval",
            },
        )

        # 记忆检索 → 下一跳
        workflow.add_conditional_edges(
            "memory_retrieval",
            self._after_memory,
            {
                "rag": "rag_retrieval",
                "tool": "tool_planning",
                "chat": "prompt_builder",
            },
        )

        # RAG → Prompt Builder
        workflow.add_edge("rag_retrieval", "prompt_builder")

        # 工具规划 → 工具执行
        workflow.add_conditional_edges(
            "tool_planning",
            self._after_tool_planning,
            {
                "execute": "tool_execution",
                "skip": "prompt_builder",
            },
        )

        # 工具执行 → Prompt Builder
        workflow.add_edge("tool_execution", "prompt_builder")

        # Prompt Builder → LLM
        workflow.add_edge("prompt_builder", "llm_generate")

        # LLM → END
        workflow.add_edge("llm_generate", END)

        return workflow.compile()

    # ---- 节点实现 ----

    async def _router(self, state: AgentState) -> dict[str, Any]:
        """路由器：分析用户意图"""
        user_input = state["user_input"]
        mode = state.get("mode", "chat")
        logger.info(f"[Router] mode={mode}, input: {user_input[:50]}...")

        # Mode-driven routing (mode takes priority)
        if mode == "rag" or (state.get("doc_ids") and state.get("doc_ids")):
            state["next_action"] = "rag"
            return state
        if mode == "tool" or mode == "orchestrate":
            state["next_action"] = "tool"
            return state

        # 简单规则路由
        input_lower = user_input.lower().strip()

        # If documents exist in knowledge base, always try RAG
        if self._rag.document_count > 0:
            state["next_action"] = "rag"
            return state

        # RAG keywords (fallback when no documents)
        rag_keywords = ["文档", "资料", "知识库", "文件", "检索", "搜索资料", "rag", "RAG"]
        if any(kw in input_lower for kw in rag_keywords):
            state["next_action"] = "rag"
            return state

        # Tool 
        tool_keywords = ["计算", "算", "=", "+", "-", "*", "/", "时间", "几点", "日期"]
        if any(kw in input_lower for kw in tool_keywords):
            state["next_action"] = "tool"
            return state

        # 默认：直接对话
        state["next_action"] = "chat"
        return state

    async def _memory_retrieval(self, state: AgentState) -> dict[str, Any]:
        """记忆检索"""
        logger.info("[Memory] 检索相关记忆...")
        user_input = state["user_input"]

        # 检索长期记忆
        mem_items = await self._memory.retrieve(user_input, top_k=3)

        # 获取近期对话
        recent = await self._memory.get_recent(limit=10)

        state["retrieved_memory"] = mem_items

        # 构建记忆上下文
        parts: list[str] = []
        if mem_items:
            parts.append("### 相关记忆")
            for item in mem_items:
                parts.append(f"- [{item.role}]: {item.content[:200]}")

        if recent:
            parts.append("\n### 近期对话")
            for item in recent:
                parts.append(f"- [{item.role}]: {item.content[:200]}")

        state["memory_context"] = "\n".join(parts) if parts else ""
        return state

    async def _rag_retrieval(self, state: AgentState) -> dict[str, Any]:
        """RAG 检索"""
        logger.info("[RAG] 检索文档...")
        user_input = state["user_input"]
        doc_ids = state.get("doc_ids") or None

        if doc_ids:
            docs = await self._rag.query_with_doc_ids(user_input, doc_ids=doc_ids)
            context = "\n\n---\n\n".join(
                f"[文档 {i+1}] (来源: {d.metadata.get('source', '未知')})\n{d.content}"
                for i, d in enumerate(docs)
            ) if docs else ""
        else:
            context, docs = await self._rag.query_with_context(user_input)

        state["retrieved_docs"] = docs
        state["rag_context"] = context

        logger.info(f"[RAG] 检索到 {len(docs)} 篇文档")
        return state

    async def _tool_planning(self, state: AgentState) -> dict[str, Any]:
        """工具规划"""
        logger.info("[Tool] 规划工具调用...")
        user_input = state["user_input"]

        # 简单规则：检测计算和时间的精确需求
        tool_calls: list[dict[str, Any]] = []

        if any(c in user_input for c in "+-*/%0123456789") and any(
            kw in user_input.lower() for kw in ["算", "=", "多少", "等于", "计算"]
        ):
            tool_calls.append({
                "name": "calculate",
                "arguments": {"expression": user_input},
            })

        if any(kw in user_input.lower() for kw in ["时间", "几点", "日期", "星期"]):
            tool_calls.append({
                "name": "get_current_time",
                "arguments": {},
            })

        state["tool_calls"] = tool_calls
        return state


    async def _react_loop(self, state, max_iterations=5):
        """ReAct: Thought -> Action -> Observation for multi-tool orchestration"""
        user_input = state["user_input"]
        obs = state.get("observations", [])
        tcs = state.get("tool_calls", [])

        tools_desc = "\n".join(
            f"- {t.definition.name}: {t.definition.description}"
            for t in self._tool_registry._tools.values()
        )

        react_prompt = f"""You are an AI agent using ReAct.

Tools:
{tools_desc}

Task: {user_input}

Format:
Thought: [reasoning]
Action: [tool_name]
Action Input: {{JSON args}}
Observation: [result]
... (repeat)
Final Answer: [answer in Chinese]

Begin!"""

        messages = [Message(role="system", content=react_prompt)]

        for i in range(max_iterations):
            logger.info(f"[ReAct] iter {i+1}/{max_iterations}")
            try:
                resp = await self._llm.chat(messages)
                text = resp.content

                if "Final Answer:" in text:
                    state["final_answer"] = text.split("Final Answer:")[-1].strip()
                    state["observations"] = obs
                    state["tool_calls"] = tcs
                    state["next_action"] = "chat"
                    return state

                am = re.search(r"Action:\s*(\w+)", text)
                aim = re.search(r"Action Input:\s*(\{.+?\})", text, re.DOTALL)

                if am:
                    tn = am.group(1).strip()
                    ta = {}
                    if aim:
                        try: ta = json.loads(aim.group(1))
                        except: ta = {"query": user_input}

                    result = await self._tool_registry.execute(tn, **ta)
                    ot = f"[{tn}]: {result.output}"
                    if result.error: ot = f"[{tn}] err: {result.error}"

                    obs.append(ot)
                    tcs.append({"name": tn, "args": ta, "result": ot})
                    messages.append(Message(role="assistant", content=text))
                    messages.append(Message(role="user", content=ot))
                else:
                    state["final_answer"] = text
                    state["observations"] = obs
                    state["tool_calls"] = tcs
                    state["next_action"] = "chat"
                    return state
            except Exception as e:
                logger.error(f"[ReAct] err: {e}")
                obs.append(f"[Error] {e}")
                break

        state["final_answer"] = "[ReAct max iterations]\n" + "\n".join(obs)
        state["observations"] = obs
        state["tool_calls"] = tcs
        state["next_action"] = "chat"
        return state

    async def _tool_execution(self, state: AgentState) -> dict[str, Any]:
        """工具执行"""
        logger.info("[Tool] 执行工具...")
        observations: list[str] = []

        for tc in state.get("tool_calls", []):
            result = await self._tool_registry.execute(
                tc["name"], **tc.get("arguments", {})
            )
            if result.success:
                observations.append(f"[{tc['name']}]: {result.output}")
            else:
                observations.append(f"[{tc['name']}] 错误: {result.error}")

        state["observations"] = observations
        return state

    async def _prompt_builder(self, state: AgentState) -> dict[str, Any]:
        """构建 Prompt"""
        # 此节点主要是组装上下文，实际 prompt 在 _llm_generate 中构建
        return state

    async def _llm_generate(self, state: AgentState) -> dict[str, Any]:
        """LLM 生成最终回答"""
        logger.info("[LLM] 生成回答...")

        # 构建消息
        messages: list[Message] = [
            Message(role="system", content=SYSTEM_PROMPT),
        ]

        # 添加 RAG 上下文
        user_prompt = state["user_input"]
        rag_context = state.get("rag_context", "")
        memory_context = state.get("memory_context", "")
        observations = state.get("observations", [])

        extra_context: list[str] = []

        if rag_context:
            extra_context.append(f"## 参考文档\n{rag_context}")

        if memory_context:
            extra_context.append(f"## 历史记忆\n{memory_context}")

        if observations:
            extra_context.append(f"## 工具结果\n" + "\n".join(observations))

        if extra_context:
            user_prompt = (
                "\n\n".join(extra_context)
                + f"\n\n## 用户问题\n{user_prompt}"
            )

        messages.append(Message(role="user", content=user_prompt))

        # 获取工具定义（如果有工具需求）
        tools = None
        if state.get("tool_calls") or state.get("next_action") == "tool":
            tools = self._tool_registry.get_definitions()

        # 调用 LLM
        response = await self._llm.chat(messages, tools=tools)
        state["final_answer"] = response.content

        # 保存到记忆
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

    # ---- 条件路由 ----

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

    # ---- 公共接口 ----

    async def run(self, user_input: str, conversation_id: str | None = None, doc_ids: list[str] | None = None, mode: str = "chat") -> AgentState:
        """运行工作流"""
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
        self, user_input: str, conversation_id: str | None = None, doc_ids: list[str] | None = None, mode: str = "chat"
    ) -> AsyncIterator[str]:
        """流式运行工作流"""
        # 先用同步模式执行检索和工具
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

        # 执行路由和检索
        state = await self._router(initial_state)
        state = await self._memory_retrieval(state)

        if state["next_action"] == "rag" or self._rag.document_count > 0:
            state = await self._rag_retrieval(state)
        if state["next_action"] == "tool":
            state = await self._tool_planning(state)
            if state.get("tool_calls"):
                state = await self._tool_execution(state)

        # 构建 prompt 并流式输出
        messages: list[Message] = [
            Message(role="system", content=SYSTEM_PROMPT),
        ]

        user_prompt = state["user_input"]
        rag_context = state.get("rag_context", "")
        memory_context = state.get("memory_context", "")
        observations = state.get("observations", [])

        extra_context: list[str] = []
        if rag_context:
            extra_context.append(f"## 参考文档\n{rag_context}")
        if memory_context:
            extra_context.append(f"## 历史记忆\n{memory_context}")
        if observations:
            extra_context.append(f"## 工具结果\n" + "\n".join(observations))
        if extra_context:
            user_prompt = "\n\n".join(extra_context) + f"\n\n## 用户问题\n{user_prompt}"

        messages.append(Message(role="user", content=user_prompt))

        # 流式输出（先发送工具调用信息）
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


        # Store retrieved docs reference for later memory storage
        _retrieved_docs_for_memory = retrieved_docs

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

        # Store retrieved docs in memory (deferred to avoid blocking stream)
        if _retrieved_docs_for_memory:
            for d in _retrieved_docs_for_memory:
                src = d.metadata.get("source", "unknown") if hasattr(d, "metadata") else "unknown"
                doc_content = d.content if hasattr(d, "content") else ""
                await self._memory.add(MemoryItem(
                    id="",
                    content=f"[RAG检索召回] 文档来源: {src} | 内容摘要: {doc_content[:500]}",
                    role="system",
                    metadata={"source": src, "type": "rag_retrieval", "score": d.score if hasattr(d, "score") else 0}
                ))

        # 保存记忆
        await self._memory.add(MemoryItem(
            id="", content=state["user_input"], role="user",
        ))
        await self._memory.add(MemoryItem(
            id="", content=full_answer, role="assistant",
        ))


# 全局单例
_agent_instance: AgentWorkflow | None = None


def get_agent() -> AgentWorkflow:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AgentWorkflow()
    return _agent_instance
