# Guru AI Monitor: Tracing the Agentic State Machine
**Agents of SigNoz Hackathon 2026 Submission**

Guru AI Monitor is an autonomous, stateful Discord study agent engineered for rigorous academic preparation. Moving beyond standard stateless LLM wrappers, this system operates on an asynchronous event loop backed by an embedded SQLite state machine, with every execution path fully instrumented using OpenTelemetry and exported to SigNoz.

---

## System Architecture

    [ User / Discord Client ]
               │
               ▼  (Async Webhook / Event)
    [ Discord.py Event Loop ] ──(Span: discord.on_message)
               │
               ├──► [ SQLite State Machine ] ──(Span: sqlite-query-mistakes)
               │           │
               │           ▼  (Historical Error Context)
               ├──► [ Google Gemini LLM ]   ──(Span: gemini-llm-mistake-drill-generation)
               │                                 │ (Attributes: gen_ai.usage.input_tokens, llm.prompt.type)
               │                                 │
               ▼                                 ▼
    [ OTLP gRPC / HTTP Exporter ] ────────► [ SigNoz Observability Platform ]

---

## 🚀 Core Observability Features & Traces

### 1. The Elite Mistake Loop (AI + Database Orchestration)
When a student logs a mistake, the bot queries the SQLite database for past errors and pipes them directly into Gemini AI to generate a highly targeted revision drill.

**Proof of Observability:** The flame graph below exposes the "brain" of the agent, visualizing the exact transition from local database retrieval directly into the LLM payload generation.

![AI Mistake Loop](https://github.com/KshatraSanctum/Guru-AI-Monitor/raw/93237f3fe4e6eef07f92b0eb0c75cbe0bdf29c48/screenshots/ai_mistake_loop.png.png)
*Notice the custom attributes capturing the exact AI prompt type and response length.*

### 2. Tracking AI Latency (Active Recall Engine)
Generating real-time questions requires tracking external API latencies to ensure the bot remains responsive. By tracking `gen_ai.usage.completion_tokens`, this trace allows immediate identification of whether a delay is tied to model inference (high token output) or a local network bottleneck.

![AI Recall Latency](https://github.com/KshatraSanctum/Guru-AI-Monitor/raw/93237f3fe4e6eef07f92b0eb0c75cbe0bdf29c48/screenshots/ai_recall_latency.png.png)
*The trace above shows the latency of the Gemini API call during a standard active recall request.*

### 3. Database Logging (Mistake Capture)
When a user inputs a mistake in Discord, the bot instantly captures it and persists it into the SQLite database for long-term tracking.

![Database Log Mistake](https://github.com/KshatraSanctum/Guru-AI-Monitor/raw/93237f3fe4e6eef07f92b0eb0c75cbe0bdf29c48/screenshots/db_log_mistake.png.png)
*The trace above tracks the incoming Discord API webhook and the subsequent execution of the SQLite `INSERT` statement.*

### 4. Database Health & Progress Tracking
The bot tracks granular syllabus completion using SQLite. By injecting `study.subject` and `study.chapter` as custom span attributes, the telemetry elevates from standard database tracking to true Business Logic Observability.

![Success Trace](https://github.com/KshatraSanctum/Guru-AI-Monitor/raw/93237f3fe4e6eef07f92b0eb0c75cbe0bdf29c48/screenshots/success_trace.png.png)
*Proof of Observability (Success): Successfully logging a new chapter and tracking the exact execution time of the `INSERT` query.*

![Error Trace](https://github.com/KshatraSanctum/Guru-AI-Monitor/raw/93237f3fe4e6eef07f92b0eb0c75cbe0bdf29c48/screenshots/error_trace.png.png)
*Proof of Observability (Error Trapping): A simulated database lock gracefully caught and logged by the telemetry wrapper.*

---

## 🛠️ Tech Stack
* **Language:** Python
* **Interface:** Discord.py
* **AI:** Google Gemini API
* **Database:** SQLite
* **Observability:** OpenTelemetry (OTLP), SigNoz

  ## ⚙️ Quick Start & Reproduction

### 1. Clone the Repository
```bash
git clone https://github.com/KshatraSanctum/Guru-AI-Monitor.git
cd Guru-AI-Monitor
```
### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
### 3. Configure Environment Variables
Create a .env file in the root directory and add your credentials:
```bash
DISCORD_TOKEN="your_discord_bot_token"
GEMINI_API_KEY="your_google_gemini_api_key"
OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
```
### 4. Run the Agent 
```bash
python bot.py
```

