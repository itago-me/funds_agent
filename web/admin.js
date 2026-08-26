const api = {
  authMe: "/auth/me",
  authLogout: "/auth/logout",
  adminUsers: "/admin/users",
  adminUser: (userId) => `/admin/users/${encodeURIComponent(userId)}`,
  adminUserPassword: (userId) =>
    `/admin/users/${encodeURIComponent(userId)}/password`,
};

const elements = {
  userName: document.querySelector("#admin-user-name"),
  logoutButton: document.querySelector("#admin-logout-button"),
  refreshButton: document.querySelector("#admin-users-refresh-button"),
  message: document.querySelector("#admin-user-message"),
  users: document.querySelector("#admin-users"),
};

function setMessage(message, type = "") {
  elements.message.textContent = message;
  elements.message.className = `form-message ${type}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDateTime(value) {
  return value ? String(value).replace("T", " ") : "-";
}

function redirectToLogin() {
  window.location.href = `/login?next=${encodeURIComponent("/admin")}`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, { credentials: "same-origin", ...options });
  if (response.status === 401) {
    redirectToLogin();
  }
  if (response.status === 403) {
    window.location.href = "/";
  }
  if (!response.ok) {
    let message = `${url} returned ${response.status}`;
    try {
      const data = await response.json();
      message = data.detail ?? message;
    } catch {
      // Keep the HTTP status fallback for non-JSON errors.
    }
    throw new Error(message);
  }
  return response.json();
}

function renderAdminUsers(data, currentUser) {
  const users = data.users ?? [];
  elements.users.classList.remove("loading");

  if (users.length === 0) {
    elements.users.innerHTML = '<p class="empty">暂无用户。</p>';
    return;
  }

  elements.users.innerHTML = users
    .map((user) => {
      const userId = escapeHtml(user.id);
      const isSelf = String(currentUser.id) === String(user.id);
      const selfDisabled = isSelf ? "disabled" : "";
      const selectedAdmin = user.role === "admin" ? "selected" : "";
      const selectedUser = user.role === "user" ? "selected" : "";
      const checked = user.is_active ? "checked" : "";

      return `
        <div class="admin-user-row" data-admin-user-id="${userId}">
          <div class="admin-user-identity">
            <strong>${escapeHtml(user.username)}</strong>
            <span class="item-meta">ID #${userId} / 创建于 ${escapeHtml(formatDateTime(user.created_at))}</span>
          </div>
          <label class="admin-user-field">
            <span>角色</span>
            <select data-admin-role ${selfDisabled}>
              <option value="user" ${selectedUser}>user</option>
              <option value="admin" ${selectedAdmin}>admin</option>
            </select>
          </label>
          <label class="option-toggle admin-active-toggle">
            <input type="checkbox" data-admin-active ${checked} ${selfDisabled} />
            <span>启用</span>
          </label>
          <button type="button" data-admin-action="update" ${selfDisabled}>保存</button>
          <label class="admin-password-field">
            <span>新密码</span>
            <input type="password" data-admin-password minlength="8" placeholder="至少 8 位" />
          </label>
          <button type="button" data-admin-action="reset-password">重置密码</button>
        </div>
      `;
    })
    .join("");
}

async function loadAdminUsers(currentUser) {
  elements.users.classList.add("loading");
  elements.users.textContent = "加载用户列表...";
  try {
    const data = await fetchJson(api.adminUsers);
    renderAdminUsers(data, currentUser);
    return data;
  } catch (error) {
    elements.users.classList.remove("loading");
    elements.users.innerHTML = `<p class="error-text">${escapeHtml(error.message)}</p>`;
    throw error;
  }
}

async function updateAdminUser(userId, payload) {
  return fetchJson(api.adminUser(userId), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function resetAdminUserPassword(userId, password) {
  return fetchJson(api.adminUserPassword(userId), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
}

async function loadCurrentAdmin() {
  try {
    const data = await fetchJson(api.authMe);
    const user = data.user ?? null;
    if (!user || user.role !== "admin") {
      window.location.href = "/";
      return null;
    }
    elements.userName.textContent = `${user.username} (admin)`;
    return user;
  } catch (error) {
    return null;
  }
}

async function handleUsersClick(event, currentUser) {
  if (!(event.target instanceof Element)) {
    return;
  }

  const actionButton = event.target.closest("[data-admin-action]");
  const row = actionButton?.closest("[data-admin-user-id]");
  if (!actionButton || !row) {
    return;
  }

  const userId = row.dataset.adminUserId;
  actionButton.disabled = true;
  try {
    if (actionButton.dataset.adminAction === "update") {
      await updateAdminUser(userId, {
        role: row.querySelector("[data-admin-role]")?.value,
        is_active: row.querySelector("[data-admin-active]")?.checked,
      });
      setMessage(`用户 #${userId} 已更新。`, "success");
      await loadAdminUsers(currentUser);
    } else {
      const passwordInput = row.querySelector("[data-admin-password]");
      const password = passwordInput?.value ?? "";
      if (password.length < 8) {
        throw new Error("新密码至少需要 8 位。");
      }
      await resetAdminUserPassword(userId, password);
      passwordInput.value = "";
      setMessage(`用户 #${userId} 的密码已重置。`, "success");
    }
  } catch (error) {
    setMessage(error.message, "error");
  } finally {
    actionButton.disabled = false;
  }
}

async function logout() {
  await fetchJson(api.authLogout, { method: "POST" });
  window.location.href = "/login";
}

async function initializeAdminPage() {
  const user = await loadCurrentAdmin();
  if (!user) {
    return;
  }
  await loadAdminUsers(user);

  elements.refreshButton.addEventListener("click", () => {
    loadAdminUsers(user).catch(() => {});
  });
  elements.users.addEventListener("click", (event) => {
    handleUsersClick(event, user);
  });
  elements.logoutButton.addEventListener("click", () => {
    logout().catch((error) => setMessage(error.message, "error"));
  });
}

initializeAdminPage().catch((error) => {
  setMessage(error.message, "error");
});
