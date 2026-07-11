"""
Load Testing: Concurrent LTI Launches
Simulates 100+ students simultaneously launching EVOKE from Brightspace

Usage:
    locust -f tests/load_test_lti_launch.py --host=http://localhost:8000 --users=100 --spawn-rate=10

Metrics to monitor:
    - Requests/sec: Should handle 10+ launches/sec
    - Response time p95: <500ms
    - Success rate: 100%
    - Database pool: Stays within limit
"""

from locust import HttpUser, task, between
import json
from datetime import datetime, timedelta
import jwt


class LTILaunchUser(HttpUser):
    """Simulates a student launching EVOKE from Brightspace"""

    wait_time = between(1, 3)  # Wait 1-3 seconds between launches

    @staticmethod
    def create_test_jwt(user_id: int) -> str:
        """Create a test JWT"""
        payload = {
            "iss": "https://school.brightspace.com",
            "aud": "test-client-id",
            "sub": str(user_id),
            "email": f"student{user_id}@school.edu",
            "name": f"Test Student {user_id}",
            "roles": ["http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"],
            "iat": int(datetime.utcnow().timestamp()),
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        }

        # Note: In real tests, this would be signed with the actual Brightspace key
        # For now, return unsigned payload
        return jwt.encode(payload, "test-secret", algorithm="HS256")

    @task(1)
    def launch_from_brightspace(self):
        """Simulate student launching EVOKE from Brightspace"""
        user_id = 6000 + abs(hash(self.client.username or "")) % 1000

        jwt_token = self.create_test_jwt(user_id)

        with self.client.post(
            "/api/lti/launch",
            data={"id_token": jwt_token},
            catch_response=True,
            name="/api/lti/launch"
        ) as response:
            if response.status_code in [200, 302]:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def launch_same_user_concurrent(self):
        """Simulate same user launching in multiple tabs (concurrency test)"""
        jwt_token = self.create_test_jwt(6001)

        with self.client.post(
            "/api/lti/launch",
            data={"id_token": jwt_token},
            catch_response=True,
            name="/api/lti/launch [concurrent]"
        ) as response:
            if response.status_code in [200, 302]:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


class LTILaunchWithFollowupUser(HttpUser):
    """Simulates a student launching and then accessing missions"""

    wait_time = between(2, 5)

    @staticmethod
    def create_test_jwt(user_id: int) -> str:
        """Create a test JWT"""
        payload = {
            "iss": "https://school.brightspace.com",
            "aud": "test-client-id",
            "sub": str(user_id),
            "email": f"student{user_id}@school.edu",
            "name": f"Test Student {user_id}",
            "iat": int(datetime.utcnow().timestamp()),
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
        }
        return jwt.encode(payload, "test-secret", algorithm="HS256")

    @task(1)
    def launch_and_view_missions(self):
        """Launch and view missions (more realistic flow)"""
        user_id = 6000 + abs(hash(self.client.username or "")) % 1000
        jwt_token = self.create_test_jwt(user_id)

        # 1. LTI Launch
        with self.client.post(
            "/api/lti/launch",
            data={"id_token": jwt_token},
            catch_response=True,
            name="/api/lti/launch"
        ) as response:
            if response.status_code not in [200, 302]:
                response.failure(f"Launch failed: {response.status_code}")
                return

            # Extract session token if available
            session_token = response.headers.get("set-cookie", "")

        # 2. View missions (with session)
        with self.client.get(
            "/api/missions",
            params={"user_id": str(user_id)},
            headers={"Cookie": f"session_token={session_token}"},
            catch_response=True,
            name="/api/missions"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Missions view failed: {response.status_code}")


if __name__ == "__main__":
    print("""
    Load Testing: LTI Launches

    Run with:
        locust -f tests/load_test_lti_launch.py \\
            --host=http://localhost:8000 \\
            --users=100 \\
            --spawn-rate=10 \\
            --run-time=5m

    Metrics to watch:
    - Requests/sec
    - Response time (p50, p95, p99)
    - Success rate
    - Failure rate

    Expected results:
    - 100+ concurrent users supported
    - <500ms p95 response time
    - 100% success rate
    - No database connection errors
    """)
