const api = {
  health: "/health",
  fund: (fundCode, useRealData) =>
    `/funds/${encodeURIComponent(fundCode)}?use_real_data=${useRealData}`,
  fundSnapshots: (fundCode, limit = 10) =>
    `/funds/${encodeURIComponent(fundCode)}/snapshots?limit=${limit}`,
  watchlist: "/watchlist",
  addWatchlistFund: "/watchlist/funds",
  deleteWatchlistFund: (fundCode) => `/watchlist/funds/${encodeURIComponent(fundCode)}`,
  runReport: "/reports/run",
  reports: "/reports?limit=8",
  reportDetail: (reportId) => `/reports/${encodeURIComponent(reportId)}`,
  latestReport: "/reports/latest",
  taskRuns: "/task-runs?limit=8",
  taskRunDetail: (taskId) => `/task-runs/${encodeURIComponent(taskId)}`,
  rerunTaskRun: (taskId) => `/task-runs/${encodeURIComponent(taskId)}/rerun`,
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
  reportDetailMeta: document.querySelector("#report-detail-meta"),
  latestReport: document.querySelector("#latest-report"),
  watchlist: document.querySelector("#watchlist"),
  watchlistForm: document.querySelector("#watchlist-form"),
  watchlistInput: document.querySelector("#watchlist-input"),
  watchlistAddButton: document.querySelector("#watchlist-add-button"),
  watchlistMessage: document.querySelector("#watchlist-message"),
  fundLookupForm: document.querySelector("#fund-lookup-form"),
  fundLookupInput: document.querySelector("#fund-lookup-input"),
  fundLookupButton: document.querySelector("#fund-lookup-button"),
  fundLookupUseRealData: document.querySelector("#fund-lookup-use-real-data"),
  fundLookupMessage: document.querySelector("#fund-lookup-message"),
  fundLookupResult: document.querySelector("#fund-lookup-result"),
  fundDetailMessage: document.querySelector("#fund-detail-message"),
  fundDetailResult: document.querySelector("#fund-detail-result"),
  reportHistory: document.querySelector("#report-history"),
  taskRuns: document.querySelector("#task-runs"),
  snapshots: document.querySelector("#fund-snapshots"),
  runWatchlistReportButton: document.querySelector("#run-watchlist-report-button"),
  reportUseRealData: document.querySelector("#report-use-real-data"),
  reportUseLlm: document.querySelector("#report-use-llm"),
  reportActionMessage: document.querySelector("#report-action-message"),
  refreshButton: document.querySelector("#refresh-button"),
};

let latestLookupFund = null;
let selectedReportId = null;

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `${url} returned ${response.status}`;
    try {
      const errorData = await response.json();
      message = errorData.detail ?? message;
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new Error(message);
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

function setWatchlistMessage(message, type = "") {
  elements.watchlistMessage.textContent = message;
  elements.watchlistMessage.className = `form-message ${type}`;
}

function setFundLookupMessage(message, type = "") {
  elements.fundLookupMessage.textContent = message;
  elements.fundLookupMessage.className = `form-message ${type}`;
}

function setFundDetailMessage(message, type = "") {
  elements.fundDetailMessage.textContent = message;
  elements.fundDetailMessage.className = `form-message ${type}`;
}

function setReportActionMessage(message, type = "") {
  elements.reportActionMessage.textContent = message;
  elements.reportActionMessage.className = `form-message ${type}`;
}

function formatOptionalPercent(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }

  const numberValue = Number(value);
  if (Number.isNaN(numberValue)) {
    return "-";
  }
  return `${numberValue.toFixed(2)}%`;
}

function toNumber(value) {
  const numberValue = Number(value);
  return Number.isNaN(numberValue) ? null : numberValue;
}

