import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog
from pystray import Icon as TrayIcon, MenuItem, Menu
from PIL import Image, ImageDraw
import threading
import re
import winreg
import time
import glob

# --- 基礎路徑設定 ---
def get_base_dir():
    return os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath(os.path.dirname(__file__))

def fix_path(path):
    return path.replace("\\", "/")

BASE_DIR = get_base_dir()
APACHE_DIR = os.path.join(BASE_DIR, "apache2")
CONF_FILE = os.path.join(APACHE_DIR, "conf", "httpd.conf")
APACHE_EXE = os.path.join(APACHE_DIR, "bin", "httpd.exe")

# 預設值 (如果讀不到 Config 時使用)
DEFAULT_PHP_DIR = os.path.join(BASE_DIR, "php")
DEFAULT_WWW_DIR = os.path.join(BASE_DIR, "www")
DEFAULT_PORT = "80"

# --- 核心邏輯區 ---

def find_php_dll(php_path):
    """在指定的 PHP 資料夾中尋找 Apache DLL"""
    if not os.path.exists(php_path):
        return None
    # 優先尋找 php8apache2_4.dll, 接著是 php7... 或是萬用字元
    patterns = ["php*apache*.dll"]
    for pattern in patterns:
        dlls = glob.glob(os.path.join(php_path, pattern))
        if dlls:
            return dlls[0]
    return None

def read_config_status():
    """讀取 httpd.conf 目前的設定值"""
    config = {
        "port": DEFAULT_PORT,
        "php_dir": DEFAULT_PHP_DIR,
        "www_dir": DEFAULT_WWW_DIR
    }
    
    if not os.path.exists(CONF_FILE):
        return config

    with open(CONF_FILE, "r", encoding="utf-8") as f:
        content = f.read()

        # 讀取 Port
        m_port = re.search(r"(?i)^Listen\s+(\d+)", content, re.MULTILINE)
        if m_port: config["port"] = m_port.group(1)

        # 讀取 PHPDir
        m_php = re.search(r'(?i)^PHPIniDir\s+"(.*?)"', content, re.MULTILINE)
        if m_php: config["php_dir"] = os.path.normpath(m_php.group(1))

        # 讀取 WWW Dir (DocumentRoot)
        m_www = re.search(r'(?i)^DocumentRoot\s+"(.*?)"', content, re.MULTILINE)
        if m_www: config["www_dir"] = os.path.normpath(m_www.group(1))
        
    return config

