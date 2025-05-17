import subprocess
import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
import sys
import traceback
import locale # 未使用到，但保留

# --- 設定、語系和日誌變數 ---
# config 將只存放 "settings" 部分的內容
config = {}
# all_languages 將存放 "languages" 部分的內容
all_languages = {}
# lang 將存放當前選定語系具體的翻譯字典
lang = {}

server_process = None
log_file_handle = None
log_file_path = 'server.log'

DEBUG = True

def debug_print(*args, **kwargs):
    """條件式偵錯輸出"""
    if DEBUG:
        print("DEBUG:", *args, **kwargs)

# --- 語系文字取得函數 ---
def t(key, default=''):
    """根據 key 取得當前語系的文字，如果 key 不存在則回傳預設文字。"""
    return lang.get(key, default)


# --- 配置和語系載入/儲存 (整併) ---
def load_config_and_languages():
    """從 config.json 載入配置、語系資料和當前語系設定。"""
    global config, all_languages, lang

    debug_print("Loading config and languages from config.json...")

    full_data = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                full_data = json.load(f)
            debug_print("config.json loaded successfully.")
        except json.JSONDecodeError:
            debug_print("config.json JSON decode error. Using default structure.")
            messagebox.showwarning(t("config_warning_title", "警告"), t("config_warning_json_error", "config.json 格式錯誤，將使用預設設定。"))
        except Exception as e:
             debug_print(f"Unexpected error loading config.json: {e}")
             traceback.print_exc()
             messagebox.showerror(t("config_error_title", "錯誤"), t("config_error_load", f"載入設定檔失敗：\n{e}"))

    # 從載入的資料中提取 settings 和 languages
    config = full_data.get("settings", {}) # 如果沒有 "settings" Key，給予空字典
    all_languages = full_data.get("languages", {}) # 如果沒有 "languages" Key，給予空字典

    # 設定 config 的預設值，確保 key 存在
    config.setdefault("php_path", "./php/php.exe")
    config.setdefault("www_path", "./www")
    config.setdefault("port", 8080)
    # 新增：設定預設語系代碼，預設是 'zh-TW'
    config.setdefault("current_language", "en")

    debug_print("Config settings loaded:", config)
    debug_print("Available languages loaded:", list(all_languages.keys()))

    # 載入當前語系 (使用 load_language 函數，它現在從 all_languages 獲取數據)
    # 如果 config 中的 current_language 不存在於 all_languages 中，load_language 會處理回退
    load_language(config.get("current_language", "en"))


def save_config_and_languages():
    """將當前配置、語系資料和當前語系設定儲存到 config.json。"""
    debug_print("Saving config and languages to config.json...")
    # 在儲存前，確保 config 中的 current_language 是當前實際載入的語系代碼
    # 找到當前 lang 字典對應的語系代碼
    current_lang_code = "zh-TW" # 預設值
    for code, lang_dict_item in all_languages.items():
         if lang_dict_item is lang:
              current_lang_code = code
              break
    config["current_language"] = current_lang_code

    # 構建完整的數據結構
    full_data = {
        "settings": config,
        "current_language": config.get("current_language", "zh-TW"), # 也可以直接從 config 讀取
        "languages": all_languages
    }

    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=4)
        debug_print("config.json saved successfully.")
    except Exception as e:
        debug_print(f"Error saving config.json: {e}")
        traceback.print_exc()
        messagebox.showerror(t("config_error_title", "錯誤"), t("config_error_save", f"儲存設定檔失敗：\n{e}"))


