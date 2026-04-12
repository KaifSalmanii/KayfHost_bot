import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from huggingface_hub import HfApi
from flask import Flask
from threading import Thread

# --- [ CREDENTIALS ] ---
TELEGRAM_TOKEN = os.environ.get('BOT_TOKEN', 'YAHAN_TOKEN_MAT_DAALNA')
HF_TOKEN = os.environ.get('HF_TOKEN', 'YAHAN_HF_TOKEN_MAT_DAALNA')

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
hf_api = HfApi(token=HF_TOKEN)

# --- [ HUGGING FACE DOCKER TEMPLATE ] ---
DOCKERFILE_CONTENT = """
FROM python:3.9-slim
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"
WORKDIR /app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .
CMD ["python", "main.py"]
"""

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.reply("🔥 Welcome to the Auto-Hosting Bot!\n\nMujhe apni `.py` file bhejo, aur main use 24/7 server par host kar doonga.")

@dp.message(F.document)
async def handle_python_file(message: types.Message):
    file_name = message.document.file_name
    user_id = message.from_user.id
    
    if not file_name.endswith('.py'):
        await message.reply("❌ Sirf .py files allow hain!")
        return
        
    msg = await message.reply("⏳ File downloading...")
    
    # 1. Download the file temporarily
    file = await bot.get_file(message.document.file_id)
    download_path = f"/tmp/{file_name}"
    await bot.download_file(file.file_path, download_path)
    
    await msg.edit_text("⚙️ Hugging Face par naya server ban raha hai...")
    
    try:
        # 2. Create a unique Space name for the user
        space_name = f"user-{user_id}-bot"
        username = hf_api.whoami()['name']
        repo_id = f"{username}/{space_name}"
        
        # 3. Create the Space
        hf_api.create_repo(
            repo_id=repo_id,
            repo_type="space",
            space_sdk="docker",
            exist_ok=True # Agar pehle se hai toh overwrite karega
        )
        
        await msg.edit_text("📤 Files upload ho rahi hain...")
        
        # 4. Upload user's Python file as main.py
        hf_api.upload_file(
            path_or_fileobj=download_path,
            path_in_repo="main.py",
            repo_id=repo_id,
            repo_type="space"
        )
        
        # 5. Upload Dockerfile
        with open("/tmp/Dockerfile", "w") as f:
            f.write(DOCKERFILE_CONTENT)
        hf_api.upload_file(
            path_or_fileobj="/tmp/Dockerfile",
            path_in_repo="Dockerfile",
            repo_id=repo_id,
            repo_type="space"
        )
        
        # 6. Upload empty requirements (user needs to provide this later, keeping basic for now)
        with open("/tmp/requirements.txt", "w") as f:
            f.write("aiogram\nflask")
        hf_api.upload_file(
            path_or_fileobj="/tmp/requirements.txt",
            path_in_repo="requirements.txt",
            repo_id=repo_id,
            repo_type="space"
        )
        
        await msg.edit_text(f"✅ **Aapka Bot Host Ho Gaya Hai!**\n\n🚀 Dashboard: https://huggingface.co/spaces/{repo_id}")
        
    except Exception as e:
        await msg.edit_text(f"❌ Hosting Failed: {e}")
        
# --- [ WEB SERVER FOR 24/7 UPTIME ] ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Master Host Bot is Running!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

async def main():
    Thread(target=run_web).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
