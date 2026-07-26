import os
from dotenv import load_dotenv

load_dotenv()  # Loads variables from your local .env file automatically
import discord
from discord.ext import commands
import sqlite3
import datetime
import google.generativeai as genai
import asyncio

# --- OPENTELEMETRY / SIGNOZ SETUP ---
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# 1. Define OTel Resource for SigNoz
resource = Resource.create(attributes={
    "service.name": "guru-ai-monitor",
    "service.version": "1.0.0",
    "deployment.environment": "hackathon"
})

provider = TracerProvider(resource=resource)
trace.set_tracer_provider(provider)

# 2. Connect to SigNoz OTLP endpoint (default local or via environment)
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Get our tracer instance
tracer = trace.get_tracer("guru.ai.monitor.tracer")
# ------------------------------------
# --- OPENTELEMETRY METRICS SETUP ---
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=5000)

meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
meter = meter_provider.get_meter("guru.ai.monitor.meter")

# Custom Hackathon Metrics Counters
recall_counter = meter.create_counter(
    name="guru_recall_requests_total",
    description="Total number of active recall sessions requested",
    unit="1"
)

# --- AI SETUP ---
# 1. Replace with your actual Gemini API Key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("🔍 Finding an active, unrestricted AI model...")
model = None

# List of modern models to try in order
candidate_models = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']

for m_name in candidate_models:
    try:
        test_model = genai.GenerativeModel(m_name)
        # Test generation immediately to verify access
        test_model.generate_content("Hello")
        model = test_model
        print(f"✅ Success! Locked in model: {m_name}")
        break
    except Exception:
        continue

if not model:
    # Fallback to whatever the API lists first if manual candidates fail
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            try:
                test_model = genai.GenerativeModel(m.name)
                test_model.generate_content("Hello")
                model = test_model
                print(f"✅ Success! Locked in fallback model: {m.name}")
                break
            except Exception:
                continue

if not model:
    print("❌ Critical Error: No working Gemini models found for this API key.")

# --- DATABASE SETUP & OTEL TRACING ---
DB_NAME = "guru_memory.db"

def init_db():
    with tracer.start_as_current_span("sqlite-database-init-mistake-loop") as span:
        span.set_attribute("db.system", "sqlite")
        span.set_attribute("db.name", DB_NAME)
        
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS study_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    topic TEXT,
                    question TEXT,
                    status TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chapter_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT,
                    chapter_name TEXT,
                    completion_date TEXT,
                    next_recall_date TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS topic_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT UNIQUE,
                    mastery_level TEXT,
                    revision_count INTEGER,
                    last_reviewed TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mistake_bank (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT,
                    chapter TEXT,
                    question TEXT,
                    timestamp TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS syllabus_tracker (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    subject TEXT,
                    chapter TEXT,
                    exercise_name TEXT,
                    total_questions INTEGER,
                    completed_questions INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'Pending'
                )
            ''')
            
            conn.commit()
            conn.close()
            print("🔗 Advanced Mistake-Loop & Granular Syllabus Database Initialized with OTel Tracing.")
            span.set_status(trace.StatusCode.OK)
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            print(f"❌ Database error: {e}")

init_db()

# --- BOT SETUP & OTEL TRACING ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    with tracer.start_as_current_span("discord-bot-ready") as span:
        span.set_attribute("bot.username", str(bot.user))
        print(f'🟢 {bot.user} is online!')
        print('🗄️ SQLite Database connected.')
        print('🧠 Gemini AI brain connected and ready to generate quizzes.')

# Command 1: Log a chapter (Traced with SQLite OTel Spans)
@bot.command()
async def done(ctx, subject: str, *, chapter_name: str):
    with tracer.start_as_current_span("discord-command-done") as span:
        span.set_attribute("user.id", str(ctx.author.id))
        span.set_attribute("study.subject", subject)
        span.set_attribute("study.chapter", chapter_name)
        
        today = datetime.date.today()
        recall_date = today + datetime.timedelta(days=10) 
        
        try:
            with tracer.start_as_current_span("sqlite-insert-chapter") as db_span:
                conn = sqlite3.connect('guru_memory.db')
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO chapter_progress (subject, chapter_name, completion_date, next_recall_date)
                    VALUES (?, ?, ?, ?)
                ''', (subject, chapter_name, str(today), str(recall_date)))
                conn.commit()
                conn.close()
                db_span.set_status(trace.StatusCode.OK)
                
            await ctx.send(f"✅ **Logged:** {subject} - {chapter_name}. \n📅 *I will test you on this via active recall on {recall_date}.*")
            span.set_status(trace.StatusCode.OK)
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            await ctx.send(f"⚠️ Error logging chapter to database.")

