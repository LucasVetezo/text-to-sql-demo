"""
Unified query router — /api/unified/query

Classification pipeline
-----------------------
1. Regex pre-checks for strong domain signals (credit, sentiment, speech).
2. History-aware inference: when the current query is ambiguous or a short
   follow-up, `_infer_domain_from_history()` scans recent assistant messages
   for vocabulary fingerprints (cx_score, transcript, risk_score, etc.) and
   inherits the domain from the active conversation thread.  This replaces
   brittle keyword patching for context-dependent turns like "tell me more",
   "give me a detailed analysis of this call", "why did that happen?".
3. Pattern-match fallback across the four specialist domains.
4. Credit is the catch-all default when no other signal fires.

Fan-out & synthesis
-------------------
For multi-domain queries the router calls all relevant specialist agents in
parallel via asyncio.gather(), then synthesises a single coherent response
through GPT.  The frontend always receives one AgentResponse.
"""

import asyncio
import re
import time
import uuid
from typing import Any

import openai
from fastapi import APIRouter
from openai import AsyncOpenAI

from app.agents.credit_sql_agent import credit_sql_graph
from app.agents.fraud_sql_agent import fraud_sql_graph
from app.agents.sentiment_agent import sentiment_graph
from app.agents.speech_agent import speech_graph
from app.config import settings
from app.routers._agent_utils import invoke_agent
from app.schemas.responses import AgentRequest, AgentResponse

router = APIRouter(prefix="/api/unified", tags=["Unified Intelligence"])

# ── Domain registry ────────────────────────────────────────────────────────────
_DOMAINS = [
    {
        "key": "fraud",
        "pattern": re.compile(
            r"fraud|transact|suspicious|flagg|risk.?score|merchant|dispute|stolen|phish",
            re.I,
        ),
        "graph": fraud_sql_graph,
        "use_case": "fraud-sql",
        "label": "Fraud Intelligence",
    },
    {
        "key": "sentiment",
        "pattern": re.compile(
            # Social/sentiment domain: match posts, platforms, and brand perception signals.
            # Visual intent words (chart, graph, visual, plot) are NOT domain signals —
            # they describe the desired output format, not the data source.
            r"sentiment|social|twitter|x\.com|linkedin|post|review|feedback|brand|"
            r"complaint|public opinion",
            re.I,
        ),
        "graph": sentiment_graph,
        "use_case": "sentiment",
        "label": "Social Sentiment",
    },
    {
        "key": "speech",
        "pattern": re.compile(
            r"call.?cent|speech|transcript|cx|customer.?experience|voice|recording|"
            r"agent.?(score|rating)|sipho|nomsa",
            re.I,
        ),
        "graph": speech_graph,
        "use_case": "speech",
        "label": "CX & Speech",
    },
    {
        "key": "credit",
        "pattern": re.compile(r".*", re.I),   # default fallback
        "graph": credit_sql_graph,
        "use_case": "credit-sql",
        "label": "Credit Intelligence",
    },
]

# Credit signals require genuine data-intent phrasing — not just the word "credit" in isolation,
# which appears naturally in follow-up questions about sentiment topics.
_CREDIT_SIGNALS = re.compile(
    r"decline.?rate|approval.?rate|credit.?score|lend|loan.?applic"
    r"|applic(?:ation)?\s+(?:rate|decline|approval|reject|trend)"
    r"|correlat.{0,20}credit|credit.{0,20}correlat"
    r"|credit.{0,20}(?:data|metric|kpi|statistic|figure|number)",
    re.I,
)
_SENTIMENT_SIGNALS = re.compile(
    # Genuine sentiment-domain signals: platform names, sentiment vocabulary, brand-perception terms.
    # Deliberately excludes chart/graph/visual/plot — those describe output format, not domain.
    r"sentiment|social|twitter|linkedin|post|brand|complaint|feedback|correl|spike",
    re.I,
)
_SPEECH_SIGNALS = re.compile(
    # Strong CX/speech-domain signals — prioritised over generic "sentiment" keyword.
    r"call.?cent|call.?transcript|transcript|call.?record|cx\b|customer.?experience"
    r"|agent.?(?:score|rating|call|perform)|sipho|nomsa|whisper|call.?analys"
    r"|interact.{0,30}agent|agent.{0,30}interact",
    re.I,
)
# Conversational / general queries — greetings, thanks, meta questions, small talk.
# These must NOT be routed to a specialist SQL agent.
_CONVERSATIONAL = re.compile(
    r"^\s*(?:"
    r"hi+|hello+|hey+|howdy|greetings"
    r"|good\s+(?:morning|afternoon|evening|day)"
    r"|thank(?:s| you)(?:\s+so\s+much|\s+a\s+lot|\s+very\s+much)?"
    r"|bye(?:bye)?|goodbye|see\s+you"
    r"|ok(?:ay)?|got\s+it|sure|great|sounds\s+good|perfect|cool"
    r"|how\s+are\s+you|what(?:'s|\s+is)\s+up"
    r"|what\s+(?:can\s+you\s+do|are\s+you|do\s+you\s+do)"
    r"|who\s+are\s+you|tell\s+me\s+about\s+yourself"
    r"|help(?:\s+me)?"
    r")\s*[?!.]*\s*$",
    re.I,
)

