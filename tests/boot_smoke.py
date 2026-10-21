#!/usr/bin/env python3
"""Boot the NyxOS ISO in QEMU and check that the pieces work together.

    python3 tests/boot_smoke.py image/build/nyxos-amd64.iso

Needs: qemu-system-x86_64, xorriso. Uses KVM if /dev/kvm exists, otherwise slow TCG emulation
(allow 10+ minutes). Boots with -kernel/-initrd taken from the ISO so the serial console is
guaranteed; the ISO's own bootloader is NOT exercised here.

Set NYX_TEST_USER / NYX_TEST_PASSWORD if the serial console asks for a login.
Set NYX_TEST_EXTRA_ARGS to add kernel arguments (e.g. to try a boot fix without rebuilding).

Optional real-model check: set NYX_TEST_LLM_URL (as seen from the guest, e.g. http://10.0.2.2:31415/v1,
10.0.2.2 is the QEMU host) and NYX_TEST_LLM_KEY / NYX_TEST_LLM_MODEL. The key is passed to the guest
over the serial console only for this run.
"""
import os
import re
import subprocess
import sys
import tempfile
import threading
import time


class Guest:
    def __init__(self, cmd):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.buf = ""
        self.pos = 0
        self.lock = threading.Lock()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            chunk = self.proc.stdout.read1(4096)
            if not chunk:
                return
            text = chunk.decode("utf-8", "replace")
            if os.environ.get("NYX_TEST_VERBOSE"):
                sys.stdout.write(text)
                sys.stdout.flush()
            with self.lock:
                self.buf += text

    def send(self, text):
        self.proc.stdin.write(text.encode())
        self.proc.stdin.flush()

    def expect(self, pattern, timeout):
        """Wait for regex in output produced since the last successful expect. Returns the match or None."""
        end = time.time() + timeout
        rx = re.compile(pattern, re.S)
        while time.time() < end:
            with self.lock:
                m = rx.search(self.buf, self.pos)
                if m:
                    self.pos = m.end()
                    return m
            if self.proc.poll() is not None:
                return None
            time.sleep(0.5)
        return None

    def tail(self, n=1500):
        with self.lock:
            return self.buf[-n:]


def default_boot_entry(iso, workdir):
    """Read the ISO's own default GRUB entry: (kernel path, initrd path, kernel args)."""
    cfg = os.path.join(workdir, "grub.cfg")
    subprocess.run(["xorriso", "-osirrox", "on", "-indev", iso, "-extract", "/boot/grub/grub.cfg", cfg],
                   check=True, capture_output=True)
    text = open(cfg, encoding="utf-8", errors="replace").read()
    linux = re.search(r"^\s*linux\s+(\S+)\s*(.*)$", text, re.M)
    initrd = re.search(r"^\s*initrd\s+(\S+)", text, re.M)
    if not linux or not initrd:
        raise SystemExit("no linux/initrd line in the ISO's grub.cfg")
    args = [a for a in linux.group(2).split() if not a.startswith("findiso=") and a not in ("quiet", "splash")]
    return linux.group(1), initrd.group(1), args


def extract_kernel(iso, workdir):
    kernel_path, initrd_path, args = default_boot_entry(iso, workdir)
    out = []
    for src, name in ((kernel_path, "vmlinuz"), (initrd_path, "initrd")):
        dst = os.path.join(workdir, name)
        subprocess.run(["xorriso", "-osirrox", "on", "-indev", iso, "-extract", src, dst],
                       check=True, capture_output=True)
        out.append(dst)
    return out[0], out[1], args


USER = os.environ.get("NYX_TEST_USER", "ubuntu")
PASSWORD = os.environ.get("NYX_TEST_PASSWORD", "")


def main(iso):
    results = []

    def check(name, ok, detail=""):
        results.append((name, ok))
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail and not ok else ""), flush=True)

    with tempfile.TemporaryDirectory() as work:
        kernel, initrd, boot_args = extract_kernel(iso, work)
        accel = "kvm:tcg" if os.path.exists("/dev/kvm") else "tcg"
        cmd = [
            "qemu-system-x86_64", "-machine", f"accel={accel}", "-m", "3072", "-smp", "4",
            "-nographic", "-no-reboot", "-cdrom", iso, "-kernel", kernel, "-initrd", initrd,
            "-append", " ".join(boot_args + os.environ.get("NYX_TEST_EXTRA_ARGS", "").split()
                                 + ["console=ttyS0,115200", "noprompt", "systemd.show_status=0"]),
            "-nic", "user",
        ]
        print(f"booting with accel={accel} ...", flush=True)
        g = Guest(cmd)
        try:
            booted = False
            deadline = time.time() + 2400
            while time.time() < deadline and not booted:
                if g.expect(r"Kernel panic|Attempted to kill init", 0.1):
                    break
                g.send("\n")
                m = g.expect(r"(login:|Password:)", 5)
                if m:
                    g.send("ubuntu\n" if "login:" in m.group(0) else "\n")
                # A real shell answers arithmetic; the echoed command and kernel logs cannot fake "42".
                g.send("sh -c 'echo NYX-BOOT-$((6*7))'\n")
                booted = bool(g.expect(r"NYX-BOOT-42", 15))
            check("boots to a shell on serial console", booted, g.tail())
            if not booted:
                return finish(results)

            def run(snippet, timeout=60):
                """Run a shell snippet (works in bash and nu), return (exit code, output) or (None, output)."""
                g.pos = len(g.buf)
                g.send(f"sh -c '{snippet}; echo NYX_RESULT=$?'\n")
                m = g.expect(r"NYX_RESULT=(\d+)", timeout)
                with g.lock:
                    out = g.buf[g.pos - 400:g.pos] if m else g.tail()
                return (int(m.group(1)) if m else None), out

            code, out = run("nu --version | grep -q 0.116")
            check("nushell 0.116 installed", code == 0, out)
            code, out = run("nyx config | grep -q backend")
            check("nyx runs (python module, config)", code == 0, out)
            code, out = run('test "$(systemctl is-active nyxd nyx-alertlog | grep -cx active)" = 2')
            check("nyxd and nyx-alertlog services active", code == 0, out)
            code, out = run("test -f /usr/local/share/nushell/vendor/autoload/nyx.nu && test -f /etc/nyx/nyx.conf")
            check("nushell glue and nyx.conf installed", code == 0, out)
            code, out = run(
                'logger -p user.err -t nyxsmoke "nyx smoke test event"; sleep 6; '
                'nyx alerts --history | grep -q "nyx smoke test event"', 90)
            check("injected log error reaches nyx alerts (M5)", code == 0, out)

            url = os.environ.get("NYX_TEST_LLM_URL")
            if url:
                key, model = os.environ.get("NYX_TEST_LLM_KEY", ""), os.environ.get("NYX_TEST_LLM_MODEL", "auto")
                env = f"NYX_BACKEND=local NYX_LOCAL_URL={url} NYX_LOCAL_MODEL={model} NYX_LOCAL_KEY={key}"
                code, out = run(f'{env} nyx --dry-run list the biggest files here | grep -q "risk:"', 180)
                check("real model turns English into a proposal (M2)", code == 0, out)
                code, out = run(f'{env} nyx --dry-run install the htop package | grep -q "nyx-pkg install htop"', 180)
                check("real model package intent becomes nyx-pkg (M4)", code == 0, out)
            else:
                print("SKIP  real model checks (set NYX_TEST_LLM_URL)")
        finally:
            g.proc.kill()
    return finish(results)


def finish(results):
    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed or not results else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(sys.argv[1]))
