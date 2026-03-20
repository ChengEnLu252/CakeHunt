#!/usr/bin/env python3
# encoding=utf-8
"""
multi_account_manager.py — CakeHunt 多帳號管理器
每個帳號 = 獨立 subprocess (nodriver_tixcraft.py --input <tmp_config.json>)
stdout 解析 → 狀態分類 → WebSocket 廣播
"""
import copy, json, os, subprocess, sys, tempfile, threading, uuid
from datetime import datetime
from typing import Dict, List, Optional, Set

# ── 狀態常數 ──────────────────────────────────────────────────────────────────
STATUS_IDLE       = "idle"
STATUS_STARTING   = "starting"
STATUS_RUNNING    = "running"       # 1. 搶票中
STATUS_NO_MATCH   = "no_match"      # 3. 無符合條件，依邏輯順序搶票
STATUS_ORDERING   = "ordering"      # 4. 搶票成功，請於限定時間內輸入訂單資訊
STATUS_SUCCESS    = "success"       # 5. 搶票完成
STATUS_FAILED     = "failed"        # 2/6. 搶票失敗
STATUS_PAUSED     = "paused"
STATUS_ERROR      = "error"
STATUS_STOPPED    = "stopped"

STATUS_META = {
    STATUS_IDLE:     {"label": "待機中",                                      "bs": "secondary"},
    STATUS_STARTING: {"label": "啟動中...",                                   "bs": "primary"},
    STATUS_RUNNING:  {"label": "① 搶票中",                                   "bs": "primary"},
    STATUS_NO_MATCH: {"label": "③ 無符合條件，依邏輯順序搶票",               "bs": "warning"},
    STATUS_ORDERING: {"label": "④ 搶票成功！請於限定時間內輸入訂單資訊",    "bs": "info"},
    STATUS_SUCCESS:  {"label": "⑤ 🎉 搶票完成！",                           "bs": "success"},
    STATUS_FAILED:   {"label": "② / ⑥ 搶票失敗",                           "bs": "danger"},
    STATUS_PAUSED:   {"label": "已暫停",                                      "bs": "secondary"},
    STATUS_ERROR:    {"label": "發生錯誤",                                    "bs": "danger"},
    STATUS_STOPPED:  {"label": "已停止",                                      "bs": "secondary"},
}

def _classify_line(line: str) -> Optional[str]:
    s = line.strip().lower()
    if not s:
        return None

    # 5. 搶票完成
    if any(x in s for x in [
        "purchase completed", "訂購完成", "booking successful",
        "order completed", "感謝購票", "thank you for", "訂單完成",
        "[success]", "ticket assigned"
    ]):
        return STATUS_SUCCESS

    # 4. 搶票成功，進入訂單填寫
    if any(x in s for x in [
        "訂單已保留", "order reserved", "registrations/new",
        "checkout", "payment", "確認訂單", "填寫資料",
        "please complete", "ordering", "訂票中"
    ]):
        return STATUS_ORDERING

    # 2/6. 搶票失敗
    if any(x in s for x in [
        "sold out", "已售完", "售罄", "no ticket available",
        "purchase failed", "訂票失敗", "搶票失敗", "failed to purchase"
    ]):
        return STATUS_FAILED

    # 3. 無符合條件，依邏輯順序搶票
    if any(x in s for x in [
        "keyword not match", "no match", "條件不符",
        "area not found", "date not found", "skip", "pass",
        "sold_out", "pass_date", "keyword_exclude",
        "selecting", "選票", "選擇", "area", "seat", "區域",
        "captcha", "驗證碼", "ocr", "cloudflare"
    ]):
        return STATUS_NO_MATCH

    # 1. 搶票中（URL 跳轉）
    if line.strip().startswith("http"):
        return STATUS_RUNNING

    return None

