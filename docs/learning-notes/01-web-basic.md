\# Web 基础学习笔记



HTML、CSS、JavaScript 是前端开发的三大基础。HTML 负责网页结构，决定页面上有什么；CSS 负责样式和布局，决定页面长什么样；JavaScript 负责交互行为，决定用户操作后页面会发生什么。



在 AI Enterprise OS 的聊天页面原型中，HTML 定义了标题、聊天记录区域、输入框、添加文件按钮和发送按钮。CSS 控制聊天卡片、消息气泡、按钮样式、输入框布局、间距、颜色等。JavaScript 负责读取用户输入、添加消息、模拟 AI 回复、显示“正在思考”、禁用按钮、防止重复发送等交互逻辑。



DOM 是 JavaScript 操作网页的方式。JavaScript 可以通过 `document.getElementById()` 找到 HTML 元素，也可以通过 `document.createElement()` 创建新元素，再通过 `appendChild()` 把新元素添加到页面中。例如，发送消息时，JavaScript 会创建一条新的消息元素，并把它添加到聊天记录区域。



`innerHTML` 和 `textContent` 都可以修改元素内容，但它们有重要区别。`innerHTML` 会把内容当成 HTML 解析，写起来方便但存在安全风险；`textContent` 会把内容当成普通文本显示，更适合处理用户输入，可以降低 XSS 攻击风险。因此，聊天消息中的用户输入应该优先使用 `textContent` 显示。



加载状态是 AI 产品中很重要的交互体验。当用户发送消息后，页面需要告诉用户系统正在工作，例如显示“AI 正在思考……”或把发送按钮改成“生成中……”。这可以减少用户等待时的不确定感。



防止重复发送不能只依赖按钮禁用，因为用户还可能通过 Enter 键触发发送逻辑。更好的做法是同时使用 UI 控制和逻辑判断：按钮禁用负责界面表现，`isGenerating` 状态变量负责判断当前是否允许继续发送。



目前纯 HTML、CSS、JavaScript 版本已经实现了基础聊天页面、消息气泡、点击发送、Enter 发送、模拟 AI 回复、加载状态、防重复发送，以及使用 `textContent` 避免用户输入带来的安全风险。



在 AI Enterprise OS 架构中，HTML、CSS、JavaScript 属于 Presentation Layer，也就是表现层。后续学习 React 时，会把这些页面结构、样式和交互逻辑进一步组件化，让前端代码更容易维护和扩展。

