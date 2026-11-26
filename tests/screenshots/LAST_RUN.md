# Course_platform V4 自动化测试报告

> 本报告由 `tests/test_script.py --mode all` 于 2026-11-26T18:07:43+08:00 自动生成。截图使用相对路径，可直接在 GitHub 中显示。

## 1. 测试结论

| 测试部分 | 状态 | 用例数 | 通过 | 失败 |
| --- | --- | ---: | ---: | ---: |
| 后端与业务接口 | PASS | 33 | 33 | 0 |
| 前端浏览器页面 | PASS | 28 | 28 | 0 |
| **本次总结果** | **PASS** | **61** | **61** | **0** |

## 2. 执行顺序与方法

1. 后端阶段：使用 pytest 和 Flask 测试客户端，逐项测试接口、数据校验、角色权限与业务闭环。
2. 前端阶段：自动启动临时测试服务，依次测试登录页、错误密码，再按“教务管理员 → 教师 → 助教 → 学生”登录。
3. 每个角色按左侧导航从上到下测试全部可见页面；页面须可访问、内容非空，且不得出现 HTTP 500 或非预期控制台错误。
4. 每一步前端检查均保存截图；无论 PASS 或 FAIL 都会记录状态。失败时报告保留错误信息和当时截图。

后端单独运行：`python tests/test_script.py --mode backend`  
前端单独运行：`python tests/test_script.py --mode frontend`  
完整运行：`python tests/test_script.py --mode all`

## 3. 测试运行环境

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows-10-10.0.26300-SP0 |
| Conda 环境 | course_platform_test |
| Python | 3.11.18 |
| pytest | 7.4.4 |
| Flask | 3.0.3 |
| Playwright | 1.65.2 |
| Chromium | 159.0.8154.6 |
| Git 分支 | course-platform-final-tested |
| Git 提交 | 024a85d |
| 测试服务 | http://127.0.0.1:5088 |
| 测试数据 | 临时隔离数据库（不修改正式数据） |

## 4. 后端与业务接口逐项结果

| 编号 | 状态 | 测试说明 | 来源 |
| --- | --- | --- | --- |
| BE-01 | PASSED | AC-03 逾期成果提交被拒绝且不生成有效记录 | `backend/tests/test_app.py` |
| BE-02 | PASSED | 互评去除极值并保留一位小数 | `backend/tests/test_app.py` |
| BE-03 | PASSED | 成绩发布快照、学生隐私及 Excel/PDF 导出 | `backend/tests/test_app.py` |
| BE-04 | PASSED | 匿名互评分配下载及匿名文件名 | `backend/tests/test_app.py` |
| BE-05 | PASSED | 助教无权录入或查看教师终评分 | `backend/tests/test_app.py` |
| BE-06 | PASSED | 未登录拦截、错误密码及教师登录 | `backend/tests/test_app.py` |
| BE-07 | PASSED | 综合成绩计算公式 | `backend/tests/test_app.py` |
| BE-08 | PASSED | 单条通知标记已读 | `backend/tests/test_app.py` |
| BE-09 | PASSED | 学生无法直接下载其他团队文件 | `backend/tests/test_app.py` |
| BE-10 | PASSED | 互评不足两份时显示边界预警 | `backend/tests/test_app.py` |
| BE-11 | PASSED | 互评必须具有系统分配任务 | `backend/tests/test_app.py` |
| BE-12 | PASSED | 评分团队必须属于当前项目 | `backend/tests/test_app.py` |
| BE-13 | PASSED | 团队人数不足时禁止提交 | `backend/tests/test_app.py` |
| BE-14 | PASSED | 学生数据范围不泄露其他团队信息 | `backend/tests/test_app.py` |
| BE-15 | PASSED | 学生无权创建项目 | `backend/tests/test_app.py` |
| BE-16 | PASSED | 未知用户返回规范 JSON 401 | `backend/tests/test_app.py` |
| BE-17 | PASSED | 撤回成绩后保留历史快照 | `backend/tests/test_app.py` |
| BE-18 | PASSED | 未发布成绩对学生隐藏 | `backend/tests/test_app.py` |
| BE-19 | PASSED | 课程创建、项目草稿及正式发布 | `backend/tests/test_app.py` |
| BE-20 | PASSED | 学生成绩申诉、管理员处理、审计与备份 | `backend/tests/test_app.py` |
| BE-21 | PASSED | 入队申请必须由组长审批 | `backend/tests/test_app.py` |
| BE-22 | PASSED | 连续五次登录失败后账号锁定 | `backend/tests/test_app.py` |
| BE-23 | PASSED | 指定成员任务及成果提交权限 | `backend/tests/test_app.py` |
| BE-24 | PASSED | 三维互评、草稿及异常评分预警 | `backend/tests/test_app.py` |
| BE-25 | PASSED | 助教退回、查收及迭代过程评分 | `backend/tests/test_app.py` |
| BE-26 | PASSED | 评分权重范围及总和校验 | `backend/tests/test_app.py` |
| BE-27 | PASSED | 创建/退出团队及教师例外调员 | `tests/test_full_api.py` |
| BE-28 | PASSED | 成绩发布后 CSV 导出 | `tests/test_full_api.py` |
| BE-29 | PASSED | 成员任务创建及状态更新 | `tests/test_full_api.py` |
| BE-30 | PASSED | 项目修改及新增迭代 | `tests/test_full_api.py` |
| BE-31 | PASSED | 公共接口、会话、全部已读及退出 | `tests/test_full_api.py` |
| BE-32 | PASSED | 催交、互评开关、预警处理及过程/终评分 | `tests/test_full_api.py` |
| BE-33 | PASSED | 成果上传、下载、版本历史及撤回 | `tests/test_full_api.py` |

