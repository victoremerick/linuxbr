#!/bin/bash
# Runs only inside the explicitly marked disposable QEMU guest.
set -euo pipefail
[[ $(systemd-detect-virt) == kvm || $(systemd-detect-virt) == qemu ]]
grep -q 'linuxbr.domain-test=1' /proc/cmdline
role=$1
exec >/dev/ttyS0 2>&1
trap 's=$?; echo "LINUXBR_DOMAIN_EXIT=$s"; sync; systemctl poweroff --force --force' EXIT
export DEBIAN_FRONTEND=noninteractive
ip link set ens4 up
ip addr add 192.168.76.$([[ $role == dc ]] && echo 10 || echo 20)/24 dev ens4
apt-get update -qq
if [[ $role == dc ]]; then
    apt-get install -y -qq samba-ad-dc winbind dnsutils
    systemctl stop samba-ad-dc smbd nmbd winbind systemd-resolved || true
    hostnamectl set-hostname dc1
    echo '192.168.76.10 dc1.lab.example.test dc1' >>/etc/hosts
    mv /etc/samba/smb.conf /etc/samba/smb.conf.original
    samba-tool domain provision --realm=LAB.EXAMPLE.TEST --domain=LAB --server-role=dc --dns-backend=SAMBA_INTERNAL --adminpass="$(cat /opt/domain-test/admin.secret)" --use-rfc2307 --option='interfaces=lo ens4' --option='bind interfaces only=yes'
    samba-tool user create employee "$(cat /opt/domain-test/user.secret)"
    systemctl unmask samba-ad-dc
    systemctl start samba-ad-dc
    echo 'PASS AD test controller ready'
    sleep 1500
else
    apt-get install -y -qq realmd adcli sssd-ad sssd-tools libnss-sss libpam-sss samba-common-bin packagekit pamtester python3-dbus dnsutils xdotool
    hostnamectl set-hostname brclient
    echo '192.168.76.20 brclient.lab.example.test brclient' >>/etc/hosts
    useradd -m -s /bin/bash -G sudo localadmin
    echo "localadmin:$(cat /opt/domain-test/local.secret)" | chpasswd
    pam-auth-update --package --enable mkhomedir
    systemctl stop systemd-resolved || true
    rm -f /etc/resolv.conf
    printf 'nameserver 192.168.76.10\nsearch lab.example.test\n' >/etc/resolv.conf
    for i in $(seq 1 120); do dig +short @192.168.76.10 _ldap._tcp.lab.example.test SRV | grep -q dc1 && break; sleep 5; done
    if [[ -f /opt/domain-test/graphical.py ]]; then
        mkdir -p /mnt/control
        mount -t 9p -o trans=virtio,version=9p2000.L control /mnt/control
    fi
    python3 /opt/domain-test/check.py
fi
