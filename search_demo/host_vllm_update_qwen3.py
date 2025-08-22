#!/usr/bin/env python3
# host_vllm.py
import argparse
import json
import os
import subprocess
import time
import requests
import signal

def wait_for_server(base_url: str, timeout: int = 1200):
    start = time.time()
    while True:
        try:
            r = requests.get(f"{base_url}/v1/models", timeout=3)
            if r.status_code == 200:
                print("[INFO] vLLM server is up.")
                return
        except Exception:
            pass
        if time.time() - start > timeout:
            raise RuntimeError(f"Server did not start at {base_url} within {timeout}s")
        time.sleep(2)

def main():
    p = argparse.ArgumentParser(description="Start vLLM OpenAI-compatible server")
    p.add_argument("--model", required=True, help="HF 名称或本地路径")
    p.add_argument("--model-name", required=True, help="对外服务的模型名（/v1/models 会显示）")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--gpu", type=int, default=1,
                   help="tensor-parallel size；若提供 --gpus 列表则忽略该参数")
    p.add_argument("--gpus", type=str, default=None,
                   help="指定 GPU 列表，例如 '0,1'；会设置 CUDA_VISIBLE_DEVICES")
    p.add_argument("--pid-file", type=str, default=None,
                   help="保存进程信息的 JSON 文件路径（默认 .vllm_<port>.json）")

    # 工具调用相关
    p.add_argument("--enable-auto-tool-choice", action="store_true",
                   help="启用自动工具调用（tools/function calling）。AG2 DeepResearch 需要。")
    p.add_argument("--tool-call-parser", type=str, default=None,
                   help="工具调用解析器，例如 hermes（Qwen3），llama3_json（Llama 3），deepseek_v3（DeepSeek V3）等。")

    # Ctrl+C 行为
    p.add_argument("--keep-alive-on-ctrl-c", action="store_true",
                   help="Ctrl+C 时保留子进程在后台运行（默认不保留，会终止子进程）。")

    args = p.parse_args()

    env = os.environ.copy()
    tp = args.gpu
    if args.gpus:
        env["CUDA_VISIBLE_DEVICES"] = args.gpus
        tp = len([g for g in args.gpus.split(",") if g.strip() != ""])

    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        f"--model={args.model}",
        f"--served-model-name={args.model_name}",
        f"--tensor-parallel-size={tp}",
        "--gpu-memory-utilization=0.85",
        f"--port={args.port}",
        "--trust-remote-code",
    ]

    # 注意这里用下划线属性名
    if args.enable_auto_tool_choice:
        cmd.append("--enable-auto-tool-choice")
    if args.tool_call_parser:
        cmd += ["--tool-call-parser", args.tool_call_parser]

    print("[INFO] Launching:", " ".join(cmd))
    proc = subprocess.Popen(cmd, shell=False, env=env)

    base_url = f"http://localhost:{args.port}"
    wait_for_server(base_url, timeout=1200)

    meta = {
        "pid": proc.pid,
        "port": args.port,
        "model": args.model,
        "model_name": args.model_name,
        "cmd": cmd,
        "start_time": int(time.time()),
        "enable_auto_tool_choice": args.enable_auto_tool_choice,
        "tool_call_parser": args.tool_call_parser,
    }
    pid_file = args.pid_file or f".vllm_{args.port}.json"
    with open(pid_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Started vLLM server on {base_url} (PID={proc.pid})")
    print(f"[INFO] Metadata written to {pid_file}")

    try:
        proc.wait()
    except KeyboardInterrupt:
        if args.keep_alive_on_ctrl_c:
            print("\n[INFO] Ctrl+C detected. Keeping child process running in background (PID not reaped).")
        else:
            print("\n[INFO] Ctrl+C detected. Terminating child process...")
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    print("[WARN] Graceful terminate timed out. Sending SIGKILL...")
                    if os.name == "nt":
                        proc.kill()
                    else:
                        os.kill(proc.pid, signal.SIGKILL)
            finally:
                print("[INFO] Child process terminated. Exiting.")

if __name__ == "__main__":
    main()
