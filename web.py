"""Local-only browser interface for code_annotations (stdlib, no dependencies)."""
from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .analyzer import Index
from .editor import diff, edit, write

_PAGE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Code Annotations</title>
<style>
:root{font-family:Inter,"Segoe UI","Microsoft YaHei",sans-serif;background:#f5f6fa;color:#1e293b}
*{box-sizing:border-box}body{margin:0}.wrap{max-width:1100px;margin:44px auto;padding:0 22px}
header{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}
h1{font-size:26px;letter-spacing:-.7px;margin:0}h2{font-size:17px;margin:0 0 18px}
.subtitle{color:#64748b;font-size:14px;margin-top:7px}.pill{font-size:12px;color:#475569;border:1px solid #cbd5e1;border-radius:20px;padding:7px 11px}
.panel{background:#fff;border:1px solid #e2e8f0;border-radius:15px;padding:26px;margin-bottom:20px;box-shadow:0 3px 15px #15234207}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}label{display:block;font-size:13px;font-weight:650;margin-bottom:8px}
input{width:100%;height:44px;border:1px solid #cbd5e1;border-radius:9px;padding:0 13px;font:13px Consolas,monospace;background:#fff}
input:focus{outline:2px solid #bfdbfe;border-color:#3b82f6}.hint{font-size:12px;color:#64748b;margin-top:8px}
.actions{display:flex;align-items:center;gap:10px;margin-top:23px;flex-wrap:wrap}
button{border:1px solid #cbd5e1;border-radius:9px;background:#fff;padding:11px 19px;cursor:pointer;font-weight:650;color:#334155}
button.primary{background:#1d4ed8;border-color:#1d4ed8;color:white}button.danger{color:#b91c1c;border-color:#fca5a5}
button:disabled{opacity:.45;cursor:not-allowed}button:hover:not(:disabled){filter:brightness(.96)}
#status{font-size:13px;color:#64748b;margin-left:auto}.summary{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:15px;font-size:13px;color:#475569}
strong{color:#111827}.file{padding:13px 15px;border:1px solid #e2e8f0;border-radius:9px;margin:9px 0;font-size:13px}
.file details summary{cursor:pointer;font-weight:650}.file small{display:block;margin-top:6px;color:#64748b}
pre{white-space:pre;overflow:auto;max-height:400px;border-radius:9px;background:#0f172a;color:#dbeafe;padding:18px;font:12px/1.55 Consolas,monospace}
.empty{color:#94a3b8;font-size:13px;padding:26px 0}.error{color:#b91c1c!important}
@media(max-width:700px){.grid{grid-template-columns:1fr}.wrap{margin:22px auto}.panel{padding:18px}#status{width:100%;margin-left:0}}
</style></head><body><main class="wrap">
<header><div><h1>Code Annotations</h1><div class="subtitle">Python 函数 / 类调用关系 · 本地注释管理</div></div><span class="pill">Local Workspace</span></header>
<section class="panel"><h2>分析范围</h2>
<div class="grid"><div><label for="root">项目根目录 · 用于分析完整调用关系</label><input id="root" placeholder="D:\project"><div class="hint">扫描该目录下所有 Python 模块，建立双向调用索引</div></div>
<div><label for="target">目标文件或目录 · 实际修改范围</label><input id="target" placeholder="D:\project\utils.py"><div class="hint">必须位于根目录内；可填写单个 .py 文件或子目录</div></div></div>
<div class="actions"><button id="preview" class="primary">预览生成</button><button id="previewRemove">预览移除</button><button id="apply" disabled>确认写入</button><button id="remove" class="danger" disabled>确认移除</button><span id="status">先填写目录并预览</span></div>
</section>
<section class="panel"><h2>变更预览</h2><div id="summary" class="summary"></div><div id="results" class="empty">尚未分析。预览不会修改任何文件。</div></section>
</main><script>
const $ = id => document.getElementById(id);
let preview = null;
function reset(){preview=null;$('apply').disabled=true;$('remove').disabled=true}
['root','target'].forEach(id=>$(id).addEventListener('input',reset));
function status(msg,err=false){$('status').textContent=msg;$('status').className=err?'error':''}
function el(tag,text,cls){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x}
async function request(action,commit=false){
 const root=$('root').value.trim(),target=$('target').value.trim();
 if(!root||!target){status('请填写项目根目录和目标路径',true);return}
 const buttons=['preview','previewRemove','apply','remove'].map($);
 buttons.forEach(b=>b.disabled=true);status('正在分析...');
 try{
  const response=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({root,target,action,commit})});
  const data=await response.json();if(!response.ok)throw Error(data.error||'请求失败');
  $('summary').replaceChildren(el('span','扫描文件：'+data.scanned),el('span','存在变更：'+data.changed),el('span','调用节点：'+data.symbols));
  $('results').replaceChildren();
  if(!data.files.length){$('results').append(el('div','无需修改，当前内容已符合要求。','empty'))}
  for(const f of data.files){
   const box=el('div',undefined,'file'),details=document.createElement('details');
   const title=document.createElement('summary');title.textContent=f.path;details.append(title);
   const pre=el('pre',f.diff);details.append(pre);box.append(details);$('results').append(box);
  }
  preview=commit?null:{root,target,action};
  $('apply').disabled=commit||action!=='write'||data.changed===0;
  $('remove').disabled=commit||action!=='remove'||data.changed===0;
  status(commit?('操作完成，修改 '+data.changed+' 个文件'):'预览完成，尚未修改文件');
 }catch(e){reset();status(e.message,true)}
 finally{buttons.slice(0,2).forEach(b=>b.disabled=false)}
}
$('preview').onclick=()=>request('write');
$('previewRemove').onclick=()=>request('remove');
$('apply').onclick=()=>{if(preview?.action==='write'&&confirm('确定将调用关系注释写入所选文件？'))request('write',true)};
$('remove').onclick=()=>{if(preview?.action==='remove'&&confirm('确定移除目标范围内的自动调用关系注释？'))request('remove',true)};
</script></body></html>"""


def run_operation(payload: dict) -> dict:
    root_raw, target_raw = payload.get("root"), payload.get("target")
    action, commit = payload.get("action"), payload.get("commit", False)
    if not isinstance(root_raw, str) or not isinstance(target_raw, str):
        raise ValueError("必须提供根目录和目标路径")
    if action not in {"write", "remove"} or not isinstance(commit, bool):
        raise ValueError("无效操作")
    root, target = Path(root_raw).expanduser().resolve(), Path(target_raw).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("项目根目录不存在")
    if not target.exists() or not target.is_relative_to(root):
        raise ValueError("目标路径必须存在且位于项目根目录之内")
    if target.is_file() and target.suffix != ".py":
        raise ValueError("目标文件必须是 Python 源码")
    index = Index(root).build()
    paths = [target] if target.is_file() else sorted(p for p in index.by_file if p.is_relative_to(target))
    modifications = []
    for path in paths:
        if path.resolve() not in index.by_file:
            continue
        before, after = edit(path, index, action)
        if before != after:
            modifications.append((path, before, after))
    if commit:
        # Verify all inputs before making any changes.
        for path, before, _ in modifications:
            raw = path.read_bytes()
            codec = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
            if raw.decode(codec) != before:
                raise RuntimeError(f"分析期间文件已变更：{path}")
        for path, before, after in modifications:
            write(path, before, after)
    return {
        "scanned": len(paths),
        "changed": len(modifications),
        "symbols": sum(len(index.by_file.get(p, [])) for p in paths),
        "files": [{"path": str(p.relative_to(root)), "diff": diff(p, b, a)} for p, b, a in modifications],
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlparse(self.path).path != "/":
            self.send_error(404)
            return
        data = _PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if urlparse(self.path).path != "/api/run":
            self.send_error(404)
            return
        try:
            origin = self.headers.get("Origin")
            if origin and origin != f"http://127.0.0.1:{self.server.server_port}":
                raise ValueError("禁止跨站写入请求")
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                raise ValueError("只接受 application/json 请求")
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 65536:
                raise ValueError("请求内容大小不合法")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("请求格式不合法")
            result = run_operation(payload)
            code = 200
        except (ValueError, OSError, SyntaxError, RuntimeError, UnicodeError) as exc:
            result, code = {"error": str(exc)}, 400
        except Exception:
            result, code = {"error": "分析失败，请检查路径或源码内容"}, 500
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def main(argv=None):
    parser = argparse.ArgumentParser(description="Launch local code_annotations web interface")
    parser.add_argument("--port", type=int, default=8799, help="Local port (default: 8799)")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    # Bind only to loopback; do not expose filesystem-changing endpoints on a LAN.
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        if args.port != 8799:
            parser.error(f"指定端口 {args.port} 无法使用：{exc}")
        print(f"默认端口 8799 不可用（{exc}），自动选择可用端口。", flush=True)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Code Annotations: {url}", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
