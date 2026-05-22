import discord
from discord import app_commands
import asyncio
from playwright.async_api import async_playwright

# إعداد صلاحيات البوت الأساسية
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# دالة برمجية للتحكم بموقع أترنوس وتشغيل السيرفر تلقائياً
async def run_aternos_server(username, password):
    async with async_playwright() as p:
        # تشغيل متصفح مخفي (Headless)
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # الانتقال لصفحة تسجيل الدخول
            await page.goto("https://aternos.org/go/")
            
            # إدخال بيانات الحساب
            await page.fill("input[placeholder='Username or Email']", username)
            await page.fill("input[placeholder='Password']", password)
            
            # الضغط على زر تسجيل الدخول
            await page.click("button:has-text('Login')")
            await page.wait_for_timeout(3000)  # انتظار التحميل
            
            # الضغط على السيرفر (في حال وجود سيرفر واحد)
            await page.click(".server-body")
            await page.wait_for_timeout(2000)
            
            # البحث عن زر التشغيل والضغط عليه
            start_button = page.locator("#start")
            await start_button.click()
            
            await browser.close()
            return "✅ تم إرسال أمر التشغيل بنجاح! قد يستغرق السيرفر دقائق ليعمل."
        except Exception as e:
            await browser.close()
            return f"❌ حدث خطأ أثناء محاولة الاتصال بأترنوس: {str(e)}"

@client.event
async def on_ready():
    # مزامنة الأوامر مع ديسكورد عند تشغيل البوت
    await tree.sync()
    print(f"🔥 تم تشغيل البوت بنجاح باسم: {client.user}")

# أمر تفاعلي (Slash Command) لتشغيل السيرفر
@tree.command(name="start_server", description="تشغيل سيرفر أترنوس الخاص بك")
@app_commands.describe(username="اسم المستخدم في أترنوس", password="كلمة مرور حساب أترنوس")
async def start_server(interaction: discord.Interaction, username: str, password: str):
    # إعلام المستخدم أن البوت يعالج الطلب الآن (تجنباً لانتهاء وقت الاستجابة التلقائي 3 ثوانٍ)
    await interaction.response.defer(ephemeral=True)
    
    # تشغيل الدالة التلقائية
    result = await run_aternos_server(username, password)
    
    # إرسال النتيجة للمستخدم بشكل خاص
    await interaction.followup.send(result)

# ضع التوكن الخاص ببوت الديسكورد هنا
client.run("YOUR_DISCORD_BOT_TOKEN")
