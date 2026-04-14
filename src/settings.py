#!/usr/bin/env python3
#encoding=utf-8
import asyncio
import base64
import json
import os
import platform
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime

import tornado
from tornado.web import Application
from tornado.web import StaticFileHandler

import requests
import util

import tornado.websocket
from multi_account_manager import multi_manager, _merge_config

from typing import (
    Dict,
    Any,
    Union,
    Optional,
    Awaitable,
    Tuple,
    List,
    Callable,
    Iterable,
    Generator,
    Type,
    TypeVar,
    cast,
    overload,
)

try:
    import ddddocr
except Exception as exc:
    print(f"[WARNING] ddddocr module not available: {exc}")
    print("[WARNING] OCR captcha auto-solve will be disabled.")

# Get script directory for resource paths
#SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 改後
if hasattr(sys, '_MEIPASS'):
    SCRIPT_DIR = sys._MEIPASS
else:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CONST_APP_VERSION = "NN多帳號開掛版"

CONST_MAXBOT_ANSWER_ONLINE_FILE = "MAXBOT_ONLINE_ANSWER.txt"
CONST_MAXBOT_CONFIG_FILE = "settings.json"
CONST_MAXBOT_INT28_FILE = "MAXBOT_INT28_IDLE.txt"
CONST_MAXBOT_LAST_URL_FILE = "MAXBOT_LAST_URL.txt"
CONST_MAXBOT_QUESTION_FILE = "MAXBOT_QUESTION.txt"

CONST_SERVER_PORT = 16888

# ── 單帳號 Bot 進程追蹤 ────────────────────────────────────────────────────────
# 儲存目前執行中的 bot subprocess，讓重新搶票時可以先砍掉舊進程
_single_bot_process = None

CONST_FROM_TOP_TO_BOTTOM = "from top to bottom"
CONST_FROM_BOTTOM_TO_TOP = "from bottom to top"
CONST_CENTER = "center"
CONST_RANDOM = "random"
CONST_SELECT_ORDER_DEFAULT = CONST_RANDOM
CONST_EXCLUDE_DEFAULT = "\"輪椅\",\"身障\",\"身心\",\"障礙\",\"Restricted View\",\"燈柱遮蔽\",\"視線不完整\""
CONST_CAPTCHA_SOUND_FILENAME_DEFAULT = "assets/sounds/ding-dong.wav"
CONST_HOMEPAGE_DEFAULT = "about:blank"

CONST_OCR_CAPTCH_IMAGE_SOURCE_NON_BROWSER = "NonBrowser"
CONST_OCR_CAPTCH_IMAGE_SOURCE_CANVAS = "canvas"

CONST_WEBDRIVER_TYPE_NODRIVER = "nodriver"

CONST_SUPPORTED_SITES = ["https://kktix.com"
    ,"https://tixcraft.com (拓元)"
    ,"https://ticketmaster.sg"
    #,"https://ticketmaster.com"
    ,"https://teamear.tixcraft.com/ (添翼)"
    ,"https://www.indievox.com/ (獨立音樂)"
    ,"https://www.famiticket.com.tw (全網)"
    ,"https://ticket.ibon.com.tw/"
    ,"https://kham.com.tw/ (寬宏)"
    ,"https://ticket.com.tw/ (年代)"
    ,"https://tickets.udnfunlife.com/ (udn售票網)"
    ,"https://ticketplus.com.tw/ (遠大)"
    ,"===[香港或南半球的系統]==="
    ,"http://www.urbtix.hk/ (城市)"
    ,"https://www.cityline.com/ (買飛)"
    ,"https://hotshow.hkticketing.com/ (快達票)"
    ,"https://ticketing.galaxymacau.com/ (澳門銀河)"
    ,"http://premier.ticketek.com.au"
    ]


