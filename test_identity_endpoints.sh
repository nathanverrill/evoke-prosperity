#!/bin/bash

# Test script for EVOKE Identity System (Task 1.1)
# Tests the four identity linking endpoints

set -e

BASE_URL="http://localhost:8000"
BS_URL="http://localhost:8001"

echo "========================================"
echo "EVOKE Identity System Test (Task 1.1)"
echo "========================================"
echo ""

# Test data
EVOKE_USER_ID="ac29d0ec-508b-4ae3-9a0f-1a090d924f29"
MINECRAFT_UUID="550e8400-e29b-41d4-a716-446655440000"
MINECRAFT_USERNAME="DemoPlayer"

echo "1. Getting Brightspace token..."
BS_TOKEN=$(curl -s -X POST "$BS_URL/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=learner@evoke.local&password=password" | jq -r '.access_token')
echo "   Token: $BS_TOKEN"
echo ""

echo "2. Testing POST /api/identity/link-brightspace"
echo "   Request: Link Brightspace user 6001 to EVOKE user"
LINK_BS=$(curl -s -X POST "$BASE_URL/api/identity/link-brightspace" \
  -H "Content-Type: application/json" \
  -d "{
    \"evoke_user_id\": \"$EVOKE_USER_ID\",
    \"brightspace_user_id\": 6001,
    \"brightspace_access_token\": \"$BS_TOKEN\"
  }")
echo "   Response: $LINK_BS" | jq '.'
echo ""

echo "3. Testing POST /api/identity/link-minecraft"
echo "   Request: Link Minecraft UUID to EVOKE user"
LINK_MC=$(curl -s -X POST "$BASE_URL/api/identity/link-minecraft" \
  -H "Content-Type: application/json" \
  -d "{
    \"evoke_user_id\": \"$EVOKE_USER_ID\",
    \"minecraft_uuid\": \"$MINECRAFT_UUID\",
    \"minecraft_username\": \"$MINECRAFT_USERNAME\"
  }")
echo "   Response:"
echo "$LINK_MC" | jq '.'
echo ""

echo "4. Testing GET /api/identity/{evoke_user_id}"
echo "   Request: Get identity mapping for user"
GET_ID=$(curl -s "$BASE_URL/api/identity/$EVOKE_USER_ID")
echo "   Response:"
echo "$GET_ID" | jq '.'
echo ""

echo "5. Testing GET /api/identity/by-brightspace/{brightspace_user_id}"
echo "   Request: Look up EVOKE user by Brightspace ID"
GET_BS=$(curl -s "$BASE_URL/api/identity/by-brightspace/6001")
echo "   Response:"
echo "$GET_BS" | jq '.'
echo ""

echo "========================================"
echo "Testing complete! ✅"
echo "========================================"
echo ""
echo "If all endpoints returned valid JSON responses,"
echo "the identity system is working correctly."
echo ""
echo "Check the database with:"
echo "  docker compose -f evoke-infra/docker-compose.yml exec -T postgres \\"
echo "    psql -U evoke -d evoke -c \"SELECT * FROM evoke_identities;\""