# --- 語系載入函數 (修改為從全域變數 all_languages 載入) ---
def load_language(lang_code='zh-TW'):
    """
    從全域變數 all_languages 中載入指定語系到全域變數 lang。
    如果找不到語系，會顯示警告並嘗試回退。
    """
    global lang, all_languages
    debug_print(f"Setting current language to: {lang_code}")
    if not all_languages:
        debug_print("all_languages is empty, cannot load any language.")
        lang = {} # 沒有可用語系，使用空字典
        # 不彈出錯誤，因為 load_config_and_languages 會處理 lang.json 載入失敗的情況
        return

    if lang_code in all_languages:
        lang = all_languages[lang_code]
        debug_print(f"Language '{lang_code}' set successfully.")
    else:
        debug_print(f"Language code '{lang_code}' not found in all_languages.")
        # 找不到指定語系，嘗試回退到一個存在的語系
        if all_languages:
            first_code = list(all_languages.keys())[0]
            lang = all_languages[first_code]
            debug_print(f"Set fallback language: {first_code}")
            messagebox.showwarning(t("lang_load_warning_title", "語系載入警告"),
                                   t("lang_code_not_found", f"找不到語系 '{lang_code}'，已載入 '{first_code}'。",
                                     lang_code=lang_code, fallback_code=first_code)) # 使用 format 傳參數
        else:
            debug_print("all_languages is empty after check, cannot load any language.")
            lang = {} # 沒有可用語系，使用空字典


# --- 路徑選擇函數 (保持不變，替換 messagebox 文字為 t()) ---
def set_php_path():
    """開啟檔案選擇對話框設定 PHP 執行檔路徑。"""
    path = filedialog.askopenfilename(filetypes=[(t("php_exec_filetype", "PHP 執行檔"), "*.exe")], title=t("select_php_title", "選擇 PHP 執行檔"))
    if path:
        php_path_entry.delete(0, tk.END)
        php_path_entry.insert(0, path)
        debug_print(f"PHP path set to: {path}")

def set_www_path():
    """開啟資料夾選擇對話框設定網站根目錄。"""
    path = filedialog.askdirectory(title=t("select_www_title", "選擇網站根目錄"))
    if path:
        www_path_entry.delete(0, tk.END)
        www_path_entry.insert(0, path)
        debug_print(f"WWW path set to: {path}")

# --- 尋找和開啟 php.ini (保持不變，替換 messagebox 文字為 t()) ---
# ... (find_php_ini_path, open_php_ini 函數保持不變，已在之前版本中替換 t() ) ...
def find_php_ini_path(php_executable_path):
    debug_print(f"Attempting to find php.ini for: {php_executable_path}")

    if not php_executable_path or not os.path.exists(php_executable_path) or not os.path.isfile(php_executable_path):
        debug_print("PHP executable path is invalid or does not exist.")
        return None

    try:
        flags = 0
        if os.name == 'nt':
            flags = subprocess.CREATE_NO_WINDOW

        command = [php_executable_path, "-i"]
        debug_print(f"Running command: {command}")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True,
            creationflags=flags if os.name == 'nt' else 0
        )
        output = result.stdout
        debug_print("--- php -i Output (first 500 chars) ---")
        debug_print(output[:500] + ("..." if len(output) > 500 else ""))
        debug_print("----------------------------------------")

        ini_path = None

        for line in output.splitlines():
            stripped_line = line.strip()
            if stripped_line.startswith("Loaded Configuration File =>"):
                ini_path = stripped_line.split("=>", 1)[1].strip()
                debug_print(f"Potential INI path found: {ini_path}")
                break

        if ini_path and os.path.exists(ini_path) and os.path.isfile(ini_path):
            debug_print(f"Validated INI path: {ini_path}")
            return ini_path
        else:
            debug_print(f"INI path '{ini_path}' is invalid or not a file.")
            return None

    except FileNotFoundError:
        debug_print(f"Error: PHP executable not found by subprocess at {php_executable_path}")
        messagebox.showerror(t("error_title", "錯誤"), t("error_php_not_found_run_i", f"找不到 PHP 執行檔：\n{php_executable_path}"))
        return None
    except subprocess.CalledProcessError as e:
        debug_print(f"Error executing PHP: Return Code {e.returncode}")
        debug_print(f"Stderr: {e.stderr}")
        messagebox.showerror(t("error_title", "錯誤"), t("error_php_i_failed", f"執行 PHP 失敗 (返回碼 {e.returncode}):\n{e.stderr}\n請確認 PHP 執行檔是否正常。"))
        return None
    except Exception as e:
        debug_print(f"Unexpected error in find_php_ini_path: {e}")
        traceback.print_exc()
        messagebox.showerror(t("error_title", "錯誤"), t("error_parse_php_i", f"解析 php -i 輸出時發生錯誤：\n{e}"))
        return None