def get_default_config():
    config_dict={}

    config_dict["homepage"] = CONST_HOMEPAGE_DEFAULT
    config_dict["browser"] = "chrome"
    config_dict["language"] = "English"
    config_dict["ticket_number"] = 2
    config_dict["refresh_datetime"] = ""

    config_dict["ocr_captcha"] = {}
    config_dict["ocr_captcha"]["enable"] = True
    config_dict["ocr_captcha"]["beta"] = True
    config_dict["ocr_captcha"]["force_submit"] = True
    config_dict["ocr_captcha"]["image_source"] = CONST_OCR_CAPTCH_IMAGE_SOURCE_CANVAS
    config_dict["ocr_captcha"]["use_universal"] = True
    config_dict["ocr_captcha"]["path"] = "assets/model/universal"
    config_dict["webdriver_type"] = CONST_WEBDRIVER_TYPE_NODRIVER

    config_dict["date_auto_select"] = {}
    config_dict["date_auto_select"]["enable"] = True
    config_dict["date_auto_select"]["date_keyword"] = ""
    config_dict["date_auto_select"]["mode"] = CONST_SELECT_ORDER_DEFAULT

    config_dict["area_auto_select"] = {}
    config_dict["area_auto_select"]["enable"] = True
    config_dict["area_auto_select"]["mode"] = CONST_SELECT_ORDER_DEFAULT
    config_dict["area_auto_select"]["area_keyword"] = ""
    config_dict["keyword_exclude"] = CONST_EXCLUDE_DEFAULT

    config_dict['kktix']={}
    config_dict["kktix"]["auto_press_next_step_button"] = True
    config_dict["kktix"]["auto_fill_ticket_number"] = True
    config_dict["kktix"]["max_dwell_time"] = 90

    config_dict['cityline']={}

    config_dict['tixcraft']={}
    config_dict["tixcraft"]["pass_date_is_sold_out"] = True
    config_dict["tixcraft"]["auto_reload_coming_soon_page"] = True


    # Contact information
    config_dict['contact']={}
    config_dict["contact"]["real_name"] = ""
    config_dict["contact"]["phone"] = ""
    config_dict["contact"]["credit_card_prefix"] = ""

    # Accounts section (cookies, accounts, passwords)
    config_dict['accounts']={}
    config_dict["accounts"]["tixcraft_sid"] = ""
    config_dict["accounts"]["tixcraft_account"] = ""
    config_dict["accounts"]["tixcraft_password"] = ""
    config_dict["accounts"]["ibonqware"] = ""
    config_dict["accounts"]["funone_session_cookie"] = ""
    config_dict["accounts"]["fansigo_cookie"] = ""
    config_dict["accounts"]["fansigo_account"] = ""
    config_dict["accounts"]["fansigo_password"] = ""
    config_dict["accounts"]["facebook_account"] = ""
    config_dict["accounts"]["kktix_account"] = ""
    config_dict["accounts"]["fami_account"] = ""
    config_dict["accounts"]["cityline_account"] = ""
    config_dict["accounts"]["urbtix_account"] = ""
    config_dict["accounts"]["hkticketing_account"] = ""
    config_dict["accounts"]["kham_account"] = ""
    config_dict["accounts"]["ticket_account"] = ""
    config_dict["accounts"]["udn_account"] = ""
    config_dict["accounts"]["ticketplus_account"] = ""

    config_dict["accounts"]["facebook_password"] = ""
    config_dict["accounts"]["kktix_password"] = ""
    config_dict["accounts"]["fami_password"] = ""
    config_dict["accounts"]["urbtix_password"] = ""
    config_dict["accounts"]["cityline_password"] = ""
    config_dict["accounts"]["hkticketing_password"] = ""
    config_dict["accounts"]["kham_password"] = ""
    config_dict["accounts"]["ticket_password"] = ""
    config_dict["accounts"]["udn_password"] = ""
    config_dict["accounts"]["ticketplus_password"] = ""

    # Advanced settings (non-credential settings only)
    config_dict['advanced']={}

    config_dict['advanced']['play_sound']={}
    config_dict["advanced"]["play_sound"]["ticket"] = True
    config_dict["advanced"]["play_sound"]["order"] = True
    config_dict["advanced"]["play_sound"]["filename"] = CONST_CAPTCHA_SOUND_FILENAME_DEFAULT

    config_dict["advanced"]["disable_adjacent_seat"] = False
    config_dict["advanced"]["hide_some_image"] = False
    config_dict["advanced"]["block_facebook_network"] = False

    config_dict["advanced"]["headless"] = False
    config_dict["advanced"]["verbose"] = False
    config_dict["advanced"]["show_timestamp"] = False
    config_dict["advanced"]["auto_guess_options"] = False
    config_dict["advanced"]["user_guess_string"] = ""
    config_dict["advanced"]["discount_code"] = ""

    # Server port for settings web interface (Issue #156)
    config_dict["advanced"]["server_port"] = CONST_SERVER_PORT
    # remote_url will be dynamically generated based on server_port
    config_dict["advanced"]["remote_url"] = ""

    config_dict["advanced"]["auto_reload_page_interval"] = 5
    config_dict["advanced"]["auto_reload_overheat_count"] = 4
    config_dict["advanced"]["auto_reload_overheat_cd"] = 1.0
    config_dict["advanced"]["reset_browser_interval"] = 0
    config_dict["advanced"]["proxy_server_port"] = ""
    config_dict["advanced"]["window_size"] = "600,1024"

    config_dict["advanced"]["idle_keyword"] = ""
    config_dict["advanced"]["resume_keyword"] = ""
    config_dict["advanced"]["idle_keyword_second"] = ""
    config_dict["advanced"]["resume_keyword_second"] = ""

    config_dict["advanced"]["discord_webhook_url"] = ""
    config_dict["advanced"]["telegram_bot_token"] = ""
    config_dict["advanced"]["telegram_chat_id"] = ""

    # Keyword priority fallback (Feature 003)
    config_dict["date_auto_fallback"] = False  # default: strict mode (avoid unwanted purchases)
    config_dict["area_auto_fallback"] = False  # default: strict mode (avoid unwanted purchases)

    return config_dict

def read_last_url_from_file():
    app_root = util.get_app_root()
    last_url_filepath = os.path.join(app_root, CONST_MAXBOT_LAST_URL_FILE)
    text = ""
    if os.path.exists(last_url_filepath):
        try:
            with open(last_url_filepath, "r", encoding="utf-8") as text_file:
                text = text_file.readline().strip()
        except Exception as e:
            print(f"[ERROR] Failed to read last_url from {last_url_filepath}: {e}")
    return text

