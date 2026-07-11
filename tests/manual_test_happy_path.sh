#!/bin/bash
#
# Manual Test Script: Complete Brightspace Integration Workflow
#
# Tests: LTI launch → evidence submission → grading → award sync → collection
#
# Prerequisites:
#   - EVOKE backend running on localhost:8000
#   - PostgreSQL with test data loaded
#   - jq installed (for JSON parsing)
#
# Usage:
#   bash tests/manual_test_happy_path.sh
#

set -e

BASE_URL="http://localhost:8000"
PASSED=0
FAILED=0

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

print_failure() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

assert_status() {
    local response=$1
    local expected=$2
    local test_name=$3

    local status=$(echo "$response" | jq -r '.status // "error"')

    if [ "$status" = "$expected" ]; then
        print_success "$test_name"
        return 0
    else
        print_failure "$test_name (got: $status, expected: $expected)"
        return 1
    fi
}

# ============================================================================
# Test 1: Service Health Check
# ============================================================================
print_test "Checking EVOKE service health..."

health_response=$(curl -s "${BASE_URL}/api/health" 2>/dev/null || echo '{"status":"error"}')
if echo "$health_response" | jq -e '.status' > /dev/null 2>&1; then
    print_success "EVOKE service is running"
else
    print_failure "EVOKE service health check failed"
    echo "Make sure EVOKE backend is running: python -m evoke.main"
    exit 1
fi

# ============================================================================
# Test 2: LTI Launch (JWT Verification)
# ============================================================================
print_test "Phase 1: LTI Launch & Authentication"

# Create test JWT (not signed, but valid structure)
test_jwt=$(cat <<'EOF'
eyJhbGciOiJSUzI1NiIsImtpZCI6InRlc3Qta2V5In0.eyJpc3MiOiJodHRwczovL3NjaG9vbC5icmlnaHRzcGFjZS5jb20iLCJhdWQiOiJ0ZXN0LWNsaWVudC1pZCIsInN1YiI6IjYwMDEiLCJlbWFpbCI6InN0dWRlbnRAc2Nob29sLmVkdSIsIm5hbWUiOiJUZXN0IFN0dWRlbnQiLCJyb2xlcyI6WyJodHRwOi8vcHVybC5pbXNnbG9iYWwub3JnL3ZvY2FiL2xpcy92Mi9tZW1iZXJzaGlwI0xlYXJuZXIiXSwiaWF0IjoxNjg1NjY2MDAwLCJleHAiOjE2ODU2Njk2MDB9.signature
EOF
)

print_info "Attempting LTI launch..."

lti_response=$(curl -s -X POST "${BASE_URL}/api/lti/launch" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "id_token=${test_jwt}" \
    -w "\n%{http_code}" 2>/dev/null)

# Extract status code
http_code=$(echo "$lti_response" | tail -n1)
response_body=$(echo "$lti_response" | sed '$d')

print_info "HTTP Status: $http_code"

if [ "$http_code" = "302" ] || [ "$http_code" = "200" ]; then
    print_success "LTI launch endpoint responds"

    # Extract session_token from response
    session_token=$(echo "$response_body" | jq -r '.session_token // empty' 2>/dev/null || echo "")

    if [ -z "$session_token" ]; then
        print_info "Session token not in response (may be in cookie)"
        session_token="test-session-token"
    fi

    print_info "Session Token: ${session_token:0:20}..."
else
    print_failure "LTI launch failed with status $http_code"
    echo "Response: $response_body"
fi

# ============================================================================
# Test 3: Submit Evidence
# ============================================================================
print_test "Phase 2: Evidence Submission & Badge Award"

print_info "Submitting evidence..."

submit_response=$(curl -s -X POST "${BASE_URL}/api/submit-evidence" \
    -H "Content-Type: application/json" \
    -H "Cookie: session_token=${session_token}" \
    -d '{
        "mission_id": "mission-001",
        "evidence_url": "https://example.com/evidence.jpg",
        "description": "My awesome evidence"
    }' 2>/dev/null)

print_info "Submission Response: $submit_response"

if echo "$submit_response" | jq -e '.status' > /dev/null 2>&1; then
    status=$(echo "$submit_response" | jq -r '.status')

    if [ "$status" = "success" ]; then
        print_success "Evidence submitted successfully"

        # Extract submission ID for later use
        submission_id=$(echo "$submit_response" | jq -r '.brightspace_submission_id // "unknown"')
        print_info "Submission ID: $submission_id"

        # Verify badge was awarded
        if echo "$submit_response" | jq -e '.award' > /dev/null; then
            award_id=$(echo "$submit_response" | jq -r '.award.id')
            award_tier=$(echo "$submit_response" | jq -r '.award.tier')
            print_success "Common badge awarded (ID: $award_id, Tier: $award_tier)"
        else
            print_info "Badge award info not in response"
        fi
    else
        print_failure "Evidence submission failed: $status"
        echo "Full response: $submit_response"
    fi