# Chart follow-up: user is interrogating an already-rendered visual or referencing previous output.
# These queries belong purely in the sentiment domain — no need to hit the credit SQL agent.
_CHART_FOLLOWUP = re.compile(
    r"pie.?chart|bar.?chart|the\s+(?:graph|chart|visual|breakdown|plot|donut)"
    r"|according\s+to\s+(?:the\s+)?(?:chart|graph|data|pie|visual|breakdown)"
    r"|you(?:'re|\s+are)\s+telling\s+me|you\s+said|so\s+are\s+you"
    r"|what\s+(?:does\s+)?(?:this|that|the)\s+(?:mean|suggest|indicate|tell|show)"
    r"|the\s+\d+\s*%|that\s+means|in\s+(?:the\s+)?(?:context|light)\s+of",
    re.I,
)


_GENERAL_DOMAIN = {"key": "general", "label": None}


# ── Domain vocabulary fingerprints (used for history-based context inference) ──
# Each key maps to signals that strongly suggest the assistant was in that domain.
_DOMAIN_FINGERPRINTS: dict[str, re.Pattern] = {
    "speech": re.compile(
        r"call_id|transcript|cx.?score|agent.{0,20}(?:name|score|call)"
        r"|resolution.?status|call.?(?:summary|reason|duration|centre)"
        r"|customer.?experience|contact.?centre",
        re.I,
    ),
    "fraud": re.compile(
        r"fraud|transaction.?(?:id|amount|flag)|risk.?score|dispute|merchant",
        re.I,
    ),
    "sentiment": re.compile(
        r"social.?post|twitter|linkedin|sentiment.?(?:label|score|breakdown)"
        r"|platform.{0,30}(?:positive|negative)|brand.?(?:sentiment|perception)",
        re.I,
    ),
    "credit": re.compile(
        r"applic(?:ation)?.?(?:id|rate|status)|credit.?score|loan.?applic"
        r"|decline.?rate|approval.?rate",
        re.I,
    ),
}


def _infer_domain_from_history(history: list[dict]) -> str | None:
    """
    Scan the last few assistant messages and return the domain key whose
    fingerprint vocabulary is most present.  Returns None if no clear signal.
    """
    # Only look at the most recent assistant turns (up to last 3)
    assistant_text = " ".join(
        m["content"]
        for m in reversed(history)
        if m.get("role") == "assistant" and m.get("content")
    )[:2000]  # cap chars to keep it fast

    if not assistant_text:
        return None

    scores: dict[str, int] = {}
    for domain_key, pattern in _DOMAIN_FINGERPRINTS.items():
        scores[domain_key] = len(pattern.findall(assistant_text))

    best_key, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_key if best_score >= 2 else None