def migrate_config(config_dict):
    """Migrate old config structure to new structure."""
    if config_dict is None:
        return config_dict

    # Migrate ocr_model_path from advanced to ocr_captcha.path
    if "advanced" in config_dict and "ocr_model_path" in config_dict["advanced"]:
        if "ocr_captcha" not in config_dict:
            config_dict["ocr_captcha"] = {}
        if "path" not in config_dict["ocr_captcha"]:
            config_dict["ocr_captcha"]["path"] = config_dict["advanced"]["ocr_model_path"]
        del config_dict["advanced"]["ocr_model_path"]

    # Ensure ocr_captcha.path exists
    if "ocr_captcha" in config_dict and "path" not in config_dict["ocr_captcha"]:
        config_dict["ocr_captcha"]["path"] = "assets/model/universal"

    # Migrate server_port: ensure old config has this field (Issue #156)
    if "advanced" in config_dict:
        if "server_port" not in config_dict["advanced"]:
            config_dict["advanced"]["server_port"] = CONST_SERVER_PORT

    # Migrate discount_code from accounts to advanced
    if "accounts" in config_dict and "discount_code" in config_dict["accounts"]:
        if "advanced" not in config_dict:
            config_dict["advanced"] = {}
        # Only migrate if advanced.discount_code doesn't exist or is empty
        if "discount_code" not in config_dict["advanced"] or not config_dict["advanced"]["discount_code"]:
            config_dict["advanced"]["discount_code"] = config_dict["accounts"]["discount_code"]
        del config_dict["accounts"]["discount_code"]

    # Ensure advanced.discount_code exists
    if "advanced" in config_dict and "discount_code" not in config_dict["advanced"]:
        config_dict["advanced"]["discount_code"] = ""

    # Ensure all default fields exist (fills missing keys from new versions)
    default = get_default_config()
    for section in ["advanced", "kktix", "tixcraft", "date_auto_select", "area_auto_select", "ocr_captcha", "contact", "accounts", "cityline"]:
        if section in default:
            if section not in config_dict or not isinstance(config_dict[section], dict):
                config_dict[section] = dict(default[section])
            else:
                for key, value in default[section].items():
                    if key not in config_dict[section]:
                        config_dict[section][key] = value

    # Top-level scalar fields (auto-fill any missing non-section keys)
    dict_sections = {k for k, v in default.items() if isinstance(v, dict)}
    for key, value in default.items():
        if key not in dict_sections and key not in config_dict:
            config_dict[key] = value

    return config_dict

def load_json():
    app_root = util.get_app_root()

    # overwrite config path.
    config_filepath = os.path.join(app_root, CONST_MAXBOT_CONFIG_FILE)

    config_dict = None
    if os.path.isfile(config_filepath):
        try:
            with open(config_filepath, encoding='utf-8') as json_data:
                config_dict = json.load(json_data)
        except Exception as e:
            print(f"[ERROR] Failed to load {config_filepath}: {e}")
            print("[ERROR] Settings file may be corrupted. Using default settings.")
            config_dict = get_default_config()
    else:
        config_dict = get_default_config()

    # Apply migrations for backward compatibility
    config_dict = migrate_config(config_dict)

    return config_filepath, config_dict

def reset_json():
    app_root = util.get_app_root()
    config_filepath = os.path.join(app_root, CONST_MAXBOT_CONFIG_FILE)
    if os.path.exists(str(config_filepath)):
        try:
            os.unlink(str(config_filepath))
        except Exception as exc:
            print(exc)
            pass

    config_dict = get_default_config()
    return config_filepath, config_dict

def maxbot_idle():
    app_root = util.get_app_root()
    idle_filepath = os.path.join(app_root, CONST_MAXBOT_INT28_FILE)
    try:
        with open(idle_filepath, "w") as text_file:
            text_file.write("")
    except Exception as e:
        print(f"[ERROR] Failed to create idle file: {e}")

def maxbot_resume():
    app_root = util.get_app_root()
    idle_filepath = os.path.join(app_root, CONST_MAXBOT_INT28_FILE)
    for i in range(3):
         util.force_remove_file(idle_filepath)

def stop_single_bot():
    """砍掉單帳號 bot 進程（Chrome 也會一起關閉）"""
    global _single_bot_process
    if _single_bot_process is not None:
        if _single_bot_process.poll() is None:
            try:
                if platform.system() != 'Windows':
                    # Bot 以 start_new_session=True 啟動，有獨立 process group
                    # 用 SIGTERM 砍整個 group（包含 Chrome 子進程）
                    try:
                        os.killpg(os.getpgid(_single_bot_process.pid), signal.SIGTERM)
                    except (ProcessLookupError, OSError):
                        _single_bot_process.terminate()
                else:
                    _single_bot_process.terminate()
                _single_bot_process.wait(timeout=8)
                print("[BotManager] 舊的 bot 進程已終止")
            except Exception:
                try:
                    _single_bot_process.kill()
                    print("[BotManager] 舊的 bot 進程已強制終止")
                except Exception:
                    pass
        _single_bot_process = None

    # 等待 Chrome 釋放 user data dir lock
    # Mac 需要較長等待時間
    if platform.system() == 'Darwin':
        time.sleep(2)
    else:
        time.sleep(0.5)

    # 確保 idle 檔清除，避免新進程一啟動就進暫停狀態
    maxbot_resume()

