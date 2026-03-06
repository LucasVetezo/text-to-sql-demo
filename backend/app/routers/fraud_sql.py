"""Fraud SQL router — /api/fraud endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.agents.fraud_sql_agent import fraud_sql_graph
from app.routers._agent_utils import invoke_agent
from app.schemas.responses import AgentRequest, AgentResponse

router = APIRouter(prefix="/api/fraud", tags=["Fraud Cases"])


@router.post("/query", response_model=AgentResponse, summary="Query fraud cases with NL")
async def query_fraud(request: AgentRequest) -> AgentResponse:
    """
    Submit a natural language question about fraud investigation cases.
    The agent generates SQL, executes it against `fraud_cases`,
    and returns insights with the generated SQL shown.

    **Example queries:**
    - "What are the most common types of fraud we've seen?"
    - "Show me high-risk transactions (score > 0.8) that are still under investigation"
    - "Which merchant categories have the most confirmed fraud?"
    - "Summarise the assessor commentary for account takeover cases"
    """
    try:
        result = await invoke_agent(
            graph=fraud_sql_graph,
            query=request.query,
            session_id=request.session_id,
            use_case="fraud-sql",
        )
        return AgentResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {exc}",
        )


@router.get("/examples", summary="Get example queries for the fraud use case")
async def get_fraud_examples() -> dict:
    return {
        "examples": [
            "What are the top fraud types by transaction volume?",
            "Show me all confirmed fraud cases in the last 30 days",
            "Which channel (online/ATM/POS) has the highest fraud rate?",
            "Find transactions over R50,000 with risk scores above 0.9",
            "What locations have the most suspected fraud activity?",
            "Summarise assessor commentary themes for card-not-present fraud",
            "Compare fraud amounts across merchant categories",
            "How many cases are still open vs closed by fraud type?",
        ]
    }
