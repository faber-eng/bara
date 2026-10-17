from fastapi import APIRouter, Depends, HTTPException, Request

from casework.deadline import DeadlineHandler, OverduePublishFailed
from push_auth import require_push_caller

router = APIRouter(prefix="/api/internal")


@router.post("/deadline/{task_id}", dependencies=[Depends(require_push_caller)])
def task_deadline(task_id: str, request: Request) -> dict[str, str]:
    deadlines: DeadlineHandler = request.app.state.deadlines
    try:
        outcome = deadlines.handle_deadline(task_id)
    except OverduePublishFailed as error:
        raise HTTPException(status_code=503, detail="publish_failed") from error
    return {"outcome": outcome}