def launch_maxbot():
    global launch_counter, _single_bot_process
    if "launch_counter" in globals():
        launch_counter += 1
    else:
        launch_counter = 0

    # ── 先砍掉舊的 bot 進程 ──────────────────────────────────────────────────
    stop_single_bot()

    config_filepath, config_dict = load_json()

    script_name = "nodriver_tixcraft"

    window_size = config_dict["advanced"]["window_size"]
    if len(window_size) > 0:
        if "," in window_size:
            size_array = window_size.split(",")
            target_width = int(size_array[0])
            target_left = target_width * launch_counter
            if target_left >= 1440:
                launch_counter = 0
            window_size = window_size + "," + str(launch_counter)

    # ── 直接啟動並儲存進程參考 ───────────────────────────────────────────────
    def _do_launch():
        global _single_bot_process
        working_dir = util.get_app_root()
        cmd_argument = []
        if len(window_size) > 0:
            cmd_argument.append('--window_size=' + window_size)

        # Unix 使用 start_new_session=True 建立獨立 process group
        # 這樣 stop_single_bot() 才能用 os.killpg() 一次砍掉 bot + Chrome
        popen_kwargs = {"cwd": working_dir}
        if platform.system() != 'Windows':
            popen_kwargs["start_new_session"] = True
        # Mac frozen 模式：bot 的 cwd 要指向解壓縮根目錄
        # 因為 settings.json 存在那裡，bot 啟動後才找得到
        if hasattr(sys, 'frozen') and platform.system() == 'Darwin':
            exe_dir = os.path.dirname(sys.executable)
            popen_kwargs["cwd"] = exe_dir
            print(f"[BotManager] exe_dir: {exe_dir}")
            print(f"[BotManager] cwd設定: {exe_dir}")
            print(f"[BotManager] settings.json存在: {os.path.exists(os.path.join(exe_dir, 'settings.json'))}")
            
        try:
            if hasattr(sys, 'frozen'):
                print("execute in frozen mode")
                if platform.system() == 'Darwin':
                    exe_dir = os.path.dirname(sys.executable)
                    parent_dir = os.path.dirname(exe_dir)
                    bot_path = os.path.join(parent_dir, 'nodriver_tixcraft', 'nodriver_tixcraft')
                    if not os.path.exists(bot_path):
                        # 合併目錄結構：bot 與 settings 在同一資料夾
                        bot_path = os.path.join(exe_dir, 'nodriver_tixcraft')
                    # ⚠️ 不傳 --input，讓 bot 自行找 settings.json
                    # 傳 --input 會讓 is_multi_account_mode = True，導致搶完不退出
                    cmd = [bot_path] + cmd_argument
                elif platform.system() == 'Windows':
                    # 必須用完整路徑，subprocess 找 exe 的搜尋範圍與 cwd 無關
                    _exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                    _bot_path = os.path.join(_exe_dir, script_name + '.exe')
                    print(f"[BotManager] Windows bot 路徑：{_bot_path}")
                    print(f"[BotManager] 路徑存在：{os.path.exists(_bot_path)}")
                    cmd = [_bot_path] + cmd_argument
                else:
                    cmd = ['./' + script_name] + cmd_argument
                proc = subprocess.Popen(cmd, **popen_kwargs)
            else:
                interpreter_binary = sys.executable
                print("execute in shell mode.")
                cmd_array = [interpreter_binary, script_name + '.py'] + cmd_argument
                proc = subprocess.Popen(cmd_array, **popen_kwargs)
            _single_bot_process = proc
            print(f"[BotManager] Bot 啟動，PID: {proc.pid}")
        except Exception as exc:
            print(f"[BotManager] 啟動失敗：{exc}")

    threading.Thread(target=_do_launch, daemon=True).start()

def change_maxbot_status_by_keyword():
    config_filepath, config_dict = load_json()

    system_clock_data = datetime.now()
    current_time = system_clock_data.strftime('%H:%M:%S')
    #print('Current Time is:', current_time)
    #print("idle_keyword", config_dict["advanced"]["idle_keyword"])
    if len(config_dict["advanced"]["idle_keyword"]) > 0:
        is_matched =  util.is_text_match_keyword(config_dict["advanced"]["idle_keyword"], current_time)
        if is_matched:
            #print("match to idle:", current_time)
            maxbot_idle()
    #print("resume_keyword", config_dict["advanced"]["resume_keyword"])
    if len(config_dict["advanced"]["resume_keyword"]) > 0:
        is_matched =  util.is_text_match_keyword(config_dict["advanced"]["resume_keyword"], current_time)
        if is_matched:
            #print("match to resume:", current_time)
            maxbot_resume()
    
    current_time = system_clock_data.strftime('%S')
    if len(config_dict["advanced"]["idle_keyword_second"]) > 0:
        is_matched =  util.is_text_match_keyword(config_dict["advanced"]["idle_keyword_second"], current_time)
        if is_matched:
            #print("match to idle:", current_time)
            maxbot_idle()
    if len(config_dict["advanced"]["resume_keyword_second"]) > 0:
        is_matched =  util.is_text_match_keyword(config_dict["advanced"]["resume_keyword_second"], current_time)
        if is_matched:
            #print("match to resume:", current_time)
            maxbot_resume()

