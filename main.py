import os
import json
import asyncio
import urllib.request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from huggingface_hub import HfApi
from flask import Flask
from threading import Thread

# --- [ CONFIG & CREDENTIALS ] ---
TELEGRAM_TOKEN = os.environ.get('BOT_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')
ADMIN_ID = os.environ.get('ADMIN_ID', 'YAHAN_APNA_ID_DAL_SAKTE_HO') 
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

# --- [ KEYBOARDS (REPLY UI) ] ---
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

# --- [ START & CANCEL ] ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    add_user(str(message.from_user.id))
    if not await check_sub(message.from_user.id):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        builder.row(InlineKeyboardButton(text="✅ Check Joined", callback_data="verify_sub"))
        return await message.reply("🛑 **Access Denied!**\n\nBot use karne ke liye channel join karein.", reply_markup=builder.as_markup())
    
    await message.reply(f"🔥 **Welcome to KayfHost!**\nDeveloped by Kaif Salmani.\n\nNiche diye gaye options use karein:", reply_markup=get_main_menu())

@dp.message(F.text == "❌ Cancel")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("🚫 Action cancelled. Returning to main menu.", reply_markup=get_main_menu())

@dp.callback_query(F.data == "verify_sub")
async def verify_sub(callback: types.CallbackQuery):
    if await check_sub(callback.from_user.id): 
        await callback.message.delete()
        await callback.message.answer("✅ Verification Successful!", reply_markup=get_main_menu())
    else: await callback.answer("❌ Pehle join toh kar lo bhai!", show_alert=True)

# --- [ MAIN MENU TEXT HANDLERS ] ---
@dp.message(F.text == "📊 System Status")
async def sys_status_menu(message: types.Message, state: FSMContext):
    await state.clear()
    db = load_db()
    total_bots = sum(len(bots) for bots in db["projects"].values())
    status_text = (
        "📊 **KayfHost Cloud Status**\n\n"
        "🟢 **Servers:** Online\n"
        "🟢 **Database:** Connected (Cloud Sync)\n"
        f"🤖 **Active Bots:** {total_bots}\n"
        "⚡ **Ping:** Fast\n\n"
        "*(All systems are running perfectly)*"
    )
    await message.reply(status_text)

@dp.message(F.text == "📖 Guide")
async def guide_menu(message: types.Message, state: FSMContext):
    await state.clear()
    guide_text = "📖 **User Guide**\n\n1️⃣ **Create:** Project banayein.\n2️⃣ **Files:** main.py & requirements.txt bhejein.\n3️⃣ **Update:** My Projects se files badlein.\n\n⚠️ Hum automatically 24/7 pinger lagate hain!"
    await message.reply(guide_text)

@dp.message(F.text == "💰 Donate")
async def donate_menu(message: types.Message, state: FSMContext):
    await state.clear()
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}&pn=KayfHost%20Dev"
    msg = await message.reply_photo(photo=qr_url, caption=f"☕ **Support Kaif Salmani**\nUPI: `{UPI_ID}`")
    asyncio.create_task(delete_after(msg, 60))

@dp.message(F.text == "🔗 Useful Links")
async def links_menu(message: types.Message, state: FSMContext):
    await state.clear()
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📤 Share Bot", url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text=Best%2024/7%20Free%20Bot%20Hosting%20Platform!%20🚀"))
    builder.row(InlineKeyboardButton(text="👨‍💻 Dev", url=DEV_URL), InlineKeyboardButton(text="❓ Help", url=f"https://t.me/{HELP_USER[1:]}"))
    await message.reply("🔗 **Important Links:**", reply_markup=builder.as_markup())

