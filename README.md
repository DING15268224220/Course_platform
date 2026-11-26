# 高校课程项目协作与评审平台 最终版

高校课程项目协作与评审平台面向课程项目教学场景，覆盖项目发布、在线组队、任务分工、成果提交、过程检查、匿名互评、成绩核定、申诉复核和操作审计等业务流程。系统提供网页版和 Electron 桌面版，并按照教务管理员、教师、助教和学生四类角色进行权限控制。

## 核心功能

- 课程与项目：支持课程创建、项目草稿、项目发布、多轮迭代、截止时间和评分权重设置。
- 团队协作：支持学生创建团队、申请入队、组长审批、成员调整和个人任务分配。
- 成果管理：支持 PDF、ZIP、MP4 文件提交、版本记录、成果撤回、查收和退回修改。
- 过程检查：支持助教查看提交进度、录入过程分并向未提交团队发送提醒。
- 匿名互评：支持三维评分、草稿保存、匿名成果下载、极值剔除和异常评分预警。
- 成绩管理：支持过程分、互评分和终评分加权计算，以及个人系数和扣分调整。
- 成绩复核：支持成绩发布与撤回、学生申诉、教务复核及 CSV、Excel、PDF 导出。
- 安全与审计：支持角色权限隔离、登录失败锁定、截止时间提醒和关键操作日志。

## 角色权限

| 角色 | 主要权限 |
| --- | --- |
| 教务管理员 | 全局查看、成绩复核、发布撤回、数据导出和审计查询 |
| 教师 | 课程项目管理、互评控制、终评分、成绩发布与导出 |
| 助教 | 成果查收与退回、过程评分、催交和互评预警处理 |
| 学生 | 团队协作、任务更新、成果提交、匿名互评和成绩申诉 |

## 技术架构

| 模块 | 技术 |
| --- | --- |
| 前端 | HTML5、CSS3、原生 JavaScript |
| 后端 | Python、Flask、Waitress |
| 数据存储 | SQLite |
| 桌面端 | Electron、Node.js、electron-builder |
| 数据导出 | openpyxl、ReportLab |
| 自动化测试 | pytest、Playwright、Chromium |

## 快速开始

### 环境要求

- Windows 10 或 Windows 11，64 位。
- Python 3.10 或更高版本。
- 运行桌面版时需要 Node.js 22.12.0 或更高版本。

### 启动系统

双击项目根目录中的 `启动系统.bat`，根据菜单选择操作：

1. 启动网页版并访问 `http://127.0.0.1:5080`。
2. 启动 Electron 桌面版。
3. 安装或更新运行依赖。
4. 检查本机运行环境。
5. 运行自动化测试。
6. 构建 Windows 便携版。

也可以先安装网页版依赖：

```powershell
python -m pip install -r .\backend\requirements.txt
```

运行期间需要保持启动窗口开启。系统运行后产生的数据库和上传文件分别保存在 `backend/data` 与 `backend/uploads`。

## 演示账号

演示账号统一密码为 `123456`。

| 角色 | 账号 |
| --- | --- |
| 教务管理员 | `a1` |
| 教师 | `t1` |
| 助教 | `ta1` |
| 学生 | `s1` |

登录页面还提供其他学生演示账号，可用于团队协作和匿名互评流程。

## 自动化测试

测试套件使用临时数据库和独立服务，不修改正式运行数据。完整测试包含 33 项后端与业务接口用例，以及 28 项前端浏览器页面用例。

```powershell
conda create -n course_platform_test python=3.11 -y
conda activate course_platform_test
python -m pip install -r .\backend\requirements-dev.txt
python -m pip install playwright
python -m playwright install chromium
python .\tests\test_script.py --mode all
```

测试结果、运行日志和页面截图保存在 `tests/screenshots`，详细结果见 [自动化测试报告](tests/TEST_REPORT.pdf)。

## 项目文档

- [系统设计报告](高校课程项目协作设计报告.md)：类设计、体系结构、数据流、权限矩阵和接口设计。
- [系统运行说明](3、系统说明.txt)：功能模块、运行环境、启动方法和演示账号。
- [自动化测试报告](tests/TEST_REPORT.pdf)：测试环境、用例结果和页面截图。

## 项目结构

```text
Course_platform/
├─ backend/          Flask 后端、数据库初始化和接口测试
├─ frontend/         登录页、工作台、业务页面和样式资源
├─ desktop/          Electron 桌面端和 Windows 打包脚本
├─ tests/            完整测试脚本、测试报告、日志和截图
├─ docs/             界面效果图和开发文档
├─ tools/            启动菜单与统一运行逻辑
├─ 高校课程项目协作设计报告.md  类设计、体系结构和接口设计
├─ 启动系统.bat      Windows 启动入口
├─ 1、环境清单.txt   环境与依赖说明
└─ 3、系统说明.txt   系统功能与运行说明
```

`desktop/node_modules`、Python 缓存、运行数据库和上传文件均为本地生成内容，由 `.gitignore` 排除。
