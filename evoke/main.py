import datetime
import asyncio
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from clients import s3_client, os_client, get_producer
from workers import evoke_workers_loop

app = FastAPI()

# --- Pydantic Models for JSON Payloads ---
class InsightPayload(BaseModel):
    learner_id: str
    mission_id: str
    category: str
    source: str
    text: str

# -------------------------------------------------------------------------
# 1. EVENT PRODUCERS (Commands)
# -------------------------------------------------------------------------

@app.post("/api/submit-evidence")
async def submit_evidence(
    learner_id: str = Form(...),
    mission_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Single Learner Submission"""
    try:
        producer = get_producer()
        file_bytes = await file.read()
        object_key = f"evoke-evidence/{mission_id}/{learner_id}_{file.filename}"
        
        s3_client.put_object(Bucket="default-bucket", Key=object_key, Body=file_bytes, ContentType=file.content_type)
        
        event = {
            "event_type": "EvidenceSubmitted",
            "version": "1.0.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": {
                "learner_id": learner_id,
                "mission_id": mission_id,
                "object_key": object_key,
                "filename": file.filename
            }
        }
        
        producer.send('evoke-events', value=event)
        producer.flush()
        _bootstrap_timeline(learner_id, mission_id, file.filename)
        
        return {"status": "EvidenceSubmitted event broadcasted!", "event": event}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/teams/submit-evidence")
async def submit_team_evidence(
    learner_ids: str = Form(...), # Comma separated list of IDs
    mission_id: str = Form(...),
    file: UploadFile = File(...)
):
    """Team Submission: One file, multiple learners updated."""
    try:
        producer = get_producer()
        file_bytes = await file.read()
        team_hash = hash(learner_ids)
        object_key = f"evoke-evidence/{mission_id}/team_{team_hash}_{file.filename}"
        
        s3_client.put_object(Bucket="default-bucket", Key=object_key, Body=file_bytes, ContentType=file.content_type)
        
        team_members = [lid.strip() for lid in learner_ids.split(",")]
        
        event = {
            "event_type": "TeamEvidenceSubmitted",
            "version": "1.0.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": {
                "team_members": team_members,
                "mission_id": mission_id,
                "object_key": object_key,
                "filename": file.filename
            }
        }
        
        producer.send('evoke-events', value=event)
        producer.flush()
        
        # Bootstrap a timeline for every member of the team
        for member_id in team_members:
            _bootstrap_timeline(member_id, mission_id, file.filename)
            
        return {"status": "TeamEvidenceSubmitted event broadcasted!", "event": event}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/insights")
def publish_human_insight(payload: InsightPayload):
    """Human Reviewer (Teacher/Peer) publishes an insight to the stream."""
    try:
        producer = get_producer()
        event = {
            "event_type": "InsightPublished",
            "version": "1.0.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "data": {
                "learner_id": payload.learner_id,
                "mission_id": payload.mission_id,
                "insight": {
                    "category": payload.category,
                    "source": payload.source,
                    "text": payload.text
                }
            }
        }
        producer.send('evoke-events', value=event)
        producer.flush()
        return {"status": "InsightPublished event broadcasted!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------------------------------
# 2. READ MODELS (Queries)
# -------------------------------------------------------------------------

@app.get("/api/timeline/{learner_id}/{mission_id}")
def get_timeline(learner_id: str, mission_id: str):
    """Learner Dashboard: Single mission progression."""
    try:
        projection_id = f"{learner_id}_{mission_id}"
        res = os_client.get(index="learner-timeline", id=projection_id)
        return res['_source']
    except Exception:
        return {"status": "No active platform workflows found.", "timeline": []}


@app.get("/api/instructor/missions/{mission_id}")
def get_instructor_dashboard(mission_id: str):
    """Instructor Dashboard: All learner timelines for a specific mission."""
    try:
        query = {
            "query": { "match": { "mission_id": mission_id } },
            "size": 100 # Fetch up to 100 students for the view
        }
        res = os_client.search(index="learner-timeline", body=query)
        return [hit['_source'] for hit in res['hits']['hits']]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/{learner_id}")
def get_learner_portfolio(learner_id: str):
    """Portfolio: Aggregate of all a learner's missions and insights."""
    try:
        query = {
            "query": { "match": { "learner_id": learner_id } },
            "sort": [ { "mission_id": "asc" } ]
        }
        res = os_client.search(index="learner-timeline", body=query)
        # In a real app, a dedicated portfolio worker would build a separate 
        # index, but we can dynamically aggregate the timeline index here.
        missions = [hit['_source'] for hit in res['hits']['hits']]
        return {"learner_id": learner_id, "total_missions": len(missions), "missions": missions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------------------------------
# 3. UTILITIES & STARTUP
# -------------------------------------------------------------------------

def _bootstrap_timeline(learner_id: str, mission_id: str, filename: str):
    """Helper to synchronously seed the OpenSearch read model."""
    projection_id = f"{learner_id}_{mission_id}"
    now_str = datetime.datetime.now().isoformat()
    os_client.index(
        index="learner-timeline",
        id=projection_id,
        body={
            "learner_id": learner_id,
            "mission_id": mission_id,
            "status": "In Progress",
            "insights": [],
            "notifications": [],
            "timeline": [
                {
                    "id": "submitted",
                    "title": "Evidence Submitted",
                    "status": "completed",
                    "timestamp": now_str,
                    "content": f"Uploaded document: {filename}"
                },
                {
                    "id": "processing",
                    "title": "System Processing",
                    "status": "active",
                    "timestamp": now_str,
                    "content": "Extracting text and routing to AI Worker pipeline..."
                },
                {
                    "id": "ai_analysis",
                    "title": "AI Coach Analysis",
                    "status": "pending",
                    "timestamp": None,
                    "content": None
                },
                {
                    "id": "teacher_review",
                    "title": "Instructor / Peer Review",
                    "status": "pending",
                    "timestamp": None,
                    "content": "Awaiting human insights."
                }
            ]
        },
        refresh=True
    )

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(evoke_workers_loop())

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def serve_spa():
    response = FileResponse("static/index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response