def save_and_apply_config(new_port, new_php_dir, new_www_dir):
    """寫入設定並重啟 Apache"""
    if not os.path.exists(CONF_FILE):
        messagebox.showerror("錯誤", f"找不到設定檔: {CONF_FILE}")
        return False

    # 驗證 PHP DLL 是否存在
    php_dll = find_php_dll(new_php_dir)
    if not php_dll:
        messagebox.showerror("設定錯誤", f"在選定的 PHP 資料夾中找不到 Apache DLL (php*apache*.dll)\n路徑: {new_php_dir}")
        return False

    try:
        with open(CONF_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # 準備替換的內容
        # 1. Port
        content = re.sub(r"(?i)^Listen\s+\d+", f"Listen {new_port}", content, flags=re.MULTILINE)
        
        # 2. ServerRoot (保持不變或強制修正為當前 Apache 目錄)
        content = re.sub(r'(?i)^(\s*ServerRoot\s+).*', f'ServerRoot "{fix_path(APACHE_DIR)}"', content, flags=re.MULTILINE)

        # 3. PHP 設定
        # 如果原本沒有 PHP 設定，附加在後面；如果有，則替換
        php_ini_pattern = r'(?i)^\s*PHPIniDir\s+".*"'
        load_mod_pattern = r'(?i)^\s*LoadModule\s+php_module\s+".*"'
        
        if re.search(php_ini_pattern, content, re.MULTILINE):
            content = re.sub(php_ini_pattern, f'PHPIniDir "{fix_path(new_php_dir)}"', content, flags=re.MULTILINE)
        else:
            content += f'\nPHPIniDir "{fix_path(new_php_dir)}"'

        if re.search(load_mod_pattern, content, re.MULTILINE):
            content = re.sub(load_mod_pattern, f'LoadModule php_module "{fix_path(php_dll)}"', content, flags=re.MULTILINE)
        else:
            content += f'\nLoadModule php_module "{fix_path(php_dll)}"'

        # 4. WWW 設定 (DocumentRoot & Directory)
        doc_root_pattern = r'(?i)^\s*DocumentRoot\s+".*"'
        dir_pattern = r'(?i)^\s*<Directory\s+".*?">' # 假設 Directory 標籤指向 www
        
        # 替換 DocumentRoot
        content = re.sub(doc_root_pattern, f'DocumentRoot "{fix_path(new_www_dir)}"', content, flags=re.MULTILINE)
        
        # 替換 <Directory "..."> 
        # 注意：這裡使用簡單的正則替換所有包含 www 路徑的 Directory 標籤，可能會比較暴力，建議確保 httpd.conf 結構單純
        # 這裡我們針對舊路徑或常見結構做替換
        content = re.sub(r'(?i)<Directory\s+"[^"]+www[^"]*">', f'<Directory "{fix_path(new_www_dir)}">', content)
        # 如果上面沒抓到 (例如路徑已經被改過)，嘗試抓 DocumentRoot 下一行的 Directory
        # 為了保險，我們搜尋特定的權限區塊設定
        
        # 更穩健的做法：如果找不到特定的 Directory 標籤，我們就不改 Directory 權限部分，只改 DocumentRoot
        # 但通常 DocumentRoot 和 Directory 是成對的。這裡為了 UI 功能，我們強制寫入一個針對新 WWW 的 Directory 區塊 (如果不在乎重複)
        # 或者，使用簡單的替換邏輯：
        old_www_pattern = r'(?i)<Directory\s+"(.*?)">'
        match = re.search(old_www_pattern, content)
        if match:
             # 這是一個簡化處理，假設第一個主要的 Directory 設定就是 WebRoot
             # 為了精確，建議 httpd.conf 裡面保留註解標記，但這裡我們用正則覆蓋
             pass 
        
        # 為了確保 Directory 權限正確，直接替換 DocumentRoot 對應的 Directory 比較困難
        # 這裡採用 "尋找並取代" 整個區塊的策略比較複雜。
        # 替代方案：我們只替換 DocumentRoot，並假設使用者知道 <Directory> 權限設定，
        # 或者我們強制替換所有 <Directory "舊路徑"> 為 <Directory "新路徑">
        
        # 簡單暴力法：讀取當前設定中的 www_dir，將文件中所有該路徑替換為新路徑
        current_conf = read_config_status()
        old_www = current_conf['www_dir']
        # 將文件中所有出現的舊路徑 (fix_path 格式) 換成新路徑
        content = content.replace(fix_path(old_www), fix_path(new_www_dir))
        # 也要處理反斜線格式，以防萬一
        content = content.replace(old_www.replace("/", "\\"), fix_path(new_www_dir))

        with open(CONF_FILE, "w", encoding="utf-8") as f:
            f.write(content)
            
        # 重啟 Apache
        stop_apache()
        start_apache()
        return True

    except Exception as e:
        messagebox.showerror("錯誤", f"儲存設定失敗: {e}")
        return False

def is_apache_running():
    try:
        output = subprocess.check_output("tasklist", shell=True).decode(errors='ignore')
        return "httpd.exe" in output
    except:
        return False

def start_apache():
    if not os.path.exists(APACHE_EXE):
        return
    if is_apache_running():
        return
    try:
        subprocess.Popen([APACHE_EXE], cwd=APACHE_DIR,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except Exception as e:
        messagebox.showerror("錯誤", f"無法啟動 Apache：\n{e}")

def stop_apache(force_ensure=True):
    try:
        subprocess.call("taskkill /f /im httpd.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if force_ensure:
            for _ in range(5):
                time.sleep(0.5)
                try:
                    output = subprocess.check_output("tasklist", shell=True).decode(errors='ignore')
                    if "httpd.exe" not in output: return
                    subprocess.call("taskkill /f /im httpd.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except: pass
    except: pass

def set_autostart(enabled):
    key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    name = "ApacheGUI"
    exe_path = sys.executable
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_ALL_ACCESS) as regkey:
            if enabled:
                winreg.SetValueEx(regkey, name, 0, winreg.REG_SZ, exe_path)
            else:
                try: winreg.DeleteValue(regkey, name)
                except FileNotFoundError: pass
    except FileNotFoundError:
        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as regkey:
                winreg.SetValueEx(regkey, name, 0, winreg.REG_SZ, exe_path)
    except Exception as e:
        messagebox.showerror("錯誤", f"設定自動啟動失敗：\n{e}")

def is_autostart_enabled():
    key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    name = "ApacheGUI"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as regkey:
            winreg.QueryValueEx(regkey, name)
            return True
    except: return False

# --- GUI 介面邏輯 ---

def create_icon(show_window_func, exit_func):
    img = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([8, 8, 56, 56], outline="black", width=4)
    draw.text((20, 22), "SRV", fill="black") # 更改 Icon 文字區別
    menu = Menu(
        MenuItem("控制面板", lambda icon, item: show_window_func()),
        MenuItem("重啟 Apache", lambda icon, item: (stop_apache(), start_apache())),
        MenuItem("退出", lambda icon, item: exit_func())
    )
    return TrayIcon("Apache Manager", img, menu=menu)

def browse_folder(entry_var):
    path = filedialog.askdirectory()
    if path:
        entry_var.set(os.path.normpath(path))

def run_gui():
    # 初始化確保路徑正確 (首次運行)
    if not os.path.exists(CONF_FILE):
        # 如果沒有 conf，這裡可以加入初始化邏輯，目前省略
        pass
    
    start_apache()

    root = tk.Tk()
    root.title("Apache 環境控制台")
    root.geometry("450x350")
    root.resizable(False, False)
    
    # 當點擊關閉視窗時，只隱藏不退出
    root.protocol("WM_DELETE_WINDOW", lambda: root.withdraw())
    root.withdraw() # 初始隱藏

    # 讀取當前設定
    current_config = read_config_status()
    
    # UI 變數
    var_php_dir = tk.StringVar(value=current_config["php_dir"])
    var_www_dir = tk.StringVar(value=current_config["www_dir"])
    var_port = tk.StringVar(value=current_config["port"])
    var_autostart = tk.BooleanVar(value=is_autostart_enabled())

    # --- UI 排版 ---
    pad_opts = {'padx': 10, 'pady': 5}
    
    # 1. PHP 資料夾區塊
    grp_php = tk.LabelFrame(root, text="PHP 版本目錄", padx=5, pady=5)
    grp_php.pack(fill="x", **pad_opts)
    
    tk.Entry(grp_php, textvariable=var_php_dir).pack(side="left", fill="x", expand=True)
    tk.Button(grp_php, text="瀏覽...", command=lambda: browse_folder(var_php_dir)).pack(side="right", padx=5)

    # 2. WWW 資料夾區塊
    grp_www = tk.LabelFrame(root, text="WWW 網站根目錄", padx=5, pady=5)
    grp_www.pack(fill="x", **pad_opts)
    
    tk.Entry(grp_www, textvariable=var_www_dir).pack(side="left", fill="x", expand=True)
    tk.Button(grp_www, text="瀏覽...", command=lambda: browse_folder(var_www_dir)).pack(side="right", padx=5)

    # 3. Port 設定
    grp_port = tk.Frame(root)
    grp_port.pack(fill="x", **pad_opts)
    tk.Label(grp_port, text="Apache Port:").pack(side="left")
    tk.Entry(grp_port, textvariable=var_port, width=10).pack(side="left", padx=5)

    # 4. 操作按鈕
    def on_save():
        p_dir = var_php_dir.get()
        w_dir = var_www_dir.get()
        port = var_port.get()
        
        if not port.isdigit():
            messagebox.showerror("錯誤", "Port 必須是數字")
            return

        if save_and_apply_config(port, p_dir, w_dir):
            status_label.config(text=f"狀態: 已更新設定並重啟 (Port: {port})", fg="green")
            messagebox.showinfo("成功", "設定已儲存，Apache 已重新啟動。")
        else:
            status_label.config(text="狀態: 設定更新失敗", fg="red")

    btn_save = tk.Button(root, text="儲存設定並重啟 Apache", command=on_save, bg="#dddddd", height=2)
    btn_save.pack(fill="x", padx=20, pady=10)

    # 5. 自動啟動
    chk_auto = tk.Checkbutton(root, text="開機自動啟動本程式", variable=var_autostart,
                         command=lambda: set_autostart(var_autostart.get()))
    chk_auto.pack(pady=5)

    # 6. 狀態列
    status_label = tk.Label(root, text=f"目前 Port: {current_config['port']}", fg="blue")
    status_label.pack(side="bottom", pady=5)

    # --- System Tray ---
    def show_window():
        # 每次開啟視窗時，重新讀取設定檔顯示，確保狀態同步
        curr = read_config_status()
        var_php_dir.set(curr["php_dir"])
        var_www_dir.set(curr["www_dir"])
        var_port.set(curr["port"])
        status_label.config(text=f"目前 Port: {curr['port']}", fg="blue")
        
        root.deiconify()
        root.lift()

    def exit_app():
        stop_apache(force_ensure=True)
        tray_icon.stop()
        root.destroy()

    tray_icon = create_icon(show_window, exit_app)
    threading.Thread(target=tray_icon.run, daemon=True).start()
    
    root.mainloop()

if __name__ == "__main__":
    run_gui()