function buildFundTrendSummary(snapshots) {
  if (snapshots.length < 2) {
    return {
      navSummary: "历史快照不足，暂不能判断净值趋势。",
      riskSummary: "历史快照不足，暂不能判断风险等级变化。",
      riskLevelChanged: false,
    };
  }

  const latestSnapshot = snapshots[0] ?? {};
  const earliestSnapshot = snapshots[snapshots.length - 1] ?? {};
  const latestNav = toNumber(latestSnapshot.nav);
  const earliestNav = toNumber(earliestSnapshot.nav);
  const latestRisk = String(latestSnapshot.risk_level ?? "unknown");
  const earliestRisk = String(earliestSnapshot.risk_level ?? "unknown");
  const riskLevelChanged = latestRisk !== earliestRisk;

  let navSummary = "净值趋势暂不可用，缺少可比较的净值数据。";
  if (latestNav !== null && earliestNav !== null && earliestNav !== 0) {
    const navChange = latestNav - earliestNav;
    const navChangePercent = (navChange / earliestNav) * 100;
    const direction = navChange > 0 ? "上升" : navChange < 0 ? "下降" : "持平";
    navSummary = `最近 ${snapshots.length} 条快照中，净值从 ${earliestNav} 到 ${latestNav}，${direction} ${Math.abs(navChange).toFixed(4)}（${navChangePercent >= 0 ? "+" : ""}${navChangePercent.toFixed(2)}%）。`;
  }

  const riskSummary = riskLevelChanged
    ? `风险等级从 ${earliestRisk} 变为 ${latestRisk}。`
    : `风险等级保持为 ${latestRisk}。`;

  return {
    navSummary,
    riskSummary,
    riskLevelChanged,
  };
}

