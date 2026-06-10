const state = {
  templates: [],
  currentTemplate: null,
  run: null,
  events: [],
};

const byId = (id) => document.getElementById(id);
const titleCase = (value = "") =>
  value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());

function setHidden(id, hidden) {
  byId(id).hidden = hidden;
}

function statusClass(value) {
  return `status-${String(value || "").toLowerCase()}`;
}

function badge(element, value) {
  element.className = `status-badge ${statusClass(value)}`;
  element.textContent = titleCase(value);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => {
    toast.hidden = true;
  }, 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).join("; ")
      : body.detail || `Request failed with status ${response.status}`;
    throw new Error(detail);
  }
  return body;
}

async function loadTemplates() {
  const payload = await api("/v1/demo/cases");
  state.templates = payload.cases;
  const select = byId("case-template");
  select.innerHTML = state.templates
    .map(
      (item, index) =>
        `<option value="${index}">${escapeHtml(item.case.case_id)} · ${escapeHtml(item.case.title)}</option>`,
    )
    .join("");
  select.value = "8";
  selectTemplate(8);
}

function selectTemplate(index) {
  const template = state.templates[Number(index)];
  if (!template) return;
  state.currentTemplate = template;
  const caseData = template.case;
  byId("case-json").value = JSON.stringify(caseData, null, 2);
  byId("case-id-badge").textContent = caseData.case_id;
  byId("fact-owner").textContent = caseData.business_owner;
  byId("fact-feature").textContent = titleCase(caseData.feature_type);
  byId("fact-market").textContent = caseData.deployment.target_markets.join(", ");
  byId("fact-expected").textContent = titleCase(template.expected.outcome);
  byId("template-rationale").textContent = template.rationale;
  byId("intake-error").hidden = true;
}

function parseCase() {
  try {
    return JSON.parse(byId("case-json").value);
  } catch (error) {
    throw new Error(`Invalid case JSON: ${error.message}`);
  }
}

async function runReview() {
  const button = byId("run-review");
  const errorBox = byId("intake-error");
  errorBox.hidden = true;
  button.disabled = true;
  button.textContent = "Review running...";
  setHidden("empty-state", true);
  setHidden("results", true);
  setHidden("loading-state", false);

  try {
    const caseData = parseCase();
    const key = `console:${caseData.case_id}:${Date.now()}`;
    state.run = await api("/v1/workflows", {
      method: "POST",
      body: JSON.stringify({
        case: caseData,
        idempotency_key: key,
        top_k: 8,
      }),
    });
    const eventPayload = await api(`/v1/workflows/${state.run.run_id}/events`);
    state.events = eventPayload.events;
    state.chainValid = eventPayload.chain_valid;
    renderResults();
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
    setHidden("empty-state", false);
  } finally {
    setHidden("loading-state", true);
    button.disabled = false;
    button.textContent = "Run compliance review";
  }
}

function renderResults() {
  const run = state.run;
  if (!run?.analysis || !run?.enforcement || !run?.audit || !run?.record) {
    throw new Error("The workflow did not produce a complete review record.");
  }
  setHidden("results", false);
  const outcome = run.final_outcome || run.enforcement.outcome;
  badge(byId("status-badge"), run.status);
  byId("run-id").textContent = run.run_id;
  byId("decision-title").textContent = `${titleCase(outcome)} · ${run.case.title}`;
  byId("decision-summary").textContent = run.enforcement.summary;
  byId("risk-level").textContent = titleCase(run.enforcement.risk_level);
  byId("metric-legal").textContent = run.analysis.legal.findings.length;
  byId("metric-policy").textContent = run.analysis.policy.findings.length;
  byId("metric-controls").textContent = run.enforcement.required_controls.length;
  byId("metric-audit").textContent = run.audit.checks.length;
  byId("winning-rule").textContent = run.enforcement.winning_rule_id;
  const winning = run.enforcement.rule_trace.find(
    (trace) => trace.rule_id === run.enforcement.winning_rule_id,
  );
  byId("rule-explanation").textContent = winning?.explanation || run.enforcement.summary;
  byId("ruleset-version").textContent =
    `${run.enforcement.ruleset_id}@${run.enforcement.ruleset_version}`;
  byId("evidence-version").textContent = run.analysis.evidence.index_version;
  byId("record-id").textContent = run.record.record_id;
  byId("hash-status").textContent = `SHA-256 · ${run.record.content_hash.slice(0, 16)}...`;
  renderQuestions();
  renderFindings("legal");
  renderFindings("policy");
  renderEvidence();
  renderControls();
  renderAudit();
  renderTimeline();
  setHidden("approval-panel", run.status !== "awaiting_approval");
  activateTab("overview");
}

function renderQuestions() {
  const questions = [
    ...(state.run.case.open_questions || []),
    ...(state.run.case.known_limitations || []),
    ...(state.run.enforcement.open_questions || []),
  ];
  const unique = [...new Set(questions)];
  byId("open-questions").innerHTML = unique.length
    ? unique.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>No unresolved questions were recorded.</li>";
}

