import os
import json
import asyncio
import urllib.request
import re
from urllib.error import URLError
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from huggingface_hub import HfApi
from flask import Flask
from threading import Thread

# --- [ CONFIG & CREDENTIALS ] ---
TELEGRAM_TOKEN = os.environ.get('BOT_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID', '0')
UPI_ID = "kaifsalmani@ptyes"
DEV_URL = "https://kaifsalmani-donation.blogspot.com/?m=1"
HELP_USER = "@KaifSalmanii"
BOT_USERNAME = "KayfHostBot"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
hf_api = HfApi(token=HF_TOKEN)

# --- [ CLOUD DATABASE SETUP ] ---
DB_FILE = "database.json"
user_name = hf_api.whoami()['name']
DB_REPO_ID = f"{user_name}/KayfHost-DB"

def init_db():
    try:
        hf_api.dataset_info(DB_REPO_ID)
        req = urllib.request.Request(f"https://huggingface.co/datasets/{DB_REPO_ID}/resolve/main/database.json", headers={"Authorization": f"Bearer {HF_TOKEN}"})
        with urllib.request.urlopen(req) as response, open(DB_FILE, 'wb') as out_file: out_file.write(response.read())
    except Exception:
        hf_api.create_repo(repo_id=DB_REPO_ID, repo_type="dataset", private=True, exist_ok=True)
        default_db = {"users": [], "projects": {}, "blocked": [], "settings": {"force_channel": "@kaifsalmaniii"}}
        save_db(default_db)

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: 
                data = json.load(f)
                if "settings" not in data: data["settings"] = {"force_channel": "@kaifsalmaniii"}
                if "blocked" not in data: data["blocked"] = []
                return data
        except: pass
    return {"users": [], "projects": {}, "blocked": [], "settings": {"force_channel": "@kaifsalmaniii"}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)
    try: hf_api.upload_file(path_or_fileobj=DB_FILE, path_in_repo="database.json", repo_id=DB_REPO_ID, repo_type="dataset")
    except: pass

def is_blocked(user_id):
    return str(user_id) in load_db().get("blocked", [])

init_db()

# --- [ PINGER ENGINE ] ---
async def anti_sleep_engine():
    while True:
        try:
            db = load_db()
            for uid, projects in db.get("projects", {}).items():
                for p_data in projects.values():
                    try:
                        repo_id = p_data["repo_id"] if isinstance(p_data, dict) else p_data
                        space_slug = repo_id.split("/")[-1].replace("_", "-")
                        urllib.request.urlopen(f"https://{user_name}-{space_slug}.hf.space", timeout=5)
                    except: pass
        except: pass
        await asyncio.sleep(600)

# --- [ AUTO-REQUIREMENTS ENGINE ] ---
STD_LIBS = {"os","sys","time","json","re","math","random","asyncio","threading","urllib","datetime","traceback","logging"}
LIB_MAP = {"telebot": "pyTelegramBotAPI", "bs4": "beautifulsoup4", "cv2": "opencv-python"}

def extract_requirements(code):
    imports = set(re.findall(r'^(?:from|import)\s+([a-zA-Z0-9_]+)', code, re.MULTILINE))
    reqs = []
    for imp in imports:
        if imp not in STD_LIBS:
            reqs.append(LIB_MAP.get(imp, imp))
    return list(set(reqs))

# --- [ FSM STATES ] ---
class ProjectFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_bot_username = State()
    waiting_for_code = State()
    waiting_for_req_choice = State()
    waiting_for_manual_req = State()

