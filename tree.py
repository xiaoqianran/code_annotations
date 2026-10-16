"""Read-only Chinese call-tree explorer backed by CodeGraph CLI JSON."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

HTML = r"""<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>项目调用树 · CodeGraph</title>
<style>
*{box-sizing:border-box}body{margin:0;color:#182230;background:#f6f8fc;font:14px "Segoe UI","Microsoft YaHei",sans-serif}button,input,select{font:inherit}button{cursor:pointer;border:1px solid #d5deea;border-radius:8px;background:white;padding:9px 12px;color:#25334b}button:hover{background:#eaf1ff}input,select{border:1px solid #d5deea;border-radius:8px;background:white;padding:10px;width:100%}
header{padding:16px 25px;background:white;border-bottom:1px solid #dce3ed;display:flex;align-items:center;gap:20px}h1{font-size:20px;margin:0}header a{color:#285fce;text-decoration:none}main{padding:20px;max-width:1600px;margin:auto}.bar{display:flex;gap:12px;align-items:end;margin-bottom:15px}.bar label:first-child{flex:1}.bar label{font-size:12px;color:#63748c}.bar label input,.bar label select{margin-top:6px}.layout{display:grid;grid-template-columns:250px minmax(350px,1fr) minmax(320px,1fr);gap:14px;height:calc(100vh - 168px);min-height:560px}.pane{border:1px solid #dce3ed;background:white;border-radius:12px;overflow:auto}.pane h2{font-size:14px;margin:0;padding:15px 16px;border-bottom:1px solid #e4eaf3;position:sticky;top:0;background:white;z-index:1}.content{padding:12px}.file{display:block;width:100%;text-align:left;border:0;padding:7px 8px;white-space:normal;word-break:break-word;color:#43536e}.file.active{background:#dbeafe;color:#124abb}.node{margin:6px 0;padding:6px 8px;border-left:1px solid #d5e0ee}.node button{border:0;padding:4px 7px;font-family:Consolas,monospace;font-size:12px;word-break:break-word;text-align:left}.node .row{display:flex;align-items:center;gap:5px}.node .secondary{font-size:11px;color:#8290a6;margin:2px 0 4px 8px}.node .children{padding-left:15px;border-left:1px dashed #d7e0eb;margin-left:13px}.status{color:#62748e;font-size:12px;margin:0 0 12px}.source{white-space:pre;overflow:auto;background:#111a2a;color:#e2e8f0;padding:16px;font:12px/1.7 Consolas,monospace;min-height:350px;border-radius:8px}.tag{color:#9b5b05;background:#fff3d4;border-radius:4px;font-size:11px;padding:2px 5px}.hint{color:#74839b;font-size:12px}.toolbar{display:flex;gap:8px;margin-bottom:10px}.toolbar button.selected{background:#dbeafe;border-color:#93c5fd}.error{color:#b42318}.footer{color:#73839b;font-size:11px;margin-top:10px}@media(max-width:1050px){.layout{grid-template-columns:220px 1fr;height:auto}.pane{min-height:400px}.pane:last-child{grid-column:1 / -1}}@media(max-width:600px){.layout{display:block}.pane{margin-bottom:15px}.bar{flex-wrap:wrap}header{flex-wrap:wrap}}
</style></head><body><header><h1>项目调用树</h1><a href="/">返回注释管理</a><span class="hint">CodeGraph 分析 · 简体中文 · 只读</span></header>
<main><div class="bar"><label>项目根目录<input id="root" placeholder="D:\project\tools"></label><label style="width:180px">方向<select id="direction"><option value="callees">向下：调用了谁</option><option value="callers">向上：谁调用我</option></select></label><button id="load">读取项目</button></div>
<div class="layout">
<section class="pane"><h2>① 项目文件</h2><div class="content"><input id="filter" placeholder="搜索路径，例如 mv_processor"><p id="fileStatus" class="status"></p><div id="files"></div></div></section>
<section class="pane"><h2>② 函数调用树（点击箭头展开）</h2><div class="content"><p id="treeStatus" class="status">选中文件后显示该文件的函数。</p><div id="tree"></div><p class="footer">仅「calls」作为调用边；import 和 references 不视为执行调用。循环节点会停止展开。</p></div></section>
<section class="pane"><h2>③ 函数源码</h2><div class="content"><p id="sourceStatus" class="status">点击函数名查看对应源码。</p><pre id="source" class="source">未选择函数</pre></div></section>
</div></main><script>
const $=id=>document.getElementById(id);let paths=[],active='',generation=0;
function el(t,s,c){const a=document.createElement(t);if(s!==undefined)a.textContent=s;if(c)a.className=c;return a}
async function api(action,data){const r=await fetch('/api/tree',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...data})});const j=await r.json();if(!r.ok)throw Error(j.error||'请求失败');return j}
async function load(){const root=$('root').value.trim();if(!root)return;$('fileStatus').textContent='读取 CodeGraph 索引中...';$('tree').replaceChildren();$('source').textContent='未选择函数';generation++;try{let d=await api('files',{root});paths=d.files.filter(x=>x.path.endsWith('.py'));$('fileStatus').textContent=paths.length+' 个 Python 文件';showFiles()}catch(e){$('fileStatus').textContent=e.message;$('fileStatus').className='status error'}}
function showFiles(){const needle=$('filter').value.toLowerCase();const container=$('files');container.replaceChildren();for(const item of paths.filter(x=>x.path.toLowerCase().includes(needle)).slice(0,450)){const b=el('button',item.path,'file'+(item.path===active?' active':''));b.onclick=()=>selectFile(item.path);container.append(b)}}
async function selectFile(path){active=path;generation++;showFiles();const ticket=generation;$('tree').replaceChildren();$('treeStatus').textContent='正在读取 '+path+' 的函数...';try{const data=await api('symbols',{root:$('root').value.trim(),file:path});if(ticket!==generation)return;$('treeStatus').textContent=path+' · '+data.symbols.length+' 个函数或方法';for(const s of data.symbols){const node=createNode(s,new Set());$('tree').append(node)}}catch(e){$('treeStatus').textContent=e.message}}
function createNode(s,ancestors){const wrap=el('div',undefined,'node'),row=el('div',undefined,'row');const expand=el('button','▸');const name=el('button',s.name+'()');const info=el('div',s.filePath+':'+s.startLine,'secondary');row.append(expand,name);wrap.append(row,info);const children=el('div',undefined,'children');children.hidden=true;wrap.append(children);name.onclick=()=>showSource(s);
const key=s.id||s.filePath+':'+s.startLine;if(ancestors.has(key)){expand.textContent='↻';expand.disabled=true;info.textContent+=' · 检测到循环';return wrap}
expand.onclick=async()=>{if(!children.hidden){children.hidden=true;expand.textContent='▸';return}children.hidden=false;expand.textContent='▾';if(children.dataset.loaded)return;children.append(el('div','读取下一层...','hint'));try{const d=await api('edges',{root:$('root').value.trim(),file:s.filePath,name:s.name,direction:$('direction').value});children.replaceChildren();const next=new Set(ancestors);next.add(key);let count=0;for(const n of d.nodes){if(n.id===key)continue;children.append(createNode(n,next));count++}if(!count)children.append(el('div','无已确认的直接函数调用','hint'));children.dataset.loaded='1'}catch(e){children.replaceChildren(el('div',e.message,'error'))}};
return wrap}
async function showSource(s){$('sourceStatus').textContent=s.filePath+':'+s.startLine;$('source').textContent='加载源码...';try{const d=await api('source',{root:$('root').value.trim(),file:s.filePath,line:s.startLine});$('source').textContent=d.source}catch(e){$('source').textContent=e.message}}
$('load').onclick=load;$('filter').oninput=showFiles;$('direction').onchange=()=>{if(active)selectFile(active)};
</script></body></html>"""


def _codegraph(root: Path, *args: str) -> object:
    try:
        executable = (shutil.which("codegraph.cmd") if os.name == "nt" else shutil.which("codegraph"))
        if not executable:
            raise FileNotFoundError("codegraph")
        result = subprocess.run([executable, *args, "--path", str(root), "--json"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=35, shell=False)
    except FileNotFoundError as exc:
        raise ValueError("未找到 codegraph 命令，请先安装并确认 PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("CodeGraph 查询超时，请检查项目索引") from exc
    if result.returncode:
        raise ValueError((result.stderr or result.stdout or "CodeGraph 查询失败").strip()[:500])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("CodeGraph 未返回有效 JSON；请先在项目目录执行 codegraph init") from exc


def _root(value: object) -> Path:
    if not isinstance(value, str):
        raise ValueError("请输入有效的项目根目录")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("项目根目录不存在")
    if not (root / ".codegraph").exists():
        raise ValueError("尚未建立索引：请先在项目根目录执行 codegraph init")
    return root


def _file(root: Path, value: object) -> Path:
    if not isinstance(value, str):
        raise ValueError("文件路径缺失")
    file = (root / value).resolve()
    if not file.is_relative_to(root) or not file.is_file() or file.suffix != ".py":
        raise ValueError("只允许读取项目内的 Python 文件")
    return file


def operation(data: dict) -> dict:
    root = _root(data.get("root"))
    action = data.get("action")
    if action == "files":
        rows = _codegraph(root, "files", "--format", "flat")
        return {"files": [{"path": row["path"]} for row in rows if isinstance(row, dict) and isinstance(row.get("path"), str)]}
    file = _file(root, data.get("file"))
    relative = file.relative_to(root).as_posix()
    if action == "symbols":
        # Local AST enumerates definitions; edges come from CodeGraph JSON.
        import ast
        syntax = ast.parse(file.read_text(encoding="utf-8-sig"))
        symbols = []
        def collect(nodes, prefix=""):
            for n in nodes:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qname = prefix + n.name
                    if not isinstance(n, ast.ClassDef):
                        symbols.append({"name": n.name, "filePath": relative, "startLine": n.lineno,
                                        "id": f"{relative}:{n.lineno}", "qualname": qname})
                    collect(n.body, qname + ".")
        collect(syntax.body)
        return {"symbols": symbols}
    if action == "source":
        line = data.get("line")
        if not isinstance(line, int) or line < 1:
            raise ValueError("行号无效")
        lines = file.read_text(encoding="utf-8-sig").splitlines()
        return {"source": "\n".join(f"{i+1:>5}  {lines[i]}" for i in range(max(0,line-3), min(len(lines),line+85)))}
    if action == "edges":
        name = data.get("name")
        direction = data.get("direction")
        if not isinstance(name, str) or not name.isidentifier() or direction not in ("callers", "callees"):
            raise ValueError("无效的函数查询")
        result = _codegraph(root, direction, name, "--file", relative, "--limit", "250")
        found = []
        seen = set()
        for definition in result.get("definitions", []):
            anchor = definition.get("definition", {})
            if anchor.get("filePath") != relative:
                continue
            for node in definition.get(direction, []):
                if "calls" not in node.get("relationships", []):
                    continue
                if not node.get("filePath") or not node.get("name"):
                    continue
                key = (node["filePath"], node.get("startLine"), node["name"])
                if key in seen:
                    continue
                seen.add(key)
                found.append({"id": node.get("id") or str(key), "name": node["name"],
                              "filePath": node["filePath"], "startLine": node.get("startLine", 1)})
        return {"nodes": found}
    raise ValueError("未知操作")
