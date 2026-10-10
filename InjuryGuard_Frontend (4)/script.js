const API = "http://127.0.0.1:8000";
const KEY = "injuryguard_frontend_v1";

const $ = id => document.getElementById(id);

function normalizeEmail(value) {
  return String(value || "").trim().toLowerCase();
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  }[character]));
}

function toast(message) {
  const element = $("toast");

  if (!element) {
    console.log(message);
    return;
  }

  element.textContent = message;
  element.classList.add("show");

  setTimeout(() => element.classList.remove("show"), 3000);
}

function initials(name) {
  return String(name || "A")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map(word => word[0] || "")
    .join("")
    .toUpperCase();
}

function text(id, value) {
  if ($(id)) $(id).textContent = value ?? "";
}

function inputValue(id) {
  return $(id)?.value || "";
}

function setInput(id, value) {
  if ($(id)) $(id).value = value ?? "";
}

/* =========================================================
   DATE HELPERS
========================================================= */

function validDateOnly(value) {
  const raw = String(value || "").trim();

  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return "";

  const [year, month, day] = raw.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return "";
  }

  return raw;
}

// Timestamp records are compared using Indian calendar dates.
function dateOnly(value) {
  if (!value) return "";

  const raw = String(value).trim();

  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    return validDateOnly(raw);
  }

  // Do not guess exact dates from legacy year-only entries.
  if (!/^\d{4}-\d{2}-\d{2}T/.test(raw)) return "";

  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return "";

  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(date);

  const part = type => parts.find(p => p.type === type)?.value;

  return `${part("year")}-${part("month")}-${part("day")}`;
}

function formatDate(value, includeTime = false) {
  if (!value) return "Date not provided";

  const raw = String(value);

  if (validDateOnly(raw)) {
    return new Date(`${raw}T00:00:00+05:30`).toLocaleDateString(
      "en-GB",
      {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        year: "numeric"
      }
    );
  }

  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;

  const options = {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric"
  };

  if (includeTime) {
    options.hour = "2-digit";
    options.minute = "2-digit";
  }

  return date.toLocaleString("en-GB", options);
}

function isDateInRange(value, from, to) {
  if (!from && !to) return true;

  const date = dateOnly(value);

  if (!date) return false;
  if (from && date < from) return false;
  if (to && date > to) return false;

  return true;
}

function newestFirst(records) {
  return records.slice().sort((a, b) => {
    const first = new Date(a.date).getTime();
    const second = new Date(b.date).getTime();

    return (Number.isNaN(second) ? 0 : second) -
      (Number.isNaN(first) ? 0 : first);
  });
}

/* =========================================================
   APPLICATION STORAGE
========================================================= */

let S;

try {
  S = JSON.parse(localStorage.getItem(KEY) || "null");
} catch {
  S = null;
}

if (!S || typeof S !== "object" || Array.isArray(S)) {
  S = {};
}

S.user = S.user || null;

for (const field of [
  "accounts",
  "assessments",
  "medical",
  "feedback",
  "xrayHistory"
]) {
  S[field] = Array.isArray(S[field]) ? S[field] : [];
}

// Preserve the account still available in the old storage.
if (
  S.user &&
  !S.accounts.some(
    account =>
      normalizeEmail(account.email) === normalizeEmail(S.user.email)
  )
) {
  S.accounts.push({ ...S.user });
}

// Report dates are temporary and reset on account changes.
S.reportFilter = { from: "", to: "" };

let sessionVersion = 0;

function save() {
  if (S.user) {
    const index = S.accounts.findIndex(
      account =>
        normalizeEmail(account.email) === normalizeEmail(S.user.email)
    );

    if (index !== -1) {
      S.accounts[index] = { ...S.user };
    }
  }

  try {
    localStorage.setItem(KEY, JSON.stringify(S));
    return true;
  } catch (error) {
    console.error("Storage error:", error);
    toast("Could not save. Browser storage may be full.");
    return false;
  }
}

/* =========================================================
   STRICT ACCOUNT OWNERSHIP
========================================================= */

// Records without an explicit owner remain stored but hidden.
// Never assign an unknown old record to the current account.
function ownRecords(records) {
  const email = normalizeEmail(S.user?.email);

  if (!email) return [];

  return records.filter(record =>
    record &&
    normalizeEmail(record.athlete_email) === email
  );
}

function currentUserAssessments() {
  return newestFirst(ownRecords(S.assessments));
}

