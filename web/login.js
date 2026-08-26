const loginForm = document.querySelector("#login-form");
const usernameInput = document.querySelector("#login-username");
const passwordInput = document.querySelector("#login-password");
const loginButton = document.querySelector("#login-button");
const message = document.querySelector("#login-message");

function setMessage(text, type = "") {
  message.textContent = text;
  message.className = `form-message ${type}`;
}

async function login(username, password) {
  const response = await fetch("/auth/login", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    let detail = "登录失败，请稍后重试。";
    try {
      const data = await response.json();
      detail = data.detail ?? detail;
    } catch {
      // Keep the generic fallback for non-JSON errors.
    }
    throw new Error(detail);
  }
  return response.json();
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const username = usernameInput.value.trim();
  const password = passwordInput.value;

  if (!username || !password) {
    setMessage("请输入用户名和密码。", "error");
    return;
  }

  loginButton.disabled = true;
  setMessage("正在登录...");
  try {
    await login(username, password);
    setMessage("登录成功，正在进入工作台...", "success");
    const requestedTarget = new URLSearchParams(window.location.search).get("next") || "/";
    const target =
      requestedTarget.startsWith("/") && !requestedTarget.startsWith("//")
        ? requestedTarget
        : "/";
    window.location.href = target;
  } catch (error) {
    setMessage(error.message, "error");
    passwordInput.select();
  } finally {
    loginButton.disabled = false;
  }
});
