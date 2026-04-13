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
ADMIN_ID = os.environ.get('ADMIN_ID', '0') # Render se ID set karein
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

# --- [ ADMIN PANEL BLOCK ] ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return await message.reply("❌ **Unauthorised Access!**\nSirf Kaif Salmani hi is command ko use kar sakte hain.")
    
    db = load_db()
    total_users = len(db["users"])
    total_bots = sum(len(bots) for bots in db["projects"].values())
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Broadcast Message", callback_data="admin_broadcast")
    
    stats = (
        "👑 **KayfHost Admin Panel**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🤖 Total Bots Hosted: {total_bots}\n"
        "🟢 Status: Server Healthy"
    )
    await message.reply(stats, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_broadcast")
async def ask_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID): return
    await callback.message.reply("📝 **Broadcast Logic:**\n\nApna message (text, photo, ya video) niche bhejein. Main ise sabhi users ko bhej dunga.", reply_markup=get_cancel_menu())
    await state.set_state(AdminFlow.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminFlow.waiting_for_broadcast)
async def start_broadcast(message: types.Message, state: FSMContext):
    if message.text == "❌ Cancel":
        await state.clear()
        return await message.reply("🚫 Broadcast Cancelled.", reply_markup=get_main_menu())
    
    db = load_db()
    users = db["users"]
    await message.reply(f"🚀 **Broadcasting started...** (Total: {len(users)})", reply_markup=get_main_menu())
    
    success, fail = 0, 0
    for uid in users:
        try:
            await message.copy_to(chat_id=uid)
            success += 1
            await asyncio.sleep(0.1) # Anti-flood protection
        except:
            fail += 1
            
    await message.reply(f"✅ **Broadcast Finished!**\n\n🟢 Success: {success}\n🔴 Failed: {fail}")
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
    
    await message.reply(f"🔥 **Welcome to KayfHost!**\nDeveloped by Kaif Salmani.\n\nNiche diye gaye options use karein:", reply_markup=get_main_menu())

@dp.message(F.text == "📊 System Status")
async def sys_status_menu(message: types.Message):
    db = load_db()
    total_bots = sum(len(bots) for bots in db["projects"].values())
    await message.reply(f"📊 **Cloud Status**\n\n🟢 Server: Online\n🤖 Bots Live: {total_bots}\n💾 Database: Cloud-Synced")

@dp.message(F.text == "📖 Guide")
async def guide_menu(message: types.Message):
    await message.reply("📖 **Guide:**\n\n1. Name project\n2. Send main.py\n3. Send requirements.txt\nDone! KayfHost handles the rest.")

@dp.message(F.text == "💰 Donate")
async def donate_menu(message: types.Message):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}"
    await message.reply_photo(photo=qr_url, caption=f"💰 UPI: {UPI_ID}")

@dp.message(F.text == "🔗 Useful Links")
async def links_menu(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👨‍💻 Dev", url=DEV_URL), InlineKeyboardButton(text="❓ Help", url=f"https://t.me/{HELP_USER[1:]}"))
    await message.reply("🔗 **Useful Links:**", reply_markup=builder.as_markup())

# --- [ PROJECT MANAGEMENT ] ---
@dp.message(F.text == "📁 My Projects")
async def list_projects(message: types.Message):
    user_id = str(message.from_user.id)
    db = load_db()
    if user_id not in db["projects"] or not db["projects"][user_id]:
        return await message.reply("❌ No active projects found.")
    
    for name, repo_id in db["projects"][user_id].items():
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="▶️ Play", callback_data=f"play_{name}"), InlineKeyboardButton(text="⏸ Pause", callback_data=f"pause_{name}"))
        builder.row(InlineKeyboardButton(text="🔄 Update", callback_data=f"upd_{name}"), InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{name}"))
        await message.answer(f"📦 **Project:** {name}", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith(("pause_", "play_", "del_", "upd_")))
async def handle_actions(callback: types.CallbackQuery, state: FSMContext):
    action, proj_name = callback.data.split("_")
    user_id = str(callback.from_user.id)
    db = load_db()
    repo_id = db["projects"][user_id][proj_name]

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
            await callback.message.answer("🔄 Send new **main.py**:", reply_markup=get_cancel_menu())
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
        hb = "import threading\nfrom flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef h(): return 'OK'\nthreading.Thread(target=lambda: app.run(host='0.0.0.0', port=7860), daemon=True).start()\n"
        with open("/tmp/main.py", "w") as f: f.write(hb + old_code)
        
        for f_name in ["main.py", "requirements.txt"]:
            hf_api.upload_file(path_or_fileobj=f"/tmp/{f_name}", path_in_repo=f_name, repo_id=repo_id, repo_type="space")
        
        await prog.edit_text("⏳ Booting Server: `[🟩🟩🟩🟩🟩🟩🟩🟩⬜⬜] 80%`")
        await asyncio.sleep(5)
        await prog.edit_text(f"✅ **SUCCESS!**\n`[🟩🟩🟩🟩🟩🟩🟩🟩🟩🟩] 100%`\n🚀 {p_name} is LIVE!")
    except: await prog.edit_text("❌ Deployment Failed.")

# --- [ NEW & UPDATE HANDLERS ] ---
@dp.message(F.text == "🆕 Create Project")
async def start_new(message: types.Message, state: FSMContext):
    await message.reply("📝 Enter Project Name:", reply_markup=get_cancel_menu())
    await state.set_state(ProjectFlow.waiting_for_name)

@dp.message(ProjectFlow.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS: return await state.clear()
    await state.update_data(p_name=message.text)
    await message.reply("📤 Send **main.py**:")
    await state.set_state(ProjectFlow.waiting_for_py)

@dp.message(ProjectFlow.waiting_for_py, F.document)
async def get_py(message: types.Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "/tmp/main.py")
    await message.reply("📑 Send **requirements.txt**:")
    await state.set_state(ProjectFlow.waiting_for_req)

@dp.message(ProjectFlow.waiting_for_req, F.document)
async def get_req(message: types.Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "/tmp/requirements.txt")
    data = await state.get_data()
    p_name, u_id = data['p_name'], str(message.from_user.id)
    user_name = hf_api.whoami()['name']
    repo_id = f"{user_name}/u{u_id}-{p_name.replace(' ', '')}"
    await state.clear()
    await message.answer("Starting Deployment...", reply_markup=get_main_menu())
    await deploy_to_cloud(message, p_name, u_id, repo_id, is_new=True)

# Update handlers (Upd_py and Upd_req) also included in logic...
@dp.message(UpdateFlow.waiting_for_py, F.document)
async def upd_py(message: types.Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "/tmp/main.py")
    await message.reply("📑 Send new **requirements.txt**:")
    await state.set_state(UpdateFlow.waiting_for_req)

@dp.message(UpdateFlow.waiting_for_req, F.document)
async def upd_req(message: types.Message, state: FSMContext):
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "/tmp/requirements.txt")
    data = await state.get_data()
    await state.clear()
    await message.answer("Updating Cloud...", reply_markup=get_main_menu())
    await deploy_to_cloud(message, data['p_name'], str(message.from_user.id), data['repo_id'], is_new=False)

# --- [ SERVER ] ---
app = Flask(__name__)
@app.route('/')
def home(): return "KayfHost Running!"

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()
    asyncio.run(dp.start_polling(bot))
