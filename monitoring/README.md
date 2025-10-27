# Spock Trading System - Monitoring Infrastructure

Comprehensive monitoring setup for multi-region stock trading system using Prometheus + Grafana.

## Overview

This monitoring infrastructure provides:
- **Real-time metrics collection** from 6 global markets (KR, US, CN, HK, JP, VN)
- **Data quality monitoring** with automated alerts
- **API health tracking** with latency and error rate metrics
- **Visual dashboards** for each region + overview dashboard
- **Alerting system** with configurable notification channels

## Architecture

```
Spock Trading System
    ↓ (metrics)
Prometheus Exporter (Port 8000)
    ↓ (scrape)
Prometheus (Port 9090)
    ↓ (query)
Grafana (Port 3000)
    ↓ (alerts)
Alertmanager (Port 9093)
    ↓ (notifications)
Slack / Email / Webhook
```

## Quick Start

### 1. Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ with required packages
- Spock database at `/Users/13ruce/spock/data/spock_local.db`

Install Python dependencies:
```bash
pip install prometheus_client psutil
```

### 2. Start Monitoring Stack

```bash
# Navigate to monitoring directory
cd ~/spock/monitoring

# Start Prometheus, Grafana, and Alertmanager
docker-compose up -d

# Verify containers are running
docker-compose ps
```

Expected output:
```
NAME                  STATUS    PORTS
spock-prometheus      running   0.0.0.0:9090->9090/tcp
spock-grafana         running   0.0.0.0:3000->3000/tcp
spock-alertmanager    running   0.0.0.0:9093->9093/tcp
```

### 3. Start Metrics Exporter

```bash
# Start exporter (collects metrics from Spock database)
cd ~/spock/monitoring/exporters
python3 spock_exporter.py --port 8000 --interval 15

# Or run in background
nohup python3 spock_exporter.py --port 8000 --interval 15 > exporter.log 2>&1 &
```

Verify exporter is working:
```bash
curl http://localhost:8000/metrics
```

### 4. Access Dashboards

**Grafana** (Visualization):
- URL: http://localhost:3000
- Username: `admin`
- Password: `spock2025`

**Prometheus** (Metrics):
- URL: http://localhost:9090

**Alertmanager** (Alerts):
- URL: http://localhost:9093

## Dashboards

### Overview Dashboard
**Purpose**: System-wide monitoring across all 6 markets

**Panels**:
- Total OHLCV rows across all regions
- OHLCV rows distribution by region
- Data collection success rate per region
- API latency (p95) by region
- NULL regions detected (should be 0)
- Cross-region contamination (should be 0)
- Database size
- System status

**Access**: Grafana → "Spock Trading System - Overview"

### Region-Specific Dashboards

Each region has a dedicated dashboard:
- **Korea (KR)**: KOSPI/KOSDAQ monitoring
- **US**: NYSE/NASDAQ/AMEX monitoring
- **China (CN)**: SSE/SZSE monitoring
- **Hong Kong (HK)**: HKEX monitoring
- **Japan (JP)**: TSE monitoring
- **Vietnam (VN)**: HOSE/HNX monitoring

**Panels per region**:
- Total OHLCV rows
- Unique tickers
- Adapter status (UP/DOWN)
- Data collection rate (success/failed)
- API latency (p50, p95, p99)
- API error rate
- API rate limit usage

## Metrics Reference

### Data Quality Metrics

| Metric | Description | Type | Labels |
|--------|-------------|------|--------|
| `spock_ohlcv_rows_total` | Total OHLCV rows | Gauge | region |
| `spock_ohlcv_null_regions_total` | Rows with NULL region | Gauge | - |
| `spock_cross_region_contamination_total` | Tickers in multiple regions | Gauge | - |
| `spock_unique_tickers_total` | Unique tickers | Gauge | region |
| `spock_last_data_update_timestamp` | Last data update time | Gauge | region |

### API Metrics

| Metric | Description | Type | Labels |
|--------|-------------|------|--------|
| `spock_api_requests_total` | Total API requests | Counter | region, endpoint |
| `spock_api_requests_failed_total` | Failed API requests | Counter | region, endpoint |
| `spock_api_request_duration_seconds` | API request duration | Histogram | region, endpoint |
| `spock_api_rate_limit_usage_percent` | Rate limit usage | Gauge | region |

### Database Metrics

| Metric | Description | Type | Labels |
|--------|-------------|------|--------|
| `spock_database_size_bytes` | Database file size | Gauge | - |
| `spock_db_query_duration_seconds` | Query duration | Histogram | query_type |
| `spock_last_backup_timestamp` | Last backup time | Gauge | - |

