const state = {
  data: null,
  page: "overview",
  csrfToken: null,
  projectId: Number(localStorage.getItem("activeProject")) || null,
  sidebarCollapsed: localStorage.getItem("sidebarCollapsed") === "true",
};

const pages = {
  overview: { label: "项目总览", description: "掌握课程项目、团队协作与评审进展", icon: "dashboard" },
  projects: { label: "任务与迭代", description: "管理项目要求、阶段里程碑与评分权重", icon: "project" },
  teams: { label: "团队与提交", description: "查看团队构成、迭代成果与版本状态", icon: "team" },
  reviews: { label: "同伴互评", description: "完成分配任务并跟踪互评进度", icon: "review" },
  grades: { label: "评分与成绩", description: "录入过程分和终评分，核对成绩构成", icon: "grade" },
  logs: { label: "过程日志", description: "追溯发布、提交、互评与评分操作", icon: "log" },
};

const icons = {
  dashboard: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>',
  project: '<svg viewBox="0 0 24 24"><path d="M4 5h16v14H4z"/><path d="M8 3v4M16 3v4M8 11h8M8 15h5"/></svg>',
  team: '<svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  review: '<svg viewBox="0 0 24 24"><path d="M12 3 14.7 8.5l6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.8 1-6.1-4.4-4.3 6.1-.9L12 3Z"/></svg>',
  grade: '<svg viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></svg>',
  log: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  folder: '<svg viewBox="0 0 24 24"><path d="M3 6h7l2 2h9v11H3z"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg>',
  bell: '<svg viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></svg>',
  upload: '<svg viewBox="0 0 24 24"><path d="M12 16V4m0 0L7 9m5-5 5 5"/><path d="M4 15v5h16v-5"/></svg>',
  plus: '<svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>',
  download: '<svg viewBox="0 0 24 24"><path d="M12 4v12m0 0 5-5m-5 5-5-5M4 20h16"/></svg>',
  lock: '<svg viewBox="0 0 24 24"><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>',
  users: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="4"/><path d="M2 21v-2a5 5 0 0 1 5-5h4a5 5 0 0 1 5 5v2M17 11a3 3 0 1 0 0-6M19 14a4 4 0 0 1 3 3.9V21"/></svg>',
  file: '<svg viewBox="0 0 24 24"><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M9 13h6M9 17h6"/></svg>',
  award: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="5"/><path d="m8 12-2 9 6-3 6 3-2-9"/></svg>',
  activity: '<svg viewBox="0 0 24 24"><path d="M3 12h4l2-7 4 14 2-7h6"/></svg>',
  edit: '<svg viewBox="0 0 24 24"><path d="m4 20 4-1 11-11-3-3L5 16l-1 4ZM14 7l3 3"/></svg>',
  send: '<svg viewBox="0 0 24 24"><path d="m3 4 18 8-18 8 3-8-3-8Z"/><path d="M6 12h15"/></svg>',
  info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>',
  search: '<svg viewBox="0 0 24 24"><circle cx="10" cy="10" r="7"/><path d="m15 15 6 6"/></svg>',
};

function icon(name) { return icons[name] || icons.info; }
function esc(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[ch]));
}
function fmt(value) { return value ? String(value).replace("T", " ").slice(0, 16) : "—"; }
function roleName(role) { return ({ teacher: "教师", assistant: "助教", student: "学生" })[role] || role; }
function clamp(value, min = 0, max = 100) { return Math.max(min, Math.min(max, Number(value) || 0)); }
function pct(value, total) { return total ? Math.round((Number(value) / Number(total)) * 100) : 0; }
function project() { return state.data?.projects?.find((item) => item.id === state.data.active_project_id) || state.data?.projects?.[0]; }
function initials(name) { return String(name || "?").trim().slice(-2); }
function memberNames(team) { return String(team.members || "").split("、").filter(Boolean); }

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.csrfToken && !["GET", "HEAD"].includes((options.method || "GET").toUpperCase())) headers["X-CSRF-Token"] = state.csrfToken;
  if (options.body && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  if ((response.headers.get("content-type") || "").includes("application/json")) {
    const data = await response.json();
    if (!response.ok || data.ok === false) {
      const error = new Error(data.message || "操作失败"); error.status = response.status; throw error;
    }
    return data;
  }
  if (!response.ok) throw new Error("请求失败");
  return response;
}