def clean_tmp_file():
    app_root = util.get_app_root()
    remove_file_list = [CONST_MAXBOT_LAST_URL_FILE
        ,CONST_MAXBOT_INT28_FILE
        ,CONST_MAXBOT_ANSWER_ONLINE_FILE
        ,CONST_MAXBOT_QUESTION_FILE
    ]
    for filename in remove_file_list:
         filepath = os.path.join(app_root, filename)
         util.force_remove_file(filepath)

    Root_Dir = util.get_app_root()
    target_folder = os.listdir(Root_Dir)
    for item in target_folder:
        if item.endswith(".tmp"):
            try:
                os.remove(os.path.join(Root_Dir, item))
            except Exception as e:
                print(f"[WARNING] Failed to remove {item}: {e}")

class NoCacheStaticFileHandler(StaticFileHandler):
    """Custom StaticFileHandler that prevents caching of settings.html"""
    def set_extra_headers(self, path):
        # Disable caching only for settings.html to prevent stale UI issues
        if path == 'settings.html':
            self.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.set_header('Pragma', 'no-cache')
            self.set_header('Expires', '0')

class QuestionHandler(tornado.web.RequestHandler):
    def get(self):
        """Read MAXBOT_QUESTION.txt and return its content"""
        question_text = ""
        question_file = os.path.join(SCRIPT_DIR, CONST_MAXBOT_QUESTION_FILE)

        # Check if file exists
        if os.path.exists(question_file):
            try:
                with open(question_file, "r", encoding="utf-8") as f:
                    question_text = f.read().strip()
            except Exception as e:
                print(f"Error reading question file: {e}")

        # Return JSON response
        self.write({
            "exists": os.path.exists(question_file),
            "question": question_text
        })

class VersionHandler(tornado.web.RequestHandler):
    def get(self):
        self.write({"version":self.application.version})

class ShutdownHandler(tornado.web.RequestHandler):
    def get(self):
        global GLOBAL_SERVER_SHUTDOWN
        GLOBAL_SERVER_SHUTDOWN = True
        stop_single_bot()  # 關閉 server 時同時砍掉 bot 進程
        self.write({"showdown": GLOBAL_SERVER_SHUTDOWN})

class StopBotHandler(tornado.web.RequestHandler):
    """停止單帳號 bot（關閉 Chrome），不關閉 settings server"""
    def get(self):
        stop_single_bot()
        self.write({"stopped": True})

class StatusHandler(tornado.web.RequestHandler):
    def get(self):
        is_paused = False
        app_root = util.get_app_root()
        idle_filepath = os.path.join(app_root, CONST_MAXBOT_INT28_FILE)
        if os.path.exists(idle_filepath):
            is_paused = True
        url = read_last_url_from_file()
        self.write({"status": not is_paused, "last_url": url})

class PauseHandler(tornado.web.RequestHandler):
    def get(self):
        maxbot_idle()
        self.write({"pause": True})
    def post(self):
        maxbot_idle()
        self.write({"pause": True})

class ResumeHandler(tornado.web.RequestHandler):
    def get(self):
        maxbot_resume()
        self.write({"resume": True})
    def post(self):
        maxbot_resume()
        self.write({"resume": True})

class RunHandler(tornado.web.RequestHandler):
    def get(self):
        print('run button pressed.')
        launch_maxbot()
        self.write({"run": True})

class LoadJsonHandler(tornado.web.RequestHandler):
    def get(self):
        config_filepath, config_dict = load_json()

        # Dynamically generate remote_url based on server_port (Issue #156)
        server_port = config_dict.get("advanced", {}).get("server_port", CONST_SERVER_PORT)
        if not isinstance(server_port, int) or server_port < 1024 or server_port > 65535:
            server_port = CONST_SERVER_PORT
        config_dict["advanced"]["remote_url"] = f'"http://127.0.0.1:{server_port}/"'

        self.write(config_dict)

class ResetJsonHandler(tornado.web.RequestHandler):
    def get(self):
        config_filepath, config_dict = reset_json()
        util.save_json(config_dict, config_filepath)
        self.write(config_dict)

class SaveJsonHandler(tornado.web.RequestHandler):
    def post(self):
        _body = None
        is_pass_check = True
        error_message = ""
        error_code = 0

        if is_pass_check:
            is_pass_check = False
            try :
                _body = json.loads(self.request.body)
                is_pass_check = True
            except Exception:
                error_message = "wrong json format"
                error_code = 1002
                pass

        if is_pass_check:
            app_root = util.get_app_root()
            config_filepath = os.path.join(app_root, CONST_MAXBOT_CONFIG_FILE)
            config_dict = _body

            if config_dict["kktix"]["max_dwell_time"] > 0:
                if config_dict["kktix"]["max_dwell_time"] < 15:
                    # min value is 15 seconds.
                    config_dict["kktix"]["max_dwell_time"] = 15

            if config_dict["advanced"]["reset_browser_interval"] > 0:
                if config_dict["advanced"]["reset_browser_interval"] < 20:
                    # min value is 20 seconds.
                    config_dict["advanced"]["reset_browser_interval"] = 20

            # due to cloudflare.
            if ".cityline.com" in config_dict["homepage"]:
                config_dict["webdriver_type"] = CONST_WEBDRIVER_TYPE_NODRIVER

            util.save_json(config_dict, config_filepath)

        if not is_pass_check:
            self.set_status(401)
            self.write(dict(error=dict(message=error_message,code=error_code)))

        self.finish()