def open_php_ini():
    debug_print("Open php.ini button clicked.")
    php_path = php_path_entry.get()
    if not php_path:
        messagebox.showwarning(t("info_title", "提示"), t("info_select_php_first", "請先選擇 PHP 執行檔路徑。"))
        debug_print("No PHP path entered.")
        return

    debug_print(f"PHP path from entry: {php_path}")

    ini_path = find_php_ini_path(php_path)

    if ini_path:
        debug_print(f"INI path found by find_php_ini_path: {ini_path}")
        try:
            debug_print(f"Attempting to open file: {ini_path}")
            if sys.platform.startswith('win'):
                os.startfile(ini_path)
            elif sys.platform.startswith('darwin'):
                subprocess.run(['open', ini_path], check=True)
            else:
                subprocess.run(['xdg-open', ini_path], check=True)
            debug_print("File open command executed.")

        except Exception as e:
            debug_print(f"Error opening file: {e}")
            traceback.print_exc()
            messagebox.showerror(t("error_title", "錯誤"), t("error_open_ini", f"無法打開 php.ini 檔案：\n{ini_path}\n錯誤訊息：{e}"))
    else:
        debug_print("find_php_ini_path returned None or encountered an error already handled.")
        messagebox.showinfo(t("info_title", "資訊"), t("info_ini_not_found", "找不到 php.ini 檔案，或 PHP 未載入有效的設定檔。請確認 PHP 執行檔路徑是否正確。"))


# --- 更新配置從 Entry ---
def update_config_from_entries():
    """從 GUI 輸入框讀取值，更新配置 (settings 部分)。"""
    debug_print("Updating config from entries...")
    # 直接修改 config 字典，因為它是全域變數
    config["php_path"] = php_path_entry.get()
    config["www_path"] = www_path_entry.get()
    try:
        # 這裡只更新 config 變數，儲存是在 start_server 和 switch_language 中呼叫 save_config_and_languages
        port_value = int(port_entry.get())
        if not 1 <= port_value <= 65535:
             messagebox.showerror(t("error_title", "錯誤"), t("error_invalid_port_range", "請輸入有效的埠號 (1-65535)"))
             debug_print(f"Invalid port range entered: {port_value}")
             return False
        config["port"] = port_value
        debug_print(f"Port set to: {port_value}")
    except ValueError:
        messagebox.showerror(t("error_title", "錯誤"), t("error_invalid_port_format", "請輸入有效的埠號 (數字)"))
        debug_print(f"Invalid port format entered: {port_entry.get()}")
        return False

    # 在啟動或切換語系時統一儲存
    # save_config_and_languages()
    return True

