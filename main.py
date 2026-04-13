import os
import json
import asyncio
import urllib.request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from huggingface_hub import HfApi
from flask import Flask
from threading import Thread
import time

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

# --- [ CLOUD DATABASE SETUP (THE PERMANENT FIX) ] ---
DB_FILE = "database.json"
user_name = hf_api.whoami()['name']
DB_REPO_ID = f"{user_name}/KayfHost-DB"

def init_db():
    # Render start hote hi Cloud se purana data download karega
    try:
        hf_api.dataset_info(DB_REPO_ID)
        req = urllib.request.Request(f"https://huggingface.co/datasets/{DB_REPO_ID}/resolve/main/database.json", headers={"Authorization": f"Bearer {HF_TOKEN}"})
        with urllib.request.urlopen(req) as response, open(DB_FILE, 'wb') as out_file:
            out_file.write(response.read())
        print("✅ Cloud Database Loaded Successfully!")
    except Exception as e:
        print("⚠️ No Cloud DB found. Creating new one...")
        hf_api.create_repo(repo_id=DB_REPO_ID, repo_type="dataset", private=True, exist_ok=True)
        save_db({"users": [], "projects": {}})

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: pass
    return {"users": [], "projects": {}}

def save_db(data):
    # Local save
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)
    # Cloud backup (Ye delete nahi hone dega)
    try: hf_api.upload_file(path_or_fileobj=DB_FILE, path_in_repo="database.json", repo_id=DB_REPO_ID, repo_type="dataset")
    except: pass

def add_user(user_id):
    db = load_db()
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)

# Run init_db on startup
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

def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🆕 Create Project", callback_data="new_proj"))
    builder.row(InlineKeyboardButton(text="📁 My Projects", callback_data="my_proj"))
    builder.row(
        InlineKeyboardButton(text="📊 System Status", callback_data="sys_status"), # NEW FEATURE
        InlineKeyboardButton(text="📖 Guide", callback_data="guide")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Donate", callback_data="donate"),
        InlineKeyboardButton(text="📤 Share Bot", url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text=Best%2024/7%20Free%20Bot%20Hosting%20Platform!%20🚀")
    )
    builder.row(
        InlineKeyboardButton(text="👨‍💻 Dev", url=DEV_URL),
        InlineKeyboardButton(text="❓ Help", url=f"https://t.me/{HELP_USER[1:]}")
    )
    return builder.as_markup()

# --- [ BACK BUTTON LOGIC ] ---
@dp.callback_query(F.data == "back_to_main")
async def back_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(f"🔥 **Welcome to KayfHost!**\nDeveloped by Kaif Salmani.\n\nNiche diye gaye buttons se project manage karein:", reply_markup=get_main_menu())

def get_back_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Back to Menu", callback_data="back_to_main")
    return builder.as_markup()

# --- [ ADMIN PANEL ] ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    db = load_db()
    total_users = len(db["users"])
    total_bots = sum(len(bots) for bots in db["projects"].values())
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Broadcast Message", callback_data="admin_broadcast")
    await message.reply(f"👑 **KayfHost Admin**\n\n👥 Users: {total_users}\n🤖 Bots Hosted: {total_bots}", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_broadcast")
async def ask_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID): return
    await callback.message.reply("📝 Broadcast message likhein.")
    await state.set_state(AdminFlow.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminFlow.waiting_for_broadcast)
async def send_broadcast(message: types.Message, state: FSMContext):
    users = load_db()["users"]
    success, fail = 0, 0
    await message.reply(f"⏳ Broadcasting to {len(users)} users...")
    for uid in users:
        try:
            await message.copy_to(uid)
            success += 1
            await asyncio.sleep(0.1)
        except: fail += 1
    await message.reply(f"✅ Complete!\n📩 Sent: {success} | ❌ Failed: {fail}")
    await state.clear()

# --- [ START & COMMANDS ] ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    add_user(str(message.from_user.id))
    if not await check_sub(message.from_user.id):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        builder.row(InlineKeyboardButton(text="✅ Check Joined", callback_data="verify_sub"))
        return await message.reply("🛑 **Access Denied!**\n\nBot use karne ke liye channel join karein.", reply_markup=builder.as_markup())
    
    await message.reply(f"🔥 **Welcome to KayfHost!**\nDeveloped by Kaif Salmani.\n\nNiche diye gaye buttons se project manage karein:", reply_markup=get_main_menu())

@dp.callback_query(F.data == "verify_sub")
async def verify_sub(callback: types.CallbackQuery):
    if await check_sub(callback.from_user.id): await callback.message.edit_text("✅ Verification Successful!", reply_markup=get_main_menu())
    else: await callback.answer("❌ Pehle join toh kar lo bhai!", show_alert=True)

# --- [ MENUS WITH BACK BUTTON ] ---
@dp.callback_query(F.data == "sys_status")
async def sys_status_menu(callback: types.CallbackQuery):
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
    await callback.message.edit_text(status_text, reply_markup=get_back_button())

@dp.callback_query(F.data == "guide")
async def guide_menu(callback: types.CallbackQuery):
    guide_text = "📖 **User Guide**\n\n1️⃣ **Create:** Project banayein.\n2️⃣ **Files:** main.py & requirements.txt bhejein.\n3️⃣ **Update:** My Projects se files badlein.\n\n⚠️ Hum automatically 24/7 pinger lagate hain!"
    await callback.message.edit_text(guide_text, reply_markup=get_back_button())

@dp.callback_query(F.data == "donate")
async def donate_menu(callback: types.CallbackQuery):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}&pn=KayfHost%20Dev"
    msg = await callback.message.reply_photo(photo=qr_url, caption=f"☕ **Support Kaif Salmani**\nUPI: `{UPI_ID}`")
    asyncio.create_task(delete_after(msg, 60))
    await callback.answer("QR Code sent in chat!")