# A query is considered "context-dependent" (i.e. a follow-up that can't be
# classified on its own) when it is short, contains mostly pronouns/determiners,
# and has no strong domain keyword.
_AMBIGUOUS_FOLLOWUP = re.compile(
    r"^\s*(?:"
    r"(?:i\s+want|give\s+me|show\s+me|tell\s+me|can\s+you|please)"
    r".{0,60}"
    r"(?:this|that|it|these|those|more|details?|analysis|breakdown|summary|report)"
    r"|(?:expand|elaborate|drill.?down|go.?deeper|more.?detail|break.?down)"
    r"|(?:what|why|how).{0,40}(?:this|that|it|those|these)"
    r")\s*[?.!]*\s*$",
    re.I,
)


def _classify(query: str, history: list[dict] | None = None) -> list[dict]:
    """Return list of domain dicts to consult for this query.

    Classification priority:
    1. Conversational / trivially short → general
    2. Query itself has unambiguous domain signals → use those
    3. Query is ambiguous/follow-up → inherit domain from conversation history
    4. Pattern-match fallback → credit (default)
    """
    # ── 1. Short conversational input — no specialist agent needed ────────────
    if _CONVERSATIONAL.match(query) or len(query.split()) <= 3 and not any(
        pat.search(query)
        for pat in (
            re.compile(r"fraud|transact|credit|loan|sentiment|social|speech|call", re.I),
        )
    ):
        return [_GENERAL_DOMAIN]

    # ── 2. Classify from query text ───────────────────────────────────────────
    # Chart/visual follow-up: interrogating an already-rendered chart.
    if _CHART_FOLLOWUP.search(query) and _SENTIMENT_SIGNALS.search(query):
        return [next(d for d in _DOMAINS if d["key"] == "sentiment")]

    has_credit    = bool(_CREDIT_SIGNALS.search(query))
    has_sentiment = bool(_SENTIMENT_SIGNALS.search(query))
    has_speech    = bool(_SPEECH_SIGNALS.search(query))

    if has_speech:
        speech = next(d for d in _DOMAINS if d["key"] == "speech")
        if has_sentiment and not any(w in query.lower() for w in ("transcript", "call", "cx")):
            sentiment = next(d for d in _DOMAINS if d["key"] == "sentiment")
            return [speech, sentiment]
        return [speech]

    if has_credit and has_sentiment:
        credit    = next(d for d in _DOMAINS if d["key"] == "credit")
        sentiment = next(d for d in _DOMAINS if d["key"] == "sentiment")
        return [credit, sentiment]

    # If any non-default domain pattern matches clearly, use it directly.
    non_default_match = next(
        (d for d in _DOMAINS[:-1] if d["pattern"].search(query)), None
    )
    if non_default_match:
        return [non_default_match]

    # ── 3. Ambiguous query — inherit domain from conversation history ──────────
    # This handles follow-ups like "give me a detailed analysis of this call",
    # "why did that happen?", "show me more" — intent is clear from context,
    # not from keywords in the current message.
    if history and (not has_credit):
        inherited = _infer_domain_from_history(history)
        if inherited:
            inherited_domain = next(
                (d for d in _DOMAINS if d["key"] == inherited), None
            )
            if inherited_domain:
                return [inherited_domain]

    # ── 4. Fallback: credit (default catch-all) ───────────────────────────────
    return [_DOMAINS[-1]]


# ── Conversational / general reply ────────────────────────────────────────────
_openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

_GENERAL_SYSTEM = """\
You are the NedCard Intelligence assistant — an internal AI platform for Nedbank analysts.
You can answer questions about credit applications, fraud transactions, social sentiment,
and call-centre CX data. For greetings, small talk, or meta questions, respond naturally
and briefly in one or two sentences without forcing the conversation toward any data domain.
Do NOT mention SQL, databases, or internal tooling unless asked."""


async def _conversational_reply(query: str, history: list[dict] | None = None) -> str:
    """Direct GPT call for greetings / meta questions — no SQL agent, no tools."""
    # Include prior history so follow-up conversational turns aren't context-blind
    history_msgs = [
        {"role": m["role"], "content": m["content"]}
        for m in (history or [])
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    resp = await _openai_client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _GENERAL_SYSTEM},
            *history_msgs,
            {"role": "user",   "content": query},
        ],
        temperature=0.5,
        max_tokens=200,
    )
    return resp.choices[0].message.content or "Hello! How can I help you today?"


# ── Synthesis LLM call ─────────────────────────────────────────────────────────

