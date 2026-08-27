document.addEventListener("DOMContentLoaded", () => {
    const errorEl = document.getElementById("auth-error");

    function showError(message) {
        errorEl.textContent = message;
        errorEl.style.display = "block";
    }

    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", (e) => {
            e.preventDefault();
            errorEl.style.display = "none";

            const payload = {
                username: document.getElementById("username").value.trim(),
                password: document.getElementById("password").value,
            };

            fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })
                .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
                .then(({ ok, data }) => {
                    if (ok && data.status === "success") {
                        window.location.href = data.redirect || "/";
                    } else {
                        showError(data.message || "Login failed.");
                    }
                })
                .catch(() => showError("Could not reach the server. Is it running?"));
        });
    }

    const registerForm = document.getElementById("register-form");
    if (registerForm) {
        registerForm.addEventListener("submit", (e) => {
            e.preventDefault();
            errorEl.style.display = "none";

            const payload = {
                name: document.getElementById("name").value.trim(),
                username: document.getElementById("username").value.trim(),
                password: document.getElementById("password").value,
            };

            fetch("/api/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            })
                .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
                .then(({ ok, data }) => {
                    if (ok && data.status === "success") {
                        window.location.href = data.redirect || "/assessment";
                    } else {
                        showError(data.message || "Registration failed.");
                    }
                })
                .catch(() => showError("Could not reach the server. Is it running?"));
        });
    }
});
