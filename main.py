import os
import json
import asyncio
import urllib.request
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
CHANNEL_USERNAME = "@kaifsalmaniii"
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
        with urllib.request.urlopen(req) as response, open(DB_FILE, 'wb') as out_file:
            out_file.write(response.read())
    except Exception:
        hf_api.create_repo(repo_id=DB_REPO_ID, repo_type="dataset", private=True, exist_ok=True)
        save_db({"users": [], "projects": {}})

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: pass
    return {"users": [], "projects": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)
    try: hf_api.upload_file(path_or_fileobj=DB_FILE, path_in_repo="database.json", repo_id=DB_REPO_ID, repo_type="dataset")
    except: pass

def add_user(user_id):
    db = load_db()
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)

init_db()

# --- [ 🔴 NEW: ANTI-SLEEP AUTO PINGER ] ---
async def anti_sleep_engine():
    """Ye function har 10 min mein saare bots ko ping karega taaki HF unhe sulaye na"""
    while True:
        try:
            db = load_db()
            for uid, projects in db.get("projects", {}).items():
                for pname, repo_id in projects.items():
                    # Generate HF Direct Space URL for Pinging
                    # Format: username-spacename.hf.space
                    space_slug = repo_id.split("/")[-1].replace("_", "-")
                    ping_url = f"https://{user_name}-{space_slug}.hf.space"
                    try:
                        urllib.request.urlopen(ping_url, timeout=5)
                    except Exception:
                        pass # Ignore errors, the goal is just to hit the server
        except Exception as e:
            print(f"Pinger Error: {e}")
        
        await asyncio.sleep(600) # Wait 10 minutes

# --- [ FSM STATES ] ---
class ProjectFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_py = State()
    waiting_for_req = State()

class UpdateFlow(StatesGroup):
    waiting_for_py = State()
    waiting_for_req = State()

class AdminFlow(StatesGroup):
    waiting_for_broadcast = State()