function toast(message, isError = false) {
  const el = document.querySelector("#toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.hidden = false;
  
  // 核心逻辑：如果弹窗开着，就把 Toast 移动到弹窗内部，突破 Top Layer 限制
  const modal = document.querySelector("#modal");
  if (modal && modal.open) {
    modal.appendChild(el);
  } else {
    document.body.appendChild(el);
  }
  
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(() => { el.hidden = true; }, 2800);
}

function skeleton() {
  return '<div class="skeleton-grid"><div class="skeleton skeleton-stat"></div><div class="skeleton skeleton-stat"></div><div class="skeleton skeleton-stat"></div><div class="skeleton skeleton-stat"></div></div>';
}

function showApp() {
  document.querySelector("#login-screen").hidden = true;
  document.querySelector("#app-shell").hidden = false;
}

async function showLogin(message = "") {
  state.data = null;
  state.csrfToken = null;
  document.querySelector("#app-shell").hidden = true;
  document.querySelector("#login-screen").hidden = false;
  const error = document.querySelector("#login-error");
  error.textContent = message;
  error.hidden = !message;
  try {
    const data = await api("/api/demo-users");
    document.querySelector("#login-user").innerHTML = data.users.map((item) => '<option value="' + item.id + '">' + esc(item.name) + " · " + roleName(item.role) + "</option>").join("");
    document.querySelector("#login-hint").textContent = data.password_hint || "请输入账号密码";
  } catch (loadError) {
    error.textContent = loadError.message; error.hidden = false;
  }
}

async function start() {
  try {
    const status = await api("/api/session");
    if (status.authenticated) { state.csrfToken = status.csrf_token; await load(); }
    else await showLogin();
  } catch (error) { await showLogin("服务暂时不可用，请稍后重试"); }
}

async function load({ quiet = false } = {}) {
  const content = document.querySelector("#content");
  content.setAttribute("aria-busy", "true");
  if (!quiet) content.innerHTML = skeleton();
  try {
    const query = state.projectId ? "?project_id=" + state.projectId : "";
    state.data = await api("/api/bootstrap" + query);
    state.csrfToken = state.data.csrf_token;
    state.projectId = state.data.active_project_id;
    if (state.projectId) localStorage.setItem("activeProject", String(state.projectId));
    showApp();
    renderShell();
    render();
  } catch (error) {
    if (error.status === 401) showLogin();
    else content.innerHTML = emptyState("数据加载失败", error.message, "activity");
  } finally {
    content.setAttribute("aria-busy", "false");
  }
}

function allowedPages(role) {
  if (role === "student") return ["overview", "projects", "teams", "reviews", "grades"];
  if (role === "assistant") return ["overview", "projects", "teams", "grades", "logs"];
  return Object.keys(pages);
}

function renderShell() {
  const user = state.data.current_user;
  const available = allowedPages(user.role);
  if (!available.includes(state.page)) state.page = "overview";
  const current = pages[state.page];
  document.body.classList.toggle("sidebar-collapsed", state.sidebarCollapsed);
  document.querySelector("#nav").innerHTML = available.map((key) => {
    const item = pages[key];
    return '<button class="nav-item ' + (state.page === key ? "active" : "") + '" type="button" data-page="' + key + '" aria-current="' + (state.page === key ? "page" : "false") + '" title="' + item.label + '"><span class="nav-icon">' + icon(item.icon) + '</span><span class="nav-label">' + item.label + '</span></button>';
  }).join("");
  document.querySelectorAll("[data-page]").forEach((button) => {
    button.onclick = () => {
      state.page = button.dataset.page;
      renderShell();
      render();
      document.querySelector("#content").focus({ preventScroll: true });
    };
  });

  document.querySelector("#page-title").textContent = current.label;
  document.querySelector("#breadcrumb-current").textContent = current.label;
  document.querySelector("#page-description").textContent = current.description;
  document.querySelector("#user-name").textContent = user.name;
  document.querySelector("#user-role").textContent = roleName(user.role) + " · 已安全登录";
  document.querySelector("#user-avatar").textContent = initials(user.name);
  const p = project();
  const courseName = p?.course_name || state.data.courses?.[0]?.name || "课程工作台";
  const term = p?.term || state.data.courses?.[0]?.term || "当前学期";
  document.querySelector("#workspace-course").textContent = courseName;
  document.querySelector("#workspace-term").textContent = term;
  document.querySelector("#breadcrumb-course").textContent = courseName;
  const projectSelect = document.querySelector("#project-select");
  projectSelect.innerHTML = state.data.projects.map((item) => '<option value="' + item.id + '" ' + (item.id === state.data.active_project_id ? "selected" : "") + ">" + esc(item.title) + "</option>").join("");
  projectSelect.disabled = state.data.projects.length < 2;
  projectSelect.onchange = async () => { state.projectId = Number(projectSelect.value); await load(); };
}

function render() {
  const renderer = {
    overview: overviewPage,
    projects: projectsPage,
    teams: teamsPage,
    reviews: reviewsPage,
    grades: gradesPage,
    logs: logsPage,
  }[state.page];
  const content = document.querySelector("#content");
  content.innerHTML = renderer();
  bindActions();
}

function statCard(label, value, suffix, description, iconName, tone = "", progress = null) {
  return '<article class="stat-card"><div class="stat-head"><span>' + label + '</span><span class="stat-icon ' + tone + '">' + icon(iconName) + '</span></div><div class="stat-value"><strong>' + value + '</strong><span>' + suffix + '</span></div><div class="stat-foot"><span>' + description + '</span>' + (progress === null ? "" : "<strong>" + progress + "%</strong>") + '</div>' + (progress === null ? "" : '<progress class="mini-progress" max="100" value="' + clamp(progress) + '"></progress>') + "</article>";
}

function overviewPage() {
  const p = project();
  if (!p) return emptyState("还没有课程项目", "教师发布项目后，这里将展示实时进展。", "project");
  const grades = p.gradebook || [];
  const validGrades = grades.filter((item) => item.total !== null);
  const average = validGrades.length ? (validGrades.reduce((sum, item) => sum + Number(item.total), 0) / validGrades.length).toFixed(1) : "—";
  const activeSubmissions = state.data.submissions.filter((item) => item.status !== "withdrawn").length;
  const expectedSubmissions = Math.max(1, state.data.teams.length * p.iterations.length);
  const submissionProgress = pct(activeSubmissions, expectedSubmissions);
  let reviewCount = 0;
  let expectedReviews = 0;
  
  if (state.data.current_user.role === "student") {
    // 学生端：显示自己完成了多少个互评任务
    const targets = state.data.review_targets || [];
    reviewCount = targets.filter(item => item.reviewed).length;
    expectedReviews = Math.min(3, targets.length);
  } else {
    // 教师/助教端：显示全班总评数据
    reviewCount = grades.reduce((sum, item) => sum + Number(item.peer_count || 0), 0);
    expectedReviews = Math.max(1, memberTotal() * 3);
  }
  const reviewProgress = pct(reviewCount, expectedReviews);

  return '<div class="stats">'
    + statCard("课程项目", state.data.projects.length, "个", "当前学期已发布", "folder")
    + statCard("项目团队", state.data.teams.length, "支", "成员共 " + memberTotal() + " 人", "users", "teal")
    + statCard("成果提交", activeSubmissions + "/" + expectedSubmissions, "份", "按团队与迭代统计", "upload", "amber", submissionProgress)
    + statCard("互评进度", reviewCount + "/" + expectedReviews, "次", "每位学生最多 3 次", "review", "violet", reviewProgress)
    + statCard("团队均分", average, "分", validGrades.length + " 支团队已完成计算", "award")
    + '</div>'
    + '<div class="dashboard-grid"><div class="stack">'
    + projectSummaryCard(p)
    + gradeSnapshotCard(p)
    + '</div><aside class="stack">'
    + progressCard(p, submissionProgress, reviewProgress)
    + identityCard()
    + notificationCard()
    + '</aside></div>';
}

function memberTotal() {
  return state.data.teams.reduce((total, team) => total + memberNames(team).length, 0);
}

function projectSummaryCard(p) {
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("project") + '</span><div><h2>重点项目</h2><p class="subtle">当前课程的主要交付与里程碑</p></div></div><span class="tag green">进行中</span></div>'
    + '<div class="project-hero"><div class="project-top"><div><div class="project-meta"><span class="tag green">' + (p.status === "published" ? "已发布" : "草稿") + '</span><span class="project-code">PROJECT · ' + String(p.id).padStart(3, "0") + '</span></div><h2>' + esc(p.title) + '</h2><p class="project-description subtle">' + esc(p.description) + '</p></div><div class="deadline-block"><span>项目总截止时间</span><strong>' + fmt(p.overall_deadline) + '</strong></div></div>'
    + weightPanel(p)
    + '<div class="phase-list">' + p.iterations.map((item) => '<div class="phase-item"><i class="phase-marker"></i><div class="phase-copy"><strong>' + esc(item.name) + '</strong><span>' + esc(item.requirements) + '</span></div><time class="phase-date">' + fmt(item.deadline) + '</time></div>').join("") + '</div></div></section>';
}

function weightPanel(p) {
  const values = [
    ["同伴互评", Number(p.peer_weight) * 100],
    ["助教过程分", Number(p.process_weight) * 100],
    ["教师终评", Number(p.final_weight) * 100],
  ];
  return '<div class="weight-panel">' + values.map(([label, value]) => '<div class="weight-item"><div><span>' + label + '</span><strong>' + value + '%</strong></div><progress class="weight-progress" max="100" value="' + value + '"></progress></div>').join("") + '</div>';
}

function progressCard(p, submissionProgress, reviewProgress) {
  const gradeProgress = pct(p.gradebook.filter((item) => item.total !== null).length, Math.max(1, p.gradebook.length));
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("activity") + '</span><div><h2>项目进度</h2><p class="subtle">关键环节完成情况</p></div></div></div><div class="progress-overview">'
    + progressRow("迭代提交", submissionProgress)
    + progressRow("同伴互评", reviewProgress)
    + progressRow("成绩核算", gradeProgress)
    + '</div></section>';
}
function progressRow(label, progress) {
  return '<div class="progress-row"><label>' + label + '</label><progress class="progress-track" max="100" value="' + clamp(progress) + '"></progress><strong>' + clamp(progress) + '%</strong></div>';
}

function identityCard() {
  const user = state.data.current_user;
  const permissions = {
    teacher: ["发布项目并设置评分规则", "开启互评、录入终评分", "发布与导出课程成绩"],
    assistant: ["查看全部团队提交", "记录团队过程分", "查看成绩与审计日志"],
    student: ["浏览任务并参与团队", "负责人提交迭代成果", "完成分配的同伴互评"],
  }[user.role];
  return '<section class="card"><div class="identity-card"><span class="user-avatar">' + esc(initials(user.name)) + '</span><div><h3>' + esc(user.name) + '</h3><span class="tag">' + roleName(user.role) + '</span></div></div><ul class="permission-list">' + permissions.map((item) => '<li>' + icon("check") + "<span>" + item + "</span></li>").join("") + "</ul></section>";
}

function notificationCard() {
  const notices = state.data.notifications || [];
  const unread = notices.filter((item) => !item.is_read).length;
  // 给每条通知加上 data-page 属性，并绑定跳转
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("bell") + '</span><div><h2>通知中心</h2><p class="subtle">' + unread + ' 条未读消息</p></div></div>' + (unread ? '<button class="button ghost small" data-action="read-all" type="button">全部已读</button>' : '<span class="tag green">' + notices.length + '</span>') + '</div>'
    + (notices.length ? '<div class="notice-list">' + notices.slice(0, 5).map((item) => '<article class="notice ' + (!item.is_read ? "unread" : "") + '" data-action="read-notice" data-id="' + item.id + '" data-page="' + item.target_page + '"><span class="notice-icon">' + icon("bell") + '</span><strong>' + esc(item.title) + '</strong><span>' + esc(item.content) + '</span><time>' + fmt(item.created_at).slice(5) + '</time></article>').join("") + "</div>" : emptyState("暂无通知", "关键节点的提醒会显示在这里。", "bell"))
    + "</section>";
}

function gradeSnapshotCard(p) {
  const weights = [p.peer_weight, p.process_weight, p.final_weight].map((value) => Math.round(Number(value) * 100));
  return '<section class="card flush"><div class="card-head table-card-head"><div class="card-title"><span class="section-icon">' + icon("grade") + '</span><div><h2>成绩快照</h2><p class="subtle">按互评 ' + weights[0] + '% · 过程 ' + weights[1] + '% · 终评 ' + weights[2] + '% 实时计算</p></div></div>' + (p.grades_published ? '<span class="tag green">已发布</span>' : '<span class="tag amber">待发布</span>') + '</div>' + gradeTable(p.gradebook) + "</section>";
}

function gradeTable(items) {
  return '<div class="table-wrap"><table><thead><tr><th>团队</th><th>同伴互评</th><th>过程分</th><th>教师终评</th><th>综合总分</th></tr></thead><tbody>' + items.map((item) => '<tr><td><strong>' + esc(item.team_name) + '</strong></td><td>' + scoreCell(item.peer_score, "") + '</td><td>' + scoreCell(item.process_score, "process") + '</td><td>' + scoreCell(item.final_score, "final") + '</td><td>' + (item.total === null ? '<span class="pending">待核算</span>' : '<span class="score">' + item.total + '</span>') + '</td></tr>').join("") + "</tbody></table></div>";
}
function scoreCell(value, type) {
  if (value === null || value === undefined) return '<span class="pending">待录入</span>';
  return '<div class="score-cell ' + type + '"><div class="score-number"><span>' + value + '</span><small>/100</small></div><progress class="score-bar" max="100" value="' + clamp(value) + '"></progress></div>';
}

function projectsPage() {
  const user = state.data.current_user;
  const action = user.role === "teacher" ? '<button class="button" type="button" data-action="new-project">' + icon("plus") + "<span>发布新项目</span></button>" : "";
  
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("project") + '</span><div><h2>课程项目与迭代</h2><p class="subtle">清晰管理任务要求、阶段截止与评分权重</p></div></div><div class="card-actions">' + action + "</div></div>"
    + state.data.projects.map((item) => 
      '<div class="project-hero spaced ' + (item.id === state.data.active_project_id ? "selected-project" : "") + '">' 
        + '<div class="project-top">' 
          + '<div>' 
            + '<div class="project-meta"><span class="tag green">' + (item.status === "published" ? "已发布" : "草稿") + '</span><span class="project-code">COURSE · ' + esc(item.course_name) + '</span></div>'
            + '<h2>' + esc(item.title) + '</h2>'
            + '<p class="project-description subtle">' + esc(item.description) + '</p>'
          + '</div>' 
          + '<div class="card-actions" style="display: flex; align-items: center; gap: 12px;">' 
            + '<div class="deadline-block"><span>组队截止 / 项目截止</span><strong>' + fmt(item.team_deadline).slice(5) + ' · ' + fmt(item.overall_deadline).slice(5) + '</strong></div>' 
            + (user.role === "teacher" && !item.grades_published ? '<button class="button ghost small" data-action="edit-weights" data-id="' + item.id + '" type="button">' + icon("edit") + '<span>修改权重</span></button>' : '')
            + (item.id !== state.data.active_project_id ? '<button class="button secondary small" data-action="select-project" data-id="' + item.id + '" type="button">切换到此项目</button>' : '<span class="tag green">当前项目</span>')
          + '</div>' 
        + '</div>' 
        + '<div style="margin-top: 15px;">' + weightPanel(item) + '</div>' 
        + '<div class="phase-list" style="margin-top: 20px;">' + item.iterations.map((phase) => '<div class="phase-item"><i class="phase-marker"></i><div class="phase-copy"><strong>' + esc(phase.name) + '</strong><span>' + esc(phase.requirements) + '</span></div><time class="phase-date">' + fmt(phase.deadline) + '</time></div>').join("") + "</div>"
      + '</div>'
    ).join("")
    + "</section>";
}

function teamStatus(team) {
  const mapping = { forming: ["组队中", "amber"], locked: ["已锁定", "gray"], active: ["进行中", "green"], completed: ["已结项", "violet"] };
  return mapping[team.status] || [team.status, "gray"];
}
function avatars(team) {
  const names = memberNames(team);
  return '<div class="avatar-stack">' + names.slice(0, 5).map((name) => '<span class="avatar" title="' + esc(name) + '">' + esc(initials(name)) + '</span>').join("") + '<span class="member-count">' + names.length + "/5 人</span></div>";
}

function teamsPage() {
  const user = state.data.current_user;
  const p = project();
  const createAction = user.role === "student" && !state.data.my_team ? '<button class="button" type="button" data-action="new-team">' + icon("plus") + "<span>创建团队</span></button>" : "";
  const uploadAction = user.role === "student" && state.data.my_team?.is_leader ? p.iterations.map((item) => '<button class="button" type="button" data-action="upload" data-id="' + item.id + '" data-name="' + esc(item.name) + '">' + icon("upload") + '<span>提交 ' + esc(item.name) + '</span></button>').join("") : "";
  return '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("team") + '</span><div><h2>项目团队</h2><p class="subtle">每队 3—5 人，组队截止后成员锁定</p></div></div><div class="card-actions">' + createAction + '</div></div><div class="team-grid">' + state.data.teams.map((team) => {
    const status = teamStatus(team);
    const join = user.role === "student" && !state.data.my_team ? '<button class="button secondary small" type="button" data-action="join-team" data-id="' + team.id + '">申请加入</button>' : "";
    const leave = user.role === "student" && state.data.my_team?.id === team.id ? '<button class="button danger small" type="button" data-action="leave-team" data-id="' + team.id + '">退出团队</button>' : "";
    return '<article class="team-card"><div class="team-card-head"><span class="tag ' + status[1] + '">' + status[0] + '</span><span class="project-code">TEAM · ' + String(team.id).padStart(2, "0") + '</span></div><h3>' + esc(team.name) + '</h3><span class="leader">队长 · ' + esc(team.leader_name) + '</span>' + avatars(team) + '<div class="team-card-foot"><span class="subtle">' + (team.member_count >= 3 ? "人数符合要求" : "还需 " + (3 - team.member_count) + " 人") + '</span>' + join + leave + "</div></article>";
  }).join("") + "</div></section>"
    + '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("file") + '</span><div><h2>迭代提交记录</h2><p class="subtle">支持 PDF、ZIP、MP4，单文件不超过 200MB</p></div></div><div class="card-actions">' + uploadAction + '</div></div>'
    + (user.role === "student" && state.data.my_team?.is_leader ? '<div class="upload-zone spaced"><div><span class="upload-zone-icon">' + icon("upload") + '</span><strong>按右上角选择迭代并上传成果</strong><span>提交后保留全部版本；支持 PDF / ZIP / MP4，单文件不超过 200MB</span></div></div>' : "")
    + submissionTable()
    + "</section>";
}

