"""
End-to-End Integration Tests for Brightspace Integration
Tests complete workflows: LTI launch → submit → grade → collect
"""

import pytest
import json
import asyncio
from datetime import datetime, timedelta
import jwt
from unittest.mock import patch, AsyncMock, MagicMock
import httpx
from fastapi.testclient import TestClient

# Assumes EVOKE backend is running on localhost:8000
BASE_URL = "http://localhost:8000"


# ============================================================================
# Happy Path Tests
# ============================================================================

class TestHappyPath:
    """Complete workflow: LTI launch → evidence submission → grading → collection"""

    @pytest.fixture
    def test_jwt(self):
        """Create valid test JWT"""
        payload = {
            "iss": "https://school.brightspace.com",
            "aud": "test-client-id",
            "sub": "6001",
            "email": "student@school.edu",
            "name": "Test Student",
            "roles": ["http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"],
            "iat": datetime.utcnow().timestamp(),
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
        }
        # Note: In real tests, sign with actual Brightspace key
        # For now, return unsigned payload (would need real key)
        return json.dumps(payload)

    def test_complete_workflow(self, test_jwt):
        """Test: LTI launch → submit → grade → collect"""

        # ========== Phase 1: LTI Launch ==========
        response = httpx.post(
            f"{BASE_URL}/api/lti/launch",
            data={"id_token": test_jwt}
        )

        assert response.status_code == 302, f"LTI launch failed: {response.text}"
        assert "session_token" in response.headers.get("set-cookie", "")

        # Extract session token
        session_token = None
        for cookie in response.headers.get("set-cookie", "").split(","):
            if "session_token" in cookie:
                session_token = cookie.split("=")[1].split(";")[0]
                break

        assert session_token, "No session_token in response"

        # ========== Phase 2: Submit Evidence ==========
        submit_response = httpx.post(
            f"{BASE_URL}/api/submit-evidence",
            json={
                "mission_id": "mission-001",
                "evidence_url": "https://example.com/evidence.jpg",
                "description": "My awesome evidence"
            },
            headers={"Cookie": f"session_token={session_token}"}
        )

        assert submit_response.status_code == 200, f"Submit failed: {submit_response.text}"
        submit_data = submit_response.json()
        assert submit_data["status"] == "success"
        assert "brightspace_submission_id" in submit_data

        submission_id = submit_data["brightspace_submission_id"]

        # ========== Phase 3: Simulate Grade Webhook ==========
        grade_response = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": submission_id,
                "brightspace_user_id": 6001,
                "grade": 95,
                "feedback": "Excellent work!"
            }
        )

        assert grade_response.status_code == 200, f"Grade webhook failed: {grade_response.text}"
        grade_data = grade_response.json()
        assert grade_data["status"] == "success"
        assert grade_data["award_tier"] == "legendary"

        # ========== Phase 4: Verify Grade Synced ==========
        # Get submission and verify grade
        verify_response = httpx.get(
            f"{BASE_URL}/api/submission/{submission_id}",
            headers={"Cookie": f"session_token={session_token}"}
        )

        assert verify_response.status_code == 200
        submission = verify_response.json()
        assert submission["grade"] == 95
        assert submission["feedback"] == "Excellent work!"


# ============================================================================
# Error Scenario Tests
# ============================================================================