# Multi-Topic Status Command
@bot.command()
async def status(ctx, *, topic: str):
    """Check your multi-topic study state and mastery level, fully traced via OTel"""
    with tracer.start_as_current_span("discord-command-status") as span:
        span.set_attribute("user.id", str(ctx.author.id))
        span.set_attribute("study.topic", topic)
        
        try:
            with tracer.start_as_current_span("sqlite-query-topic-state") as db_span:
                conn = sqlite3.connect('guru_memory.db')
                cursor = conn.cursor()
                cursor.execute("SELECT mastery_level, revision_count, last_reviewed FROM topic_states WHERE topic = ?", (topic,))
                row = cursor.fetchone()
                conn.close()
                db_span.set_status(trace.StatusCode.OK)
            
            if row:
                mastery, revisions, last_revised = row
                await ctx.send(f"📊 **Topic Report: `{topic}`**\n- **Mastery Level:** {mastery}\n- **Total Revisions:** {revisions}\n- **Last Reviewed:** {last_revised}")
            else:
                await ctx.send(f"⚠️ No active data found for topic: `{topic}`. Start a session using `!recall {topic}` or log progress with `!done`!")
                
            span.set_status(trace.StatusCode.OK)
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            await ctx.send(f"⚠️ Error retrieving topic stats.")
#Catching error
@bot.command(name="simulate_fault")
async def simulate_fault(ctx, fault_type: str = "db_lock"):
    """Simulates a database failure to test OpenTelemetry error tracing."""
    with tracer.start_as_current_span("discord-command-simulate-fault") as span:
        span.set_attribute("user.id", str(ctx.author.id))
        
        if fault_type == "db_lock":
            try:
                with tracer.start_as_current_span("sqlite-query-execution") as db_span:
                    # Simulate a crash
                    error_msg = "OperationalError: database is locked"
                    raise Exception(error_msg)
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.StatusCode.ERROR, str(e))
                await ctx.send("💥 **Simulated Fault:** Database lock error captured in telemetry!")

# --- GRANULAR SYLLABUS & PROGRESS ENGINE (STEPS 1 - 4) ---

@bot.command()
async def setup_syllabus(ctx, subject: str = "General", chapter: str = "General", exercise: str = "General", total_q: int = 0):
    """Sets up or updates an exercise in your syllabus tracker with total question counts"""
    with tracer.start_as_current_span("discord-command-setup-syllabus") as span:
        span.set_attribute("user.id", str(ctx.author.id))
        span.set_attribute("study.subject", subject)
        span.set_attribute("study.chapter", chapter)
        
        try:
            with tracer.start_as_current_span("sqlite-upsert-syllabus") as db_span:
                conn = sqlite3.connect('guru_memory.db')
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, completed_questions FROM syllabus_tracker WHERE user_id = ? AND subject = ? AND chapter = ? AND exercise_name = ?",
                    (str(ctx.author.id), subject, chapter, exercise)
                )
                row = cursor.fetchone()
                
                if row:
                    cursor.execute(
                        "UPDATE syllabus_tracker SET total_questions = ? WHERE id = ?",
                        (total_q, row[0])
                    )
                    action = "Updated"
                else:
                    cursor.execute(
                        "INSERT INTO syllabus_tracker (user_id, subject, chapter, exercise_name, total_questions) VALUES (?, ?, ?, ?, ?)",
                        (str(ctx.author.id), subject, chapter, exercise, total_q)
                    )
                    action = "Registered"
                
                conn.commit()
                conn.close()
                db_span.set_status(trace.StatusCode.OK)
                
            await ctx.send(f"🎯 **Syllabus {action}:** [{subject}] `{chapter}` -> **{exercise}** set to **{total_q} total questions**.")
            span.set_status(trace.StatusCode.OK)
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            await ctx.send("❌ Error updating syllabus tracker.")

