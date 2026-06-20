/* ─────────────────────────────────────────────────────────────────────────────
   MediScan AI — Frontend JavaScript
   Handles: tab switching, file upload, API calls, results rendering, download
   ───────────────────────────────────────────────────────────────────────────── */

const API_BASE = "";  // Same origin — FastAPI serves frontend

let currentTab = "text";
let selectedFile = null;
let currentReportId = null;
let loadingInterval = null;

// ── Tab Switching ─────────────────────────────────────────────────────────────

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.getElementById(`tab-${tab}`).classList.add("active");
  document.getElementById(`panel-${tab}`).classList.add("active");
}

// ── Character Counter ─────────────────────────────────────────────────────────

document.getElementById("report-text").addEventListener("input", function() {
  const count = this.value.length;
  const el = document.getElementById("char-count");
  el.textContent = `${count.toLocaleString()} / 15,000 characters`;
  el.style.color = count > 14000 ? "#ef4444" : "#5a6a8a";
});

// ── File Upload ───────────────────────────────────────────────────────────────

function handleFileSelect(input) {
  if (!input.files || !input.files[0]) return;
  const file = input.files[0];
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    alert("Please select a PDF file.");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    alert("File too large. Maximum size is 10MB.");
    return;
  }
  selectedFile = file;
  document.getElementById("file-name").textContent = file.name;
  document.getElementById("file-selected").style.display = "flex";

  const zone = document.getElementById("upload-zone");
  zone.style.borderColor = "var(--accent-green)";
  zone.style.background = "rgba(16,185,129,0.04)";
}

function removeFile() {
  selectedFile = null;
  document.getElementById("pdf-input").value = "";
  document.getElementById("file-selected").style.display = "none";

  const zone = document.getElementById("upload-zone");
  zone.style.borderColor = "";
  zone.style.background = "";
}

// Drag & Drop support
const uploadZone = document.getElementById("upload-zone");
uploadZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadZone.style.borderColor = "var(--accent-blue)";
  uploadZone.style.background = "rgba(59,130,246,0.08)";
});
uploadZone.addEventListener("dragleave", () => {
  uploadZone.style.borderColor = "";
  uploadZone.style.background = "";
});
uploadZone.addEventListener("drop", (e) => {
  e.preventDefault();
  const file = e.dataTransfer.files[0];
  if (file) {
    const fakeInput = { files: [file] };
    document.getElementById("pdf-input").files = e.dataTransfer.files;
    handleFileSelect({ files: [file] });
  }
});

// ── Validation ────────────────────────────────────────────────────────────────

function validate() {
  const age = document.getElementById("patient-age").value;
  const sex = document.getElementById("patient-sex").value;

  if (!age || parseInt(age) < 1 || parseInt(age) > 120) {
    alert("Please enter a valid age (1-120).");
    return false;
  }
  if (!sex) {
    alert("Please select biological sex (required for clinical calculations).");
    return false;
  }
  if (currentTab === "text") {
    const text = document.getElementById("report-text").value.trim();
    if (!text) {
      alert("Please paste your lab report text.");
      return false;
    }
    if (text.length < 20) {
      alert("Report text seems too short. Please paste the full report.");
      return false;
    }
  } else {
    if (!selectedFile) {
      alert("Please upload a PDF file.");
      return false;
    }
  }
  return true;
}

// ── Analysis ──────────────────────────────────────────────────────────────────

async function startAnalysis() {
  if (!validate()) return;

  showLoading();
  simulateAgentProgress();

  try {
    let reportId;

    if (currentTab === "text") {
      reportId = await analyzeText();
    } else {
      reportId = await analyzePDF();
    }

    if (!reportId) throw new Error("Analysis failed — no report ID returned");

    currentReportId = reportId;

    // Fetch full report
    const resp = await fetch(`${API_BASE}/report/${reportId}`);
    if (!resp.ok) throw new Error("Failed to fetch report");
    const report = await resp.json();

    clearInterval(loadingInterval);
    markAllStepsDone();

    await sleep(600);
    showResults(report);

  } catch (err) {
    clearInterval(loadingInterval);
    hideLoading();
    showError(err.message || "An unexpected error occurred. Please try again.");
  }
}

