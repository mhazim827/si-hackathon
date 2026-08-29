(() => {
  const esc = value => String(value || "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#039;",'"':"&quot;"}[char]));
  const request = (url, options = {}) => fetch(url, options).then(async response => {
    const body = await response.json();
    if (!response.ok) throw new Error(body.message || "Something went wrong.");
    return body;
  });
  function addCollaborationDecisions() {
    if (window.SKILLBRIDGE_ROLE !== "industry") return;
    request("/api/profile").then(data => {
      const insert = () => {
        const grid = document.querySelector("#profile-content .profile-grid");
        if (!grid) return setTimeout(insert, 80);
        if (document.querySelector("#collaboration-decisions")) return;
        const requests = data.collaboration_requests || [];
        const content = requests.length ? requests.map(item => `<div class="mini-row"><div><b>${esc(item.academician_organisation || item.academician_name)}</b><span>${esc(item.message)}</span></div>${item.status === "Sent" ? `<div class="button-row compact-actions"><button class="btn primary small" data-collaboration-decision="${item.id}" data-status="Acknowledged">Accept</button><button class="btn ghost small" data-collaboration-decision="${item.id}" data-status="Declined">Reject</button></div>` : `<span class="type-pill">${esc(item.status)}</span>`}</div>`).join("") : `<p class="muted">No collaboration requests yet.</p>`;
        const wrapper = document.createElement("div");
        wrapper.id = "collaboration-decisions";
        wrapper.style.display = "contents";
        wrapper.innerHTML = `<section class="surface profile-wide"><div class="surface-title"><div><p class="eyebrow">Collaboration requests</p><h2>Accept or reject academic partnerships</h2></div></div>${content}</section>`;
        grid.appendChild(wrapper);
      };
      insert();
    }).catch(() => {});
  }
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-collaboration-decision]");
    if (!button) return;
    button.disabled = true;
    request(`/api/collaboration-requests/${button.dataset.collaborationDecision}`, {method:"PATCH", headers:{"Content-Type":"application/json"}, body:JSON.stringify({status:button.dataset.status})}).then(() => location.reload()).catch(error => { button.disabled = false; alert(error.message); });
  });
  document.addEventListener("DOMContentLoaded", addCollaborationDecisions);
})();