function submissionTable() {
  if (!state.data.submissions.length) return emptyState("暂无提交记录", "团队负责人上传成果后，版本和提交时间会显示在这里。", "file");
  const myTeam = state.data.my_team;
  return '<div class="table-wrap"><table><thead><tr><th>团队</th><th>迭代阶段</th><th>成果文件</th><th>状态</th><th>版本</th><th>提交时间</th><th>操作</th></tr></thead><tbody>' + state.data.submissions.map((item) => '<tr><td><strong>' + esc(item.team_name) + '</strong></td><td>' + esc(item.iteration_name) + '</td><td>' + esc(item.file_name) + '</td><td><span class="tag ' + (item.status === "withdrawn" ? "amber" : "green") + '">' + statusText(item.status) + '</span></td><td>v' + item.version + ' · ' + (item.version_count || 1) + ' 个版本</td><td class="nowrap">' + fmt(item.submitted_at) + '</td><td><div class="card-actions"><button class="button ghost small" data-action="download" data-id="' + item.id + '" type="button">下载</button><button class="button ghost small" data-action="versions" data-id="' + item.id + '" type="button">历史</button>' + (myTeam?.id === item.team_id && myTeam?.is_leader && item.status !== "withdrawn" ? '<button class="button danger small" data-action="withdraw" data-id="' + item.id + '" type="button">撤回</button>' : "") + "</div></td></tr>").join("") + "</tbody></table></div>";
}
function statusText(status) {
  return ({ submitted: "已提交", reviewing: "评审中", withdrawn: "已撤回", returned: "已退回", completed: "已完成" })[status] || status;
}