class SendkeyHandler(tornado.web.RequestHandler):
    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

        _body = None
        is_pass_check = True
        errorMessage = ""
        errorCode = 0

        if is_pass_check:
            is_pass_check = False
            try :
                _body = json.loads(self.request.body)
                is_pass_check = True
            except Exception:
                errorMessage = "wrong json format"
                errorCode = 1001
                pass

        if is_pass_check:
            app_root = util.get_app_root()
            if "token" in _body:
                tmp_file = _body["token"] + ".tmp"
                config_filepath = os.path.join(app_root, tmp_file)
                util.save_json(_body, config_filepath)

        self.write({"return": True})

class TestDiscordWebhookHandler(tornado.web.RequestHandler):
    ALLOWED_HOSTS = ("discord.com", "discordapp.com")

    def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.write({"success": False, "message": "wrong json format"})
            return

        webhook_url = body.get("webhook_url", "").strip()
        if not webhook_url:
            self.write({"success": False, "message": "webhook URL is empty"})
            return

        from urllib.parse import urlparse
        try:
            parsed = urlparse(webhook_url)
        except Exception:
            self.write({"success": False, "message": "invalid URL format"})
            return

        if parsed.scheme != "https":
            self.write({"success": False, "message": "only HTTPS URLs are allowed"})
            return

        if not any(parsed.netloc == host or parsed.netloc.endswith("." + host) for host in self.ALLOWED_HOSTS):
            self.write({"success": False, "message": "only Discord webhook URLs are allowed"})
            return

        if not parsed.path.startswith("/api/webhooks/"):
            self.write({"success": False, "message": "invalid Discord webhook URL format"})
            return

        _, config_dict = load_json()
        debug = util.create_debug_logger(config_dict)

        payload = {
            "content": "[Test] Tickets Hunter webhook test successful!",
            "username": "Tickets Hunter"
        }
        try:
            response = requests.post(webhook_url, json=payload, timeout=5.0)
            if response.status_code in (200, 204):
                debug.log("[Discord Webhook] Test OK")
                self.write({"success": True, "message": "ok"})
            else:
                debug.log("[Discord Webhook] Test failed: HTTP %d" % response.status_code)
                self.write({"success": False, "message": "HTTP %d" % response.status_code})
        except Exception as exc:
            debug.log("[Discord Webhook] Test failed: %s" % str(exc))
            self.write({"success": False, "message": str(exc)})

class TestTelegramHandler(tornado.web.RequestHandler):
    def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.write({"success": False, "message": "wrong json format"})
            return

        bot_token = body.get("bot_token", "").strip()
        chat_id = body.get("chat_id", "").strip()

        if not bot_token:
            self.write({"success": False, "message": "Bot Token is empty"})
            return

        import re
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', bot_token):
            self.write({"success": False, "message": "Bot Token format invalid"})
            return

        if not chat_id:
            self.write({"success": False, "message": "Chat ID is empty"})
            return

        chat_ids = [cid.strip() for cid in chat_id.split(",") if cid.strip()]
        if not chat_ids:
            self.write({"success": False, "message": "Chat ID is empty"})
            return

        invalid_ids = [cid for cid in chat_ids if not re.match(r'^-?\d+$', cid)]
        if invalid_ids:
            self.write({"success": False, "message": "Chat ID format invalid: %s" % ", ".join(invalid_ids)})
            return

        _, config_dict = load_json()
        debug = util.create_debug_logger(config_dict)

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        text = "[Test] Tickets Hunter Telegram test successful!"
        errors = []
        ok_count = 0
        for cid in chat_ids:
            try:
                payload = {"chat_id": cid, "text": text}
                response = requests.post(url, json=payload, timeout=5.0)
                result = response.json()
                if response.status_code == 200 and result.get("ok", False):
                    ok_count += 1
                else:
                    desc = result.get("description", "HTTP %d" % response.status_code)
                    errors.append(f"{cid}: {desc}")
            except (requests.RequestException, ValueError) as exc:
                safe_msg = str(exc).replace(bot_token, "***") if bot_token else str(exc)
                errors.append(f"{cid}: {safe_msg}")

        if ok_count == len(chat_ids):
            debug.log("[Telegram] Test OK (%d chat(s))" % ok_count)
            self.write({"success": True, "message": "ok"})
        elif ok_count > 0:
            debug.log("[Telegram] Test partial: %d/%d OK" % (ok_count, len(chat_ids)))
            self.write({"success": True, "message": "%d/%d OK, errors: %s" % (ok_count, len(chat_ids), "; ".join(errors))})
        else:
            msg = "; ".join(errors)
            debug.log("[Telegram] Test failed: %s" % msg)
            self.write({"success": False, "message": msg})