@bot.command()
async def progress(ctx, subject: str, chapter: str, exercise: str, solved_count: int):
    """Logs solved questions for a specific exercise and tracks completion percentage"""
    with tracer.start_as_current_span("discord-command-log-progress") as span:
        span.set_attribute("user.id", str(ctx.author.id))
        span.set_attribute("study.subject", subject)
        
        try:
            with tracer.start_as_current_span("sqlite-update-progress") as db_span:
                conn = sqlite3.connect('guru_memory.db')
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, total_questions, completed_questions FROM syllabus_tracker WHERE user_id = ? AND subject = ? AND chapter = ? AND exercise_name = ?",
                    (str(ctx.author.id), subject, chapter, exercise)
                )
                row = cursor.fetchone()
                
                if not row:
                    await ctx.send(f"⚠️ Exercise not found! Setup first using `!setup_syllabus {subject} {chapter} {exercise} <total_questions>`")
                    conn.close()
                    return
                
                row_id, total, current_completed = row
                new_completed = current_completed + solved_count
                status_val = "Completed" if new_completed >= total else "In Progress"
                
                cursor.execute(
                    "UPDATE syllabus_tracker SET completed_questions = ?, status = ? WHERE id = ?",
                    (new_completed, status_val, row_id)
                )
                conn.commit()
                conn.close()
                db_span.set_status(trace.StatusCode.OK)
                
            percentage = min(100.0, (new_completed / total) * 100)
            await ctx.send(f"📈 **Progress Updated!** [{subject}] {chapter} - {exercise}\n- **Completed:** {new_completed}/{total} ({percentage:.1f}%)\n- **Status:** {status_val}")
            span.set_status(trace.StatusCode.OK)
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            await ctx.send("❌ Error saving exercise progress.")

@bot.command()
async def syllabus_status(ctx, subject: str = None):
    """Views overall completion metrics across chapters and exercises"""
    with tracer.start_as_current_span("discord-command-syllabus-status") as span:
        try:
            conn = sqlite3.connect('guru_memory.db')
            cursor = conn.cursor()
            if subject:
                cursor.execute("SELECT chapter, exercise_name, total_questions, completed_questions, status FROM syllabus_tracker WHERE user_id = ? AND subject = ?", (str(ctx.author.id), subject))
            else:
                cursor.execute("SELECT subject, chapter, exercise_name, total_questions, completed_questions, status FROM syllabus_tracker WHERE user_id = ?", (str(ctx.author.id),))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                await ctx.send("📂 No syllabus data found. Use `!setup_syllabus` to map out your coursework!")
                return
                
            output = "📊 **Granular Syllabus Tracker Status:**\n"
            for row in rows:
                if subject:
                    chap, ex, tot, comp, stat = row
                    output += f"- **{chap}** | `{ex}`: {comp}/{tot} ({stat})\n"
                else:
                    sub, chap, ex, tot, comp, stat = row
                    output += f"- **[{sub}] {chap}** | `{ex}`: {comp}/{tot} ({stat})\n"
                    
            await ctx.send(output[:1950])
            span.set_status(trace.StatusCode.OK)
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            await ctx.send("⚠️ Error fetching syllabus tracking data.")

# --- ELITE MISTAKE LOOP ENGINE ---
@bot.command()
async def mistake(ctx, subject: str, chapter: str, *, bad_question: str):
    """Logs a question you got wrong into the Mistake Bank for targeted re-testing"""
    with tracer.start_as_current_span("discord-command-log-mistake") as span:
        span.set_attribute("user.id", str(ctx.author.id))
        span.set_attribute("study.subject", subject)
        span.set_attribute("study.chapter", chapter)
        
        try:
            with tracer.start_as_current_span("sqlite-insert-mistake") as db_span:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                timestamp = datetime.datetime.now().isoformat()
                cursor.execute(
                    "INSERT INTO mistake_bank (subject, chapter, question, timestamp) VALUES (?, ?, ?, ?)",
                    (subject, chapter, bad_question, timestamp)
                )
                conn.commit()
                conn.close()
                db_span.set_status(trace.StatusCode.OK)
                
            await ctx.send(f"📌 **Logged to Mistake Bank:** [{subject}] {chapter}. I'll target this in your next revision set!")
            span.set_status(trace.StatusCode.OK)
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            await ctx.send("❌ Error saving mistake to database.")

