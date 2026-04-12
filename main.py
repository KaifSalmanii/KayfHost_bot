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

# --- [ CREDENTIALS & SETUP ] ---
TELEGRAM_TOKEN = os.environ.get('BOT_TOKEN')
HF_TOKEN = os.environ.get('HF_TOKEN')

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
hf_api = HfApi(token=HF_TOKEN)

# --- [ DATABASE SETUP ] ---
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: 
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f: 
        json.dump(data, f, indent=4)

# --- [ FSM STATES (Bot ki Memory) ] ---
class ProjectFlow(StatesGroup):
    waiting_for_name = State()
    waiting_for_py = State()
    waiting_for_req = State()

# --- [ 1. START MENU ] ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear() # Purani memory saaf karna
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Create New Project", callback_data="new_proj")
    builder.button(text="📂 My Projects", callback_data="my_proj")
    
    await message.reply("🔥 Welcome to **KayfHost**!\n\nAapka apna auto-hosting platform. Kya karna chahte hain?", reply_markup=builder.as_markup())

# --- [ 2. SHOW EXISTING PROJECTS ] ---
@dp.callback_query(F.data == "my_proj")
async def show_projects(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    db = load_db()
    
    if user_id in db and db[user_id]:
        proj_list = "\n".join([f"🔹 {name}" for name in db[user_id].keys()])
        await callback.message.edit_text(f"📂 **Aapke Projects:**\n\n{proj_list}\n\nUpdate karne ke liye bas naya project banayein aur **same naam** daalein.")
    else:
        await callback.message.edit_text("❌ Aapka koi active project nahi hai. Pehle 'Create New Project' par click karein.")

# --- [ 3. NEW PROJECT CLICKED ] ---
@dp.callback_query(F.data == "new_proj")
async def ask_project_name(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📝 Apne project ka naam batao (e.g., PromoBot):")
    await state.set_state(ProjectFlow.waiting_for_name)

# --- [ 4. SAVE NAME & ASK .PY ] ---
@dp.message(ProjectFlow.waiting_for_name)
async def ask_for_py(message: types.Message, state: FSMContext):
    project_name = message.text
    await state.update_data(proj_name=project_name)
    
    await message.reply(f"Great! Ab apne '{project_name}' ki **main.py** file bhejo.")
    await state.set_state(ProjectFlow.waiting_for_py)

# --- [ 5. RECEIVE .PY & ASK REQ.TXT ] ---
@dp.message(ProjectFlow.waiting_for_py, F.document)
async def ask_for_req(message: types.Message, state: FSMContext):
    if not message.document.file_name.endswith('.py'):
        await message.reply("❌ Sirf .py files allow hain! Dobara bhejo.")
        return
        
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    download_path = f"/tmp/main.py"
    await bot.download_file(file.file_path, download_path)
    
    await message.reply("✅ Code received! Ab iski **requirements.txt** file bhejo.")
    await state.set_state(ProjectFlow.waiting_for_req)

# --- [ 6. RECEIVE REQ & DEPLOY ] ---
@dp.message(ProjectFlow.waiting_for_req, F.document)
async def final_deploy(message: types.Message, state: FSMContext):
    if not message.document.file_name.endswith('.txt'):
        await message.reply("❌ Sirf .txt file allow hai! Dobara bhejo.")
        return

    msg = await message.reply("⚙️ Aapka code secure server par deploy ho raha hai... Please wait.")
    
    # Download requirements.txt
    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    req_path = f"/tmp/requirements.txt"
    await bot.download_file(file.file_path, req_path)
    
    user_data = await state.get_data()
    project_name = user_data['proj_name']
    user_id = str(message.from_user.id)
    
    db = load_db()
    
    try:
        username = hf_api.whoami()['name']
        
        # Check if project exists (Update logic)
        if user_id in db and project_name in db[user_id]:
            repo_id = db[user_id][project_name]
            await msg.edit_text("🔄 Existing project mila. System ko update kiya ja raha hai...")
        else:
            # Create new project space
            space_name = f"u{user_id}-{project_name.replace(' ', '')}"
            repo_id = f"{username}/{space_name}"
            hf_api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True)
            
            # Save to Database
            if user_id not in db: 
                db[user_id] = {}
            db[user_id][project_name] = repo_id
            save_db(db)
            
            # Upload Dockerfile (Silent backend work)
            docker_content = 'FROM python:3.9-slim\nRUN useradd -m -u 1000 user\nUSER user\nENV PATH="/home/user/.local/bin:${PATH}"\nWORKDIR /app\nCOPY --chown=user requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY --chown=user . .\nCMD ["python", "main.py"]'
            with open("/tmp/Dockerfile", "w") as f: 
                f.write(docker_content)
            hf_api.upload_file(path_or_fileobj="/tmp/Dockerfile", path_in_repo="Dockerfile", repo_id=repo_id, repo_type="space")

        # Upload main.py and requirements.txt
        hf_api.upload_file(path_or_fileobj="/tmp/main.py", path_in_repo="main.py", repo_id=repo_id, repo_type="space")
        hf_api.upload_file(path_or_fileobj=req_path, path_in_repo="requirements.txt", repo_id=repo_id, repo_type="space")
        
        await msg.edit_text(f"✅ **Deployment Successful!**\n\n🚀 Aapka project **'{project_name}'** live ho chuka hai. Ise fully start hone mein 2-3 minute lagenge.")
        
    except Exception as e:
        await msg.edit_text(f"❌ Deployment Failed: {str(e)}")
    
    finally:
        await state.clear()

# --- [ WEB SERVER FOR RENDER 24/7 UPTIME ] ---
app = Flask(__name__)

@app.route('/')
def home():
    return "KayfHost Master Engine is Running smoothly! 🚀"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

async def main():
    Thread(target=run_web).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
