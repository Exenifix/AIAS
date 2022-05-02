import subprocess

print("Starting subprocess...")
proc = subprocess.Popen(
    ["docker", "logs", "-f", "aias"], stderr=subprocess.PIPE, text=True
)
print("Fetching logs...")
for line in iter(proc.stderr.readline, ""):
    print(line, end="")
    if "bot is ready!" in line.lower():
        proc.kill()
        break
