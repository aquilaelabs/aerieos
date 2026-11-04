"""The boot menu's Rescue entry picked over serial, and each line of a file run there."""
import socket,sys,time
SOCK="/tmp/vmwalk-root.sock"
s=socket.socket(socket.AF_UNIX); s.connect(SOCK); s.settimeout(0.5)
buf=b""; end=time.time()+90; picked=False
while time.time()<end:
    try: buf+=s.recv(65536)
    except socket.timeout: pass
    if not picked and b"Press enter to boot" in buf:
        for k in [b"\x1b[B"]*3: s.sendall(k); time.sleep(0.2)
        time.sleep(0.3); tail=buf[-1500:]; s.sendall(b"\r"); picked=True; print("picked rescue"); buf=b""
    if picked and b"Press Enter for system maintenance" in buf:
        s.sendall(b"\r"); time.sleep(2); break
print(buf[-500:].decode("utf-8","replace"))
def run(c,w=4):
    s.sendall(c.encode()+b"\n"); out=b"";e=time.time()+w
    while time.time()<e:
        try: out+=s.recv(65536)
        except socket.timeout: pass
    print(">>",c); print(out.decode("utf-8","replace")[-int(sys.argv[2]) if len(sys.argv)>2 else -3000:])
for c in open(sys.argv[1]): 
    if c.strip(): run(c.rstrip("\n"), 6)
