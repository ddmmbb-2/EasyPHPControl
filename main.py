import os
import sys
import json
import subprocess
import threading
import time
import re
import webview
import tkinter as tk
from tkinter import filedialog
from flask import Flask, render_template, jsonify, request

# --- 路徑配置 ---
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.dirname(__file__))

BASE_DIR = get_base_dir()
APACHE_DIR = os.path.join(BASE_DIR, "apache2")
CONF_FILE = os.path.join(APACHE_DIR, "conf", "httpd.conf")
VHOST_CONF_FILE = os.path.join(APACHE_DIR, "conf", "extra", "httpd-vhosts.conf")
BIN_DIR = os.path.join(APACHE_DIR, "bin")
APACHE_EXE = os.path.join(BIN_DIR, "httpd.exe")
WACS_EXE = os.path.join(BASE_DIR, "tools", "wacs.exe")
SITES_DB = os.path.join(BASE_DIR, "sites.json")

# --- Flask 初始化 ---
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

class SystemManager:
    @staticmethod
    def is_apache_running():
        try:
            output = subprocess.check_output("tasklist", shell=True).decode(errors='ignore')
            return "httpd.exe" in output
        except:
            return False

    @staticmethod
    def toggle_apache(action):
        try:
            if action == "start":
                if not SystemManager.is_apache_running():
                    subprocess.Popen([APACHE_EXE], cwd=APACHE_DIR, creationflags=subprocess.CREATE_NO_WINDOW)
            elif action == "stop":
                subprocess.call("taskkill /f /im httpd.exe", shell=True)
            elif action == "restart":
                SystemManager.toggle_apache("stop")
                time.sleep(1.5) # 稍微延長等待時間確保 Port 釋放
                SystemManager.toggle_apache("start")
            return True
        except Exception as e:
            print(f"Apache 操作失敗: {e}")
            return False

class VHostManager:
    @staticmethod
    def load_sites():
        if not os.path.exists(SITES_DB): return []
        try:
            with open(SITES_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []

    @staticmethod
    def save_sites(sites):
        with open(SITES_DB, 'w', encoding='utf-8') as f:
            json.dump(sites, f, indent=4, ensure_ascii=False)
        VHostManager.generate_config(sites)

    @staticmethod
    def generate_config(sites):
        config_content = "# 由 ApacheManager 自動生成，請勿手動修改\n\n"
        
        # 修正 1: 處理唯一 Port 監聽
        unique_ports = {int(site.get('port', 80)) for site in sites if site.get('port')}
        for port in sorted(unique_ports):
            config_content += f"Listen {port}\n"
        config_content += "\n"

        for site in sites:
            domain = site.get('domain', 'localhost')
            port = site.get('port', 80)
            # 修正 2: 路徑斜線轉換
            target = site.get('target', '').replace('\\', '/')
            sType = site.get('type', 'dir')

            config_content += f"<VirtualHost *:{port}>\n"
            config_content += f"    ServerName {domain}\n"
            
            if sType == 'proxy':
                config_content += "    ProxyPreserveHost On\n"
                config_content += "    ProxyRequests Off\n"
                # 確保 Proxy 目標有 http://
                proxy_target = target if target.startswith('http') else f"http://{target}"
                config_content += f"    ProxyPass / {proxy_target}/\n"
                config_content += f"    ProxyPassReverse / {proxy_target}/\n"
            else:
                config_content += f"    DocumentRoot \"{target}\"\n"
                config_content += f"    <Directory \"{target}\">\n"
                config_content += "        Options Indexes FollowSymLinks\n"
                config_content += "        AllowOverride All\n"
                config_content += "        Require all granted\n"
                config_content += "    </Directory>\n"
            
            config_content += "</VirtualHost>\n\n"

        os.makedirs(os.path.dirname(VHOST_CONF_FILE), exist_ok=True)
        with open(VHOST_CONF_FILE, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        SystemManager.toggle_apache("restart")

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    return jsonify({"running": SystemManager.is_apache_running()})

@app.route('/api/control', methods=['POST'])
def control_apache():
    action = request.json.get('action')
    SystemManager.toggle_apache(action)
    return jsonify({"status": "ok"})

@app.route('/api/sites', methods=['GET', 'POST'])
def manage_sites():
    if request.method == 'GET':
        return jsonify(VHostManager.load_sites())
    else:
        sites = request.json
        VHostManager.save_sites(sites)
        return jsonify({"status": "saved"})

@app.route('/api/browse', methods=['GET'])
def browse_folder():
    try:
        root = tk.Tk()
        root.withdraw()
        root.wm_attributes('-topmost', 1)
        root.focus_force() # 確保視窗跳出
        folder_path = filedialog.askdirectory()
        root.destroy()
        return jsonify({'path': folder_path if folder_path else ''})
    except Exception as e:
        return jsonify({'path': '', 'error': str(e)})

@app.route('/api/ssl', methods=['POST'])
def apply_ssl():
    # SSL 邏輯維持原樣，但建議實務上提醒使用者 wacs.exe 需要管理員權限
    data = request.json
    result = VHostManager.run_ssl_request(data['domain'], data['email'])
    return jsonify({"result": result})

def start_app():
    # 使用 debug=True 可以在開發時看到網頁 console 報錯
    webview.create_window('Apache 管理員 (WebUI)', app, width=1000, height=750)
    webview.start()

if __name__ == '__main__':
    start_app()