# --- 啟動伺服器 ---
def start_server():
    """啟動 PHP 內建伺服器並將輸出導向日誌檔案。"""
    global server_process, log_file_handle

    debug_print("Attempting to start server...")

    # 1. 從 Entry 更新 config 變數 (settings 部分)
    if not update_config_from_entries():
        debug_print("Config update failed, not starting server.")
        return

    # 2. 儲存最新的配置到檔案 (包含 settings 和 languages)
    save_config_and_languages() # 在啟動前儲存一次最新設定


    if server_process and server_process.poll() is None:
         messagebox.showinfo(t("info_title", "資訊"), t("info_server_already_running", "伺服器已在運行中。"))
         debug_print("Server is already running.")
         return

    # 使用更新後的 config 變數中的值
    php_path = os.path.abspath(config.get("php_path", ""))
    doc_root = os.path.abspath(config.get("www_path", ""))
    port = str(config.get("port", 8080))

    # 檢查路徑有效性
    if not os.path.exists(php_path):
        messagebox.showerror(t("error_title", "錯誤"), t("error_php_not_found", f"找不到 PHP 執行檔：\n{php_path}"))
        status_label.config(text=t("status_start_failed", "🛑 伺服器啟動失敗"), foreground="red")
        debug_print(f"PHP executable not found: {php_path}")
        return
    if not os.path.isfile(php_path):
         messagebox.showerror(t("error_title", "錯誤"), t("error_php_not_file", f"PHP 路徑必須指向一個執行檔：\n{php_path}"))
         status_label.config(text=t("status_start_failed", "🛑 伺服器啟動失敗"), foreground="red")
         debug_print(f"PHP path is not a file: {php_path}")
         return

    if not os.path.exists(doc_root):
        messagebox.showerror(t("error_title", "錯誤"), t("error_www_not_found", f"找不到網站根目錄：\n{doc_root}"))
        status_label.config(text=t("status_start_failed", "🛑 伺服器啟動失敗"), foreground="red")
        debug_print(f"Document root not found: {doc_root}")
        return
    if not os.path.isdir(doc_root):
         messagebox.showerror(t("error_title", "錯誤"), t("error_www_not_dir", f"網站根目錄必須指向一個資料夾：\n{doc_root}"))
         status_label.config(text=t("status_start_failed", "🛑 伺服器啟動失敗"), foreground="red")
         debug_print(f"Document root is not a directory: {doc_root}")
         return

    try:
        # 開啟日誌檔案
        try:
            log_file_handle = open(log_file_path, 'a', encoding='utf-8', buffering=1)
            debug_print(f"Log file opened: {log_file_path}")
        except IOError as e:
            messagebox.showerror(t("error_title", "錯誤"), t("error_log_open", f"無法打開或建立日誌檔案：\n{log_file_path}\n錯誤訊息：{e}"))
            status_label.config(text=t("status_start_failed", "🛑 伺服器啟動失敗"), foreground="red")
            debug_print(f"Failed to open log file: {log_file_path}, error: {e}")
            return

        flags = 0
        if os.name == 'nt':
            flags = subprocess.CREATE_NO_WINDOW

        debug_print(f"Starting server with command: [{php_path}, -S, 0.0.0.0:{port}, -t, {doc_root}]")
        server_process = subprocess.Popen(
            [php_path, "-S", f"0.0.0.0:{port}", "-t", doc_root],
            creationflags=flags if os.name == 'nt' else 0,
            stdout=log_file_handle,
            stderr=subprocess.STDOUT
        )
        debug_print(f"Server process started with PID: {server_process.pid}")

        status_label.config(text=t("status_running", "✅ 伺服器運行中："), foreground="green")
        url = f"http://localhost:{port}/"
        url_label.config(text=url, foreground="blue", cursor="hand2")
        url_label.unbind("<Button-1>")
        url_label.bind("<Button-1>", lambda e: webbrowser.open(url))
        debug_print(f"Server running at {url}")

        start_button.config(state=tk.DISABLED)
        stop_button.config(state=tk.NORMAL)

    except FileNotFoundError:
         messagebox.showerror(t("error_title", "啟動失敗"), t("error_php_not_found_start", f"找不到 PHP 執行檔，請檢查路徑是否正確：\n{php_path}"))
         status_label.config(text=t("status_start_failed", "🛑 伺服器啟動失敗"), foreground="red")
         url_label.config(text="", foreground="black", cursor="")
         url_label.unbind("<Button-1>")
         debug_print(f"FileNotFoundError when starting server for: {php_path}")
         if log_file_handle:
              try:
                   log_file_handle.close()
                   log_file_handle = None
                   debug_print("Log file closed due to start failure (FileNotFoundError).")
              except Exception as close_e:
                   debug_print(f"Error closing log file after FileNotFoundError: {close_e}")

    except Exception as e:
        debug_print(f"Error starting server: {e}")
        traceback.print_exc()
        messagebox.showerror(t("error_title", "啟動失敗"), t("error_start_generic", f"發生錯誤：\n{e}"))
        start_button.config(state=tk.NORMAL)
        stop_button.config(state=tk.DISABLED)
        status_label.config(text=t("status_start_failed", "🛑 伺服器啟動失敗"), foreground="red")
        url_label.config(text="", foreground="black", cursor="")
        url_label.unbind("<Button-1>")
        if log_file_handle:
              try:
                   log_file_handle.close()
                   log_file_handle = None
                   debug_print("Log file closed due to start failure (Generic Exception).")
              except Exception as close_e:
                   debug_print(f"Error closing log file after generic exception: {close_e}")


