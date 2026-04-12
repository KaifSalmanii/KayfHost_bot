import os
import json
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from huggingface_hub import HfApi
from flask import Flask
from threading import Thread

# --- [ CONFIG & CREDENTIALS ] ---
TELEGRAM_TOKEN = os.environ.get('BOT_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')
CHANNEL_USERNAME = "@kaifsalmaniii"
UPI_ID = "kaifsalmani@ptyes"
DEV_URL = "https://kaifsalmani-donation.blogspot.com/?m=1"
HELP_USER = "@KaifSalmanii"
BOT_USERNAME = "KayfHostBot" 

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
hf_api = HfApi(token=HF_TOKEN)

# --- [ DATABASE SETUP ] ---
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

# --- [ FSM STATES ] ---
class ProjectFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_py = State()
    waiting_for_req = State()

# --- [ HELPER: AUTO DELETE MESSAGE ] ---
async def delete_after(message: types.Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

# --- [ HELPER: FORCE SUB CHECK ] ---
async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

# --- [ KEYBOARDS ] ---
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

# --- [ COMMANDS ] ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    is_joined = await check_sub(message.from_user.id)
    if not is_joined:
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

# --- [ GUIDE OPTION ] ---
@dp.callback_query(F.data == "guide")
async def guide_menu(callback: types.CallbackQuery):
    guide_text = (
        "📖 **KayfHost User Guide**\n\n"
        "1️⃣ **Create Project:** Button par click karein aur project ka ek unique naam dein.\n"
        "2️⃣ **main.py:** Apni bot ki main file bhejein.\n"
        "3️⃣ **requirements.txt:** Saari libraries ki list bhejein.\n"
        "4️⃣ **Wait:** 2 minute mein aapka bot Hugging Face par live ho jayega.\n\n"
        "⚠️ **Note:** Hum automatically 'Flask Heartbeat' add karte hain taaki bot 24/7 chalta rahe."
    )
    msg = await callback.message.answer(guide_text)
    asyncio.create_task(delete_after(msg, 60)) 
    await callback.answer()

# --- [ DONATION & QR ] ---
@dp.callback_query(F.data == "donate")
async def donate_menu(callback: types.CallbackQuery):
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}&pn=KayfHost%20Dev"
    msg = await callback.message.reply_photo(
        photo=qr_url, 
        caption=f"☕ **Support Kaif Salmani**\n\nUPI ID: `{UPI_ID}`\n\n*Yeh message 2 minute mein auto-delete ho jayega.*"
    )
    asyncio.create_task(delete_after(msg, 120))
    await callback.answer()

# --- [ PROJECT MANAGEMENT ] ---
@dp.callback_query(F.data == "my_proj")
async def list_projects(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    db = load_db()
    if user_id not in db or not db[user_id]:
        msg = await callback.message.answer("❌ Aapka koi project nahi hai.")
        asyncio.create_task(delete_after(msg, 10))
        return await callback.answer()
    
    for name, repo_id in db[user_id].items():
        builder = InlineKeyboardBuilder()
        builder.button(text="🗑 Delete", callback_data=f"del_{name}")
        await callback.message.answer(f"📦 **Project:** {name}\n🔗 ID: `{repo_id}`", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def handle_delete(callback: types.CallbackQuery):
    proj_name = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    db = load_db()
    try:
        hf_api.delete_repo(repo_id=db[user_id][proj_name], repo_type="space")
        del db[user_id][proj_name]
        save_db(db)
        await callback.message.edit_text(f"✅ {proj_name} Successfully Deleted!")
        await asyncio.sleep(5)
        await callback.message.delete()
    except Exception as e: # FIXED THE TYPO HERE
        await callback.answer(f"❌ Error: {str(e)}", show_alert=True)

# --- [ DEPLOYMENT LOGIC ] ---
@dp.callback_query(F.data == "new_proj")
async def start_new(callback: types.CallbackQuery, state: FSMContext):
    msg = await callback.message.answer("📝 Project ka Naam batayein:")
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

    deploy_msg = await message.answer("⚙️ Deploying... Please wait.")
    file = await bot.get_file(message.document.file_id)
    await bot.download_file(file.file_path, "/tmp/requirements.txt")
    
    p_name, u_id = data['p_name'], str(message.from_user.id)
    db = load_db()
    
    try:
        user_name = hf_api.whoami()['name']
        repo_id = f"{user_name}/u{u_id}-{p_name.replace(' ', '')}"
        hf_api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
        
        docker_content = 'FROM python:3.9-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt flask\nCOPY . .\nEXPOSE 7860\nCMD ["python", "main.py"]'
        with open("/tmp/Dockerfile", "w") as f: f.write(docker_content)
        
        with open("/tmp/main.py", "r") as f: old_code = f.read()
        hb = "import threading\nfrom flask import Flask\napp = Flask(__name__)\n@app.route('/')\ndef h(): return 'OK'\nthreading.Thread(target=lambda: app.run(host='0.0.0.0', port=7860), daemon=True).start()\n"
        with open("/tmp/main.py", "w") as f: f.write(hb + old_code)
        
        for f_name in ["main.py", "requirements.txt", "Dockerfile"]:
            hf_api.upload_file(path_or_fileobj=f"/tmp/{f_name}", path_in_repo=f_name, repo_id=repo_id, repo_type="space")
        
        if u_id not in db: db[u_id] = {}
        db[u_id][p_name] = repo_id
        save_db(db)
        await deploy_msg.edit_text(f"🚀 **{p_name}** Live ho gaya!\n\nYeh message 1 minute mein delete ho jayega.")
        asyncio.create_task(delete_after(deploy_msg, 60))
    except Exception as e:
        await deploy_msg.edit_text(f"❌ Failed: {str(e)}")
    await state.clear()

# --- [ SERVER ] ---
app = Flask(__name__)
@app.route('/')
def home(): return "KayfHost Master Running!"

if __name__ == "__main__":
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))).start()
    asyncio.run(dp.start_polling(bot))
    
