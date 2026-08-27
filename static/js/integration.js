document.addEventListener("DOMContentLoaded", () => {
    fetchOpportunities();
});

/**
 * Fetches ranked internship/opportunity recommendations for the logged-in
 * student from the Flask API endpoint and updates the DOM dynamically.
 */
function fetchOpportunities() {
    const container = document.getElementById("opportunities-container");
    if (!container) return;

    fetch("/api/opportunities")
        .then(response => {
            if (response.status === 401) {
                window.location.href = "/login";
                throw new Error("redirecting to login");
            }
            if (!response.ok) {
                throw new Error(`HTTP Status Code: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === "success" && data.opportunities.length > 0) {
                renderCards(data.opportunities, container);
            } else {
                container.innerHTML = "<p>No matched opportunities found at this time.</p>";
            }
        })
        .catch(error => {
            if (error.message === "redirecting to login") return;
            console.error("Fetch Error:", error);
            container.innerHTML = `
                <div style="color: #721c24; background-color: #f8d7da; padding: 15px; border-radius: 6px; width: 100%;">
                    <p><strong>Error loading recommendations:</strong> Unable to connect to backend server.</p>
                </div>
            `;
        });
}

/**
 * Renders individual opportunity cards inside the HTML container element.
 */
function renderCards(opportunities, container) {
    container.innerHTML = ""; // Clear existing loading text

    opportunities.forEach(opp => {
        const card = document.createElement("article");
        card.className = "opportunity-card";

        // Assign badge color class based on status label
        let badgeClass = "badge-gap";
        if (opp.status === "Strong Match") badgeClass = "badge-strong";
        else if (opp.status === "Partial Match") badgeClass = "badge-partial";

        // Generate tags for matched skills
        const matchedTags = opp.matched_skills.length > 0
            ? opp.matched_skills.map(skill => `<span class="tag tag-matched">${escapeHtml(skill)}</span>`).join("")
            : `<span class="tag tag-none">None</span>`;

        // Generate tags for missing skills
        const missingTags = opp.missing_skills.length > 0
            ? opp.missing_skills.map(skill => `<span class="tag tag-missing">${escapeHtml(skill)}</span>`).join("")
            : `<span class="tag tag-none">None</span>`;

        card.innerHTML = `
            <div>
                <div class="card-header">
                    <div>
                        <h3>${escapeHtml(opp.title)}</h3>
                        <p class="company-name">${escapeHtml(opp.company)} • ${escapeHtml(opp.type)}</p>
                    </div>
                    <div class="score-badge ${badgeClass}">
                        <span class="score-number">${opp.match_score}%</span>
                        <span class="score-label">${escapeHtml(opp.status)}</span>
                    </div>
                </div>

                <div class="card-body">
                    <p style="font-size: 0.85rem; margin-top: 5px;"><strong>Matched Skills:</strong></p>
                    <div class="tag-container">${matchedTags}</div>

                    <p style="font-size: 0.85rem; margin-top: 5px;"><strong>Skills to Learn:</strong></p>
                    <div class="tag-container">${missingTags}</div>
                </div>
            </div>

            <div class="card-footer" style="margin-top: 15px;">
                <button class="btn-apply" onclick="applyOpportunity(${opp.opportunity_id}, this)">Apply Now</button>
            </div>
        `;

        container.appendChild(card);
    });
}

/**
 * Escapes HTML characters to safeguard against XSS injections.
 */
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Triggered when a user clicks 'Apply Now' — records the application
 * against the logged-in student in the database.
 */
function applyOpportunity(opportunityId, buttonEl) {
    fetch(`/api/apply/${opportunityId}`, { method: "POST" })
        .then(res => res.json())
        .then(data => {
            if (data.status === "success") {
                buttonEl.textContent = "Applied ✓";
                buttonEl.disabled = true;
            } else {
                alert("Could not record application: " + data.message);
            }
        })
        .catch(err => console.error("Apply error:", err));
}