# --- 停止伺服器 ---
def stop_server():
    """停止正在運行的 PHP 內建伺服器。"""
    global server_process, log_file_handle

    if server_process:
        debug_print("Stopping server...")
        try:
            if os.name == 'nt':
                 server_process.terminate()
                 try:
                      server_process.wait(timeout=3)
                      debug_print("Server process terminated successfully.")
                 except subprocess.TimeoutExpired:
                      debug_print("Server process did not terminate within timeout, attempting kill...")
                      server_process.kill()
                      server_process.wait()
                      debug_print("Server process killed.")
            else:
                server_process.terminate()
                try:
                    server_process.wait(timeout=3)
                    debug_print("Server process terminated successfully.")
                except subprocess.TimeoutExpired:
                    debug_print("Server process did not terminate within timeout, attempting kill...")
                    server_process.kill()
                    server_process.wait()
                    debug_print("Server process killed.")

        except Exception as e:
             debug_print(f"Error stopping server process: {e}")
             traceback.print_exc()
             # 即使停止過程出錯，也嘗試關閉日誌檔案

        server_process = None
        debug_print("Server process handle cleared.")

    # 關閉日誌檔案句柄
    if log_file_handle:
         try:
             log_file_handle.close()
             log_file_handle = None
             debug_print("Log file handle closed.")
         except Exception as e:
             debug_print(f"Error closing log file: {e}")
             traceback.print_exc()

    status_label.config(text=t("status_stopped", "🛑 伺服器已停止"), foreground="red")
    url_label.config(text="", foreground="black", cursor="")
    url_label.unbind("<Button-1>")

    start_button.config(state=tk.NORMAL)
    stop_button.config(state=tk.DISABLED)
    debug_print("Stop server function finished.")

# --- 視窗關閉處理 ---
def on_closing():
    """處理視窗關閉事件，停止伺服器並退出。"""
    global server_process, log_file_handle
    debug_print("Window closing requested.")

    # 在退出前儲存一次當前配置和語系
    save_config_and_languages()
    debug_print("Config and languages saved on closing.")


    if server_process and server_process.poll() is None:
        if messagebox.askyesno(t("quit_title", "退出"), t("quit_confirm_running", "伺服器正在運行中，確定要停止並退出嗎？")):
            stop_server() # stop_server 會關閉日誌檔案
            debug_print("Server stopped, destroying window.")
            root.destroy()
        else:
            debug_print("Closing cancelled by user.")
    else:
        # 如果伺服器沒有運行，確保任何殘留的日誌檔案句柄也被關閉
        if log_file_handle:
             try:
                 log_file_handle.close()
                 log_file_handle = None
                 debug_print("Log file handle closed during on_closing (server not running).")
             except Exception as e:
                 debug_print(f"Error closing log file during on_closing: {e}")
                 traceback.print_exc()

        debug_print("Server not running, destroying window.")
        root.destroy()
        debug_print("Window destroyed.")

# --- 更新 GUI 文字函數 ---
def update_gui_texts():
    """根據當前載入的語系更新所有 GUI 元件的文字。"""
    # 需要確保這些 widget 變數已經被定義（在 GUI 建構部分）
    global root
    global php_path_label, www_path_label, port_label, language_label
    global start_button, stop_button, select_php_button, open_php_ini_button, select_www_button
    global status_label # status_label 的基礎文字需要更新
    global language_combobox # Combobox 的選項可能需要更新 (雖然這裡只更新文字)

    debug_print("Updating GUI texts...")

    root.title(t("title", "PHP 管理器"))

    # 更新固定標籤
    php_path_label.config(text=t("php_path_label", "PHP 路徑："))
    www_path_label.config(text=t("www_path_label", "網站根目錄："))
    port_label.config(text=t("port_label", "埠號："))
    language_label.config(text=t("language_label", "語系："))

    # 更新按鈕文字
    start_button.config(text=t("start_server", "▶️ 啟動伺服器"))
    stop_button.config(text=t("stop_server", "⏹️ 停止伺務器"))
    select_php_button.config(text=t("select_php", "選擇..."))
    open_php_ini_button.config(text=t("open_php_ini", "打開 php.ini"))
    select_www_button.config(text=t("select_www", "選擇..."))

    # 更新 Combobox 選項 (即使語系本身不變，這個列表是從 all_languages 來的)
    lang_codes = list(all_languages.keys())
    lang_codes.sort()
    # 保存當前選中的值
    current_selection = language_combobox.get()
    # 更新 Combobox 的值列表
    language_combobox.config(values=lang_codes)
    # 嘗試恢復之前的選擇，如果存在
    if current_selection in lang_codes:
        language_combobox.set(current_selection)
    elif lang_codes:
        language_combobox.set(lang_codes[0]) # 否則設置為第一個選項
    else:
         language_combobox.set("") # 如果沒有選項，設置為空

    # 更新狀態標籤 (僅基礎文字，運行/停止狀態會在 start/stop 函數中設定)
    # 這裡根據當前伺服器狀態重新設定一次文字，確保使用了新的語系
    if server_process and server_process.poll() is None:
         status_label.config(text=t("status_running", "✅ 伺服器運行中："))
    elif status_label.cget("text").startswith("🛑 自動啟動失敗") or status_label.cget("text") == t("status_auto_start_failed", "🛑 自動啟動失敗"): # 檢查原始 key 或當前文字
         status_label.config(text=t("status_auto_start_failed", "🛑 自動啟動失敗"))
    elif status_label.cget("text").startswith("🛑 伺服器已停止") or status_label.cget("text") == t("status_stopped", "🛑 伺服器已停止"):
         status_label.config(text=t("status_stopped", "🛑 伺服器已停止"))
    elif status_label.cget("text").startswith("🛑 伺服器啟動失敗") or status_label.cget("text") == t("status_start_failed", "🛑 伺服器啟動失敗"):
         status_label.config(text=t("status_start_failed", "🛑 伺服器啟動失敗"))
    else:
         status_label.config(text=t("status_not_started", "伺服器尚未啟動"))

    # URL 標籤是動態內容，不需要翻譯


