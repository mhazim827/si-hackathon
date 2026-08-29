(() => {
  const esc = value => String(value || "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#039;",'"':"&quot;"}[char]));
  const request = (url, options = {}) => fetch(url, options).then(async response => {
    const body = await response.json();
    if (!response.ok) throw new Error(body.message || "Something went wrong.");
    return body;
  });
  const render = items => items.length ? items.map(item => `<article class="announcement"><span class="type-pill">${esc(item.target_title)}</span><h3>${esc(item.subject)}</h3><p>${esc(item.message)}</p><small>${esc(item.publisher)} · ${new Date(item.created_at).toLocaleDateString()}</small></article>`).join("") : `<p class="muted">No announcements yet.</p>`;

  function loadAnnouncements() {
    const student = document.querySelector("#student-announcements");
    const faculty = document.querySelector("#faculty-announcements");
    if (!student && !faculty) return;
    request("/api/announcements").then(data => {
      (student || faculty).innerHTML = render(data.announcements);
    }).catch(error => (student || faculty).innerHTML = `<p class="muted">${esc(error.message)}</p>`);
  }

  function wirePublisherAnnouncements() {
    const dialog = document.querySelector("#announcement-dialog");
    const open = document.querySelector("[data-open-announcement]");
    const form = document.querySelector("#announcement-form");
    if (!dialog || !open || !form) return;
    open.addEventListener("click", () => {
      const select = document.querySelector("#announcement-target");
      select.innerHTML = `<option value="">Loading your publishing targets…</option>`;
      request("/api/publisher-announcement-targets").then(data => {
        const programs = data.programs.map(item => `<option value="program:${item.id}">Programme · ${esc(item.title)}</option>`).join("");
        const opportunities = data.opportunities.map(item => `<option value="opportunity:${item.id}">Opportunity · ${esc(item.title)}</option>`).join("");
        select.innerHTML = `<option value="">Choose a programme or opportunity</option>${programs}${opportunities}`;
        dialog.showModal();
      }).catch(error => alert(error.message));
    });
    document.querySelectorAll("[data-close-announcement]").forEach(button => button.addEventListener("click", () => dialog.close()));
    form.addEventListener("submit", event => {
      event.preventDefault();
      const raw = Object.fromEntries(new FormData(form));
      const [target_type, target_id] = (raw.target_key || "").split(":");
      const message = document.querySelector("#announcement-message");
      request("/api/announcements", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({target_type, target_id, subject:raw.subject, message:raw.message})}).then(result => {
        message.textContent = result.message;
        message.className = "form-message success";
        setTimeout(() => { dialog.close(); form.reset(); }, 900);
      }).catch(error => { message.textContent = error.message; message.className = "form-message error"; });
    });
  }

  function loadPublisherProgrammeRegistrations() {
    const target = document.querySelector("#publisher-programme-registrations");
    if (!target) return;
    request("/api/publisher-programme-registrations").then(data => {
      target.innerHTML = data.registrations.length ? data.registrations.map(item => `<div class="mini-row"><div><span class="type-pill">${esc(item.program_title)}</span><b>${esc(item.name)}</b><span>${esc(item.headline || "Student profile")}</span><small>${esc(item.email)} · Registered ${new Date(item.registered_at).toLocaleDateString()}</small></div><span class="type-pill">Registered</span></div>`).join("") : `<p class="muted">No students have registered for your programmes yet.</p>`;
    }).catch(error => target.innerHTML = `<p class="muted">${esc(error.message)}</p>`);
  }

  document.addEventListener("DOMContentLoaded", () => { loadAnnouncements(); wirePublisherAnnouncements(); loadPublisherProgrammeRegistrations(); });
})();