function reviewsPage() {
  const p = project();
  const user = state.data.current_user;
  if (user.role === "teacher") {
    const completed = p.gradebook.reduce((sum, item) => sum + Number(item.peer_count || 0), 0);
    return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("review") + '</span><div><h2>互评阶段控制</h2><p class="subtle">开启后，学生可评审其他团队，每人最多 3 个团队</p></div></div><button class="button ' + (p.review_open ? "danger" : "") + '" type="button" data-action="toggle-review">' + icon(p.review_open ? "lock" : "send") + "<span>" + (p.review_open ? "关闭互评" : "开启互评") + '</span></button></div><div class="project-hero"><div class="project-top"><div><span class="tag ' + (p.review_open ? "green" : "gray") + '">' + (p.review_open ? "互评进行中" : "互评未开启") + '</span><h2>本轮互评已收集 ' + completed + ' 份评价</h2><p class="subtle">系统会阻止学生评价本团队，并限制每人最多评价 3 个其他团队。</p></div><div class="deadline-block"><span>当前阶段</span><strong>' + (p.review_open ? "开放提交" : "暂停提交") + "</strong></div></div></div></section>";
  }
  if (user.role !== "student") return emptyState("当前角色不参与同伴互评", "助教可以在评分页面查看团队得分。", "review");
  const targets = state.data.review_targets || [];
  const completed = targets.filter((item) => item.reviewed).length;
  
  // 卡片底部增加下载按钮和评价按钮的布局
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("review") + '</span><div><h2>我的互评任务</h2><p class="subtle">已完成 ' + completed + "/" + Math.min(3, targets.length) + ' 项 · 不能评审本团队</p></div></div><span class="tag ' + (p.review_open ? "green" : "gray") + '">' + (p.review_open ? "互评开放" : "互评关闭") + '</span></div><div class="review-grid">' + targets.map((target) => '<article class="review-card ' + (target.reviewed ? "complete" : "") + '"><span class="tag ' + (target.reviewed ? "green" : "amber") + '">' + (target.reviewed ? "已完成" : "待评价") + '</span><h3>' + esc(target.name) + '</h3><p class="subtle">从完成度、创新性和文档质量进行综合评价。</p><div class="review-score"><strong>' + (target.current_average ?? "—") + '</strong><span>我的评分</span></div><div class="card-actions" style="justify-content: center; margin-top: 15px;">' + (target.submission_id ? '<button class="button ghost small" type="button" data-action="download" data-id="' + target.submission_id + '" data-filename="' + esc(target.submission_filename || "submission.pdf") + '">' + icon("download") + ' <span>下载成果</span></button>' : '') + '<button class="button secondary small" type="button" data-action="review" data-id="' + target.id + '" data-name="' + esc(target.name) + '">' + icon("edit") + "<span>" + (target.reviewed ? "修改评价" : "开始评价") + "</span></button></div></article>").join("") + "</div></section>";
}