# --- [ HELPERS ] ---
async def delete_after(message: types.Message, delay: int):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# --- [ KEYBOARDS ] ---
def get_main_menu():
    kb = [
        [KeyboardButton(text="🆕 Create Project"), KeyboardButton(text="📁 My Projects")],
        [KeyboardButton(text="📊 System Status"), KeyboardButton(text="📖 Guide")],
        [KeyboardButton(text="💰 Donate"), KeyboardButton(text="🔗 Useful Links")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cancel_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Cancel")]], resize_keyboard=True)

MENU_BUTTONS = ["🆕 Create Project", "📁 My Projects", "📊 System Status", "📖 Guide", "💰 Donate", "🔗 Useful Links", "❌ Cancel"]

# --- [ ADMIN PANEL ] ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID): return await message.reply("❌ **Unauthorised Access!**")
    db = load_db()
    total_users, total_bots = len(db["users"]), sum(len(b) for b in db["projects"].values())
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Broadcast Message", callback_data="admin_broadcast")
    await message.reply(f"👑 **Admin Panel**\n👥 Users: {total_users}\n🤖 Bots: {total_bots}", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_broadcast")
async def ask_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID): return
    await callback.message.reply("📝 Broadcast message bhejein:", reply_markup=get_cancel_menu())
    await state.set_state(AdminFlow.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminFlow.waiting_for_broadcast)
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        return await message.reply("🚫 Cancelled.", reply_markup=get_main_menu())
    users = load_db()["users"]
    await message.reply(f"🚀 Broadcasting to {len(users)} users...", reply_markup=get_main_menu())
    success, fail = 0, 0
    for uid in users:
        try:
            await message.copy_to(chat_id=uid)
            success += 1
            await asyncio.sleep(0.1)
        except: fail += 1
    await message.reply(f"✅ Finished!\n🟢 Success: {success}\n🔴 Failed: {fail}")
    await state.clear()

# --- [ GLOBAL COMMANDS & MENUS ] ---
@dp.message(CommandStart(), StateFilter("*"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    add_user(str(message.from_user.id))
    if not await check_sub(message.from_user.id):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        builder.row(InlineKeyboardButton(text="✅ Check Joined", callback_data="verify_sub"))
        return await message.reply("🛑 **Access Denied!**\nJoin channel to use the bot.", reply_markup=builder.as_markup())
    await message.reply(f"🔥 **Welcome to KayfHost!**\nDeveloped by Kaif Salmani.", reply_markup=get_main_menu())

@dp.callback_query(F.data == "verify_sub")
async def verify_sub(callback: types.CallbackQuery):
    if await check_sub(callback.from_user.id): 
        await callback.message.delete()
        await callback.message.answer("✅ Verification Successful!", reply_markup=get_main_menu())
    else: await callback.answer("❌ Please join first!", show_alert=True)

@dp.message(F.text == "❌ Cancel", StateFilter("*"))
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    msg = await message.reply("🚫 Action cancelled.", reply_markup=get_main_menu())
    asyncio.create_task(delete_after(message, 1))

@dp.message(F.text == "📊 System Status", StateFilter("*"))
async def sys_status_menu(message: types.Message, state: FSMContext):
    await state.clear()
    db = load_db()
    total_bots = sum(len(bots) for bots in db["projects"].values())
    await message.reply(f"📊 **Cloud Status**\n\n🟢 Server: Online\n🤖 Bots Live: {total_bots}\n⚡ Ping: Fast (Auto-Pinger Active)\n💾 DB: Cloud-Synced")
    asyncio.create_task(delete_after(message, 1))

@dp.message(F.text == "📖 Guide", StateFilter("*"))
async def guide_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("📖 **Guide:**\n1. You can upload `.py` file OR just paste your code directly in the chat.\n2. We automatically add 24/7 Anti-Sleep pingers to your bot.")
    asyncio.create_task(delete_after(message, 1))

@dp.message(F.text == "💰 Donate", StateFilter("*"))
async def donate_menu(message: types.Message, state: FSMContext):
    await state.clear()
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}"
    await message.reply_photo(photo=qr_url, caption=f"💰 UPI: `{UPI_ID}`")
    asyncio.create_task(delete_after(message, 1))

@dp.message(F.text == "🔗 Useful Links", StateFilter("*"))
async def links_menu(message: types.Message, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📤 Share Bot", url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text=Best%2024/7%20Free%20Bot%20Hosting%20Platform!%20🚀"))
    builder.row(InlineKeyboardButton(text="👨‍💻 Dev", url=DEV_URL), InlineKeyboardButton(text="❓ Help", url=f"https://t.me/{HELP_USER[1:]}"))
    await message.reply("🔗 **Useful Links:**", reply_markup=builder.as_markup())
    asyncio.create_task(delete_after(message, 1))

# --- [ PROJECT MANAGEMENT ] ---
@dp.message(F.text == "📁 My Projects", StateFilter("*"))
async def list_projects(message: types.Message, state: FSMContext):
    await state.clear()
    asyncio.create_task(delete_after(message, 1))
    user_id = str(message.from_user.id)
    db = load_db()
    if user_id not in db["projects"] or not db["projects"][user_id]:
        return await message.reply("❌ No active projects found.")
    
    for name, repo_id in db["projects"][user_id].items():
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="▶️ Play", callback_data=f"play_{name}"), InlineKeyboardButton(text="⏸ Pause", callback_data=f"pause_{name}"))
        builder.row(InlineKeyboardButton(text="🔄 Update", callback_data=f"upd_{name}"), InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{name}"))
        await message.answer(f"📦 **Project:** {name}\n🛡️ Protected by Auto-Pinger", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith(("pause_", "play_", "del_", "upd_")))
async def handle_actions(callback: types.CallbackQuery, state: FSMContext):
    action, proj_name = callback.data.split("_")
    user_id = str(callback.from_user.id)
    db = load_db()
    try: repo_id = db["projects"][user_id][proj_name]
    except KeyError: return await callback.answer("❌ Project not found.", show_alert=True)

    try:
        if action == "del":
            hf_api.delete_repo(repo_id=repo_id, repo_type="space")
            del db["projects"][user_id][proj_name]
            save_db(db)
            await callback.message.edit_text(f"✅ {proj_name} Deleted.")
        elif action == "pause":
            hf_api.pause_space(repo_id=repo_id)
            await callback.answer(f"⏸ {proj_name} Paused.")
        elif action == "play":
            hf_api.restart_space(repo_id=repo_id)
            await callback.answer(f"▶️ {proj_name} Starting...")
        elif action == "upd":
            await state.update_data(p_name=proj_name, repo_id=repo_id)
            msg = await callback.message.answer("🔄 **Upload `main.py` file** OR **Paste your python code** below:", reply_markup=get_cancel_menu())
            await state.update_data(last_msg_id=msg.message_id)
            await state.set_state(UpdateFlow.waiting_for_py)
            await callback.answer()
    except: await callback.answer("Server Error!")

# --- [ DEPLOY LOGIC WITH PROGRESS BAR ] ---
async def deploy_to_cloud(message, p_name, u_id, repo_id, is_new=False):
    prog = await message.answer("🚀 Deployment: `[⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜] 0%`")
    try:
        if is_new:
            await prog.edit_text("⚙️ Creating Space: `[🟩🟩⬜⬜⬜⬜⬜⬜⬜⬜] 20%`")
            hf_api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
            db = load_db()
            if u_id not in db["projects"]: db["projects"][u_id] = {}
            db["projects"][u_id][p_name] = repo_id
            save_db(db)
            docker_content = 'FROM python:3.9-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt flask\nCOPY . .\nEXPOSE 7860\nCMD ["python", "main.py"]'
            with open("/tmp/Dockerfile", "w") as f: f.write(docker_content)
            hf_api.upload_file(path_or_fileobj="/tmp/Dockerfile", path_in_repo="Dockerfile", repo_id=repo_id, repo_type="space")

        await prog.edit_text("📤 Uploading Code: `[🟩🟩🟩🟩🟩🟩⬜⬜⬜⬜] 60%`")
        with open("/tmp/main.py", "r") as f: old_code = f.read()
        hb = "import threading\nfrom flask import Flask\nimport urllib.request\napp = Flask(__name__)\n@app.route('/')\ndef h(): return 'OK'\nthreading.Thread(target=lambda: app.run(host='0.0.0.0', port=7860), daemon=True).start()\n"
        with open("/tmp/main.py", "w") as f: f.write(hb + old_code)
        
        for f_name in ["main.py", "requirements.txt"]:
            hf_api.upload_file(path_or_fileobj=f"/tmp/{f_name}", path_in_repo=f_name, repo_id=repo_id, repo_type="space")
        
        await prog.edit_text("⏳ Booting Server: `[🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜] 80%`")
        await asyncio.sleep(5)
        await prog.edit_text(f"✅ **SUCCESS!**\n`[🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩] 100%`\n🚀 '{p_name}' is LIVE 24/7!")
    except Exception as e: await prog.edit_text(f"❌ Deployment Failed.\nError: {e}")

# --- [ NEW PROJECT LOGIC (WITH PASTE CODE FEATURE) ] ---
@dp.message(F.text == "🆕 Create Project", StateFilter("*"))
async def start_new(message: types.Message, state: FSMContext):
    await state.clear()
    asyncio.create_task(delete_after(message, 1)) # Clean user message
    msg = await message.reply("📝 Enter a unique **Project Name**:", reply_markup=get_cancel_menu())
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_name)

