const state = {
  data: null,
  page: "overview",
  csrfToken: null,
  projectId: Number(localStorage.getItem("activeProject")) || null,
  sidebarCollapsed: localStorage.getItem("sidebarCollapsed") === "true",
};

const pages = {
  overview: { label: "工作台概览", description: "集中查看课程项目进度、团队协作状态、评审任务与成绩发布情况", icon: "dashboard" },
  projects: { label: "项目管理", description: "管理项目要求、阶段里程碑、截止时间与评分权重", icon: "project" },
  teams: { label: "团队与成员", description: "查看团队构成、负责人和成员协作状态", icon: "team" },
  submissions: { label: "成果提交", description: "查看迭代成果、提交版本与文件状态", icon: "file" },
  reviews: { label: "匿名互评", description: "管理匿名分配任务并跟踪互评进度", icon: "review" },
  grades: { label: "成绩管理", description: "录入过程分和终评分，核对并发布成绩", icon: "grade" },
  logs: { label: "操作记录", description: "追溯发布、提交、互评与评分等关键操作", icon: "log" },
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
function roleName(role) { return ({ admin: "教务管理员", teacher: "教师", assistant: "助教", student: "学生" })[role] || role; }
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

function responseFilename(response, fallback) {
  const disposition = response.headers.get("content-disposition") || "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encoded) return decodeURIComponent(encoded[1].replace(/["']/g, ""));
  const plain = disposition.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1].trim() : fallback;
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
  const passwordInput = document.querySelector("#login-password");
  const passwordToggle = document.querySelector("#login-password-toggle");
  passwordInput.type = "password";
  passwordToggle.setAttribute("aria-label", "显示密码");
  passwordToggle.title = "显示密码";
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
  if (role === "student") return ["overview", "projects", "teams", "submissions", "reviews", "grades", "logs"];
  if (role === "assistant") return ["overview", "projects", "teams", "submissions", "grades", "logs"];
  if (role === "admin") return ["overview", "projects", "teams", "submissions", "grades", "logs"];
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
    overview: overviewDashboardPage,
    projects: projectsPage,
    teams: teamsPage,
    submissions: submissionsPage,
    reviews: reviewsPage,
    grades: gradesPage,
    logs: logsPage,
  }[state.page];
  const content = document.querySelector("#content");
  const current = pages[state.page];
  content.innerHTML = '<header class="content-heading"><div><h1>' + esc(current.label === "工作台概览" ? "课程项目工作台" : current.label) + '</h1><p>' + esc(current.description) + '</p></div><span class="content-date">当前学期 · 实时数据</span></header>' + renderer();
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

function dashboardStatCard(label, value, suffix, note, iconName, tone, trend) {
  return '<article class="dashboard-stat ' + tone + '"><div class="dashboard-stat-top"><span class="dashboard-stat-icon">' + icon(iconName) + '</span><span class="dashboard-stat-label">' + esc(label) + '</span></div><div class="dashboard-stat-value"><strong>' + esc(value) + '</strong><span>' + esc(suffix) + '</span></div><div class="dashboard-stat-foot"><span class="dashboard-trend">' + esc(trend) + '</span><span>' + esc(note) + '</span></div></article>';
}

function overviewDashboardPage() {
  const p = project();
  if (!p) return emptyState("还没有课程项目", "教师发布项目后，这里将展示实时进展。", "project");
  const grades = p.gradebook || [];
  const validGrades = grades.filter((item) => item.total !== null);
  const average = validGrades.length ? (validGrades.reduce((sum, item) => sum + Number(item.total), 0) / validGrades.length).toFixed(1) : "—";
  const activeSubmissions = state.data.submissions.filter((item) => item.status !== "withdrawn").length;
  const notices = state.data.notifications || [];
  const unread = notices.filter((item) => !item.is_read).length;
  const reviewCount = grades.reduce((sum, item) => sum + Number(item.peer_count || 0), 0);
  const expectedReviews = Math.max(1, memberTotal() * 3);
  const pendingReviews = Math.max(0, expectedReviews - reviewCount);
  const pendingLabel = state.data.current_user.role === "student"
    ? Math.max(0, Math.min(3, (state.data.review_targets || []).length) - (state.data.review_targets || []).filter((item) => item.reviewed).length)
    : pendingReviews;

  return '<div class="dashboard-stats">'
    + dashboardStatCard("项目团队", state.data.teams.length, "个", "团队协作状态正常", "users", "indigo", "● 实时")
    + dashboardStatCard("已提交成果", activeSubmissions, "份", "包含全部历史版本", "file", "teal", "↑ 持续更新")
    + dashboardStatCard("待完成互评", pendingLabel, "项", "匿名分配与公平评价", "review", "violet", p.review_open ? "● 进行中" : "待开放")
    + dashboardStatCard("当前平均成绩", average, "分", validGrades.length + " 支团队已核算", "grade", "blue", average === "—" ? "待评分" : "↑ 已更新")
    + dashboardStatCard("未读通知", unread, "条", "关键节点与风险提醒", "bell", "amber", unread ? "● 待处理" : "全部已读")
    + '</div>'
    + '<div class="dashboard-primary"><section class="dashboard-panel dashboard-progress-panel">'
    + dashboardProjectProgress(p)
    + dashboardTeamProgress(p)
    + '</section><aside class="dashboard-side">'
    + dashboardTodoCard(p)
    + dashboardNoticeCard(notices)
    + '</aside></div>'
    + '<div class="dashboard-analytics">'
    + dashboardTrendCard(activeSubmissions, reviewCount)
    + dashboardGradeComposition(p, validGrades, average)
    + '</div>';
}

function dashboardProjectProgress(p) {
  const iterations = p.iterations || [];
  const active = state.data.submissions.filter((item) => item.status !== "withdrawn");
  const iterationDone = (iteration) => iteration && active.some((item) => item.iteration_id === iteration.id);
  const reviewDone = (p.gradebook || []).some((item) => Number(item.peer_count || 0) > 0);
  const stages = [
    { label: "项目发布", date: "已发布", state: "complete" },
    { label: "团队组建", date: fmt(p.team_deadline).slice(5, 10), state: state.data.teams.length ? "complete" : "current" },
    { label: iterations[0]?.name || "第一次迭代", date: fmt(iterations[0]?.deadline).slice(5, 10), state: iterationDone(iterations[0]) ? "complete" : "current" },
    { label: iterations[1]?.name || "第二次迭代", date: fmt(iterations[1]?.deadline || p.overall_deadline).slice(5, 10), state: iterationDone(iterations[1]) ? "complete" : (iterationDone(iterations[0]) ? "current" : "future") },
    { label: "匿名互评", date: fmt(p.review_deadline).slice(5, 10), state: reviewDone && !p.review_open ? "complete" : (p.review_open ? "current" : "future") },
    { label: "成绩发布", date: fmt(p.overall_deadline).slice(5, 10), state: p.grades_published ? "complete" : "future" },
  ];
  return '<div class="dashboard-panel-head"><div><span class="panel-kicker">PROJECT FLOW</span><h2>' + icon("activity") + '课程项目进度</h2></div><span class="tag green">实时同步</span></div><div class="dashboard-timeline">'
    + stages.map((stage, index) => '<div class="dashboard-stage ' + stage.state + '"><span class="stage-dot">' + (stage.state === "complete" ? icon("check") : index + 1) + '</span><strong>' + esc(stage.label) + '</strong><small>' + esc(stage.date || "待安排") + '</small><em>' + (stage.state === "complete" ? "已完成" : stage.state === "current" ? "进行中" : "待开始") + '</em></div>').join("")
    + '</div>';
}

