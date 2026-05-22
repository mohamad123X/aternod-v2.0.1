import os
import discord
from discord.ext import commands
from playwright.async_api import async_playwright

# 1. جلب البيانات الحساسة من متغيرات البيئة (التي سنقوم بإعدادها في Railway)
# استخدمنا os.getenv لكي لا نكتب كلمات المرور في الكود المكشوف
TOKEN = os.getenv("DISCORD_TOKEN")
ATERNOS_USER = os.getenv("ATERNOS_USER")
ATERNOS_PASS = os.getenv("ATERNOS_PASS")

# 2. إعداد البوت والصلاحيات
intents = discord.Intents.default()
intents.message_content = True # ضروري ليتمكن البوت من قراءة الأوامر في الشات
bot = commands.Bot(command_prefix="!", intents=intents)

# 3. دالة التحكم بمتصفح Playwright لفتح موقع أترنوس
async def start_aternos_server():
    async with async_playwright() as p:
        # تشغيل المتصفح بشكل مخفي (بدون واجهة رسومية) لأننا على خادم سحابي
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # الانتقال إلى صفحة تسجيل الدخول
            await page.goto("https://aternos.org/go/")
            
            # انتظار ظهور حقول الإدخال وكتابة البيانات
            await page.wait_for_selector("input[placeholder='Username or Email']")
            await page.fill("input[placeholder='Username or Email']", ATERNOS_USER)
            await page.fill("input[placeholder='Password']", ATERNOS_PASS)
            
            # الضغط على زر الدخول (ابحث عن الزر الذي يحتوي على كلمة Login أو تسجيل)
            await page.click("button:has-text('Login')")
            
            # الانتظار حتى يتم تحميل الصفحة الرئيسية واختيار السيرفر
            await page.wait_for_timeout(4000) 
            await page.click(".server-body") # الضغط على أول سيرفر في القائمة
            
            # الانتظار والضغط على زر التشغيل (Start)
            await page.wait_for_timeout(3000)
            await page.click("#start")
            
            await browser.close()
            return "✅ تم إرسال أمر تشغيل السيرفر بنجاح! قد يستغرق بعض الوقت ليصبح Online."
            
        except Exception as e:
            await browser.close()
            # في حال حدوث خطأ (مثل تغير تصميم الموقع أو خطأ في البيانات) سيعلمنا البوت بالسبب
            return f"❌ حدث خطأ أثناء الاتصال بأترنوس: {e}"

# 4. حدث تشغيل البوت (عندما يتصل بنجاح)
@bot.event
async def on_ready():
    print(f"🔥 تم تشغيل بوت {bot.user} بنجاح وهو جاهز للعمل!")

# 5. أمر تشغيل السيرفر عبر الديسكورد (اكتب !start في السيرفر)
@bot.command(name="start")
async def start(ctx):
    # إرسال رسالة للمستخدم ليعلم أن البوت بدأ العمل
    await ctx.send("⏳ جاري الاتصال بأترنوس... يرجى الانتظار بضع ثوانٍ.")
    
    # تشغيل الدالة التلقائية وجلب النتيجة
    result = await start_aternos_server()
    
    # إرسال النتيجة النهائية
    await ctx.send(result)

# 6. تشغيل البوت
if __name__ == "__main__":
    if not TOKEN:
        print("❌ تحذير: لم يتم العثور على توكن البوت. (هذا طبيعي إذا كنت تجربه بدون ملف .env حالياً)")
    else:
        bot.run(TOKEN)
