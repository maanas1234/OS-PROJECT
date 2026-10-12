# NyxOS image (Owner: Utpal)

This directory builds an experimental Ubuntu 24.04 (Noble) amd64 live ISO with
`live-build`. It uses the Ubuntu archive, boots through Casper to a shell, and
installs Nushell, `nyx-pkg`, and the `nyxd` system service.

## Build

On an Ubuntu or Debian amd64 build host, install `live-build`, `debootstrap`,
`xorriso`, `squashfs-tools`, `isolinux`, `syslinux-common`, `syslinux-utils`,
`grub-pc-bin`, `grub-efi-amd64-bin`, `mtools`, and `dosfstools`. The build must
run as root and needs network access to Ubuntu package archives and crates.io.
From the repository root, run:

```sh
sudo ./image/build.sh
```

The script stages the current package wrapper and daemon source into
`image/.build-work`, runs the image build, then writes
`image/build/nyxos-amd64.iso`. It reuses live-build's bootstrap and downloaded
package caches across runs while clearing the old chroot and ISO output before
each build. Package indexes are refreshed each time. Rust build tools are
installed temporarily inside the image build chroot and removed after
compiling `nyxd`.

To discard the saved cache and start over, run
`sudo lb clean --purge` from `image/.build-work`.

The image is a live system, not an installer for a persistent disk install. It
is configured to autologin the ephemeral `ubuntu` account on the local and
serial consoles. Review boot behavior in QEMU before treating it as ready for
hardware. The ISO build has not yet been validated in this repository.