function dashboardTeamProgress(p) {
  const iterations = p.iterations || [];
  const rows = state.data.teams.slice(0, 4).map((team) => {
    const submissions = state.data.submissions.filter((item) => item.team_id === team.id && item.status !== "withdrawn");
    const grade = (p.gradebook || []).find((item) => item.team_id === team.id) || {};
    const submissionRate = pct(submissions.length, Math.max(1, iterations.length));
    const progress = Math.min(100, Math.round(submissionRate * .72 + (Number(grade.peer_count || 0) ? 18 : 0) + (grade.total !== null && grade.total !== undefined ? 10 : 0)));
    const stage = p.grades_published ? "成绩已发布" : p.review_open ? "匿名互评" : (iterations[Math.min(submissions.length, Math.max(0, iterations.length - 1))]?.name || "项目实施");
    const risk = submissions.length ? ["正常", "green"] : ["需关注", "amber"];
    return '<tr><td><span class="team-name-cell">' + icon("team") + '<strong>' + esc(team.name) + '</strong></span></td><td>' + esc(stage) + '</td><td><span class="status-check">' + (submissions.length ? icon("check") + " 已提交" : "待提交") + '</span></td><td>' + (Number(grade.peer_count || 0) ? "互评完成" : p.review_open ? "互评中" : "待互评") + '</td><td><div class="team-progress-cell"><progress max="100" value="' + progress + '"></progress><strong>' + progress + '%</strong></div></td><td><span class="tag ' + risk[1] + '">' + risk[0] + '</span></td></tr>';
  }).join("");
  return '<div class="dashboard-team-table"><table><thead><tr><th>团队名称</th><th>当前阶段</th><th>提交状态</th><th>互评状态</th><th>项目进度</th><th>风险提示</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
}

function dashboardTodoCard(p) {
  const finalPending = (p.gradebook || []).filter((item) => item.final_score === null || item.final_score === undefined).length;
  const reviewPage = allowedPages(state.data.current_user.role).includes("reviews") ? "reviews" : "grades";
  const todos = [
    { icon: "file", text: "审核最新迭代成果", meta: state.data.submissions.length + " 份记录", level: "高", tone: "red", page: "submissions" },
    { icon: "grade", text: "查看异常互评分数", meta: "匿名评审", level: "中", tone: "amber", page: reviewPage },
    { icon: "check", text: "完成教师终评", meta: finalPending + " 支团队", level: finalPending ? "高" : "低", tone: finalPending ? "red" : "green", page: "grades" },
    { icon: "send", text: p.grades_published ? "查看已发布成绩" : "发布课程成绩", meta: fmt(p.overall_deadline).slice(5, 10), level: "中", tone: "amber", page: "grades" },
  ];
  return '<section class="dashboard-panel dashboard-todo"><div class="dashboard-panel-head compact"><h2>' + icon("log") + '待办事项</h2><span>共 ' + todos.length + ' 项</span></div><div class="todo-list">' + todos.map((item) => '<article><span class="todo-icon">' + icon(item.icon) + '</span><div><strong>' + esc(item.text) + '</strong><small>' + esc(item.meta) + '</small></div><span class="priority ' + item.tone + '">' + item.level + '</span><button type="button" data-jump-page="' + item.page + '">去处理</button></article>').join("") + '</div></section>';
}

function dashboardNoticeCard(notices) {
  const visible = notices.slice(0, 4);
  return '<section class="dashboard-panel dashboard-notices"><div class="dashboard-panel-head compact"><h2>' + icon("bell") + '通知中心</h2>' + (notices.some((item) => !item.is_read) ? '<button class="text-button" data-action="read-all" type="button">全部已读</button>' : '<span>已全部查看</span>') + '</div><div class="dashboard-notice-list">' + (visible.length ? visible.map((item) => '<article data-action="read-notice" data-id="' + item.id + '" data-page="' + item.target_page + '"><i class="' + (!item.is_read ? "unread" : "") + '"></i><div><strong>' + esc(item.title) + '</strong><small>' + esc(item.content) + '</small></div><time>' + fmt(item.created_at).slice(5) + '</time></article>').join("") : '<p class="dashboard-empty-note">暂无通知</p>') + '</div></section>';
}

function dashboardTrendCard(submissionCount, reviewCount) {
  const submissionValues = [0, Math.ceil(submissionCount * .25), Math.ceil(submissionCount * .48), Math.ceil(submissionCount * .75), Math.ceil(submissionCount * .9), submissionCount];
  const reviewValues = [0, 0, Math.ceil(reviewCount * .18), Math.ceil(reviewCount * .48), Math.ceil(reviewCount * .82), reviewCount];
  const max = Math.max(1, ...submissionValues, ...reviewValues);
  const points = (values) => values.map((value, index) => (44 + index * 108) + ',' + (174 - Math.round(value / max * 128))).join(' ');
  return '<section class="dashboard-panel dashboard-trend"><div class="dashboard-panel-head compact"><h2>' + icon("activity") + '提交与评审趋势</h2><div class="chart-legend"><span class="indigo">成果提交</span><span class="teal">互评完成</span></div></div><svg class="trend-svg" viewBox="0 0 590 195" role="img" aria-label="提交与评审趋势折线图"><path class="grid-line" d="M40 46H580M40 88H580M40 130H580M40 174H580"/><polyline class="trend-line submissions" points="' + points(submissionValues) + '"/><polyline class="trend-line reviews" points="' + points(reviewValues) + '"/></svg><div class="chart-axis"><span>项目发布</span><span>团队组建</span><span>第一次迭代</span><span>第二次迭代</span><span>匿名互评</span><span>成绩发布</span></div></section>';
}

function dashboardGradeComposition(p, validGrades, average) {
  const totals = validGrades.map((item) => Number(item.total));
  const highest = totals.length ? Math.max(...totals).toFixed(1).replace('.0', '') : "—";
  const pending = Math.max(0, (p.gradebook || []).length - validGrades.length);
  const peer = Math.round(Number(p.peer_weight) * 100);
  const process = Math.round(Number(p.process_weight) * 100);
  const final = Math.round(Number(p.final_weight) * 100);
  return '<section class="dashboard-panel dashboard-composition"><div class="dashboard-panel-head compact"><h2>' + icon("award") + '成绩构成</h2><span>' + (p.grades_published ? "已发布" : "实时核算") + '</span></div><div class="composition-body"><div class="donut"><span>成绩构成</span></div><div class="composition-legend"><span class="peer">同伴互评 <strong>' + peer + '%</strong></span><span class="process">助教过程评分 <strong>' + process + '%</strong></span><span class="final">教师终评 <strong>' + final + '%</strong></span></div><div class="composition-metrics"><div><span>平均分</span><strong>' + esc(average) + '</strong></div><div><span>最高分</span><strong>' + esc(highest) + '</strong></div><div><span>待评分</span><strong class="amber-text">' + pending + '</strong></div></div></div></section>';
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
    admin: ["全局查看课程与项目", "处理成绩复核与撤回发布", "导出成绩归档和查看审计日志"],
    teacher: ["发布项目并设置评分规则", "开启互评、录入终评分", "发布与导出课程成绩"],
    assistant: ["查看全部团队提交", "记录团队过程分", "查看成绩与审计日志"],
    student: ["浏览任务并参与团队", "负责人提交迭代成果", "完成分配的同伴互评"],
  }[user.role];
  return '<section class="card"><div class="identity-card"><span class="user-avatar">' + esc(initials(user.name)) + '</span><div><h3>' + esc(user.name) + '</h3><span class="tag">' + roleName(user.role) + '</span></div></div><ul class="permission-list">' + permissions.map((item) => '<li>' + icon("check") + "<span>" + item + "</span></li>").join("") + "</ul></section>";
}

