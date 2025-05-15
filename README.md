# 多语言翻译工具

这是一个基于Flask的多语言翻译Web应用程序，支持多种语言之间的翻译，包括自动语言检测功能。
可在下面这个链接体验

[智能翻译助手](https://translate.lovejisoo.cn/)
## 功能特点

- 支持多语言翻译（中文、英语、日语、韩语）
- 自动检测源语言
- 长文本智能分段翻译
- 翻译历史记录保存
- 单词/词汇表管理
- 响应式界面设计

## 技术栈

- 后端：Flask (Python)
- 翻译API：MyMemory Translation API
- 前端：HTML, CSS, JavaScript

## 安装与运行

1. 克隆仓库：
```bash
git clone https://github.com/你的用户名/多语言翻译工具.git
cd 多语言翻译工具
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 运行应用：
```bash
python app.py
```

4. 访问应用：
   在浏览器中打开 `http://localhost:5000`

## 依赖项

- Flask==3.0.2
- deep-translator==1.11.4
- python-dotenv==1.0.1
- werkzeug==3.0.1
- langdetect==1.0.9
- requests==2.31.0

## 贡献

欢迎提交Issue和Pull Request。

## 许可证

MIT
