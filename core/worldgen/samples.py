"""core.worldgen.samples — mondes/missions d'exemple codés en dur.

Utilisés par ``dev_tools/world_editor_gui.py`` (bouton « Sample ») pour démarrer
depuis un monde minimaliste mais réaliste. Extraits du fichier GUI lors du
refactor pour alléger ce dernier. Purement des factories de dict.
"""
from __future__ import annotations

from typing import Any, Dict

from core.worldgen._impl import _now_ts


def make_sample_world(seed: int = 123) -> Dict[str, Any]:
    return {
        "schema": "world_v2",
        "seed": int(seed),
        "generated_at": _now_ts(),
        "regions": [{"region_id": "eu", "name": "EU"}],
        "targets": [
            {
                "target_id": "t_coffee_001",
                "type": "public_wifi",
                "name": "Café Aurora",
                "region_id": "eu",
                "networks": [
                    {
                        "network_id": "wifi_guest",
                        "type": "wifi_public",
                        "ssid": "Aurora_Free_WiFi",
                        "security": "open",
                        "clients": [
                            {"device_id": "ph_01", "kind": "smartphone", "owner": "guest", "os": "Android"},
                            {"device_id": "lp_01", "kind": "laptop", "owner": "guest", "os": "Windows"},
                        ],
                    }
                ],
                "hosts": [
                    {
                        "host_id": "wifi_guest:ap",
                        "network_id": "wifi_guest",
                        "ip": "10.42.0.1",
                        "hostname": "ap-aurora",
                        "os": "OpenWRT",
                        "services": [
                            {"port": 80, "name": "http", "version": "uhttpd_1.0", "vuln_tags": ["rce_http"]},
                            {"port": 22, "name": "ssh", "version": "OpenSSH_8.2", "vuln_tags": ["bruteforce"]},
                        ],
                        "os_model": {
                            "users": ["root", "admin"],
                            "files": {
                                "/etc/config/wireless": "config wifi-iface\n\toption ssid 'Aurora_Free_WiFi'\n",
                                "/home/admin/notes.txt": "todo: change router password\n",
                            },
                            "suid_bins": ["/usr/bin/busybox"],
                        },
                    }
                ],
            },
            {
                "target_id": "t_company_001",
                "type": "company",
                "name": "Northwind Dynamics",
                "region_id": "eu",
                "networks": [
                    {"network_id": "lan", "type": "lan"},
                    {"network_id": "wifi_staff", "type": "wifi_private", "ssid": "ND-STAFF", "security": "wpa2"},
                ],
                "hosts": [
                    {
                        "host_id": "lan:0",
                        "network_id": "lan",
                        "ip": "10.0.0.10",
                        "hostname": "git",
                        "os": "Debian",
                        "services": [
                            {"port": 22, "name": "ssh", "version": "OpenSSH_9.0", "vuln_tags": ["bruteforce"]},
                            {"port": 80, "name": "http", "version": "nginx_1.22", "vuln_tags": []},
                        ],
                        "os_model": {
                            "users": ["root", "dev", "git"],
                            "files": {
                                "/srv/git/README.md": "# Northwind Dynamics repos\n",
                                "/home/dev/flag.txt": "FLAG{northwind_onboarding_001}",
                                "/home/dev/finance_report_2025.txt": "CONFIDENTIAL\nRevenue: ...\n",
                                "/home/dev/.nxc/wallet.key": "WALLET_KEY\ncurrency=NXC\naddress=0xSAMPLE001\nprivate_key=ENCRYPTED_T_COMPANY_001_W00\n",
                            },
                            "suid_bins": ["/usr/bin/find"],
                        },
                    }
                ],
                "crypto_wallets": [
                    {
                        "wallet_id": "t_company_001_w00",
                        "currency": "NXC",
                        "balance": 2500,
                        "address": "0xSAMPLE001",
                        "security": "medium",
                        "key_file": "/home/dev/.nxc/wallet.key",
                    }
                ],
            },
            {
                "target_id": "t_bank_001",
                "type": "bank",
                "name": "Northwind Bank",
                "region_id": "eu",
                "networks": [
                    {"network_id": "bank_lan", "type": "lan"},
                ],
                "hosts": [
                    {
                        "host_id": "bank_lan:0",
                        "network_id": "bank_lan",
                        "ip": "10.20.0.10",
                        "hostname": "core-banking",
                        "os": "Debian",
                        "services": [
                            {"port": 22, "name": "ssh", "version": "OpenSSH_9.0", "vuln_tags": ["bruteforce"]},
                            {"port": 8443, "name": "api", "version": "express_4.18", "vuln_tags": ["sqli"]},
                        ],
                        "os_model": {
                            "users": ["root", "dev", "banker"],
                            "files": {
                                "/srv/banking/accounts.csv": "id,holder,balance\n1,SAMPLE_CLIENT,99999\n",
                                "/home/dev/treasury_report.txt": "TREASURY REPORT\nRef: FIN-00001\n",
                                "/home/dev/.btc/wallet.key": "WALLET_KEY\ncurrency=BTC\naddress=0xBANK001\nprivate_key=ENCRYPTED_T_BANK_001_W00\n",
                            },
                            "suid_bins": ["/usr/bin/find"],
                        },
                    }
                ],
                "crypto_wallets": [
                    {
                        "wallet_id": "t_bank_001_w00",
                        "currency": "BTC",
                        "balance": 18500,
                        "address": "0xBANK001",
                        "security": "elite",
                        "key_file": "/home/dev/.btc/wallet.key",
                    }
                ],
            },
        ],
    }


def make_sample_missions(seed: int = 123) -> Dict[str, Any]:
    return {
        "schema": "missions_v2",
        "seed": int(seed),
        "missions": [
            {
                "mission_id": "m000",
                "title": "Recon: Aurora Free WiFi",
                "network_id": "wifi_guest",
                "objective": {"type": "scan_network", "network_id": "wifi_guest", "min_hosts": 1},
                "reward": {"money": 120},
            },
            {
                "mission_id": "m001",
                "title": "Loot: Northwind flag",
                "network_id": "lan",
                "objective": {"type": "loot_file", "host_id": "lan:0", "path": "/home/dev/flag.txt"},
                "reward": {"money": 260},
            },
        ],
    }
