# Alert Notification Setup Guide

Complete guide for configuring alert notifications in the Quant Platform monitoring system.

## Table of Contents

1. [Overview](#overview)
2. [Environment Variables Setup](#environment-variables-setup)
3. [Slack Configuration](#slack-configuration)
4. [Email Configuration](#email-configuration)
5. [Webhook Configuration](#webhook-configuration)
6. [Testing Notifications](#testing-notifications)
7. [Alert Management](#alert-management)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Quant Platform supports multiple notification channels configured via environment variables:

- **Email**: SMTP-based email notifications (Gmail, Outlook, custom SMTP)
- **Slack**: Real-time alerts to Slack channels via webhooks
- **Webhook**: Custom HTTP endpoints for integration with other systems
- **Console**: Alertmanager logs (always active)

### Alert Priority (Balanced Mode)

- **Critical Alerts** (🚨): Email + Slack + Webhook + Console (repeat: 30min)
- **Warning Alerts** (⚠️): Slack + Webhook + Console (repeat: 2h)
- **Info Alerts** (ℹ️): Suppressed (console only)

---

## Environment Variables Setup

### 1. Copy Example File

```bash
cd /Users/13ruce/spock/monitoring
cp .env.alertmanager.example .env.alertmanager
```

### 2. Edit `.env.alertmanager`

```bash
# Use your preferred text editor
vim .env.alertmanager
# or
nano .env.alertmanager
# or
code .env.alertmanager
```

### 3. Configure Credentials

See sections below for specific setup instructions for each notification channel.

---

## Slack Configuration

### Step 1: Create Slack App

1. Go to [Slack API](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From scratch"**
3. Enter App Name: `Quant Platform Alerts`
4. Select your workspace

### Step 2: Enable Incoming Webhooks

1. In your app settings, go to **"Incoming Webhooks"**
2. Toggle **"Activate Incoming Webhooks"** to **On**
3. Click **"Add New Webhook to Workspace"**

### Step 3: Create Channels

Create the following Slack channels in your workspace:

- `#quant-critical-alerts` - Critical alerts (Email + Slack)
- `#quant-warnings` - Warning alerts (Slack only)
- `#spock-critical-alerts` - Legacy Spock critical alerts
- `#spock-data-quality` - Legacy data quality alerts
- `#spock-api-health` - Legacy API health alerts
- `#spock-trading` - Legacy trading alerts

### Step 4: Configure Webhook for Each Channel

For **each channel**, repeat:

1. Click **"Add New Webhook to Workspace"**
2. Select the channel (e.g., `#quant-critical-alerts`)
3. Copy the Webhook URL (format: `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`)

### Step 5: Set Environment Variable

In `.env.alertmanager`:

```bash
# Slack Webhook URL (primary channel - quant-critical-alerts)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Note**: The example configuration uses a single webhook URL. To use different webhooks per channel, modify `alertmanager.yml` to specify `api_url` in each Slack receiver.

### Example Slack Alert

```
🚨 CRITICAL | HighBacktestFailureRate

*Alert Category:* `backtest_performance`
*Severity:* `critical`
*Status:* 🔥 *FIRING*

---
*Summary:* High backtest failure rate for strategy MomentumValue

*Details:*
Backtest failure rate is 35.2% for strategy MomentumValue (threshold: 30%)

*Strategy:* `MomentumValue`
*Engine:* `backtrader`

*Started:* 2025-10-22 10:15:30 KST

📊 View in Prometheus | 📈 View in Grafana Dashboard

*Alert Count:* 1 alert(s)
```

---

## Email Configuration

### Option A: Gmail (Recommended for Development)

#### Step 1: Enable 2-Factor Authentication

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **"2-Step Verification"**

#### Step 2: Generate App Password

1. Go to [App Passwords](https://myaccount.google.com/apppasswords)
2. Select **"Mail"** and **"Other (Custom name)"**
3. Enter: `Quant Platform Alerts`
4. Click **"Generate"**
5. Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)

#### Step 3: Configure Environment Variables

In `.env.alertmanager`:

```bash
# Gmail SMTP Configuration
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx  # App password (16 chars)
EMAIL_TO=team@example.com,admin@example.com  # Comma-separated recipients
```

### Option B: Outlook/Microsoft 365

In `.env.alertmanager`:

```bash
EMAIL_SMTP_HOST=smtp-mail.outlook.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your-email@outlook.com
EMAIL_PASSWORD=your-password
EMAIL_TO=team@example.com
```

### Option C: Custom SMTP Server

In `.env.alertmanager`:

```bash
EMAIL_SMTP_HOST=smtp.yourcompany.com
EMAIL_SMTP_PORT=587  # or 465 for SSL
EMAIL_USERNAME=alerts@yourcompany.com
EMAIL_PASSWORD=your-smtp-password
EMAIL_TO=team@yourcompany.com,ops@yourcompany.com
```

### Email Template Example

**Subject**: 🚨 [CRITICAL] Quant Platform: HighBacktestFailureRate

**Body** (HTML formatted):

- Alert header with severity badge (red for critical, yellow for warning)
- Summary and detailed description
- Strategy name, engine, factor (if applicable)
- Start/end timestamps
- Recommendation (if available)
- Links to Prometheus and Grafana
- Alert summary footer

---

## Webhook Configuration

### Use Case: Custom Integrations

Send alerts to custom endpoints for:
- PagerDuty integration
- Discord bot
- Custom monitoring dashboards
- Incident management systems
- Logging aggregators (e.g., Datadog, New Relic)

### Step 1: Setup Your Webhook Endpoint

Your endpoint should:
- Accept POST requests
- Handle JSON payloads
- Return HTTP 200 on success

### Step 2: Configure Environment Variable

In `.env.alertmanager`:

```bash
# Custom Webhook URL
CUSTOM_WEBHOOK_URL=https://your-webhook-endpoint.com/alerts
```

### Step 3: Webhook Payload Format

Your endpoint will receive JSON in this format:

```json
{
  "status": "firing",
  "alert_count": 1,
  "firing_count": 1,
  "resolved_count": 0,
  "common_labels": {
    "alertname": "HighBacktestFailureRate",
    "severity": "critical",
    "category": "backtest_performance"
  },
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighBacktestFailureRate",
        "severity": "critical",
        "category": "backtest_performance",
        "strategy_name": "MomentumValue",
        "engine": "backtrader"
      },
      "annotations": {
        "summary": "High backtest failure rate for strategy MomentumValue",
        "description": "Backtest failure rate is 35.2% for strategy MomentumValue (threshold: 30%)",
        "recommendation": "Check backtest configuration and data availability"
      },
      "starts_at": "2025-10-22T10:15:30+09:00",
      "generator_url": "http://localhost:9090/graph?g0.expr=..."
    }
  ],
  "external_url": "http://localhost:9093",
  "timestamp": "2025-10-22T10:15:30+09:00"
}
```

### Example Webhook Receiver (Python Flask)

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/alerts', methods=['POST'])
def receive_alert():
    payload = request.json

    # Process alert
    status = payload['status']
    alert_count = payload['alert_count']

    for alert in payload['alerts']:
        alertname = alert['labels']['alertname']
        severity = alert['labels']['severity']
        summary = alert['annotations']['summary']

        # Your custom logic here
        print(f"[{severity.upper()}] {alertname}: {summary}")

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
```

---

## Testing Notifications

### Step 1: Apply Configuration

```bash
cd /Users/13ruce/spock/monitoring

# Reload Alertmanager configuration
docker-compose exec alertmanager kill -HUP 1

# Or restart Alertmanager
docker-compose restart alertmanager
```

### Step 2: Run Test Script

```bash
# Test all notification channels
python3 scripts/test_alerts.py --all

# Test specific channel
python3 scripts/test_alerts.py --channel slack
python3 scripts/test_alerts.py --channel email
python3 scripts/test_alerts.py --channel webhook

# Test specific alert
python3 scripts/test_alerts.py --alert HighBacktestFailureRate
```

### Step 3: Verify Notifications

1. **Slack**: Check `#quant-critical-alerts` and `#quant-warnings` channels
2. **Email**: Check inbox for `EMAIL_TO` recipients
3. **Webhook**: Check your webhook endpoint logs
4. **Console**: Check Alertmanager logs:
   ```bash
   docker-compose logs -f alertmanager
   ```

### Step 4: Validate Alertmanager Status

```bash
# Check Alertmanager health
curl http://localhost:9093/api/v2/status

# View active alerts
curl http://localhost:9093/api/v2/alerts

# View silences
curl http://localhost:9093/api/v2/silences
```

---

## Alert Management

### Silencing Alerts

**Use Case**: Suppress alerts during maintenance windows or known issues.

#### Method 1: Via Script

```bash
# Silence specific alert for 2 hours
python3 scripts/manage_silences.py create \
  --alertname HighBacktestFailureRate \
  --duration 2h \
  --comment "Maintenance window"

# Silence all critical alerts for 1 hour
python3 scripts/manage_silences.py create \
  --severity critical \
  --duration 1h \
  --comment "Emergency maintenance"

# List active silences
python3 scripts/manage_silences.py list

# Delete silence
python3 scripts/manage_silences.py delete --id <silence-id>
```

#### Method 2: Via Alertmanager UI

1. Open [Alertmanager UI](http://localhost:9093)
2. Click **"New Silence"**
3. Add matchers (e.g., `alertname="HighBacktestFailureRate"`)
4. Set duration and comment
5. Click **"Create"**

#### Method 3: Via API

```bash
# Create silence
curl -X POST http://localhost:9093/api/v2/silences \
  -H "Content-Type: application/json" \
  -d '{
    "matchers": [
      {"name": "alertname", "value": "HighBacktestFailureRate", "isRegex": false}
    ],
    "startsAt": "2025-10-22T10:00:00Z",
    "endsAt": "2025-10-22T12:00:00Z",
    "createdBy": "admin",
    "comment": "Maintenance window"
  }'
```

### Viewing Alerts

#### Prometheus UI

1. Open [Prometheus](http://localhost:9090/alerts)
2. View active/pending/inactive alerts
3. Check alert rule expressions

#### Grafana Dashboard

1. Open [Grafana](http://localhost:3000)
2. Navigate to **"Quant Platform Overview"** dashboard
3. View alert status panels

#### Alertmanager UI

1. Open [Alertmanager](http://localhost:9093)
2. View grouped alerts
3. Filter by severity, category, status

---

## Troubleshooting

### Issue: Slack notifications not working

**Symptoms**:
- Alerts appear in Alertmanager but not in Slack
- Alertmanager logs show webhook errors

**Solutions**:

1. **Verify webhook URL**:
   ```bash
   # Test webhook URL directly
   curl -X POST ${SLACK_WEBHOOK_URL} \
     -H "Content-Type: application/json" \
     -d '{"text": "Test message from Quant Platform"}'
   ```

2. **Check Alertmanager logs**:
   ```bash
   docker-compose logs alertmanager | grep -i slack
   ```

3. **Verify channel exists** in Slack workspace

4. **Check webhook permissions** in Slack App settings

---

### Issue: Email notifications not working

**Symptoms**:
- Email not received
- Alertmanager logs show SMTP errors

**Solutions**:

1. **Verify SMTP credentials**:
   ```bash
   # Test SMTP connection (Gmail example)
   telnet smtp.gmail.com 587
   ```

2. **Check App Password** (Gmail):
   - Make sure 2FA is enabled
   - Generate new App Password if needed

3. **Check spam folder** for test emails

4. **Verify EMAIL_TO addresses** are correct

5. **Check Alertmanager logs**:
   ```bash
   docker-compose logs alertmanager | grep -i email
   ```

6. **Test with simple SMTP script**:
   ```python
   import smtplib
   from email.mime.text import MIMEText

   msg = MIMEText("Test email")
   msg['Subject'] = 'Test'
   msg['From'] = 'your-email@gmail.com'
   msg['To'] = 'recipient@example.com'

   with smtplib.SMTP('smtp.gmail.com', 587) as server:
       server.starttls()
       server.login('your-email@gmail.com', 'app-password')
       server.send_message(msg)
   ```

---

### Issue: Webhook endpoint not receiving alerts

**Symptoms**:
- Webhook endpoint logs show no incoming requests
- Alertmanager logs show connection errors

**Solutions**:

1. **Verify endpoint is accessible**:
   ```bash
   curl -X POST ${CUSTOM_WEBHOOK_URL} \
     -H "Content-Type: application/json" \
     -d '{"test": "message"}'
   ```

2. **Check firewall rules** if using external endpoint

3. **Verify endpoint returns HTTP 200** on success

4. **Check Alertmanager logs**:
   ```bash
   docker-compose logs alertmanager | grep -i webhook
   ```

5. **Test with local webhook receiver**:
   ```bash
   # Start simple webhook receiver
   python3 -m http.server 5001

   # Set CUSTOM_WEBHOOK_URL=http://host.docker.internal:5001
   # Restart Alertmanager and test
   ```

---

### Issue: Environment variables not loaded

**Symptoms**:
- Alertmanager shows `${VARIABLE_NAME}` in configuration
- Template errors in logs

**Solutions**:

1. **Verify .env.alertmanager exists**:
   ```bash
   ls -la /Users/13ruce/spock/monitoring/.env.alertmanager
   ```

2. **Check docker-compose.yml** has env_file mount:
   ```yaml
   alertmanager:
     env_file:
       - .env.alertmanager
   ```

3. **Restart Alertmanager**:
   ```bash
   docker-compose restart alertmanager
   ```

4. **Verify environment variables loaded**:
   ```bash
   docker-compose exec alertmanager env | grep EMAIL
   ```

---

### Issue: Alerts not firing

**Symptoms**:
- Metrics show high values but no alerts
- Prometheus shows alerts as inactive

**Solutions**:

1. **Check alert rule syntax** in `prometheus/quant_alerts.yml`

2. **Verify Prometheus loaded rules**:
   ```bash
   curl http://localhost:9090/api/v1/rules
   ```

3. **Check alert rule evaluation**:
   - Open [Prometheus](http://localhost:9090/alerts)
   - Check if rule expression returns data

4. **Reload Prometheus configuration**:
   ```bash
   docker-compose exec prometheus kill -HUP 1
   ```

5. **Check `for` duration** in alert rules:
   ```yaml
   for: 10m  # Alert must be true for 10 minutes
   ```

---

### Issue: Too many alerts (alert storm)

**Symptoms**:
- Hundreds of alerts firing simultaneously
- Notification channels overwhelmed

**Solutions**:

1. **Use alert silences** for known issues:
   ```bash
   python3 scripts/manage_silences.py create \
     --category backtest_performance \
     --duration 1h
   ```

2. **Check inhibit rules** in `alertmanager.yml`:
   - Critical alerts suppress warnings
   - API down suppresses dependent alerts

3. **Adjust alert thresholds** in `prometheus/quant_alerts.yml`

4. **Increase `group_interval`** in `alertmanager.yml`:
   ```yaml
   route:
     group_interval: 10m  # Batch alerts for 10 minutes
   ```

---

## Security Best Practices

### 1. Protect Credentials

- ✅ **DO**: Use environment variables for all credentials
- ✅ **DO**: Add `.env.alertmanager` to `.gitignore`
- ❌ **DON'T**: Commit credentials to Git
- ❌ **DON'T**: Hardcode credentials in configuration files

### 2. Secure SMTP Passwords

- Use **App Passwords** instead of account passwords (Gmail, Outlook)
- Rotate passwords regularly (every 90 days)
- Use dedicated alerting email accounts

### 3. Protect Webhook URLs

- Use HTTPS endpoints only
- Implement webhook signature verification
- Rotate webhook URLs if compromised

### 4. Access Control

- Restrict Alertmanager UI access (use firewall, VPN, or authentication)
- Limit Slack webhook permissions to specific channels
- Use least-privilege principle for email accounts

### 5. Monitoring

- Monitor Alertmanager logs for suspicious activity
- Set up alerts for failed notification attempts
- Review active silences regularly

---

## Additional Resources

### Official Documentation

- [Prometheus Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Alert Notification Templates](https://prometheus.io/docs/alerting/latest/notification_examples/)
- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)

### Quant Platform Docs

- `monitoring/prometheus/quant_alerts.yml` - Alert rule definitions
- `monitoring/alertmanager/templates/quant_alerts.tmpl` - Notification templates
- `monitoring/grafana/dashboards/` - Grafana dashboards

### Support

For issues or questions:
1. Check Alertmanager logs: `docker-compose logs alertmanager`
2. Verify Prometheus rules: http://localhost:9090/alerts
3. Test notifications: `python3 scripts/test_alerts.py`
4. Review this guide for troubleshooting steps

---

**Last Updated**: 2025-10-22
**Version**: 1.0.0
**Status**: Production Ready