完整 pytest 日志：[`screenshots/backend-tests.log`](screenshots/backend-tests.log)

### 4.1 需求分析验收追踪

| 需求/验收项 | 验证内容 | 关联测试 | 结果 |
| --- | --- | --- | --- |
| AC-01 | 评分权重合计必须为 100% | BE-26 | PASS |
| AC-02 | 在线组队、申请审批与教师例外调员留痕 | BE-21、BE-27 | PASS |
| AC-03 | 迭代截止后拒绝成果提交 | BE-01 | PASS |
| AC-04 | 互评去除最高分和最低分后计算平均值 | BE-02 | PASS |
| AC-05 | 助教过程检查、退回、催交与操作记录 | BE-25、BE-32 | PASS |
| AC-06 | 成绩加权、个人隐私、发布与撤回快照 | BE-03、BE-17 | PASS |
| AC-07 | CSV、Excel 和 PDF 成绩导出 | BE-28、BE-03 | PASS |
| SEC-01 | 登录锁定、角色权限及数据范围隔离 | BE-22、BE-14、BE-05 | PASS |
| AUD-01 | 审计链校验与数据库备份 | BE-20 | PASS |

## 5. 前端测试顺序与逐项结果

| 顺序 | 编号 | 角色 | 页面/检查 | 状态 | 截图证据 |
| ---: | --- | --- | --- | --- | --- |
| 1 | FE-00 | 公共 | 登录页加载及演示账号列表 | PASS | [查看截图](screenshots/00-login-page.png) |
| 2 | FE-01 | 教师 | 错误密码显示明确提示（预期异常） | PASS | [查看截图](screenshots/01-invalid-password.png) |
| 3 | FE-02 | 教务管理员 | 教务管理员进入工作台概览页面 | PASS | [查看截图](screenshots/admin-01-overview.png) |
| 4 | FE-03 | 教务管理员 | 教务管理员进入项目管理页面 | PASS | [查看截图](screenshots/admin-02-projects.png) |
| 5 | FE-04 | 教务管理员 | 教务管理员进入团队与成员页面 | PASS | [查看截图](screenshots/admin-03-teams.png) |
| 6 | FE-05 | 教务管理员 | 教务管理员进入成果提交页面 | PASS | [查看截图](screenshots/admin-04-submissions.png) |
| 7 | FE-06 | 教务管理员 | 教务管理员进入成绩管理页面 | PASS | [查看截图](screenshots/admin-05-grades.png) |
| 8 | FE-07 | 教务管理员 | 教务管理员进入操作记录页面 | PASS | [查看截图](screenshots/admin-06-logs.png) |
| 9 | FE-08 | 教师 | 教师进入工作台概览页面 | PASS | [查看截图](screenshots/teacher-01-overview.png) |
| 10 | FE-09 | 教师 | 教师进入项目管理页面 | PASS | [查看截图](screenshots/teacher-02-projects.png) |
| 11 | FE-10 | 教师 | 教师进入团队与成员页面 | PASS | [查看截图](screenshots/teacher-03-teams.png) |
| 12 | FE-11 | 教师 | 教师进入成果提交页面 | PASS | [查看截图](screenshots/teacher-04-submissions.png) |
| 13 | FE-12 | 教师 | 教师进入匿名互评页面 | PASS | [查看截图](screenshots/teacher-05-reviews.png) |
| 14 | FE-13 | 教师 | 教师进入成绩管理页面 | PASS | [查看截图](screenshots/teacher-06-grades.png) |
| 15 | FE-14 | 教师 | 教师进入操作记录页面 | PASS | [查看截图](screenshots/teacher-07-logs.png) |
| 16 | FE-15 | 助教 | 助教进入工作台概览页面 | PASS | [查看截图](screenshots/assistant-01-overview.png) |
| 17 | FE-16 | 助教 | 助教进入项目管理页面 | PASS | [查看截图](screenshots/assistant-02-projects.png) |
| 18 | FE-17 | 助教 | 助教进入团队与成员页面 | PASS | [查看截图](screenshots/assistant-03-teams.png) |
| 19 | FE-18 | 助教 | 助教进入成果提交页面 | PASS | [查看截图](screenshots/assistant-04-submissions.png) |
| 20 | FE-19 | 助教 | 助教进入成绩管理页面 | PASS | [查看截图](screenshots/assistant-05-grades.png) |
| 21 | FE-20 | 助教 | 助教进入操作记录页面 | PASS | [查看截图](screenshots/assistant-06-logs.png) |
| 22 | FE-21 | 学生 | 学生进入工作台概览页面 | PASS | [查看截图](screenshots/student-01-overview.png) |
| 23 | FE-22 | 学生 | 学生进入项目管理页面 | PASS | [查看截图](screenshots/student-02-projects.png) |
| 24 | FE-23 | 学生 | 学生进入团队与成员页面 | PASS | [查看截图](screenshots/student-03-teams.png) |
| 25 | FE-24 | 学生 | 学生进入成果提交页面 | PASS | [查看截图](screenshots/student-04-submissions.png) |
| 26 | FE-25 | 学生 | 学生进入匿名互评页面 | PASS | [查看截图](screenshots/student-05-reviews.png) |
| 27 | FE-26 | 学生 | 学生进入成绩管理页面 | PASS | [查看截图](screenshots/student-06-grades.png) |
| 28 | FE-27 | 学生 | 学生进入操作记录页面 | PASS | [查看截图](screenshots/student-07-logs.png) |