_SYNTHESIS_SYSTEM = """You are a senior Nedbank analyst. You have received data from two
specialist AI agents and must write ONE unified response.

Tone rules — match the format to the question:
- Conversational follow-up or clarification? Respond conversationally in 2–4 short paragraphs.
  No headers. No "Executive Summary" banner. Just answer the question directly.
- Complex multi-part question asking for a strategic view? Use headers and bullet lists only
  where they genuinely help readability.
- Never default to a heavy executive-summary template for every answer.
- Integrate the numbers naturally — don't just list them side by side.
- End with a single punchy "So what?" sentence only when it adds value.

Keep it tight. Directness is more valuable than length."""


async def _synthesise(query: str, agent_results: list[dict]) -> str:
    """Use GPT to merge multiple specialist answers into a single coherent response."""
    parts = "\n\n".join(
        f"### {r['label']} data\n{r['answer']}"
        for r in agent_results
        if r.get("answer")
    )
    prompt = f"""The user asked: **{query}**

You have the following specialist data:

{parts}

Write a single, unified executive-level response that directly answers the user's question
using all of the data above. Integrate the numbers, don't just list them side by side."""

    resp = await _openai_client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SYNTHESIS_SYSTEM},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.3,
        max_tokens=900,
    )
    return resp.choices[0].message.content or ""


# ── Endpoint ───────────────────────────────────────────────────────────────────
@router.post("/query", response_model=AgentResponse, summary="Unified AI query — auto-routes across domains")
async def query_unified(request: AgentRequest) -> AgentResponse:
    """
    Single entry point for all queries in the production UI.
    Classifies intent, queries the right specialist agent(s) in parallel,
    and returns a single synthesised answer.
    """
    session_id = request.session_id or str(uuid.uuid4())
    start      = time.perf_counter()
    domains    = _classify(request.query, history=request.history)

    # ── Conversational shortcut — skip all specialist agents ───────────────────
    if len(domains) == 1 and domains[0]["key"] == "general":
        answer = await _conversational_reply(request.query, history=request.history)
        return AgentResponse(
            answer     = answer,
            latency_ms = round((time.perf_counter() - start) * 1000, 1),
            agent_label= None,   # no specialist — frontend hides the domain pill
        )

    # ── Fan-out: call each relevant agent in parallel ──────────────────────────
    tasks = [
        invoke_agent(
            graph     = d["graph"],
            query     = request.query,
            session_id= session_id,
            use_case  = d["use_case"],
            history   = request.history,
        )
        for d in domains
    ]
    raw_results: list[Any] = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect successful responses
    agent_results: list[dict] = []
    sql_query:     str | None = None
    table_data:    Any        = None
    agent_chart_data: dict | None = None   # from execute_*_sql_chart tool calls

    for domain, result in zip(domains, raw_results):
        if isinstance(result, Exception):
            continue
        agent_results.append({"label": domain["label"], "answer": result.get("answer", "")})
        if not sql_query and result.get("sql_query"):
            sql_query = result["sql_query"]
        if table_data is None and result.get("table_data"):
            table_data = result["table_data"]
        # First agent that produced chart_data via a chart tool wins
        if agent_chart_data is None and result.get("chart_data"):
            agent_chart_data = result["chart_data"]

    if not agent_results:
        return AgentResponse(
            answer="I was unable to retrieve data at this time. Please try again.",
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
        )

    # ── Synthesise if multiple agents contributed ──────────────────────────────
    if len(agent_results) > 1:
        final_answer = await _synthesise(request.query, agent_results)
    else:
        final_answer = agent_results[0]["answer"]

    # ── Bundle chart data ──────────────────────────────────────────────────────
    # Only attach chart_data when an agent explicitly called a chart tool.
    # Never attach a pre-canned chart — charts are only rendered upon explicit request.
    chart_data: dict | None = agent_chart_data

    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    # Label shown in the frontend domain pill
    agent_label = " + ".join(d["label"] for d in domains if d.get("label"))

    return AgentResponse(
        answer      = final_answer,
        sql_query   = sql_query,
        table_data  = table_data,
        latency_ms  = latency_ms,
        chart_data  = chart_data,
        agent_label = agent_label or None,
    )