function currentUserMedical() {
  return ownRecords(S.medical);
}

function currentUserXrays() {
  return newestFirst(ownRecords(S.xrayHistory));
}

function currentUserFeedback() {
  return newestFirst(ownRecords(S.feedback));
}

function filteredReportData() {
  const { from, to } = S.reportFilter;

  return {
    from,
    to,
    assessments: currentUserAssessments().filter(
      record => isDateInRange(record.date, from, to)
    ),
    medical: currentUserMedical().filter(
      record => isDateInRange(record.date, from, to)
    ),
    xrays: currentUserXrays().filter(
      record => isDateInRange(record.date, from, to)
    )
  };
}

/* =========================================================
   AUTHENTICATION AND NAVIGATION
========================================================= */

function auth(mode) {
  $("loginForm")?.classList.toggle("hide", mode !== "login");
  $("signupForm")?.classList.toggle("hide", mode !== "signup");

  text(
    "authTitle",
    mode === "login" ? "Welcome back" : "Create your account"
  );

  text(
    "authText",
    mode === "login"
      ? "Sign in to your personal injury screening dashboard."
      : "Create your athlete account for this local demo."
  );
}

function page(name) {
  document.querySelectorAll(".page").forEach(element => {
    element.classList.add("hide");
  });

  $(name)?.classList.remove("hide");

  document.querySelectorAll("nav button").forEach(button => {
    button.classList.toggle("active", button.dataset.page === name);
  });

  const titles = {
    dashboard: "Dashboard",
    assessment: "New Assessment",
    profile: "My Profile",
    history: "Assessment History",
    medical: "Medical History",
    guidance: "Safety Guidance",
    feedbackPage: "Feedback",
    report: "Athlete Report"
  };

  text("pageTitle", titles[name] || "Dashboard");

  if (name === "report") renderReport();

  window.scrollTo(0, 0);
}

function clearAssessmentForm() {
  $("assessmentForm")?.reset();
  $("result")?.classList.add("hide");

  text("xrayName", "Choose a file");
  text("videoName", "Choose a file");

  if (S.user) setInput("sport", S.user.sport);
}

function resetSessionUI() {
  sessionVersion++;
  S.reportFilter = { from: "", to: "" };

  clearAssessmentForm();

  $("medicalForm")?.reset();
  $("feedbackForm")?.reset();

  setInput("reportFrom", "");
  setInput("reportTo", "");

  for (const id of [
    "historyList",
    "medicalList",
    "feedbackList",
    "recent",
    "xrayHistoryList",
    "reportXrayList",
    "reportMedicalList",
    "reportAssessmentList"
  ]) {
    if ($(id)) $(id).innerHTML = "";
  }
}

function openApp() {
  if (!S.user) {
    auth("login");
    return;
  }

  $("auth")?.classList.add("hide");
  $("app")?.classList.remove("hide");

  render();
  page("dashboard");
}

document.querySelectorAll("nav button").forEach(button => {
  button.onclick = event => {
    event.preventDefault();
    page(button.dataset.page);
  };
});

document.querySelectorAll("[data-go]").forEach(button => {
  button.onclick = event => {
    event.preventDefault();
    page(button.dataset.go);
  };
});

if ($("signupLink")) {
  $("signupLink").onclick = event => {
    event.preventDefault();
    auth("signup");
  };
}

if ($("loginLink")) {
  $("loginLink").onclick = event => {
    event.preventDefault();
    auth("login");
  };
}

if ($("loginForm")) {
  $("loginForm").onsubmit = event => {
    event.preventDefault();

    const email = normalizeEmail(inputValue("loginEmail"));
    const password = inputValue("loginPassword");

    const account = S.accounts.find(
      item =>
        normalizeEmail(item.email) === email &&
        item.password === password
    );

    if (!account) {
      toast("Email or password is incorrect.");
      return;
    }

    S.user = { ...account };

    resetSessionUI();
    save();
    openApp();

    toast("Logged in successfully");
  };
}

