# HTML to Vue conversion for electron-app
_Exported on 5/26/2026 at 18:25:34 GMT+8 from Cursor (3.5.33)_

---

**User**

我现在的项目需要以@electron-app 为骨架，@设计稿和代码 中的HTML页面转化为骨架中的VUE页面

---

**Cursor**

我已经把骨架和 5 个设计稿都过了一遍，整体情况如下：

**骨架（[electron-app](electron-app)）**：Electron + Vue3 + TS + Vite + Pinia + Vue Router(hash) + Element Plus(自动按需) + Axios + Less，路由表 [routes.ts](electron-app/src/renderer/src/router/routes.ts) 现在只有 `Home` / `About`。

**5 个设计稿**全部使用 Tailwind CDN + Material Symbols + 自定义设计令牌（[DESIGN.md](设计稿和代码/zenith_ai/DESIGN.md)），可拆分为：
- `zenith_ai_1` → 对话/语音主页（侧栏 + 聊天气泡 + 语音波形）
- `zenith_ai_2` → 任务看板（三列 Kanban + 底部 Footer）
- `zenith_ai_3` → 设置页（语音/隐私/集成，含开关、滑杆）
- `zenith_ai_4` → 知识库与技能中心（技能卡片网格 + 文档表格）
- `zenith_ai_5` → 登录页（独立全屏布局，无侧栏）

其中 1~4 都共享 **SideNav + TopAppBar + 新建对话按钮**，5 是独立布局。

在出计划前，有 2 个会影响整体实现路线的关键选择必须先和你对齐：

> **设计稿是用 Tailwind CDN + 自定义设计令牌写的，骨架里只有 Less。CSS 方案怎么选？**
> - A. 在 electron-app 中安装并配置 Tailwind v3，把 DESIGN.md 里的颜色/字体/圆角/spacing 都搬进 tailwind.config（推荐，最贴近设计稿、迁移成本最低） ✔
> - B. 不装 Tailwind，把每个页面手工改写成 Less + scoped 样式（工作量大但产物干净，无 CDN 依赖）
> - C. 改用 UnoCSS（更轻量，按需生成，配置语法和 Tailwind 接近）

> **设计稿里没用 Element Plus,所有控件(按钮/输入/开关/选择器/弹层)都是按设计令牌手写的。Element Plus 怎么处理?**
> - A. 保留 Element Plus(以后复杂控件如 Dialog/Message/Table 用得到),但本次迁移的 5 个页面全部按设计稿手写,不引入 EP 组件 ✔
> - B. 主要用 Element Plus,通过覆盖主题变量让其贴合设计令牌(开发快,但视觉细节会和设计稿有差异)
> - C. 移除 Element Plus 依赖,完全按设计稿手写组件库

收到。基于你的选择（Tailwind v3 + 保留 EP 但本次手搓），下面给出完整迁移计划。

现在更新 main.ts 引入样式：

同时把别名同步进 tsconfig，否则 vue-tsc 检查会报错。先看一下现有 tsconfig：

我先建共享组件，然后用这些组件搭 Layout：

现在建 Layout 组件：

删除骨架示例文件：

检查 lint 错误：

运行类型检查：

修两个类型错误：

web 类型检查通过。再跑完整 typecheck 和 lint：

骨架没自带 ESLint 配置，跳过。改为跑构建验证：

构建成功。验证一下生成的 css 包含了 Tailwind 关键类：

CSS 37KB，4 个关键标识符各匹配多次，Tailwind 编译正常工作。最后清理 todo：

全部 13 个 todo 已完成。下面是这次迁移的整体结果。

## 完成总览

### 工具链改造
- 装好 `tailwindcss@3.4` + `postcss` + `autoprefixer`，新建 [tailwind.config.js](electron-app/tailwind.config.js) 把 [DESIGN.md](设计稿和代码/zenith_ai/DESIGN.md) 的全套设计令牌（颜色/字体/字号/圆角/spacing/动画）注入 `theme.extend`，并配置 `wave / shimmer / fadeInUp` 三个关键帧。
- 新建 [postcss.config.js](electron-app/postcss.config.js)。
- 重写 [styles.less](electron-app/src/renderer/src/assets/css/styles.less)：删除骨架原本的深蓝示例样式，引入 Tailwind 三件套指令，加入 wave-line / kanban-col / material-symbols-outlined 等设计稿专用样式。
- 在 [main.ts](electron-app/src/renderer/src/main.ts) 引入全局样式。
- 改写 [index.html](electron-app/src/renderer/index.html)：放宽 CSP（`style-src` / `font-src` 允许 Google Fonts），加入 Hanken Grotesk / Noto Sans SC / Material Symbols 的 `<link>`。
- 扩展 [electron.vite.config.ts](electron-app/electron.vite.config.ts) 与 [tsconfig.web.json](electron-app/tsconfig.web.json) 别名：新增 `@layout` / `@assets`，并把现有别名同步到 tsconfig 让 vue-tsc 识别。