# --- [ PROJECT MANAGEMENT (PLAY FIX & BACK BUTTON) ] ---
@dp.callback_query(F.data == "my_proj")
async def list_projects(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    db = load_db()
    if user_id not in db["projects"] or not db["projects"][user_id]:
        return await callback.message.edit_text("❌ Aapka koi active project nahi hai.", reply_markup=get_back_button())
    
    await callback.message.delete()
    for name, repo_id in db["projects"][user_id].items():
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="▶️ Play", callback_data=f"play_{name}"),
            InlineKeyboardButton(text="⏸ Pause", callback_data=f"pause_{name}")
        )
        builder.row(
            InlineKeyboardButton(text="🔄 Update", callback_data=f"upd_{name}"),
            InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{name}")
        )
        await callback.message.answer(f"📦 **Project:** {name}\n☁️ KayfHost Cloud", reply_markup=builder.as_markup())
    
    # Bottom main Back button
    await callback.message.answer("Navigation:", reply_markup=get_back_button())

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
        elif action == "play": # <-- PLAY BUTTON FIX 
            hf_api.restart_space(repo_id=repo_id)
            await callback.answer(f"▶️ {proj_name} Resuming Server... (Takes 1 min)")
        elif action == "upd":
            await state.update_data(p_name=proj_name, repo_id=repo_id)
            msg = await callback.message.answer(f"🔄 **Update {proj_name}**\n\nNayi **main.py** bhejein:")
            await state.update_data(last_msg_id=msg.message_id)
            await state.set_state(UpdateFlow.waiting_for_py)
            await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Server Error. Try again.", show_alert=True)

# --- [ SMART CLOUD DEPLOYER ] ---
async def deploy_to_cloud(message, p_name, u_id, repo_id, is_new=False):
    deploy_msg = await message.answer(f"⚙️ Building KayfHost Cloud Server for '{p_name}'...")
    try:
        if is_new:
            hf_api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
            db = load_db()
            if str(u_id) not in db["projects"]: db["projects"][str(u_id)] = {}
            db["projects"][str(u_id)][p_name] = repo_id
            save_db(db)
            docker_content = 'FROM python:3.9-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt flask\nCOPY . .\nEXPOSE 7860\nCMD ["python", "main.py"]'
            with open("/tmp/Dockerfile", "w") as f: f.write(docker_content)
            hf_api.upload_file(path_or_fileobj="/tmp/Dockerfile", path_in_repo="Dockerfile", repo_id=repo_id, repo_type="space")

        with open("/tmp/main.py", "r") as f: old_code = f.read()
        hb = "import threading\nfrom flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef h(): return 'OK'\nthreading.Thread(target=lambda: app.run(host='0.0.0.0', port=7860), daemon=True).start()\n"
        with open("/tmp/main.py", "w") as f: f.write(hb + old_code)
        
        for f_name in ["main.py", "requirements.txt"]:
            hf_api.upload_file(path_or_fileobj=f"/tmp/{f_name}", path_in_repo=f_name, repo_id=repo_id, repo_type="space")
        
        await deploy_msg.edit_text("⏳ Server Booting Up... Checking errors...")

        is_live = False
        for i in range(24):
            stage = hf_api.space_info(repo_id).runtime.stage
            if stage == "RUNNING": is_live = True; break
            elif stage in ["RUNTIME_ERROR", "BUILD_ERROR"]: break
            await asyncio.sleep(10)
            
        if is_live: await deploy_msg.edit_text(f"✅ **SUCCESS!**\n\n🚀 '{p_name}' KayfHost Cloud par LIVE hai!")
        else: await deploy_msg.edit_text(f"❌ **CRITICAL ERROR!**\n\nAapke code mein error hai. Server crash ho gaya.")
        asyncio.create_task(delete_after(deploy_msg, 60))
        
    except Exception as e: await deploy_msg.edit_text(f"❌ Cloud API Error!")

# --- [ CREATE & UPDATE LOGIC (AUTO-DELETE CLEANUP) ] ---
@dp.callback_query(F.data == "new_proj")
async def start_new(callback: types.CallbackQuery, state: FSMContext):
    msg = await callback.message.edit_text("📝 Project ka naya Naam batayein:", reply_markup=get_back_button())
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_name)

@dp.message(ProjectFlow.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
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
    await deploy_to_cloud(message, p_name, message.from_user.id, repo_id, is_new=False)

# --- [ SERVER ] ---
app = Flask(__name__)
@app.route('/')
def home(): return "KayfHost Cloud Engine Running!"

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()
    asyncio.run(dp.start_polling(bot))
