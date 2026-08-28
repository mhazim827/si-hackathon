document.addEventListener("DOMContentLoaded", () => {
  const catalog = document.getElementById("skill-catalog"), start = document.getElementById("start-challenge"), section = document.getElementById("challenge-section"), questionBox = document.getElementById("challenge-questions"), saveSection = document.getElementById("save-section");
  let skills = [], currentSkill = 0, tier = "beginner", results = {};

  fetch("/api/skills-catalog").then(response => response.json()).then(data => {
    catalog.innerHTML = Object.entries(data.categories).map(([category, entries]) => `<fieldset class="skill-group"><legend>${category}</legend><div>${entries.map(skill => `<label class="skill-choice"><input type="checkbox" value="${skill}" ${data.current_skills.includes(skill) ? "checked" : ""}><span>${skill.replaceAll("-", " ")}</span></label>`).join("")}</div></fieldset>`).join("");
  }).catch(() => catalog.innerHTML = "<p>We couldn’t load the skill catalogue. Please refresh.</p>");

  start.addEventListener("click", () => {
    const selected = [...document.querySelectorAll(".skill-choice input:checked")].map(input => input.value);
    const custom = document.getElementById("custom-skills").value.split(",").map(value => value.trim().toLowerCase()).filter(Boolean);
    skills = [...new Set([...selected, ...custom])];
    const message = document.getElementById("selection-message");
    if (!skills.length) { message.textContent = "Choose at least one skill to begin."; message.className = "form-message error"; return; }
    if (skills.length > 3) { message.textContent = "Choose up to three skills for a focused adaptive challenge."; message.className = "form-message error"; return; }
    start.disabled = true; start.textContent = "Building your path…";
    fetch("/api/assessment/start", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({skills})}).then(response => response.json().then(data => ({ok:response.ok, data}))).then(({ok,data}) => {
      if (!ok) throw new Error(data.message); section.classList.remove("hidden"); document.getElementById("skill-selection").classList.add("hidden"); document.getElementById("challenge-eyebrow").textContent = `Skill 1 of ${skills.length}`; loadQuestion(); window.scrollTo({top:0,behavior:"smooth"});
    }).catch(error => { message.textContent=error.message; message.className="form-message error"; start.disabled=false; start.textContent="Build my adaptive challenge →"; });
  });

  function loadQuestion() {
    const skill=skills[currentSkill];
    document.getElementById("challenge-skill").textContent = `${display(skill)} · ${title(tier)} level`;
    document.getElementById("challenge-description").textContent = tier === "beginner" ? "Start with a foundation problem. Solve it to unlock the intermediate challenge." : tier === "intermediate" ? "You’ve unlocked an applied problem. Solve it to face the expert challenge." : "This final scenario tests judgement and the way you approach complexity.";
    document.getElementById("challenge-progress").textContent = `${currentSkill + 1} / ${skills.length}`;
    questionBox.innerHTML = `<div class="loading-card">Finding a ${title(tier).toLowerCase()} problem for ${display(skill)}…</div>`;
    fetch(`/api/assessment/question?skill=${encodeURIComponent(skill)}&tier=${tier}`).then(response => response.json().then(data=>({ok:response.ok,data}))).then(({ok,data}) => { if(!ok)throw new Error(data.message); renderQuestion(data.question); }).catch(error => questionBox.innerHTML=`<p class="form-message error">${error.message}</p>`);
  }
  function renderQuestion(question) {
    questionBox.innerHTML = `<fieldset class="challenge-question"><legend><span>${title(question.tier)}</span>${question.question}</legend>${question.options.map((option,index)=>`<label><input type="radio" name="answer" value="${index}"><i>${String.fromCharCode(65+index)}</i>${option}</label>`).join("")}<p id="question-feedback" class="form-message"></p><button class="btn primary" id="submit-answer">Check answer →</button></fieldset>`;
    let gradedResult = null;
    document.getElementById("submit-answer").addEventListener("click", () => {
      if (gradedResult) { advance(question, gradedResult); } else { grade(question, data => { gradedResult = data; }); }
    });
  }
  function grade(question, onGraded) {
    const selected=document.querySelector("input[name=answer]:checked"), feedback=document.getElementById("question-feedback"), button=document.getElementById("submit-answer");
    if(!selected){feedback.textContent="Select an answer before continuing."; feedback.className="form-message error";return;} button.disabled=true; button.textContent="Checking…";
    fetch("/api/assessment/grade",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({skill:question.skill,tier:question.tier,answer:selected.value})}).then(response=>response.json().then(data=>({ok:response.ok,data}))).then(({ok,data})=>{if(!ok)throw new Error(data.message); feedback.textContent=data.correct?`Correct — ${data.next_tier ? `you’ve unlocked the ${title(data.next_tier)} level.` : "you’ve completed this skill path."}`:`Not quite. You’ve demonstrated ${data.level} readiness in ${display(question.skill)}.`;feedback.className=`form-message ${data.correct?"success":"error"}`; button.textContent=data.complete?"Continue to next skill →":`Try ${title(data.next_tier)} level →`; button.disabled=false; onGraded(data);}).catch(error=>{feedback.textContent=error.message;feedback.className="form-message error";button.disabled=false;button.textContent="Check answer →";});
  }
  function advance(question, data) { if(data.complete){results[question.skill]=data.level;currentSkill++;if(currentSkill===skills.length)finishChallenges();else{tier="beginner";document.getElementById("challenge-eyebrow").textContent=`Skill ${currentSkill+1} of ${skills.length}`;loadQuestion();}}else{tier=data.next_tier;loadQuestion();} }
  function finishChallenges(){section.classList.add("hidden");saveSection.classList.remove("hidden");saveSection.querySelector("b").textContent=`Results ready: ${Object.entries(results).map(([skill,level])=>`${display(skill)} · ${level}`).join(" | ")}`;}
  document.getElementById("save-assessment").addEventListener("click",()=>{const button=document.getElementById("save-assessment");button.disabled=true;button.textContent="Saving your profile…";fetch("/api/assess",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}).then(response=>response.json().then(data=>({ok:response.ok,data}))).then(({ok,data})=>{if(!ok)throw new Error(data.message);window.location.href="/profile";}).catch(error=>{alert(error.message);button.disabled=false;button.textContent="Save my skill profile →";});});
  const display=value=>value.replaceAll("-"," ").replace(/\b\w/g,letter=>letter.toUpperCase()); const title=value=>value[0].toUpperCase()+value.slice(1);
});
