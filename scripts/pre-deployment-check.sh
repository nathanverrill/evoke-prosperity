#!/bin/bash
#
# Pre-Deployment Check Script
# Validates all systems are ready for deployment
#
# Usage:
#   bash scripts/pre-deployment-check.sh
#

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

check_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# ============================================================================
# System Resources
# ============================================================================
print_header "System Resources"

# CPU
cpu_count=$(nproc)
if [ "$cpu_count" -ge 2 ]; then
    check_pass "CPU cores: $cpu_count (minimum 2)"
else
    check_fail "CPU cores: $cpu_count (need at least 2)"
fi

# Memory
mem_total=$(free -h | awk '/^Mem/ {print $2}')
mem_available=$(free -h | awk '/^Mem/ {print $7}')
if [ "$(echo "$mem_available" | grep -oE '^[0-9]+')" -ge 2 ]; then
    check_pass "Memory available: $mem_available (minimum 2GB)"
else
    check_fail "Memory available: $mem_available (need at least 2GB)"
fi

# Disk Space
disk_available=$(df -h / | awk 'NR==2 {print $4}')
disk_percent=$(df -h / | awk 'NR==2 {print $5}')
if [ "$(echo "$disk_percent" | grep -oE '^[0-9]+')" -lt 80 ]; then
    check_pass "Disk space: $disk_available (usage: $disk_percent)"
else
    check_fail "Disk space: $disk_available (usage: $disk_percent - too high!)"
fi

# ============================================================================
# Database Connectivity
# ============================================================================
print_header "Database Connectivity"

if [ -z "$DATABASE_URL" ]; then
    check_fail "DATABASE_URL environment variable not set"
else
    # Extract connection info
    DB_HOST=$(echo "$DATABASE_URL" | grep -oE '/@[^/]+' | sed 's/@//')
    DB_NAME=$(echo "$DATABASE_URL" | grep -oE '/[^/]*$' | sed 's///')

    # Test connection
    if psql "$DATABASE_URL" -c "SELECT 1" > /dev/null 2>&1; then
        check_pass "Database connection successful ($DB_HOST)"

        # Check for required tables
        if psql "$DATABASE_URL" -c "SELECT 1 FROM submissions LIMIT 1" > /dev/null 2>&1; then
            check_pass "Required tables exist"
        else
            check_fail "Required tables missing (run migrations)"
        fi

        # Check connection pool
        ACTIVE_CONNS=$(psql "$DATABASE_URL" -c "SELECT count(*) FROM pg_stat_activity" | grep -oE '^[0-9]+' | head -1)
        if [ "$ACTIVE_CONNS" -lt 50 ]; then
            check_pass "Database connections: $ACTIVE_CONNS (healthy)"
        else
            check_warn "Database connections: $ACTIVE_CONNS (potentially high)"
        fi
    else
        check_fail "Database connection failed ($DB_HOST)"
    fi
fi

# ============================================================================
# Brightspace Configuration
# ============================================================================
print_header "Brightspace Configuration"

if [ -z "$BRIGHTSPACE_TENANT_URL" ]; then
    check_fail "BRIGHTSPACE_TENANT_URL not set"
else
    check_pass "BRIGHTSPACE_TENANT_URL configured"
fi

if [ -z "$BRIGHTSPACE_APP_KEY" ]; then
    check_fail "BRIGHTSPACE_APP_KEY not set"
else
    check_pass "BRIGHTSPACE_APP_KEY configured"
fi

if [ -z "$BRIGHTSPACE_LTI_CLIENT_ID" ]; then
    check_fail "BRIGHTSPACE_LTI_CLIENT_ID not set"
else
    check_pass "BRIGHTSPACE_LTI_CLIENT_ID configured"
fi

# Test Brightspace connectivity
if [ -n "$BRIGHTSPACE_TENANT_URL" ]; then
    if curl -s -I "$BRIGHTSPACE_TENANT_URL/api/" | grep -q "200\|301\|302"; then
        check_pass "Brightspace API reachable"
    else
        check_warn "Brightspace API not responding (may be temporary)"
    fi
fi

# ============================================================================
# Application Configuration
# ============================================================================
print_header "Application Configuration"

if [ -z "$SECRET_KEY" ]; then
    check_fail "SECRET_KEY not configured"
else
    check_pass "SECRET_KEY configured"
fi

if [ -z "$JWT_SECRET" ]; then
    check_fail "JWT_SECRET not configured"
else
    check_pass "JWT_SECRET configured"
fi

if [ -z "$LOG_LEVEL" ]; then
    check_warn "LOG_LEVEL not set (using default)"
else
    check_pass "LOG_LEVEL configured: $LOG_LEVEL"
fi