# --- 語系切換處理函數 ---
def switch_language(event):
    """Combobox 選項改變時觸發，載入新語系並更新 GUI 和配置。"""
    selected_code = language_combobox.get()
    debug_print(f"Language selected from combobox: {selected_code}")

    # 1. 載入新語系到 lang
    load_language(selected_code)

    # 2. 更新 GUI 文字
    update_gui_texts()
    debug_print("Language switched and GUI texts updated.")

    # 3. 更新 config 中的 current_language 並儲存到檔案
    # config['current_language'] 已經在 load_config_and_languages 中定義預設值
    # switch_language 選擇新語系後，這個值會在 save_config_and_languages 時被更新並儲存
    # 所以這裡只需要呼叫儲存即可
    save_config_and_languages()
    debug_print("Config saved after language switch.")


# --- GUI 建構 ---

# 1. 在任何 GUI 元件創建之前，載入配置和語系
load_config_and_languages()

root = tk.Tk()
# 視窗標題將在 update_gui_texts() 中設定
root.resizable(False, False)

style = ttk.Style()
style.theme_use('clam')


# ==== 使用 grid 佈局管理器 ====
root.columnconfigure(1, weight=1)

current_row = 0 # 用於追蹤 grid 的行號

# --- 語系切換控制 ---
language_label = ttk.Label(root, text="") # 文字將由 update_gui_texts 設定
language_label.grid(row=current_row, column=0, padx=5, pady=5, sticky="w")

# Combobox 需要在載入 config 後才能獲取 values
lang_codes = list(all_languages.keys())
lang_codes.sort()
language_combobox = ttk.Combobox(root, values=lang_codes, state="readonly", width=15)
language_combobox.grid(row=current_row, column=1, padx=5, pady=5, sticky="w")

# 在 Combobox 創建後，設定初始顯示值
initial_lang_code = config.get("current_language", "zh-TW")
if initial_lang_code in lang_codes:
     language_combobox.set(initial_lang_code)
elif lang_codes:
     language_combobox.set(lang_codes[0])
else:
     language_combobox.set("") # 沒有可用語系

language_combobox.bind("<<ComboboxSelected>>", switch_language)
current_row += 1


# --- PHP 路徑選擇 ---
php_path_label = ttk.Label(root, text="") # 文字將由 update_gui_texts 設定
php_path_label.grid(row=current_row, column=0, padx=5, pady=5, sticky="w")
php_path_entry = ttk.Entry(root, width=50)
php_path_entry.insert(0, config.get("php_path", ""))
php_path_entry.grid(row=current_row, column=1, padx=5, pady=5, sticky="ew")