class AdminFlow(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_block = State()
    waiting_for_unblock = State()
    waiting_for_channel = State()

class UpdateFlow(StatesGroup):
    waiting_for_code = State()
    waiting_for_req_choice = State()
    waiting_for_manual_req = State()

# --- [ HELPERS ] ---
async def delete_after(message: types.Message, delay: int):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

async def check_sub(user_id):
    db = load_db()
    channel = db.get("settings", {}).get("force_channel", "")
    if not channel: return True
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def get_main_menu():
    kb = [[KeyboardButton(text="🆕 Create Project"), KeyboardButton(text="📁 My Projects")],
          [KeyboardButton(text="📊 System Status"), KeyboardButton(text="📖 Guide")],
          [KeyboardButton(text="💰 Donate"), KeyboardButton(text="🔗 Useful Links")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cancel_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Cancel")]], resize_keyboard=True)

MENU_BTNS = ["🆕 Create Project", "📁 My Projects", "📊 System Status", "📖 Guide", "💰 Donate", "🔗 Useful Links", "❌ Cancel"]

# --- [ ADMIN PANEL ] ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    db = load_db()
    users, bots, blocked = len(db["users"]), sum(len(b) for b in db["projects"].values()), len(db["blocked"])
    
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📢 Broadcast", callback_data="adm_bc"), InlineKeyboardButton(text="🔄 Change Channel", callback_data="adm_ch"))
    b.row(InlineKeyboardButton(text="🚫 Block User", callback_data="adm_block"), InlineKeyboardButton(text="✅ Unblock User", callback_data="adm_unblock"))
    b.row(InlineKeyboardButton(text="📋 Users & Bots List", callback_data="adm_list"))
    
    await message.reply(f"👑 **KayfHost Admin Panel**\n\n👥 Users: {users} | 🤖 Bots: {bots}\n🚫 Blocked: {blocked}\n📢 Channel: {db['settings'].get('force_channel', 'None')}", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("adm_"))
async def admin_actions(callback: types.CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID): return
    action = callback.data.split("_")[1]
    
    if action == "list":
        db = load_db()
        text = "📋 **Users & Bots:**\n"
        for uid, projs in db["projects"].items():
            if projs:
                text += f"\n👤 User: `{uid}`\n"
                for pname, pdata in projs.items():
                    b_user = pdata.get('bot_username', 'Unknown') if isinstance(pdata, dict) else 'Unknown'
                    text += f" ├ {pname} ({b_user})\n"
        await callback.message.answer(text[:4000])
        
    elif action == "bc":
        await callback.message.reply("📝 Send Broadcast Message:", reply_markup=get_cancel_menu())
        await state.set_state(AdminFlow.waiting_for_broadcast)
    elif action == "block":
        await callback.message.reply("🚫 Send User ID to block:", reply_markup=get_cancel_menu())
        await state.set_state(AdminFlow.waiting_for_block)
    elif action == "unblock":
        await callback.message.reply("✅ Send User ID to unblock:", reply_markup=get_cancel_menu())
        await state.set_state(AdminFlow.waiting_for_unblock)
    elif action == "ch":
        await callback.message.reply("🔄 Send new Channel Username (with @):", reply_markup=get_cancel_menu())
        await state.set_state(AdminFlow.waiting_for_channel)
    await callback.answer()

@dp.message(AdminFlow.waiting_for_broadcast)
async def adm_do_bc(m: types.Message, state: FSMContext):
    if m.text == "❌ Cancel": return await state.clear()
    users = load_db()["users"]
    msg = await m.reply("🚀 Broadcasting...")
    s, f = 0, 0
    for u in users:
        try: await m.copy_to(u); s += 1; await asyncio.sleep(0.1)
        except: f += 1
    await msg.edit_text(f"✅ Success: {s} | ❌ Fail: {f}")
    await state.clear()

@dp.message(AdminFlow.waiting_for_block)
async def adm_do_block(m: types.Message, state: FSMContext):
    if m.text == "❌ Cancel": return await state.clear()
    db = load_db()
    if m.text not in db["blocked"]: db["blocked"].append(m.text)
    save_db(db)
    await m.reply(f"🚫 User {m.text} Blocked!", reply_markup=get_main_menu())
    await state.clear()

@dp.message(AdminFlow.waiting_for_unblock)
async def adm_do_unblock(m: types.Message, state: FSMContext):
    if m.text == "❌ Cancel": return await state.clear()
    db = load_db()
    if m.text in db["blocked"]: db["blocked"].remove(m.text)
    save_db(db)
    await m.reply(f"✅ User {m.text} Unblocked!", reply_markup=get_main_menu())
    await state.clear()

@dp.message(AdminFlow.waiting_for_channel)
async def adm_do_ch(m: types.Message, state: FSMContext):
    if m.text == "❌ Cancel": return await state.clear()
    db = load_db()
    db["settings"]["force_channel"] = m.text
    save_db(db)
    await m.reply(f"🔄 Force Sub Channel updated to: {m.text}", reply_markup=get_main_menu())
    await state.clear()

# --- [ GLOBAL MENU ] ---
@dp.message(CommandStart(), StateFilter("*"))
async def start_cmd(m: types.Message, state: FSMContext):
    if is_blocked(m.from_user.id): return await m.reply("🚫 BANNED.")
    await state.clear()
    db = load_db()
    if str(m.from_user.id) not in db["users"]: db["users"].append(str(m.from_user.id)); save_db(db)
    
    if not await check_sub(m.from_user.id):
        b = InlineKeyboardBuilder()
        ch = db["settings"].get("force_channel", "")
        b.row(InlineKeyboardButton(text="📢 Join Channel", url=f"https://t.me/{ch[1:]}"))
        b.row(InlineKeyboardButton(text="✅ Check Joined", callback_data="verify_sub"))
        return await m.reply("🛑 **Access Denied!** Join channel first.", reply_markup=b.as_markup())
    await m.reply(f"🔥 **Welcome to KayfHost!**\nDeveloped by Kaif Salmani.", reply_markup=get_main_menu())

@dp.callback_query(F.data == "verify_sub")
async def verify_sub(c: types.CallbackQuery):
    if is_blocked(c.from_user.id): return
    if await check_sub(c.from_user.id): 
        await c.message.delete(); await c.message.answer("✅ Verified!", reply_markup=get_main_menu())
    else: await c.answer("❌ Please join first!", show_alert=True)

@dp.message(F.text == "❌ Cancel", StateFilter("*"))
async def cancel_action(m: types.Message, state: FSMContext):
    await state.clear()
    msg = await m.reply("🚫 Action cancelled.", reply_markup=get_main_menu())
    asyncio.create_task(delete_after(m, 1)); asyncio.create_task(delete_after(msg, 3))

@dp.message(F.text == "📊 System Status", StateFilter("*"))
async def sys_status_menu(m: types.Message, state: FSMContext):
    if is_blocked(m.from_user.id): return await m.reply("🚫 BANNED.")
    await state.clear(); db = load_db()
    bots = sum(len(b) for b in db["projects"].values())
    await m.reply(f"📊 **Cloud Status**\n🟢 Server: Online\n🤖 Bots Live: {bots}\n⚡ Ping: Ultra-Fast (Anti-Sleep)")
    asyncio.create_task(delete_after(m, 1))

@dp.message(F.text == "📖 Guide", StateFilter("*"))
async def guide_menu(m: types.Message, state: FSMContext):
    if is_blocked(m.from_user.id): return
    await state.clear()
    await m.reply("📖 **Guide:**\n1. Use 'Create Project'\n2. Upload file OR Paste Code\n3. Bot Auto-detects Requirements!\n4. We log errors if your code crashes.")
    asyncio.create_task(delete_after(m, 1))

@dp.message(F.text == "💰 Donate", StateFilter("*"))
async def donate_menu(m: types.Message, state: FSMContext):
    if is_blocked(m.from_user.id): return
    await state.clear()
    qr = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}"
    await m.reply_photo(photo=qr, caption=f"💰 UPI: `{UPI_ID}`")
    asyncio.create_task(delete_after(m, 1))

@dp.message(F.text == "🔗 Useful Links", StateFilter("*"))
async def links_menu(m: types.Message, state: FSMContext):
    if is_blocked(m.from_user.id): return
    await state.clear(); b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📤 Share Bot", url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text=Best%20Host"))
    b.row(InlineKeyboardButton(text="👨‍💻 Dev", url=DEV_URL), InlineKeyboardButton(text="❓ Help", url=f"https://t.me/{HELP_USER[1:]}"))
    await m.reply("🔗 **Links:**", reply_markup=b.as_markup())
    asyncio.create_task(delete_after(m, 1))

