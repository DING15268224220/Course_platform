Course_platform 最终版功能测试说明
==================================

系统设计报告：高校课程项目协作设计报告.md
固定版测试报告：tests\TEST_REPORT.pdf

一、测试内容

1. 执行 backend\tests\test_app.py 中原有后端测试。
2. 执行 tests\test_full_api.py，补测项目修改、迭代新增、团队创建/退出、
   教师例外调员、成员任务状态、成果上传/下载/版本/撤回、催交、互评开关、
   预警处理、过程分、终评分、CSV 导出、通知全部已读和退出登录等功能。
3. 使用 Playwright 登录教务管理员、教师、助教、学生四类角色。
4. 遍历每个角色全部可见页面，检查页面可访问且内容非空，并逐页截图。
5. 监听浏览器控制台错误和 HTTP 500 错误。

测试默认启动独立临时服务和临时数据库，不修改项目正式数据。

二、安装环境

在项目根目录执行：

   conda activate course_platform_test
   python -m pip install -r .\backend\requirements-dev.txt
   python -m pip install playwright
   python -m playwright install chromium

三、分别执行前端、后端测试

只执行后端和业务接口测试（无需 Playwright）：

   python .\tests\test_script.py --mode backend

只执行前端浏览器和截图测试：

   python .\tests\test_script.py --mode frontend

执行完整测试：

   python .\tests\test_script.py --mode all

显示浏览器执行：

   python .\tests\test_script.py --mode frontend --headed

默认自动启动端口 5088 的隔离测试服务，无需先启动项目。
如果 5088 被占用，可改用：

   python .\tests\test_script.py --mode all --port 5090

如需检查已经启动的指定服务：

   python .\tests\test_script.py --mode frontend --base-url http://127.0.0.1:5080

注意：指定外部服务时，浏览器登录检查会使用该服务的数据；完整后端接口测试
仍使用临时数据库。

四、固定输出路径

所有输出统一保存到：

   项目根目录\tests\screenshots

其中包括：

   00-login-page.png             登录页
   01-invalid-password.png       错误密码提示
   admin-*.png                   教务管理员全部可见页面
   teacher-*.png                 教师全部可见页面
   assistant-*.png               助教全部可见页面
   student-*.png                 学生全部可见页面
   backend-tests.log             后端及业务接口测试日志
   test-results.json             机器可读结果和截图清单
   LAST_RUN.md                   最近一次测试摘要

完整图文测试报告会自动更新到：

   tests\TEST_REPORT.md

固定版测试报告：

   tests\TEST_REPORT.pdf

报告按实际顺序列出前后端每项 PASS/FAIL、运行环境、异常说明，并直接嵌入截图。

正常完整执行会生成 28 张 PNG：登录相关 2 张，加四类角色共 26 个页面视图。

五、判断结果

控制台最终同时显示：

   后端及业务接口：PASS
   浏览器全部页面：PASS
   最终结果：PASS

才表示完整验收通过。出现 FAIL 时先查看 screenshots\LAST_RUN.md 和
screenshots\backend-tests.log。