function gradesPage() {
  const p = project();
  const user = state.data.current_user;
  if (user.role === "student" && !p.grades_published) return emptyState("成绩尚未发布", "教师完成所有评分并发布后，你可以在这里查看本团队成绩。", "grade");
  if (!p.gradebook.length) return emptyState("暂无可显示的成绩", "当前项目还没有形成成绩记录。", "grade");
  const actions = (user.role === "teacher"
    ? '<button class="button ghost" type="button" data-action="export">' + icon("download") + '<span>导出 CSV</span></button>' + (p.grades_published ? '<span class="tag green">成绩已发布</span>' : '<button class="button" type="button" data-action="publish-grades">' + icon("send") + "<span>发布成绩</span></button>")
    : user.role === "assistant" ? '<span class="tag gray">可录入过程分</span>' : '<span class="tag green">已发布</span>');
  const formula = '总分 = 互评 × ' + Number(p.peer_weight) * 100 + '% + 过程分 × ' + Number(p.process_weight) * 100 + '% + 终评 × ' + Number(p.final_weight) * 100 + '%';
  return '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("grade") + '</span><div><h2>成绩汇总</h2><p class="subtle">' + formula + '</p></div></div><div class="card-actions">' + actions + "</div></div>" + gradeTable(p.gradebook) + "</section>"
    + '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("award") + '</span><div><h2>团队成绩构成</h2><p class="subtle">查看各评分环节占比并完成待录入项</p></div></div></div><div class="grade-team-grid">' + p.gradebook.map((item) => gradeTeamCard(item, user)).join("") + "</div></section>";
}
function gradeTeamCard(item, user) {
  const locked = project().grades_published;
  const buttons = (!locked && (user.role === "assistant" || user.role === "teacher") ? '<button class="button secondary small" type="button" data-action="score-process" data-id="' + item.team_id + '" data-name="' + esc(item.team_name) + '">过程分</button>' : "")
    + (!locked && user.role === "teacher" ? '<button class="button secondary small" type="button" data-action="score-final" data-id="' + item.team_id + '" data-name="' + esc(item.team_name) + '">终评分</button>' : "");
  return '<article class="grade-team-card"><div class="grade-team-top"><div><h3>' + esc(item.team_name) + '</h3><span class="subtle">' + (item.total === null ? "仍有评分待录入" : "成绩构成完整") + '</span></div><strong class="grade-total">' + (item.total ?? "—") + '</strong></div><div class="composition"><i class="part-peer ' + (item.peer_score === null ? "missing" : "") + '"></i><i class="part-process ' + (item.process_score === null ? "missing" : "") + '"></i><i class="part-final ' + (item.final_score === null ? "missing" : "") + '"></i></div><div class="legend"><span>互评 ' + (item.peer_score ?? "—") + '</span><span>过程 ' + (item.process_score ?? "—") + '</span><span>终评 ' + (item.final_score ?? "—") + '</span></div><div class="card-actions top-gap">' + buttons + "</div></article>";
}

