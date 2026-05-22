import os
import json
import discord
import asyncio
from discord import app_commands
from discord.ext import commands
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# تحميل متغيرات البيئة المحلية (أثناء التطوير)
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# إعدادات البوت الأساسية مع النوايا المعتمدة والمصححة
intents = discord.Intents.default()
intents.message_content = True  # لقراءة محتوى الرسائل والأوامر العادية
intents.guilds = True           # لإدارة السيرفر وإنشاء القنوات تلقائياً
bot = commands.Bot(command_prefix="!", intents=intents)

DB_FILE = "config_db.json"

# --- 1. دالات إدارة قاعدة البيانات البسيطة (JSON) ---
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- 2. دالة التحكم بمتصفح Playwright (التشغيل والإيقاف) ---
async def control_aternos(action: str, username: str, password: str, account_type: str, server_ip: str):
    async with async_playwright() as p:
        # تشغيل المتصفح بوضع مخفي وإعدادات تمنع الحظر المستمر
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # الانتقال إلى صفحة أترنوس
            await page.goto("https://aternos.org/go/")
            await page.wait_for_selector("input[placeholder='Username or Email']", timeout=10000)
            
            # كتابة بيانات الدخول
            await page.fill("input[placeholder='Username or Email']", username)
            await page.fill("input[placeholder='Password']", password)
            await page.click("button:has-text('Login')")
            
            # التعامل مع الحسابات المشتركة لمنحها وقت للتحميل
            if account_type == "shared":
                await page.wait_for_timeout(3000)
            
            # انتظار ظهور قائمة السيرفرات
            await page.wait_for_selector(".server-body", timeout=10000)
            
            # اختيار السيرفر بناءً على المدخلات
            if server_ip and server_ip != "الأول":
                server_element = page.locator(f".server-body:has-text('{server_ip}')")
                if await server_element.count() > 0:
                    await server_element.first.click()
                else:
                    await page.click(".server-body")
            else:
                await page.click(".server-body")
            
            # تنفيذ أمر التشغيل (Start) أو الإطفاء (Stop)
            if action == "start":
                await page.wait_for_selector("#start", timeout=10000)
                status = await page.locator(".statuslabel-label").inner_text()
                if "Offline" in status:
                    await page.click("#start")
                    msg = "✅ تم إرسال أمر تشغيل السيرفر بنجاح! السيرفر الآن قيد التحضير والتجهيز."
                else:
                    msg = f"⚠️ السيرفر ليس مغلقاً حالياً. حالته الحالية هي: {status}"
                    
            elif action == "stop":
                await page.wait_for_selector("#stop", timeout=10000)
                status = await page.locator(".statuslabel-label").inner_text()
                if "Online" in status or "Starting" in status:
                    await page.click("#stop")
                    msg = "🛑 تم إرسال أمر إطفاء السيرفر بنجاح! جاري الإغلاق الآمن."
                else:
                    msg = f"⚠️ لا يمكن إغلاق السيرفر لأنه في حالة: {status}"
            
            await browser.close()
            return msg
            
        except Exception as e:
            await browser.close()
            return f"❌ حدث خطأ أثناء محاولة أتمتة الموقع. تفاصيل: {e}"

