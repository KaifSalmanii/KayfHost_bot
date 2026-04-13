import os
import json
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
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

# --- [ DATABASE SETUP (UPGRADED) ] ---
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: pass
    return {"users": [], "projects": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

def add_user(user_id):
    db = load_db()
    if user_id not in db["users"]:
        db["users"].append(user_id)
        save_db(db)

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
        InlineKeyboardButton(text="💰 Donate", callback_data="donate"),
        InlineKeyboardButton(text="📖 Guide", callback_data="guide")
    )
    builder.row(
        InlineKeyboardButton(text="📤 Share Bot", url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text=Best%2024/7%20Free%20Bot%20Hosting%20Platform!%20🚀"),
        InlineKeyboardButton(text="👨‍💻 Dev", url=DEV_URL)
    )
    builder.row(InlineKeyboardButton(text="❓ Help", url=f"https://t.me/{HELP_USER[1:]}"))
    return builder.as_markup()

# --- [ ADMIN PANEL ] ---
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return await message.reply("❌ You are not authorized.")
    
    db = load_db()
    total_users = len(db["users"])
    total_bots = sum(len(bots) for bots in db["projects"].values())
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Broadcast Message", callback_data="admin_broadcast")
    
    stats = f"👑 **KayfHost Admin Panel**\n\n👥 Total Users: {total_users}\n🤖 Total Bots Hosted: {total_bots}"
    await message.reply(stats, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_broadcast")
async def ask_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID): return
    await callback.message.reply("📝 Broadcast message likhein. (Text ya Photo)")
    await state.set_state(AdminFlow.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminFlow.waiting_for_broadcast)
async def send_broadcast(message: types.Message, state: FSMContext):
    db = load_db()
    users = db["users"]
    success, fail = 0, 0
    await message.reply(f"⏳ Broadcasting to {len(users)} users...")
    
    for uid in users:
        try:
            await message.copy_to(uid)
            success += 1
            await asyncio.sleep(0.1) # Anti-spam
        except: fail += 1
        
    await message.reply(f"✅ Broadcast Complete!\n\n📩 Sent: {success}\n❌ Failed: {fail}")
    await state.clear()

# --- [ START & MENUS ] ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    add_user(str(message.from_user.id))
    
    if not await check_sub(message.from_user.id):
        builder = InlineKeyboardBuilder()
        builder.button(text="📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
        builder.button(text="✅ Check Joined", callback_data="verify_sub")
        return await message.reply("🛑 **Access Denied!**\n\nBot use karne ke liye pehle hamara channel join karein.", reply_markup=builder.as_markup())
    
    await message.reply(f"🔥 **Welcome to KayfHost!**\nDeveloped by Kaif Salmani.\n\nNiche diye gaye buttons se project manage karein:", reply_markup=get_main_menu())

@dp.callback_query(F.data == "verify_sub")
async def verify_sub(callback: types.CallbackQuery):
    if await check_sub(callback.from_user.id):
        await callback.message.edit_text("✅ Verification Successful! Welcome.", reply_markup=get_main_menu())
    else:
        await callback.answer("❌ Pehle join toh kar lo bhai!", show_alert=True)

@dp.callback_query(F.data == "guide")
async def guide_menu(callback: types.CallbackQuery):
    guide_text = "📖 **KayfHost User Guide**\n\n1️⃣ **Create:** Project banayein.\n2️⃣ **main.py & req:** Apni files bhejein.\n3️⃣ **Update:** My Projects mein jake code update karein.\n4️⃣ **Errors:** Agar code mein galti hui, toh bot turant bata dega.\n\n⚠️ Hum 24/7 pinger khud lagate hain!"
    msg = await callback.message.answer(guide_text)
    asyncio.create_task(delete_after(msg, 60)) 
    await callback.answer()

@dp.callback_query(F.data == "donate")
async def donate_menu(callback: types.CallbackQuery):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}&pn=KayfHost%20Dev"
    msg = await callback.message.reply_photo(photo=qr_url, caption=f"☕ **Support Kaif Salmani**\n\nUPI: `{UPI_ID}`\n\n*Auto-delete in 2 mins.*")
    asyncio.create_task(delete_after(msg, 120))
    await callback.answer()

# --- [ PROJECT MANAGEMENT (Update / Play / Pause / Delete) ] ---
@dp.callback_query(F.data == "my_proj")
async def list_projects(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    db = load_db()
    if user_id not in db["projects"] or not db["projects"][user_id]:
        msg = await callback.message.answer("❌ Aapka koi project nahi hai.")
        asyncio.create_task(delete_after(msg, 10))
        return await callback.answer()
    
    for name, repo_id in db["projects"][user_id].items():
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="▶️ Play", callback_data=f"play_{name}"),
            InlineKeyboardButton(text="⏸ Pause", callback_data=f"pause_{name}")
        )
        builder.row(
            InlineKeyboardButton(text="🔄 Update Files", callback_data=f"upd_{name}"),
            InlineKeyboardButton(text="🗑 Delete", callback_data=f"del_{name}")
        )
        await callback.message.answer(f"📦 **Project:** {name}\n☁️ KayfHost Cloud Server", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith(("pause_", "play_", "del_", "upd_")))