# --- [ PROJECT MANAGEMENT & LOG VIEWER ] ---
@dp.message(F.text == "📁 My Projects", StateFilter("*"))
async def list_projects(m: types.Message, state: FSMContext):
    if is_blocked(m.from_user.id): return await m.reply("🚫 BANNED.")
    await state.clear(); asyncio.create_task(delete_after(m, 1))
    db = load_db(); uid = str(m.from_user.id)
    if uid not in db["projects"] or not db["projects"][uid]: return await m.reply("❌ No active projects.")
    
    for pname, pdata in db["projects"][uid].items():
        b_user = pdata.get('bot_username', '') if isinstance(pdata, dict) else ''
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="▶️ Play", callback_data=f"play_{pname}"), InlineKeyboardButton(text="⏸ Pause", callback_data=f"pause_{pname}"))
        b.row(InlineKeyboardButton(text="🔄 Update", callback_data=f"upd_{pname}"), InlineKeyboardButton(text="📄 View Logs", callback_data=f"log_{pname}"))
        b.row(InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{pname}"))
        title = f"📦 **Project:** {pname}\n🤖 Bot: {b_user}" if b_user else f"📦 **Project:** {pname}"
        await m.answer(title, reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith(("pause_", "play_", "del_", "upd_", "log_")))
async def handle_actions(c: types.CallbackQuery, state: FSMContext):
    act, pname = c.data.split("_"); uid = str(c.from_user.id); db = load_db()
    try: 
        pdata = db["projects"][uid][pname]
        repo_id = pdata["repo_id"] if isinstance(pdata, dict) else pdata
    except: return await c.answer("❌ Project not found.", show_alert=True)

    try:
        if act == "del":
            hf_api.delete_repo(repo_id=repo_id, repo_type="space")
            del db["projects"][uid][pname]; save_db(db)
            await c.message.edit_text(f"✅ {pname} Deleted.")
        elif act == "pause": hf_api.pause_space(repo_id=repo_id); await c.answer("⏸ Paused.")
        elif act == "play": hf_api.restart_space(repo_id=repo_id); await c.answer("▶️ Starting...")
        elif act == "log":
            try:
                url = f"https://huggingface.co/spaces/{repo_id}/resolve/main/error.log"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {HF_TOKEN}"})
                with urllib.request.urlopen(req) as res: logs = res.read().decode('utf-8')
                if not logs.strip(): logs = "No crashes detected! Bot is healthy."
            except: logs = "No error log file found. System is either healthy or still building."
            await c.message.reply(f"📄 **Logs for {pname}:**\n\n`{logs[-3500:]}`")
            await c.answer()
        elif act == "upd":
            await state.update_data(pname=pname, repo_id=repo_id)
            msg = await c.message.answer("🔄 **Upload `main.py`** OR **Paste Code**:", reply_markup=get_cancel_menu())
            await state.update_data(last_msg_id=msg.message_id)
            await state.set_state(UpdateFlow.waiting_for_code)
            await c.answer()
    except Exception as e: await c.answer(f"Error: {e}", show_alert=True)

# --- [ CLOUD DEPLOYER (THE PRO ENGINE WITH WRAPPER) ] ---
async def deploy_to_cloud(m, pname, uid, repo_id, bot_user="", is_new=False):
    prog = await m.answer("🚀 Deployment: `[⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜] 0%`")
    try:
        if is_new:
            await prog.edit_text("⚙️ Creating Space: `[🟩🟩⬜⬜⬜⬜⬜⬜⬜⬜] 20%`")
            hf_api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
            db = load_db()
            if uid not in db["projects"]: db["projects"][uid] = {}
            db["projects"][uid][pname] = {"repo_id": repo_id, "bot_username": bot_user}
            save_db(db)
            docker = 'FROM python:3.9-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt flask\nCOPY . .\nEXPOSE 7860\nCMD ["python", "run.py"]'
            with open("/tmp/Dockerfile", "w") as f: f.write(docker)
            hf_api.upload_file(path_or_fileobj="/tmp/Dockerfile", path_in_repo="Dockerfile", repo_id=repo_id, repo_type="space")

        await prog.edit_text("📤 Uploading Code Engine: `[🟩🟩🟩🟩🟩🟩⬜⬜⬜⬜] 60%`")
        
        wrapper_code = """import threading\nfrom flask import Flask\nimport traceback\nimport time\nimport sys\n
app = Flask(__name__)\n@app.route('/')\ndef h(): return 'OK'\nthreading.Thread(target=lambda: app.run(host='0.0.0.0', port=7860), daemon=True).start()\n
try:\n    import main\nexcept Exception as e:\n    with open("error.log", "w") as f: f.write(traceback.format_exc())\n    while True: time.sleep(3600)"""
        with open("/tmp/run.py", "w") as f: f.write(wrapper_code)
        with open("/tmp/error.log", "w") as f: f.write("System Started Clean.")
        
        for f_name in ["main.py", "requirements.txt", "run.py", "error.log"]:
            hf_api.upload_file(path_or_fileobj=f"/tmp/{f_name}", path_in_repo=f_name, repo_id=repo_id, repo_type="space")
        
        await prog.edit_text("⏳ Booting Server: `[🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜] 80%`")
        await asyncio.sleep(5)
        await prog.edit_text(f"✅ **SUCCESS!**\n`[🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩] 100%`\n🚀 '{pname}' is LIVE!\n\n*(Agar bot na chale toh 'My Projects' mein jake View Logs check karein)*", reply_markup=get_main_menu())
    except Exception as e: await prog.edit_text(f"❌ Deployment Failed.\nError: {e}", reply_markup=get_main_menu())

# --- [ NEW PROJECT STEP-BY-STEP (Auto-Req & Cleanup) ] ---
@dp.message(F.text == "🆕 Create Project", StateFilter("*"))
async def start_new(m: types.Message, state: FSMContext):
    if is_blocked(m.from_user.id): return await m.reply("🚫 BANNED.")
    await state.clear(); asyncio.create_task(delete_after(m, 1))
    msg = await m.reply("📝 Step 1: Project ka **Naam** batayein:", reply_markup=get_cancel_menu())
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_name)