async function analyzeText() {
  const body = {
    report_text: document.getElementById("report-text").value,
    patient_name: document.getElementById("patient-name").value || "Patient",
    patient_age: parseInt(document.getElementById("patient-age").value),
    patient_sex: document.getElementById("patient-sex").value,
  };

  const resp = await fetch(`${API_BASE}/analyze/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "Analysis failed");
  return data.report_id;
}

async function analyzePDF() {
  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("patient_name", document.getElementById("patient-name").value || "Patient");
  formData.append("patient_age", document.getElementById("patient-age").value);
  formData.append("patient_sex", document.getElementById("patient-sex").value);

  const resp = await fetch(`${API_BASE}/analyze/pdf`, {
    method: "POST",
    body: formData,
  });

  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail || "PDF analysis failed");
  return data.report_id;
}

// ── Download ──────────────────────────────────────────────────────────────────

async function downloadReport() {
  if (!currentReportId) return;

  const btn = document.getElementById("download-btn");
  btn.textContent = "⏳ Generating PDF...";
  btn.disabled = true;

  try {
    const resp = await fetch(`${API_BASE}/download/${currentReportId}`);
    if (!resp.ok) {
      // Try to get actual error from server
      let errMsg = "Download failed";
      try { const e = await resp.json(); errMsg = e.detail || errMsg; } catch {}
      throw new Error(errMsg);
    }

    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `MediScan_Report_${currentReportId}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    btn.textContent = "✅ Downloaded!";
    setTimeout(() => {
      btn.textContent = "⬇️ Download PDF";
      btn.disabled = false;
    }, 2000);

  } catch (err) {
    btn.textContent = "❌ Failed";
    btn.disabled = false;
    alert("PDF download failed: " + err.message);
  }
}

// ── Results Rendering ─────────────────────────────────────────────────────────

function showResults(report) {
  document.getElementById("loading-section").style.display = "none";
  document.getElementById("analyzer").style.display = "none";

  const resultsSection = document.getElementById("results-section");
  resultsSection.style.display = "block";
  resultsSection.scrollIntoView({ behavior: "smooth" });

  // Patient info
  const patientInfo = `${report.patient_name} · Age ${report.patient_age} · ${capitalize(report.patient_sex)} · Report #${report.report_id}`;
  document.getElementById("results-patient-info").textContent = patientInfo;

  // Summary cards
  const summary = report.summary || {};
  document.getElementById("summary-grid").innerHTML = `
    <div class="summary-card total fade-in">
      <div class="summary-num">${summary.total_tests || 0}</div>
      <div class="summary-label">Tests Analyzed</div>
    </div>
    <div class="summary-card normal fade-in">
      <div class="summary-num">${summary.normal_count || 0}</div>
      <div class="summary-label">Normal</div>
    </div>
    <div class="summary-card abnormal fade-in">
      <div class="summary-num">${summary.abnormal_count || 0}</div>
      <div class="summary-label">Need Attention</div>
    </div>
    <div class="summary-card borderline fade-in">
      <div class="summary-num">${summary.borderline_count || 0}</div>
      <div class="summary-label">Borderline</div>
    </div>
  `;

  // Agent badge
  const iterations = report.judge_iterations || 1;
  document.getElementById("agent-badge").innerHTML =
    `🤖 <strong>6 AI Agents</strong> processed this report &nbsp;·&nbsp; ` +
    `🔬 LangGraph orchestration &nbsp;·&nbsp; ` +
    `✍️ CrewAI (Llama4-Scout) explanations &nbsp;·&nbsp; ` +
    `⚖️ Qwen judge validated in ${iterations} iteration${iterations > 1 ? "s" : ""} &nbsp;·&nbsp; ` +
    `📚 RAG-enriched with WHO reference ranges`;

  // Main report content
  const crewOutput = report.crew_explanation || "Report generation in progress...";
  // Render the crew markdown as styled HTML
  document.getElementById("report-content").innerHTML = renderMarkdown(crewOutput);

  // Calculated metrics
  const metrics = report.calculated_metrics || [];
  if (metrics.length > 0) {
    const metricsSection = document.getElementById("metrics-section");
    metricsSection.style.display = "block";
    metricsSection.classList.add("fade-in");

    document.getElementById("metrics-grid").innerHTML = metrics
      .filter(m => m.value !== null && m.value !== undefined)
      .map(m => `
        <div class="metric-card ${m.severity || "normal"}">
          <div class="metric-name">${escapeHtml(m.name)}</div>
          <div class="metric-value">${escapeHtml(String(m.value))}</div>
          <div class="metric-unit">${escapeHtml(m.unit || "")}</div>
          <div class="metric-interp">${escapeHtml(m.interpretation || "")}</div>
          <div class="metric-formula">Formula: ${escapeHtml(m.formula || "")} · Ref: ${escapeHtml(m.reference || "")}</div>
        </div>
      `).join("");
  }

  // Disclaimer
  document.getElementById("disclaimer-text").textContent = report.disclaimer || "";
}