if ($("signupForm")) {
  $("signupForm").onsubmit = event => {
    event.preventDefault();

    const email = normalizeEmail(inputValue("suEmail"));

    if (S.accounts.some(
      account => normalizeEmail(account.email) === email
    )) {
      toast("Account already exists. Please sign in.");
      return;
    }

    const account = {
      name: inputValue("suName").trim(),
      age: inputValue("suAge"),
      gender: inputValue("suGender"),
      bloodGroup: inputValue("suBloodGroup"),
      email,
      password: inputValue("suPass"),
      sport: inputValue("suSport").trim(),
      phone: ""
    };

    if (!account.name || !account.email || !account.password) {
      toast("Please complete your account details.");
      return;
    }

    S.accounts.push({ ...account });
    S.user = { ...account };

    // Do not erase any other account's history.
    resetSessionUI();
    save();
    openApp();

    toast("Account created");
  };
}

if ($("logout")) {
  $("logout").onclick = event => {
    event.preventDefault();

    S.user = null;

    resetSessionUI();
    save();

    $("app")?.classList.add("hide");
    $("auth")?.classList.remove("hide");

    setInput("loginPassword", "");
    auth("login");

    toast("Logged out");
  };
}

/* =========================================================
   PROFILE
========================================================= */

if ($("profileForm")) {
  $("profileForm").onsubmit = event => {
    event.preventDefault();

    if (!S.user) return;

    Object.assign(S.user, {
      name: inputValue("profileName").trim(),
      age: inputValue("profileAge"),
      gender: inputValue("profileGender"),
      bloodGroup: inputValue("profileBloodGroup"),
      sport: inputValue("profileSport").trim(),
      phone: inputValue("profilePhone").trim()
    });

    save();
    render();

    toast("Profile saved");
  };
}

/* =========================================================
   DASHBOARD AND HISTORY
========================================================= */

function assessmentCard(record) {
  const level = String(record.risk_level || "UNKNOWN").toUpperCase();

  const badgeClass = {
    LOW: "low",
    MODERATE: "moderate",
    HIGH: "high"
  }[level] || "";

  return `
    <article class="history">
      <div>
        <strong>${esc(record.sport || "Assessment")}</strong>
        <small>${esc(formatDate(record.date, true))}</small>
        <small>
          Pain: ${esc(record.pain_level ?? "—")}/10
          · ${esc(record.pain_location || "Not specified")}
        </small>
        <small>
          Media:
          ${record.xray ? "X-ray " : ""}
          ${record.video ? "Video" : ""}
          ${!record.xray && !record.video ? "Body details only" : ""}
        </small>
        ${
          record.xray_history_count
            ? `<small>X-ray records used:
                ${esc(record.xray_history_count)}</small>`
            : ""
        }
      </div>
      <span class="badge ${badgeClass}">
        ${esc(record.risk_percentage ?? "—")}% · ${esc(level)}
      </span>
    </article>
  `;
}

function render() {
  const user = S.user;
  if (!user) return;

  const assessments = currentUserAssessments();
  const medical = currentUserMedical();
  const feedback = currentUserFeedback();
  const latest = assessments[0];

  text("heroName", user.name || "Athlete");
  text("sideName", user.name || "Athlete");
  text("sideSport", user.sport || "Athlete");
  text("sideAvatar", initials(user.name));

  if ($("topUser")) {
    $("topUser").innerHTML = `
      <span>${esc(initials(user.name))}</span>
      <b>${esc(user.name)}
        <small>${esc(user.email)}</small>
      </b>
    `;
  }

  text("profileAvatar", initials(user.name));
  text("profileNameDisplay", user.name || "Athlete");
  text("profileEmail", user.email);

  for (const [id, value] of [
    ["profileName", user.name],
    ["profileAge", user.age],
    ["profileGender", user.gender],
    ["profileBloodGroup", user.bloodGroup],
    ["profileSport", user.sport],
    ["profilePhone", user.phone]
  ]) {
    setInput(id, value);
  }

  if (!inputValue("sport")) setInput("sport", user.sport);

  text("countAssess", assessments.length);
  text("countMedical", medical.length);
  text("dashboardXrayCount", currentUserXrays().length);

  text(
    "lastRisk",
    latest ? `${latest.risk_percentage}%` : "—"
  );

  text(
    "lastDate",
    latest ? formatDate(latest.date) : "No assessment yet"
  );

  if ($("recent")) {
    $("recent").innerHTML = assessments.length
      ? assessments.slice(0, 4).map(assessmentCard).join("")
      : "<p>No assessments yet.</p>";
  }

  if ($("historyList")) {
    $("historyList").innerHTML = assessments.length
      ? assessments.map(assessmentCard).join("")
      : '<div class="form-card">No saved assessments yet.</div>';
  }

  if ($("medicalList")) {
    $("medicalList").innerHTML = medical.length
      ? medical.map((record, index) => `
          <article class="history">
            <div>
              <strong>${esc(record.condition)}</strong>
              <small>
                ${esc(record.area)}
                · ${esc(formatDate(record.date))}
              </small>
              <small>${esc(record.notes || "No notes")}</small>
            </div>
            <button
              type="button"
              class="secondary"
              onclick="delMed(${index})"
            >Delete</button>
          </article>
        `).join("")
      : '<div class="form-card">No medical history entries.</div>';
  }

  if ($("feedbackList")) {
    $("feedbackList").innerHTML = feedback.length
      ? feedback.map(record => `
          <article class="feedback">
            <div>
              <strong>${esc(record.rating)}</strong>
              <small>${esc(formatDate(record.date, true))}</small>
              <p>${esc(record.text)}</p>
            </div>
          </article>
        `).join("")
      : '<div class="form-card">No feedback saved yet.</div>';
  }

  renderXrayHistory();
  renderReport();
}

