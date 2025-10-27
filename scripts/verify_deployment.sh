#!/bin/bash
echo "======================================================================="
echo "Spock Trading System - Deployment Verification"
echo "======================================================================="

# Check Python version
echo -e "\n1. Python Version:"
python3 --version

# Check virtual environment
echo -e "\n2. Virtual Environment:"
which python3

# Check dependencies
echo -e "\n3. Critical Dependencies:"
pip list | grep -E 'pandas|numpy|psutil'

# Check database
echo -e "\n4. Database:"
ls -lh data/spock_local.db 2>/dev/null && echo "✅ Database exists" || echo "❌ Database not found"

# Check credentials
echo -e "\n5. Credentials:"
[ -f .env ] && echo "✅ .env file exists" || echo "❌ .env file not found"

# Check metrics directory
echo -e "\n6. Metrics Directory:"
ls -ld metrics_reports/ 2>/dev/null && echo "✅ Metrics directory exists" || echo "❌ Metrics directory not found"

# Test metrics collection
echo -e "\n7. Metrics Collection Test:"
python3 -c "from modules.metrics_collector import MetricsCollector; \
collector = MetricsCollector(); \
metrics = collector.collect_all_metrics(); \
print(f'✅ Metrics collected: {len(metrics)} categories')" 2>&1

# Test alert system
echo -e "\n8. Alert System Test:"
python3 -c "from modules.alert_system import AlertSystem; \
alert_system = AlertSystem(); \
print('✅ Alert system initialized')" 2>&1

# Check monitoring dashboard
echo -e "\n9. Monitoring Dashboard:"
[ -f monitoring/dashboard.html ] && echo "✅ Dashboard file exists" || echo "❌ Dashboard not found"

# Check data quality validation
echo -e "\n10. Data Quality Validation:"
[ -f scripts/validate_data_quality.py ] && echo "✅ Validation script exists" || echo "❌ Validation script not found"

echo -e "\n======================================================================="
echo "Deployment Verification Complete"
echo "======================================================================="