// ── Loading Simulation ────────────────────────────────────────────────────────

function showLoading() {
  document.getElementById("analyzer").style.display = "none";
  document.getElementById("loading-section").style.display = "block";
  document.getElementById("results-section").style.display = "none";
  document.getElementById("loading-section").scrollIntoView({ behavior: "smooth" });

  // Reset all steps
  for (let i = 1; i <= 6; i++) {
    const step = document.getElementById(`step-${i}`);
    step.classList.remove("active", "done");
  }
}

function simulateAgentProgress() {
  const delays = [2000, 5000, 9000, 14000, 22000, 30000];
  delays.forEach((delay, index) => {
    setTimeout(() => {
      // Mark previous as done
      if (index > 0) {
        const prev = document.getElementById(`step-${index}`);
        if (prev) { prev.classList.remove("active"); prev.classList.add("done"); }
      }
      const step = document.getElementById(`step-${index + 1}`);
      if (step) step.classList.add("active");
    }, delay);
  });
}

function markAllStepsDone() {
  for (let i = 1; i <= 6; i++) {
    const step = document.getElementById(`step-${i}`);
    step.classList.remove("active");
    step.classList.add("done");
  }
}

function hideLoading() {
  document.getElementById("loading-section").style.display = "none";
  document.getElementById("analyzer").style.display = "block";
}

// ── Reset ─────────────────────────────────────────────────────────────────────

function resetAnalyzer() {
  currentReportId = null;
  selectedFile = null;

  document.getElementById("results-section").style.display = "none";
  document.getElementById("loading-section").style.display = "none";
  document.getElementById("analyzer").style.display = "block";

  document.getElementById("report-text").value = "";
  document.getElementById("patient-name").value = "";
  document.getElementById("patient-age").value = "";
  document.getElementById("patient-sex").value = "";
  document.getElementById("char-count").textContent = "0 / 15,000 characters";
  document.getElementById("file-selected").style.display = "none";
  document.getElementById("pdf-input").value = "";

  document.getElementById("analyzer").scrollIntoView({ behavior: "smooth" });
}

// ── Error Display ─────────────────────────────────────────────────────────────

function showError(message) {
  const html = `
    <div style="
      max-width: 540px; margin: 80px auto;
      background: rgba(239,68,68,0.08);
      border: 1px solid rgba(239,68,68,0.25);
      border-radius: 16px; padding: 40px; text-align: center;
    ">
      <div style="font-size:3rem; margin-bottom:16px">❌</div>
      <h3 style="font-size:1.2rem; margin-bottom:12px; color:#ef4444">Analysis Failed</h3>
      <p style="color:#94a3c8; font-size:0.9rem; margin-bottom:24px">${escapeHtml(message)}</p>
      <button onclick="resetAnalyzer()" style="
        padding:12px 28px; background:rgba(59,130,246,0.1);
        border:1px solid rgba(59,130,246,0.3); border-radius:10px;
        color:#3b82f6; cursor:pointer; font-family:Inter,sans-serif; font-size:0.9rem;
      ">Try Again</button>
    </div>
  `;
  document.getElementById("loading-section").innerHTML = html;
  document.getElementById("loading-section").style.display = "block";
}

