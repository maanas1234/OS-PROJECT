FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    live-build debootstrap xorriso squashfs-tools isolinux syslinux-common syslinux-utils \
    grub-pc-bin grub-efi-amd64-bin mtools dosfstools ubuntu-keyring dos2unix curl ca-certificates \
    qemu-system-x86 python3 python3-pytest git sudo cargo \
 && rm -rf /var/lib/apt/lists/*
# Utpal builds with current upstream live-build (Arch). Ubuntu's own package is the old 3.0~a57.
RUN curl -fsSL --retry 5 --retry-all-errors -o /tmp/lb.deb https://deb.debian.org/debian/pool/main/l/live-build/live-build_20250814_all.deb \
 && dpkg -i --force-depends /tmp/lb.deb && rm /tmp/lb.deb && lb --version