/* =========================================================
   MEDICAL HISTORY
========================================================= */

if ($("medDate")) $("medDate").type = "date";

if ($("medicalForm")) {
  $("medicalForm").onsubmit = event => {
    event.preventDefault();

    if (!S.user) {
      toast("Please log in first.");
      return;
    }

    const date = validDateOnly(inputValue("medDate"));

    if (!date) {
      toast("Please select the medical record date.");
      return;
    }

    S.medical.unshift({
      athlete_email: normalizeEmail(S.user.email),
      created_at: new Date().toISOString(),
      condition: inputValue("medCondition").trim(),
      area: inputValue("medArea").trim(),
      date,
      notes: inputValue("medNotes").trim()
    });

    save();
    event.target.reset();
    render();

    toast("Medical history saved");
  };
}

window.delMed = function(index) {
  const record = currentUserMedical()[index];

  if (!record) return;

  const actualIndex = S.medical.indexOf(record);
  if (actualIndex === -1) return;

  S.medical.splice(actualIndex, 1);

  save();
  render();

  toast("Medical history deleted");
};

/* =========================================================
   X-RAY HISTORY
========================================================= */

function renderXrayHistory() {
  const records = currentUserXrays();

  text(
    "xrayCount",
    `${records.length} ${records.length === 1 ? "X-ray" : "X-rays"}`
  );

  text("dashboardXrayCount", records.length);

  if (!$("xrayHistoryList")) return;

  $("xrayHistoryList").innerHTML = records.length
    ? records.map((record, index) => `
        <article class="xray-history-item">
          <div class="xray-history-icon">X-ray</div>
          <div class="xray-history-info">
            <strong>${esc(formatDate(record.date))}</strong>
            <small>
              Body part: ${esc(record.bodyPart || "Not specified")}
            </small>
            <small>Status: ${esc(record.status || "Unknown")}</small>
            <small>
              Severity: ${esc(record.severity || "Unknown")}
            </small>
            ${record.notes ? `<p>${esc(record.notes)}</p>` : ""}
            <small class="xray-file-name">
              ${esc(record.fileName || "X-ray image")}
            </small>
          </div>
          <button
            type="button"
            class="secondary delete-xray"
            onclick="deleteXray(${index})"
          >Delete</button>
        </article>
      `).join("")
    : '<div class="empty-xray">No X-rays added yet.</div>';
}

window.deleteXray = function(index) {
  const record = currentUserXrays()[index];

  if (!record) return;

  const actualIndex = S.xrayHistory.indexOf(record);
  if (actualIndex === -1) return;

  S.xrayHistory.splice(actualIndex, 1);

  save();
  render();

  toast("X-ray removed");
};

if ($("addXray")) {
  $("addXray").onclick = event => {
    event.preventDefault();

    if (!S.user) {
      toast("Please log in first.");
      return;
    }

    const file = $("xray")?.files?.[0];
    const date = validDateOnly(inputValue("xrayDate"));
    const bodyPart = inputValue("xrayBodyPart");
    const status = inputValue("xrayStatus");

    if (!file) {
      toast("Please choose an X-ray image first.");
      return;
    }

    if (!date || !bodyPart || !status) {
      toast("Select X-ray date, body part and injury status.");
      return;
    }

    S.xrayHistory.unshift({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      athlete_email: normalizeEmail(S.user.email),
      created_at: new Date().toISOString(),
      date,
      bodyPart,
      status,
      severity: inputValue("xraySeverity"),
      notes: inputValue("xrayNotes").trim(),
      fileName: file.name
    });

    save();

    for (const id of [
      "xray",
      "xrayDate",
      "xrayBodyPart",
      "xrayStatus",
      "xraySeverity",
      "xrayNotes"
    ]) {
      setInput(id, "");
    }

    text("xrayName", "Choose a file");

    render();
    toast("X-ray added to your history");
  };
}

