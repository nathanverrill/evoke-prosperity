"""
Brightspace LMS Simulator - Based on D2L Brightspace API (July 2026)

This app simulates the key Brightspace API endpoints needed to test EVOKE Prosperity
integration before connecting to a real Brightspace instance.
"""

import os
from fastapi import FastAPI, Form, HTTPException, Header, Query
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
from brightspace_api import BrightspaceSimulator

app = FastAPI(title="Brightspace LMS Simulator")
simulator = BrightspaceSimulator()

EVOKE_API_URL = os.getenv("EVOKE_API_URL", "http://web:8000")

# ========== HEALTH CHECK ==========

@app.get("/health")
async def health():
    return {"status": "ok", "service": "brightspace-sim"}

# ========== OAUTH 2.0 ENDPOINTS ==========

@app.post("/oauth2/token")
async def oauth2_token(
    grant_type: str = Form(...),
    username: str = Form(None),
    password: str = Form(None),
    refresh_token: str = Form(None)
):
    """
    OAuth 2.0 Token Endpoint
    Simplified version of: POST /oauth2/token
    """
    if grant_type == "password":
        # Resource Owner Password Credentials
        access_token, refresh, expires_in = simulator.login(username, password)
        if not access_token:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {
            "access_token": access_token,
            "refresh_token": refresh,
            "expires_in": expires_in,
            "token_type": "Bearer"
        }

    elif grant_type == "refresh_token":
        # Refresh token flow
        access_token, expires_in = simulator.refresh_access_token(refresh_token)
        if not access_token:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        return {
            "access_token": access_token,
            "expires_in": expires_in,
            "token_type": "Bearer"
        }

    else:
        raise HTTPException(status_code=400, detail="Unsupported grant type")

# ========== IDENTITY ENDPOINTS ==========

@app.get("/d2l/api/lp/1.96/users/whoami")
async def whoami(authorization: str = Header(None)):
    """
    GET /d2l/api/lp/1.96/users/whoami
    Returns current user info
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]
    user = simulator.whoami(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "UserId": user["UserId"],
        "Username": user["Username"],
        "FirstName": user["FirstName"],
        "LastName": user["LastName"],
        "Email": user["Email"],
        "IsActive": user["IsActive"]
    }

# ========== AWARD SERVICE (BAS) ENDPOINTS ==========

@app.get("/d2l/api/bas/1.62/issued/users/{user_id}")
async def get_issued_awards(user_id: str, authorization: str = Header(None)):
    """
    GET /d2l/api/bas/1.62/issued/users/{user_id}/
    Returns all badges earned by user
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]
    awards = simulator.get_issued_awards(token, user_id)
    if awards is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {"Awards": awards}

@app.post("/d2l/api/bas/1.62/orgunits/1/issued")
async def issue_award(
    award_id: str = Form(...),
    user_id: str = Form(...),
    criteria: str = Form(""),
    evidence: str = Form(""),
    authorization: str = Header(None)
):
    """
    POST /d2l/api/bas/1.62/orgunits/{orgUnitId}/issued/
    Issues a badge to a user
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]
    success = simulator.issue_award(token, user_id, award_id, criteria, evidence)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to issue award")

    return {"success": True, "AwardId": award_id, "UserId": user_id}

# ========== GROUP MANAGEMENT ENDPOINTS ==========

@app.post("/d2l/api/lp/1.96/1/groupcategories")
async def create_group_category(
    name: str = Form(...),
    description: str = Form(""),
    authorization: str = Header(None)
):
    """
    POST /d2l/api/lp/1.96/{orgUnitId}/groupcategories/
    Creates a group category
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]
    category_id = simulator.create_group_category(token, name, description)

    if not category_id:
        raise HTTPException(status_code=400, detail="Failed to create group category")

    return {"GroupCategoryId": category_id, "Name": name}

