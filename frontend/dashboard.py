import os
import sys
from pathlib import Path
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import httpx

# Ensure app root is on python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.schemas import FeedbackCategory, SentimentType, FeedbackEntry
from app.storage.repository import repository
from app.services.llm_engine import analyze_feedback_text
from app.services.audio_service import transcribe_audio_file

# Streamlit Page Config
st.set_page_config(
    page_title="Signal2Insight — Civic AI Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 10px;
    }
    .alert-card {
        background-color: rgba(153, 27, 27, 0.25);
        border: 1px solid #ef4444;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
    }
    .category-badge {
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def check_api_status() -> bool:
    try:
        r = httpx.get(f"{API_BASE_URL}/health", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


def get_entries():
    """Retrieve entries either via FastAPI or direct local repository."""
    try:
        r = httpx.get(f"{API_BASE_URL}/api/feedback?limit=500", timeout=2.0)
        if r.status_code == 200:
            return [FeedbackEntry(**item) for item in r.json()]
    except Exception:
        pass
    # Fallback to direct repository access
    return repository.list_entries(limit=500)


def get_analytics():
    """Retrieve analytics either via FastAPI or direct local repository."""
    try:
        r = httpx.get(f"{API_BASE_URL}/api/analytics/overview", timeout=2.0)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    # Fallback to direct repository analytics
    overview = repository.get_analytics()
    return overview.model_dump()


# --- Sidebar ---
st.sidebar.image("https://img.icons8.com/fluency/96/satellite-sending-signal.png", width=64)
st.sidebar.title("Signal2Insight")
st.sidebar.caption("ImpactHack 2026 • Civic Intelligence")

api_online = check_api_status()
if api_online:
    st.sidebar.success("● FastAPI Backend Connected (Port 8000)")
else:
    st.sidebar.info("● Standalone Mode (Direct Storage Active)")

st.sidebar.markdown("---")
st.sidebar.subheader("Quick Actions")
if st.sidebar.button("🔄 Reload Demo Seed Data", use_container_width=True):
    repository.reset_to_seed()
    st.sidebar.success("Database reset to demo seeds!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Filter Live Feed")
filter_category = st.sidebar.multiselect(
    "Civic Category",
    options=[c.value for c in FeedbackCategory],
    default=[]
)
filter_sentiment = st.sidebar.multiselect(
    "Sentiment",
    options=[s.value for s in SentimentType],
    default=[]
)
filter_critical_only = st.sidebar.checkbox("🚨 Critical Alerts Only (Urgency ≥ 4)", value=False)
search_query = st.sidebar.text_input("🔍 Search keyword", "")

# --- Header & Alerts ---
st.title("📡 Signal2Insight: Civic Engagement Intelligence")
st.caption("AI-powered unstructured feedback ingestion, real-time urgency triage, and actionable municipal summaries.")

analytics = get_analytics()
total_entries = analytics.get("total_entries", 0)
critical_count = analytics.get("critical_alerts_count", 0)
avg_urgency = analytics.get("average_urgency", 0.0)
sent_dist = analytics.get("sentiment_distribution", {})
pos_count = sent_dist.get("Positive", 0)
neg_count = sent_dist.get("Negative", 0)

# --- Emergency Alert Banner ---
recent_critical = analytics.get("recent_critical_alerts", [])
if recent_critical:
    with st.container():
        st.markdown(f"""
        <div class="alert-card">
            <h4 style="color: #fca5a5; margin:0 0 8px 0;">🚨 CRITICAL SAFETY ALERTS ({len(recent_critical)} ACTIVE)</h4>
        </div>
        """, unsafe_allow_html=True)
        cols = st.columns(min(3, len(recent_critical)))
        for i, item in enumerate(recent_critical[:3]):
            with cols[i % 3]:
                st.error(f"**[{item['category']}] Urgency {item['urgency_score']}/5**\n\n{item['summary']}\n\n👉 *{item['recommended_action']}*")

# --- KPI Metric Cards ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Total Signals Ingested", value=total_entries, delta=f"{total_entries} records")
with col2:
    st.metric(label="Critical Hazards Flagged", value=critical_count, delta="Requires immediate triage", delta_color="inverse")
with col3:
    st.metric(label="Average Urgency Score", value=f"{avg_urgency} / 5.0")
with col4:
    st.metric(label="Positive vs Negative Ratio", value=f"{pos_count} : {neg_count}")

st.markdown("---")

# --- Charts Row ---
chart_col1, chart_col2, chart_col3 = st.columns(3)

with chart_col1:
    st.subheader("Category Distribution")
    cat_dist = analytics.get("category_distribution", {})
    if cat_dist and sum(cat_dist.values()) > 0:
        fig_cat = px.pie(
            names=list(cat_dist.keys()),
            values=list(cat_dist.values()),
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_cat.update_layout(margin=dict(t=20, b=20, l=10, r=10), height=260)
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("No category data available.")

with chart_col2:
    st.subheader("Sentiment Breakdown")
    if sent_dist and sum(sent_dist.values()) > 0:
        fig_sent = px.pie(
            names=list(sent_dist.keys()),
            values=list(sent_dist.values()),
            color=list(sent_dist.keys()),
            color_discrete_map={"Positive": "#10b981", "Neutral": "#64748b", "Negative": "#ef4444"}
        )
        fig_sent.update_layout(margin=dict(t=20, b=20, l=10, r=10), height=260)
        st.plotly_chart(fig_sent, use_container_width=True)
    else:
        st.info("No sentiment data available.")

with chart_col3:
    st.subheader("Urgency Level (1-5)")
    urg_dist = analytics.get("urgency_distribution", {})
    if urg_dist:
        scores = [f"Score {k}" for k in urg_dist.keys()]
        counts = list(urg_dist.values())
        colors = ["#10b981", "#06b6d4", "#f59e0b", "#f97316", "#ef4444"]
        fig_urg = go.Figure(data=[go.Bar(x=scores, y=counts, marker_color=colors)])
        fig_urg.update_layout(
            margin=dict(t=20, b=20, l=10, r=10),
            height=260,
            yaxis=dict(title="Count"),
            xaxis=dict(title="Rating")
        )
        st.plotly_chart(fig_urg, use_container_width=True)
    else:
        st.info("No urgency data.")

st.markdown("---")

# --- Ingestion Portal Section ---
st.subheader("⚡ Live Feedback Ingestion & AI Structured Extraction")
st.caption("Submit unstructured citizen feedback to trigger real-time Pydantic extraction with LLM classification.")

tab_text, tab_audio = st.tabs(["📝 Text Submission", "🎙️ Audio Voicemail Submission"])

with tab_text:
    quick_test = st.radio(
        "Load Quick Demonstration Scenario:",
        [
            "Custom Input",
            "Emergency: Live downed power line on sidewalk",
            "Public Health: Brown tap water in residential block",
            "Community Commendation: Swift playground repairs"
        ],
        horizontal=True
    )

    preset_texts = {
        "Emergency: Live downed power line on sidewalk": "URGENT: High voltage live power line snapped and is sparking into a standing water puddle on 4th and Main near the playground. People are walking by!",
        "Public Health: Brown tap water in residential block": "There is murky brown tap water with an oily smell running from the taps in our apartment complex on Maple St. Kids are complaining of stomach aches.",
        "Community Commendation: Swift playground repairs": "I wanted to send a big thank you to the parks crew for repairing the broken swing set at Lincoln Park. It looks great and was done so fast!"
    }

    default_val = preset_texts.get(quick_test, "")
    user_text = st.text_area("Citizen Feedback Verbatim Text:", value=default_val, height=90, placeholder="Enter citizen comments, complaints, or compliments here...")

    loc_col, src_col = st.columns(2)
    with loc_col:
        input_location = st.text_input("Reported Location (optional):", value="Downtown District" if quick_test != "Custom Input" else "")
    with src_col:
        input_source = st.selectbox("Source Channel:", ["text", "web_form", "sms", "hotline"])

    if st.button("🚀 Process & Ingest Feedback", type="primary", use_container_width=True):
        if not user_text.strip():
            st.warning("Please enter feedback text.")
        else:
            with st.spinner("AI Engine analyzing unstructured feedback..."):
                import asyncio
                analysis = asyncio.run(analyze_feedback_text(user_text))

                new_entry = FeedbackEntry(
                    raw_text=user_text,
                    source=input_source,
                    location=input_location or None,
                    category=analysis.category,
                    sentiment=analysis.sentiment,
                    urgency_score=analysis.urgency_score,
                    is_critical_alert=analysis.is_critical_alert,
                    summary=analysis.summary,
                    recommended_action=analysis.recommended_action
                )
                repository.add_entry(new_entry)

                st.success("Entry successfully analyzed and stored!")
                res_col1, res_col2 = st.columns([1, 1])
                with res_col1:
                    st.json(new_entry.model_dump(mode="json"))
                with res_col2:
                    if new_entry.is_critical_alert:
                        st.error(f"🚨 CRITICAL ALERT\n\n**Category:** {new_entry.category.value}\n**Urgency:** {new_entry.urgency_score}/5\n\n**Summary:** {new_entry.summary}\n\n**Recommended Action:** {new_entry.recommended_action}")
                    else:
                        st.info(f"✅ STANDARD LOG\n\n**Category:** {new_entry.category.value}\n**Urgency:** {new_entry.urgency_score}/5\n\n**Summary:** {new_entry.summary}\n\n**Recommended Action:** {new_entry.recommended_action}")
                st.rerun()

with tab_audio:
    st.write("Upload a civic hotline voicemail or citizen voice recording (.wav, .mp3, .m4a):")
    uploaded_file = st.file_uploader("Upload Audio File", type=["wav", "mp3", "m4a"])
    audio_loc = st.text_input("Audio Location (optional):", value="Voicemail Line 1")

    if uploaded_file is not None:
        st.audio(uploaded_file)
        if st.button("🎙️ Transcribe & Analyze Voicemail", type="primary"):
            with st.spinner("Transcribing audio and extracting structured civic insights..."):
                import asyncio
                file_bytes = uploaded_file.read()
                transcribed = asyncio.run(transcribe_audio_file(file_bytes, uploaded_file.name))
                st.write(f"**Transcribed Speech:** *\"{transcribed}\"*")

                analysis = asyncio.run(analyze_feedback_text(transcribed))
                entry = FeedbackEntry(
                    raw_text=transcribed,
                    source="audio",
                    location=audio_loc,
                    category=analysis.category,
                    sentiment=analysis.sentiment,
                    urgency_score=analysis.urgency_score,
                    is_critical_alert=analysis.is_critical_alert,
                    summary=analysis.summary,
                    recommended_action=analysis.recommended_action
                )
                repository.add_entry(entry)
                st.success("Audio processed into structured civic entry!")
                st.json(entry.model_dump(mode="json"))
                st.rerun()

st.markdown("---")

# --- Feedback Feed Table ---
st.subheader("📋 Civic Feedback Records & Municipal Action Plan")

all_entries = get_entries()

# Apply UI Filters
filtered = all_entries
if filter_category:
    filtered = [e for e in filtered if e.category.value in filter_category]
if filter_sentiment:
    filtered = [e for e in filtered if e.sentiment.value in filter_sentiment]
if filter_critical_only:
    filtered = [e for e in filtered if e.is_critical_alert]
if search_query:
    q = search_query.lower()
    filtered = [
        e for e in filtered
        if q in e.raw_text.lower() or q in e.summary.lower() or q in e.recommended_action.lower() or (e.location and q in e.location.lower())
    ]

st.caption(f"Displaying {len(filtered)} of {len(all_entries)} total entries.")

if filtered:
    table_data = []
    for e in filtered:
        table_data.append({
            "ID": e.entry_id,
            "Urgency": f"{'🚨 ' if e.is_critical_alert else ''}{e.urgency_score}/5",
            "Category": e.category.value,
            "Sentiment": e.sentiment.value,
            "Summary": e.summary,
            "Recommended Action": e.recommended_action,
            "Location": e.location or "-",
            "Time": e.created_at.strftime("%Y-%m-%d %H:%M")
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Export
    csv_bytes = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Filtered Records (CSV)",
        data=csv_bytes,
        file_name="signal2insight_feedback.csv",
        mime="text/csv",
    )
else:
    st.info("No records match your selected filters.")