/* =========================================================
   FEEDBACK
========================================================= */

if ($("feedbackForm")) {
  $("feedbackForm").onsubmit = event => {
    event.preventDefault();

    if (!S.user) return;

    S.feedback.unshift({
      athlete_email: normalizeEmail(S.user.email),
      rating: inputValue("rating"),
      text: inputValue("feedbackText"),
      date: new Date().toISOString()
    });

    save();
    event.target.reset();
    render();

    toast("Feedback saved");
  };
}

/* =========================================================
   FILE INPUTS
========================================================= */

for (const [fileId, nameId] of [
  ["xray", "xrayName"],
  ["video", "videoName"]
]) {
  if ($(fileId)) {
    $(fileId).onchange = event => {
      text(
        nameId,
        event.target.files?.[0]?.name || "Choose a file"
      );
    }
  }
}

/* =========================================================
   AI ASSESSMENT
========================================================= */

if ($("assessmentForm")) {
  $("assessmentForm").onsubmit = async event => {
    event.preventDefault();

    if (!S.user) {
      toast("Please log in first.");
      return;
    }

    const user = { ...S.user };
    const submittingSession = sessionVersion;
    const button = $("analyze");

    const fields = [
      "sport",
      "intensity",
      "previous_injury",
      "recovery_days",
      "pain_location",
      "pain_level",
      "muscle_condition",
      "ligament_stability",
      "mental_readiness",
      "sleep_quality",
      "feedback"
    ];

    // Capture input values before waiting for the API.
    const values = Object.fromEntries(
      fields.map(field => [field, inputValue(field)])
    );

    const xrayFile = $("xray")?.files?.[0];
    const videoFile = $("video")?.files?.[0];

    const xraySnapshot = currentUserXrays().map(record => ({
      date: record.date,
      bodyPart: record.bodyPart,
      status: record.status,
      severity: record.severity,
      notes: record.notes
    }));

    if (button) {
      button.disabled = true;
      button.textContent = "Analyzing...";
    }

    try {
      const formData = new FormData();

      for (const [field, value] of Object.entries(values)) {
        formData.append(field, value);
      }

      const athleteFields = {
        athlete_name: user.name,
        athlete_email: normalizeEmail(user.email),
        athlete_age: user.age,
        athlete_gender: user.gender,
        athlete_blood_group: user.bloodGroup,
        athlete_sport: user.sport,
        athlete_phone: user.phone
      };

      for (const [field, value] of Object.entries(athleteFields)) {
        formData.append(field, value ?? "");
      }

      formData.append(
        "xray_history",
        JSON.stringify(xraySnapshot.map(record => ({
          date: record.date,
          body_part: record.bodyPart,
          status: record.status,
          severity: record.severity,
          notes: record.notes
        })))
      );

      if (xrayFile) formData.append("xray", xrayFile);
      if (videoFile) formData.append("video", videoFile);

      const response = await fetch(
        `${API}/api/combined-assessment`,
        {
          method: "POST",
          body: formData
        }
      );

      let data;

      try {
        data = await response.json();
      } catch {
        throw new Error("FastAPI returned an invalid response.");
      }

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : data.message || "Could not complete assessment."
        );
      }

      if (
        submittingSession !== sessionVersion ||
        normalizeEmail(S.user?.email) !== normalizeEmail(user.email)
      ) {
        throw new Error(
          "Login changed during assessment. Please submit again."
        );
      }

      const assessment = {
        ...data,
        ...values,
        date: new Date().toISOString(),
        athlete_name: user.name,
        athlete_email: normalizeEmail(user.email),
        athlete_age: user.age,
        athlete_gender: user.gender,
        athlete_blood_group: user.bloodGroup,
        athlete_phone: user.phone,
        sport: values.sport || user.sport,
        xray: Boolean(xrayFile),
        video: Boolean(videoFile),
        xray_history_count: xraySnapshot.length,
        xray_history: xraySnapshot
      };

      S.assessments.unshift(assessment);
      save();

      render();
      showResult(assessment);

      toast("Assessment completed");
    } catch (error) {
      console.error("Assessment error:", error);
      toast(error.message || "Check whether FastAPI is running.");
    } finally {
      if (button) {
        button.disabled = false;
        button.textContent = "Analyze assessment";
      }
    }
  };
}