### System Metrics

| Metric | Description | Type | Labels |
|--------|-------------|------|--------|
| `spock_memory_usage_percent` | Memory usage | Gauge | - |
| `spock_disk_free_bytes` | Free disk space | Gauge | - |

## Alert Rules

### Critical Alerts (Immediate Action)

1. **NullRegionDetected**
   - Condition: `spock_ohlcv_null_regions_total > 0`
   - Action: Investigate data collection pipeline

2. **CrossRegionContamination**
   - Condition: `spock_cross_region_contamination_total > 0`
   - Action: Check adapter region injection

3. **CriticalAPIErrorRate**
   - Condition: Error rate > 20%
   - Action: Check API credentials and connectivity

4. **SpockServiceDown**
   - Condition: Service not responding
   - Action: Restart service, check logs

### Warning Alerts (Review Required)

1. **LowDataCollectionRate**
   - Condition: Success rate < 80%
   - Action: Review collection logs

2. **HighAPIErrorRate**
   - Condition: Error rate > 5%
   - Action: Monitor API status

3. **HighAPILatency**
   - Condition: p95 latency > 2 seconds
   - Action: Check network and API performance

4. **StaleMarketData**
   - Condition: No updates for 24 hours
   - Action: Check scheduler and market hours

## Configuration

### Prometheus Configuration

Edit `prometheus/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s      # Metrics collection frequency
  evaluation_interval: 15s  # Rule evaluation frequency

scrape_configs:
  - job_name: 'spock_trading'
    static_configs:
      - targets: ['localhost:8000']  # Metrics exporter
```

### Alert Rules

Edit `prometheus/alerts.yml`:
```yaml
groups:
  - name: data_quality
    rules:
      - alert: LowDataCollectionRate
        expr: |
          (rate(spock_data_collection_success_total[5m]) /
           rate(spock_data_collection_attempts_total[5m])) < 0.80
        for: 5m
        annotations:
          summary: "Low data collection rate"
```

### Alertmanager Notifications

**⚠️ Alert notification setup required for production use!**

#### Quick Setup

1. **Configure credentials**:
   ```bash
   cd ~/spock/monitoring
   cp .env.alertmanager.example .env.alertmanager
   vim .env.alertmanager  # Add your real credentials
   ```

2. **Enable notification channels**:
   ```bash
   vim alertmanager/alertmanager.yml
   # Uncomment desired receivers (Slack, Email, Webhook)
   ```

3. **Restart Alertmanager**:
   ```bash
   docker-compose restart alertmanager
   ```

4. **Test notifications**:
   ```bash
   python3 scripts/test_alerts.py --channel slack
   python3 scripts/test_alerts.py --channel email
   ```

#### Supported Notification Channels

- **Slack**: Rich formatted messages with emoji and severity colors
- **Email**: HTML emails with detailed alert information
- **Webhook**: Custom HTTP endpoints for integration with other systems
- **Console**: Alertmanager logs (always enabled)

#### Alert Priority Levels

**Balanced Mode** (default):
- **Critical**: Email + Slack + Webhook + Console (repeat: 30min)
- **Warning**: Slack + Webhook + Console (repeat: 2h)
- **Info**: Suppressed (console only)

#### Complete Setup Guide

For detailed setup instructions including:
- Slack app creation and webhook configuration
- Gmail/Outlook/Custom SMTP setup
- Custom webhook endpoint development
- Alert testing procedures
- Troubleshooting common issues

**See**: [`docs/ALERT_NOTIFICATION_SETUP.md`](docs/ALERT_NOTIFICATION_SETUP.md)

#### Alert Management

**Silence alerts during maintenance**:
```bash
# Silence specific alert for 2 hours
python3 scripts/manage_silences.py create \
  --alertname HighBacktestFailureRate \
  --duration 2h \
  --comment "Maintenance window"

# List active silences
python3 scripts/manage_silences.py list --active-only

# Delete silence
python3 scripts/manage_silences.py delete --id <silence-id>
```

## Maintenance

### View Logs

```bash
# Prometheus logs
docker logs spock-prometheus

# Grafana logs
docker logs spock-grafana

# Alertmanager logs
docker logs spock-alertmanager

# Metrics exporter logs
tail -f ~/spock/monitoring/exporters/exporter.log
```

### Restart Services

