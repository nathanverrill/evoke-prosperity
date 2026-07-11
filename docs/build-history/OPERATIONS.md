# EVOKE LMS Integration - Operations Guide

**Quick reference for operations and support teams**

---

## Service Health

### Check Service Status

```bash
# Health check
curl http://localhost:8000/api/health
# Response: {"status": "ok"}

# Readiness check
curl http://localhost:8000/api/ready
# Response: {"status": "ready", "checks": {...}}
```

### View Application Logs

```bash
# Docker deployment
docker logs -f evoke-prod

# Kubernetes deployment
kubectl logs -f deployment/evoke

# View logs with error filter
docker logs evoke-prod | grep ERROR

# View logs from specific time
docker logs --since 30m evoke-prod
```

### Monitor Metrics

```bash
# Prometheus metrics
curl http://localhost:9090/api/v1/query?query=launches_total

# Custom dashboard
# Open: http://grafana-host:3000/d/evoke-dashboard

# CLI monitoring
watch -n 5 'curl -s http://localhost:8000/api/health'
```

---

## Database Management

### Database Connection

```bash
# Connect to database
psql postgresql://evoke:password@db-host:5432/evoke

# Check database size
SELECT pg_size_pretty(pg_database_size('evoke'));

# Check active connections
SELECT count(*) FROM pg_stat_activity;

# List long-running queries
SELECT * FROM pg_stat_statements
  WHERE query_start < now() - interval '5 minutes'
  ORDER BY total_time DESC;
```

### Database Maintenance

```bash
# Vacuum (reclaim space)
VACUUM ANALYZE;

# Reindex (rebuild indexes)
REINDEX DATABASE evoke;

# Analyze (update statistics)
ANALYZE;
```

### Database Backup

```bash
# Manual backup
pg_basebackup -h db-host -U backup_user -D /backups/manual -Ft -z

# Verify backup
tar -xzf /backups/manual/base.tar.gz -C /tmp/verify

# Restore from backup (see DISASTER_RECOVERY.md)
```

---

## Common Troubleshooting

### Issue: "Database connection timeout"

**Symptoms:**
- All requests returning 503
- Logs: "connection pool exhausted"

**Diagnosis:**
```bash
# Check database server
psql -h db-host -c "SELECT version();"

# Check connection count
psql -h db-host -c "SELECT count(*) FROM pg_stat_activity;"

# Check pool size
echo $DATABASE_POOL_SIZE
```

**Solution:**
```bash
# Option 1: Restart application (clears stale connections)
docker restart evoke-prod

# Option 2: Increase pool size
export DATABASE_POOL_SIZE=20
docker restart evoke-prod

# Option 3: If database hung, restart database
systemctl restart postgresql
```

### Issue: "Brightspace sync failing"

**Symptoms:**
- Evidence submitted but not in Brightspace dropbox
- Grade webhook returns error

**Diagnosis:**
```bash
# Check logs
docker logs evoke-prod | grep -i brightspace

# Test Brightspace API
curl -I https://school.brightspace.com/api/

# Verify credentials
cat .env | grep BRIGHTSPACE
```

**Solution:**
```bash
# 1. Verify Brightspace is up
ping school.brightspace.com

# 2. Check OAuth token expiration
curl -X POST https://school.brightspace.com/oauth/oauth2/token \
  -d "client_id=$BRIGHTSPACE_APP_KEY&client_secret=$BRIGHTSPACE_APP_SECRET&grant_type=client_credentials"

# 3. Check Brightspace logs
# Login to Brightspace admin panel

# 4. Retry failed syncs
curl GET http://localhost:8000/api/webhooks/brightspace/poll
```

### Issue: "High memory usage"

**Symptoms:**
- Container using 3GB+
- Performance degrading
- Potential OOM kill

**Diagnosis:**
```bash
# Check memory usage
docker stats evoke-prod

# Check Python memory
docker exec evoke-prod ps aux | grep python

# Check for memory leaks
docker top evoke-prod
```

**Solution:**
```bash
# 1. Check for long-running transactions
psql -c "SELECT * FROM pg_stat_activity WHERE wait_event IS NOT NULL;"

# 2. Kill long-running queries (if safe)
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
  WHERE state = 'active' AND query_start < now() - interval '1 hour';

# 3. Restart container
docker restart evoke-prod

# 4. If persists, profile with py-spy
pip install py-spy
py-spy record -o profile.svg --pid $(pgrep -f evoke)
```

### Issue: "LTI launches failing"

**Symptoms:**
- Students can't launch from Brightspace
- "JWT verification failed" errors

**Diagnosis:**
```bash
# Check logs
docker logs evoke-prod | grep -i jwt

# Verify Brightspace public key
echo $BRIGHTSPACE_LTI_PUBLIC_KEY | jq .

# Test JWT verification
curl -X POST http://localhost:8000/api/lti/launch \
  -F id_token="eyJ..."
```

**Solution:**
```bash
# 1. Verify public key is valid
echo $BRIGHTSPACE_LTI_PUBLIC_KEY | jq .kty

# 2. Check key expiration
echo $BRIGHTSPACE_LTI_PUBLIC_KEY | jq .exp

# 3. Update key from Brightspace if needed
# Login to Brightspace → Admin Panel → LTI Keys

# 4. Restart application
docker restart evoke-prod
```

### Issue: "Slow response times"

**Symptoms:**
- LTI launches taking >500ms
- Submissions taking >1s
- Users complaining about slowness