function notificationCard() {
  const notices = state.data.notifications || [];
  const unread = notices.filter((item) => !item.is_read).length;
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("bell") + '</span><div><h2>通知中心</h2><p class="subtle">' + unread + ' 条未读消息</p></div></div>' + (unread ? '<button class="button ghost small" data-action="read-all" type="button">全部已读</button>' : '<span class="tag green">' + notices.length + '</span>') + '</div>'
    + (notices.length ? '<div class="notice-list">' + notices.slice(0, 5).map((item) => '<article class="notice ' + (!item.is_read ? "unread" : "") + '" data-action="read-notice" data-id="' + item.id + '" data-page="' + item.target_page + '"><span class="notice-icon">' + icon("bell") + '</span><strong>' + esc(item.title) + '</strong><span>' + esc(item.content) + '</span><time>' + fmt(item.created_at).slice(5) + '</time></article>').join("") + "</div>" : emptyState("暂无通知", "关键节点的提醒会显示在这里。", "bell"))
    + "</section>";
}

function gradeSnapshotCard(p) {
  const weights = [p.peer_weight, p.process_weight, p.final_weight].map((value) => Math.round(Number(value) * 100));
  return '<section class="card flush"><div class="card-head table-card-head"><div class="card-title"><span class="section-icon">' + icon("grade") + '</span><div><h2>成绩快照</h2><p class="subtle">按互评 ' + weights[0] + '% · 过程 ' + weights[1] + '% · 终评 ' + weights[2] + '% 实时计算</p></div></div>' + (p.grades_published ? '<span class="tag green">已发布</span>' : '<span class="tag amber">待发布</span>') + '</div>' + gradeTable(p.gradebook) + "</section>";
}

function gradeTable(items) {
  if (state.data.current_user.role === "student") {
    return '<div class="table-wrap"><table><thead><tr><th>团队</th><th>团队互评均分</th><th>我的最终成绩</th></tr></thead><tbody>'
      + items.map((item) => '<tr><td><strong>' + esc(item.team_name) + '</strong></td><td>' + scoreCell(item.peer_score, "") + '</td><td><span class="score">' + (item.individual_score ?? "—") + '</span></td></tr>').join("")
      + '</tbody></table></div>';
  }
  if (state.data.current_user.role === "assistant") {
    return '<div class="table-wrap"><table><thead><tr><th>团队</th><th>同伴互评</th><th>助教过程分</th></tr></thead><tbody>'
      + items.map((item) => '<tr><td><strong>' + esc(item.team_name) + '</strong></td><td>' + scoreCell(item.peer_score, "") + '</td><td>' + scoreCell(item.process_score, "process") + '</td></tr>').join("")
      + '</tbody></table></div>';
  }
  return '<div class="table-wrap"><table><thead><tr><th>团队</th><th>同伴互评</th><th>过程分</th><th>教师终评</th><th>综合总分</th></tr></thead><tbody>' + items.map((item) => '<tr><td><strong>' + esc(item.team_name) + '</strong></td><td>' + scoreCell(item.peer_score, "") + '</td><td>' + scoreCell(item.process_score, "process") + '</td><td>' + scoreCell(item.final_score, "final") + '</td><td>' + (item.total === null ? '<span class="pending">待核算</span>' : '<span class="score">' + item.total + '</span>') + '</td></tr>').join("") + "</tbody></table></div>";
}
function scoreCell(value, type) {
  if (value === null || value === undefined) return '<span class="pending">待录入</span>';
  return '<div class="score-cell ' + type + '"><div class="score-number"><span>' + value + '</span><small>/100</small></div><progress class="score-bar" max="100" value="' + clamp(value) + '"></progress></div>';
}

function projectsPage() {
  const user = state.data.current_user;
  const action = user.role === "teacher"
    ? '<button class="button ghost" type="button" data-action="new-course">' + icon("plus") + '<span>新建课程</span></button><button class="button" type="button" data-action="new-project">' + icon("plus") + "<span>新建项目</span></button>"
    : "";
  
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("project") + '</span><div><h2>课程项目与迭代</h2><p class="subtle">清晰管理任务要求、阶段截止与评分权重</p></div></div><div class="card-actions">' + action + "</div></div>"
    + state.data.projects.map((item) => 
      '<div class="project-hero spaced ' + (item.id === state.data.active_project_id ? "selected-project" : "") + '">' 
        + '<div class="project-top">' 
          + '<div>' 
            + '<div class="project-meta"><span class="tag ' + (item.status === "published" ? "green" : "amber") + '">' + (item.status === "published" ? "已发布" : "草稿") + '</span><span class="project-code">COURSE · ' + esc(item.course_name) + '</span></div>'
            + '<h2>' + esc(item.title) + '</h2>'
            + '<p class="project-description subtle">' + esc(item.description) + '</p>'
          + '</div>' 
          + '<div class="card-actions project-actions">'
            + '<div class="deadline-block"><span>组队截止 / 项目截止</span><strong>' + fmt(item.team_deadline).slice(5) + ' · ' + fmt(item.overall_deadline).slice(5) + '</strong></div>' 
            + (user.role === "teacher" && !item.grades_published ? '<button class="button ghost small" data-action="edit-weights" data-id="' + item.id + '" type="button">' + icon("edit") + '<span>修改权重</span></button>' : '')
            + (user.role === "teacher" && !item.grades_published ? '<button class="button ghost small" data-action="add-iteration" data-id="' + item.id + '" type="button">' + icon("plus") + '<span>新增迭代</span></button>' : '')
            + (user.role === "teacher" && item.status === "draft" ? '<button class="button secondary small" data-action="publish-project" data-id="' + item.id + '" type="button">确认发布</button>' : '')
            + (item.id !== state.data.active_project_id ? '<button class="button secondary small" data-action="select-project" data-id="' + item.id + '" type="button">切换到此项目</button>' : '<span class="tag green">当前项目</span>')
          + '</div>' 
        + '</div>' 
        + '<div class="weight-top-gap">' + weightPanel(item) + '</div>'
        + '<div class="phase-list phase-top-gap">' + item.iterations.map((phase) => '<div class="phase-item"><i class="phase-marker"></i><div class="phase-copy"><strong>' + esc(phase.name) + '</strong><span>' + esc(phase.requirements) + '</span></div><time class="phase-date">' + fmt(phase.deadline) + '</time></div>').join("") + "</div>"
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
  const createAction = user.role === "student" && !state.data.my_team ? '<button class="button" type="button" data-action="new-team">' + icon("plus") + "<span>创建团队</span></button>" : "";
  return '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("team") + '</span><div><h2>项目团队</h2><p class="subtle">每队 3—5 人，入队申请由组长审核</p></div></div><div class="card-actions">' + createAction + '</div></div><div class="team-grid">' + state.data.teams.map((team) => {
    const status = teamStatus(team);
    const join = user.role === "student" && !state.data.my_team ? '<button class="button secondary small" type="button" data-action="join-team" data-id="' + team.id + '">申请加入</button>' : "";
    const leave = user.role === "student" && state.data.my_team?.id === team.id ? '<button class="button danger small" type="button" data-action="leave-team" data-id="' + team.id + '">退出团队</button>' : "";
    const adjust = ["teacher", "admin"].includes(user.role) ? '<button class="button ghost small" type="button" data-action="adjust-member" data-id="' + team.id + '" data-name="' + esc(team.name) + '">例外调整</button>' : "";
    return '<article class="team-card"><div class="team-card-head"><span class="tag ' + status[1] + '">' + status[0] + '</span><span class="project-code">TEAM · ' + String(team.id).padStart(2, "0") + '</span></div><h3>' + esc(team.name) + '</h3><span class="leader">队长 · ' + esc(team.leader_name) + '</span>' + avatars(team) + '<div class="team-card-foot"><span class="subtle">' + (team.member_count >= 3 ? "人数符合要求" : "还需 " + (3 - team.member_count) + " 人") + '</span><div class="card-actions">' + join + leave + adjust + "</div></div></article>";
  }).join("") + "</div></section>" + joinRequestPanel() + memberTaskPanel();
}

