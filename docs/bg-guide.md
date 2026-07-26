# 背景图（bg.png）使用说明

## 这是什么

`assets/bg.png` 是 Web UI 的全屏背景图，覆盖整个页面底层。UI 组件（卡片、按钮等）浮在它上面，带半透明毛玻璃效果。

## 当前背景

赛博朋克城市夜景风格：
- 深蓝/紫色调为主
- 霓虹灯管、高楼轮廓、雨夜反射
- 与 VTuber 二次元主题搭配

## 尺寸建议

| 属性 | 建议值 |
|------|--------|
| 分辨率 | 1920×1080 或更高 |
| 格式 | PNG（支持透明/无损） |
| 文件大小 | < 2MB（太大影响加载） |
| 风格 | 暗色调为主，避免高亮区域干扰文字阅读 |

## 替换方法

直接覆盖文件即可，无需改代码：

```bash
# 把你的新背景图重命名为 bg.png，放到 assets/ 目录
mv your_background.png assets/bg.png
```

刷新浏览器 `http://127.0.0.1:8081` 立即生效。

## 设计建议

- **暗底优先**：UI 文字是浅色（#e2e6f0），背景太亮会看不清
- **避免复杂图案**：中间区域会被卡片盖住，边缘/四角可以丰富
- **色调统一**：建议和 sticker、banner 的蓝色/紫色系保持一致
- **压缩**：用 [tinypng.com](https://tinypng.com) 压缩后再放

## 代码层面

背景图在 `index.html` 的 CSS 中定义：

```css
body {
  background: var(--bg-deep) url('/assets/bg.png') center top / cover fixed no-repeat;
}
```

- `center top` — 图片顶部居中
- `cover` — 等比缩放，填满屏幕
- `fixed` — 滚动时背景不动（视差效果）

如果要改位置或效果，编辑 `src/txt_to_audiobook/templates/index.html` 的 `body` 样式。

## 示例：纯色背景（不用图片）

把 `body` 的 `background` 改成纯渐变：

```css
body {
  background: linear-gradient(135deg, #0a0e1a 0%, #1a1030 50%, #0a1a20 100%);
}
```

然后可以删掉 `assets/bg.png` 节省空间。

## 文件位置

```
txt-to-audiobook/
└── assets/
    └── bg.png          ← 背景图
    ├── sticker1.png    ← 表情贴纸 1
    ├── sticker2.png    ← 表情贴纸 2
    ├── sticker3.png    ← 表情贴纸 3
    ├── sticker4.png    ← 表情贴纸 4
    └── Screenshot.png  ← README 截图
```
