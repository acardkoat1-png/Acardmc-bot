import discord
from discord import Embed, Color, ButtonStyle
from discord.ui import Button, View, Modal, InputText, Select
import sqlite3
import datetime
import os
import random
import traceback

# ===================== إعدادات البوت =====================
bot = discord.Bot(intents=discord.Intents.all())
TOKEN = os.getenv('DISCORD_TOKEN')

# ===================== قاعدة البيانات =====================
# استخدام /tmp لـ Railway
DB_PATH = '/tmp/data.db' if os.path.exists('/tmp') else 'data.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

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
    item_type TEXT,
    quantity INTEGER,
    price INTEGER,
    image_url TEXT,
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

def get_active_auctions(filter_type=None):
    if filter_type and filter_type != "all":
        c.execute("""SELECT id, seller_id, item_name, item_type, quantity, price, image_url 
                     FROM auctions WHERE status = 'active' AND item_type = ? 
                     ORDER BY id DESC""", (filter_type,))
    else:
        c.execute("""SELECT id, seller_id, item_name, item_type, quantity, price, image_url 
                     FROM auctions WHERE status = 'active' ORDER BY id DESC""")
    return c.fetchall()

# ===================== صور ماين كرافت =====================
ITEM_IMAGES = {
    "سيف دايموند":   "https://static.wikia.nocookie.net/minecraft_gamepedia/images/d/d5/Diamond_Sword_JE2_BE2.png",
    "سيف نيثريت":    "https://static.wikia.nocookie.net/minecraft_gamepedia/images/2/2e/Netherite_Sword_JE2.png",
    "فأس دايموند":   "https://static.wikia.nocookie.net/minecraft_gamepedia/images/a/ac/Diamond_Axe_JE3_BE3.png",
    "فأس نيثريت":    "https://static.wikia.nocookie.net/minecraft_gamepedia/images/c/c0/Netherite_Axe_JE2.png",
    "درع دايموند":   "https://static.wikia.nocookie.net/minecraft_gamepedia/images/6/69/Diamond_Chestplate_JE2_BE2.png",
    "درع نيثريت":    "https://static.wikia.nocookie.net/minecraft_gamepedia/images/3/3f/Netherite_Chestplate_JE2.png",
    "قوس":           "https://static.wikia.nocookie.net/minecraft_gamepedia/images/7/76/Bow_%28Pull_2%29_JE1_BE1.png",
    "درع":           "https://static.wikia.nocookie.net/minecraft_gamepedia/images/3/3a/Shield_JE2_BE2.png",
    "تفاحة ذهبية":  "https://static.wikia.nocookie.net/minecraft_gamepedia/images/b/b0/Golden_Apple_JE3_BE3.png",
    "تفاحة مشبعة":  "https://static.wikia.nocookie.net/minecraft_gamepedia/images/8/88/Enchanted_Golden_Apple_JE2_BE2.png",
}

def get_item_image(item_name):
    for key, url in ITEM_IMAGES.items():
        if key.lower() in item_name.lower():
            return url
    return "https://static.wikia.nocookie.net/minecraft_gamepedia/images/1/10/Grass_Block_JE9.png"

# ===================== زر الشراء =====================
class BuyButton(Button):
    def __init__(self, auction_id, price, seller_id, item_name):
        super().__init__(
            label="🛒 شراء الآن",
            style=ButtonStyle.success,
            custom_id=f"buy_{auction_id}"
        )
        self.auction_id = auction_id
        self.price = price
        self.seller_id = str(seller_id)
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        try:
            buyer_id = str(interaction.user.id)

            if buyer_id == self.seller_id:
                await interaction.response.send_message("❌ لا يمكنك شراء سلعتك بنفسك!", ephemeral=True)
                return

            # التحقق من أن العرض لا يزال نشطاً
            c.execute("SELECT status FROM auctions WHERE id = ?", (self.auction_id,))
            result = c.fetchone()
            if not result or result[0] != 'active':
                await interaction.response.send_message("❌ هذا العرض لم يعد متاحاً!", ephemeral=True)
                return

            buyer = get_user(buyer_id)
            if buyer[1] < self.price:
                await interaction.response.send_message(
                    f"❌ رصيدك غير كافٍ! تحتاج **${self.price}**، لديك **${buyer[1]}**",
                    ephemeral=True
                )
                return

            c.execute("UPDATE auctions SET status = 'sold' WHERE id = ?", (self.auction_id,))
            update_balance(buyer_id, -self.price)
            update_balance(self.seller_id, self.price)
            c.execute("UPDATE users SET total_sales = total_sales + ? WHERE user_id = ?",
                      (self.price, self.seller_id))
            conn.commit()

            embed = Embed(
                title="✅ تمت الصفقة بنجاح!",
                description=f"🎉 اشترى {interaction.user.mention} **{self.item_name}** بـ **${self.price}**",
                color=Color.green()
            )
            embed.set_image(url=get_item_image(self.item_name))
            embed.set_footer(text="شكراً للتسوق في متجر مملكتنا!")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            print(f"🔥 خطأ في زر الشراء: {traceback.format_exc()}")
            try:
                await interaction.response.send_message(f"❌ حدث خطأ: `{e}`", ephemeral=True)
            except:
                await interaction.followup.send(f"❌ حدث خطأ: `{e}`", ephemeral=True)