@app.post("/d2l/api/lp/1.96/1/groupcategories/{category_id}/groups")
async def create_group(
    category_id: str,
    name: str = Form(...),
    code: str = Form(""),
    description: str = Form(""),
    authorization: str = Header(None)
):
    """
    POST /d2l/api/lp/1.96/{orgUnitId}/groupcategories/{categoryId}/groups/
    Creates a group
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]
    group_id = simulator.create_group(token, category_id, name, code, description)

    if not group_id:
        raise HTTPException(status_code=400, detail="Failed to create group")

    return {"GroupId": group_id, "Name": name, "GroupCategoryId": category_id}

@app.post("/d2l/api/lp/1.96/1/groupcategories/{category_id}/groups/{group_id}/enrollments")
async def enroll_user_in_group(
    category_id: str,
    group_id: str,
    user_id: str = Form(...),
    authorization: str = Header(None)
):
    """
    POST /d2l/api/lp/1.96/{orgUnitId}/groupcategories/{categoryId}/groups/{groupId}/enrollments/
    Adds a user to a group
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]
    success = simulator.enroll_user_in_group(token, group_id, user_id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to enroll user in group")

    return {"success": True, "UserId": user_id, "GroupId": group_id}

# ========== ASSIGNMENT CATALOG ==========

@app.get("/d2l/api/lp/1.96/dropbox/assignments")
async def list_assignments():
    """
    GET /d2l/api/lp/1.96/dropbox/assignments
    Lists all assignments (missions) with their EVOKE metadata in
    CustomFields. Not authenticated, matching the read-only, low-stakes
    nature of a catalog listing in this simulator -- what EVOKE's startup
    sync calls to build its missions table cache. A real Brightspace
    integration would use a real assignment/content-object listing API with
    the service-account OAuth flow; this sim endpoint stands in for that.
    """
    return {"Assignments": simulator.get_all_assignments()}

# ========== DROPBOX (ASSIGNMENT) ENDPOINTS ==========

@app.post("/d2l/api/lp/1.96/dropbox/{assignment_id}/submissions")
async def submit_to_dropbox(
    assignment_id: str,
    user_id: str = Form(...),
    file_name: str = Form(...),
    file_content: str = Form(...),
    authorization: str = Header(None)
):
    """
    POST /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions
    Submits evidence/file to a dropbox
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]
    submission_id = simulator.submit_to_dropbox(
        token, assignment_id, user_id, file_name, file_content.encode()
    )

    if not submission_id:
        raise HTTPException(status_code=400, detail="Failed to submit to dropbox")

    return {
        "SubmissionId": submission_id,
        "AssignmentId": assignment_id,
        "UserId": user_id,
        "FileName": file_name
    }

@app.get("/d2l/api/lp/1.96/dropbox/{assignment_id}/submissions")
async def get_dropbox_submissions(assignment_id: str, authorization: str = Header(None)):
    """
    GET /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions
    Gets all submissions for an assignment
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]
    submissions = simulator.get_submissions_for_assignment(token, assignment_id)

    if submissions is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {"Submissions": submissions}

# ========== TEACHER GRADING ENDPOINTS ==========

