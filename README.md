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

## GitHub Actions 多账号运行

三章节自动化工作流支持选择账号、课程、章节顺序和视频倍速。账号凭据不放在工作流输入中，使用一个仓库 Secret `SUPERSTAR_ACCOUNTS_JSON` 保存账号注册表；账号别名和课程配置使用 [account_registry.example.json](account_registry.example.json) 作为格式模板。

将填好但未提交的注册表作为 `SUPERSTAR_ACCOUNTS_JSON` Secret 保存后，在 `SuperStar three-chapter automation` 的 `Run workflow` 页面填写：

- `account_id`：注册表中的账号别名，例如 `A`
- `course_id`：该账号注册过的课程 ID
- `clazz_id`：可选；同一课程对应多个班级时必须填写
- `chapter_selection`：可选的章节顺序号，例如 `4,5,6`
- `chapter_plan`：可选的连续批次计划，例如 `4,5,6;7,8,9;10,11,12`；当前批次成功后会自动拉起下一次 Action，直到计划完成
- `auto_continue`：可选；打开后自动连续处理未完成章节
- `start_chapter`：自动续跑的起始章节顺序号，默认从第 `1` 章检查
- `end_chapter`：自动续跑的结束章节顺序号，填写 `0` 表示一直处理到最后
- `video_speed`：`1.0` 到 `2.0`

注册表和账号密码不要提交到仓库。课程 ID 只允许使用该账号注册表中登记的课程；如果未指定班级且课程对应多个班级，工作流会停止并提示可用班级。

`chapter_plan` 和 `chapter_selection` 只能填写一个。批次链中的每一批最多三个章节，某一批失败后不会继续派发后续批次；工作流需要 `actions: write` 权限来启动下一次运行。

如果打开 `auto_continue`，请不要填写 `chapter_plan` 或 `chapter_selection`。例如设置 `start_chapter=4`、`end_chapter=12`，工作流会从第 4 个章节顺序开始，跳过已完成章节，每次处理最多三个未完成章节，直到第 12 个章节；设置 `end_chapter=0` 则一直处理到课程末尾。

## 赞助
>如果觉着代码对你有帮助，可以赞赏一下开发者

![截图](/images/reward.jpg)