async def handle_actions(callback: types.CallbackQuery, state: FSMContext):
    action, proj_name = callback.data.split("_")
    user_id = str(callback.from_user.id)
    db = load_db()
    
    try:
        repo_id = db["projects"][user_id][proj_name]
    except KeyError:
        return await callback.answer("❌ Project not found.", show_alert=True)

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
            hf_api.request_space_hardware(repo_id=repo_id, hardware="cpu-basic")
            await callback.answer(f"▶️ {proj_name} Resuming...")
        elif action == "upd":
            await state.update_data(p_name=proj_name, repo_id=repo_id)
            msg = await callback.message.answer(f"🔄 **Update {proj_name}**\n\nNayi **main.py** file bhejein:")
            await state.update_data(last_msg_id=msg.message_id)
            await state.set_state(UpdateFlow.waiting_for_py)
            await callback.answer()
    except Exception as e:
        await callback.answer(f"❌ Server Error. Try again.", show_alert=True)

# --- [ SMART CLOUD DEPLOYER (The Core Engine) ] ---
async def deploy_to_cloud(message, p_name, u_id, repo_id, is_new=False):
    deploy_msg = await message.answer(f"⚙️ Building KayfHost Cloud Server for '{p_name}'...\n\n*Checking code safety...*")
    
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

        # Smart Heartbeat Injector
        with open("/tmp/main.py", "r") as f: old_code = f.read()
        hb = "import threading\nfrom flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef h(): return 'OK'\nthreading.Thread(target=lambda: app.run(host='0.0.0.0', port=7860), daemon=True).start()\n"
        with open("/tmp/main.py", "w") as f: f.write(hb + old_code)
        
        # Uploading Files
        for f_name in ["main.py", "requirements.txt"]:
            hf_api.upload_file(path_or_fileobj=f"/tmp/{f_name}", path_in_repo=f_name, repo_id=repo_id, repo_type="space")
        
        await deploy_msg.edit_text("⏳ Server Booting Up... (Takes 1-3 mins). Checking errors...")

        # --- SMART STATUS CHECKER ---
        is_live = False
        for i in range(24): # Polling for 4 minutes max (10s intervals)
            info = hf_api.space_info(repo_id)
            stage = info.runtime.stage
            
            if stage == "RUNNING":
                is_live = True
                break
            elif stage in ["RUNTIME_ERROR", "BUILD_ERROR"]:
                break
                
            if i % 2 == 0: await deploy_msg.edit_text(f"⏳ Booting Up... [Checking {i*10}s]\nStatus: Booting...")
            await asyncio.sleep(10)
            
        if is_live:
            await deploy_msg.edit_text(f"✅ **SUCCESS!**\n\n🚀 Aapka bot **'{p_name}'** KayfHost Cloud par LIVE hai aur 24/7 chal raha hai!\n*(This message auto-deletes in 60s)*")
        else:
            await deploy_msg.edit_text(f"❌ **CRITICAL ERROR!**\n\nAapke bot code ya requirements.txt mein error hai jiski wajah se server crash ho gaya. \n\n*Kripya 'My Projects' mein jakar Update button dabayein aur sahi files bhejein.*")
        
        asyncio.create_task(delete_after(deploy_msg, 60))
        
    except Exception as e:
        await deploy_msg.edit_text(f"❌ Cloud API Error! Please try again later.")

# --- [ CREATE NEW BOT LOGIC ] ---
@dp.callback_query(F.data == "new_proj")
async def start_new(callback: types.CallbackQuery, state: FSMContext):
    msg = await callback.message.answer("📝 Project ka naya Naam batayein:")
    await state.update_data(last_msg_id=msg.message_id)
    await state.set_state(ProjectFlow.waiting_for_name)
    await callback.answer()

@dp.message(ProjectFlow.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try: await bot.delete_message(message.chat.id, data['last_msg_id'])
    except: pass
    await message.delete()

    await state.update_data(p_name=message.text)
    msg = await message.answer(f"📤 Project **'{message.text}'** ke liye apni **main.py** file bhejein:")
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

# --- [ UPDATE BOT LOGIC ] ---
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