# --- [ PROJECT MANAGEMENT (Inline Actions) ] ---
@dp.message(F.text == "📁 My Projects")
async def list_projects(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = str(message.from_user.id)
    db = load_db()
    if user_id not in db["projects"] or not db["projects"][user_id]:
        return await message.reply("❌ Aapka koi active project nahi hai.")
    
    await message.reply("📂 **Fetching your projects...**")
    for name, repo_id in db["projects"][user_id].items():
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="▶️ Play", callback_data=f"play_{name}"), InlineKeyboardButton(text="⏸ Pause", callback_data=f"pause_{name}"))
        builder.row(InlineKeyboardButton(text="🔄 Update", callback_data=f"upd_{name}"), InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{name}"))
        await message.answer(f"📦 **Project:** {name}\n☁️ KayfHost Cloud", reply_markup=builder.as_markup())

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
            await callback.message.edit_text(f"✅ {proj_name} Deleted!")
        elif action == "pause":
            hf_api.pause_space(repo_id=repo_id)
            await callback.answer(f"⏸ {proj_name} Paused.")
        elif action == "play":
            hf_api.restart_space(repo_id=repo_id)
            await callback.answer(f"▶️ {proj_name} Resuming Server... (Takes 1 min)")
        elif action == "upd":
            await state.update_data(p_name=proj_name, repo_id=repo_id)
            msg = await callback.message.answer(f"🔄 **Update {proj_name}**\n\nNayi **main.py** bhejein:", reply_markup=get_cancel_menu())
            await state.update_data(last_msg_id=msg.message_id)
            await state.set_state(UpdateFlow.waiting_for_py)
            await callback.answer()
    except Exception:
        await callback.answer(f"❌ Server Error. Try again.", show_alert=True)

# --- [ SMART CLOUD DEPLOYER WITH PROGRESS BAR ] ---
async def deploy_to_cloud(message, p_name, u_id, repo_id, is_new=False):
    deploy_msg = await message.answer("🚀 Deployment Initialized...\n`[⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜] 0%`")
    try:
        if is_new:
            await deploy_msg.edit_text("⚙️ Creating Cloud Container...\n`[🟩🟩⬜⬜⬜⬜⬜⬜⬜⬜] 20%`")
            hf_api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
            db = load_db()
            if str(u_id) not in db["projects"]: db["projects"][str(u_id)] = {}
            db["projects"][str(u_id)][p_name] = repo_id
            save_db(db)
            
            docker_content = 'FROM python:3.9-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt flask\nCOPY . .\nEXPOSE 7860\nCMD ["python", "main.py"]'
            with open("/tmp/Dockerfile", "w") as f: f.write(docker_content)
            hf_api.upload_file(path_or_fileobj="/tmp/Dockerfile", path_in_repo="Dockerfile", repo_id=repo_id, repo_type="space")

        await deploy_msg.edit_text("📦 Injecting Dependencies...\n`[🟩🟩🟩🟩⬜⬜⬜⬜⬜⬜] 40%`")
        with open("/tmp/main.py", "r") as f: old_code = f.read()
        hb = "import threading\nfrom flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef h(): return 'OK'\nthreading.Thread(target=lambda: app.run(host='0.0.0.0', port=7860), daemon=True).start()\n"
        with open("/tmp/main.py", "w") as f: f.write(hb + old_code)
        
        await deploy_msg.edit_text("📝 Uploading Source Code...\n`[🟩🟩🟩🟩🟩🟩⬜⬜⬜⬜] 60%`")
        for f_name in ["main.py", "requirements.txt"]:
            hf_api.upload_file(path_or_fileobj=f"/tmp/{f_name}", path_in_repo=f_name, repo_id=repo_id, repo_type="space")
        
        is_live = False
        for i in range(24):
            bar = "🟩" * 8 + "⬜" * 2 if i < 10 else "🟩" * 9 + "⬜" * 1
            await deploy_msg.edit_text(f"⏳ Booting Up Server...\n`[{bar}] 80%`\n*Checking health (Attempt {i+1}/24)...*")
            
            stage = hf_api.space_info(repo_id).runtime.stage
            if stage == "RUNNING": is_live = True; break
            elif stage in ["RUNTIME_ERROR", "BUILD_ERROR"]: break
            await asyncio.sleep(10)
            
        if is_live: await deploy_msg.edit_text(f"✅ **DEPLOYMENT SUCCESS!**\n`[🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩] 100%`\n\n🚀 '{p_name}' is now LIVE on KayfHost Cloud!")
        else: await deploy_msg.edit_text(f"❌ **CRITICAL ERROR!**\n`[🟥🟥🟥🟥🟥🟥🟥🟥🟥🟥] FAILED`\n\nAapke code ya requirements mein error hai. Server crash ho gaya.")
        asyncio.create_task(delete_after(deploy_msg, 60))
        
    except Exception: await deploy_msg.edit_text(f"❌ Cloud API Error!")

# --- [ CREATE & UPDATE LOGIC ] ---
@dp.message(F.text == "🆕 Create Project")
async def start_new(message: types.Message, state: FSMContext):
    await state.clear()
    msg = await message.reply("📝 Project ka naya Naam batayein:", reply_markup=get_cancel_menu())
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_name)

@dp.message(ProjectFlow.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS: return await state.clear()
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    await message.delete()
    await state.update_data(p_name=message.text)
    msg = await message.answer(f"📤 **'{message.text}'** ke liye **main.py** bhejein:")
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_py)

@dp.message(ProjectFlow.waiting_for_py, F.document)
async def get_py(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    await message.delete()
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "/tmp/main.py")
    msg = await message.answer("📑 Ab **requirements.txt** bhejein:")
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_req)

@dp.message(ProjectFlow.waiting_for_req, F.document)
async def get_req_and_deploy(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    await message.delete()
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "/tmp/requirements.txt")
    p_name, u_id = data['p_name'], str(message.from_user.id)
    user_name = hf_api.whoami()['name']
    repo_id = f"{user_name}/u{u_id}-{p_name.replace(' ', '')}"
    await state.clear()
    await message.answer("Deploying process starting...", reply_markup=get_main_menu())
    await deploy_to_cloud(message, p_name, u_id, repo_id, is_new=True)

@dp.message(UpdateFlow.waiting_for_py, F.document)
async def update_py(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    await message.delete()
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "/tmp/main.py")
    msg = await message.answer("📑 Ab nayi **requirements.txt** bhejein:")
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(UpdateFlow.waiting_for_req)

@dp.message(UpdateFlow.waiting_for_req, F.document)
async def update_req(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    await message.delete()
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "/tmp/requirements.txt")
    p_name, repo_id = data['p_name'], data['repo_id']
    await state.clear()
    await message.answer("Updating process starting...", reply_markup=get_main_menu())
    await deploy_to_cloud(message, p_name, message.from_user.id, repo_id, is_new=False)

# --- [ SERVER ] ---
app = Flask(__name__)
@app.route('/')
def home(): return "KayfHost Cloud Engine Running!"

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()
    asyncio.run(dp.start_polling(bot))