php_button_frame = ttk.Frame(root)
php_button_frame.grid(row=current_row, column=2, padx=5, pady=5, sticky="e")
select_php_button = ttk.Button(php_button_frame, text="", command=set_php_path) # 文字將由 update_gui_texts 設定
select_php_button.pack(side=tk.LEFT, padx=2)
open_php_ini_button = ttk.Button(php_button_frame, text="", command=open_php_ini) # 文字將由 update_gui_texts 設定
open_php_ini_button.pack(side=tk.LEFT, padx=2)
current_row += 1


# --- 網站根目錄選擇 ---
www_path_label = ttk.Label(root, text="") # 文字將由 update_gui_texts 設定
www_path_label.grid(row=current_row, column=0, padx=5, pady=5, sticky="w")
www_path_entry = ttk.Entry(root, width=50)
www_path_entry.insert(0, config.get("www_path", ""))
www_path_entry.grid(row=current_row, column=1, padx=5, pady=5, sticky="ew")

www_button_frame = ttk.Frame(root)
www_button_frame.grid(row=current_row, column=2, padx=5, pady=5, sticky="e")
select_www_button = ttk.Button(www_button_frame, text="", command=set_www_path) # 文字將由 update_gui_texts 設定
select_www_button.pack(side=tk.LEFT, padx=2)
current_row += 1


# --- 埠號設定 ---
port_label = ttk.Label(root, text="") # 文字將由 update_gui_texts 設定
port_label.grid(row=current_row, column=0, padx=5, pady=5, sticky="w")
port_entry = ttk.Entry(root, width=10)
port_entry.insert(0, str(config.get("port", 8080)))
port_entry.grid(row=current_row, column=1, padx=5, pady=5, sticky="w")
current_row += 1


# --- 控制按鈕 ---
button_frame = ttk.Frame(root, padding="10")
button_frame.grid(row=current_row, column=0, columnspan=3, pady=10, sticky="ew")
control_buttons_inner_frame = ttk.Frame(button_frame)
control_buttons_inner_frame.pack(expand=True)

start_button = ttk.Button(control_buttons_inner_frame, text="", command=start_server) # 文字將由 update_gui_texts 設定
start_button.pack(side=tk.LEFT, padx=10)

stop_button = ttk.Button(control_buttons_inner_frame, text="", command=stop_server, state=tk.DISABLED) # 文字將由 update_gui_texts 設定
stop_button.pack(side=tk.LEFT, padx=10)
current_row += 1


# --- 狀態顯示 ---
status_frame = ttk.Frame(root, padding="10")
status_frame.grid(row=current_row, column=0, columnspan=3, sticky="ew")
status_frame.columnconfigure(0, weight=1)

status_label = ttk.Label(status_frame, text="", anchor="center") # 文字將由 update_gui_texts 或狀態函數設定
status_label.grid(row=0, column=0, sticky="ew")

url_label = ttk.Label(status_frame, text="", anchor="center") # 文字由狀態函數設定
url_label.grid(row=1, column=0, sticky="ew")


# 2. 在所有 GUI 元件創建並定義好變數後，更新一次所有文字
# Combobox 的 values 在創建時已經設定，但文字需要更新
update_gui_texts()


# 設定視窗關閉事件
root.protocol("WM_DELETE_WINDOW", on_closing)

# === 自動啟動伺服器 ===
debug_print("Attempting auto-start...")
try:
    # start_server 內部會呼叫 update_config_from_entries 和 save_config_and_languages
    start_server()
except Exception as e:
    debug_print(f"Auto-start failed with unhandled exception: {e}")
    traceback.print_exc()
    messagebox.showerror(t("auto_start_failed_title", "自動啟動失敗"), t("auto_start_failed_generic", f"伺服器啟動時發生未預期錯誤：\n{e}"))
    # 確保按鈕狀態正確
    start_button.config(state=tk.NORMAL)
    stop_button.config(state=tk.DISABLED)
    # 確保狀態標籤顯示自動啟動失敗，並使用 t()
    status_label.config(text=t("status_auto_start_failed", "🛑 自動啟動失敗"), foreground="red")
    url_label.config(text="", foreground="black", cursor="")
    url_label.unbind("<Button-1>")
debug_print("Auto-start attempt finished.")


root.mainloop()