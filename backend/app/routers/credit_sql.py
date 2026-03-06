"""Credit SQL router — /api/credit endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.agents.credit_sql_agent import credit_sql_graph
from app.routers._agent_utils import invoke_agent
from app.schemas.responses import AgentRequest, AgentResponse

router = APIRouter(prefix="/api/credit", tags=["Credit Applications"])


@router.post("/query", response_model=AgentResponse, summary="Query credit applications with NL")
async def query_credit(request: AgentRequest) -> AgentResponse:
    """
    Submit a natural language question about credit applications.
    The agent generates SQL, executes it against `credit_applications`,
    and returns a plain-English answer with the SQL used.

    **Example queries:**
    - "What are the top 5 decline reasons for credit applications in Gauteng?"
    - "Show me applicants with credit scores below 580 who were approved"
    - "What is the average loan amount requested by employment status?"
    - "Summarise the assessor comments for rejected applications this year"
    """
    try:
        result = await invoke_agent(
            graph=credit_sql_graph,
            query=request.query,
            session_id=request.session_id,
            use_case="credit-sql",
        )
        return AgentResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {exc}",
        )


@router.get("/examples", summary="Get example queries for the credit use case")
async def get_credit_examples() -> dict:
    """Return example natural language queries for the UI."""
    return {
        "examples": [
            "What are the top 5 most common decline reasons?",
            "Show me the average credit score by employment status",
            "Which province has the highest rejection rate?",
            "How many applications were approved vs rejected this year?",
            "What is the average annual income of approved applicants vs rejected?",
            "List the last 10 rejected applications in Johannesburg with assessor comments",
            "Show me applicants with a debt-to-income ratio above 40%",
            "What percentage of credit applications are from self-employed individuals?",
        ]
    }