class OcrHandler(tornado.web.RequestHandler):
    def get(self):
        self.write({"answer": "1234"})

    def post(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')

        _body = None
        is_pass_check = True
        errorMessage = ""
        errorCode = 0

        if is_pass_check:
            is_pass_check = False
            try :
                _body = json.loads(self.request.body)
                is_pass_check = True
            except Exception:
                errorMessage = "wrong json format"
                errorCode = 1001
                pass

        img_base64 = None
        image_data = ""
        if is_pass_check:
            if 'image_data' in _body:
                image_data = _body['image_data']
                if len(image_data) > 0:
                    img_base64 = base64.b64decode(image_data)
            else:
                errorMessage = "image_data not exist"
                errorCode = 1002

        #print("is_pass_check:", is_pass_check)
        #print("errorMessage:", errorMessage)
        #print("errorCode:", errorCode)
        ocr_answer = ""
        if not img_base64 is None:
            try:
                ocr_answer = self.application.ocr.classification(img_base64)
                print("ocr_answer:", ocr_answer)
            except Exception as exc:
                pass

        self.write({"answer": ocr_answer})

class QueryHandler(tornado.web.RequestHandler):
    def format_config_keyword_for_json(self, user_input):
        if len(user_input) > 0:
            # Remove any existing quotes first
            user_input = user_input.replace('"', '').replace("'", '')

            # Add quotes to each keyword
            # Use semicolon as the ONLY delimiter (Issue #23)
            if util.CONST_KEYWORD_DELIMITER in user_input:
                items = user_input.split(util.CONST_KEYWORD_DELIMITER)
                user_input = ','.join([f'"{item.strip()}"' for item in items if item.strip()])
            else:
                user_input = f'"{user_input.strip()}"'
        return user_input

    def compose_as_json(self, user_input):
        user_input = self.format_config_keyword_for_json(user_input)
        return "{\"data\":[%s]}" % user_input

    def get(self):
        global txt_answer_value
        answer_text = ""
        try:
            answer_text = txt_answer_value.get().strip()
        except Exception as exc:
            pass
        answer_text_output = self.compose_as_json(answer_text)
        #print("answer_text_output:", answer_text_output)
        self.write(answer_text_output)
        
# ══════════════════════════════════════════════════════════
# Multi-Account Handlers
# ══════════════════════════════════════════════════════════
class MultiAccountWebSocket(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin): return True
    def open(self):
        multi_manager.add_ws_client(self)
        self.write_message(json.dumps(
            {"type": "init", "accounts": multi_manager.get_all_status()},
            ensure_ascii=False
        ))
    def on_message(self, message): pass
    def on_close(self): multi_manager.remove_ws_client(self)

class MultiAccountListHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Content-Type", "application/json; charset=utf-8")
    def get(self):
        self.write(json.dumps({"accounts": multi_manager.get_all_status()}, ensure_ascii=False))
    def post(self):
        try: body = json.loads(self.request.body.decode("utf-8"))
        except: self.write(json.dumps({"success": False, "message": "JSON錯誤"})); return
        entry = body.get("account_entry", {})
        if not entry: self.write(json.dumps({"success": False, "message": "缺少account_entry"})); return
        import uuid
        aid = entry.get("id") or str(uuid.uuid4())[:8]
        entry["id"] = aid
        _, base_config = load_json()
        merged = _merge_config(base_config, entry)
        self.write(json.dumps(multi_manager.start_account(aid, entry.get("name", aid), merged), ensure_ascii=False))

class MultiAccountControlHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Content-Type", "application/json; charset=utf-8")
    def post(self, account_id):
        action = self.get_argument("action", "stop")
        if action == "stop": result = multi_manager.stop_account(account_id)
        elif action == "remove": result = multi_manager.remove_account(account_id)
        else: result = {"success": False, "message": f"未知動作:{action}"}
        self.write(json.dumps(result, ensure_ascii=False))

class MultiAccountBulkHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Content-Type", "application/json; charset=utf-8")
    def post(self):
        action = self.get_argument("action", "")
        _, base_config = load_json()
        if action == "start_all":
            items = base_config.get("multi_accounts", [])
            if not items: self.write(json.dumps({"success": False, "message": "settings.json 未設定 multi_accounts"})); return
            self.write(json.dumps({"success": True, "results": multi_manager.start_all_from_config(items, base_config)}, ensure_ascii=False))
        elif action == "stop_all":
            multi_manager.stop_all()
            self.write(json.dumps({"success": True}))
        else:
            self.write(json.dumps({"success": False, "message": f"未知:{action}"}))

class MultiAccountConfigHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Content-Type", "application/json; charset=utf-8")
    def get(self):
        _, config_dict = load_json()
        self.write(json.dumps({"multi_accounts": config_dict.get("multi_accounts", [])}, ensure_ascii=False))
    def post(self):
        try: body = json.loads(self.request.body.decode("utf-8"))
        except: self.write(json.dumps({"success": False, "message": "JSON錯誤"})); return
        config_path, config_dict = load_json()
        config_dict["multi_accounts"] = body.get("multi_accounts", [])
        util.save_json(config_dict, config_path)
        self.write(json.dumps({"success": True}))
        
class MultiAccountPauseHandler(tornado.web.RequestHandler):
    """暫停單一帳號的搶票（寫入暫停檔，bot 偵測到後會進入 idle 狀態）"""
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Content-Type", "application/json; charset=utf-8")
    def post(self, account_id):
        import tempfile
        pause_file = os.path.join(tempfile.gettempdir(), f"cakehunt_pause_{account_id}.txt")
        try:
            with open(pause_file, "w") as f:
                f.write("")
            # 同時更新 multi_manager 的狀態顯示
            acc = multi_manager.get_account(account_id)
            if acc:
                from multi_account_manager import STATUS_PAUSED
                acc.status = STATUS_PAUSED
                acc.add_log("[MultiAccount] 已送出暫停指令")
                multi_manager._broadcast({"type": "status_update", "account": acc.to_dict()})
            self.write(json.dumps({"success": True}))
        except Exception as e:
            self.write(json.dumps({"success": False, "message": str(e)}))

class MultiAccountResumeHandler(tornado.web.RequestHandler):
    """繼續單一帳號的搶票（刪除暫停檔）"""
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Content-Type", "application/json; charset=utf-8")
    def post(self, account_id):
        import tempfile
        pause_file = os.path.join(tempfile.gettempdir(), f"cakehunt_pause_{account_id}.txt")
        try:
            if os.path.exists(pause_file):
                os.remove(pause_file)
            acc = multi_manager.get_account(account_id)
            if acc:
                from multi_account_manager import STATUS_RUNNING
                acc.status = STATUS_RUNNING
                acc.add_log("[MultiAccount] 已送出繼續指令")
                multi_manager._broadcast({"type": "status_update", "account": acc.to_dict()})
            self.write(json.dumps({"success": True}))
        except Exception as e:
            self.write(json.dumps({"success": False, "message": str(e)}))

async def main_server():
    ocr = None
    try:
        ocr = ddddocr.DdddOcr(show_ad=False, beta=True)
    except Exception as exc:
        print(exc)
        pass

    app = Application([
        ("/version", VersionHandler),
        ("/shutdown", ShutdownHandler),
        ("/stop_bot", StopBotHandler),
        ("/sendkey", SendkeyHandler),

        # status api
        ("/status", StatusHandler),
        ("/pause", PauseHandler),
        ("/resume", ResumeHandler),
        (r"/multi_accounts/pause/(.+)",  MultiAccountPauseHandler),
        (r"/multi_accounts/resume/(.+)", MultiAccountResumeHandler),
        ("/run", RunHandler),
        
        # json api
        ("/load", LoadJsonHandler),
        ("/save", SaveJsonHandler),
        ("/reset", ResetJsonHandler),

        ("/test_discord_webhook", TestDiscordWebhookHandler),
        ("/test_telegram", TestTelegramHandler),
        ("/ocr", OcrHandler),
        ("/query", QueryHandler),
        ("/question", QuestionHandler),
        ("/ws/multi",                       MultiAccountWebSocket),
        ("/multi_accounts",                 MultiAccountListHandler),
        (r"/multi_accounts/control/(.+)",   MultiAccountControlHandler),
        ("/multi_accounts/bulk",            MultiAccountBulkHandler),
        ("/multi_accounts/config",          MultiAccountConfigHandler),
        ('/(.*)', NoCacheStaticFileHandler, {"path": os.path.join(SCRIPT_DIR, 'www')}),
    ])
    app.ocr = ocr;
    app.version = CONST_APP_VERSION;

    # Get server_port from config, fallback to default (Issue #156)
    _, config_dict = load_json()
    server_port = config_dict.get("advanced", {}).get("server_port", CONST_SERVER_PORT)

    # Validate port range
    if not isinstance(server_port, int) or server_port < 1024 or server_port > 65535:
        print(f"[WARNING] Invalid server_port: {server_port}, using default: {CONST_SERVER_PORT}")
        server_port = CONST_SERVER_PORT

    app.listen(server_port)
    print("server running on port:", server_port)

    url = "http://127.0.0.1:" + str(server_port) + "/index.html"
    print("goto url:", url)
    webbrowser.open_new(url)
    await asyncio.Event().wait()

def get_server_port():
    """Get server port from config file, fallback to default."""
    _, config_dict = load_json()
    server_port = config_dict.get("advanced", {}).get("server_port", CONST_SERVER_PORT)
    if not isinstance(server_port, int) or server_port < 1024 or server_port > 65535:
        server_port = CONST_SERVER_PORT
    return server_port

def web_server():
    server_port = get_server_port()
    is_port_binded = util.is_connectable(server_port)
    if not is_port_binded:
        asyncio.run(main_server())
    else:
        # port 已被佔用：直接開啟瀏覽器，不重複啟動 server
        import webbrowser
        url = "http://127.0.0.1:" + str(server_port) + "/index.html"
        print("port already in use, opening browser:", url)
        webbrowser.open_new(url)

def settgins_gui_timer():
    while True:
        change_maxbot_status_by_keyword()
        time.sleep(0.4)
        if GLOBAL_SERVER_SHUTDOWN:
            break

if __name__ == "__main__":
    global GLOBAL_SERVER_SHUTDOWN
    GLOBAL_SERVER_SHUTDOWN = False
    
    threading.Thread(target=settgins_gui_timer, daemon=True).start()
    threading.Thread(target=web_server, daemon=True).start()
    
    clean_tmp_file()

    print("To exit web server press Ctrl + C.")
    while True:
        time.sleep(0.4)
        if GLOBAL_SERVER_SHUTDOWN:
            break
    print("Bye bye, see you next time.")