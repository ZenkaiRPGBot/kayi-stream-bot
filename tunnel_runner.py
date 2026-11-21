import subprocess
import re
import os
import time

tunnel_file = os.path.join(os.path.dirname(__file__), "tunnel_url.txt")
cf_exe = os.path.join(os.path.dirname(__file__), "cloudflared.exe")

print("Starting cloudflared tunnel manager...", flush=True)
while True:
    try:
        proc = subprocess.Popen(
            [cf_exe, "tunnel", "--url", "http://127.0.0.1:8081"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        url = None
        for line in proc.stdout:
            clean_l = line.strip()
            print("[cf]", clean_l, flush=True)
            m = re.search(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', clean_l)
            if m:
                url = m.group(1)
                print(f"\n==========================================", flush=True)
                print(f"🔥 CLOUDFLARE TUNNEL LIVE: {url}", flush=True)
                print(f"==========================================\n", flush=True)
                with open(tunnel_file, "w") as f:
                    f.write(url)
            if "Tunnel not found" in clean_l or "Unauthorized" in clean_l:
                print("[cf] Detected dead tunnel session. Forcing restart...", flush=True)
                proc.kill()
                break
        proc.wait()
    except Exception as e:
        print(f"[tunnel error] {e}", flush=True)
    print("Tunnel process disconnected. Restarting in 3s...", flush=True)
    time.sleep(3)