**Diagnosis:**
```bash
# Check database query performance
psql -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Check Brightspace API latency
curl -w "@curl-format.txt" -o /dev/null -s https://school.brightspace.com/api/

# Check application response time
curl -w "Time: %{time_total}s\n" http://localhost:8000/api/health

# Check system resources
top -b -n1 | head -20
```

**Solution:**
```bash
# 1. Optimize database indexes
REINDEX DATABASE evoke;
ANALYZE;

# 2. Increase database memory
# Adjust shared_buffers in postgresql.conf

# 3. Enable query caching
# Add caching layer (Redis)

# 4. Scale horizontally
# Add more FastAPI instances behind load balancer
```

---

## Performance Tuning

### Database Tuning

```bash
# Edit postgresql.conf
shared_buffers = 256MB        # 25% of total RAM
effective_cache_size = 1GB    # 50-75% of total RAM
maintenance_work_mem = 64MB
work_mem = 16MB
random_page_cost = 1.1        # For SSD storage

# Apply changes
systemctl restart postgresql
```

### Application Tuning

```bash
# Increase worker count
uvicorn --workers 8 evoke.main:app

# Increase timeout
HTTP_CLIENT_TIMEOUT=30

# Increase connection pool
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

### Cache Configuration

```bash
# Enable Redis caching
CACHE_BACKEND=redis
REDIS_URL=redis://cache-host:6379/0

# Cache TTL (in seconds)
CACHE_TTL_MISSIONS=3600
CACHE_TTL_BADGES=3600
CACHE_TTL_USERS=300
```

---

## Monitoring Dashboards

### Grafana Dashboards

**Available dashboards:**
- `evoke-dashboard` - Overview (launches, submissions, errors)
- `brightspace-integration` - Brightspace API metrics
- `database-performance` - PostgreSQL metrics
- `system-resources` - CPU, memory, disk

**Access:**
- URL: `http://grafana-host:3000`
- Default credentials: admin/admin (change!)

### Alert Channels

**Critical alerts → PagerDuty (page on-call engineer)**
- LTI launch error rate > 5%
- Database connection pool exhausted
- Brightspace API down
- Certificate expiring

**Warning alerts → Slack #evoke-ops**
- LTI launch error rate > 1%
- Database query duration > 500ms p95
- Brightspace API latency > 2s
- Disk space < 10%

---

## Deployment

### Pre-Deployment Checklist

```bash
bash scripts/pre-deployment-check.sh
```

Validates:
- [x] System resources (CPU, memory, disk)
- [x] Database connectivity
- [x] Brightspace configuration
- [x] SSL/TLS certificate
- [x] Network connectivity
- [x] Required dependencies
- [x] Backups exist

### Deployment Procedure

```bash
# 1. Pre-deployment validation
bash scripts/pre-deployment-check.sh

# 2. Backup current database
pg_basebackup -h db-host -U backup_user -D /backups/pre-deploy -Ft -z

# 3. Deploy new version
docker pull evoke:v1.1.0
docker stop evoke-prod
docker run -d --name evoke-prod ... evoke:v1.1.0

# 4. Health checks
curl http://localhost:8000/api/health
curl http://localhost:8000/api/ready

# 5. Smoke tests
bash tests/manual_test_happy_path.sh

# 6. Monitor for 30 minutes
watch -n 5 'curl -s http://localhost:8000/api/health'
```

### Rollback Procedure

```bash
# 1. Identify last good version
git log --oneline | head -3

# 2. Stop current version
docker stop evoke-prod

# 3. Restore previous version
docker run -d --name evoke-prod ... evoke:v1.0.5

# 4. Verify
curl http://localhost:8000/api/health

# 5. Run tests
bash tests/manual_test_happy_path.sh
```

---

## Scheduled Maintenance

### Daily Tasks

- Monitor error rates
- Check disk space
- Verify backups completed

### Weekly Tasks

- Review slow queries
- Test backup restoration
- Check SSL certificate expiration
- Review error logs

### Monthly Tasks

- Analyze database performance
- Update dependencies
- Review and adjust alert thresholds
- Capacity planning

### Quarterly Tasks

- Security audit
- Disaster recovery drill
- Performance baseline review
- Capacity forecast

---

## Escalation Procedures

### Level 1: Alerts & Monitoring

**Responsibility:** On-call engineer monitors alerts

- [x] LTI launch errors > 5% → PAGE ENGINEER
- [x] Database down → PAGE ENGINEER
- [x] Brightspace API down → PAGE ENGINEER

### Level 2: Investigation & Triage

**Responsibility:** On-call engineer investigates

1. Check application logs
2. Check system metrics
3. Check database status
4. Check Brightspace status
5. Create incident ticket

### Level 3: Resolution & Escalation

**Responsibility:** Team lead or senior engineer

1. If database issue → Database administrator
2. If Brightspace issue → Brightspace support
3. If infrastructure issue → Infrastructure team
4. If code bug → Development team

---

## Contact & Escalation

**On-Call Engineer:** PagerDuty rotation  
**Team Lead:** team-lead@school.edu  
**Brightspace Support:** support@brightspace.com  
**Infrastructure Team:** infrastructure@school.edu  
**Database DBA:** dba@school.edu

---

**For detailed procedures, see:**
- DEPLOYMENT.md - Deployment procedures
- MONITORING.md - Monitoring setup
- DISASTER_RECOVERY.md - Backup and recovery
- TROUBLESHOOTING.md - Detailed troubleshooting guide