function showResult(result) {
  $("result")?.classList.remove("hide");

  const level = String(result.risk_level || "UNKNOWN").toUpperCase();

  text("percent", `${result.risk_percentage ?? "—"}%`);
  text("level", level);
  text("message", result.message || "Screening result generated.");

  if ($("level")) {
    const badgeClass = {
      LOW: "low",
      MODERATE: "moderate",
      HIGH: "high"
    }[level] || "";

    $("level").className = `badge ${badgeClass}`;
  }

  let dos = [
    "Monitor how you feel during and after activity.",
    "Allow adequate recovery before increasing training load.",
    "Follow normal warm-up and recovery practices."
  ];

  const avoid = [
    "Avoid pushing through significant or worsening pain.",
    "Do not treat the AI score as a diagnosis.",
    "Seek professional evaluation for severe or persistent symptoms."
  ];

  if (level === "HIGH") {
    dos = [
      "Pause demanding activity and pay attention to symptoms.",
      "Consider evaluation by a qualified healthcare professional.",
      "Keep the result to discuss with a professional."
    ];
  } else if (level === "MODERATE") {
    dos = [
      "Monitor symptoms closely and allow adequate recovery.",
      "Use a gradual return to activity.",
      "Seek professional advice if symptoms persist or worsen."
    ];
  }

  if ($("doList")) {
    $("doList").innerHTML = dos.map(
      item => `<li>${esc(item)}</li>`
    ).join("");
  }

  if ($("avoidList")) {
    $("avoidList").innerHTML = avoid.map(
      item => `<li>${esc(item)}</li>`
    ).join("");
  }

  $("result")?.scrollIntoView({ behavior: "smooth" });
}

if ($("newCheck")) {
  $("newCheck").onclick = event => {
    event.preventDefault();
    clearAssessmentForm();
  };
}

/* =========================================================
   REPORT DATE CONTROLS
========================================================= */

// Add missing date controls to the existing report HTML.
if ($("report") && !$("reportFrom")) {
  const controls = document.createElement("div");
  controls.className = "form-card";

  controls.innerHTML = `
    <h3>Report period</h3>
    <div class="grid2">
      <label>
        From date
        <input id="reportFrom" type="date">
      </label>
      <label>
        To date
        <input id="reportTo" type="date">
      </label>
    </div>
    <div class="actions">
      <button id="applyReportFilter" type="button">
        Apply date range
      </button>
      <button
        id="clearReportFilter"
        type="button"
        class="secondary"
      >Full report</button>
    </div>
    <p id="reportPeriod"></p>
  `;

  $("report").prepend(controls);
}

function setReportDateRange(from, to) {
  if (!validDateOnly(from) || !validDateOnly(to)) {
    toast("Please select both From and To dates.");
    return false;
  }

  if (from > to) {
    toast("From date cannot be after To date.");
    return false;
  }

  S.reportFilter = { from, to };
  renderReport();

  return true;
}

function applySelectedReportDates() {
  const from = inputValue("reportFrom");
  const to = inputValue("reportTo");

  if (!from && !to) {
    S.reportFilter = { from: "", to: "" };
    renderReport();
    return true;
  }

  return setReportDateRange(from, to);
}

if ($("applyReportFilter")) {
  $("applyReportFilter").onclick = event => {
    event.preventDefault();

    setReportDateRange(
      inputValue("reportFrom"),
      inputValue("reportTo")
    );
  };
}

if ($("clearReportFilter")) {
  $("clearReportFilter").onclick = event => {
    event.preventDefault();

    S.reportFilter = { from: "", to: "" };

    setInput("reportFrom", "");
    setInput("reportTo", "");

    renderReport();

    toast("Showing full history for your account");
  };
}

/* =========================================================
   REPORT PREVIEW
========================================================= */