function logsPage() {
  const logs = state.data.logs || [];
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("log") + '</span><div><h2>过程审计日志</h2><p class="subtle">发布、组队、提交、互评和评分等关键操作均留痕</p></div></div><span class="tag">' + logs.length + ' 条记录</span></div>'
    + (logs.length ? '<div class="audit-list">' + logs.map((item) => {
      const kind = item.action === "score" ? "score-log" : item.action === "export" ? "export-log" : "";
      const markerIcon = item.action === "score" ? "grade" : item.action === "export" ? "download" : item.action === "submit" ? "upload" : "activity";
      return '<article class="audit-item"><span class="audit-marker ' + kind + '">' + icon(markerIcon) + '</span><div class="audit-copy"><strong>' + esc(item.detail) + '</strong><span>' + esc(item.user_name) + ' · ' + esc(item.action) + ' · ' + esc(item.entity) + " #" + esc(item.entity_id) + '</span></div><time class="audit-time">' + fmt(item.created_at) + "</time></article>";
    }).join("") + "</div>" : emptyState("暂无日志", "关键操作完成后会自动写入这里。", "log"))
    + "</section>";
}

function emptyState(title, description, iconName) {
  return '<div class="empty"><div><span class="empty-icon">' + icon(iconName) + '</span><strong>' + esc(title) + '</strong><span>' + esc(description) + "</span></div></div>";
}

function openModal(title, description, html) {
  document.querySelector("#modal-title").textContent = title;
  document.querySelector("#modal-description").textContent = description || "";
  document.querySelector("#modal-body").innerHTML = html;
  document.querySelector("#modal").showModal();
}
function closeModal() { document.querySelector("#modal").close(); }
function formHtml(fields, actionLabel = "保存") {
  return '<div class="form-grid">' + fields + '</div><div class="form-actions"><button class="button ghost" value="cancel">取消</button><button class="button" type="button" id="modal-submit">' + actionLabel + "</button></div>";
}
function value(id) { return document.querySelector("#" + id)?.value.trim() || ""; }
function requiredValue(id, message) {
  const input = document.querySelector("#" + id);
  const field = input?.closest(".field");
  if (input && input.value.trim()) { field?.classList.remove("invalid"); return input.value.trim(); }
  field?.classList.add("invalid");
  input?.focus();
  throw new Error(message);
}

async function runBusy(button, task) {
  if (button.disabled) return;
  const original = button.innerHTML;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.textContent = "处理中…";
  try { await task(); }
  finally { button.disabled = false; button.removeAttribute("aria-busy"); button.innerHTML = original; }
}

function bindModalSubmit(task) {
  document.querySelector("#modal-submit").onclick = (event) => runBusy(event.currentTarget, async () => {
    try { await task(); }
    catch (error) { 
      if (error.status) {
        closeModal(); 
      }
      toast(error.message, true); 
    }
  });
}

