# code_annotations

轻量级 Python 函数、类与方法调用关系注释工具。可通过命令行或本地网页分析指定项目，并在源码中生成、更新或移除结构化调用注释。

> 当前为早期开发版本。静态分析不能完整推断反射、动态分发、GUI 回调、复杂类型绑定等调用。使用前请预览差异并在 Git 管理下操作。

## 目录

```text
code_annotations/
├── __init__.py
├── __main__.py
├── analyzer.py
├── formatter.py
├── editor.py
├── web.py
└── start_web.bat
```

## 使用

使用 Python 3.10+，项目本身不要求安装第三方依赖。从 **code_annotations 的父目录**执行：

```powershell
python -m code_annotations inspect path/to/project --root path/to/project
python -m code_annotations write path/to/project --root path/to/project
python -m code_annotations check path/to/project --root path/to/project
python -m code_annotations remove path/to/project --root path/to/project
```

若仅修改单个文件，仍应指定完整项目根目录，用于识别跨模块调用：

```powershell
python -m code_annotations write path/to/project/utils.py --root path/to/project
```

## Web 界面

从父目录运行：

```powershell
python -m code_annotations.web
```

也可在 Windows 上双击 `start_web.bat`。默认地址为 `http://127.0.0.1:8799/`，若默认端口不可用会自动选择其他端口。服务仅绑定本机回环地址。

前端分别填写 **项目根目录（完整分析范围）** 与 **目标文件或目录（实际修改范围）**，先预览，再确认写入或移除。

## 注释格式

```python
# 原有注释：由作者维护
# 功能：查找列
# 说明：返回匹配关键词的列名。
## 调用了：
#   本模块
#   └─ normalize()
## 被调用：
#   项目模块
#   └─ processors.mv_processor              → process_file()
def find_column(columns, keyword):
    ...
```

只自动管理 `## 调用了：` / `## 被调用：`，保留原有注释、功能、说明、Docstring 及代码逻辑。模块箭头固定显示列并对长函数列表折行。

## v0.2.0 安全性改进

- 写入前校验全部目标文件，并先把新内容暂存到同目录临时文件。
- 单个文件采用原子替换；批量写入发生普通异常时尝试恢复已替换的文件。
- 支持 UTF-8 BOM、CRLF、装饰器及原有中文业务注释的可逆操作。
- 运行回归测试：从项目父目录执行 `python -m unittest discover -s code_annotations/tests -v`。
- 注意：断电、进程强制终止、多进程同时写同一项目，以及操作系统拒绝恢复等极端情况，不保证跨文件强事务性。建议使用 Git 版本管理。

## 开发原则

- 写入与移除应是可逆的，并能重复执行而不产生重复注释。
- 每次编辑前后验证 Python AST 一致。
- 分析主要基于 Python 标准库 AST；不承诺完整动态调用覆盖。
- 尽量在独立测试目录先使用；不要直接在未提交的关键业务文件上批量操作。

## License

MIT