@bot.command()
async def review_mistakes(ctx, subject: str, *, chapter: str):
    """Pulls past mistakes from SQLite, builds a targeted 10-question drill via Gemini, and traces it via OTel"""
    with tracer.start_as_current_span("discord-command-review-mistakes") as span:
        span.set_attribute("user.id", str(ctx.author.id))
        span.set_attribute("study.subject", subject)
        span.set_attribute("study.chapter", chapter)
        
        # Track the custom business metric for SigNoz Dashboards
        recall_counter.add(1, {"subject": subject, "chapter": chapter})
        
        await ctx.send(f"🔄 *Pulling past errors for **{subject} - {chapter}** from Mistake Bank and building a 10-question targeted drill...*")
        
        try:
            with tracer.start_as_current_span("sqlite-query-mistakes") as db_span:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("SELECT question FROM mistake_bank WHERE subject = ? AND chapter = ?", (subject, chapter))
                rows = cursor.fetchall()
                conn.close()
                
                past_mistakes = [row[0] for row in rows]
                db_span.set_attribute("mistakes.retrieved_count", len(past_mistakes))
                db_span.set_status(trace.StatusCode.OK)
            
            prompt = f"""
            You are an elite engineering entrance exam mentor. 
            The student previously struggled with these specific concepts in {subject} ({chapter}):
            {past_mistakes if past_mistakes else "General conceptual gaps in this chapter."}
            
            Generate a targeted set of exactly 10 high-yield active recall questions specifically engineered to target and eliminate these weaknesses. 
            Provide them in a clear, numbered list from 1 to 10.
            """
            
            with tracer.start_as_current_span("gemini-llm-mistake-drill-generation") as llm_span:
                llm_span.set_attribute("llm.prompt.type", "targeted_mistake_review")
                response = await asyncio.to_thread(model.generate_content, prompt)
                text_output = response.text
                llm_span.set_attribute("llm.response.length", len(text_output))
                llm_span.set_status(trace.StatusCode.OK)
            
            chunks = [text_output[i:i+1900] for i in range(0, len(text_output), 1900)]
            with tracer.start_as_current_span("discord-send-mistake-chunks") as discord_span:
                discord_span.set_attribute("chunks.count", len(chunks))
                for chunk in chunks:
                    await ctx.send(chunk)
                discord_span.set_status(trace.StatusCode.OK)
                
            span.set_status(trace.StatusCode.OK)
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            await ctx.send(f"⚠️ Error generating targeted mistake review.")
            print(f"Error details: {e}")

# Command 2: The AI Active Recall Generator (Optimized, Non-Blocking & Fully Traced)
@bot.command()
async def recall(ctx, *, topic: str):
    with tracer.start_as_current_span("discord-command-recall") as span:
        span.set_attribute("user.id", str(ctx.author.id))
        span.set_attribute("recall.topic", topic)
        
        await ctx.send(f"🧠 *Guru is analyzing syllabus and drafting questions for: **{topic}***...")
        
        prompt = (
            "You are an advanced AI study mentor preparing a student for elite engineering exams. "
            "First, briefly show your internal reasoning and question selection strategy inside a thought block. "
            "Then, provide 3 final, high-level, rapid-fire active recall questions."
        )
        
        try:
            with tracer.start_as_current_span("gemini-llm-generate-content") as llm_span:
                llm_span.set_attribute("llm.prompt", prompt)
                llm_span.set_attribute("llm.topic", topic)
                
                response = await asyncio.to_thread(model.generate_content, prompt)
                text_output = response.text
                
                llm_span.set_attribute("llm.response.length", len(text_output))
                llm_span.set_status(trace.StatusCode.OK)
            
            chunks = [text_output[i:i+1900] for i in range(0, len(text_output), 1900)]
            
            with tracer.start_as_current_span("discord-send-chunks") as discord_span:
                discord_span.set_attribute("chunks.count", len(chunks))
                for chunk in chunks:
                    await ctx.send(chunk)
                discord_span.set_status(trace.StatusCode.OK)
                
            span.set_status(trace.StatusCode.OK)
            
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            await ctx.send(f"⚠️ Error generating AI content.")
            print(f"API Error details: {e}")

# --- BOT ENTRYPOINT ---
if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("🚨 DISCORD_TOKEN is missing! The bot cannot start.")
    else:
        print("🚀 Starting Discord bot...")
        bot.run(token)