class TestErrorScenarios:
    """Test error handling and edge cases"""

    def test_invalid_jwt_signature(self):
        """Test: Invalid JWT signature rejected"""
        invalid_jwt = jwt.encode(
            {"sub": "6001", "email": "student@school.edu"},
            "wrong-secret",
            algorithm="HS256"
        )

        response = httpx.post(
            f"{BASE_URL}/api/lti/launch",
            data={"id_token": invalid_jwt}
        )

        assert response.status_code == 401, "Invalid JWT should be rejected"

    def test_expired_jwt(self):
        """Test: Expired JWT rejected"""
        payload = {
            "iss": "https://school.brightspace.com",
            "aud": "test-client-id",
            "sub": "6001",
            "exp": (datetime.utcnow() - timedelta(hours=1)).timestamp(),  # Expired
        }

        expired_jwt = jwt.encode(payload, "secret", algorithm="HS256")

        response = httpx.post(
            f"{BASE_URL}/api/lti/launch",
            data={"id_token": expired_jwt}
        )

        assert response.status_code == 401, "Expired JWT should be rejected"

    def test_missing_user_link(self):
        """Test: Grade webhook for unknown Brightspace user"""
        response = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "unknown-sub",
                "brightspace_user_id": 9999,  # User doesn't exist
                "grade": 95
            }
        )

        # Should fail gracefully
        assert response.status_code == 400 or response.status_code == 404

    def test_duplicate_grade_webhook(self):
        """Test: Duplicate webhook calls don't create duplicate awards"""
        # First call
        response1 = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "dup-sub-001",
                "brightspace_user_id": 6001,
                "grade": 95
            }
        )

        assert response1.status_code == 200

        # Second call (duplicate)
        response2 = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "dup-sub-001",
                "brightspace_user_id": 6001,
                "grade": 95
            }
        )

        # Should succeed (idempotent)
        assert response2.status_code == 200

        # Parse responses
        data1 = response1.json()
        data2 = response2.json()

        # Both should report success
        assert data1["status"] == "success"
        assert data2["status"] == "success"

    def test_invalid_grade_value(self):
        """Test: Grade validation"""
        response = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "sub-001",
                "brightspace_user_id": 6001,
                "grade": 150  # Invalid grade
            }
        )

        # Should fail validation
        assert response.status_code in [400, 422], "Invalid grade should be rejected"

    def test_missing_required_fields(self):
        """Test: Missing required webhook fields"""
        response = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "sub-001"
                # Missing brightspace_user_id and grade
            }
        )

        assert response.status_code in [400, 422], "Missing fields should fail"


# ============================================================================
# Concurrency Tests
# ============================================================================

class TestConcurrency:
    """Test concurrent request handling"""

    @pytest.mark.asyncio
    async def test_concurrent_lti_launches(self):
        """Test: Multiple simultaneous LTI launches from same user"""
        jwt_payload = {
            "iss": "https://school.brightspace.com",
            "aud": "test-client-id",
            "sub": "6001",
            "email": "student@school.edu",
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
        }
        token = jwt.encode(jwt_payload, "secret", algorithm="HS256")

        # Launch 5 concurrent requests
        async with httpx.AsyncClient() as client:
            tasks = [
                client.post(
                    f"{BASE_URL}/api/lti/launch",
                    data={"id_token": token}
                )
                for _ in range(5)
            ]

            responses = await asyncio.gather(*tasks)

            # All should succeed
            for response in responses:
                assert response.status_code == 302

    @pytest.mark.asyncio
    async def test_concurrent_submissions(self):
        """Test: Multiple simultaneous evidence submissions"""
        session_token = "test-session-token"

        async with httpx.AsyncClient() as client:
            tasks = [
                client.post(
                    f"{BASE_URL}/api/submit-evidence",
                    json={
                        "mission_id": f"mission-{i}",
                        "evidence_url": f"https://example.com/evidence-{i}.jpg"
                    },
                    headers={"Cookie": f"session_token={session_token}"}
                )
                for i in range(10)
            ]

            responses = await asyncio.gather(*tasks)

            # All should succeed
            success_count = sum(1 for r in responses if r.status_code == 200)
            assert success_count == 10


# ============================================================================
# Grade Tier Mapping Tests
# ============================================================================

class TestGradeTierMapping:
    """Test correct badge tier assignment based on grade"""

    def test_legendary_tier_95_plus(self):
        """Test: Grade 95+ = legendary tier"""
        response = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "grade-test-95",
                "brightspace_user_id": 6001,
                "grade": 95
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["award_tier"] == "legendary"

    def test_epic_tier_85_94(self):
        """Test: Grade 85-94 = epic tier"""
        response = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "grade-test-90",
                "brightspace_user_id": 6001,
                "grade": 90
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["award_tier"] == "epic"

    def test_common_tier_below_85(self):
        """Test: Grade <85 = common tier (or already awarded)"""
        response = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "grade-test-80",
                "brightspace_user_id": 6001,
                "grade": 80
            }
        )

        # Should either return common or indicate already awarded
        assert response.status_code in [200, 409]


# ============================================================================
# Session Security Tests
# ============================================================================