function joinRequestPanel() {
  const requests = state.data.join_requests || [];
  if (!requests.length) return "";
  return '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("users") + '</span><div><h2>入队申请</h2><p class="subtle">申请、审批和结果均保留操作记录</p></div></div></div><div class="table-wrap"><table><thead><tr><th>申请人</th><th>目标团队</th><th>申请时间</th><th>状态</th><th>操作</th></tr></thead><tbody>' + requests.map((item) => '<tr><td><strong>' + esc(item.user_name) + '</strong></td><td>' + esc(item.team_name) + '</td><td>' + fmt(item.requested_at) + '</td><td><span class="tag ' + (item.status === "pending" ? "amber" : item.status === "approved" ? "green" : "gray") + '">' + ({ pending: "待审核", approved: "已同意", rejected: "已拒绝" }[item.status] || esc(item.status)) + '</span></td><td>' + (item.status === "pending" && state.data.current_user.role === "student" && state.data.my_team?.is_leader ? '<div class="card-actions"><button class="button secondary small" data-action="decide-join" data-id="' + item.id + '" data-decision="approved">同意</button><button class="button danger small" data-action="decide-join" data-id="' + item.id + '" data-decision="rejected">拒绝</button></div>' : '—') + '</td></tr>').join("") + '</tbody></table></div></section>';
}

function memberTaskPanel() {
  const tasks = state.data.member_tasks || [];
  const user = state.data.current_user;
  const canAssign = user.role === "student" && state.data.my_team?.is_leader;
  if (!tasks.length && !canAssign) return "";
  const action = canAssign ? '<button class="button" type="button" data-action="new-member-task">' + icon("plus") + '<span>分配成员任务</span></button>' : "";
  return '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("check") + '</span><div><h2>迭代任务分工</h2><p class="subtle">组长分配任务，成员更新个人完成状态</p></div></div><div class="card-actions">' + action + '</div></div>' + (tasks.length ? '<div class="table-wrap"><table><thead><tr><th>迭代</th><th>任务</th><th>负责人</th><th>截止时间</th><th>状态</th><th>操作</th></tr></thead><tbody>' + tasks.map((task) => '<tr><td>' + esc(task.iteration_name) + '</td><td><strong>' + esc(task.title) + '</strong><br><span class="subtle">' + esc(task.description) + '</span></td><td>' + esc(task.assignee_name) + '</td><td>' + fmt(task.due_at) + '</td><td><span class="tag ' + (task.status === "done" ? "green" : task.status === "doing" ? "amber" : "gray") + '">' + ({ todo: "待开始", doing: "进行中", done: "已完成" }[task.status] || task.status) + '</span></td><td>' + (user.role === "student" ? '<button class="button ghost small" data-action="task-status" data-id="' + task.id + '" data-status="' + (task.status === "todo" ? "doing" : task.status === "doing" ? "done" : "todo") + '">' + (task.status === "done" ? "重新开始" : task.status === "doing" ? "标记完成" : "开始任务") + '</button>' : '—') + '</td></tr>').join("") + '</tbody></table></div>' : emptyState("暂无成员任务", "点击右上角为团队成员分配迭代任务。", "check")) + '</section>';
}

function submissionsPage() {
  const user = state.data.current_user;
  const p = project();
  const assignedIterations = new Set((state.data.member_tasks || []).filter((task) => task.assignee_id === user.id).map((task) => task.iteration_id));
  const uploadAction = user.role === "student" ? p.iterations.filter((item) => state.data.my_team?.is_leader || assignedIterations.has(item.id)).map((item) => '<button class="button" type="button" data-action="upload" data-id="' + item.id + '" data-name="' + esc(item.name) + '">' + icon("upload") + '<span>提交 ' + esc(item.name) + '</span></button>').join("") : "";
  const remindAction = user.role === "assistant" || user.role === "teacher" ? p.iterations.map((item) => '<button class="button ghost small" type="button" data-action="remind-missing" data-id="' + item.id + '">催交 ' + esc(item.name) + '</button>').join("") : "";
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("file") + '</span><div><h2>迭代提交记录</h2><p class="subtle">支持 PDF、ZIP、MP4，单文件不超过 200MB</p></div></div><div class="card-actions">' + uploadAction + '</div></div>'
    + (remindAction ? '<div class="card-actions spaced">' + remindAction + '</div>' : '')
    + (user.role === "student" && uploadAction ? '<div class="upload-zone spaced"><div><span class="upload-zone-icon">' + icon("upload") + '</span><strong>按右上角选择迭代并上传成果</strong><span>负责人或被指定成员可提交；系统保留全部版本</span></div></div>' : "")
    + submissionTable()
    + "</section>" + processCheckHistory();
}

function submissionTable() {
  if (!state.data.submissions.length) return emptyState("暂无提交记录", "团队负责人上传成果后，版本和提交时间会显示在这里。", "file");
  const myTeam = state.data.my_team;
  const role = state.data.current_user.role;
  return '<div class="table-wrap"><table><thead><tr><th>团队</th><th>迭代阶段</th><th>成果文件</th><th>状态</th><th>版本</th><th>提交时间</th><th>操作</th></tr></thead><tbody>' + state.data.submissions.map((item) => '<tr><td><strong>' + esc(item.team_name) + '</strong></td><td>' + esc(item.iteration_name) + '</td><td>' + esc(item.file_name) + '</td><td><span class="tag ' + (item.status === "withdrawn" || item.status === "returned" ? "amber" : "green") + '">' + statusText(item.status) + (item.returned_reason ? '<br><small>' + esc(item.returned_reason) + '</small>' : '') + '</span></td><td>v' + item.version + ' · ' + (item.version_count || 1) + ' 个版本</td><td class="nowrap">' + fmt(item.submitted_at) + '</td><td><div class="card-actions"><button class="button ghost small" data-action="download" data-id="' + item.id + '" type="button">下载</button><button class="button ghost small" data-action="versions" data-id="' + item.id + '" type="button">历史</button>' + (role === "assistant" && !project().grades_published ? '<button class="button secondary small" data-action="process-check" data-team="' + item.team_id + '" data-iteration="' + item.iteration_id + '" data-name="' + esc(item.team_name) + ' · ' + esc(item.iteration_name) + '">过程检查</button>' : '') + (myTeam?.id === item.team_id && myTeam?.is_leader && item.status !== "withdrawn" ? '<button class="button danger small" data-action="withdraw" data-id="' + item.id + '" type="button">撤回</button>' : "") + "</div></td></tr>").join("") + "</tbody></table></div>";
}
function statusText(status) {
  return ({ submitted: "已提交", reviewing: "评审中", received: "助教已查收", withdrawn: "已撤回", returned: "已退回", completed: "已完成", archived: "已归档" })[status] || status;
}