@dp.message(ProjectFlow.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS: return await state.clear()
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    asyncio.create_task(delete_after(message, 1))

    await state.update_data(p_name=message.text)
    msg = await message.answer("📤 **Upload `main.py`** file \n\nOR \n\n💻 **Paste your Python code** directly below:", reply_markup=get_cancel_menu())
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_py)

@dp.message(ProjectFlow.waiting_for_py) # Removed F.document to accept text too
async def get_py(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS: return await state.clear()
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    asyncio.create_task(delete_after(message, 1))

    # Logic to handle File OR Text Paste
    if message.document:
        file = await bot.get_file(message.document.file_id)
        await bot.download_file(file.file_path, "/tmp/main.py")
    elif message.text:
        with open("/tmp/main.py", "w") as f: f.write(message.text)
    else:
        msg = await message.answer("❌ Invalid format. Please send a File or Text Code.")
        return await state.update_data(last_msg_id=msg.message_id)

    msg = await message.answer("📑 **Upload `requirements.txt`** file \n\nOR \n\n📋 **Paste your requirements** (e.g., aiogram flask):", reply_markup=get_cancel_menu())
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_req)

@dp.message(ProjectFlow.waiting_for_req) # Removed F.document
async def get_req(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS: return await state.clear()
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    asyncio.create_task(delete_after(message, 1))

    # Logic to handle File OR Text Paste
    if message.document:
        file = await bot.get_file(message.document.file_id)
        await bot.download_file(file.file_path, "/tmp/requirements.txt")
    elif message.text:
        with open("/tmp/requirements.txt", "w") as f: f.write(message.text)
    else:
        return await message.answer("❌ Invalid format.")

    p_name, u_id = data['p_name'], str(message.from_user.id)
    repo_id = f"{user_name}/u{u_id}-{p_name.replace(' ', '')}"
    await state.clear()
    await message.answer("🚀 Triggering Deploy...", reply_markup=get_main_menu())
    await deploy_to_cloud(message, p_name, u_id, repo_id, is_new=True)

# --- [ UPDATE LOGIC (FILE OR TEXT) ] ---
@dp.message(UpdateFlow.waiting_for_py)
async def upd_py(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS: return await state.clear()
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    asyncio.create_task(delete_after(message, 1))

    if message.document:
        file = await bot.get_file(message.document.file_id)
        await bot.download_file(file.file_path, "/tmp/main.py")
    elif message.text:
        with open("/tmp/main.py", "w") as f: f.write(message.text)

    msg = await message.answer("📑 **Upload `requirements.txt`** file OR **Paste requirements**:", reply_markup=get_cancel_menu())
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(UpdateFlow.waiting_for_req)

@dp.message(UpdateFlow.waiting_for_req)
async def upd_req(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS: return await state.clear()
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    asyncio.create_task(delete_after(message, 1))

    if message.document:
        file = await bot.get_file(message.document.file_id)
        await bot.download_file(file.file_path, "/tmp/requirements.txt")
    elif message.text:
        with open("/tmp/requirements.txt", "w") as f: f.write(message.text)

    await state.clear()
    await message.answer("🔄 Starting Cloud Update...", reply_markup=get_main_menu())
    await deploy_to_cloud(message, data['p_name'], str(message.from_user.id), data['repo_id'], is_new=False)

# --- [ MAIN SERVER & RUNNER ] ---
app = Flask(__name__)
@app.route('/')
def home(): return "KayfHost Master Online!"

async def main():
    # Start the Anti-Sleep Pinger in background
    asyncio.create_task(anti_sleep_engine())
    await dp.start_polling(bot)

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()
    asyncio.run(main())
        