function renderReport() {
  const user = S.user;
  if (!user) return;

  const report = filteredReportData();
  const latest = report.assessments[0];

  for (const [id, value] of [
    ["reportName", user.name || "Athlete"],
    ["reportFullName", user.name || "Not provided"],
    ["reportAge", user.age || "Not provided"],
    ["reportGender", user.gender || "Not provided"],
    ["reportBloodGroup", user.bloodGroup || "Not provided"],
    ["reportPrimarySport", user.sport || "Not provided"],
    ["reportSport", user.sport || "Not provided"],
    ["reportEmail", user.email || "Not provided"],
    ["reportAvatar", initials(user.name)]
  ]) {
    text(id, value);
  }

  text(
    "reportPeriod",
    report.from && report.to
      ? `${formatDate(report.from)} to ${formatDate(report.to)}`
      : "Full history for this account"
  );

  text("reportAssessmentCount", report.assessments.length);
  text("reportXrayCount", report.xrays.length);
  text("reportMedicalCount", report.medical.length);

  text(
    "reportRiskScore",
    latest ? `${latest.risk_percentage ?? "—"}%` : "—"
  );

  text(
    "reportRiskLevel",
    latest ? latest.risk_level : "No assessment"
  );

  text(
    "reportAssessmentDate",
    latest ? formatDate(latest.date, true) : "No assessment"
  );

  text(
    "reportRiskMessage",
    latest
      ? latest.message || "Assessment completed."
      : "No assessment in this period."
  );

  if ($("reportXrayList")) {
    $("reportXrayList").innerHTML = report.xrays.length
      ? report.xrays.map(record => `
          <div class="report-item">
            <strong>${esc(formatDate(record.date))}</strong>
            <small>
              Body part: ${esc(record.bodyPart || "Not specified")}
            </small>
            <small>Status: ${esc(record.status || "Unknown")}</small>
            <small>
              Severity: ${esc(record.severity || "Unknown")}
            </small>
            ${record.notes
              ? `<small>Notes: ${esc(record.notes)}</small>`
              : ""}
          </div>
        `).join("")
      : '<div class="ig-record-empty">No X-rays in this period.</div>';
  }

  if ($("reportMedicalList")) {
    $("reportMedicalList").innerHTML = report.medical.length
      ? report.medical.map(record => `
          <div class="report-item">
            <strong>${esc(record.condition || "Medical record")}</strong>
            <small>Area: ${esc(record.area || "Not specified")}</small>
            <small>Date: ${esc(formatDate(record.date))}</small>
            <small>Notes: ${esc(record.notes || "No notes")}</small>
          </div>
        `).join("")
      : '<div class="ig-record-empty">No medical records in this period.</div>';
  }

  if ($("reportAssessmentList")) {
    $("reportAssessmentList").innerHTML = report.assessments.length
      ? report.assessments.map(record => `
          <div class="report-item">
            <strong>${esc(record.sport || "Assessment")}</strong>
            <small>Date: ${esc(formatDate(record.date, true))}</small>
            <small>Risk: ${esc(record.risk_percentage ?? "—")}%</small>
            <small>Level: ${esc(record.risk_level || "Unknown")}</small>
          </div>
        `).join("")
      : '<div class="ig-record-empty">No assessments in this period.</div>';
  }

  // Update the summary cards in the original report HTML.
  const summaryValues = [
    latest ? `${latest.risk_percentage ?? "—"}%` : "—",
    latest ? latest.risk_level : "No assessment",
    report.xrays.length,
    report.assessments.length
  ];

  document.querySelectorAll(
    "#report .ig-summary-card strong"
  ).forEach((element, index) => {
    if (index < summaryValues.length) {
      element.textContent = summaryValues[index];
    }
  });
}

/* =========================================================
   PRINT / SAVE AS PDF
========================================================= */

