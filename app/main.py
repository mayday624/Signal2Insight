from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.config import settings
from app.routes.analytics import router as analytics_router
from app.routes.feedback import router as feedback_router
from app.storage.repository import repository

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("signal2insight.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for startup and shutdown procedures."""
    logger.info("Starting up Signal2Insight API...")
    # Verify repository loaded
    count = len(repository.list_entries())
    logger.info(f"Signal2Insight storage ready with {count} civic feedback records.")
    yield
    logger.info("Shutting down Signal2Insight API...")


app = FastAPI(
    title="Signal2Insight API",
    description=(
        "AI-powered civic intelligence backend that ingests unstructured community feedback "
        "(text & audio), analyzes urgency and sentiment using structured Pydantic outputs, "
        "and flags critical public safety hazards for municipal officials."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

# Enable CORS for frontend applications (React, Next.js, Streamlit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(feedback_router)
app.include_router(analytics_router)


@app.get("/", tags=["System"])
def root_info():
    """Service status and quick links."""
    return {
        "service": "Signal2Insight",
        "status": "operational",
        "version": settings.app_version,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "web_dashboard_url": "/dashboard",
        "api_endpoints": {
            "ingest_text": "POST /api/feedback/ingest",
            "ingest_audio": "POST /api/feedback/ingest-audio",
            "batch_ingest": "POST /api/feedback/batch",
            "list_feedback": "GET /api/feedback",
            "analytics_overview": "GET /api/analytics/overview",
            "critical_alerts": "GET /api/analytics/critical-alerts",
        },
    }


@app.get("/health", tags=["System"])
def health_check():
    """Health check for service monitoring."""
    overview = repository.get_analytics()
    return {
        "status": "healthy",
        "total_records": overview.total_entries,
        "critical_alerts": overview.critical_alerts_count,
        "llm_provider": settings.llm_provider,
        "has_openai_key": bool(settings.openai_api_key),
        "has_gemini_key": bool(settings.gemini_api_key),
    }


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard UI"])
def standalone_web_dashboard():
    """
    Built-in modern web dashboard served directly from FastAPI using Tailwind CSS & Chart.js.
    Provides instant access without requiring Node/npm build steps.
    """
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Signal2Insight — Civic Intelligence Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            brand: { 50: '#f0fdf4', 500: '#16a34a', 600: '#15803d', 900: '#14532d' }
          }
        }
      }
    }
  </script>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen font-sans">
  <!-- Top Navigation -->
  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <i class="fa-solid fa-satellite-dish text-white text-lg"></i>
        </div>
        <div>
          <h1 class="font-bold text-lg leading-tight tracking-wide text-white">Signal2Insight</h1>
          <p class="text-xs text-slate-400">ImpactHack 2026 • AI Civic Intelligence Platform</p>
        </div>
      </div>
      <div class="flex items-center space-x-3">
        <button onclick="clearAllData()" class="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-xs font-medium text-slate-300 transition">
          <i class="fa-solid fa-trash-can mr-1.5"></i> Clear Records
        </button>
        <a href="/docs" target="_blank" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-white transition shadow-sm">
          <i class="fa-solid fa-bolt mr-1.5"></i> API Docs
        </a>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 py-6 space-y-6">
    <!-- Critical Alerts Emergency Banner -->
    <div id="criticalBanner" class="hidden rounded-xl border border-red-500/40 bg-red-950/40 p-4 backdrop-blur shadow-xl shadow-red-950/50">
      <div class="flex items-start justify-between">
        <div class="flex items-center space-x-3">
          <span class="flex h-3 w-3 relative">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
          </span>
          <h2 class="text-red-300 font-bold uppercase tracking-wider text-xs">Urgent Safety Alerts Detected</h2>
        </div>
        <span id="criticalCountBadge" class="bg-red-500/20 text-red-300 border border-red-500/30 px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold">0 Critical</span>
      </div>
      <div id="criticalItemsList" class="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3"></div>
    </div>

    <!-- KPI Metric Cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="rounded-xl border border-slate-800 bg-slate-950 p-4">
        <div class="flex items-center justify-between text-slate-400 text-xs uppercase font-semibold">
          <span>Total Signals Ingested</span>
          <i class="fa-solid fa-comments text-slate-500"></i>
        </div>
        <div id="kpiTotal" class="mt-2 text-2xl font-black text-white">0</div>
        <div class="mt-1 text-xs text-slate-400">Verbatim civic community entries</div>
      </div>

      <div class="rounded-xl border border-slate-800 bg-slate-950 p-4">
        <div class="flex items-center justify-between text-slate-400 text-xs uppercase font-semibold">
          <span>Critical Alerts</span>
          <i class="fa-solid fa-triangle-exclamation text-red-400"></i>
        </div>
        <div id="kpiCritical" class="mt-2 text-2xl font-black text-red-400">0</div>
        <div class="mt-1 text-xs text-red-400/80">Urgency rating &ge; 4 / hazard</div>
      </div>

      <div class="rounded-xl border border-slate-800 bg-slate-950 p-4">
        <div class="flex items-center justify-between text-slate-400 text-xs uppercase font-semibold">
          <span>Average Urgency</span>
          <i class="fa-solid fa-gauge-high text-amber-400"></i>
        </div>
        <div id="kpiUrgency" class="mt-2 text-2xl font-black text-amber-400">0.0</div>
        <div class="mt-1 text-xs text-slate-400">On a 1 to 5 scale</div>
      </div>

      <div class="rounded-xl border border-slate-800 bg-slate-950 p-4">
        <div class="flex items-center justify-between text-slate-400 text-xs uppercase font-semibold">
          <span>Sentiment Ratio</span>
          <i class="fa-solid fa-heart-pulse text-emerald-400"></i>
        </div>
        <div id="kpiSentiment" class="mt-2 text-2xl font-black text-emerald-400">-</div>
        <div class="mt-1 text-xs text-slate-400">Positive vs Negative</div>
      </div>
    </div>

    <!-- Charts Row -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="rounded-xl border border-slate-800 bg-slate-950 p-5">
        <h3 class="text-sm font-semibold text-slate-200 mb-4 flex items-center">
          <i class="fa-solid fa-chart-pie text-emerald-400 mr-2"></i> Category Breakdown
        </h3>
        <div class="h-56 relative flex items-center justify-center">
          <canvas id="categoryChart"></canvas>
        </div>
      </div>

      <div class="rounded-xl border border-slate-800 bg-slate-950 p-5">
        <h3 class="text-sm font-semibold text-slate-200 mb-4 flex items-center">
          <i class="fa-solid fa-face-smile text-cyan-400 mr-2"></i> Sentiment Distribution
        </h3>
        <div class="h-56 relative flex items-center justify-center">
          <canvas id="sentimentChart"></canvas>
        </div>
      </div>

      <div class="rounded-xl border border-slate-800 bg-slate-950 p-5">
        <h3 class="text-sm font-semibold text-slate-200 mb-4 flex items-center">
          <i class="fa-solid fa-chart-column text-amber-400 mr-2"></i> Urgency Distribution (1-5)
        </h3>
        <div class="h-56 relative flex items-center justify-center">
          <canvas id="urgencyChart"></canvas>
        </div>
      </div>
    </div>

    <!-- Live Ingestion & Processing Section -->
    <div class="rounded-xl border border-slate-800 bg-slate-950 p-5">
      <div class="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
        <div>
          <h3 class="text-sm font-bold text-white flex items-center">
            <i class="fa-solid fa-microchip text-emerald-400 mr-2"></i> Live Civic Signal Ingestion & AI Structured Extraction
          </h3>
          <p class="text-xs text-slate-400 mt-0.5">Submit unstructured citizen text or audio for real-time Pydantic parsing.</p>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Input Form -->
        <div class="space-y-4">
          <div>
            <label class="block text-xs font-semibold text-slate-300 mb-1">Citizen Feedback Text</label>
            <textarea id="feedbackInput" rows="3" class="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 placeholder-slate-500" placeholder="e.g. Broken water pipe flooding sidewalk on Main Street near 3rd Ave..."></textarea>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Location / District</label>
              <input id="locationInput" type="text" placeholder="e.g. Ward 2, Oak St" class="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500">
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Source Channel</label>
              <select id="sourceInput" class="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500">
                <option value="text">Mobile App / SMS</option>
                <option value="web_form">Municipal Web Portal</option>
                <option value="hotline_audio">Hotline Voicemail</option>
              </select>
            </div>
          </div>

          <div class="flex items-center space-x-3 pt-2">
            <button id="submitBtn" onclick="submitFeedback()" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs py-2 px-4 rounded-lg transition flex items-center justify-center space-x-2">
              <i class="fa-solid fa-wand-magic-sparkles"></i>
              <span>Analyze & Ingest Feedback</span>
            </button>
          </div>
        </div>

        <!-- Real-time Structured Result Output -->
        <div class="rounded-lg bg-slate-900 border border-slate-800 p-4 font-mono text-xs flex flex-col justify-between">
          <div class="flex items-center justify-between text-slate-400 mb-2 border-b border-slate-800 pb-2">
            <span class="font-bold text-slate-300 flex items-center">
              <i class="fa-solid fa-code text-cyan-400 mr-2"></i> Structured Pydantic Output
            </span>
            <span id="extractionStatus" class="text-slate-500">Awaiting input</span>
          </div>
          <pre id="jsonResult" class="overflow-x-auto text-emerald-400 flex-1 leading-relaxed max-h-48 text-xs">// LLM Pydantic Output will appear here in real-time...</pre>
        </div>
      </div>
    </div>

    <!-- Feed Table & Filter Controls -->
    <div class="rounded-xl border border-slate-800 bg-slate-950 p-5 space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h3 class="text-sm font-bold text-white flex items-center">
          <i class="fa-solid fa-list-check text-cyan-400 mr-2"></i> Actionable Civic Feedback Feed
        </h3>

        <!-- Filter Controls -->
        <div class="flex flex-wrap items-center gap-2">
          <input id="searchInput" oninput="loadFeedbackList()" type="text" placeholder="Search keyword..." class="rounded-lg bg-slate-900 border border-slate-700 px-3 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500">
          <select id="categoryFilter" onchange="loadFeedbackList()" class="rounded-lg bg-slate-900 border border-slate-700 px-2 py-1 text-xs text-white">
            <option value="">All Categories</option>
            <option value="Safety">Safety</option>
            <option value="Infrastructure">Infrastructure</option>
            <option value="Public Health">Public Health</option>
            <option value="Environment">Environment</option>
            <option value="Education">Education</option>
            <option value="Governance">Governance</option>
          </select>
          <select id="sentimentFilter" onchange="loadFeedbackList()" class="rounded-lg bg-slate-900 border border-slate-700 px-2 py-1 text-xs text-white">
            <option value="">All Sentiments</option>
            <option value="Positive">Positive</option>
            <option value="Neutral">Neutral</option>
            <option value="Negative">Negative</option>
          </select>
          <label class="flex items-center space-x-1.5 text-xs text-red-300 font-medium cursor-pointer">
            <input id="criticalOnlyCheck" onchange="loadFeedbackList()" type="checkbox" class="rounded bg-slate-900 border-slate-700 text-red-500">
            <span>Critical Only</span>
          </label>
        </div>
      </div>

      <!-- Table -->
      <div class="overflow-x-auto rounded-lg border border-slate-800">
        <table class="w-full text-left text-xs">
          <thead class="bg-slate-900 text-slate-400 uppercase font-semibold border-b border-slate-800">
            <tr>
              <th class="px-4 py-3">ID / Source</th>
              <th class="px-4 py-3">Category</th>
              <th class="px-4 py-3">Urgency</th>
              <th class="px-4 py-3">Summary</th>
              <th class="px-4 py-3">Recommended Action</th>
              <th class="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody id="feedbackTableBody" class="divide-y divide-slate-800 text-slate-300">
            <!-- Dynamic rows -->
          </tbody>
        </table>
      </div>
    </div>
  </main>

  <script>
    let catChartInstance = null;
    let sentChartInstance = null;
    let urgChartInstance = null;

    async function fetchAnalytics() {
      try {
        const res = await fetch('/api/analytics/overview');
        const data = await res.json();

        document.getElementById('kpiTotal').innerText = data.total_entries;
        document.getElementById('kpiCritical').innerText = data.critical_alerts_count;
        document.getElementById('kpiUrgency').innerText = data.average_urgency;

        const pos = data.sentiment_distribution['Positive'] || 0;
        const neg = data.sentiment_distribution['Negative'] || 0;
        document.getElementById('kpiSentiment').innerText = `${pos} : ${neg}`;

        // Render Critical Banner
        const banner = document.getElementById('criticalBanner');
        const list = document.getElementById('criticalItemsList');
        const badge = document.getElementById('criticalCountBadge');

        if (data.recent_critical_alerts && data.recent_critical_alerts.length > 0) {
          banner.classList.remove('hidden');
          badge.innerText = `${data.recent_critical_alerts.length} Critical`;
          list.innerHTML = data.recent_critical_alerts.map(item => `
            <div class="p-2.5 rounded-lg bg-red-900/30 border border-red-500/30">
              <div class="flex items-center justify-between text-red-200 font-bold text-xs">
                <span>[${item.category}] Urgency ${item.urgency_score}/5</span>
                <span class="text-xs text-red-300">${item.location || 'Reported'}</span>
              </div>
              <p class="text-xs text-slate-200 mt-1 line-clamp-2">${item.summary}</p>
              <div class="text-[11px] text-amber-300 mt-1 font-semibold flex items-center">
                <i class="fa-solid fa-arrow-right text-[9px] mr-1"></i> ${item.recommended_action}
              </div>
            </div>
          `).join('');
        } else {
          banner.classList.add('hidden');
        }

        renderCharts(data);
      } catch (e) {
        console.error("Failed to load analytics", e);
      }
    }

    function renderCharts(data) {
      // Category Chart
      const catCtx = document.getElementById('categoryChart').getContext('2d');
      if (catChartInstance) catChartInstance.destroy();
      catChartInstance = new Chart(catCtx, {
        type: 'doughnut',
        data: {
          labels: Object.keys(data.category_distribution),
          datasets: [{
            data: Object.values(data.category_distribution),
            backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 10 } } }
          }
        }
      });

      // Sentiment Chart
      const sentCtx = document.getElementById('sentimentChart').getContext('2d');
      if (sentChartInstance) sentChartInstance.destroy();
      sentChartInstance = new Chart(sentCtx, {
        type: 'pie',
        data: {
          labels: Object.keys(data.sentiment_distribution),
          datasets: [{
            data: Object.values(data.sentiment_distribution),
            backgroundColor: ['#10b981', '#64748b', '#ef4444'],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'right', labels: { color: '#94a3b8', font: { size: 10 } } }
          }
        }
      });

      // Urgency Chart
      const urgCtx = document.getElementById('urgencyChart').getContext('2d');
      if (urgChartInstance) urgChartInstance.destroy();
      urgChartInstance = new Chart(urgCtx, {
        type: 'bar',
        data: {
          labels: ['Score 1', 'Score 2', 'Score 3', 'Score 4 (Critical)', 'Score 5 (Critical)'],
          datasets: [{
            label: 'Feedback Count',
            data: [
              data.urgency_distribution[1] || 0,
              data.urgency_distribution[2] || 0,
              data.urgency_distribution[3] || 0,
              data.urgency_distribution[4] || 0,
              data.urgency_distribution[5] || 0
            ],
            backgroundColor: ['#10b981', '#06b6d4', '#f59e0b', '#f97316', '#ef4444'],
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, ticks: { color: '#94a3b8', precision: 0 } },
            x: { ticks: { color: '#94a3b8', font: { size: 10 } } }
          },
          plugins: { legend: { display: false } }
        }
      });
    }

    async function loadFeedbackList() {
      const category = document.getElementById('categoryFilter').value;
      const sentiment = document.getElementById('sentimentFilter').value;
      const isCritical = document.getElementById('criticalOnlyCheck').checked;
      const search = document.getElementById('searchInput').value;

      const params = new URLSearchParams();
      if (category) params.append('category', category);
      if (sentiment) params.append('sentiment', sentiment);
      if (isCritical) params.append('is_critical_alert', 'true');
      if (search) params.append('search', search);

      try {
        const res = await fetch(`/api/feedback?${params.toString()}`);
        const entries = await res.json();
        const tbody = document.getElementById('feedbackTableBody');

        if (entries.length === 0) {
          tbody.innerHTML = `<tr><td colspan="6" class="text-center py-6 text-slate-500">No feedback entries matching selected criteria.</td></tr>`;
          return;
        }

        tbody.innerHTML = entries.map(e => {
          const urgencyColor = e.urgency_score >= 4 ? 'bg-red-500/20 text-red-300 border-red-500/30' :
                               e.urgency_score === 3 ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                               'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
          const sentColor = e.sentiment === 'Positive' ? 'text-emerald-400' :
                            e.sentiment === 'Negative' ? 'text-red-400' : 'text-slate-400';

          return `
            <tr class="hover:bg-slate-900/60 transition">
              <td class="px-4 py-3 whitespace-nowrap">
                <span class="font-mono text-slate-400 font-semibold">${e.entry_id}</span>
                <div class="text-[11px] text-slate-500 capitalize">${e.source} ${e.location ? '• ' + e.location : ''}</div>
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                <span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                  ${e.category}
                </span>
                <span class="ml-1 text-[11px] font-semibold ${sentColor}">(${e.sentiment})</span>
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                <span class="px-2 py-0.5 rounded border text-[11px] font-mono font-bold ${urgencyColor}">
                  Score ${e.urgency_score}/5 ${e.is_critical_alert ? '🚨' : ''}
                </span>
              </td>
              <td class="px-4 py-3 max-w-xs">
                <p class="truncate text-slate-200" title="${e.summary}">${e.summary}</p>
                <p class="truncate text-[11px] text-slate-500 italic" title="${e.raw_text}">"${e.raw_text}"</p>
              </td>
              <td class="px-4 py-3 max-w-xs">
                <p class="text-cyan-300 font-medium truncate" title="${e.recommended_action}">${e.recommended_action}</p>
              </td>
              <td class="px-4 py-3 whitespace-nowrap">
                <button onclick="deleteEntry('${e.entry_id}')" class="text-slate-500 hover:text-red-400 transition" title="Delete record">
                  <i class="fa-regular fa-trash-can"></i>
                </button>
              </td>
            </tr>
          `;
        }).join('');
      } catch (e) {
        console.error("Failed to load feedback feed", e);
      }
    }

    async function submitFeedback() {
      const text = document.getElementById('feedbackInput').value.trim();
      const location = document.getElementById('locationInput').value.trim();
      const source = document.getElementById('sourceInput').value;
      const btn = document.getElementById('submitBtn');
      const statusEl = document.getElementById('extractionStatus');
      const jsonPre = document.getElementById('jsonResult');

      if (!text) {
        alert("Please enter community feedback text.");
        return;
      }

      btn.disabled = true;
      btn.innerHTML = `<i class="fa-solid fa-spinner animate-spin"></i> <span>Processing AI Extraction...</span>`;
      statusEl.innerText = "Analyzing with LLM...";

      try {
        const res = await fetch('/api/feedback/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, location: location || null, source })
        });
        const saved = await res.json();

        jsonPre.innerText = JSON.stringify(saved, null, 2);
        statusEl.innerText = saved.is_critical_alert ? "CRITICAL ALERT FLAGGED" : "Ingestion Complete";
        statusEl.className = saved.is_critical_alert ? "text-red-400 font-bold" : "text-emerald-400 font-bold";

        document.getElementById('feedbackInput').value = '';
        await fetchAnalytics();
        await loadFeedbackList();
      } catch (e) {
        jsonPre.innerText = "Error: " + e.message;
        statusEl.innerText = "Failed";
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> <span>Analyze & Ingest Feedback</span>`;
      }
    }

    async function deleteEntry(entryId) {
      if (!confirm(`Delete entry ${entryId}?`)) return;
      try {
        await fetch(`/api/feedback/${entryId}`, { method: 'DELETE' });
        await fetchAnalytics();
        await loadFeedbackList();
      } catch (e) {
        alert("Failed to delete: " + e.message);
      }
    }

    async function clearAllData() {
      if (!confirm("Clear all feedback records from database?")) return;
      try {
        await fetch('/api/feedback/clear', { method: 'POST' });
        await fetchAnalytics();
        await loadFeedbackList();
      } catch (e) {
        alert("Failed to clear records: " + e.message);
      }
    }

    // Initial load
    fetchAnalytics();
    loadFeedbackList();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
