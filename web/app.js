const api = {
  health: "/health",
  fund: (fundCode, useRealData) =>
    `/funds/${encodeURIComponent(fundCode)}?use_real_data=${useRealData}`,
  watchlist: "/watchlist",
  addWatchlistFund: "/watchlist/funds",
  deleteWatchlistFund: (fundCode) => `/watchlist/funds/${encodeURIComponent(fundCode)}`,
  runReport: "/reports/run",
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
  taskRuns: document.querySelector("#task-runs"),
  snapshots: document.querySelector("#fund-snapshots"),
  runWatchlistReportButton: document.querySelector("#run-watchlist-report-button"),
  reportUseRealData: document.querySelector("#report-use-real-data"),
  reportUseLlm: document.querySelector("#report-use-llm"),
  reportActionMessage: document.querySelector("#report-action-message"),
  refreshButton: document.querySelector("#refresh-button"),
};

let latestLookupFund = null;

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
        <button type="button" data-lookup-action="add">加入自选</button>
        <button type="button" data-lookup-action="run-report">生成单只日报</button>
      </div>
    </div>
  `;
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
    if (action === "add") {
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
loadDashboard();