# ── AccountInstance ───────────────────────────────────────────────────────────
class AccountInstance:
    def __init__(self, account_id, name, config):
        self.account_id  = account_id
        self.name        = name
        self.config      = config
        self.status      = STATUS_IDLE
        self.current_url = ""
        self.logs: List[str] = []
        self.process     = None
        self.config_file = None
        self.started_at  = None
        self._lock       = threading.Lock()

    def add_log(self, line: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.logs.append(f"[{ts}] {line.rstrip()}")
            if len(self.logs) > 100:
                self.logs = self.logs[-100:]

    def parse_stdout_line(self, line: str):
        line = line.rstrip()
        if not line:
            return
        self.add_log(line)
        if line.strip().startswith("http"):
            self.current_url = line.strip()
        if self.status == STATUS_SUCCESS:
            return
        new_status = _classify_line(line)
        if new_status:
            self.status = new_status

    def to_dict(self) -> dict:
        with self._lock:
            logs_snap = list(self.logs[-30:])
        is_alive = self.process is not None and self.process.poll() is None
        meta = STATUS_META.get(self.status, STATUS_META[STATUS_IDLE])
        return {
            "account_id":    self.account_id,
            "name":          self.name,
            "display_name":  self._get_display_name(),
            "status":        self.status,
            "status_label":  meta["label"],
            "status_bs":     meta["bs"],
            "current_url":   self.current_url,
            "logs":          logs_snap,
            "is_running":    is_alive,
            "started_at":    self.started_at,
            "homepage":      self.config.get("homepage", ""),
            "ticket_number": self.config.get("ticket_number", 1),
        }
        
    def _get_display_name(self) -> str:
        """取得顯示名稱：優先用帳號 email，否則用 name"""
        ao = self.config.get("accounts_override", {})
        platform = self.config.get("platform", "")
        # 依平台取帳號
        account = ao.get(platform + "_account", "") if platform else ""
        if not account:
            # 嘗試從 accounts 全域設定取
            accounts = self.config.get("accounts", {})
            for key in ["kktix_account", "tixcraft_sid", "fami_account", 
                        "ibon_account", "ticketplus_account"]:
                val = accounts.get(key, "")
                if val and len(val) > 3:
                    account = val
                    break
        return account if account else self.name

# ── MultiAccountManager ───────────────────────────────────────────────────────
class MultiAccountManager:
    _instance = None

    def __init__(self):
        self._accounts: Dict[str, AccountInstance] = {}
        self._lock     = threading.Lock()
        self._ws_lock  = threading.Lock()
        self._ws_clients: Set = set()
        self._bot_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "nodriver_tixcraft.py"
        )

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_ws_client(self, client):
        with self._ws_lock:
            self._ws_clients.add(client)

    def remove_ws_client(self, client):
        with self._ws_lock:
            self._ws_clients.discard(client)

    def _broadcast(self, data: dict):
        msg = json.dumps(data, ensure_ascii=False)
        with self._ws_lock:
            dead = set()
            for c in self._ws_clients:
                try:
                    c.write_message(msg)
                except Exception:
                    dead.add(c)
            self._ws_clients -= dead

    def get_all_status(self) -> List[dict]:
        with self._lock:
            return [a.to_dict() for a in self._accounts.values()]

    def get_account(self, account_id) -> Optional[AccountInstance]:
        with self._lock:
            return self._accounts.get(account_id)

    def start_account(self, account_id, name, merged_config) -> dict:
        with self._lock:
            ex = self._accounts.get(account_id)
            if ex and ex.process and ex.process.poll() is None:
                return {"success": False, "message": "已在執行中"}

        tmp_dir     = tempfile.gettempdir()
        config_path = os.path.join(tmp_dir, f"cakehunt_acc_{account_id}.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(merged_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return {"success": False, "message": str(e)}

        acc = AccountInstance(account_id, name, merged_config)
        acc.config_file = config_path
        acc.status      = STATUS_STARTING
        acc.started_at  = datetime.now().isoformat()
        acc.add_log(f"[MultiAccount] 啟動：{name}")
        acc.add_log(f"[MultiAccount] 目標：{merged_config.get('homepage','')}")

        with self._lock:
            self._accounts[account_id] = acc

        try:
            import copy as _copy
            env = _copy.copy(os.environ)
            env["PYTHONUNBUFFERED"] = "1"

            import sys as _sys
            if getattr(_sys, 'frozen', False):
                # 打包後：找同目錄的 nodriver_tixcraft 執行檔
                import os as _os
                _exe_dir = _os.path.dirname(_sys.executable)
                if _sys.platform == 'win32':
                    _bot_exe = _os.path.join(_exe_dir, 'nodriver_tixcraft.exe')
                else:
                    _bot_exe = _os.path.join(_exe_dir, 'nodriver_tixcraft')
                _cmd = [_bot_exe, "--input", config_path]
            else:
                # 開發模式：用 Python 執行 .py
                _cmd = [_sys.executable, "-u", self._bot_script, "--input", config_path]

            proc = subprocess.Popen(
                _cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env=env,
            )
            acc.process = proc
            acc.status  = STATUS_RUNNING
        except Exception as e:
            acc.status = STATUS_ERROR
            acc.add_log(f"[MultiAccount] 啟動失敗：{e}")
            self._broadcast({"type": "status_update", "account": acc.to_dict()})
            return {"success": False, "message": str(e)}

        threading.Thread(target=self._read_output, args=(account_id,), daemon=True).start()
        self._broadcast({"type": "status_update", "account": acc.to_dict()})
        return {"success": True}

    def stop_account(self, account_id) -> dict:
        acc = self.get_account(account_id)
        if not acc:
            return {"success": False, "message": "找不到帳號"}
        if acc.process and acc.process.poll() is None:
            try: acc.process.terminate()
            except: pass
        if acc.status != STATUS_SUCCESS:
            acc.status = STATUS_STOPPED
        acc.add_log("[MultiAccount] 手動停止")
        self._broadcast({"type": "status_update", "account": acc.to_dict()})
        return {"success": True}

    def remove_account(self, account_id) -> dict:
        self.stop_account(account_id)
        with self._lock:
            self._accounts.pop(account_id, None)
        self._broadcast({"type": "account_removed", "account_id": account_id})
        return {"success": True}

    def stop_all(self):
        with self._lock:
            ids = list(self._accounts.keys())
        for aid in ids:
            self.stop_account(aid)

    def start_all_from_config(self, multi_accounts, base_config) -> List[dict]:
        results = []
        for entry in multi_accounts:
            aid    = entry.get("id") or str(uuid.uuid4())[:8]
            name   = entry.get("name", aid)
            merged = _merge_config(base_config, entry)
            result = self.start_account(aid, name, merged)
            results.append({"account_id": aid, "name": name, **result})
        return results

    def _read_output(self, account_id):
        acc = self.get_account(account_id)
        if not acc or not acc.process:
            return
        try:
            for line in iter(acc.process.stdout.readline, ""):
                acc.parse_stdout_line(line)
                self._broadcast({"type": "status_update", "account": acc.to_dict()})
        except Exception as e:
            acc.add_log(f"[MultiAccount] 讀取中斷：{e}")
        exit_code = acc.process.poll()
        acc.add_log(f"[MultiAccount] 程序結束（exit: {exit_code}）")
        if acc.status not in (STATUS_SUCCESS, STATUS_STOPPED, STATUS_FAILED):
            acc.status = STATUS_STOPPED
        self._broadcast({"type": "status_update", "account": acc.to_dict()})
        if acc.config_file and os.path.exists(acc.config_file):
            try: os.remove(acc.config_file)
            except: pass

# ── Config merge ──────────────────────────────────────────────────────────────
def _merge_config(base: dict, entry: dict) -> dict:
    config = copy.deepcopy(base)
    for key in ("homepage", "ticket_number"):
        if key in entry and entry[key]:
            config[key] = entry[key]
    if entry.get("area_keyword"):
        config.setdefault("area_auto_select", {})["area_keyword"] = entry["area_keyword"]
    if entry.get("date_keyword"):
        config.setdefault("date_auto_select", {})["date_keyword"] = entry["date_keyword"]
    if entry.get("accounts_override"):
        config.setdefault("accounts", {}).update(entry["accounts_override"])
    config.pop("multi_accounts", None)
    return config

multi_manager = MultiAccountManager.get_instance()