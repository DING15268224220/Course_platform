# 高校课程项目协作与评审平台 v2.0

本地运行的课程项目管理系统，提供浏览器版与 Electron 桌面版。系统覆盖项目发布、团队管理、多轮迭代提交、同伴互评、助教过程评分、教师终评、成绩发布与导出、通知和审计日志。

## 目录结构

```
project1/
├── frontend/                     前端（纯静态，由后端直接托管）
│   ├── index.html                单页应用外壳 + 登录页 + 弹窗容器
│   ├── app.js                    全部页面渲染与交互逻辑
│   └── style.css                 全部样式（含响应式与打印样式）
├── backend/                      后端（Flask + SQLite）
│   ├── app.py                    应用入口、建表/种子数据、全部 API 路由、成绩计算
│   ├── requirements.txt          Python 依赖（Flask、waitress）
│   ├── tests/test_app.py         接口与业务规则测试（pytest）
│   ├── data/                     运行时数据目录（platform.db、.secret-key）
│   └── uploads/                  浏览器版上传文件目录
├── desktop/                      Electron 桌面版与打包链
│   ├── main.cjs                  主进程：拉起本地后端 + 打开窗口
│   ├── package.json              依赖与 electron-builder 打包配置
│   ├── start-desktop.bat         启动桌面开发版
│   ├── build-desktop.bat         构建 Windows 便携版
│   ├── scripts/                  后端 PyInstaller 打包脚本
│   └── requirements-desktop.txt  打包后端所需的额外依赖
├── start.bat                     浏览器版一键启动
├── README.md
└── 需求差距说明.txt              与《软件工程需求分析报告》的功能差距清单
```

代码只分 `frontend/`、`backend/`、`desktop/` 三个目录；构建产物、虚拟环境、缓存、编辑器配置均不入库（见 `.gitignore`）。

## 快速启动（浏览器版）

双击 `start.bat`，或在 PowerShell 中运行：

```powershell
cd D:\project1
D:\Anaconda\python.exe -m pip install -r backend\requirements.txt
D:\Anaconda\python.exe backend\app.py
```

浏览器打开 <http://127.0.0.1:5000>。`frontend/` 由后端通过 `/static/` 路由托管，无需单独的 Node 服务。

## 登录

首次启动会自动创建演示账号，统一演示密码：`123456`（可用环境变量 `PLATFORM_DEMO_PASSWORD` 覆盖）。

- 教师：张老师
- 助教：王助教
- 学生：丁沈昊、余容、蒋奇纯、李根等

系统使用会话登录和请求安全令牌，不再通过页面参数切换身份。

## 测试

```powershell
cd D:\project1\backend
D:\Anaconda\python.exe -m pytest -q

node --check ..\frontend\app.js
node --check ..\desktop\main.cjs
```

测试使用独立临时数据库，不会修改 `backend\data\platform.db`。

## 桌面版

开发版：双击 `desktop\start-desktop.bat`，或：

```powershell
cd D:\project1\desktop
npm install
npm run desktop
```

Electron 默认优先使用 `5055` 端口，端口占用时自动选择可用端口；关闭窗口时本地后端一并停止。

Windows 便携版：双击 `desktop\build-desktop.bat`，或：

```powershell
cd D:\project1\desktop
npm install
npm run dist:win
```

产物位于 `desktop\release\CourseProjectReviewPlatform-2.0.0-portable.exe`。该命令会先用 PyInstaller 把 `backend\app.py` 与 `frontend\` 打进单文件后端，再交给 electron-builder 打包。桌面发行版的数据保存在 Windows 用户的应用数据目录。

## 数据与备份

- 浏览器版数据库：`backend\data\platform.db`
- 浏览器版上传文件：`backend\uploads\`
- 桌面开发版数据：`backend\data\`
- 桌面发行版数据：Windows 用户应用数据目录中的 `platform-data`

升级启动时会自动补齐数据库字段和版本表，不会清空已有数据。重要演示前建议复制 `backend\data\platform.db` 和 `backend\uploads\` 备份。

## 主要业务规则（已实现部分）

- 项目数据按课程、项目和登录身份隔离。
- 三项评分权重必须分别在 0—100% 内，并合计 100%。
- 团队达到 3—5 人后才能提交成果、开启互评或发布成绩。
- 每次重新上传都会保存独立版本；只有组长可上传/撤回。
- 文件支持 PDF、ZIP、MP4，单文件不超过 200MB，并校验文件头与扩展名。
- 学生成绩在教师发布前不可见。
- 发布、组队、提交、互评、评分和导出等关键操作均写入项目审计日志。

未实现或与需求不符的功能见 `需求差距说明.txt`。
