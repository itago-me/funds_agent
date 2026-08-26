const registerForm = document.querySelector("#register-form");
const usernameInput = document.querySelector("#register-username");
const passwordInput = document.querySelector("#register-password");
const passwordConfirmInput = document.querySelector("#register-password-confirm");
const registerButton = document.querySelector("#register-button");
const message = document.querySelector("#register-message");

function setMessage(text, type = "") {
  message.textContent = text;
  message.className = `form-message ${type}`;
}

async function register(username, password) {
  const response = await fetch("/auth/register", {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    let detail = "注册失败，请稍后重试。";
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

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  const passwordConfirm = passwordConfirmInput.value;

  if (!username || !password || !passwordConfirm) {
    setMessage("请填写完整的注册信息。", "error");
    return;
  }
  if (password !== passwordConfirm) {
    setMessage("两次输入的密码不一致。", "error");
    passwordConfirmInput.select();
    return;
  }

  registerButton.disabled = true;
  setMessage("正在注册...");
  try {
    await register(username, password);
    setMessage("注册成功，请返回登录页。", "success");
    window.location.href = "/login";
  } catch (error) {
    setMessage(error.message, "error");
    passwordInput.select();
  } finally {
    registerButton.disabled = false;
  }
});