function buildFundTrendChart(snapshots) {
  const points = snapshots
    .map((snapshot) => ({
      nav: toNumber(snapshot.nav),
      date: snapshot.nav_date ?? snapshot.report_date ?? "-",
    }))
    .filter((point) => point.nav !== null)
    .reverse();

  if (points.length < 2) {
    return `
      <div class="trend-chart empty">
        <p>趋势图暂不可用，至少需要两条有效净值快照。</p>
      </div>
    `;
  }

  const navValues = points.map((point) => point.nav);
  const minNav = Math.min(...navValues);
  const maxNav = Math.max(...navValues);
  const navRange = maxNav - minNav;
  const chartPoints = points
    .map((point, index) => {
      const x = points.length === 1 ? 0 : (index / (points.length - 1)) * 100;
      const y = navRange === 0 ? 50 : 92 - ((point.nav - minNav) / navRange) * 84;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const firstPoint = points[0];
  const lastPoint = points[points.length - 1];

  return `
    <div class="trend-chart" aria-label="基金净值趋势图">
      <div class="trend-chart-head">
        <span>净值趋势</span>
        <strong>${escapeHtml(firstPoint.date)} 至 ${escapeHtml(lastPoint.date)}</strong>
      </div>
      <svg viewBox="0 0 100 100" role="img" aria-label="净值从 ${escapeHtml(firstPoint.nav)} 到 ${escapeHtml(lastPoint.nav)}">
        <line x1="0" y1="92" x2="100" y2="92"></line>
        <line x1="0" y1="8" x2="100" y2="8"></line>
        <polyline points="${chartPoints}"></polyline>
      </svg>
      <div class="trend-chart-scale">
        <span>低 ${escapeHtml(minNav.toFixed(4))}</span>
        <span>高 ${escapeHtml(maxNav.toFixed(4))}</span>
      </div>
    </div>
  `;
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
    .map(
      (code) => `
        <span class="chip watchlist-chip">
          <span>${escapeHtml(code)}</span>
          <button
            class="chip-action"
            type="button"
            data-fund-detail-code="${escapeHtml(code)}"
            aria-label="查看 ${escapeHtml(code)} 详情"
          >
            详情
          </button>
          <button
            class="chip-remove"
            type="button"
            data-fund-code="${escapeHtml(code)}"
            aria-label="删除 ${escapeHtml(code)}"
          >
            删除
          </button>
        </span>
      `,
    )
    .join("");
}

function renderFundLookupResult(data) {
  const fund = data.fund ?? {};
  const warnings = data.warnings ?? [];
  const snapshotComparison = fund.snapshot_comparison ?? {};
  latestLookupFund = fund;
  elements.fundLookupResult.classList.remove("empty");
  elements.fundLookupResult.innerHTML = `
    <div class="lookup-card">
      <div class="row">
        <div>
          <div class="item-title">${escapeHtml(fund.fund_code)} ${escapeHtml(fund.fund_name)}</div>
          <div class="item-meta">${escapeHtml(data.data_source ?? "-")} / ${escapeHtml(fund.theme ?? "-")}</div>
        </div>
        <span class="badge ${escapeHtml(fund.risk_level ?? "unknown")}">${escapeHtml(fund.risk_level ?? "unknown")}</span>
      </div>
      <div class="lookup-grid">
        <span>净值</span><strong>${escapeHtml(fund.nav ?? "-")}</strong>
        <span>净值日期</span><strong>${escapeHtml(fund.nav_date ?? "-")}</strong>
        <span>日涨跌</span><strong>${escapeHtml(formatOptionalPercent(fund.daily_change_percent))}</strong>
        <span>7 日收益</span><strong>${escapeHtml(formatOptionalPercent(fund.seven_day_return_percent))}</strong>
        <span>30 日收益</span><strong>${escapeHtml(formatOptionalPercent(fund.thirty_day_return_percent))}</strong>
        <span>30 日回撤</span><strong>${escapeHtml(formatOptionalPercent(fund.drawdown_30d))}</strong>
      </div>
      <p class="lookup-summary">${escapeHtml(fund.change_summary ?? "暂无变化摘要。")}</p>
      <p class="lookup-summary">${escapeHtml(snapshotComparison.summary ?? "暂无快照对比。")}</p>
      ${
        warnings.length > 0
          ? `<p class="error-text">${escapeHtml(warnings.join(" / "))}</p>`
          : ""
      }
      <div class="button-row lookup-actions">
        <button type="button" data-lookup-action="detail">查看详情</button>
        <button type="button" data-lookup-action="add">加入自选</button>
        <button type="button" data-lookup-action="run-report">生成单只日报</button>
      </div>
    </div>
  `;
}

function renderFundDetail(data) {
  const snapshots = data.snapshots ?? [];
  elements.fundDetailResult.classList.remove("empty");

  if (snapshots.length === 0) {
    elements.fundDetailResult.innerHTML = `
      <div class="fund-detail-card">
        <div class="item-title">${escapeHtml(data.fund_code ?? "-")}</div>
        <p class="empty">暂无该基金的历史快照。</p>
      </div>
    `;
    return;
  }

  const latestSnapshot = snapshots[0] ?? {};
  const trendSummary = buildFundTrendSummary(snapshots);
  const trendChart = buildFundTrendChart(snapshots);
  elements.fundDetailResult.innerHTML = `
    <div class="fund-detail-card">
      <div class="row">
        <div>
          <div class="item-title">${escapeHtml(data.fund_code)} ${escapeHtml(latestSnapshot.fund_name ?? "")}</div>
          <div class="item-meta">显示 ${escapeHtml(data.count)} / 共 ${escapeHtml(data.total)} 条快照</div>
        </div>
        <span class="badge ${escapeHtml(latestSnapshot.risk_level ?? "unknown")}">${escapeHtml(latestSnapshot.risk_level ?? "unknown")}</span>
      </div>
      <div class="lookup-grid">
        <span>最近净值</span><strong>${escapeHtml(latestSnapshot.nav ?? "-")}</strong>
        <span>净值日期</span><strong>${escapeHtml(latestSnapshot.nav_date ?? latestSnapshot.report_date ?? "-")}</strong>
        <span>日涨跌</span><strong>${escapeHtml(formatOptionalPercent(latestSnapshot.daily_change_percent))}</strong>
        <span>数据源</span><strong>${escapeHtml(latestSnapshot.data_source ?? "-")}</strong>
      </div>
      <div class="trend-summary ${trendSummary.riskLevelChanged ? "risk-changed" : ""}">
        <p>${escapeHtml(trendSummary.navSummary)}</p>
        <p>${escapeHtml(trendSummary.riskSummary)}</p>
      </div>
      ${trendChart}
      <div class="snapshot-table">
        <div class="snapshot-row snapshot-header">
          <span>报告日期</span>
          <span>净值</span>
          <span>日涨跌</span>
          <span>风险</span>
        </div>
        ${snapshots
          .map(
            (snapshot) => `
              <div class="snapshot-row">
                <span>${escapeHtml(snapshot.report_date ?? "-")}</span>
                <strong>${escapeHtml(snapshot.nav ?? "-")}</strong>
                <span>${escapeHtml(formatOptionalPercent(snapshot.daily_change_percent))}</span>
                <span class="badge ${escapeHtml(snapshot.risk_level ?? "unknown")}">${escapeHtml(snapshot.risk_level ?? "unknown")}</span>
              </div>
            `,
          )
          .join("")}
      </div>
    </div>
  `;
}

function renderReportMetadata(metadata) {
  const fundCodes = metadata.fund_codes ?? [];
  const warnings = metadata.warnings ?? [];
  const historyComparison = metadata.history_comparison ?? {};
  elements.reportDetailMeta.classList.remove("loading");
  elements.reportDetailMeta.innerHTML = `
    <div class="report-meta-grid">
      <div><span>报告 ID</span><strong>#${escapeHtml(metadata.report_id ?? "-")}</strong></div>
      <div><span>报告日期</span><strong>${escapeHtml(metadata.report_date ?? "-")}</strong></div>
      <div><span>生成时间</span><strong>${escapeHtml(formatDateTime(metadata.created_at))}</strong></div>
      <div><span>数据源</span><strong>${escapeHtml(metadata.data_source ?? "-")}</strong></div>
      <div><span>分析模式</span><strong>${escapeHtml(metadata.analysis_mode ?? "-")}</strong></div>
      <div><span>基金数量</span><strong>${escapeHtml(metadata.fund_count ?? fundCodes.length)}</strong></div>
      <div><span>Warning</span><strong>${escapeHtml(metadata.warnings_count ?? warnings.length)}</strong></div>
      <div><span>报告文件</span><strong>${escapeHtml(metadata.report_file_name ?? "-")}</strong></div>
    </div>
    <div class="report-meta-section">
      <span>基金代码</span>
      <p>${escapeHtml(fundCodes.join(", ") || "-")}</p>
    </div>
    <div class="report-meta-section">
      <span>历史对比</span>
      <p>${escapeHtml(historyComparison.summary ?? "暂无历史对比。")}</p>
    </div>
    <div class="report-meta-section">
      <span>Warning 内容</span>
      ${
        warnings.length > 0
          ? `<ul>${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
          : "<p>无 warning。</p>"
      }
    </div>
  `;
}

function renderLatestReport(data) {
  const metadata = data.metadata ?? {};
  selectedReportId = metadata.report_id ?? null;
  elements.latestReportDate.textContent = metadata.report_date ?? "-";
  elements.reportMeta.textContent = [
    `报告：${metadata.report_id ?? "最新"}`,
    `数据源：${metadata.data_source ?? "-"}`,
    `分析模式：${metadata.analysis_mode ?? "-"}`,
    `基金：${(metadata.fund_codes ?? []).join(", ") || "-"}`,
  ].join(" / ");
  renderReportMetadata(metadata);
  elements.latestReport.classList.remove("loading");
  elements.latestReport.innerHTML = renderMarkdown(data.content ?? "暂无报告内容。");
}

function renderReportHistory(data) {
  const reports = data.reports ?? [];
  elements.reportHistory.classList.remove("loading");

  if (reports.length === 0) {
    elements.reportHistory.innerHTML = '<p class="empty">暂无历史报告。</p>';
    return;
  }

  elements.reportHistory.innerHTML = reports
    .map((item) => {
      const isSelected = String(item.report_id) === String(selectedReportId);
      const warnings = item.warnings_count ? ` / warning：${item.warnings_count}` : "";
      const fundCodes = (item.fund_codes ?? []).join(", ") || "-";
      return `
        <button
          class="report-history-item ${isSelected ? "selected" : ""}"
          type="button"
          data-report-id="${escapeHtml(item.report_id)}"
        >
          <span class="item-title">${escapeHtml(item.report_date ?? "-")} · #${escapeHtml(item.report_id ?? "-")}</span>
          <span class="item-meta">
            ${escapeHtml(item.data_source ?? "-")} / ${escapeHtml(item.analysis_mode ?? "-")} / ${escapeHtml(item.fund_count ?? 0)} 只基金${escapeHtml(warnings)}
          </span>
          <span class="item-meta">${escapeHtml(fundCodes)}</span>
        </button>
      `;
    })
    .join("");
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
      const taskId = item.task_id ?? "";
      const reportId = item.report_id ?? "";
      const warnings = item.warnings_count ? ` / warning：${item.warnings_count}` : "";
      const error = item.error ? `<div class="error-text">${escapeHtml(item.error)}</div>` : "";
      const reportAction =
        reportId !== ""
          ? `<button type="button" data-task-action="report" data-report-id="${escapeHtml(reportId)}">打开报告</button>`
          : "";
      const rerunAction =
        status === "failed"
          ? `<button type="button" data-task-action="rerun" data-task-id="${escapeHtml(taskId)}">失败重跑</button>`
          : "";
      return `
        <div class="timeline-item" data-task-id="${escapeHtml(taskId)}">
          <div class="row">
            <div class="item-title">#${escapeHtml(taskId)} · ${escapeHtml(formatDateTime(item.started_at))}</div>
            <span class="badge ${escapeHtml(status)}">${escapeHtml(status)}</span>
          </div>
          <div class="item-meta">
            ${escapeHtml(item.data_source ?? "-")} / ${escapeHtml(item.analysis_mode ?? "-")} /
            ${escapeHtml(item.duration_seconds ?? "-")}s${escapeHtml(warnings)}
          </div>
          ${error}
          <div class="button-row task-actions">
            <button type="button" data-task-action="detail" data-task-id="${escapeHtml(taskId)}">详情</button>
            ${reportAction}
            ${rerunAction}
          </div>
          <div class="task-detail-slot"></div>
        </div>
      `;
    })
    .join("");
}

function renderTaskRunDetail(taskRun) {
  const warnings = Array.isArray(taskRun.warnings) ? taskRun.warnings : [];
  const fundCodes = Array.isArray(taskRun.fund_codes) ? taskRun.fund_codes : [];
  const runOptions = taskRun.run_options && typeof taskRun.run_options === "object" ? taskRun.run_options : {};
  const reportText = taskRun.report_id
    ? `#${taskRun.report_id} / ${taskRun.report_file_name ?? "-"}`
    : taskRun.report_path ?? "未关联报告";
  const errorDetail = taskRun.error
    ? `<div class="task-detail-section"><span>错误</span><p class="error-text">${escapeHtml(taskRun.error_type ?? "Error")}：${escapeHtml(taskRun.error)}</p></div>`
    : "";
  const warningDetail =
    warnings.length > 0
      ? `<ul>${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
      : "<p>无 warning。</p>";

  return `
    <div class="task-detail">
      <div class="task-detail-grid">
        <div><span>开始时间</span><strong>${escapeHtml(formatDateTime(taskRun.started_at))}</strong></div>
        <div><span>结束时间</span><strong>${escapeHtml(formatDateTime(taskRun.finished_at))}</strong></div>
        <div><span>耗时</span><strong>${escapeHtml(taskRun.duration_seconds ?? "-")}s</strong></div>
        <div><span>关联报告</span><strong>${escapeHtml(reportText)}</strong></div>
        <div><span>数据源</span><strong>${escapeHtml(taskRun.data_source ?? "-")}</strong></div>
        <div><span>分析模式</span><strong>${escapeHtml(taskRun.analysis_mode ?? "-")}</strong></div>
      </div>
      <div class="task-detail-section">
        <span>基金代码</span>
        <p>${escapeHtml(fundCodes.join(", ") || "-")}</p>
      </div>
      <div class="task-detail-section">
        <span>运行参数</span>
        <p>${escapeHtml(formatReportOptions({
          useRealData: Boolean(runOptions.use_real_data),
          useLlm: Boolean(runOptions.use_llm),
        }))} / ${runOptions.use_watchlist ? "自选基金" : "指定基金"}</p>
      </div>
      <div class="task-detail-section">
        <span>Warning</span>
        ${warningDetail}
      </div>
      ${errorDetail}
    </div>
  `;
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
    fetchJson(api.reports).then(renderReportHistory).catch((error) => renderError(elements.reportHistory, error.message)),
    fetchJson(api.taskRuns).then(renderTaskRuns).catch((error) => renderError(elements.taskRuns, error.message)),
    fetchJson(api.snapshots).then(renderSnapshots).catch((error) => renderError(elements.snapshots, error.message)),
  ];

  await Promise.allSettled(tasks);
}

async function addWatchlistFund(fundCode) {
  return fetchJson(api.addWatchlistFund, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ fund_code: fundCode }),
  });
}

async function deleteWatchlistFund(fundCode) {
  return fetchJson(api.deleteWatchlistFund(fundCode), {
    method: "DELETE",
  });
}

async function lookupFund(fundCode, useRealData) {
  return fetchJson(api.fund(fundCode, useRealData));
}

async function loadFundSnapshots(fundCode, limit = 10) {
  return fetchJson(api.fundSnapshots(fundCode, limit));
}

async function loadReportDetail(reportId) {
  return fetchJson(api.reportDetail(reportId));
}

async function loadTaskRunDetail(taskId) {
  return fetchJson(api.taskRunDetail(taskId));
}

async function rerunTaskRun(taskId) {
  return fetchJson(api.rerunTaskRun(taskId), {
    method: "POST",
  });
}

function getReportOptions() {
  return {
    useRealData: elements.reportUseRealData.checked,
    useLlm: elements.reportUseLlm.checked,
  };
}

function formatReportOptions(options) {
  return [
    options.useRealData ? "真实数据" : "样例数据",
    options.useLlm ? "LLM 分析" : "规则分析",
  ].join(" / ");
}

async function runWatchlistReport(options) {
  return fetchJson(api.runReport, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      codes: null,
      use_watchlist: true,
      use_real_data: options.useRealData,
      use_llm: options.useLlm,
    }),
  });
}

async function runSingleFundReport(fundCode, options) {
  return fetchJson(api.runReport, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      codes: [fundCode],
      use_watchlist: false,
      use_real_data: options.useRealData,
      use_llm: options.useLlm,
    }),
  });
}

async function refreshWatchlist() {
  const data = await fetchJson(api.watchlist);
  renderWatchlist(data);
  return data;
}

async function handleFundLookupSubmit(event) {
  event.preventDefault();
  const fundCode = elements.fundLookupInput.value.trim();
  if (!fundCode) {
    setFundLookupMessage("请输入基金代码。", "error");
    return;
  }

  elements.fundLookupButton.disabled = true;
  elements.fundLookupUseRealData.disabled = true;
  setFundLookupMessage("正在查询...");
  try {
    const data = await lookupFund(fundCode, elements.fundLookupUseRealData.checked);
    renderFundLookupResult(data);
    setFundLookupMessage("查询成功。", "success");
  } catch (error) {
    latestLookupFund = null;
    elements.fundLookupResult.classList.add("empty");
    elements.fundLookupResult.innerHTML = "暂无查询结果。";
    setFundLookupMessage(error.message, "error");
  } finally {
    elements.fundLookupButton.disabled = false;
    elements.fundLookupUseRealData.disabled = false;
  }
}

async function handleFundLookupResultClick(event) {
  if (!(event.target instanceof Element)) {
    return;
  }

  const actionButton = event.target.closest("[data-lookup-action]");
  if (!actionButton || !latestLookupFund) {
    return;
  }

  const action = actionButton.dataset.lookupAction;
  const fundCode = String(latestLookupFund.fund_code ?? "");
  if (!fundCode) {
    setFundLookupMessage("查询结果缺少基金代码。", "error");
    return;
  }

  actionButton.disabled = true;
  try {
    if (action === "detail") {
      setFundLookupMessage(`正在打开 ${fundCode} 的基金详情...`);
      await openFundDetail(fundCode);
      setFundLookupMessage(`已打开 ${fundCode} 的基金详情。`, "success");
    } else if (action === "add") {
      const data = await addWatchlistFund(fundCode);
      renderWatchlist(data);
      setFundLookupMessage(data.message ?? "已加入自选基金。", "success");
    } else if (action === "run-report") {
      const options = getReportOptions();
      setFundLookupMessage(`正在生成单只基金日报：${formatReportOptions(options)}...`);
      const data = await runSingleFundReport(fundCode, options);
      const warnings = data.result?.warnings ?? [];
      const warningText = warnings.length > 0 ? `，warning：${warnings.length}` : "";
      setFundLookupMessage(`单只基金日报生成成功${warningText}。`, "success");
      await loadDashboard();
    }
  } catch (error) {
    setFundLookupMessage(error.message, "error");
  } finally {
    actionButton.disabled = false;
  }
}

async function openFundDetail(fundCode) {
  setFundDetailMessage(`正在加载 ${fundCode} 的历史快照...`);
  const data = await loadFundSnapshots(fundCode, 10);
  renderFundDetail(data);
  setFundDetailMessage(`已加载 ${fundCode} 的历史快照。`, "success");
}

async function handleReportHistoryClick(event) {
  if (!(event.target instanceof Element)) {
    return;
  }

  const reportButton = event.target.closest("[data-report-id]");
  if (!reportButton) {
    return;
  }

  const reportId = reportButton.dataset.reportId;
  if (!reportId) {
    return;
  }

  reportButton.disabled = true;
  setReportActionMessage(`正在打开历史报告 #${reportId}...`);
  try {
    const data = await loadReportDetail(reportId);
    renderLatestReport(data);
    const reports = await fetchJson(api.reports);
    renderReportHistory(reports);
    setReportActionMessage(`已打开历史报告 #${reportId}。`, "success");
  } catch (error) {
    setReportActionMessage(error.message, "error");
  } finally {
    reportButton.disabled = false;
  }
}

async function handleTaskRunsClick(event) {
  if (!(event.target instanceof Element)) {
    return;
  }

  const actionButton = event.target.closest("[data-task-action]");
  if (!actionButton) {
    return;
  }

  const action = actionButton.dataset.taskAction;
  const taskId = actionButton.dataset.taskId;
  const reportId = actionButton.dataset.reportId;
  const taskItem = actionButton.closest(".timeline-item");
  const detailSlot = taskItem?.querySelector(".task-detail-slot");

  actionButton.disabled = true;
  try {
    if (action === "detail" && taskId && detailSlot) {
      detailSlot.innerHTML = '<p class="item-meta">正在加载任务详情...</p>';
      const data = await loadTaskRunDetail(taskId);
      detailSlot.innerHTML = renderTaskRunDetail(data.task_run ?? {});
    } else if (action === "report" && reportId) {
      setReportActionMessage(`正在打开任务关联报告 #${reportId}...`);
      const data = await loadReportDetail(reportId);
      renderLatestReport(data);
      const reports = await fetchJson(api.reports);
      renderReportHistory(reports);
      setReportActionMessage(`已打开任务关联报告 #${reportId}。`, "success");
    } else if (action === "rerun" && taskId) {
      setReportActionMessage(`正在重跑失败任务 #${taskId}...`);
      const data = await rerunTaskRun(taskId);
      const warnings = data.result?.warnings ?? [];
      const warningText = warnings.length > 0 ? `，warning：${warnings.length}` : "";
      setReportActionMessage(`失败任务 #${taskId} 已重跑成功${warningText}。`, "success");
      await loadDashboard();
    }
  } catch (error) {
    if (detailSlot && action === "detail") {
      detailSlot.innerHTML = `<p class="error-text">${escapeHtml(error.message)}</p>`;
    } else {
      setReportActionMessage(error.message, "error");
    }
  } finally {
    actionButton.disabled = false;
  }
}

async function handleWatchlistSubmit(event) {
  event.preventDefault();
  const fundCode = elements.watchlistInput.value.trim();
  if (!fundCode) {
    setWatchlistMessage("请输入基金代码。", "error");
    return;
  }

  elements.watchlistAddButton.disabled = true;
  setWatchlistMessage("正在添加...");
  try {
    const data = await addWatchlistFund(fundCode);
    renderWatchlist(data);
    elements.watchlistInput.value = "";
    setWatchlistMessage(data.message ?? "已更新自选基金。", "success");
  } catch (error) {
    setWatchlistMessage(error.message, "error");
  } finally {
    elements.watchlistAddButton.disabled = false;
  }
}

async function handleWatchlistClick(event) {
  if (!(event.target instanceof Element)) {
    return;
  }

  const detailButton = event.target.closest("[data-fund-detail-code]");
  if (detailButton) {
    const fundCode = detailButton.dataset.fundDetailCode;
    if (!fundCode) {
      return;
    }

    detailButton.disabled = true;
    try {
      await openFundDetail(fundCode);
    } catch (error) {
      setFundDetailMessage(error.message, "error");
    } finally {
      detailButton.disabled = false;
    }
    return;
  }

  const removeButton = event.target.closest("[data-fund-code]");
  if (!removeButton) {
    return;
  }

  const fundCode = removeButton.dataset.fundCode;
  removeButton.disabled = true;
  setWatchlistMessage(`正在删除 ${fundCode}...`);
  try {
    const data = await deleteWatchlistFund(fundCode);
    renderWatchlist(data);
    setWatchlistMessage(data.message ?? "已更新自选基金。", "success");
  } catch (error) {
    setWatchlistMessage(error.message, "error");
    removeButton.disabled = false;
  }
}

async function handleRunWatchlistReport() {
  const options = getReportOptions();
  elements.runWatchlistReportButton.disabled = true;
  elements.refreshButton.disabled = true;
  elements.reportUseRealData.disabled = true;
  elements.reportUseLlm.disabled = true;
  setReportActionMessage(`正在生成自选基金日报：${formatReportOptions(options)}...`);

  try {
    const data = await runWatchlistReport(options);
    const result = data.result ?? {};
    const warnings = result.warnings ?? [];
    const warningText = warnings.length > 0 ? `，warning：${warnings.length}` : "";
    setReportActionMessage(
      `日报生成成功：${formatReportOptions(options)}${warningText}。`,
      "success",
    );
    await loadDashboard();
  } catch (error) {
    setReportActionMessage(error.message, "error");
  } finally {
    elements.runWatchlistReportButton.disabled = false;
    elements.refreshButton.disabled = false;
    elements.reportUseRealData.disabled = false;
    elements.reportUseLlm.disabled = false;
  }
}

elements.refreshButton.addEventListener("click", loadDashboard);
elements.runWatchlistReportButton.addEventListener("click", handleRunWatchlistReport);
elements.watchlistForm.addEventListener("submit", handleWatchlistSubmit);
elements.watchlist.addEventListener("click", handleWatchlistClick);
elements.fundLookupForm.addEventListener("submit", handleFundLookupSubmit);
elements.fundLookupResult.addEventListener("click", handleFundLookupResultClick);
elements.reportHistory.addEventListener("click", handleReportHistoryClick);
elements.taskRuns.addEventListener("click", handleTaskRunsClick);
loadDashboard();