## 6. 问题、失败与预期异常

- 本次未发现实际失败用例、HTTP 500 或非预期浏览器控制台错误。
- 错误密码、未知账号、越权访问、团队人数不足、非法权重、五次失败锁定等属于**预期异常测试**；系统正确拒绝这些操作时，该测试记为 PASS。
- 因此报告不会把“预期收到 401/403/400”误判成产品缺陷。

## 7. 前端截图证据（按实际执行顺序）

### 公共

#### FE-00 · 登录页加载及演示账号列表 · PASS

![登录页加载及演示账号列表](screenshots/00-login-page.png)

### 教师

#### FE-01 · 错误密码显示明确提示（预期异常） · PASS

![错误密码显示明确提示（预期异常）](screenshots/01-invalid-password.png)

### 教务管理员

#### FE-02 · 教务管理员进入工作台概览页面 · PASS

![教务管理员进入工作台概览页面](screenshots/admin-01-overview.png)

#### FE-03 · 教务管理员进入项目管理页面 · PASS

![教务管理员进入项目管理页面](screenshots/admin-02-projects.png)

#### FE-04 · 教务管理员进入团队与成员页面 · PASS

![教务管理员进入团队与成员页面](screenshots/admin-03-teams.png)

#### FE-05 · 教务管理员进入成果提交页面 · PASS

![教务管理员进入成果提交页面](screenshots/admin-04-submissions.png)