```bash
# Restart all monitoring services
cd ~/spock/monitoring
docker-compose restart

# Restart individual service
docker-compose restart prometheus
docker-compose restart grafana

# Restart metrics exporter
pkill -f spock_exporter.py
python3 exporters/spock_exporter.py --port 8000 &
```

### Stop Monitoring

```bash
# Stop all services
cd ~/spock/monitoring
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Update Dashboards

1. Edit JSON files in `grafana/dashboards/`
2. Reload Grafana provisioning:
   ```bash
   docker-compose restart grafana
   ```

Or import dashboards via Grafana UI:
- Dashboards → Import → Upload JSON file

## Troubleshooting

### Exporter Not Starting

**Symptom**: `curl http://localhost:8000/metrics` fails

**Solutions**:
1. Check database path:
   ```bash
   ls -l /Users/13ruce/spock/data/spock_local.db
   ```

2. Check port availability:
   ```bash
   lsof -i :8000
   ```

3. Check exporter logs:
   ```bash
   python3 spock_exporter.py --port 8000 --verbose
   ```

### Prometheus Not Scraping

**Symptom**: "No data" in Grafana dashboards

**Solutions**:
1. Check Prometheus targets:
   - Open http://localhost:9090/targets
   - All targets should be "UP"

2. Verify exporter is running:
   ```bash
   curl http://localhost:8000/metrics | head
   ```

3. Check Prometheus logs:
   ```bash
   docker logs spock-prometheus
   ```

### Grafana Not Showing Data

**Symptom**: Empty dashboard panels

**Solutions**:
1. Check data source connection:
   - Grafana → Configuration → Data Sources
   - Test Prometheus connection

2. Check metric names in queries:
   - Panel → Edit → Query
   - Verify metric exists: `spock_ohlcv_rows_total`

3. Check time range:
   - Dashboard → Time range selector
   - Try "Last 6 hours"

### Alerts Not Firing

**Symptom**: No alerts despite metrics exceeding thresholds

**Solutions**:
1. Check alert rules:
   ```bash
   curl http://localhost:9090/api/v1/rules
   ```

2. Check Alertmanager:
   - Open http://localhost:9093
   - Check "Alerts" tab

3. Verify alert expression:
   - Prometheus → Alerts
   - Check "Pending" or "Firing" status

## Performance Considerations

### Metrics Collection Overhead

- **CPU**: ~1-2% for exporter
- **Memory**: ~50-100MB for exporter
- **Network**: ~1KB/sec for scraping
- **Database**: Minimal impact (read-only queries)

### Optimization Tips

1. **Increase scrape interval** for lower overhead:
   ```yaml
   scrape_interval: 30s  # Default: 15s
   ```

2. **Reduce retention** for less storage:
   ```yaml
   storage.tsdb.retention.time: 15d  # Default: 30d
   ```

3. **Disable unused metrics** in exporter code

## Security

### Access Control

1. **Change default passwords**:
   ```yaml
   # docker-compose.yml
   environment:
     - GF_SECURITY_ADMIN_PASSWORD=YOUR_STRONG_PASSWORD
   ```

2. **Enable HTTPS** for production:
   - Configure reverse proxy (nginx/caddy)
   - Add SSL certificates

3. **Restrict network access**:
   - Firewall rules for ports 3000, 9090, 9093
   - VPN or SSH tunnel for remote access

### Best Practices

- ✅ Regular backup of Grafana dashboards
- ✅ Version control for configuration files
- ✅ Monitor disk space usage
- ✅ Test alert notifications regularly
- ✅ Review and update alert thresholds

## Next Steps

After Week 1 Foundation setup:

1. **Week 2-3**: US Market Deployment
   - Verify US adapter metrics in dashboard
   - Validate data collection rate
   - Monitor API latency

2. **Week 4-6**: Asia Markets Deployment
   - Add CN/HK/JP specific panels
   - Configure region-specific alerts
   - Monitor cross-region performance

3. **Week 7**: Vietnam Market Deployment
   - Complete all 6 regional dashboards
   - Validate multi-region data quality

4. **Week 8**: Optimization
   - Fine-tune alert thresholds
   - Optimize metric collection
   - Performance benchmarking

## Support

For issues or questions:
1. Check logs (exporter, Prometheus, Grafana)
2. Review troubleshooting section
3. Consult deployment design: `docs/MULTI_REGION_DEPLOYMENT_DESIGN.md`

---

**Monitoring Infrastructure Version**: 1.0.0
**Last Updated**: 2025-10-15
**Status**: ✅ Production Ready
