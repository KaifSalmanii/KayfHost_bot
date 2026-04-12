import os
import json
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from huggingface_hub import HfApi
from flask import Flask
from threading import Thread

# --- [ SETUP ] ---
TELEGRAM_TOKEN = os.environ.get('BOT_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
hf_api = HfApi(token=HF_TOKEN)

# --- [ DATABASE CHOTA SA ] ---
# Asli project mein yahan Firebase use hoga, abhi ke liye JSON use kar rahe hain
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

# --- [ FSM STATES ] ---
class ProjectFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_py = State()
    waiting_for_req = State()

# --- [ 1. START MENU ] ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Create New Project", callback_data="new_proj")
    builder.button(text="📂 My Projects", callback_data="my_proj")
    
    await message.reply("Welcome to KayfHost!\nKya karna chahte hain?", reply_markup=builder.as_markup())

# --- [ 2. NEW PROJECT CLIKED ] ---
@dp.callback_query(F.data == "new_proj")
async def ask_project_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Apne project ka naam batao (e.g., Project X):")
    await state.set_state(ProjectFlow.waiting_for_name)

# --- [ 3. SAVE NAME & ASK .PY ] ---
@dp.message(ProjectFlow.waiting_for_name)
async def ask_for_py(message: types.Message, state: FSMContext):
    project_name = message.text
    await state.update_data(proj_name=project_name)
    
    await message.reply(f"Great! Ab apne '{project_name}' ki **main.py** file bhejo.")
    await state.set_state(ProjectFlow.waiting_for_py)

# --- [ 4. RECEIVE .PY & ASK REQ.TXT ] ---
@dp.message(ProjectFlow.waiting_for_py, F.document)
async def ask_for_req(message: types.Message, state: FSMContext):
    # .py file download karo
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    download_path = f"/tmp/main.py"
    await bot.download_file(file.file_path, download_path)
    
    await message.reply("✅ File received! Ab iski **requirements.txt** file bhejo.")
    await state.set_state(ProjectFlow.waiting_for_req)

# --- [ 5. RECEIVE REQ & DEPLOY ] ---
@dp.message(ProjectFlow.waiting_for_req, F.document)
async def final_deploy(message: types.Message, state: FSMContext):
    msg = await message.reply("⚙️ Uploading files... Please wait.")
    
    # requirements.txt download karo
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    req_path = f"/tmp/requirements.txt"
    await bot.download_file(file.file_path, req_path)
    
    user_data = await state.get_data()
    project_name = user_data['proj_name']
    user_id = str(message.from_user.id)
    
    db = load_db()
    username = hf_api.whoami()['name']
    
    # Check agar project pehle se hai toh wahi update hoga, warna naya space banega
    if user_id in db and project_name in db[user_id]:
        repo_id = db[user_id][project_name]
        await msg.edit_text("🔄 Existing project mila. Updating files...")
    else:
        space_name = f"u{user_id}-{project_name.replace(' ', '')}"
        repo_id = f"{username}/{space_name}"
        hf_api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
        
        # Save to DB
        if user_id not in db: db[user_id] = {}
        db[user_id][project_name] = repo_id
        save_db(db)
        
        # Upload Dockerfile (Is baar chup-chap upload karenge)
        docker_content = 'FROM python:3.9-slim\nRUN useradd -m -u 1000 user\nUSER user\nENV PATH="/home/user/.local/bin:${PATH}"\nWORKDIR /app\nCOPY --chown=user requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY --chown=user . .\nCMD ["python", "main.py"]'
        with open("/tmp/Dockerfile", "w") as f: f.write(docker_content)
        hf_api.upload_file(path_or_fileobj="/tmp/Dockerfile", path_in_repo="Dockerfile", repo_id=repo_id, repo_type="space")

    # Upload main.py and requirements.txt (Ye purani file ko khud overwrite kar dega)
    hf_api.upload_file(path_or_fileobj="/tmp/main.py", path_in_repo="main.py", repo_id=repo_id, repo_type="space")
    hf_api.upload_file(path_or_fileobj=req_path, path_in_repo="requirements.txt", repo_id=repo_id, repo_type="space")
    
    await msg.edit_text(f"✅ **Aapka bot live ho chuka hai!**\n\nIse chalne mein 2-3 minute lagenge.")
    await state.clear()

# ... Flask server code same rahega ...