function processCheckHistory() {
  const checks = state.data.process_checks || [];
  if (!checks.length) return "";
  return '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("check") + '</span><div><h2>过程检查记录</h2><p class="subtle">按迭代留存查收、退回和阶段评分依据</p></div></div></div><div class="audit-list">' + checks.map((item) => '<article class="audit-item"><span class="audit-marker">' + icon("check") + '</span><div class="audit-copy"><strong>' + esc(item.team_name) + ' · ' + esc(item.iteration_name) + ' · ' + ({ returned: "退回修改", received: "查收", scored: "阶段评分" }[item.action] || item.action) + '</strong><span>' + esc(item.comment) + (item.score === null ? '' : ' · ' + item.score + ' 分') + ' · ' + esc(item.assistant_name) + '</span></div><time class="audit-time">' + fmt(item.created_at) + '</time></article>').join("") + '</div></section>';
}

function reviewsPage() {
  const p = project();
  const user = state.data.current_user;
  if (user.role === "teacher") {
    const completed = p.gradebook.reduce((sum, item) => sum + Number(item.peer_count || 0), 0);
    return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("review") + '</span><div><h2>互评阶段控制</h2><p class="subtle">仅对已提交团队分配；团队不足时自动降级轮转</p></div></div><button class="button ' + (p.review_open ? "danger" : "") + '" type="button" data-action="toggle-review">' + icon(p.review_open ? "lock" : "send") + "<span>" + (p.review_open ? "关闭互评" : "开启互评") + '</span></button></div><div class="project-hero"><div class="project-top"><div><span class="tag ' + (p.review_open ? "green" : "gray") + '">' + (p.review_open ? "互评进行中" : "互评未开启") + '</span><h2>本轮互评已收集 ' + completed + ' 份评价</h2><p class="subtle">系统会阻止学生评价本团队，并限制每人最多评价 3 个其他团队。</p></div><div class="deadline-block"><span>当前阶段</span><strong>' + (p.review_open ? "开放提交" : "暂停提交") + "</strong></div></div></div></section>" + reviewAlertsPanel();
  }
  if (user.role !== "student") return emptyState("当前角色不参与同伴互评", "助教可以在评分页面查看团队得分。", "review");
  const targets = state.data.review_targets || [];
  const completed = targets.filter((item) => item.reviewed).length;
  
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("review") + '</span><div><h2>我的互评任务</h2><p class="subtle">已完成 ' + completed + "/" + Math.min(3, targets.length) + ' 项 · 系统不会公开对方身份</p></div></div><span class="tag ' + (p.review_open ? "green" : "gray") + '">' + (p.review_open ? "互评开放" : "互评关闭") + '</span></div><div class="review-grid">' + targets.map((target) => '<article class="review-card ' + (target.reviewed ? "complete" : "") + '"><span class="tag ' + (target.reviewed ? "green" : target.review_status === "draft" ? "violet" : "amber") + '">' + (target.reviewed ? "已完成" : target.review_status === "draft" ? "草稿" : "待评价") + '</span><h3>' + esc(target.name) + '</h3><p class="subtle">匿名查看成果后，从完成度、创新性和文档质量分别评分。</p><div class="review-score"><strong>' + (target.current_score ?? "—") + '</strong><span>三维平均分</span></div><div class="card-actions review-actions-center">' + (target.has_submission ? '<button class="button ghost small" type="button" data-action="download-review" data-id="' + target.assignment_id + '">' + icon("download") + ' <span>下载匿名成果</span></button>' : '') + '<button class="button secondary small" type="button" data-action="review" data-id="' + target.assignment_id + '" data-name="' + esc(target.name) + '" data-completeness="' + (target.completeness_score ?? 85) + '" data-innovation="' + (target.innovation_score ?? 85) + '" data-documentation="' + (target.documentation_score ?? 85) + '">' + icon("edit") + "<span>" + (target.reviewed || target.review_status === "draft" ? "继续评价" : "开始评价") + "</span></button></div></article>").join("") + "</div></section>";
}

function reviewAlertsPanel() {
  const alerts = state.data.review_alerts || [];
  if (!alerts.length) return "";
  return '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("activity") + '</span><div><h2>异常评分预警</h2><p class="subtle">评分离散度过大时挂起预警，人工复核后方可发布成绩</p></div></div></div><div class="audit-list">' + alerts.map((item) => '<article class="audit-item"><span class="audit-marker ' + (item.status === "open" ? "score-log" : "") + '">' + icon("activity") + '</span><div class="audit-copy"><strong>' + esc(item.team_name) + ' · ' + (item.status === "open" ? "待复核" : "已处理") + '</strong><span>' + esc(item.detail) + (item.resolution ? ' · 结论：' + esc(item.resolution) : '') + '</span></div>' + (item.status === "open" ? '<button class="button danger small" data-action="resolve-alert" data-id="' + item.id + '">处理预警</button>' : '<span class="tag green">已处理</span>') + '</article>').join("") + '</div></section>';
}