# --- 3. أزرار لوحة التحكم المستمرة (Persistent Control Panel) ---
class AternosControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # جعل الأزرار تعمل للأبد بدون توقف (Persistent)

    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """فحص رتب المستخدم لمطابقتها مع الرتب المسموحة بالسيرفر"""
        db = load_db()
        guild_id = str(interaction.guild_id)
        
        if guild_id not in db:
            await interaction.response.send_message("❌ لم يتم العثور على إعدادات مثبتة لهذا السيرفر.", ephemeral=True)
            return False
            
        config = db[guild_id]
        
        # تخطي الفحص تلقائياً إذا كان العضو يمتلك رتبة مسؤول كاملة
        if interaction.user.guild_permissions.administrator:
            return True
            
        # فحص رتب المستخدم العادية
        user_roles = [role.name.lower() for role in interaction.user.roles]
        allowed_roles = [role.strip().lower() for role in config["allowed_roles"].split(",")]
        
        if any(role in allowed_roles for role in user_roles):
            return True
            
        await interaction.response.send_message("⛔ عذراً، لا تمتلك رتبة مسموح لها بالتحكم في تشغيل السيرفر.", ephemeral=True)
        return False

    @discord.ui.button(label="🟢 تشغيل السيرفر", style=discord.ButtonStyle.success, custom_id="persistent_btn_start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        
        await interaction.response.send_message("⏳ جاري فتح المتصفح والاتصال بأترنوس لتشغيل السيرفر...", ephemeral=True)
        db = load_db()
        config = db[str(interaction.guild_id)]
        
        result = await control_aternos(
            action="start",
            username=config["username"],
            password=config["password"],
            account_type=config["account_type"],
            server_ip=config["server_ip"]
        )
        await interaction.followup.send(content=result, ephemeral=True)

    @discord.ui.button(label="🔴 إطفاء السيرفر", style=discord.ButtonStyle.danger, custom_id="persistent_btn_stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        
        await interaction.response.send_message("⏳ جاري فتح المتصفح والاتصال بأترنوس لإيقاف السيرفر...", ephemeral=True)
        db = load_db()
        config = db[str(interaction.guild_id)]
        
        result = await control_aternos(
            action="stop",
            username=config["username"],
            password=config["password"],
            account_type=config["account_type"],
            server_ip=config["server_ip"]
        )
        await interaction.followup.send(content=result, ephemeral=True)

# --- 4. النافذة المنبثقة لإدخال البيانات (Modal) ---
class AternosSetupModal(discord.ui.Modal, title="⚙️ إعداد وتثبيت بيانات أترنوس"):
    def __init__(self, account_type: str):
        super().__init__()
        self.account_type = account_type

    username = discord.ui.TextInput(label="اسم المستخدم في أترنوس (Username)", placeholder="اكتب اسم الحساب هنا...")
    password = discord.ui.TextInput(label="كلمة السر الخاصة بأترنوس", style=discord.TextStyle.short, placeholder="كلمة المرور...")
    channel_name = discord.ui.TextInput(label="اسم القناة المراد إنشاؤها للتحكم", default="🎮-تحكم-السيرفر")
    allowed_roles = discord.ui.TextInput(label="الرتب المسموح لها بالتحكم (افصل بفاصلة)", placeholder="مثال: Admin, Member, Staff")
    server_ip = discord.ui.TextInput(label="اسم أو آي بي السيرفر المحدد (اختياري)", default="الأول", required=False, placeholder="اتركه كـ 'الأول' أو اكتب اسم السيرفر بدقة")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        
        try:
            # إنشاء قناة التحكم الجديدة
            new_channel = await guild.create_text_channel(name=self.channel_name.value)
            
            # حفظ البيانات المدخلة في قاعدة بيانات الـ JSON بناءً على الـ Guild ID
            db = load_db()
            db[str(guild.id)] = {
                "username": self.username.value,
                "password": self.password.value,
                "account_type": self.account_type,
                "allowed_roles": self.allowed_roles.value,
                "server_ip": self.server_ip.value,
                "channel_id": new_channel.id
            }
            save_db(db)
            
            # تصميم وإرسال رسالة التحكم المضمنة (Embed) مع الأزرار التفاعلية
            embed = discord.Embed(
                title="🎮 لوحة التحكم بسيرفر مايـن كرافـت",
                description=(
                    "مرحباً بك في قناة التحكم الخاصة بك! يمكنك استخدام الأزرار أدناه لإدارة السيرفر مباشرة.\n\n"
                    "🟢 **زر التشغيل:** يقوم بفتح السيرفر وجعله Online.\n"
                    "🔴 **زر الإطفاء:** يقوم بإغلاق السيرفر فوراً.\n\n"
                    "⚠️ **ملاحظة:** الرتب المسموح لها بالضغط هي فقط المحددة أثناء الإعداد بالإضافة للمسؤولين (Administrators)."
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text="Aternod Bot v2.0.1 - أتمتة تشغيل السيرفرات")
            
            await new_channel.send(embed=embed, view=AternosControlView())
            await interaction.followup.send(content=f"✅ تم التثبيت بنجاح! تم إنشاء القناة المخصصة هنا: {new_channel.mention}", ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(content=f"❌ حدث خطأ أثناء محاولة إنشاء القناة: {e}", ephemeral=True)

# --- 5. القائمة المنسدلة لاختيار نوع الحساب (Select Menu) ---
class AccountTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="أنا مالك السيرفر الأساسي (Creator)", value="owner", description="الحساب الأساسي المنشئ للسيرفر", emoji="👑"),
            discord.SelectOption(label="أنا متعاون مع شخص (Shared Access)", value="shared", description="تم إعطائي صلاحية الوصول للسيرفر من حساب آخر", emoji="🤝")
        ]
        super().__init__(placeholder="اختر نوع ملكية حساب أترنوس للبدء...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # فتح النافذة المنبثقة مباشرة بناءً على نوع الحساب المختار
        await interaction.response.send_modal(AternosSetupModal(account_type=self.values[0]))

class AccountTypeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AccountTypeSelect())

# --- 6. الأوامر المائلة وأحداث البوت ---
@bot.event
async def on_ready():
    print(f"🔥 تم تشغيل بوت {bot.user} بنجاح وبدون أخطاء!")
    
    # تسجيل الأزرار التفاعلية لتظل نشطة باستمرار حتى عند إعادة التشغيل
    bot.add_view(AternosControlView())
    
    try:
        synced = await bot.tree.sync()
        print(f"🔄 تم مزامنة {len(synced)} أوامر مائلة مع ديسكورد بنجاح.")
    except Exception as e:
        print(f"❌ فشل في مزامنة الأوامر: {e}")

# أمر التثبيت والإعداد الأساسي المائل
@bot.tree.command(name="setup_aternos", description="إعداد وتثبيت سيرفر أترنوس بإنشاء قناة وأزرار تحكم مستمرة")
@app_commands.checks.has_permissions(administrator=True) # حماية الأمر ليكون للمسؤولين فقط منعا للتخريب
async def setup_aternos(interaction: discord.Interaction):
    view = AccountTypeView()
    await interaction.response.send_message("🛠️ يرجى تحديد نوع ملكية الحساب الخاص بك من القائمة أدناه للمتابعة:", view=view, ephemeral=True)

@setup_aternos.error
async def setup_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("⛔ عذراً، هذا الأمر مخصص فقط لمسؤولي السيرفر (Administrators).", ephemeral=True)

# تشغيل البوت
if __name__ == "__main__":
    if not TOKEN:
        print("❌ خطأ حرج: لم يتم العثور على توكن البوت في متغيرات البيئة.")
    else:
        bot.run(TOKEN)
