document.addEventListener("DOMContentLoaded", () => {
    const stepsContainer = document.getElementById("question-steps");
    const currentQuestionEl = document.getElementById("current-question");
    const totalQuestionsEl = document.getElementById("total-questions");
    const progressBar = document.getElementById("assessment-progress");
    const prevBtn = document.getElementById("previous-button");
    const nextBtn = document.getElementById("next-button");
    const submitBtn = document.getElementById("submit-button");
    const form = document.getElementById("assessment-form");

    let currentStep = 0;
    let totalSteps = 0;
    let existingSkills = [];
    let categoryNames = [];

    fetch("/api/skills-catalog")
        .then((res) => {
            if (res.status === 401) {
                window.location.href = "/login";
                throw new Error("Not logged in");
            }
            return res.json();
        })
        .then((data) => buildForm(data.categories, data.current_skills || []))
        .catch((err) => {
            if (err.message !== "Not logged in") {
                stepsContainer.innerHTML = "<p>Could not load the assessment. Please refresh.</p>";
                console.error(err);
            }
        });

    function buildForm(categories, currentSkills) {
        existingSkills = currentSkills;
        categoryNames = Object.keys(categories);
        totalSteps = categoryNames.length + 1; // +1 for the "other skills" free-text step

        totalQuestionsEl.textContent = totalSteps;
        progressBar.max = totalSteps;

        stepsContainer.innerHTML = "";

        categoryNames.forEach((category, idx) => {
            const skills = categories[category];
            const step = document.createElement("div");
            step.className = "question-step";
            step.dataset.question = String(idx);
            step.style.display = idx === 0 ? "block" : "none";

            const optionsHtml = skills.map((skill) => {
                const checked = existingSkills.includes(skill) ? "checked" : "";
                const label = skill.replace(/-/g, " ");
                return `<label class="radio-option">
                            <input type="checkbox" name="skills" value="${skill}" ${checked}>
                            ${label.charAt(0).toUpperCase() + label.slice(1)}
                        </label>`;
            }).join("");

            step.innerHTML = `
                <fieldset>
                    <legend>${idx + 1}. Which of these ${category} skills do you have? (select all that apply)</legend>
                    ${optionsHtml}
                </fieldset>`;
            stepsContainer.appendChild(step);
        });

        // Final step: free-text skills not in the catalog
        const cataloguedSkills = new Set(Object.values(categories).flat());
        const uncataloguedExisting = existingSkills.filter((s) => !cataloguedSkills.has(s));

        const customStep = document.createElement("div");
        customStep.className = "question-step";
        customStep.dataset.question = String(totalSteps - 1);
        customStep.style.display = "none";
        customStep.innerHTML = `
            <fieldset>
                <legend>${totalSteps}. Any other skills? (any field — sciences, languages, sports, anything)</legend>
                <div class="input-group">
                    <label for="custom-skills">Comma-separated list</label>
                    <input type="text" id="custom-skills" placeholder="e.g. spanish, genetics, chess-coaching"
                           value="${uncataloguedExisting.join(', ')}">
                </div>
            </fieldset>`;
        stepsContainer.appendChild(customStep);

        updateStepDisplay();
    }

    function updateStepDisplay() {
        document.querySelectorAll(".question-step").forEach((step) => {
            step.style.display = (parseInt(step.dataset.question) === currentStep) ? "block" : "none";
        });

        currentQuestionEl.textContent = currentStep + 1;
        progressBar.value = currentStep + 1;
        prevBtn.disabled = currentStep === 0;

        if (currentStep === totalSteps - 1) {
            nextBtn.style.display = "none";
            submitBtn.style.display = "inline-block";
        } else {
            nextBtn.style.display = "inline-block";
            submitBtn.style.display = "none";
            nextBtn.textContent = "Next";
        }
    }

    nextBtn.addEventListener("click", () => {
        if (currentStep < totalSteps - 1) {
            currentStep++;
            updateStepDisplay();
        }
    });

    prevBtn.addEventListener("click", () => {
        if (currentStep > 0) {
            currentStep--;
            updateStepDisplay();
        }
    });

    form.addEventListener("submit", (e) => {
        e.preventDefault();

        const checkedSkills = Array.from(
            document.querySelectorAll('input[name="skills"]:checked')
        ).map((el) => el.value);

        const customInput = document.getElementById("custom-skills");
        const customSkills = customInput
            ? customInput.value.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean)
            : [];

        const allSkills = Array.from(new Set([...checkedSkills, ...customSkills]));

        fetch("/api/assess", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ skills: allSkills }),
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.status === "success") {
                    alert(`Assessment saved! ${allSkills.length} skill(s) on your profile.`);
                    window.location.href = "/";
                } else {
                    alert("Error saving assessment: " + data.message);
                }
            })
            .catch((err) => console.error("Submit error:", err));
    });
});
