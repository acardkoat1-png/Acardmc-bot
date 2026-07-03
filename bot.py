import discord
from discord import Option, Embed, Color, ButtonStyle
from discord.ui import Button, View
import sqlite3
import datetime
import os
import random
import traceback

# ===================== إعدادات البوت =====================
bot = discord.Bot(intents=discord.Intents.all())
TOKEN = os.getenv('DISCORD_TOKEN')

# ===================== قاعدة البيانات =====================
conn = sqlite3.connect('data.db')
c = conn.cursor()

# إنشاء الجداول
c.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    balance INTEGER DEFAULT 100,
    last_daily TEXT,
    total_sales INTEGER DEFAULT 0
)''')

c.execute('''CREATE TABLE IF NOT EXISTS auctions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id TEXT,
    item_name TEXT,
    quantity INTEGER,
    price INTEGER,
    status TEXT DEFAULT 'active'
)''')
conn.commit()

# ===================== دوال مساعدة =====================
def get_user(user_id):
    c.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (str(user_id), 100))
        conn.commit()
        return (str(user_id), 100, None, 0)
    return user

def update_balance(user_id, amount):
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()

def get_active_auctions():
    c.execute("SELECT id, seller_id, item_name, quantity, price FROM auctions WHERE status = 'active' ORDER BY id DESC")
    return c.fetchall()

# ===================== زر الشراء =====================
class BuyButton(Button):
    def __init__(self, auction_id, price, seller_id):
        super().__init__(label="شراء الآن", style=ButtonStyle.success, emoji="🛒", custom_id=f"buy_{auction_id}")
        self.auction_id = auction_id
        self.price = price
        self.seller_id = seller_id

    async def callback(self, interaction: discord.Interaction):
        try:
            buyer_id = str(interaction.user.id)
            seller_id = str(self.seller_id)

            if buyer_id == seller_id:
                await interaction.response.send_message("❌ لا يمكنك شراء سلعتك بنفسك!", ephemeral=True)
                return

            buyer = get_user(buyer_id)
            if buyer[1] < self.price:
                await interaction.response.send_message(f"❌ رصيدك غير كافٍ! تحتاج ${self.price}، لديك ${buyer[1]}", ephemeral=True)
                return

            c.execute("UPDATE auctions SET status = 'sold' WHERE id = ?", (self.auction_id,))
            update_balance(buyer_id, -self.price)
            update_balance(seller_id, self.price)
            c.execute("UPDATE users SET total_sales = total_sales + ? WHERE user_id = ?", (self.price, seller_id))
            conn.commit()

            embed = Embed(
                title="✅ تمت الصفقة بنجاح!",
                description=f"🎉 اشترى {interaction.user.mention} السلعة **بـ ${self.price}**",
                color=Color.green()
            )
            embed.set_footer(text="شكراً للتسوق في متجر مملكتنا!")
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ حدث خطأ أثناء الشراء: `{e}`", ephemeral=True)
            print(f"🔥 خطأ في زر الشراء: {traceback.format_exc()}")

# ===================== أمر /sell (نسخة مبسطة مع أزرار) =====================
@bot.slash_command(name="sell", description="💰 اعرض سلعتك للبيع في المزاد")
async def sell(
    ctx: discord.ApplicationContext,
    item_name: discord.Option(str, "📦 اسم العنصر (مثال: سيف نيثريت)"),
    price: discord.Option(int, "💰 السعر بالدولار"),
    quantity: discord.Option(int, "🔢 الكمية", default=1)
):
    try:
        if price <= 0 or quantity <= 0:
            await ctx.respond("❌ السعر والكمية يجب أن يكونا أكبر من صفر!", ephemeral=True)
            return

        embed = Embed(
            title="📝 تأكيد العرض",
            description=f"**العنصر:** {item_name}\n**الكمية:** {quantity}\n**السعر:** ${price}\n\nهل أنت متأكد؟",
            color=Color.blue()
        )
        embed.set_footer(text=f"بواسطة {ctx.author.name}", icon_url=ctx.author.avatar.url)

        class ConfirmView(View):
            def __init__(self):
                super().__init__(timeout=60)
                self.value = None

            @discord.ui.button(label="✅ تأكيد", style=ButtonStyle.success)
            async def confirm(self, button: Button, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ هذا الزر ليس لك!", ephemeral=True)
                    return
                self.value = True
                self.stop()
                await interaction.response.defer()

            @discord.ui.button(label="❌ إلغاء", style=ButtonStyle.danger)
            async def cancel(self, button: Button, interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ هذا الزر ليس لك!", ephemeral=True)
                    return
                self.value = False
                self.stop()
                await interaction.response.defer()

        view = ConfirmView()
        await ctx.respond(embed=embed, view=view)
        await view.wait()

        if view.value is None:
            await ctx.edit(content="⏰ انتهى الوقت! حاول مرة أخرى.", embed=None, view=None)
            return
        if not view.value:
            await ctx.edit(content="❌ تم إلغاء العرض.", embed=None, view=None)
            return

        c.execute("INSERT INTO auctions (seller_id, item_name, quantity, price) VALUES (?, ?, ?, ?)",
                  (str(ctx.author.id), item_name, quantity, price))
        conn.commit()
        auction_id = c.lastrowid

        success_embed = Embed(
            title="✅ تم عرض سلعتك بنجاح!",
            description=f"📦 **{item_name}** (x{quantity}) معروض بـ **${price}**\n🆔 رقم العرض: `{auction_id}`",
            color=Color.green()
        )
        success_embed.set_footer(text="استخدم /shop لرؤية جميع العروض!")
        await ctx.edit(embed=success_embed, view=None)

    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ: `{e}`", ephemeral=True)
        print(f"🔥 خطأ في /sell: {traceback.format_exc()}")

# ===================== أمر /shop =====================
@bot.slash_command(name="shop", description="🛍️ تصفح متجر المزاد الفاخر")
async def shop(ctx: discord.ApplicationContext):
    try:
        items = get_active_auctions()
        if not items:
            embed = Embed(
                title="🏪 السوق فارغ!",
                description="لا توجد عناصر معروضة. كن أنت أول تاجر باستخدام الأمر `/sell`!",
                color=Color.gold()
            )
            await ctx.respond(embed=embed)
            return

        embed = Embed(
            title="⚔️ متجر مملكة ماين كرافت ⚔️",
            description="━━━━━━━━━━━━━━━━━━━━━━━\n**أحدث التحف المعروضة في المزاد**\n━━━━━━━━━━━━━━━━━━━━━━━",
            color=Color.from_rgb(255, 215, 0)
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_footer(text=f"طلب بواسطة {ctx.author.name}", icon_url=ctx.author.avatar.url)

        view = View(timeout=60)
        for idx, item in enumerate(items[:5]):
            embed.add_field(
                name=f"**[{item[0]}]** {item[2]} (x{item[3]})",
                value=f"💰 السعر: **${item[4]}**\n👤 البائع: <@{item[1]}>",
                inline=False
            )
            view.add_item(BuyButton(auction_id=item[0], price=item[4], seller_id=item[1]))

        await ctx.respond(embed=embed, view=view)
    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ في المتجر: `{e}`", ephemeral=True)
        print(f"🔥 خطأ في /shop: {traceback.format_exc()}")

# ===================== أمر /balance =====================
@bot.slash_command(name="balance", description="💰 اعرض رصيدك الحالي")
async def balance(ctx: discord.ApplicationContext, member: discord.Member = None):
    try:
        if member is None:
            member = ctx.author

        user = get_user(str(member.id))
        bal = user[1]
        target = 10000
        progress = min(bal / target, 1.0)
        bar_length = 20
        filled = int(progress * bar_length)
        bar = "▓" * filled + "░" * (bar_length - filled)

        embed = Embed(
            title=f"💰 رصيد {member.name}",
            description=f"**${bal}** دولار\n━━━━━━━━━━━━━━━━━━\n`{bar}` **{int(progress * 100)}%**\nهدفك القادم: ${target}",
            color=Color.blue()
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_footer(text="استمر في البيع لزيادة رصيدك!")
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ: `{e}`", ephemeral=True)
        print(f"🔥 خطأ في /balance: {traceback.format_exc()}")

# ===================== أمر /daily =====================
@bot.slash_command(name="daily", description="🎁 احصل على مكافأتك اليومية")
async def daily(ctx: discord.ApplicationContext):
    try:
        user = get_user(str(ctx.author.id))
        today = datetime.date.today().isoformat()

        if user[2] == today:
            await ctx.respond("❌ لقد حصلت على مكافأتك اليومية بالفعل! عُد غداً.", ephemeral=True)
            return

        reward = random.randint(50, 200)
        update_balance(str(ctx.author.id), reward)
        c.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (today, str(ctx.author.id)))
        conn.commit()

        embed = Embed(
            title="🎉 مكافأة يومية!",
            description=f"لقد حصلت على **${reward}** دولار كهدية من الملك!\nرصيدك الجديد: **${get_user(str(ctx.author.id))[1]}**",
            color=Color.gold()
        )
        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ: `{e}`", ephemeral=True)
        print(f"🔥 خطأ في /daily: {traceback.format_exc()}")

# ===================== أمر /leaderboard =====================
@bot.slash_command(name="leaderboard", description="🏆 أعلى التجار في المملكة")
async def leaderboard(ctx: discord.ApplicationContext):
    try:
        c.execute("SELECT user_id, total_sales FROM users ORDER BY total_sales DESC LIMIT 10")
        top_users = c.fetchall()

        embed = Embed(title="🏆 قائمة أغنى التجار", color=Color.purple())
        medals = ["🥇", "🥈", "🥉"]
        for i, (user_id, sales) in enumerate(top_users):
            medal = medals[i] if i < 3 else f"#{i+1}"
            try:
                member = await bot.fetch_user(int(user_id))
                name = member.name
            except:
                name = "مستخدم غير معروف"
            embed.add_field(name=f"{medal} {name}", value=f"إجمالي المبيعات: **${sales}**", inline=False)

        await ctx.respond(embed=embed)
    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ: `{e}`", ephemeral=True)
        print(f"🔥 خطأ في /leaderboard: {traceback.format_exc()}")

# ===================== تشغيل البوت =====================
@bot.event
async def on_ready():
    print(f"🚀 تم تشغيل البوت كـ {bot.user.name}")
    print(f"✅ متصل بـ {len(bot.guilds)} سيرفر")

bot.run(TOKEN)