@dp.message(ProjectFlow.waiting_for_name)
async def get_name(m: types.Message, state: FSMContext):
    if m.text in MENU_BTNS: return await state.clear()
    data = await state.get_data(); asyncio.create_task(delete_after(m, 1))
    try: await bot.delete_message(m.chat.id, data['last_msg_id'])
    except: pass
    await state.update_data(pname=m.text)
    msg = await m.answer(f"🤖 Step 2: Apne naye bot ka **@Username** batayein (Ya 'Skip' likhein):")
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_bot_username)

@dp.message(ProjectFlow.waiting_for_bot_username)
async def get_bot_usr(m: types.Message, state: FSMContext):
    data = await state.get_data(); asyncio.create_task(delete_after(m, 1))
    try: await bot.delete_message(m.chat.id, data['last_msg_id'])
    except: pass
    bot_user = m.text if m.text.lower() != 'skip' else ''
    await state.update_data(buser=bot_user)
    msg = await m.answer("📤 Step 3: **Upload `main.py`** OR **Paste Python Code**:")
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_code)

@dp.message(ProjectFlow.waiting_for_code)
async def get_code(m: types.Message, state: FSMContext):
    data = await state.get_data(); asyncio.create_task(delete_after(m, 1))
    try: await bot.delete_message(m.chat.id, data['last_msg_id'])
    except: pass

    code_content = ""
    if m.document:
        f = await bot.get_file(m.document.file_id)
        await bot.download_file(f.file_path, "/tmp/main.py")
        with open("/tmp/main.py", "r") a