// ── Markdown Renderer ─────────────────────────────────────────────────────────

function renderMarkdown(text) {
  if (!text) return "";

  const lines = text.split("\n");
  let html = "";
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    // Close open list before headings/blank lines
    if (inList && (line.trim() === "" || /^#{1,4}\s/.test(line))) {
      html += "</ul>";
      inList = false;
    }

    // H2 — Section title (SECTION 1, SECTION 2 etc.)
    if (/^##\s+/.test(line)) {
      const title = line.replace(/^##\s+/, "").replace(/\*\*/g, "");
      html += `<div class="md-section-header">${escapeHtml(title)}</div>`;

    // H3 — Sub section
    } else if (/^###\s+/.test(line)) {
      const title = line.replace(/^###\s+/, "").replace(/\*\*/g, "");
      html += `<h3 class="md-h3">${escapeHtml(title)}</h3>`;

    // H4 — Category (Blood Health, Thyroid etc.)
    } else if (/^####\s+/.test(line)) {
      const title = line.replace(/^####\s+/, "").replace(/\*\*/g, "");
      html += `<div class="md-category">${escapeHtml(title)}</div>`;

    // Horizontal rule
    } else if (/^---+$/.test(line.trim())) {
      html += `<hr class="md-hr" />`;

    // Blank line
    } else if (line.trim() === "") {
      html += `<div class="md-spacer"></div>`;

    // List item
    } else if (/^[-*]\s/.test(line)) {
      if (!inList) { html += `<ul class="md-list">`; inList = true; }
      const content = inlineFormat(line.replace(/^[-*]\s/, ""));
      // Detect status badges in test result lines
      const styled = styleBadges(content);
      html += `<li class="md-li">${styled}</li>`;

    // Regular paragraph
    } else {
      const content = styleBadges(inlineFormat(line));
      html += `<p class="md-p">${content}</p>`;
    }
  }

  if (inList) html += "</ul>";
  return html;
}

function inlineFormat(text) {
  // Bold + italic
  text = text.replace(/\*\*\*(.*?)\*\*\*/g, "<strong><em>$1</em></strong>");
  // Bold
  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Italic
  text = text.replace(/\*(.*?)\*/g, "<em>$1</em>");
  // Inline code
  text = text.replace(/`(.*?)`/g, "<code>$1</code>");
  return text;
}

function styleBadges(text) {
  // Only match BRACKETED single letters or full words — never bare H/L inside words
  // Bracketed forms: [H], [HIGH], [High], **[High]**, **[Low]** etc.
  text = text.replace(/\*{0,2}\[(H|HIGH|High)\]\*{0,2}/g,
    '<span class="badge badge-high">HIGH ↑</span>');
  text = text.replace(/\*{0,2}\[(L|LOW|Low)\]\*{0,2}/g,
    '<span class="badge badge-low">LOW ↓</span>');
  text = text.replace(/\*{0,2}\[(Normal|NORMAL|N)\]\*{0,2}/g,
    '<span class="badge badge-normal">NORMAL ✓</span>');
  text = text.replace(/\*{0,2}\[(Borderline|BORDERLINE)\]\*{0,2}/g,
    '<span class="badge badge-border">BORDERLINE</span>');

  // ALL-CAPS standalone words only — e.g. "9.2 g/dL HIGH" not "Highlight"
  // Also consume trailing ↑↓ the AI adds (prevents "HIGH ↑ ↑" duplicate)
  text = text.replace(/\bHIGH\b\s*[↑⬆]?/g, '<span class="badge badge-high">HIGH ↑</span>');
  text = text.replace(/\bLOW\b\s*[↓⬇]?/g,  '<span class="badge badge-low">LOW ↓</span>');
  text = text.replace(/\bNORMAL\b/g, '<span class="badge badge-normal">NORMAL ✓</span>');
  text = text.replace(/\bBORDERLINE\b/g, '<span class="badge badge-border">BORDERLINE</span>');

  return text;
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }
function escapeHtml(text) {
  const div = document.createElement("div");
  div.appendChild(document.createTextNode(String(text)));
  return div.innerHTML;
}