function gradesPage() {
  const p = project();
  const user = state.data.current_user;
  if (user.role === "student" && !p.grades_published) return emptyState("成绩尚未发布", "教师完成所有评分并发布后，你可以在这里查看本团队成绩。", "grade");
  if (!p.gradebook.length) return emptyState("暂无可显示的成绩", "当前项目还没有形成成绩记录。", "grade");
  const actions = (user.role === "teacher"
    ? (p.grades_published ? '<button class="button ghost" type="button" data-action="export">' + icon("download") + '<span>导出 Excel</span></button><button class="button ghost" type="button" data-action="export-pdf">' + icon("download") + '<span>导出 PDF</span></button><button class="button danger" type="button" data-action="unpublish-grades">撤回发布</button>' : '<button class="button" type="button" data-action="publish-grades">' + icon("send") + "<span>发布成绩</span></button>")
    : user.role === "admin" ? (p.grades_published ? '<button class="button ghost" type="button" data-action="export">' + icon("download") + '<span>导出 Excel</span></button><button class="button ghost" type="button" data-action="export-pdf">' + icon("download") + '<span>导出 PDF</span></button><button class="button danger" type="button" data-action="unpublish-grades">撤回发布</button>' : '<span class="tag amber">等待教师发布</span>')
    : user.role === "assistant" ? '<span class="tag gray">可录入过程分</span>'
    : '<button class="button ghost" type="button" data-action="new-appeal">申请成绩复核</button>');
  const formula = '总分 = 互评 × ' + Number(p.peer_weight) * 100 + '% + 过程分 × ' + Number(p.process_weight) * 100 + '% + 终评 × ' + Number(p.final_weight) * 100 + '%';
  const personal = user.role === "teacher" ? individualGradesPanel(p.gradebook, p.grades_published) : "";
  return '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("grade") + '</span><div><h2>成绩汇总</h2><p class="subtle">' + (user.role === "student" ? "仅展示本人允许查看的成绩字段" : formula) + '</p></div></div><div class="card-actions">' + actions + "</div></div>" + gradeTable(p.gradebook) + "</section>"
    + (user.role === "student" ? "" : '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("award") + '</span><div><h2>团队成绩构成</h2><p class="subtle">查看各评分环节占比并完成待录入项</p></div></div></div><div class="grade-team-grid">' + p.gradebook.map((item) => gradeTeamCard(item, user)).join("") + "</div></section>") + personal + gradeAppealPanel() + (user.role === "assistant" ? reviewAlertsPanel() : "");
}

function gradeAppealPanel() {
  const appeals = state.data.grade_appeals || [];
  if (!appeals.length) return "";
  const canResolve = ["teacher", "admin"].includes(state.data.current_user.role);
  return '<section class="card spaced"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("info") + '</span><div><h2>成绩复核记录</h2><p class="subtle">申请、处理结论和操作者全程留痕</p></div></div></div><div class="audit-list">' + appeals.map((item) => '<article class="audit-item"><span class="audit-marker">' + icon("info") + '</span><div class="audit-copy"><strong>' + esc(item.user_name) + ' · ' + ({ pending: "待处理", approved: "复核通过", rejected: "维持原成绩" }[item.status] || item.status) + '</strong><span>申请理由：' + esc(item.reason) + (item.result ? ' · 处理结论：' + esc(item.result) : '') + '</span></div>' + (canResolve && item.status === "pending" ? '<button class="button secondary small" data-action="resolve-appeal" data-id="' + item.id + '">处理</button>' : '<span class="tag ' + (item.status === "pending" ? "amber" : "green") + '">' + ({ pending: "待处理", approved: "已通过", rejected: "已驳回" }[item.status] || item.status) + '</span>') + '</article>').join("") + '</div></section>';
}
function individualGradesPanel(items, locked) {
  const people = items.flatMap((team) => (team.individuals || []).map((person) => ({ ...person, team_name: team.team_name })));
  if (!people.length) return "";
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("team") + '</span><div><h2>个人成绩核定</h2><p class="subtle">个人成绩 = 团队总分 × 系数 − 人工扣分 − 缺评扣分</p></div></div></div><div class="table-wrap"><table><thead><tr><th>团队</th><th>成员</th><th>系数</th><th>人工扣分</th><th>缺评扣分</th><th>个人成绩</th><th>操作</th></tr></thead><tbody>' + people.map((person) => '<tr><td>' + esc(person.team_name) + '</td><td><strong>' + esc(person.user_name) + '</strong></td><td>' + person.coefficient + '</td><td>' + person.manual_deduction + '</td><td>' + person.missing_review_penalty + '</td><td><span class="score">' + (person.individual_score ?? "—") + '</span></td><td>' + (locked ? '<span class="tag gray">已冻结</span>' : '<button class="button ghost small" type="button" data-action="adjust-individual" data-id="' + esc(person.user_id) + '" data-name="' + esc(person.user_name) + '" data-coefficient="' + person.coefficient + '" data-deduction="' + person.manual_deduction + '">核定</button>') + '</td></tr>').join("") + '</tbody></table></div></section>';
}
function gradeTeamCard(item, user) {
  const locked = project().grades_published;
  const buttons = (!locked && user.role === "assistant" ? '<button class="button secondary small" type="button" data-action="score-process" data-id="' + item.team_id + '" data-name="' + esc(item.team_name) + '">过程分</button>' : "")
    + (!locked && user.role === "teacher" ? '<button class="button secondary small" type="button" data-action="score-final" data-id="' + item.team_id + '" data-name="' + esc(item.team_name) + '">终评分</button>' : "");
  return '<article class="grade-team-card"><div class="grade-team-top"><div><h3>' + esc(item.team_name) + '</h3><span class="subtle">' + (item.total === null ? "仍有评分待录入" : "成绩构成完整") + '</span></div><strong class="grade-total">' + (item.total ?? "—") + '</strong></div><div class="composition"><i class="part-peer ' + (item.peer_score === null ? "missing" : "") + '"></i><i class="part-process ' + (item.process_score === null ? "missing" : "") + '"></i><i class="part-final ' + (item.final_score === null ? "missing" : "") + '"></i></div><div class="legend"><span>互评 ' + (item.peer_score ?? "—") + '</span><span>过程 ' + (item.process_score ?? "—") + '</span><span>终评 ' + (item.final_score ?? "—") + '</span></div><div class="card-actions top-gap">' + buttons + "</div></article>";
}

function logsPage() {
  const logs = state.data.logs || [];
  const adminActions = state.data.current_user.role === "admin" ? '<div class="card-actions"><button class="button ghost small" data-action="verify-audit">校验审计链</button><button class="button secondary small" data-action="backup-database">立即备份</button></div>' : '<span class="tag">' + logs.length + ' 条记录</span>';
  return '<section class="card"><div class="card-head"><div class="card-title"><span class="section-icon">' + icon("log") + '</span><div><h2>过程审计日志</h2><p class="subtle">关键操作使用 SHA-256 哈希链留痕，可检测异常篡改</p></div></div>' + adminActions + '</div>'
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
  document.querySelectorAll("[data-jump-page]").forEach((button) => {
    button.onclick = () => {
      const target = button.dataset.jumpPage;
      if (!pages[target] || !allowedPages(state.data.current_user.role).includes(target)) return;
      state.page = target;
      renderShell();
      render();
      document.querySelector("#content").focus({ preventScroll: true });
    };
  });
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.onclick = () => runBusy(button, async () => {
      const action = button.dataset.action;
      const p = project();
      try {
        if (action === "new-course") {
          openModal("新建课程", "创建课程框架后即可在课程下发布多个项目任务", formHtml(
            '<div class="field full"><label class="required" for="f-course-name">课程名称</label><input id="f-course-name" placeholder="例如：软件工程"></div>'
            + '<div class="field full"><label class="required" for="f-course-term">开课学期</label><input id="f-course-term" placeholder="例如：2026 秋"></div>',
            "创建课程"
          ));
          bindModalSubmit(async () => {
            await api("/api/courses", { method: "POST", body: JSON.stringify({ name: requiredValue("f-course-name", "请输入课程名称"), term: requiredValue("f-course-term", "请输入开课学期") }) });
            closeModal(); toast("课程创建成功"); await load({ quiet: true });
          });
        } else if (action === "new-project") {
          const courseOptions = state.data.courses.map((course) => '<option value="' + course.id + '">' + esc(course.name) + ' · ' + esc(course.term) + '</option>').join("");
          openModal("新建项目", "可保存草稿，确认后再向学生发布", formHtml(
            '<div class="form-section-title">项目基本信息</div>'
            + '<div class="field full"><label class="required" for="f-course">所属课程</label><select id="f-course">' + courseOptions + '</select></div>'
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
            "保存项目"
          ));
          document.querySelector(".form-grid").insertAdjacentHTML("beforeend", '<div class="field full"><label><input id="f-save-draft" type="checkbox"> 先保存为草稿，暂不通知学生</label></div>');
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
              course_id: Number(value("f-course")),
              save_as_draft: document.querySelector("#f-save-draft").checked,
              iterations: [{ name: "迭代 1", deadline: requiredValue("f-iteration-deadline", "请选择迭代截止时间"), requirements: requiredValue("f-requirements", "请输入迭代要求") }],
            };
            if (payload.peer_weight + payload.process_weight + payload.final_weight !== 100) throw new Error("三项评分权重必须合计 100%");
            await api("/api/projects", { method: "POST", body: JSON.stringify(payload) });
            closeModal(); toast(payload.save_as_draft ? "项目草稿已保存" : "项目发布成功"); await load({ quiet: true });
          });
        } else if (action === "add-iteration") {
          openModal("新增迭代阶段", "每个迭代具有独立截止时间和提交要求", formHtml(
            '<div class="field full"><label class="required" for="f-name">迭代名称</label><input id="f-name" placeholder="例如：迭代 2：设计与实现"></div>'
            + '<div class="field full"><label class="required" for="f-deadline">截止时间</label><input id="f-deadline" type="datetime-local"></div>'
            + '<div class="field full"><label class="required" for="f-requirements">提交要求</label><textarea id="f-requirements" placeholder="说明本轮需要提交的成果"></textarea></div>',
            "新增迭代"
          ));
          bindModalSubmit(async () => {
            await api("/api/projects/" + button.dataset.id + "/iterations", { method: "POST", body: JSON.stringify({ name: requiredValue("f-name", "请输入迭代名称"), deadline: requiredValue("f-deadline", "请选择截止时间"), requirements: requiredValue("f-requirements", "请输入提交要求") }) });
            closeModal(); toast("迭代已添加"); await load({ quiet: true });
          });
        } else if (action === "publish-project") {
          if (!window.confirm("发布后课程成员将收到通知，确认发布该项目吗？")) return;
          await api("/api/projects/" + button.dataset.id + "/publish", { method: "POST" });
          toast("项目发布成功"); await load({ quiet: true });
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
        } else if (action === "decide-join") {
          await api("/api/team-join-requests/" + button.dataset.id + "/decision", { method: "POST", body: JSON.stringify({ decision: button.dataset.decision }) });
          toast("入队申请已处理"); await load({ quiet: true });
        } else if (action === "adjust-member") {
          const studentOptions = (state.data.users || []).filter((item) => item.role === "student").map((student) => '<option value="' + student.id + '">' + esc(student.name) + ' · ' + esc(student.id) + '</option>').join("");
          openModal("例外调整 · " + button.dataset.name, "教师或教务管理员的成员调整必须填写原因并留痕", formHtml(
            '<div class="field"><label class="required" for="f-member-action">调整动作</label><select id="f-member-action"><option value="add">加入团队</option><option value="remove">移出团队</option></select></div>'
            + '<div class="field"><label class="required" for="f-member-user">学生</label><select id="f-member-user">' + studentOptions + '</select></div>'
            + '<div class="field full"><label class="required" for="f-member-reason">调整理由</label><textarea id="f-member-reason" placeholder="例如：经任课教师批准的特殊换组"></textarea></div>',
            "确认调整"
          ));
          bindModalSubmit(async () => {
            await api("/api/teams/" + button.dataset.id + "/members/adjust", { method: "POST", body: JSON.stringify({ action: value("f-member-action"), user_id: value("f-member-user"), reason: requiredValue("f-member-reason", "请填写调整理由") }) });
            closeModal(); toast("团队成员已调整并留痕"); await load({ quiet: true });
          });
        } else if (action === "new-member-task") {
          const team = state.data.teams.find((item) => item.id === state.data.my_team?.id);
          const memberOptions = (team?.member_details || []).map((member) => '<option value="' + member.id + '">' + esc(member.name) + (member.is_leader ? " · 组长" : "") + '</option>').join("");
          const iterationOptions = (p.iterations || []).map((iteration) => '<option value="' + iteration.id + '">' + esc(iteration.name) + '</option>').join("");
          openModal("分配成员任务", "明确负责人、迭代节点和交付时间", formHtml(
            '<div class="field"><label class="required" for="f-iteration">所属迭代</label><select id="f-iteration">' + iterationOptions + '</select></div>'
            + '<div class="field"><label class="required" for="f-assignee">负责人</label><select id="f-assignee">' + memberOptions + '</select></div>'
            + '<div class="field full"><label class="required" for="f-task-title">任务名称</label><input id="f-task-title" placeholder="例如：完成接口测试"></div>'
            + '<div class="field full"><label class="required" for="f-task-description">任务说明</label><textarea id="f-task-description" placeholder="说明交付内容和验收标准"></textarea></div>'
            + '<div class="field full"><label class="required" for="f-task-due">截止时间</label><input id="f-task-due" type="datetime-local"></div>',
            "分配任务"
          ));
          bindModalSubmit(async () => {
            await api("/api/member-tasks", { method: "POST", body: JSON.stringify({ project_id: p.id, iteration_id: Number(value("f-iteration")), assignee_id: value("f-assignee"), title: requiredValue("f-task-title", "请输入任务名称"), description: requiredValue("f-task-description", "请输入任务说明"), due_at: requiredValue("f-task-due", "请选择截止时间") }) });
            closeModal(); toast("成员任务已分配"); await load({ quiet: true });
          });
        } else if (action === "task-status") {
          await api("/api/member-tasks/" + button.dataset.id, { method: "PATCH", body: JSON.stringify({ status: button.dataset.status }) });
          toast("任务状态已更新"); await load({ quiet: true });
        } else if (action === "join-team") {
          if (!window.confirm("确认申请加入这个团队吗？")) return;
          await api("/api/teams/" + button.dataset.id + "/join", { method: "POST" });
          toast("入队申请已提交"); await load({ quiet: true });
        } else if (action === "leave-team") {
          if (!window.confirm("退出后可能由下一名成员自动接任队长，确认继续吗？")) return;
          await api("/api/teams/" + button.dataset.id + "/leave", { method: "POST" });
          toast("已退出团队"); await load({ quiet: true });
        } else if (action === "upload") {
          if (p.grades_published) return toast("成绩已发布，不能再上传成果", true);
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
            const existing = state.data.submissions.find((item) => item.iteration_id === Number(button.dataset.id) && item.team_id === state.data.my_team?.id);
            if (existing?.lock_version) form.append("lock_version", existing.lock_version);
            await api("/api/submissions/" + button.dataset.id, { method: "POST", body: form });
            closeModal(); toast("成果提交成功，版本记录已更新"); await load({ quiet: true });
          });
        } else if (action === "remind-missing") {
          const result = await api("/api/projects/" + p.id + "/remind-missing", { method: "POST", body: JSON.stringify({ iteration_id: Number(button.dataset.id) }) });
          toast(result.message); await load({ quiet: true });
        } else if (action === "process-check") {
          openModal("过程检查 · " + button.dataset.name, "查收会形成阶段过程分；退回时必须说明修改原因", formHtml(
            '<div class="field"><label class="required" for="f-check-action">处理动作</label><select id="f-check-action"><option value="received">查收并评分</option><option value="returned">退回修改</option></select></div>'
            + '<div class="field"><label for="f-check-score">阶段过程分</label><input id="f-check-score" type="number" min="0" max="100" value="85"></div>'
            + '<div class="field full"><label class="required" for="f-check-comment">检查说明</label><textarea id="f-check-comment" placeholder="记录检查结论、问题或修改要求"></textarea></div>',
            "保存检查结果"
          ));
          bindModalSubmit(async () => {
            const checkAction = value("f-check-action");
            const payload = { project_id: p.id, team_id: Number(button.dataset.team), iteration_id: Number(button.dataset.iteration), action: checkAction, comment: requiredValue("f-check-comment", "请填写检查说明") };
            if (checkAction !== "returned") payload.score = Number(value("f-check-score"));
            await api("/api/process-checks", { method: "POST", body: JSON.stringify(payload) });
            closeModal(); toast("过程检查已记录"); await load({ quiet: true });
          });
        } else if (action === "download") {
          const response = await api("/api/submissions/" + button.dataset.id + "/download");
          const blob = await response.blob();
          const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = responseFilename(response, "submission"); link.click(); URL.revokeObjectURL(link.href);
          toast("文件下载已开始");
        } else if (action === "download-review") {
          const response = await api("/api/review-assignments/" + encodeURIComponent(button.dataset.id) + "/download");
          const blob = await response.blob();
          const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = responseFilename(response, "anonymous-submission"); link.click(); URL.revokeObjectURL(link.href);
          toast("匿名成果下载已开始");
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
          openModal("评价 " + button.dataset.name, "三个维度分别评分，系统自动计算平均分", formHtml(
            '<div class="field"><label for="f-completeness">完成度</label><input id="f-completeness" type="number" min="0" max="100" value="' + button.dataset.completeness + '"></div>'
            + '<div class="field"><label for="f-innovation">创新性</label><input id="f-innovation" type="number" min="0" max="100" value="' + button.dataset.innovation + '"></div>'
            + '<div class="field"><label for="f-documentation">文档质量</label><input id="f-documentation" type="number" min="0" max="100" value="' + button.dataset.documentation + '"></div>'
            + '<div class="field full"><label class="required" for="f-comment">评价意见</label><textarea id="f-comment" placeholder="请写出具体优点和一条可执行的改进建议"></textarea><span class="field-error">请填写评价意见</span></div>',
            "保存互评"
          ));
          document.querySelector(".form-grid").insertAdjacentHTML("beforeend", '<div class="field full"><label><input id="f-review-draft" type="checkbox"> 仅保存草稿，稍后继续填写</label></div>');
          bindModalSubmit(async () => {
            const draft = document.querySelector("#f-review-draft").checked;
            const completeness = Number(value("f-completeness"));
            const innovation = Number(value("f-innovation"));
            const documentation = Number(value("f-documentation"));
            if ([completeness, innovation, documentation].some((score) => !Number.isFinite(score) || score < 0 || score > 100)) throw new Error("三个维度评分必须在 0—100 之间");
            const comment = draft ? value("f-comment") : requiredValue("f-comment", "正式提交时请填写评价意见");
            const average = Math.round(((completeness + innovation + documentation) / 3) * 100) / 100;
            if (!draft && !window.confirm("三维平均分为 " + average + " 分，确认正式提交吗？")) return;
            await api("/api/reviews", { method: "POST", body: JSON.stringify({ project_id: p.id, assignment_id: button.dataset.id, completeness_score: completeness, innovation_score: innovation, documentation_score: documentation, comment, status: draft ? "draft" : "submitted" }) });
            closeModal(); toast(draft ? "互评草稿已保存" : "互评已提交"); await load({ quiet: true });
          });
        } else if (action === "resolve-alert") {
          openModal("处理异常评分预警", "请核查评分分布和评价内容，并记录可审计的复核结论", formHtml('<div class="field full"><label class="required" for="f-resolution">复核结论</label><textarea id="f-resolution" placeholder="例如：评分差异有合理依据，允许计入成绩"></textarea></div>', "确认处理"));
          bindModalSubmit(async () => {
            await api("/api/review-alerts/" + button.dataset.id + "/resolve", { method: "POST", body: JSON.stringify({ resolution: requiredValue("f-resolution", "请填写复核结论") }) });
            closeModal(); toast("预警已处理"); await load({ quiet: true });
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
        } else if (action === "adjust-individual") {
          openModal("核定 " + button.dataset.name + " 的个人成绩", "折算系数只能下调；调整必须填写理由并写入审计日志", formHtml(
            '<div class="field"><label class="required" for="f-coefficient">折算系数</label><input id="f-coefficient" type="number" min="0" max="1" step="0.01" value="' + button.dataset.coefficient + '"></div>'
            + '<div class="field"><label class="required" for="f-deduction">人工扣分</label><input id="f-deduction" type="number" min="0" max="100" step="0.1" value="' + button.dataset.deduction + '"></div>'
            + '<div class="field full"><label class="required" for="f-reason">调整理由</label><textarea id="f-reason" placeholder="请记录可复核的教学依据"></textarea></div>',
            "保存核定"
          ));
          bindModalSubmit(async () => {
            const coefficient = Number(value("f-coefficient"));
            const manualDeduction = Number(value("f-deduction"));
            if (!Number.isFinite(coefficient) || coefficient < 0 || coefficient > 1) throw new Error("折算系数必须在 0—1 之间");
            if (!Number.isFinite(manualDeduction) || manualDeduction < 0 || manualDeduction > 100) throw new Error("人工扣分必须在 0—100 之间");
            await api("/api/individual-adjustments", { method: "POST", body: JSON.stringify({ project_id: p.id, user_id: button.dataset.id, coefficient, manual_deduction: manualDeduction, reason: requiredValue("f-reason", "请填写调整理由") }) });
            closeModal(); toast("个人成绩核定已保存"); await load({ quiet: true });
          });
        } else if (action === "new-appeal") {
          openModal("申请成绩复核", "请说明需要核查的评分环节和事实依据", formHtml('<div class="field full"><label class="required" for="f-reason">复核理由</label><textarea id="f-reason" placeholder="例如：过程检查记录与成绩明细不一致"></textarea></div>', "提交申请"));
          bindModalSubmit(async () => {
            await api("/api/grade-appeals", { method: "POST", body: JSON.stringify({ project_id: p.id, reason: requiredValue("f-reason", "请填写复核理由") }) });
            closeModal(); toast("成绩复核申请已提交"); await load({ quiet: true });
          });
        } else if (action === "resolve-appeal") {
          openModal("处理成绩复核", "处理结论会通知学生并写入审计日志", formHtml(
            '<div class="field"><label class="required" for="f-decision">处理结果</label><select id="f-decision"><option value="approved">复核通过</option><option value="rejected">维持原成绩</option></select></div>'
            + '<div class="field full"><label class="required" for="f-result">复核结论</label><textarea id="f-result" placeholder="记录核查依据和处理结果"></textarea></div>',
            "完成处理"
          ));
          bindModalSubmit(async () => {
            await api("/api/grade-appeals/" + button.dataset.id + "/resolve", { method: "POST", body: JSON.stringify({ decision: value("f-decision"), result: requiredValue("f-result", "请填写复核结论") }) });
            closeModal(); toast("成绩复核已处理"); await load({ quiet: true });
          });
        } else if (action === "publish-grades") {
          if (!window.confirm("发布后学生将收到成绩通知，确认继续吗？")) return;
          await api("/api/projects/" + p.id + "/publish-grades", { method: "POST" });
          toast("成绩已发布"); await load({ quiet: true });
        } else if (action === "unpublish-grades") {
          openModal("撤回成绩发布", "历史发布快照会保留；撤回后可修正并重新发布", formHtml('<div class="field full"><label class="required" for="f-reason">撤回理由</label><textarea id="f-reason" placeholder="请填写可审计的撤回理由"></textarea></div>', "确认撤回"));
          bindModalSubmit(async () => {
            await api("/api/projects/" + p.id + "/unpublish-grades", { method: "POST", body: JSON.stringify({ reason: requiredValue("f-reason", "请填写撤回理由") }) });
            closeModal(); toast("成绩发布已撤回"); await load({ quiet: true });
          });
        } else if (action === "export") {
          const response = await api("/api/projects/" + p.id + "/grades.xlsx");
          const blob = await response.blob(); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "project-" + p.id + "-grades.xlsx"; link.click(); URL.revokeObjectURL(link.href); toast("Excel 成绩归档已导出");
        } else if (action === "export-pdf") {
          const response = await api("/api/projects/" + p.id + "/grades.pdf");
          const blob = await response.blob(); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = responseFilename(response, "project-" + p.id + "-grades.pdf"); link.click(); URL.revokeObjectURL(link.href); toast("PDF 成绩归档已导出");
        } else if (action === "verify-audit") {
          const result = await api("/api/audit/verify");
          toast(result.message, !result.valid);
        } else if (action === "backup-database") {
          if (!window.confirm("确认立即创建数据库全量备份吗？")) return;
          const result = await api("/api/admin/backup", { method: "POST" });
          toast(result.message + " · " + result.file);
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
document.querySelector("#login-password-toggle").onclick = (event) => {
  const input = document.querySelector("#login-password");
  const showing = input.type === "text";
  input.type = showing ? "password" : "text";
  event.currentTarget.setAttribute("aria-label", showing ? "显示密码" : "隐藏密码");
  event.currentTarget.title = showing ? "显示密码" : "隐藏密码";
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

