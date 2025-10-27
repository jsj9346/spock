# Prometheus Query Reference

Quick reference for querying FastAPI metrics in Prometheus.

## HTTP Request Metrics

### Request Duration Percentiles

**P50 (Median) Latency**:
```promql
histogram_quantile(0.5, rate(http_request_duration_seconds_bucket[5m]))
```

**P95 Latency**:
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

**P99 Latency**:
```promql
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
```

**P50 by Endpoint**:
```promql
histogram_quantile(0.5,
  rate(http_request_duration_seconds_bucket[5m])
) by (endpoint)
```

**P95 by Endpoint and Method**:
```promql
histogram_quantile(0.95,
  rate(http_request_duration_seconds_bucket[5m])
) by (endpoint, method)
```

### Request Rate

**Requests per second (overall)**:
```promql
rate(http_requests_total[5m])
```

**Requests per second by endpoint**:
```promql
sum by (endpoint) (rate(http_requests_total[5m]))
```

**Requests per second by status code**:
```promql
sum by (status_code) (rate(http_requests_total[5m]))
```

### Error Rate

**4xx Error Rate**:
```promql
sum(rate(http_requests_total{status_code=~"4.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

**5xx Error Rate**:
```promql
sum(rate(http_requests_total{status_code=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

**Error Rate by Endpoint**:
```promql
sum by (endpoint) (rate(http_requests_total{status_code=~"[45].."}[5m]))
/
sum by (endpoint) (rate(http_requests_total[5m]))
```

### Active Requests

**Current active requests**:
```promql
http_requests_in_progress
```

**Active requests by endpoint**:
```promql
sum by (endpoint) (http_requests_in_progress)
```

**Max concurrent requests (last 5 min)**:
```promql
max_over_time(http_requests_in_progress[5m])
```

## Average Response Time

**Average latency (last 5 min)**:
```promql
rate(http_request_duration_seconds_sum[5m])
/
rate(http_request_duration_seconds_count[5m])
```

**Average latency by endpoint**:
```promql
sum by (endpoint) (rate(http_request_duration_seconds_sum[5m]))
/
sum by (endpoint) (rate(http_request_duration_seconds_count[5m]))
```

## Request Volume

**Total requests in last hour**:
```promql
sum(increase(http_requests_total[1h]))
```

**Request distribution by endpoint (last hour)**:
```promql
topk(10, sum by (endpoint) (increase(http_requests_total[1h])))
```

## Slowest Endpoints

**Top 10 slowest endpoints (P95)**:
```promql
topk(10,
  histogram_quantile(0.95,
    rate(http_request_duration_seconds_bucket[5m])
  ) by (endpoint)
)
```

## Usage Examples

### Grafana Dashboard Panels

**Request Rate Panel**:
- Query: `sum(rate(http_requests_total[5m]))`
- Panel Type: Graph
- Legend: "Requests/sec"

**Latency Percentiles Panel**:
- Query 1: `histogram_quantile(0.5, rate(http_request_duration_seconds_bucket[5m]))` (P50)
- Query 2: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` (P95)
- Query 3: `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))` (P99)
- Panel Type: Graph
- Legend: "{{quantile}}"

**Error Rate Panel**:
- Query: `sum(rate(http_requests_total{status_code=~"[45].."}[5m])) / sum(rate(http_requests_total[5m]))`
- Panel Type: Stat
- Format: Percent (0-1)
- Thresholds: Green (< 0.01), Yellow (0.01-0.05), Red (> 0.05)

**Active Requests Panel**:
- Query: `sum(http_requests_in_progress)`
- Panel Type: Stat
- Legend: "Active Requests"

## Alerting Rules

### High Error Rate Alert
```yaml
- alert: HighErrorRate
  expr: |
    sum(rate(http_requests_total{status_code=~"5.."}[5m]))
    /
    sum(rate(http_requests_total[5m])) > 0.05
  for: 5m
  annotations:
    summary: "High error rate detected"
    description: "Error rate is {{ $value | humanizePercentage }}"
```

### High Latency Alert
```yaml
- alert: HighLatencyP95
  expr: |
    histogram_quantile(0.95,
      rate(http_request_duration_seconds_bucket[5m])
    ) > 1.0
  for: 5m
  annotations:
    summary: "High P95 latency detected"
    description: "P95 latency is {{ $value }}s"
```

### High Request Volume Alert
```yaml
- alert: HighRequestVolume
  expr: |
    sum(rate(http_requests_total[5m])) > 100
  for: 5m
  annotations:
    summary: "High request volume detected"
    description: "Request rate is {{ $value }} req/sec"
```

## Access Points

- **Prometheus UI**: http://localhost:9090
- **Prometheus Graph**: http://localhost:9090/graph
- **Prometheus Targets**: http://localhost:9090/targets
- **Grafana**: http://localhost:3000 (admin/spock2025)

## References

- Prometheus Query Language: https://prometheus.io/docs/prometheus/latest/querying/basics/
- PromQL Functions: https://prometheus.io/docs/prometheus/latest/querying/functions/
- Histogram Quantiles: https://prometheus.io/docs/practices/histograms/
