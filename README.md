# EasyPHPControl - 輕量化 Apache WebUI 管理工具

`EasyPHPControl` 是一個基於 Python + Flask + WebUI (Pywebview) 開發的圖形化 Apache 管理工具。它旨在簡化 Windows 環境下 Apache 伺服器的日常維護，提供直觀的介面來管理多站點連接埠、反向代理以及 SSL 憑證。

## ✨ 主要功能

- **一鍵控制**：圖形化啟動、停止、重啟 Apache 服務。
- **多連接埠管理**：支援同時監聽多個 Port，並對應不同的本地資料夾。
- **反向代理 (Reverse Proxy)**：輕鬆將特定連接埠的流量轉發至內網其他服務。
- **視覺化路徑選擇**：整合 Windows 資料夾瀏覽視窗，無需手動輸入路徑。
- **SSL 自動化**：整合 `win-acme` 工具，快速申請並管理 Let's Encrypt 免費憑證。

---

## ⚠️ 重要：Apache `httpd.conf` 前置設定

為了讓本工具產生的虛擬主機設定（VHost）生效，在使用本工具前，請務必手動檢查並修改您的 `apache2/conf/httpd.conf` 檔案，確保以下模組與設定已啟用（移除行首的 `#`）：

### 1. 啟動核心模組
搜尋並取消以下四行模組的註解：
```apache
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so
LoadModule ssl_module modules/mod_ssl.so
LoadModule vhost_alias_module modules/mod_vhost_alias.so