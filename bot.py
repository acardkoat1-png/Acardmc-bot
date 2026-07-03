import discord
from discord import Embed, Color, ButtonStyle
from discord.ui import Button, View, Modal, InputText, Select
import sqlite3
import datetime
import os
import random
import traceback
import asyncio

# ===================== إعدادات البوت =====================
bot = discord.Bot(intents=discord.Intents.all())
TOKEN = os.getenv('DISCORD_TOKEN')

# ===================== قاعدة البيانات =====================
DB_PATH = '/tmp/data.db' if os.path.exists('/tmp') else 'data.db'
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول المطورة
c.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    balance INTEGER DEFAULT 100,
    bank_balance INTEGER DEFAULT 0,
    last_daily TEXT,
    total_sales INTEGER DEFAULT 0,
    rating REAL DEFAULT 0,
    rating_count INTEGER DEFAULT 0,
    tax_rate INTEGER DEFAULT 5,
    rank TEXT DEFAULT 'مبتدئ',
    join_date TEXT,
    total_trades INTEGER DEFAULT 0
)''')

c.execute('''CREATE TABLE IF NOT EXISTS auctions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id TEXT,
    item_name TEXT,
    item_type TEXT,
    quantity INTEGER,
    price INTEGER,
    image_url TEXT,
    status TEXT DEFAULT 'active',
    discount INTEGER DEFAULT 0,
    end_time TEXT,
    start_price INTEGER,
    current_bid INTEGER,
    bidder_id TEXT,
    is_auction BOOLEAN DEFAULT 0
)''')

c.execute('''CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reviewer_id TEXT,
    target_id TEXT,
    rating INTEGER,
    comment TEXT,
    created_at TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    type TEXT,
    amount INTEGER,
    description TEXT,
    created_at TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    task_type TEXT,
    progress INTEGER DEFAULT 0,
    target INTEGER,
    reward INTEGER,
    completed BOOLEAN DEFAULT 0,
    reset_date TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS coupons (
    code TEXT PRIMARY KEY,
    reward INTEGER,
    used_by TEXT,
    used BOOLEAN DEFAULT 0,
    expires_at TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS trade_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_id TEXT,
    receiver_id TEXT,
    offer_item TEXT,
    offer_quantity INTEGER,
    request_item TEXT,
    request_quantity INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TEXT
)''')

# جدول الخزينة
c.execute('''CREATE TABLE IF NOT EXISTS treasury (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    balance INTEGER DEFAULT 0
)''')
c.execute("INSERT OR IGNORE INTO treasury (id, balance) VALUES (1, 0)")

conn.commit()
print("✅ قاعدة البيانات جاهزة مع جميع الجداول المطورة")

# ===================== دوال مساعدة =====================
def get_user(user_id):
    c.execute("SELECT * FROM users WHERE user_id = ?", (str(user_id),))
    user = c.fetchone()
    if not user:
        join_date = datetime.date.today().isoformat()
        c.execute("""INSERT INTO users (user_id, balance, join_date, rank) 
                     VALUES (?, ?, ?, ?)""", (str(user_id), 100, join_date, 'مبتدئ'))
        conn.commit()
        return (str(user_id), 100, 0, None, 0, 0, 0, 5, 'مبتدئ', join_date, 0)
    return user

def update_balance(user_id, amount):
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, str(user_id)))
    conn.commit()
    # تسجيل المعاملة
    if amount > 0:
        c.execute("""INSERT INTO transactions (user_id, type, amount, description, created_at) 
                     VALUES (?, ?, ?, ?, ?)""",
                  (str(user_id), 'credit', amount, 'تحديث الرصيد', datetime.datetime.now().isoformat()))
    else:
        c.execute("""INSERT INTO transactions (user_id, type, amount, description, created_at) 
                     VALUES (?, ?, ?, ?, ?)""",
                  (str(user_id), 'debit', abs(amount), 'خصم رصيد', datetime.datetime.now().isoformat()))
    conn.commit()

def get_treasury():
    c.execute("SELECT balance FROM treasury WHERE id = 1")
    return c.fetchone()[0]

def update_treasury(amount):
    c.execute("UPDATE treasury SET balance = balance + ? WHERE id = 1", (amount,))
    conn.commit()

def get_active_auctions(filter_type=None):
    if filter_type and filter_type != "all":
        c.execute("""SELECT id, seller_id, item_name, item_type, quantity, price, image_url, discount, end_time, is_auction 
                     FROM auctions WHERE status = 'active' AND item_type = ? 
                     ORDER BY id DESC""", (filter_type,))
    else:
        c.execute("""SELECT id, seller_id, item_name, item_type, quantity, price, image_url, discount, end_time, is_auction 
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
    "بيضة التنين":  "https://static.wikia.nocookie.net/minecraft_gamepedia/images/b/ba/Dragon_Egg_JE3_BE2.png",
    "نجم النيثريت": "https://static.wikia.nocookie.net/minecraft_gamepedia/images/3/3c/Nether_Star_JE2_BE2.png",
}

def get_item_image(item_name):
    for key, url in ITEM_IMAGES.items():
        if key.lower() in item_name.lower():
            return url
    return "https://static.wikia.nocookie.net/minecraft_gamepedia/images/1/10/Grass_Block_JE9.png"

# ===================== دوال إرسال الرسائل الخاصة =====================
async def send_dm(user_id, message, embed=None):
    """إرسال رسالة خاصة (DM) لمستخدم مع ضمان عدم وجود أخطاء"""
    try:
        user = await bot.fetch_user(int(user_id))
        if embed:
            await user.send(message, embed=embed)
        else:
            await user.send(message)
        return True
    except discord.Forbidden:
        # المستخدم أغلق الرسائل الخاصة
        return False
    except Exception as e:
        print(f"⚠️ فشل إرسال DM للمستخدم {user_id}: {e}")
        return False

# ===================== زر الشراء المطور =====================
class BuyButton(Button):
    def __init__(self, auction_id, price, seller_id, item_name, discount=0):
        label = "🛒 شراء الآن"
        if discount > 0:
            label = f"🛒 شراء بخصم {discount}%"
        super().__init__(label=label, style=ButtonStyle.success, custom_id=f"buy_{auction_id}")
        self.auction_id = auction_id
        self.price = price
        self.seller_id = str(seller_id)
        self.item_name = item_name
        self.discount = discount

    async def callback(self, interaction: discord.Interaction):
        try:
            buyer_id = str(interaction.user.id)

            if buyer_id == self.seller_id:
                await interaction.response.send_message("❌ لا يمكنك شراء سلعتك بنفسك!", ephemeral=True)
                return

            # التحقق من نشاط العرض
            c.execute("SELECT status, price FROM auctions WHERE id = ?", (self.auction_id,))
            result = c.fetchone()
            if not result or result[0] != 'active':
                await interaction.response.send_message("❌ هذا العرض لم يعد متاحاً!", ephemeral=True)
                return

            actual_price = result[1]
            buyer = get_user(buyer_id)
            if buyer[1] < actual_price:
                await interaction.response.send_message(
                    f"❌ رصيدك غير كافٍ! تحتاج **${actual_price}**، لديك **${buyer[1]}**",
                    ephemeral=True
                )
                return

            # حساب الضريبة
            tax = int(actual_price * (buyer[7] / 100))  # tax_rate من الحقل 7
            final_price = actual_price - tax
            seller_profit = final_price

            # تنفيذ الصفقة
            c.execute("UPDATE auctions SET status = 'sold' WHERE id = ?", (self.auction_id,))
            update_balance(buyer_id, -actual_price)
            update_balance(self.seller_id, seller_profit)
            update_treasury(tax)  # الضريبة تذهب للخزينة
            c.execute("UPDATE users SET total_sales = total_sales + ? WHERE user_id = ?",
                      (actual_price, self.seller_id))
            c.execute("UPDATE users SET total_trades = total_trades + 1 WHERE user_id = ?", (buyer_id,))
            c.execute("UPDATE users SET total_trades = total_trades + 1 WHERE user_id = ?", (self.seller_id,))
            conn.commit()

            # رسالة نجاح مع الصورة
            embed = Embed(
                title="✅ تمت الصفقة بنجاح!",
                description=(
                    f"🎉 اشترى {interaction.user.mention} **{self.item_name}** بـ **${actual_price}**\n"
                    f"🧾 الضريبة: **${tax}** (ذهبت للخزينة)\n"
                    f"💰 ربح البائع: **${seller_profit}**"
                ),
                color=Color.green()
            )
            embed.set_image(url=get_item_image(self.item_name))
            embed.set_footer(text="شكراً للتسوق في متجر مملكتنا!")
            await interaction.response.send_message(embed=embed)

            # إرسال إشعارات DM
            seller_embed = Embed(
                title="💰 تم بيع عنصرك!",
                description=f"تم بيع **{self.item_name}** بـ **${actual_price}**\nربحك بعد الضريبة: **${seller_profit}**",
                color=Color.gold()
            )
            await send_dm(self.seller_id, "📦 عُرضك بيع!", embed=seller_embed)

            buyer_embed = Embed(
                title="🛒 تم شراء عنصرك!",
                description=f"اشتريت **{self.item_name}** بـ **${actual_price}**\nرصيدك الجديد: **${get_user(buyer_id)[1]}**",
                color=Color.blue()
            )
            await send_dm(buyer_id, "✅ عملية شراء ناجحة!", embed=buyer_embed)

            # طلب التقييم (اختياري)
            await asyncio.sleep(2)
            await send_dm(
                buyer_id,
                f"⭐ هل ترغب في تقييم البائع؟ اكتب `/rate {self.seller_id} [1-5]`"
            )

        except Exception as e:
            print(f"🔥 خطأ في زر الشراء: {traceback.format_exc()}")
            try:
                await interaction.response.send_message(f"❌ حدث خطأ: `{e}`", ephemeral=True)
            except:
                await interaction.followup.send(f"❌ حدث خطأ: `{e}`", ephemeral=True)

# ===================== نافذة البيع المطورة (مع خصم) =====================
class SellModal(Modal):
    def __init__(self):
        super().__init__(title="🏷️ إضافة عرض جديد للمزاد")

        self.add_item(InputText(
            label="📦 اسم العنصر",
            placeholder="مثل: سيف دايموند",
            max_length=50
        ))
        self.add_item(InputText(
            label="💰 السعر بالدولار",
            placeholder="100",
            value="100"
        ))
        self.add_item(InputText(
            label="🔢 الكمية",
            placeholder="1",
            value="1"
        ))
        self.add_item(InputText(
            label="🏷️ النوع (سلاح/درع/أداة/طعام)",
            placeholder="سلاح",
            required=False
        ))
        self.add_item(InputText(
            label="🎁 خصم (مئوي - اختياري)",
            placeholder="مثال: 10",
            required=False,
            max_length=3
        ))

    async def callback(self, interaction: discord.Interaction):
        try:
            item_name = self.children[0].value.strip()
            price = int(self.children[1].value.strip())
            quantity = int(self.children[2].value.strip())
            item_type = self.children[3].value.strip() or "عام"
            discount = int(self.children[4].value.strip()) if self.children[4].value.strip() else 0

            if price <= 0 or quantity <= 0:
                await interaction.response.send_message("❌ السعر والكمية يجب أن يكونا أكبر من صفر!", ephemeral=True)
                return

            if discount < 0 or discount > 90:
                await interaction.response.send_message("❌ الخصم يجب أن يكون بين 0% و 90%!", ephemeral=True)
                return

            final_price = price - int(price * (discount / 100))
            image_url = get_item_image(item_name)

            c.execute("""INSERT INTO auctions 
                         (seller_id, item_name, item_type, quantity, price, image_url, discount) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                      (str(interaction.user.id), item_name, item_type, quantity, final_price, image_url, discount))
            conn.commit()
            auction_id = c.lastrowid

            embed = Embed(
                title="✅ تم عرض سلعتك بنجاح!",
                description=(
                    f"📦 **{item_name}** (x{quantity})\n"
                    f"💰 السعر الأصلي: **${price}**\n"
                    f"🎁 الخصم: **{discount}%**\n"
                    f"💵 السعر النهائي: **${final_price}**\n"
                    f"🆔 رقم العرض: `#{auction_id}`\n"
                    f"🏷️ النوع: {item_type}"
                ),
                color=Color.green()
            )
            embed.set_image(url=image_url)
            embed.set_footer(text="انتظر حتى يشتريها أحدهم!")
            await interaction.response.send_message(embed=embed)

        except ValueError:
            await interaction.response.send_message("❌ السعر والكمية والخصم يجب أن تكون أرقاماً!", ephemeral=True)
        except Exception as e:
            print(f"🔥 خطأ في SellModal: {traceback.format_exc()}")
            await interaction.response.send_message(f"❌ حدث خطأ: `{e}`", ephemeral=True)

# ===================== أمر /sell =====================
@bot.slash_command(name="sell", description="💰 اعرض سلعتك للبيع في المزاد مع خصم اختياري")
async def sell(ctx: discord.ApplicationContext):
    modal = SellModal()
    await ctx.send_modal(modal)

# ===================== دالة عرض المتجر (مع Embed منفصل لكل عنصر) =====================
async def show_shop(responder, user, guild, filter_type=None, page=0):
    """عرض المتجر مع Embed منفصل لكل عنصر وصور PNG"""
    try:
        items = get_active_auctions(filter_type)
        items_per_page = 3  # عدد العناصر في كل صفحة
        total_pages = (len(items) + items_per_page - 1) // items_per_page

        if page >= total_pages:
            page = total_pages - 1
        if page < 0:
            page = 0

        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(items))
        page_items = items[start_idx:end_idx]

        if not items:
            embed = Embed(
                title="🏪 السوق فارغ!",
                description="لا توجد عناصر معروضة. كن أنت أول تاجر باستخدام الأمر `/sell`!",
                color=Color.gold()
            )
            if isinstance(responder, discord.ApplicationContext):
                await responder.respond(embed=embed)
            else:
                await responder.send(embed=embed)
            return

        # قائمة الفلاتر
        all_items = get_active_auctions()
        types = list(set(item[3] for item in all_items))
        options = [discord.SelectOption(label="📦 الكل", value="all")]
        for t in types:
            options.append(discord.SelectOption(label=t, value=t))

        select = Select(placeholder="🔍 فلتر حسب النوع", options=options)

        async def select_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            await show_shop(interaction.followup, interaction.user, interaction.guild, select.values[0], 0)

        select.callback = select_callback

        # إرسال Embed منفصل لكل عنصر
        for item in page_items:
            auction_id, seller_id, item_name, item_type, quantity, price, image_url, discount, end_time, is_auction = item

            embed = Embed(
                title=f"📦 **{item_name}**",
                description=(
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 رقم العرض: `#{auction_id}`\n"
                    f"🔢 الكمية: **{quantity}**\n"
                    f"💰 السعر: **${price}**\n"
                    f"👤 البائع: <@{seller_id}>\n"
                    f"🏷️ النوع: {item_type}\n"
                ),
                color=Color.from_rgb(255, 215, 0)
            )
            embed.set_image(url=image_url or get_item_image(item_name))
            embed.set_footer(text=f"متجر مملكة ماين كرافت - صفحة {page + 1}/{total_pages}")

            if discount > 0:
                original_price = int(price / (1 - discount/100))
                embed.description += f"\n🎁 **خصم {discount}%** (كان ${original_price})"

            view = View()
            view.add_item(BuyButton(auction_id, price, seller_id, item_name, discount))

            # إرسال لكل عنصر
            if isinstance(responder, discord.ApplicationContext):
                await responder.respond(embed=embed, view=view)
            else:
                await responder.send(embed=embed, view=view)

        # إرسال قائمة الفلاتر والأزرار بشكل منفصل
        if page_items:
            controls = View()
            controls.add_item(select)

            # أزرار الصفحات
            if page > 0:
                prev_button = Button(label="⏪ السابق", style=ButtonStyle.primary, custom_id="prev_page")
                async def prev_callback(interaction: discord.Interaction):
                    await interaction.response.defer()
                    await show_shop(interaction.followup, interaction.user, interaction.guild, filter_type, page - 1)
                prev_button.callback = prev_callback
                controls.add_item(prev_button)

            if page < total_pages - 1:
                next_button = Button(label="التالي ⏩", style=ButtonStyle.primary, custom_id="next_page")
                async def next_callback(interaction: discord.Interaction):
                    await interaction.response.defer()
                    await show_shop(interaction.followup, interaction.user, interaction.guild, filter_type, page + 1)
                next_button.callback = next_callback
                controls.add_item(next_button)

            embed_controls = Embed(
                title="🔍 تصفح المتجر",
                description=f"عرض العناصر {start_idx + 1} - {min(end_idx, len(items))} من {len(items)}",
                color=Color.blue()
            )
            if isinstance(responder, discord.ApplicationContext):
                await responder.respond(embed=embed_controls, view=controls)
            else:
                await responder.send(embed=embed_controls, view=controls)

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
@bot.slash_command(name="shop", description="🛍️ تصفح متجر المزاد الفاخر مع صور لكل عنصر")
async def shop(ctx: discord.ApplicationContext):
    await show_shop(ctx, ctx.author, ctx.guild)

# ===================== أمر /rate (التقييم) =====================
@bot.slash_command(name="rate", description="⭐ قيم بائعاً من 1 إلى 5 نجوم")
async def rate(
    ctx: discord.ApplicationContext,
    user: discord.Option(discord.Member, "البائع الذي تريد تقييمه"),
    rating: discord.Option(int, "التقييم من 1 إلى 5")
):
    try:
        if rating < 1 or rating > 5:
            await ctx.respond("❌ التقييم يجب أن يكون بين 1 و 5!", ephemeral=True)
            return

        target_id = str(user.id)
        reviewer_id = str(ctx.author.id)

        if target_id == reviewer_id:
            await ctx.respond("❌ لا يمكنك تقييم نفسك!", ephemeral=True)
            return

        c.execute("SELECT rating, rating_count FROM users WHERE user_id = ?", (target_id,))
        result = c.fetchone()
        if not result:
            await ctx.respond("❌ هذا المستخدم غير مسجل!", ephemeral=True)
            return

        old_rating, count = result
        new_count = count + 1
        new_rating = ((old_rating * count) + rating) / new_count

        c.execute("UPDATE users SET rating = ?, rating_count = ? WHERE user_id = ?", 
                  (new_rating, new_count, target_id))
        c.execute("INSERT INTO ratings (reviewer_id, target_id, rating, created_at) VALUES (?, ?, ?, ?)",
                  (reviewer_id, target_id, rating, datetime.datetime.now().isoformat()))
        conn.commit()

        embed = Embed(
            title="⭐ تم التقييم!",
            description=f"قيمت **{user.name}** بـ **{rating}** ⭐\nمتوسط التقييم الجديد: **{new_rating:.1f}** من 5",
            color=Color.gold()
        )
        embed.set_thumbnail(url=user.avatar.url)
        await ctx.respond(embed=embed)

    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ: `{e}`", ephemeral=True)
        print(f"🔥 خطأ في /rate: {traceback.format_exc()}")

# ===================== أمر /profile (الملف الشخصي) =====================
@bot.slash_command(name="profile", description="👤 اعرض ملفك الشخصي أو ملف عضو آخر")
async def profile(ctx: discord.ApplicationContext, member: discord.Member = None):
    try:
        if member is None:
            member = ctx.author

        user = get_user(str(member.id))
        bal, bank, _, _, sales, rating, rate_count, _, rank, join_date, trades = user

        embed = Embed(
            title=f"👤 ملف {member.name}",
            description=(
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏅 الرتبة: **{rank}**\n"
                f"💰 الرصيد: **${bal}**\n"
                f"🏦 البنك: **${bank}**\n"
                f"📦 إجمالي المبيعات: **${sales}**\n"
                f"⭐ التقييم: **{rating:.1f}** ⭐ ({rate_count} تقييم)\n"
                f"🤝 الصفقات: **{trades}**\n"
                f"📅 تاريخ الانضمام: {join_date}\n"
            ),
            color=Color.blue()
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_footer(text="استمر في البيع لترتفع رتبتك!")
        await ctx.respond(embed=embed)

    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ: `{e}`", ephemeral=True)
        print(f"🔥 خطأ في /profile: {traceback.format_exc()}")

# ===================== أمر /balance =====================
@bot.slash_command(name="balance", description="💰 اعرض رصيدك الحالي")
async def balance(ctx: discord.ApplicationContext, member: discord.Member = None):
    try:
        if member is None:
            member = ctx.author

        user = get_user(str(member.id))
        bal, bank, _, _, sales, _, _, _, rank, _, _ = user
        target = 10000
        progress = min((bal + bank) / target, 1.0)
        bar_length = 20
        filled = int(progress * bar_length)
        bar = "▓" * filled + "░" * (bar_length - filled)

        embed = Embed(
            title=f"💰 رصيد {member.name}",
            description=(
                f"**المحفظة:** ${bal}\n"
                f"**البنك:** ${bank}\n"
                f"**الإجمالي:** ${bal + bank}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"`{bar}` **{int(progress * 100)}%**\n"
                f"هدفك القادم: **${target}**\n"
                f"🏅 رتبتك: **{rank}**"
            ),
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

        if user[3] == today:
            await ctx.respond("❌ لقد حصلت على مكافأتك اليومية! عُد غداً. 🌙", ephemeral=True)
            return

        # مكافأة متصاعدة
        streak = 1
        c.execute("SELECT streak FROM user_streaks WHERE user_id = ?", (str(ctx.author.id),))
        result = c.fetchone()
        if result:
            streak = result[0] + 1
        c.execute("INSERT OR REPLACE INTO user_streaks (user_id, streak) VALUES (?, ?)", 
                  (str(ctx.author.id), streak))
        conn.commit()

        base_reward = random.randint(50, 200)
        bonus = int(base_reward * (streak / 10)) if streak > 1 else 0
        reward = base_reward + bonus

        update_balance(str(ctx.author.id), reward)
        c.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (today, str(ctx.author.id)))
        conn.commit()

        new_balance = get_user(str(ctx.author.id))[1]
        embed = Embed(
            title="🎉 مكافأة يومية!",
            description=(
                f"حصلت على **${reward}** دولار كهدية من الملك! 👑\n"
                f"🔥 **{streak}** يوم متتالي\n"
                f"🎁 مكافأة إضافية: **${bonus}**\n"
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
        c.execute("SELECT user_id, total_sales, rating FROM users ORDER BY total_sales DESC LIMIT 10")
        top_users = c.fetchall()

        embed = Embed(
            title="🏆 قائمة أغنى التجار في المملكة",
            description="━━━━━━━━━━━━━━━━━━━━━━━",
            color=Color.purple()
        )
        medals = ["🥇", "🥈", "🥉"]

        for i, (user_id, sales, rating) in enumerate(top_users):
            medal = medals[i] if i < 3 else f"#{i + 1}"
            try:
                member = await bot.fetch_user(int(user_id))
                name = member.name
            except:
                name = "مستخدم غير معروف"
            embed.add_field(
                name=f"{medal} {name}",
                value=f"💰 المبيعات: **${sales}**\n⭐ التقييم: **{rating:.1f}**",
                inline=False
            )

        await ctx.respond(embed=embed)

    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ: `{e}`", ephemeral=True)
        print(f"🔥 خطأ في /leaderboard: {traceback.format_exc()}")

# ===================== أوامر إضافية بسيطة =====================
@bot.slash_command(name="deposit", description="💰 أودع أموالاً في البنك")
async def deposit(ctx: discord.ApplicationContext, amount: discord.Option(int, "المبلغ للإيداع")):
    try:
        if amount <= 0:
            await ctx.respond("❌ المبلغ يجب أن يكون أكبر من صفر!", ephemeral=True)
            return

        user = get_user(str(ctx.author.id))
        if user[1] < amount:
            await ctx.respond(f"❌ رصيدك غير كافٍ! لديك ${user[1]}", ephemeral=True)
            return

        c.execute("UPDATE users SET balance = balance - ?, bank_balance = bank_balance + ? WHERE user_id = ?", 
                  (amount, amount, str(ctx.author.id)))
        conn.commit()

        await ctx.respond(f"✅ تم إيداع **${amount}** في البنك بنجاح! 🏦")

    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ: `{e}`", ephemeral=True)

@bot.slash_command(name="withdraw", description="🏦 اسحب أموالاً من البنك")
async def withdraw(ctx: discord.ApplicationContext, amount: discord.Option(int, "المبلغ للسحب")):
    try:
        if amount <= 0:
            await ctx.respond("❌ المبلغ يجب أن يكون أكبر من صفر!", ephemeral=True)
            return

        user = get_user(str(ctx.author.id))
        if user[2] < amount:
            await ctx.respond(f"❌ رصيدك في البنك غير كافٍ! لديك ${user[2]}", ephemeral=True)
            return

        c.execute("UPDATE users SET balance = balance + ?, bank_balance = bank_balance - ? WHERE user_id = ?", 
                  (amount, amount, str(ctx.author.id)))
        conn.commit()

        await ctx.respond(f"✅ تم سحب **${amount}** من البنك بنجاح! 💰")

    except Exception as e:
        await ctx.respond(f"❌ حدث خطأ: `{e}`", ephemeral=True)

# ===================== تشغيل البوت =====================
@bot.event
async def on_ready():
    print(f"🚀 تم تشغيل البوت كـ {bot.user.name}")
    print(f"✅ متصل بـ {len(bot.guilds)} سيرفر")
    print(f"📁 قاعدة البيانات: {DB_PATH}")

bot.run(TOKEN)
