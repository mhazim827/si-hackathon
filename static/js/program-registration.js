(() => {
  const request = (url, options = {}) => fetch(url, options).then(async response => {
    const raw = await response.text();
    let body;
    try { body = JSON.parse(raw); } catch { throw new Error("The server returned an unexpected response. Please try again."); }
    if (!response.ok) throw new Error(body.message || "Something went wrong.");
    return body;
  });

  function moveEmailForStudentRegistration() {
    const form = document.querySelector("#register-form");
    const email = document.querySelector("#email");
    const organisationFields = document.querySelector("#organisation-fields");
    if (!form || !email || !organisationFields) return;
    const emailLabel = email.closest("label");
    const personalFields = form.querySelector(".form-grid");
    const placeEmail = () => {
      const student = document.querySelector("input[name=role]:checked")?.value === "student";
      if (student) {
        personalFields.insertAdjacentElement("afterend", emailLabel);
        emailLabel.childNodes[0].textContent = "Email";
      } else {
        organisationFields.appendChild(emailLabel);
        emailLabel.childNodes[0].textContent = "Work email";
      }
      email.required = true;
    };
    document.querySelectorAll("input[name=role]").forEach(input => input.addEventListener("change", placeEmail));
    placeEmail();
  }

  async function ensureStudentEmail() {
    const profile = await request("/api/profile");
    if (profile.user.email) return true;
    const email = prompt("Enter your email to receive your programme confirmation and publisher message:");
    if (!email) return false;
    await request("/api/profile", {
      method: "PUT",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({name: profile.user.name, headline: profile.user.headline || "", bio: profile.user.bio || "", email})
    });
    return true;
  }

  document.addEventListener("DOMContentLoaded", moveEmailForStudentRegistration);
  document.addEventListener("click", async event => {
    const button = event.target.closest("[data-register-program]");
    if (!button) return;
    button.disabled = true;
    button.textContent = "Registering…";
    try {
      if (!await ensureStudentEmail()) { button.disabled = false; button.textContent = "Save programme"; return; }
      const result = await request(`/api/learning-programs/${button.dataset.registerProgram}/register`, {method: "POST"});
      button.textContent = result.registered ? "Registered ✓" : "Already registered ✓";
      button.className = "btn applied small";
    } catch (error) {
      button.disabled = false;
      button.textContent = "Save programme";
      alert(error.message);
    }
  });
})();