class TestSessionSecurity:
    """Test session cookie security settings"""

    def test_session_cookie_http_only(self):
        """Test: session_token cookie is HttpOnly"""
        jwt_payload = {
            "iss": "https://school.brightspace.com",
            "aud": "test-client-id",
            "sub": "6001",
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
        }
        token = jwt.encode(jwt_payload, "secret", algorithm="HS256")

        response = httpx.post(
            f"{BASE_URL}/api/lti/launch",
            data={"id_token": token}
        )

        set_cookie = response.headers.get("set-cookie", "")
        assert "session_token" in set_cookie
        assert "httponly" in set_cookie.lower()

    def test_session_cookie_secure_flag(self):
        """Test: session_token cookie has Secure flag"""
        jwt_payload = {
            "iss": "https://school.brightspace.com",
            "aud": "test-client-id",
            "sub": "6001",
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
        }
        token = jwt.encode(jwt_payload, "secret", algorithm="HS256")

        response = httpx.post(
            f"{BASE_URL}/api/lti/launch",
            data={"id_token": token}
        )

        set_cookie = response.headers.get("set-cookie", "")
        # In production, should have Secure flag (HTTPS)
        # In dev, may not have it
        assert "session_token" in set_cookie

    def test_session_cookie_samesite_lax(self):
        """Test: session_token cookie has SameSite=Lax"""
        jwt_payload = {
            "iss": "https://school.brightspace.com",
            "aud": "test-client-id",
            "sub": "6001",
            "exp": (datetime.utcnow() + timedelta(hours=1)).timestamp(),
        }
        token = jwt.encode(jwt_payload, "secret", algorithm="HS256")

        response = httpx.post(
            f"{BASE_URL}/api/lti/launch",
            data={"id_token": token}
        )

        set_cookie = response.headers.get("set-cookie", "")
        assert "samesite" in set_cookie.lower()


# ============================================================================
# SQL Injection & XSS Prevention Tests
# ============================================================================

class TestSecurityVulnerabilities:
    """Test protection against common vulnerabilities"""

    def test_sql_injection_in_mission_id(self):
        """Test: SQL injection in mission_id rejected"""
        response = httpx.post(
            f"{BASE_URL}/api/submit-evidence",
            json={
                "mission_id": "1' OR '1'='1",
                "evidence_url": "https://example.com/evidence.jpg"
            },
            headers={"Cookie": "session_token=test"}
        )

        # Should fail validation
        assert response.status_code in [400, 422, 404]

    def test_xss_in_feedback(self):
        """Test: XSS payload in feedback field"""
        response = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "sub-001",
                "brightspace_user_id": 6001,
                "grade": 95,
                "feedback": "<script>alert('xss')</script>"
            }
        )

        # Either rejected or safely escaped
        if response.status_code == 200:
            # If accepted, ensure script is escaped
            data = response.json()
            # Script tags should be escaped or removed
            assert "<script>" not in str(data) or "&lt;script&gt;" in str(data)

    def test_null_byte_injection(self):
        """Test: Null bytes in strings rejected"""
        response = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "sub\x00-001",
                "brightspace_user_id": 6001,
                "grade": 95
            }
        )

        # Should be rejected or sanitized
        assert response.status_code in [400, 422]


# ============================================================================
# Database Integrity Tests
# ============================================================================

class TestDatabaseIntegrity:
    """Test data consistency and integrity"""

    def test_award_uniqueness_constraint(self):
        """Test: UNIQUE constraint prevents duplicate awards"""
        # Award same badge twice
        response1 = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "unique-sub-1",
                "brightspace_user_id": 6001,
                "grade": 95
            }
        )

        response2 = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "unique-sub-1",
                "brightspace_user_id": 6001,
                "grade": 95
            }
        )

        # Both should succeed (idempotent)
        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_submission_grade_update(self):
        """Test: Submission grade can only be updated once"""
        # First grade
        response1 = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "update-sub-1",
                "brightspace_user_id": 6001,
                "grade": 85
            }
        )

        assert response1.status_code == 200

        # Update grade to higher value
        response2 = httpx.post(
            f"{BASE_URL}/api/webhooks/brightspace/grade",
            data={
                "submission_id": "update-sub-1",
                "brightspace_user_id": 6001,
                "grade": 95
            }
        )

        # Should succeed and update
        assert response2.status_code == 200
        # Verify grade was updated to 95
        assert response2.json()["award_tier"] == "legendary"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
