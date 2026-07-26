# 🔍 Guru-AI-Monitor: Distributed Telemetry & Observability Report

This document outlines the OpenTelemetry (OTel) instrumentation architecture, span waterfalls, and metric emission standards implemented in **Guru-AI-Monitor**.

---

## 🌊 End-to-End Trace Waterfall Analysis (`!review_mistakes`)

When a student triggers an active-recall review session, the OTLP exporter captures a multi-service trace. Below is the representative trace waterfall captured during a high-latency LLM fallback event:

```json
{
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "spans": [
    {
      "name": "discord-command-review-mistakes",
      "span_id": "00f067aa0ba902b7",
      "duration_ms": 1240,
      "attributes": {
        "user.id": "8472938471928",
        "study.subject": "Physics",
        "study.chapter": "Rotational Motion"
      },
      "status": "STATUS_CODE_OK"
    },
    {
      "name": "sqlite-query-mistakes",
      "parent_span_id": "00f067aa0ba902b7",
      "duration_ms": 12,
      "attributes": {
        "db.system": "sqlite",
        "db.operation": "SELECT",
        "mistake.count_retrieved": 5
      },
      "status": "STATUS_CODE_OK"
    },
    {
      "name": "gemini-llm-mistake-drill-generation",
      "parent_span_id": "00f067aa0ba902b7",
      "duration_ms": 1185,
      "attributes": {
        "llm.model.requested": "gemini-1.5-flash",
        "llm.model.fallback_triggered": true,
        "llm.response.length": 1420
      },
      "status": "STATUS_CODE_OK"
    }
  ]
}