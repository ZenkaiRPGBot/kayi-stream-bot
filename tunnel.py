import subprocess
import re
import os
import sys
import time

def start_tunnel(port=8081):
    cf_exe = os.path.join(os.path.dirname(__file__), "cloudflared.exe")
    if not os.path.exists(cf_exe):
        print("cloudflared.exe not found")
        return None, None

    cmd = [cf_exe, "tunnel", "--url", f"http://127.0.0.1:{port}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    tunnel_url = None
    start_time = time.time()
    # Read output to find trycloudflare.com
    for line in proc.stdout:
        print("[cloudflared]", line.strip())
        m = re.search(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', line)
        if m:
            tunnel_url = m.group(1)
            print(f"\n==========================================")
            print(f"🔥 PUBLIC STREAM URL: {tunnel_url}")
            print(f"==========================================\n")
            break
        if time.time() - start_time > 20:
            break

    return proc, tunnel_url

if __name__ == "__main__":
    proc, url = start_tunnel()
    if url:
        # Write to a file so bot can read it
        with open("tunnel_url.txt", "w") as f:
            f.write(url)
        proc.wait()