function reportTable(headers, rows) {
  if (!rows.length) {
    return "<p>No records in this period.</p>";
  }

  return `
    <table>
      <thead>
        <tr>
          ${headers.map(header => `<th>${esc(header)}</th>`).join("")}
        </tr>
      </thead>
      <tbody>
        ${rows.map(row => `
          <tr>
            ${row.map(value => `<td>${esc(value ?? "—")}</td>`).join("")}
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function exportPersonalReport(event) {
  event?.preventDefault();

  if (!S.user) {
    toast("Please log in first.");
    return;
  }

  if (!applySelectedReportDates()) return;

  // Preview and export use exactly the same filtered records.
  const user = { ...S.user };
  const report = filteredReportData();
  const latest = report.assessments[0];

  const reportWindow = window.open("", "_blank");

  if (!reportWindow) {
    toast("Allow popups to print or save your report.");
    return;
  }

  const period = report.from && report.to
    ? `${formatDate(report.from)} to ${formatDate(report.to)}`
    : "Full history";

  const html = `
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="UTF-8">
        <title>InjuryGuard ${esc(user.name)} Report</title>
        <style>
          * { box-sizing: border-box; }
          body {
            font-family: Arial, sans-serif;
            font-size: 12px;
            line-height: 1.5;
            color: #18232b;
            margin: 32px;
          }
          h1 { font-size: 24px; margin-bottom: 4px; }
          h2 { font-size: 16px; margin-top: 25px; }
          p { margin: 8px 0; }
          small { color: #56616a; }
          table {
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0;
          }
          th, td {
            border: 1px solid #d9dfe4;
            padding: 8px;
            text-align: left;
            vertical-align: top;
            overflow-wrap: anywhere;
          }
          th { background: #eef2f5; }
          thead { display: table-header-group; }
          tr { break-inside: avoid; }
          h2 { break-after: avoid; }
          button {
            padding: 10px 16px;
            cursor: pointer;
            margin-bottom: 15px;
          }
          @page { size: A4; margin: 15mm; }
          @media print {
            body { margin: 0; }
            button { display: none; }
          }
        </style>
      </head>
      <body>
        <button onclick="window.print()">Print / Save as PDF</button>

        <h1>INJURYGUARD AI</h1>
        <p>Athlete screening report</p>
        <p><b>${esc(user.name)}</b> · ${esc(user.email)}</p>
        <p><b>Report period:</b> ${esc(period)}</p>
        <p><b>Assessment visits:</b> ${report.assessments.length}</p>
        <small>
          Generated: ${esc(formatDate(new Date().toISOString(), true))}
          · Records saved in this browser for this account
        </small>

        <h2>1. Athlete information</h2>
        ${reportTable(["Field", "Details"], [
          ["Full name", user.name],
          ["Age", user.age],
          ["Gender", user.gender],
          ["Blood group", user.bloodGroup],
          ["Primary sport", user.sport],
          ["Email", user.email]
        ])}

        <h2>2. Latest screening in this period</h2>
        ${latest
          ? reportTable(
              ["Assessment date", "Sport", "Pain", "Risk", "Level"],
              [[
                formatDate(latest.date, true),
                latest.sport,
                `${latest.pain_level ?? "—"}/10`,
                `${latest.risk_percentage ?? "—"}%`,
                latest.risk_level
              ]]
            )
          : "<p>No assessments in this period.</p>"
        }

        <h2>3. X-ray history</h2>
        ${reportTable(
          ["X-ray date", "Body part", "Status", "Severity", "Notes"],
          report.xrays.map(record => [
            formatDate(record.date),
            record.bodyPart,
            record.status,
            record.severity,
            record.notes
          ])
        )}

        <h2>4. Medical history</h2>
        ${reportTable(
          ["Record date", "Condition", "Body area", "Notes"],
          report.medical.map(record => [
            formatDate(record.date),
            record.condition,
            record.area,
            record.notes
          ])
        )}

        <h2>5. Assessment visit history</h2>
        ${reportTable(
          ["Visit date", "Sport", "Pain", "Risk", "Level"],
          report.assessments.map(record => [
            formatDate(record.date, true),
            record.sport,
            `${record.pain_level ?? "—"}/10`,
            `${record.risk_percentage ?? "—"}%`,
            record.risk_level
          ])
        )}

        <h2>Screening information</h2>
        <p>
          This AI-assisted screening summary is not a medical diagnosis.
          Consult a qualified healthcare professional for medical evaluation.
        </p>
      </body>
    </html>
  `;

  reportWindow.document.write(html);
  reportWindow.document.close();

  // Keep the visible print button available if automatic print is blocked.
  reportWindow.setTimeout(() => {
    reportWindow.focus();
    reportWindow.print();
  }, 300);
}

for (const id of [
  "downloadReport",
  "printReport",
  "downloadReportBottom",
  "printReportBottom"
]) {
  if ($(id)) $(id).onclick = exportPersonalReport;
}

/* =========================================================
   START APPLICATION
========================================================= */

save();

if (S.user) {
  openApp();
} else {
  $("app")?.classList.add("hide");
  $("auth")?.classList.remove("hide");
  auth("login");
}