# ============================================================================
# SSL/TLS Certificate
# ============================================================================
print_header "SSL/TLS Certificate"

if [ -f "/etc/ssl/certs/evoke.pem" ]; then
    CERT_EXPIRY=$(openssl x509 -in /etc/ssl/certs/evoke.pem -noout -enddate 2>/dev/null | cut -d= -f2)
    DAYS_UNTIL_EXPIRY=$(( ($(date -d "$CERT_EXPIRY" +%s) - $(date +%s)) / 86400 ))

    if [ "$DAYS_UNTIL_EXPIRY" -gt 30 ]; then
        check_pass "SSL certificate valid for $DAYS_UNTIL_EXPIRY days"
    elif [ "$DAYS_UNTIL_EXPIRY" -gt 7 ]; then
        check_warn "SSL certificate expires in $DAYS_UNTIL_EXPIRY days (renew soon)"
    else
        check_fail "SSL certificate expires in $DAYS_UNTIL_EXPIRY days (RENEW IMMEDIATELY)"
    fi

    # Verify certificate chain
    if openssl x509 -in /etc/ssl/certs/evoke.pem -text -noout | grep -q "X509v3 Basic Constraints"; then
        check_pass "SSL certificate chain valid"
    fi
else
    check_warn "SSL certificate file not found (verify path)"
fi

# ============================================================================
# Network Connectivity
# ============================================================================
print_header "Network Connectivity"

# DNS resolution
if dig +short school.brightspace.com > /dev/null 2>&1; then
    check_pass "DNS resolution working"
else
    check_fail "DNS resolution failed"
fi

# Outbound connectivity
if curl -s -I https://school.brightspace.com > /dev/null 2>&1; then
    check_pass "Outbound HTTPS connectivity working"
else
    check_warn "Outbound HTTPS connectivity may be blocked"
fi

# ============================================================================
# Application Readiness
# ============================================================================
print_header "Application Readiness"

if [ -n "$APPLICATION_URL" ]; then
    if curl -s "$APPLICATION_URL/api/health" | grep -q "ok"; then
        check_pass "Application health check passing"
    else
        check_fail "Application health check failed"
    fi

    if curl -s "$APPLICATION_URL/api/ready" | grep -q "ready"; then
        check_pass "Application readiness check passing"
    else
        check_warn "Application not fully ready (initializing)"
    fi
else
    check_warn "APPLICATION_URL not set (cannot check readiness)"
fi

# ============================================================================
# Required Dependencies
# ============================================================================
print_header "Required Dependencies"

# Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    check_pass "Python 3 installed: $PYTHON_VERSION"
else
    check_fail "Python 3 not found"
fi

# psql
if command -v psql &> /dev/null; then
    check_pass "psql (PostgreSQL client) installed"
else
    check_fail "psql not found"
fi

# curl
if command -v curl &> /dev/null; then
    check_pass "curl installed"
else
    check_fail "curl not found"
fi

# Docker (if using Docker deployment)
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}')
    check_pass "Docker installed: $DOCKER_VERSION"
else
    check_warn "Docker not found (if using Docker deployment)"
fi

# ============================================================================
# File Permissions
# ============================================================================
print_header "File Permissions"

# Check write permissions for log directory
if [ -d "/var/log/evoke" ]; then
    if touch /var/log/evoke/test.log 2>/dev/null; then
        rm /var/log/evoke/test.log
        check_pass "Log directory writable"
    else
        check_fail "No write permissions to /var/log/evoke"
    fi
else
    check_warn "Log directory doesn't exist (will be created)"
fi

# ============================================================================
# Backup Verification
# ============================================================================
print_header "Backup Verification"

if [ -d "/backups" ]; then
    BACKUP_COUNT=$(ls -1 /backups/*/base.tar.gz 2>/dev/null | wc -l)
    if [ "$BACKUP_COUNT" -gt 0 ]; then
        check_pass "Backups exist ($BACKUP_COUNT found)"

        # Check backup age
        LATEST_BACKUP=$(ls -t /backups/*/base.tar.gz 2>/dev/null | head -1)
        BACKUP_AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 3600 ))

        if [ "$BACKUP_AGE" -lt 25 ]; then
            check_pass "Latest backup is $BACKUP_AGE hours old"
        else
            check_warn "Latest backup is $BACKUP_AGE hours old (should be < 24h)"
        fi
    else
        check_fail "No backups found"
    fi
else
    check_fail "Backup directory not found"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
print_header "Pre-Deployment Check Summary"

TOTAL=$((PASSED + FAILED))
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "Total:  $TOTAL"

if [ $FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ All checks passed! Ready for deployment.${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}✗ Some checks failed. Fix issues before deployment.${NC}"
    exit 1
fi