# ===================== نافذة البيع (Modal) - الإصلاح الرئيسي =====================
# ❌ المشكلة القديمة: modal = Modal(...) ثم modal.on_submit = func  ← لا يعمل!
# ✅ الحل: نصنع Class يرث من Modal ويحتوي callback داخله

class SellModal(Modal):
    def __init__(self):
        super().__init__(title="🏷️ إضافة عرض جديد للمزاد")

        self.add_item(InputText(
            label="📦 اسم العنصر (مثل: سيف دايموند)",
            placeholder="اكتب اسم العنصر...",
            max_length=50
        ))
        self.add_item(InputText(
            label="💰 السعر بالدولار ($)",
            placeholder="100",
            value="100",
            max_length=10
        ))
        self.add_item(InputText(
            label="🔢 الكمية",
            placeholder="1",
            value="1",
            max_length=5
        ))
        self.add_item(InputText(
            label="🏷️ النوع (سلاح / درع / أداة / طعام)",
            placeholder="سلاح",
            required=False,
            max_length=20
        ))

    # هذا هو الجزء المهم - callback وليس on_submit
    async def callback(self, interaction: discord.Interaction):
        try:
            item_name = self.children[0].value.strip()
            price_str = self.children[1].value.strip()
            qty_str   = self.children[2].value.strip()
            item_type = self.children[3].value.strip() or "عام"

            # التحقق من أن السعر والكمية أرقام
            try:
                price    = int(price_str)
                quantity = int(qty_str)
            except ValueError:
                await interaction.response.send_message(
                    "❌ السعر والكمية يجب أن يكونا أرقاماً صحيحة!", ephemeral=True
                )
                return

            if price <= 0 or quantity <= 0:
                await interaction.response.send_message(
                    "❌ السعر والكمية يجب أن يكونا أكبر من صفر!", ephemeral=True
                )
                return

            image_url = get_item_image(item_name)

            c.execute("""INSERT INTO auctions 
                         (seller_id, item_name, item_type, quantity, price, image_url) 
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (str(interaction.user.id), item_name, item_type, quantity, price, image_url))
            conn.commit()
            auction_id = c.lastrowid

            embed = Embed(
                title="✅ تم عرض سلعتك بنجاح!",
                description=(
                    f"📦 **{item_name}** (x{quantity})\n"
                    f"💰 السعر: **${price}**\n"
                    f"🆔 رقم العرض: `#{auction_id}`\n"
                    f"🏷️ النوع: {item_type}"
                ),
                color=Color.green()
            )
            embed.set_image(url=image_url)
            embed.set_footer(text="انتظر حتى يشتريها أحدهم!")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            print(f"🔥 خطأ في SellModal: {traceback.format_exc()}")
            try:
                await interaction.response.send_message(f"❌ حدث خطأ: `{e}`", ephemeral=True)
            except:
                await interaction.followup.send(f"❌ حدث خطأ: `{e}`", ephemeral=True)


# ===================== أمر /sell =====================
@bot.slash_command(name="sell", description="💰 اعرض سلعتك للبيع في المزاد")
async def sell(ctx: discord.ApplicationContext):
    modal = SellModal()
    await ctx.send_modal(modal)


# ===================== دالة مشتركة لعرض المتجر =====================
async def show_shop(responder, user, guild, filter_type=None):
    """تُستخدم من أمر /shop ومن فلتر Select على حدٍّ سواء"""
    try:
        items = get_active_auctions(filter_type)

        embed = Embed(
            title="⚔️ متجر مملكة ماين كرافت ⚔️",
            description="━━━━━━━━━━━━━━━━━━━━━━━\n**أحدث التحف المعروضة في المزاد**\n━━━━━━━━━━━━━━━━━━━━━━━",
            color=Color.from_rgb(255, 215, 0)
        )
        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if user and user.avatar:
            embed.set_footer(text=f"طلب بواسطة {user.name}", icon_url=user.avatar.url)

        if not items:
            embed.description += "\n\n🏪 **لا توجد عناصر في هذه الفئة حالياً.**"

        view = View(timeout=300)

        # قائمة الفلاتر
        all_items = get_active_auctions()
        types = list(set(item[3] for item in all_items))
        options = [discord.SelectOption(label="📦 الكل", value="all")]
        for t in types:
            options.append(discord.SelectOption(label=t, value=t))

        select = Select(placeholder="🔍 فلتر حسب النوع", options=options)

        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            await show_shop(interaction.followup, interaction.user, interaction.guild, select.values[0])

        select.callback = select_callback
        view.add_item(select)

        # إضافة العناصر وأزرار الشراء
        for item in items[:5]:
            embed.add_field(
                name=f"**#{item[0]}** — {item[2]} (x{item[4]})",
                value=f"💰 **${item[5]}** | 👤 <@{item[1]}> | 🏷️ {item[3]}",
                inline=False
            )
            view.add_item(BuyButton(
                auction_id=item[0],
                price=item[5],
                seller_id=item[1],
                item_name=item[2]
            ))

        # الإرسال — يدعم كل من ApplicationContext و followup
        if isinstance(responder, discord.ApplicationContext):
            await responder.respond(embed=embed, view=view)
        else:
            await responder.send(embed=embed, view=view)

    except Exception as e:
        print(f"🔥 خطأ في show_shop: {traceback.format_exc()}")
        error_msg = f"❌ حدث خطأ في المتجر: `{e}`"
        try:
            if isinstance(responder, discord.ApplicationContext):
                await responder.respond(error_msg, ephemeral=True)
            else:
                await responder.send(error_msg, ephemeral=True)
        except:
            pass


# ===================== أمر /shop =====================
@bot.slash_command(name="shop", description="🛍️ تصفح متجر المزاد الفاخر")
async def shop(ctx: discord.ApplicationContext):
    await show_shop(ctx, ctx.author, ctx.guild)


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
            description=(
                f"**${bal}** دولار\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"`{bar}` **{int(progress * 100)}%**\n"
                f"الهدف القادم: **${target}**"
            ),
            color=Color.blue()
        )
        if member.avatar:
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
            await ctx.respond("❌ لقد حصلت على مكافأتك اليومية! عُد غداً. 🌙", ephemeral=True)
            return

        reward = random.randint(50, 200)
        update_balance(str(ctx.author.id), reward)
        c.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (today, str(ctx.author.id)))
        conn.commit()

        new_balance = get_user(str(ctx.author.id))[1]
        embed = Embed(
            title="🎉 مكافأة يومية!",
            description=(
                f"حصلت على **${reward}** دولار كهدية من الملك! 👑\n"
                f"رصيدك الجديد: **${new_balance}**"
            ),
            color=Color.gold()
        )
        if ctx.author.avatar:
            embed.set_thumbnail(url=ctx.author.avatar.url)
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

        embed = Embed(title="🏆 قائمة أغنى التجار في المملكة", color=Color.purple())
        medals = ["🥇", "🥈", "🥉"]

        for i, (user_id, sales) in enumerate(top_users):
            medal = medals[i] if i < 3 else f"#{i + 1}"
            try:
                member = await bot.fetch_user(int(user_id))
                name = member.name
            except:
                name = "مستخدم غير معروف"
            embed.add_field(
                name=f"{medal} {name}",
                value=f"إجمالي المبيعات: **${sales}**",
                inline=False
            )

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
