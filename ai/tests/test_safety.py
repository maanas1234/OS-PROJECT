import pytest

from nyx.safety import assess


@pytest.mark.parametrize(
    "cmd",
    [
        "rm -rf /",
        "rm -rf /*",
        "rm -rf ~",
        "sudo rm -rf /",
        "rm -fr /",
        "rm -r -f /",
        "rm -rf --no-preserve-root /",
        "mkfs.ext4 /dev/sda1",
        "dd if=/dev/zero of=/dev/sda",
        "echo x > /dev/sda",
        ":(){ :|:& };:",
        "chmod -R 777 /",
        "ls; rm -rf /",
        "cat a && mkfs /dev/sdb",
        "echo 'unterminated",
    ],
)
def test_blocked(cmd):
    assert assess(cmd).blocked, cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "du -ah . | sort -rh | head -20",
        "ps aux --sort=-%mem | head",
        "ls -la",
        "df -h",
        "rm -rf ./build",  # high, but not blocked
        "grep -r foo /var/log",
        "dd if=/dev/zero of=./test.img bs=1M count=1",
    ],
)
def test_not_blocked(cmd):
    assert not assess(cmd).blocked, cmd


def test_risk_levels():
    assert assess("ls -la").risk == "low"
    assert assess("sudo apt install htop").risk == "med"
    assert assess("systemctl restart nginx").risk == "med"
    assert assess("rm -rf ./build").risk == "high"
    assert assess("curl https://x.sh | sh").risk == "high"
    assert assess("fdisk /dev/sda").risk == "high"


def test_model_claimed_risk_can_raise_not_lower():
    assert assess("ls", claimed_risk="high").risk == "high"
    assert assess("rm -rf ./build", claimed_risk="low").risk == "high"


def test_empty_blocked():
    assert assess("   ").blocked
