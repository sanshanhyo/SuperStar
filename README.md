<p align="center">
  <a href="https://www.springing.top" target="blank">
    <img src="images/logo.png" alt="Logo" width="156" height="156">
  </a>
  <h2 align="center" style="font-weight: 600">Spring-Superstar</h2>
  <p align="center">
    学习通在线刷课脚本 超星 学习通 云端刷课
  </p>
</p>

本项目宗旨是帮助大学生们解放双手，根据教程操作后就可以完成刷课，简单易懂，仅需手机就可以使用

>如果本项目对希望各位同学们给本仓库点一个免费的Star或者给小春子点一个Follow 谢谢大家！

![截图](/images/star.png)

## 用前必读必读！
默认fork仓库之后是公开的状态，也就是说你的账号和密码是处于一个明文状态！！很危险！！建议把仓库权限改为私有

之前本仓库就因为明文账号密码泄露导致一些同学账号被盗拿来恶作剧(不得不说世界上还是坏人多)，故提前在此说明，希望大家周知

## 快速开始

<a href="https://blog.springing.top/p/20241119/" target="blank">点击我查看操作说明</a>

<a href="https://github.com/Samueli924/chaoxing" target="blank">灵感来源</a>

## GitHub Actions 最小测试

本仓库的 Actions 仅提供一个手动触发的只读 smoke test，固定检查
`courseId=266120241`、`clazzId=152038953`。它验证登录、课程识别、少量章节读取、
任务类型解析和日志输出，不会执行视频、文档、答题、签到或提交操作，也不会跑完整门课。

先在 fork 后的仓库中设置以下 Actions Secrets：

- `CHAOXING_USERNAME`：学习通手机号账号
- `CHAOXING_PASSWORD`：学习通密码

运行时脚本从 `config_template.ini` 生成被 `.gitignore` 忽略的 `config.ini`，凭据不会写入提交。
在 GitHub 的 `Actions` 页面选择 `SuperStar course smoke test`，点击 `Run workflow` 手动运行。

成功日志会依次出现 `[smoke] login check passed`、`[smoke] course identification passed`、
`[smoke] chapter identification passed`、`[smoke] task-card identification passed` 和
`[smoke] SUCCESS: read-only checks completed`。课程或班级不匹配、登录失败、章节响应无法解析，
都会使 workflow 失败。

如果 `type_counts={}`，表示本次抽样章节都是已完成或未开放状态，卡片接口仍然可读，但没有可展示的未完成任务类型；
这不等同于整门课已执行。

## 单视频测试

另有一个独立的 `SuperStar video test` 手动 workflow，固定测试章节
`1.1 国防的内涵`（`pointId=1221167829`）中的一个视频任务。它会真实上报视频进度，
但不会调用答题、作业、签到或提交逻辑。成功日志为
`[video-test] SUCCESS: one video task completed`。

## 答题 API 保存测试

`SuperStar answer dry-run` 是独立的手动 workflow，使用 `TIKU_API_KEY`、
`https://api.shenwenai.com/v1` 和 `gpt-5.6-luna`，固定检查同一章节中的一个测验任务。
它会先检查 API 连通性，再以 `submit=false` 运行一次答题流程，只保存草稿，不提交测验。
成功日志为 `[answer-test] SUCCESS: one quiz answered in submit=false mode`。

另有 `SuperStar answer submit test`，只有手动触发，并通过显式 `--allow-submit` 才会提交。
当前固定测试仍未完成的 `1.2 国防的职能与使命【上】` 中的一个测验，用于验证真实提交链路，
不代表已经开启整门课自动化。

## 赞助
>如果觉着代码对你有帮助，可以赞赏一下开发者

![截图](/images/reward.jpg)