### 共享组件（[components/](electron-app/src/renderer/src/components)）
- [MaterialIcon.vue](electron-app/src/renderer/src/components/MaterialIcon.vue)：支持 `fill` / `weight` / `size`，对应字体可变轴。
- [ToggleSwitch.vue](electron-app/src/renderer/src/components/ToggleSwitch.vue)：v-model 受控开关，复用 zenith_ai_3/_4 同款样式。
- [VoiceWave.vue](electron-app/src/renderer/src/components/VoiceWave.vue)：10 根 wave-line，`active` 控制是否高亮。
- [TaskCard.vue](electron-app/src/renderer/src/components/TaskCard.vue)：三态卡片（`todo` / `doing` / `done`），doing 态带进度条 + shimmer 动画。

### 布局（[layout/](electron-app/src/renderer/src/layout)）
- [MainLayout.vue](electron-app/src/renderer/src/layout/MainLayout.vue)：侧栏 + 顶栏 + `<router-view>`；当路由是 `Tasks` 时挂载 Footer（对应 zenith_ai_2 设计）。
- [SideNav.vue](electron-app/src/renderer/src/layout/SideNav.vue)：4 个 `<router-link>`，active 状态由 `route.name` 计算，激活态图标自动 fill=1。
- [TopAppBar.vue](electron-app/src/renderer/src/layout/TopAppBar.vue)：右上角账号按钮（点击退出登录）。
- [AppFooter.vue](electron-app/src/renderer/src/layout/AppFooter.vue)：Agent 状态条 + 协议链接。

### 视图（[views/](electron-app/src/renderer/src/views)）
| 路由 | 源设计稿 | 文件 |
|---|---|---|
| `/login` | zenith_ai_5 | [LoginView.vue](electron-app/src/renderer/src/views/LoginView.vue)（接入 `loginByJson`、写入 token、跳 `/chat`；失败也用 mock token 放行便于开发）|
| `/chat` | zenith_ai_1 | [ChatView.vue](electron-app/src/renderer/src/views/ChatView.vue)（消息列表 + 语音波形 + 麦克风按钮，`listening` 可切换）|
| `/tasks` | zenith_ai_2 | [TasksView.vue](electron-app/src/renderer/src/views/TasksView.vue)（三列响应式数组渲染）|
| `/settings` | zenith_ai_3 | [SettingsView.vue](electron-app/src/renderer/src/views/SettingsView.vue)（音色 Tab / 唤醒词 / 语速滑杆 + 实时百分比 / 开关 / API key 显隐 / 邮箱连接切换）|
| `/knowledge` | zenith_ai_4 | [KnowledgeView.vue](electron-app/src/renderer/src/views/KnowledgeView.vue)（技能卡片网格 + 文档表格 hover 操作 + 状态点颜色映射）|

### 路由
- [routes.ts](electron-app/src/renderer/src/router/routes.ts)：嵌套路由，`/` 重定向到 `/chat`，并加了 `pathMatch` 兜底。
- [guards.ts](electron-app/src/renderer/src/router/guards.ts)：基于 `useUserStore.token` 的登录守卫，未登录跳 `/login`，已登录访问 `/login` 自动跳 `/chat`。

### 清理
- 删除 `Home.vue` / `About.vue` / `Versions.vue` 三个骨架示例。

### 验证
- `npm run typecheck` 通过（node + web 双向检查 0 error）。
- `npm run build` 通过：渲染包 277KB JS + 37KB CSS（已包含全部 Tailwind 编译产物），Tailwind 关键类名在产物中被正确生成。

接下来你可以直接运行 `npm run dev` 启动 Electron 看效果。Element Plus 仍保留为自动按需，未来需要复杂组件（Dialog / Message / Table）随时可用而不冲突。