@app.put("/d2l/api/lp/1.96/dropbox/{assignment_id}/submissions/{submission_id}/grade")
async def grade_submission(
    assignment_id: str,
    submission_id: str,
    grade: int = Form(...),
    feedback: str = Form(""),
    authorization: str = Header(None)
):
    """
    PUT /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions/{submissionId}/grade
    Teacher grades a submission. On success, calls back EVOKE's grading
    webhook with Brightspace-native identifiers only (brightspace user id,
    assignment ref, submission id) -- a real Brightspace webhook would never
    know EVOKE's internal UUIDs, so EVOKE resolves them server-side. This
    call was previously missing entirely: nothing ever told EVOKE a teacher
    had graded something.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ")[1]
    graded_submission = simulator.grade_submission(token, assignment_id, submission_id, grade, feedback)

    if not graded_submission:
        raise HTTPException(status_code=400, detail="Failed to grade submission")

    rating = "legendary" if grade >= 95 else "epic"
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{EVOKE_API_URL}/api/webhooks/brightspace/review",
                params={
                    "submission_id": submission_id,
                    "brightspace_user_id": graded_submission["UserId"],
                    "assignment_id": assignment_id,
                    "rating": rating,
                },
                timeout=10,
            )
    except Exception as e:
        # Non-blocking: the grade is recorded in the sim either way; EVOKE
        # missing the webhook is a delivery problem, not a grading failure.
        print(f"[brightspace-sim] Grading webhook to EVOKE failed (non-blocking): {e}")

    return {"success": True, "Grade": grade, "Rating": rating}

# ========== ADMIN/TESTING ENDPOINTS ==========

@app.get("/api/admin/users")
async def admin_get_users():
    """Get all users (testing only)"""
    return {"Users": simulator.get_all_users()}

@app.get("/api/admin/groups")
async def admin_get_groups():
    """Get all groups (testing only)"""
    return {"Groups": simulator.get_all_groups()}

@app.post("/api/admin/reset")
async def admin_reset():
    """Reset simulator to initial state (testing only)"""
    simulator.reset()
    return {"status": "reset"}

# ========== TEACHER REVIEW UI (Simple Demo) ==========

@app.get("/teacher-review")
async def teacher_review_page():
    """Simple HTML form for testing teacher grading flow"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Brightspace Simulator - Teacher Review</title>
        <style>
            body { font-family: Arial; margin: 20px; }
            .submission { background: #f9f9f9; padding: 10px; margin: 10px 0; border: 1px solid #ddd; }
            button { padding: 8px 15px; margin: 5px; cursor: pointer; }
            .epic { background: #4CAF50; color: white; }
            .legendary { background: #FFD700; }
            input, textarea { padding: 8px; margin: 5px; width: 300px; }
        </style>
    </head>
    <body>
        <h1>Brightspace Simulator - Teacher Grading</h1>
        <p>Test the teacher review workflow here.</p>

        <h2>Mock Submissions (for testing)</h2>
        <div id="submissions"></div>

        <h2>Grade a Submission</h2>
        <form id="gradeForm">
            <div>
                <label>Assignment ID:</label><br>
                <input type="text" id="assignmentId" value="m1"><br>

                <label>Submission ID:</label><br>
                <input type="text" id="submissionId" placeholder="submission-uuid"><br>

                <label>Grade (1-100):</label><br>
                <input type="number" id="grade" min="1" max="100" value="85"><br>

                <label>Feedback:</label><br>
                <textarea id="feedback" rows="4" placeholder="Teacher feedback..."></textarea><br>

                <button type="button" class="epic" onclick="gradeAsEpic()">Grade: Epic (85-90)</button>
                <button type="button" class="legendary" onclick="gradeAsLegendary()">Grade: Legendary (95+)</button>
            </div>
        </form>

        <h2>Test Data</h2>
        <p><strong>Test Users:</strong></p>
        <ul>
            <li>learner@evoke.local (user_id: 6001)</li>
            <li>teacher@evoke.local (user_id: 6002)</li>
        </ul>
        <p><strong>Test Assignments:</strong></p>
        <ul>
            <li>m1 (Follow the Flow)</li>
            <li>m2 (Money Moves)</li>
            <li>m3 (Building Blocks)</li>
        </ul>

        <script>
            async function gradeAsEpic() {
                await submitGrade(88);
            }

            async function gradeAsLegendary() {
                await submitGrade(98);
            }

            async function submitGrade(gradeValue) {
                const assignmentId = document.getElementById('assignmentId').value;
                const submissionId = document.getElementById('submissionId').value;
                const feedback = document.getElementById('feedback').value;

                if (!submissionId) {
                    alert('Please enter a submission ID');
                    return;
                }

                try {
                    const response = await fetch(
                        `/d2l/api/lp/1.96/dropbox/${assignmentId}/submissions/${submissionId}/grade`,
                        {
                            method: 'PUT',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'Authorization': 'Bearer test-token'  // For testing
                            },
                            body: `grade=${gradeValue}&feedback=${encodeURIComponent(feedback)}`
                        }
                    );

                    const result = await response.json();
                    if (response.ok) {
                        alert(`Graded successfully: ${gradeValue}`);
                    } else {
                        alert(`Error: ${result.detail}`);
                    }
                } catch (e) {
                    alert(`Error: ${e.message}`);
                }
            }

            // Load mock submissions
            async function loadSubmissions() {
                const assignments = ['m1', 'm2', 'm3'];
                let html = '';

                for (const assignmentId of assignments) {
                    // Mock some submissions
                    html += `
                        <div class="submission">
                            <h3>Assignment: ${assignmentId}</h3>
                            <p><strong>User:</strong> 6001 (Demo Learner)</p>
                            <p><strong>File:</strong> mission-response.pdf</p>
                            <p><strong>Submitted:</strong> 2024-01-15 10:30 AM</p>
                            <button onclick="gradeSubission('${assignmentId}', 'sub-123-456')">Review & Grade</button>
                        </div>
                    `;
                }

                document.getElementById('submissions').innerHTML = html;
            }

            function gradeSubission(assignmentId, submissionId) {
                document.getElementById('assignmentId').value = assignmentId;
                document.getElementById('submissionId').value = submissionId;
                document.getElementById('feedback').value = '';
            }

            loadSubmissions();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
