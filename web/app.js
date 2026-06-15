const api = {
  health: "/health",
  watchlist: "/watchlist",
  latestReport: "/reports/latest",
  taskRuns: "/task-runs?limit=8",
  snapshots: "/fund-snapshots?limit=8",
};

const elements = {
  apiStatusDot: document.querySelector("#api-status-dot"),
  apiStatusText: document.querySelector("#api-status-text"),
  watchlistCount: document.querySelector("#watchlist-count"),
  taskCount: document.querySelector("#task-count"),
  snapshotCount: document.querySelector("#snapshot-count"),
  latestReportDate: document.querySelector("#latest-report-date"),
  reportMeta: document.querySelector("#report-meta"),
  latestReport: document.querySelector("#latest-report"),
  watchlist: document.querySelector("#watchlist"),
  taskRuns: document.querySelector("#task-runs"),
  snapshots: document.querySelector("#fund-snapshots"),
  refreshButton: document.querySelector("#refresh-button"),
};

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function inlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

function renderMarkdown(markdown) {
  const lines = String(markdown ?? "").split("\n");
  const html = [];
  let inList = false;

  for (const line of lines) {
    if (/^\s*-\s+/.test(line)) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${inlineMarkdown(line.replace(/^\s*-\s+/, ""))}</li>`);
      continue;
    }

    if (inList) {
      html.push("</ul>");
      inList = false;
    }

    if (line.startsWith("### ")) {
      html.push(`<h3>${inlineMarkdown(line.slice(4))}</h3>`);
    } else if (line.startsWith("## ")) {
      html.push(`<h2>${inlineMarkdown(line.slice(3))}</h2>`);
    } else if (line.startsWith("# ")) {
      html.push(`<h1>${inlineMarkdown(line.slice(2))}</h1>`);
    } else if (line.trim() === "") {
      html.push("<br />");
    } else {
      html.push(`<p>${inlineMarkdown(line)}</p>`);
    }
  }

  if (inList) {
    html.push("</ul>");
  }

  return html.join("");
}

function setApiStatus(status, text) {
  elements.apiStatusDot.className = `status-dot ${status}`;
  elements.apiStatusText.textContent = text;
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  return String(value).replace("T", " ");
}

function renderWatchlist(data) {
  const fundCodes = data.fund_codes ?? [];
  elements.watchlistCount.textContent = fundCodes.length;
  elements.watchlist.classList.remove("loading");

  if (fundCodes.length === 0) {
    elements.watchlist.innerHTML = '<p class="empty">暂无自选基金。</p>';
    return;
  }

  elements.watchlist.innerHTML = fundCodes
    .map((code) => `<span class="chip">${escapeHtml(code)}</span>`)
    .join("");
}

function renderLatestReport(data) {
  const metadata = data.metadata ?? {};
  elements.latestReportDate.textContent = metadata.report_date ?? "-";
  elements.reportMeta.textContent = [
    `数据源：${metadata.data_source ?? "-"}`,
    `分析模式：${metadata.analysis_mode ?? "-"}`,
    `基金：${(metadata.fund_codes ?? []).join(", ") || "-"}`,
  ].join(" / ");
  elements.latestReport.classList.remove("loading");
  elements.latestReport.innerHTML = renderMarkdown(data.content ?? "暂无报告内容。");
}

function renderTaskRuns(data) {
  const taskRuns = data.task_runs ?? [];
  elements.taskCount.textContent = taskRuns.length;
  elements.taskRuns.classList.remove("loading");

  if (taskRuns.length === 0) {
    elements.taskRuns.innerHTML = '<p class="empty">暂无任务日志。</p>';
    return;
  }

  elements.taskRuns.innerHTML = taskRuns
    .map((item) => {
      const status = item.status ?? "unknown";
      const warnings = item.warnings_count ? ` / warning：${item.warnings_count}` : "";
      const error = item.error ? `<div class="error-text">${escapeHtml(item.error)}</div>` : "";
      return `
        <div class="timeline-item">
          <div class="row">
            <div class="item-title">${escapeHtml(formatDateTime(item.started_at))}</div>
            <span class="badge ${escapeHtml(status)}">${escapeHtml(status)}</span>
          </div>
          <div class="item-meta">
            ${escapeHtml(item.data_source ?? "-")} / ${escapeHtml(item.analysis_mode ?? "-")} /
            ${escapeHtml(item.duration_seconds ?? "-")}s${escapeHtml(warnings)}
          </div>
          ${error}
        </div>
      `;
    })
    .join("");
}

function renderSnapshots(data) {
  const snapshots = data.snapshots ?? [];
  elements.snapshotCount.textContent = snapshots.length;
  elements.snapshots.classList.remove("loading");

  if (snapshots.length === 0) {
    elements.snapshots.innerHTML = '<p class="empty">暂无历史快照。</p>';
    return;
  }

  elements.snapshots.innerHTML = snapshots
    .map((item) => {
      const risk = item.risk_level ?? "unknown";
      const change = item.daily_change_percent;
      return `
        <div class="snapshot-item">
          <div class="row">
            <div class="item-title">${escapeHtml(item.fund_code)} ${escapeHtml(item.fund_name)}</div>
            <span class="badge ${escapeHtml(risk)}">${escapeHtml(risk)}</span>
          </div>
          <div class="item-meta">
            净值：${escapeHtml(item.nav ?? "-")} / 日涨跌：${escapeHtml(change ?? "-")}%
            / 日期：${escapeHtml(item.nav_date ?? item.report_date ?? "-")}
          </div>
        </div>
      `;
    })
    .join("");
}

function renderError(target, message) {
  target.classList.remove("loading");
  target.innerHTML = `<p class="error-text">${escapeHtml(message)}</p>`;
}

async function loadDashboard() {
  setApiStatus("", "检查中...");

  try {
    await fetchJson(api.health);
    setApiStatus("ok", "运行正常");
  } catch (error) {
    setApiStatus("error", "连接失败");
  }

  const tasks = [
    fetchJson(api.watchlist).then(renderWatchlist).catch((error) => renderError(elements.watchlist, error.message)),
    fetchJson(api.latestReport).then(renderLatestReport).catch((error) => renderError(elements.latestReport, error.message)),
    fetchJson(api.taskRuns).then(renderTaskRuns).catch((error) => renderError(elements.taskRuns, error.message)),
    fetchJson(api.snapshots).then(renderSnapshots).catch((error) => renderError(elements.snapshots, error.message)),
  ];

  await Promise.allSettled(tasks);
}

elements.refreshButton.addEventListener("click", loadDashboard);
loadDashboard();
