# /api/plans routes
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
import os
import yaml
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel

from autogen_agentchat.messages import TextMessage, MultiModalMessage
from autogen_core.models import ChatCompletionClient

from ....learning import learn_plan_from_messages
from ....learning.memory_provider import MemoryControllerProvider

from ...datamodel import Plan
from ..deps import get_db
from .sessions import list_session_runs

router = APIRouter()


@router.get("/")
async def list_plans(user_id: str, db=Depends(get_db)) -> Dict:
    """Get all plans for a user"""
    response = db.get(Plan, filters={"user_id": user_id})
    return {"status": True, "data": response.data}


@router.get("/{plan_id}")
async def get_plan(plan_id: int, user_id: str, db=Depends(get_db)) -> Dict:
    """Get a specific plan"""
    response = db.get(Plan, filters={"id": plan_id, "user_id": user_id})
    if not response.status or not response.data:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": True, "data": response.data[0]}


@router.post("/")
async def create_plan(plan: Plan, db=Depends(get_db)) -> Dict:
    """Create a new plan"""
    if not plan.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    plan_response = db.upsert(plan)
    if not plan_response.status:
        raise HTTPException(status_code=400, detail=plan_response.message)

    return {"status": True, "data": plan_response.data}


@router.put("/{plan_id}")
async def update_plan(
    plan_id: int, user_id: str, plan: Plan, db=Depends(get_db)
) -> Dict:
    existing_plan = db.get(Plan, filters={"id": plan_id, "user_id": user_id})
    if not existing_plan.status or not existing_plan.data:
        raise HTTPException(status_code=404, detail="Plan not found")

    response = db.upsert(plan)
    if not response.status:
        raise HTTPException(status_code=400, detail=response.message)
    return {
        "status": True,
        "data": response.data,
        "message": "Plan updated successfully",
    }


@router.delete("/{plan_id}")
async def delete_plan(plan_id: int, user_id: str, db=Depends(get_db)) -> Dict:
    """Delete a specific plan"""
    response = db.delete(Plan, filters={"id": plan_id, "user_id": user_id})
    if not response.status:
        raise HTTPException(status_code=400, detail=response.message)
    return {"status": True, "data": response.data}


# Create a request model
class LearnPlanRequest(BaseModel):
    session_id: int
    user_id: str


@router.post("/learn_plan")
async def learn_plan(
    request: LearnPlanRequest,
    db=Depends(get_db),
):
    """Learn a plan from chat messages in a session"""
    session_id = request.session_id
    user_id = request.user_id

    if not session_id or not user_id:
        return {
            "status": False,
            "message": "Missing required parameters",
            "error": "MISSING_PARAMETERS",
        }

    try:
        # Read the config file, if present
        config: dict[str, Any] = {}
        config_file = os.environ.get("_CONFIG")
        if config_file:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

        # Load the client from the config
        plan_learning_config = config.get("plan_learning_client", None)
        if not plan_learning_config:
            # Fallback to orchestrator_client if plan_learning_client is not set
            plan_learning_config = config.get("orchestrator_client", None)

        if plan_learning_config:
            model_client = ChatCompletionClient.load_component(plan_learning_config)
        else:
            # If nothing was provided, use a safe default
            gpt4o_config = {
                "provider": "OpenAIChatCompletionClient",
                "config": {
                    "model": "gpt-4o-2024-08-06",
                    "api_key": os.environ.get("OPENAI_API_KEY"),
                },
                "max_retries": 5,
            }
            if os.environ.get("OPENAI_BASE_URL"):
                gpt4o_config["config"]["base_url"] = os.environ.get("OPENAI_BASE_URL")
            model_client = ChatCompletionClient.load_component(gpt4o_config)

        # 1. Retrieve messages from database
        runs_result = await list_session_runs(
            session_id=session_id, user_id=user_id, db=db
        )

        runs = runs_result.get("data", {}).get("runs", [])
        messages = []
        if len(runs) > 0:
            messages = runs[0].get("messages", [])  # only 1 run per session

        if not messages:
            return {
                "status": False,
                "message": "No messages found in this session",
                "error": "NO_MESSAGES",
            }

        # 2. Format messages for learn_plan
        messages_for_learning = []
        for msg in messages:
            # Skip messages from non-agent or orchestrator sources
            if msg.config.get("source", "") not in [
                "user",
                "user_proxy",
                "web_surfer",
                "file_surfer",
                "orchestrator",
                "Orchestrator",
                "coder_agent-llm",
                "coder_agent-executor",
            ]:
                continue
            if msg.config.get("type") == "TextMessage":
                messages_for_learning.append(
                    TextMessage(
                        source=msg.config.get("source", ""),
                        content=msg.config.get("content", ""),
                    )
                )
            elif msg.config.get("type") == "MultiModalMessage":
                messages_for_learning.append(
                    MultiModalMessage(
                        source=msg.config.get("source", ""),
                        content=msg.config.get("content", []),
                    )
                )

        # 3. Call learn_plan

        plan = await learn_plan_from_messages(model_client, messages_for_learning)

        # 4. Convert PlanStep objects to dictionaries
        steps_as_dicts = []
        for step in plan.steps:
            if isinstance(step, dict):
                steps_as_dicts.append(step)
            else:
                try:
                    steps_as_dicts.append(step.model_dump())
                except AttributeError:
                    step_dict = {
                        "title": getattr(step, "title", ""),
                        "details": getattr(step, "details", ""),
                        "agent_name": getattr(step, "agent_name", ""),
                    }
                    steps_as_dicts.append(step_dict)

        # Create database plan with converted steps
        db_plan = Plan(
            task=plan.task, steps=steps_as_dicts, user_id=user_id, session_id=session_id
        )
        response = db.upsert(db_plan)

        # Add the plan to memory
        try:
            memory_provider = MemoryControllerProvider(
                internal_workspace_root=Path(os.environ.get("INTERNAL_WORKSPACE_ROOT")),
                external_workspace_root=Path(os.environ.get("EXTERNAL_WORKSPACE_ROOT")),
                inside_docker=os.environ.get("INSIDE_DOCKER", "false").lower()
                == "true",
            )
            memory_controller = memory_provider.get_memory_controller(
                user_id, model_client
            )

            logger.info("Adding plan to memory...")
            await memory_controller.add_memo(
                task=plan.task, insight=plan.model_dump_json(), index_on_both=False
            )
            logger.info("Plan successfully added to memory")

        except Exception as e:
            logger.error(f"Error adding plan to memory: {e}")

        return {
            "status": True,
            "data": {
                "planId": response.data.get("id") if response.data else None,
            },
            "message": "Plan created successfully",
        }

    except Exception:
        import traceback

        logger.error(traceback.format_exc())

        return {
            "status": False,
            "message": "Failed to create plan",
            "error": "INTERNAL_ERROR",
        }
