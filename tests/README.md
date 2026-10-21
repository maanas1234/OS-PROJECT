# tests/ (Shared)

| What | How |
|---|---|
| `nyx` unit tests (68) | `cd ai && PYTHONPATH=. python -m pytest` (Windows, Linux, no network needed) |
| ISO boot + integration | `python3 tests/boot_smoke.py image/build/nyxos-amd64.iso` |

## boot_smoke.py

Boots the ISO in QEMU on the serial console and checks, in order: boots to a shell, Nushell present, `nyx` runs,
`nyxd` and `nyx-alertlog` active, DHCP network, Nushell glue installed, an injected `logger -p user.err` reaches
`nyx alerts`, and (optional) a real model turns English into a proposal. Last full run: **9/9**.

It uses the kernel, initrd and arguments from the ISO's own default GRUB entry plus `console=ttyS0`, so the real boot
parameters are tested. The bootloader itself (isolinux/GRUB, UEFI) is **not** exercised.

Real-model checks (optional): `NYX_TEST_LLM_URL` (as the guest sees it; `http://10.0.2.2:PORT/v1` is the QEMU host),
`NYX_TEST_LLM_KEY`, `NYX_TEST_LLM_MODEL`. Never commit keys.

Without `/dev/kvm` QEMU falls back to software emulation: a boot takes 5 to 10 minutes and is occasionally flaky when the
machine is busy (a guest can stall right after journald starts; just rerun). Use 2 CPUs; 4 hung more often.

## Building and testing in Docker (no Linux host needed)

`builder.Dockerfile` has live-build (upstream 20250814, same family as an Arch host), debootstrap, QEMU and xorriso.

```bash
docker build -t nyxos-builder -f tests/builder.Dockerfile tests/
docker run --rm --privileged -v "$PWD:/src:ro" -v "$PWD/out:/out" -v nyxos-cache:/work/image/.build-work \
  nyxos-builder bash -c 'cp -a /src/. /work/ && cd /work && sh image/build.sh && cp image/build/nyxos-amd64.iso /out/'
```

Add `-e NYX_BUNDLE_MODEL=1` for the offline-model image (+1.2 GB). Windows checkouts: run `dos2unix` over the copy first
(CRLF breaks shebangs); `.gitattributes` fixes this for fresh clones.
