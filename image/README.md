# NyxOS image (Owner: Utpal)

This directory builds an experimental Ubuntu 24.04 (Noble) amd64 live ISO with
`live-build`. It uses the Ubuntu archive, boots through Casper to a shell, and
installs Nushell, `nyx-pkg`, and the `nyxd` system service. It uses Ubuntu's
`generic` kernel flavour and stages a pinned Nushell release binary into the
image because Noble does not provide the `nushell` package.
It also supplies the legacy `mkfs.msdos` path that this live-build version
expects for UEFI images; Noble's `dosfstools` package provides `mkfs.fat`.

## Build

On an Ubuntu, Debian, or Arch based amd64 build host, install `live-build`,
`debootstrap`, `xorriso`, `squashfs-tools`, `isolinux`, `syslinux-common`, `syslinux-utils`,
`grub-pc-bin`, `grub-efi-amd64-bin`, `mtools`, and `dosfstools`. The build must
run as root and needs network access to Ubuntu package archives and crates.io.
On Arch based hosts, `dosfstools` provides `mkfs.fat`; the build script supplies
the legacy `mkfs.msdos` command name expected by live-build.
From the repository root, run:

```sh
sudo ./image/build.sh
```

The script caches the pinned Nushell archive in `image/.build-work/downloads`
and verifies its SHA-256 before each build. It stages the package wrapper,
daemon source, and Nushell binary into `image/.build-work`, runs the image
build, then writes `image/build/nyxos-amd64.iso`. It reuses live-build's
bootstrap and downloaded package caches across runs while clearing the old
chroot and ISO output before
each build. Package indexes are refreshed each time. Rust build tools are
installed temporarily inside the image build chroot and removed after
compiling `nyxd`.

To discard the saved cache and start over, run
`sudo lb clean --purge` from `image/.build-work`.

The image is a live system, not an installer for a persistent disk install. It
is configured to autologin the ephemeral `ubuntu` account on the local and
serial consoles. Review boot behavior in QEMU before treating it as ready for
hardware. The ISO build has not yet been validated in this repository.