function bindActions() {
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.onclick = () => runBusy(button, async () => {
      const action = button.dataset.action;
      const p = project();
      try {
        if (action === "new-project") {
          openModal("发布新项目", "填写基础信息、截止时间和评分权重", formHtml(
            '<div class="form-section-title">项目基本信息</div>'
            + '<div class="field full"><label class="required" for="f-title">项目名称</label><input id="f-title" value="课程项目" required><span class="field-error">请输入项目名称</span></div>'
            + '<div class="field full"><label class="required" for="f-description">项目说明</label><textarea id="f-description" required>完成项目迭代与评审闭环</textarea><span class="field-error">请输入项目说明</span></div>'
            + '<div class="form-divider"></div><div class="form-section-title">时间安排</div>'
            + '<div class="field"><label class="required" for="f-team-deadline">组队截止</label><input id="f-team-deadline" type="datetime-local" value="2026-11-10T23:59" required><span class="field-error">请选择组队截止时间</span></div>'
            + '<div class="field"><label class="required" for="f-overall-deadline">项目截止</label><input id="f-overall-deadline" type="datetime-local" value="2026-12-20T23:59" required><span class="field-error">请选择项目截止时间</span></div>'
            + '<div class="field"><label class="required" for="f-review-deadline">互评截止</label><input id="f-review-deadline" type="datetime-local" value="2026-12-18T23:59" required><span class="field-error">请选择互评截止时间</span></div>'
            + '<div class="field"><label class="required" for="f-iteration-deadline">首轮迭代截止</label><input id="f-iteration-deadline" type="datetime-local" value="2026-12-10T23:59" required><span class="field-error">请选择迭代截止时间</span></div>'
            + '<div class="field full"><label class="required" for="f-requirements">首轮迭代要求</label><textarea id="f-requirements" required>提交需求文档、源代码与演示材料</textarea><span class="field-error">请输入迭代要求</span></div>'
            + '<div class="form-divider"></div><div class="form-section-title">评分权重 · 合计必须为 100%</div>'
            + '<div class="field"><label for="f-peer">互评权重</label><input id="f-peer" type="number" min="0" max="100" value="25"><span class="field-help">建议值 25%</span></div>'
            + '<div class="field"><label for="f-process">过程分权重</label><input id="f-process" type="number" min="0" max="100" value="25"><span class="field-help">建议值 25%</span></div>'
            + '<div class="field"><label for="f-final">终评权重</label><input id="f-final" type="number" min="0" max="100" value="50"><span class="field-help">建议值 50%</span></div>',
            "确认发布"
          ));
          bindModalSubmit(async () => {
            const payload = {
              title: requiredValue("f-title", "请输入项目名称"),
              description: requiredValue("f-description", "请输入项目说明"),
              team_deadline: requiredValue("f-team-deadline", "请选择组队截止时间"),
              overall_deadline: requiredValue("f-overall-deadline", "请选择项目截止时间"),
              review_deadline: requiredValue("f-review-deadline", "请选择互评截止时间"),
              peer_weight: Number(value("f-peer")),
              process_weight: Number(value("f-process")),
              final_weight: Number(value("f-final")),
              course_id: state.data.courses?.[0]?.id,
              iterations: [{ name: "迭代 1", deadline: requiredValue("f-iteration-deadline", "请选择迭代截止时间"), requirements: requiredValue("f-requirements", "请输入迭代要求") }],
            };
            if (payload.peer_weight + payload.process_weight + payload.final_weight !== 100) throw new Error("三项评分权重必须合计 100%");
            await api("/api/projects", { method: "POST", body: JSON.stringify(payload) });
            closeModal(); toast("项目发布成功"); await load({ quiet: true });
          });
        } else if (action === "edit-weights") {
          openModal("修改评分权重", "三项权重合计必须为 100%", formHtml(
            '<div class="field"><label for="f-peer">互评权重 (%)</label><input id="f-peer" type="number" min="0" max="100" value="' + Math.round(p.peer_weight * 100) + '"><span class="field-error">0-100</span></div>'
            + '<div class="field"><label for="f-process">过程分权重 (%)</label><input id="f-process" type="number" min="0" max="100" value="' + Math.round(p.process_weight * 100) + '"><span class="field-error">0-100</span></div>'
            + '<div class="field"><label for="f-final">终评权重 (%)</label><input id="f-final" type="number" min="0" max="100" value="' + Math.round(p.final_weight * 100) + '"><span class="field-error">0-100</span></div>',
            "保存权重"
          ));
          bindModalSubmit(async () => {
            const peer = Number(value("f-peer"));
            const process = Number(value("f-process"));
            const final = Number(value("f-final"));
            if (peer + process + final !== 100) throw new Error("三项评分权重必须合计 100%");
            await api("/api/projects/" + button.dataset.id, { 
              method: "PATCH", 
              body: JSON.stringify({ peer_weight: peer, process_weight: process, final_weight: final }) 
            });
            closeModal(); toast("权重修改成功"); await load({ quiet: true });
          });
        } else if (action === "select-project") {
          state.projectId = Number(button.dataset.id); localStorage.setItem("activeProject", String(state.projectId)); await load();
        } else if (action === "new-team") {
          openModal("创建项目团队", "团队人数最终需满足 3—5 人", formHtml('<div class="field full"><label class="required" for="f-team-name">团队名称</label><input id="f-team-name" placeholder="例如：远航开发组" required><span class="field-error">请输入团队名称</span><span class="field-help">名称应简洁、易识别，项目内不能重复</span></div>', "创建团队"));
          bindModalSubmit(async () => {
            await api("/api/teams", { method: "POST", body: JSON.stringify({ project_id: p.id, name: requiredValue("f-team-name", "请输入团队名称") }) });
            closeModal(); toast("团队创建成功"); await load({ quiet: true });
          });
        } else if (action === "join-team") {
          if (!window.confirm("确认申请加入这个团队吗？")) return;
          await api("/api/teams/" + button.dataset.id + "/join", { method: "POST" });
          toast("已加入团队"); await load({ quiet: true });
        } else if (action === "leave-team") {
          if (!window.confirm("退出后可能由下一名成员自动接任队长，确认继续吗？")) return;
          await api("/api/teams/" + button.dataset.id + "/leave", { method: "POST" });
          toast("已退出团队"); await load({ quiet: true });
        } else if (action === "upload") {
          // 如果成绩已发布，前端直接拦截，连弹窗都不给开！
            if (p.grades_published) {
              return toast("成绩已发布，不能再上传成果", true);
            }
          openModal("上传 " + (button.dataset.name || "迭代成果"), "仅团队负责人可提交；支持拖拽选择文件", formHtml('<div class="field full file-field"><input id="f-file" class="file-input" type="file" accept=".pdf,.zip,.mp4"><label class="upload-zone" id="drop-zone" for="f-file"><span><span class="upload-zone-icon">' + icon("upload") + '</span><strong id="file-label">拖拽文件到这里，或点击选择</strong><span>PDF / ZIP / MP4 · 单文件不超过 200MB · 保留历史版本</span></span></label></div>', "提交成果"));
          document.querySelector("#f-file").onchange = (event) => {
            document.querySelector("#file-label").textContent = event.target.files[0]?.name || "点击选择成果文件";
          };
          const dropZone = document.querySelector("#drop-zone");
          ["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.add("dragging"); }));
          ["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove("dragging"); }));
          dropZone.addEventListener("drop", (event) => { const input = document.querySelector("#f-file"); input.files = event.dataTransfer.files; document.querySelector("#file-label").textContent = input.files[0]?.name || "点击选择成果文件"; });
          bindModalSubmit(async () => {
            const file = document.querySelector("#f-file").files[0];
            if (!file) throw new Error("请选择需要提交的成果文件");
            if (!["pdf", "zip", "mp4"].includes(file.name.split(".").pop().toLowerCase())) throw new Error("仅允许 PDF、ZIP 或 MP4 文件");
            const form = new FormData(); form.append("file", file);
            await api("/api/submissions/" + button.dataset.id, { method: "POST", body: form });
            closeModal(); toast("成果提交成功，版本记录已更新"); await load({ quiet: true });
          });
        } else if (action === "download") {
          const response = await api("/api/submissions/" + button.dataset.id + "/download");
          const blob = await response.blob();
          const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "submission"; link.click(); URL.revokeObjectURL(link.href);
          toast("文件下载已开始");
        } else if (action === "versions") {
          const result = await api("/api/submissions/" + button.dataset.id + "/versions");
          openModal("提交版本历史", "每次重新上传都会保留一条独立版本记录", '<div class="version-list">' + result.versions.map((item) => '<article><span class="tag">v' + item.version + '</span><div><strong>' + esc(item.file_name) + '</strong><span class="subtle">' + fmt(item.submitted_at) + '</span></div></article>').join("") + '</div><div class="form-actions"><button class="button ghost" value="cancel">关闭</button></div>');
        } else if (action === "withdraw") {
          if (!window.confirm("确认撤回当前提交吗？历史版本仍会保留。")) return;
          await api("/api/submissions/" + button.dataset.id + "/withdraw", { method: "POST" });
          toast("提交已撤回"); await load({ quiet: true });
        } else if (action === "read-notice") {
          await api("/api/notifications/" + button.dataset.id + "/read", { method: "POST" });
          const targetPage = button.dataset.page;
          if (targetPage && pages[targetPage]) {
            state.page = targetPage;
            renderShell();
            render();
          } else {
            await load({ quiet: true });
          }
        } else if (action === "read-all") {
          await api("/api/notifications/read-all", { method: "POST" }); toast("通知已全部标为已读"); await load({ quiet: true });
        } else if (action === "review") {
          openModal("评价 " + button.dataset.name, "从完成度、创新性和文档质量综合评分", formHtml(
            '<div class="field full"><label for="f-score-range">综合评分</label><div class="range-wrap"><input id="f-score-range" type="range" min="0" max="100" value="85"><input id="f-score" type="number" min="0" max="100" value="85" aria-label="综合评分数值"></div><span class="field-help">评分范围 0—100 分</span></div>'
            + '<div class="field full"><label class="required" for="f-comment">评价意见</label><textarea id="f-comment" placeholder="请写出具体优点和一条可执行的改进建议"></textarea><span class="field-error">请填写评价意见</span></div>',
            "提交评价"
          ));
          const range = document.querySelector("#f-score-range");
          const number = document.querySelector("#f-score");
          range.oninput = () => { number.value = range.value; };
          number.oninput = () => { range.value = clamp(number.value); };
          bindModalSubmit(async () => {
            const score = clamp(value("f-score"));
            const comment = requiredValue("f-comment", "请填写评价意见");
            if (!window.confirm("确认提交 " + score + " 分的互评结果吗？")) return;
            await api("/api/reviews", { method: "POST", body: JSON.stringify({ project_id: p.id, target_team_id: Number(button.dataset.id), score, comment }) });
            closeModal(); toast("互评已提交"); await load({ quiet: true });
          });
        } else if (action === "toggle-review") {
          const verb = p.review_open ? "关闭" : "开启";
          if (!window.confirm("确认" + verb + "本轮同伴互评吗？")) return;
          await api("/api/projects/" + p.id + "/toggle-review", { method: "POST" });
          toast("互评状态已更新"); await load({ quiet: true });
        } else if (action === "score-process" || action === "score-final") {
          const isProcess = action === "score-process";
          const kind = isProcess ? "过程分" : "终评分";
          openModal(button.dataset.name + " · " + kind, "评分范围 0—100，修改操作会写入审计日志", formHtml('<div class="field"><label class="required" for="f-score">' + kind + '</label><input id="f-score" type="number" min="0" max="100" value="90"><span class="field-error">请输入有效分数</span></div><div class="field full"><label for="f-comment">评分说明</label><textarea id="f-comment">表现符合预期</textarea></div>', "保存评分"));
          bindModalSubmit(async () => {
            const score = Number(value("f-score"));
            if (!Number.isFinite(score) || score < 0 || score > 100) throw new Error("评分必须在 0—100 之间");
            await api("/api/scores/" + (isProcess ? "process" : "final"), { method: "POST", body: JSON.stringify({ project_id: p.id, team_id: Number(button.dataset.id), score, comment: value("f-comment") }) });
            closeModal(); toast(kind + "已保存"); await load({ quiet: true });
          });
        } else if (action === "publish-grades") {
          if (!window.confirm("发布后学生将收到成绩通知，确认继续吗？")) return;
          await api("/api/projects/" + p.id + "/publish-grades", { method: "POST" });
          toast("成绩已发布"); await load({ quiet: true });
        } else if (action === "export") {
          const response = await api("/api/projects/" + p.id + "/grades.csv");
          const blob = await response.blob(); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "project-" + p.id + "-grades.csv"; link.click(); URL.revokeObjectURL(link.href); toast("成绩表已导出");
        }
      } catch (error) {
        if (error.status === 401) await showLogin("登录状态已失效，请重新登录"); else toast(error.message, true);
      }
    });
  });
}