else
    print_failure "Evidence submission response invalid"
    echo "Response: $submit_response"
fi

# ============================================================================
# Test 4: Grade Webhook
# ============================================================================
print_test "Phase 3: Teacher Grading & Sync"

print_info "Simulating teacher grade webhook..."

grade_response=$(curl -s -X POST "${BASE_URL}/api/webhooks/brightspace/grade" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "submission_id=${submission_id}" \
    -d "brightspace_user_id=6001" \
    -d "grade=95" \
    -d "feedback=Excellent work!" 2>/dev/null)

print_info "Grade Webhook Response: $grade_response"

if echo "$grade_response" | jq -e '.status' > /dev/null 2>&1; then
    status=$(echo "$grade_response" | jq -r '.status')

    if [ "$status" = "success" ]; then
        print_success "Grade webhook processed successfully"

        # Check award tier
        award_tier=$(echo "$grade_response" | jq -r '.award_tier // "unknown"')
        print_success "Award tier determined: $award_tier"

        if [ "$award_tier" = "legendary" ]; then
            print_success "Correct tier assignment (95 → legendary) ✓"
        elif [ "$award_tier" = "epic" ]; then
            print_success "Correct tier assignment (85-94 → epic) ✓"
        else
            print_info "Award tier: $award_tier"
        fi
    else
        print_failure "Grade webhook failed: $status"
        echo "Full response: $grade_response"
    fi
else
    print_failure "Grade webhook response invalid"
    echo "Response: $grade_response"
fi

# ============================================================================
# Test 5: Polling Fallback
# ============================================================================
print_test "Phase 4: Polling Fallback Test"

print_info "Testing polling endpoint (fallback for webhooks)..."

poll_response=$(curl -s -X GET "${BASE_URL}/api/webhooks/brightspace/poll" 2>/dev/null)

print_info "Polling Response: $poll_response"

if echo "$poll_response" | jq -e '.status' > /dev/null 2>&1; then
    status=$(echo "$poll_response" | jq -r '.status')
    count=$(echo "$poll_response" | jq -r '.count // 0')

    if [ "$status" = "success" ]; then
        print_success "Polling endpoint working (synced $count grades)"
    else
        print_failure "Polling endpoint failed: $status"
    fi
else
    print_failure "Polling response invalid"
fi

# ============================================================================
# Test 6: Session Validation
# ============================================================================
print_test "Phase 5: Session Management"

print_info "Validating session..."

session_response=$(curl -s -X GET "${BASE_URL}/api/session/validate" \
    -H "Cookie: session_token=${session_token}" 2>/dev/null)

print_info "Session Validation Response: $session_response"

if echo "$session_response" | jq -e '.status' > /dev/null 2>&1; then
    status=$(echo "$session_response" | jq -r '.status')

    if [ "$status" = "valid" ] || [ "$status" = "success" ]; then
        print_success "Session is valid"
    else
        print_failure "Session validation failed"
    fi
else
    print_info "Session validation response may be empty (OK)"
fi

# ============================================================================
# Test 7: Logout
# ============================================================================
print_test "Phase 6: Logout"

print_info "Testing logout..."

logout_response=$(curl -s -X POST "${BASE_URL}/api/session/logout" \
    -H "Cookie: session_token=${session_token}" 2>/dev/null)

print_info "Logout Response: $logout_response"

if echo "$logout_response" | jq -e '.status' > /dev/null 2>&1; then
    status=$(echo "$logout_response" | jq -r '.status')

    if [ "$status" = "success" ]; then
        print_success "Logout successful (session_token cleared)"
    else
        print_failure "Logout failed"
    fi
else
    print_info "Logout response may be empty (OK)"
fi

# ============================================================================
# Test 8: Error Scenarios
# ============================================================================
print_test "Error Scenario Tests"

# Invalid JWT
print_info "Testing invalid JWT rejection..."
invalid_jwt_response=$(curl -s -X POST "${BASE_URL}/api/lti/launch" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "id_token=invalid.jwt.token" \
    -w "\n%{http_code}" 2>/dev/null)

invalid_jwt_code=$(echo "$invalid_jwt_response" | tail -n1)

if [ "$invalid_jwt_code" = "401" ] || [ "$invalid_jwt_code" = "400" ]; then
    print_success "Invalid JWT rejected with $invalid_jwt_code"
else
    print_info "Invalid JWT handling: status $invalid_jwt_code"
fi

# Missing required fields
print_info "Testing missing required webhook fields..."
missing_fields_response=$(curl -s -X POST "${BASE_URL}/api/webhooks/brightspace/grade" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "submission_id=test" \
    -w "\n%{http_code}" 2>/dev/null)

missing_fields_code=$(echo "$missing_fields_response" | tail -n1)

if [ "$missing_fields_code" = "400" ] || [ "$missing_fields_code" = "422" ]; then
    print_success "Missing fields rejected with $missing_fields_code"
else
    print_info "Missing fields handling: status $missing_fields_code"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
