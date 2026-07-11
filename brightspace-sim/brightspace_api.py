"""
Brightspace LMS Simulator - Based on D2L Brightspace API (July 2026)

This simulator implements the key Brightspace API endpoints needed for EVOKE Prosperity:
- OAuth 2.0 authentication (login/token endpoints)
- User/Identity endpoints (whoami, get user info)
- Award Service (BAS) for badge management
- Group management (create groups, add users)
- Dropbox submission endpoints
"""

from datetime import datetime, timedelta
import json
import uuid
from typing import Dict, List, Optional, Tuple


class BrightspaceSimulator:
    """In-memory Brightspace LMS simulator for development/testing"""

    def __init__(self):
        # Org unit (course) for Evoke Prosperity
        self.org_unit_id = "1"
        self.org_unit_name = "Evoke Prosperity"

        # Users: dict of user_id -> user_data
        self.users: Dict[str, dict] = {
            "6001": {
                "UserId": 6001,
                "Username": "learner@evoke.local",
                "FirstName": "Demo",
                "LastName": "Learner",
                "Email": "learner@evoke.local",
                "IsActive": True,
                "Role": "learner"
            },
            "6002": {
                "UserId": 6002,
                "Username": "teacher@evoke.local",
                "FirstName": "Demo",
                "LastName": "Teacher",
                "Email": "teacher@evoke.local",
                "IsActive": True,
                "Role": "instructor"
            }
        }

        # Refresh tokens: token -> user_id
        self.refresh_tokens: Dict[str, str] = {}

        # Access tokens: token -> (user_id, expires_at)
        self.access_tokens: Dict[str, Tuple[str, float]] = {}

        # Awards (badges) defined in this org
        self.awards: Dict[str, dict] = {
            "1001": {"AwardId": 1001, "Name": "Common Tier", "Description": "Basic achievement"},
            "1002": {"AwardId": 1002, "Name": "Epic Tier", "Description": "Intermediate achievement"},
            "1003": {"AwardId": 1003, "Name": "Legendary Tier", "Description": "Master achievement"},
        }

        # Issued awards: dict of user_id -> list of award_ids
        self.issued_awards: Dict[str, List[dict]] = {}

        # Group categories: dict of category_id -> category_data
        self.group_categories: Dict[str, dict] = {}

        # Groups: dict of group_id -> group_data
        self.groups: Dict[str, dict] = {}

        # Group enrollments: dict of group_id -> list of user_ids
        self.group_enrollments: Dict[str, List[str]] = {}

        # Dropbox submissions: dict of assignment_id -> list of submission_data
        self.dropbox_submissions: Dict[str, List[dict]] = {}

        # Assignments (dropboxes): dict of assignment_id -> assignment_data
        self.assignments: Dict[str, dict] = {
            "m1": {"AssignmentId": "m1", "Name": "Follow the Flow", "OrgUnitId": "1"},
            "m2": {"AssignmentId": "m2", "Name": "Money Moves", "OrgUnitId": "1"},
            "m3": {"AssignmentId": "m3", "Name": "Building Blocks", "OrgUnitId": "1"},
        }

    # ========== OAUTH 2.0 ENDPOINTS ==========

    def login(self, username: str, password: str) -> Tuple[str, str, int]:
        """
        OAuth 2.0 Authorization Code Grant - simplified for dev

        Real flow: /d2l/auth/oauth2/authorize + /d2l/auth/oauth2/token
        Sim flow: Direct token grant

        Returns: (access_token, refresh_token, expires_in_seconds)
        """
        # Find user by username
        user = None
        for uid, u in self.users.items():
            if u["Username"] == username:
                user = u
                break

        if not user:
            return None, None, None

        # Generate tokens
        access_token = str(uuid.uuid4())
        refresh_token = str(uuid.uuid4())
        expires_in = 3600  # 1 hour

        # Store tokens
        self.access_tokens[access_token] = (str(user["UserId"]), datetime.now().timestamp() + expires_in)
        self.refresh_tokens[refresh_token] = str(user["UserId"])

        return access_token, refresh_token, expires_in

    def refresh_access_token(self, refresh_token: str) -> Tuple[str, int]:
        """Refresh an expired access token"""
        if refresh_token not in self.refresh_tokens:
            return None, None

        user_id = self.refresh_tokens[refresh_token]
        access_token = str(uuid.uuid4())
        expires_in = 3600

        self.access_tokens[access_token] = (user_id, datetime.now().timestamp() + expires_in)
        return access_token, expires_in

    def _verify_token(self, access_token: str) -> Optional[str]:
        """Verify access token and return user_id, or None if invalid"""
        if access_token not in self.access_tokens:
            return None

        user_id, expires_at = self.access_tokens[access_token]
        if datetime.now().timestamp() > expires_at:
            del self.access_tokens[access_token]
            return None

        return user_id

    # ========== IDENTITY / USER ENDPOINTS ==========

    def whoami(self, access_token: str) -> Optional[dict]:
        """
        GET /d2l/api/lp/1.96/users/whoami
        Returns the current user's ID and details
        """
        user_id = self._verify_token(access_token)
        if not user_id:
            return None

        return self.users.get(user_id)

    def get_user(self, access_token: str, user_id: str) -> Optional[dict]:
        """
        GET /d2l/api/lp/1.96/users/{user_id}
        Returns user details
        """
        if not self._verify_token(access_token):
            return None

        return self.users.get(user_id)

    # ========== AWARD SERVICE (BAS) ENDPOINTS ==========

    def get_issued_awards(self, access_token: str, user_id: str) -> Optional[List[dict]]:
        """
        GET /d2l/api/bas/1.62/issued/users/{user_id}/
        Returns all badges earned by this user
        """
        if not self._verify_token(access_token):
            return None

        awarded = []
        if user_id in self.issued_awards:
            for award_data in self.issued_awards[user_id]:
                awarded.append({
                    "AwardId": award_data["AwardId"],
                    "AwardName": award_data["AwardName"],
                    "IssuedDate": award_data["IssuedDate"],
                    "Evidence": award_data.get("Evidence", ""),
                    "Criteria": award_data.get("Criteria", "")
                })

        return awarded

    def issue_award(self, access_token: str, user_id: str, award_id: str,
                   criteria: str = "", evidence: str = "") -> bool:
        """
        POST /d2l/api/bas/1.62/orgunits/{orgUnitId}/issued/
        Issues a badge to a user

        Payload:
        {
            "AwardId": 1002,
            "IssuedToUserId": 6001,
            "Criteria": "Completed Mission 1",
            "Evidence": "Submission ID: xyz"
        }
        """
        if not self._verify_token(access_token):
            return False

        if award_id not in self.awards:
            return False

        # Check if already issued (no duplicates)
        if user_id in self.issued_awards:
            for issued in self.issued_awards[user_id]:
                if issued["AwardId"] == award_id:
                    return False  # Already issued

        # Issue the award
        if user_id not in self.issued_awards:
            self.issued_awards[user_id] = []

        self.issued_awards[user_id].append({
            "AwardId": award_id,
            "AwardName": self.awards[award_id]["Name"],
            "IssuedDate": datetime.now().isoformat(),
            "Criteria": criteria,
            "Evidence": evidence
        })

        return True

    # ========== GROUP MANAGEMENT ENDPOINTS ==========

    def create_group_category(self, access_token: str, name: str,
                            description: str = "") -> Optional[str]:
        """
        POST /d2l/api/lp/1.96/{orgUnitId}/groupcategories/
        Creates a group category (e.g., "Evoke Prosperity Teams")

        Payload:
        {
            "Name": "Evoke Teams",
            "Description": "4-person venture teams",
            "EnrollmentStyle": 1  # Manual enrollment
        }
        """
        if not self._verify_token(access_token):
            return None

        category_id = str(uuid.uuid4())
        self.group_categories[category_id] = {
            "GroupCategoryId": category_id,
            "Name": name,
            "Description": description,
            "OrgUnitId": self.org_unit_id,
            "CreatedDate": datetime.now().isoformat()
        }

        return category_id

    def create_group(self, access_token: str, category_id: str,
                    name: str, code: str = "", description: str = "") -> Optional[str]:
        """
        POST /d2l/api/lp/1.96/{orgUnitId}/groupcategories/{groupCategoryId}/groups/
        Creates a group (e.g., "Team Alpha")

        Payload:
        {
            "Name": "Team Alpha",
            "Code": "TEAM_A",
            "Description": "Venture team"
        }
        """
        if not self._verify_token(access_token):
            return None

        if category_id not in self.group_categories:
            return None

        group_id = str(uuid.uuid4())
        self.groups[group_id] = {
            "GroupId": group_id,
            "GroupCategoryId": category_id,
            "Name": name,
            "Code": code,
            "Description": description,
            "OrgUnitId": self.org_unit_id,
            "CreatedDate": datetime.now().isoformat()
        }
        self.group_enrollments[group_id] = []

        return group_id

    def enroll_user_in_group(self, access_token: str, group_id: str,
                            user_id: str) -> bool:
        """
        POST /d2l/api/lp/1.96/{orgUnitId}/groupcategories/{groupCategoryId}/groups/{groupId}/enrollments/
        Adds a user to a group

        Payload:
        {
            "UserId": 6001
        }
        """
        if not self._verify_token(access_token):
            return False

        if group_id not in self.groups:
            return False

        if user_id not in self.group_enrollments[group_id]:
            self.group_enrollments[group_id].append(user_id)

        return True

    def get_group(self, access_token: str, group_id: str) -> Optional[dict]:
        """
        GET /d2l/api/lp/1.96/groups/{groupId}/
        Returns group details with members
        """
        if not self._verify_token(access_token):
            return None

        if group_id not in self.groups:
            return None

        group = self.groups[group_id].copy()
        group["Members"] = [
            self.users.get(uid, {"UserId": uid})
            for uid in self.group_enrollments.get(group_id, [])
        ]

        return group

    # ========== DROPBOX (ASSIGNMENT) ENDPOINTS ==========

    def submit_to_dropbox(self, access_token: str, assignment_id: str,
                         user_id: str, file_name: str, file_content: bytes) -> Optional[str]:
        """
        POST /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions
        Submits a file to an assignment dropbox

        Returns: submission_id
        """
        if not self._verify_token(access_token):
            return None

        if assignment_id not in self.assignments:
            return None

        submission_id = str(uuid.uuid4())
        submission = {
            "SubmissionId": submission_id,
            "UserId": user_id,
            "AssignmentId": assignment_id,
            "FileName": file_name,
            "FileSize": len(file_content),
            "SubmittedDate": datetime.now().isoformat(),
            "Status": "submitted"
        }

        if assignment_id not in self.dropbox_submissions:
            self.dropbox_submissions[assignment_id] = []

        self.dropbox_submissions[assignment_id].append(submission)

        return submission_id

    def get_submissions_for_assignment(self, access_token: str,
                                      assignment_id: str) -> Optional[List[dict]]:
        """
        GET /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions
        Returns all submissions for an assignment
        """
        if not self._verify_token(access_token):
            return None

        if assignment_id not in self.dropbox_submissions:
            return []

        return self.dropbox_submissions[assignment_id]

    # ========== GRADING ENDPOINTS ==========

    def grade_submission(self, access_token: str, assignment_id: str,
                        submission_id: str, grade: int,
                        feedback: str = "") -> bool:
        """
        PUT /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions/{submissionId}/grade
        Grades a submission (called by teacher)
        """
        if not self._verify_token(access_token):
            return False

        if assignment_id not in self.dropbox_submissions:
            return False

        for submission in self.dropbox_submissions[assignment_id]:
            if submission["SubmissionId"] == submission_id:
                submission["Status"] = "graded"
                submission["Grade"] = grade
                submission["Feedback"] = feedback
                submission["GradedDate"] = datetime.now().isoformat()
                return True

        return False

    # ========== UTILITY METHODS ==========

    def get_all_users(self) -> List[dict]:
        """Returns all users (for admin/testing)"""
        return list(self.users.values())

    def get_all_groups(self) -> List[dict]:
        """Returns all groups (for admin/testing)"""
        result = []
        for group_id, group_data in self.groups.items():
            group = group_data.copy()
            group["Members"] = [
                self.users.get(uid)
                for uid in self.group_enrollments.get(group_id, [])
            ]
            result.append(group)
        return result

    def reset(self):
        """Reset simulator to initial state (for testing)"""
        self.__init__()