function renderFindings(agent) {
  const analysis = state.run.analysis[agent];
  byId(`${agent}-summary`).textContent = analysis.summary;
  byId(`${agent}-findings`).innerHTML = analysis.findings
    .map((finding) => {
      const citations = finding.citations
        .map(
          (citation) => `
            <div class="citation">
              <strong>${escapeHtml(citation.source_id)} · ${escapeHtml(citation.section)}</strong><br>
              ${escapeHtml(citation.excerpt)}
            </div>`,
        )
        .join("");
      return `
        <article class="finding-card">
          <div class="card-meta">
            <span class="tag">${escapeHtml(finding.finding_id)}</span>
            <span class="tag">${escapeHtml(titleCase(finding.category))}</span>
            <span class="tag severity-${escapeHtml(finding.severity)}">${escapeHtml(finding.severity)}</span>
            <span class="tag">${Math.round(finding.confidence * 100)}% confidence</span>
          </div>
          <p><strong>${escapeHtml(finding.statement)}</strong></p>
          <p>${escapeHtml(finding.rationale)}</p>
          ${citations}
        </article>`;
    })
    .join("");
}

function renderEvidence() {
  const matches = state.run.analysis.evidence.matches;
  byId("evidence-count").textContent = `${matches.length} sections`;
  byId("evidence-list").innerHTML = matches
    .map(
      (match) => `
        <article class="evidence-card">
          <header>
            <div>
              <h4>${escapeHtml(match.chunk.section_id)} · ${escapeHtml(match.chunk.section_title)}</h4>
              <div class="card-meta">
                <span class="tag">${escapeHtml(match.chunk.policy_id)}@${escapeHtml(match.chunk.policy_version)}</span>
                ${match.chunk.categories.map((category) => `<span class="tag">${escapeHtml(titleCase(category))}</span>`).join("")}
              </div>
            </div>
            <span class="score">Score ${escapeHtml(match.score)}</span>
          </header>
          <p>${escapeHtml(match.chunk.text)}</p>
          <p class="field-help">Matched on: ${escapeHtml(match.matched_on.join(" · "))}</p>
        </article>`,
    )
    .join("");
}

function renderControls() {
  const controls = state.run.enforcement.required_controls;
  byId("controls-list").innerHTML = controls.length
    ? controls
        .map(
          (control) => `
          <article class="control-card ${control.blocking ? "blocking" : ""}">
            <header>
              <div>
                <h4>${escapeHtml(control.control_id)} · ${escapeHtml(control.title)}</h4>
                <div class="card-meta">
                  <span class="tag">${escapeHtml(control.owner)}</span>
                  <span class="tag">${control.blocking ? "Blocking" : "Non-blocking"}</span>
                </div>
              </div>
            </header>
            <p>${escapeHtml(control.description)}</p>
            <div class="citation"><strong>Verification</strong><br>${escapeHtml(control.verification_method)}</div>
          </article>`,
        )
        .join("")
    : '<p class="field-help">No blocking controls are required for this outcome.</p>';
}

function renderAudit() {
  badge(byId("audit-verdict"), state.run.audit.verdict);
  byId("audit-list").innerHTML = state.run.audit.checks
    .map(
      (check) => `
        <article class="audit-card ${escapeHtml(check.status)}">
          <span class="audit-icon">${check.status === "pass" ? "✓" : "!"}</span>
          <div>
            <h4>${escapeHtml(check.title)}</h4>
            <p>${escapeHtml(check.details)}</p>
          </div>
        </article>`,
    )
    .join("");
}

function renderTimeline() {
  byId("chain-status").textContent = state.chainValid ? "Hash chain valid" : "Chain invalid";
  byId("timeline-list").innerHTML = state.events
    .map(
      (event) => `
        <li>
          <span class="timeline-dot">${event.sequence}</span>
          <div>
            <h4>${escapeHtml(titleCase(event.event_type))}</h4>
            <p>${escapeHtml(titleCase(event.stage))} · ${escapeHtml(JSON.stringify(event.payload))}</p>
          </div>
          <time>${escapeHtml(new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</time>
        </li>`,
    )
    .join("");
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === name);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${name}`);
  });
}

async function submitDecision(action) {
  if (!state.run) return;
  const reviewer = byId("reviewer-name").value.trim();
  const rationale = byId("review-rationale").value.trim();
  const payload = { action, reviewer, rationale };
  if (action === "override") payload.override_outcome = "conditional_allow";

  try {
    state.run = await api(`/v1/workflows/${state.run.run_id}/decision`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const eventPayload = await api(`/v1/workflows/${state.run.run_id}/events`);
    state.events = eventPayload.events;
    state.chainValid = eventPayload.chain_valid;
    renderResults();
    showToast(`Human decision recorded: ${titleCase(action)}`);
  } catch (error) {
    showToast(error.message);
  }
}

byId("case-template").addEventListener("change", (event) => {
  selectTemplate(event.target.value);
});
byId("format-json").addEventListener("click", () => {
  try {
    byId("case-json").value = JSON.stringify(parseCase(), null, 2);
    byId("intake-error").hidden = true;
  } catch (error) {
    byId("intake-error").textContent = error.message;
    byId("intake-error").hidden = false;
  }
});
byId("run-review").addEventListener("click", runReview);
document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => activateTab(button.dataset.tab));
});
byId("approve-review").addEventListener("click", () => submitDecision("approve"));
byId("override-review").addEventListener("click", () => submitDecision("override"));
byId("reject-review").addEventListener("click", () => submitDecision("reject"));

loadTemplates().catch((error) => {
  byId("intake-error").textContent = error.message;
  byId("intake-error").hidden = false;
});