#### FE-06 · 教务管理员进入成绩管理页面 · PASS

![教务管理员进入成绩管理页面](screenshots/admin-05-grades.png)

#### FE-07 · 教务管理员进入操作记录页面 · PASS

![教务管理员进入操作记录页面](screenshots/admin-06-logs.png)

### 教师

#### FE-08 · 教师进入工作台概览页面 · PASS

![教师进入工作台概览页面](screenshots/teacher-01-overview.png)

#### FE-09 · 教师进入项目管理页面 · PASS

![教师进入项目管理页面](screenshots/teacher-02-projects.png)

#### FE-10 · 教师进入团队与成员页面 · PASS

![教师进入团队与成员页面](screenshots/teacher-03-teams.png)

#### FE-11 · 教师进入成果提交页面 · PASS

![教师进入成果提交页面](screenshots/teacher-04-submissions.png)

#### FE-12 · 教师进入匿名互评页面 · PASS

![教师进入匿名互评页面](screenshots/teacher-05-reviews.png)

#### FE-13 · 教师进入成绩管理页面 · PASS

![教师进入成绩管理页面](screenshots/teacher-06-grades.png)

#### FE-14 · 教师进入操作记录页面 · PASS

![教师进入操作记录页面](screenshots/teacher-07-logs.png)

### 助教

#### FE-15 · 助教进入工作台概览页面 · PASS

![助教进入工作台概览页面](screenshots/assistant-01-overview.png)

#### FE-16 · 助教进入项目管理页面 · PASS

![助教进入项目管理页面](screenshots/assistant-02-projects.png)

#### FE-17 · 助教进入团队与成员页面 · PASS

![助教进入团队与成员页面](screenshots/assistant-03-teams.png)

#### FE-18 · 助教进入成果提交页面 · PASS

![助教进入成果提交页面](screenshots/assistant-04-submissions.png)

#### FE-19 · 助教进入成绩管理页面 · PASS

![助教进入成绩管理页面](screenshots/assistant-05-grades.png)

#### FE-20 · 助教进入操作记录页面 · PASS

![助教进入操作记录页面](screenshots/assistant-06-logs.png)

### 学生

#### FE-21 · 学生进入工作台概览页面 · PASS

![学生进入工作台概览页面](screenshots/student-01-overview.png)

#### FE-22 · 学生进入项目管理页面 · PASS

![学生进入项目管理页面](screenshots/student-02-projects.png)

#### FE-23 · 学生进入团队与成员页面 · PASS

![学生进入团队与成员页面](screenshots/student-03-teams.png)

#### FE-24 · 学生进入成果提交页面 · PASS

![学生进入成果提交页面](screenshots/student-04-submissions.png)

#### FE-25 · 学生进入匿名互评页面 · PASS

![学生进入匿名互评页面](screenshots/student-05-reviews.png)

#### FE-26 · 学生进入成绩管理页面 · PASS

![学生进入成绩管理页面](screenshots/student-06-grades.png)

#### FE-27 · 学生进入操作记录页面 · PASS

![学生进入操作记录页面](screenshots/student-07-logs.png)

## 8. GitHub 复跑说明

教师克隆仓库后，在项目根目录执行：

```powershell
conda create -n course_platform_test python=3.11 -y
conda activate course_platform_test
python -m pip install -r .\backend\requirements-dev.txt
python -m pip install playwright
python -m playwright install chromium
python .\tests\test_script.py --mode all
```

脚本默认使用端口 5088 和临时数据库，结束后自动停止测试服务，不修改正式数据。测试结果固定写入 `tests/screenshots`，本报告会更新为最近一次完整结果。

## 9. 方法合理性与边界

- 后端采用接口级自动化，适合验证业务规则、权限、数据库状态和异常分支。
- 前端采用真实 Chromium 验证四角色全部可见页面、页面渲染及运行时错误，并保留截图证据。
- 当前截图证明页面和角色视图可正常呈现；复杂操作的正确性主要由后端接口测试证明，而不是仅凭截图判断。
- 若评分标准明确要求“每个按钮都由浏览器点击完成”，应在此基础上继续增加端到端交互用例；本报告不会把接口测试冒充为全按钮 UI 测试。