document.querySelector("#refresh-btn").onclick = (event) => runBusy(event.currentTarget, async () => {
  await load({ quiet: true });
  toast("数据已刷新");
});
document.querySelector("#login-form").onsubmit = (event) => {
  event.preventDefault();
  runBusy(document.querySelector("#login-submit"), async () => {
    const error = document.querySelector("#login-error"); error.hidden = true;
    try {
      const result = await api("/api/login", { method: "POST", body: JSON.stringify({ user_id: value("login-user"), password: document.querySelector("#login-password").value }) });
      state.csrfToken = result.csrf_token; state.projectId = null; localStorage.removeItem("activeProject"); await load(); toast("欢迎回来，" + result.current_user.name);
    } catch (loginError) { error.textContent = loginError.message; error.hidden = false; }
  });
};
document.querySelector("#logout-btn").onclick = (event) => runBusy(event.currentTarget, async () => {
  await api("/api/logout", { method: "POST" }); state.csrfToken = null; state.data = null; await showLogin();
});
document.querySelector("#sidebar-toggle").onclick = () => {
  state.sidebarCollapsed = !state.sidebarCollapsed;
  localStorage.setItem("sidebarCollapsed", String(state.sidebarCollapsed));
  document.body.classList.toggle("sidebar-collapsed", state.sidebarCollapsed);
  const button = document.querySelector("#sidebar-toggle");
  button.setAttribute("aria-label", state.sidebarCollapsed ? "展开侧边栏" : "收起侧边栏");
  button.title = state.sidebarCollapsed ? "展开侧边栏" : "收起侧边栏";
};
document.body.classList.toggle("sidebar-collapsed", state.sidebarCollapsed);
start();

