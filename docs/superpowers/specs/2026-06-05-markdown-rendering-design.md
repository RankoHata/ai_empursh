# Markdown 渲染支持 — 设计文档

**日期**: 2026-06-05
**状态**: 待实现

## 问题

`MessageBubble.jsx` 将 AI 助手的回复以 `{content}` 直接渲染为纯文本，CSS 设置了 `white-space: pre-wrap`。后端返回的是 Markdown 格式（包含标题、粗体、代码块、列表等），用户看到的是原始 Markdown 源码而非格式化内容。

## 方案

使用 `react-markdown` + `remark-gfm` 为 AI 助手消息提供 GitHub Flavored Markdown 渲染。

### 选型理由

- `react-markdown`：React 原生组件，不依赖 `dangerouslySetInnerHTML`，无 XSS 风险
- `remark-gfm`：支持 GFM 扩展（表格、删除线、任务列表、自动链接）
- 生态标准方案，社区活跃

## 实现

### 1. 安装依赖

```bash
cd electron-app
npm install react-markdown remark-gfm
```

### 2. 修改 `MessageBubble.jsx`

- 导入 `ReactMarkdown` 和 `remarkGfm`
- `role === 'assistant'` 时用 `<ReactMarkdown>` 渲染 content
- `role === 'user'` 时保持纯文本渲染
- 组件只负责渲染，Markdown 渲染结果继承 `.bubble-content` 的字体和行高

### 3. 新增 CSS（`App.css`）

在现有 `.bubble-content` 样式块之后追加 Markdown 元素样式：

- **标题 h1-h6**: 分层字号，h1/h2 带底部分隔线
- **段落 p**: 适当上下间距
- **行内代码 `code`**: 暗红底色 + 红色文字
- **代码块 `pre code`**: 深色背景（`#0d1117`）、等宽字体、圆角边框
- **引用 blockquote**: 左侧 accent 色边框 + 半透明背景
- **列表 ul/ol**: `padding-left: 24px`
- **链接 a**: 蓝色
- **表格**: 暗色边框
- **分隔线 hr**: 暗色

所有颜色使用项目已有的 CSS 变量（`--accent`, `--border`, `--text-primary` 等），保持暗色主题一致。

### 4. 流式渲染

ReactMarkdown 在每次 content 更新时重新渲染。聊天消息典型长度（几百到几千字）下性能足够，无需额外优化。

### 5. 不变部分

- 用户消息：纯文本 + `white-space: pre-wrap`，不变
- 右键菜单「保存为笔记」：保存原始 Markdown 文本，不变
- 流式光标动画 `.bubble-content.streaming::after`：不变
- 笔记面板：笔记内容仍以纯文本显示（笔记偏个人记录，不涉及 AI 生成的 Markdown）

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `electron-app/package.json` | +`react-markdown`, `remark-gfm` |
| `electron-app/src/renderer/components/MessageBubble.jsx` | 导入 + 条件渲染 |
| `electron-app/src/renderer/App.css` | 追加 Markdown 样式 |

## 风险

- **流式性能**: 每次 chunk 触发全量 Markdown 重解析。消息短时无影响；极端长消息（>10000 字）可能存在卡顿，但目前场景不会遇到。
- **XSS**: `react-markdown` 默认不渲染 HTML 标签，安全性由库保证。
