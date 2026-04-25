import discord
from discord.ext import commands, tasks
import pymysql
import random
import asyncio
from datetime import date

# --- CẤU HÌNH ---
TOKEN = 'MTQ4OTg1MjI3Nzg4NjgxMjI3MQ.G_z5P8.Y8nYRIFunVh66LoIneDUPKRwxKLu0gkD62SqC0'  # Thay Token mới của bạn vào đây
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123123',
    'database': 'discord_bot',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}
ID_KENH_THONG_BAO = 1490233426211770509 

intents = discord.Intents.default()
intents.message_content = True

# --- GIAO DIỆN NÚT BẤM TÀI XỈU ---
class TaiXiuView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.selected_amounts = {}

    @discord.ui.select(
        placeholder="💰 Chọn số đá muốn cược...",
        options=[
            discord.SelectOption(label="1,000 Đá", value="1000"),
            discord.SelectOption(label="5,000 Đá", value="5000"),
            discord.SelectOption(label="10,000 Đá", value="10000"),
            discord.SelectOption(label="50,000 Đá", value="50000"),
            discord.SelectOption(label="100,000 Đá", value="100000"),
        ]
    )
    async def select_amount(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.selected_amounts[interaction.user.id] = int(select.values[0])
        await interaction.response.send_message(f"✅ Mức cược: **{int(select.values[0]):,}** Đá. Hãy chọn TÀI hoặc XỈU!", ephemeral=True)

    @discord.ui.button(label="TÀI", style=discord.ButtonStyle.danger, custom_id="bet_tai")
    async def bet_tai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_bet(interaction, "tai")

    @discord.ui.button(label="XỈU", style=discord.ButtonStyle.primary, custom_id="bet_xiu")
    async def bet_xiu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_bet(interaction, "xiu")

    async def handle_bet(self, interaction: discord.Interaction, choice: str):
        if not self.bot.phien_dang_mo:
            return await interaction.response.send_message("⏳ Đã đóng cược!", ephemeral=True)
        
        amount = self.selected_amounts.get(interaction.user.id)
        if not amount:
            return await interaction.response.send_message("❌ Bạn chưa chọn số tiền!", ephemeral=True)

        user_id = str(interaction.user.id)
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT gem FROM users WHERE user_id=%s", (user_id,))
        user = cursor.fetchone()

        if not user or user['gem'] < amount:
            conn.close()
            return await interaction.response.send_message("❌ Không đủ Đá Quý!", ephemeral=True)

        cursor.execute("UPDATE users SET gem = gem - %s WHERE user_id = %s", (amount, user_id))
        conn.commit(); conn.close()
        self.bot.danh_sach_cuoc.append({'user_id': user_id, 'lua_chon': choice, 'bet': amount})
        await interaction.response.send_message(f"✅ Đã đặt **{amount:,}** vào **{choice.upper()}**!", ephemeral=True)

# --- CLASS BOT ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.danh_sach_cuoc = []
        self.phien_dang_mo = True
        self.phien_hien_tai = 0
        self.lich_su_cau = []

    async def setup_hook(self):
        self.loop.create_task(self.vong_lap_taixiu_realtime())

    async def vong_lap_taixiu_realtime(self):
        await self.wait_until_ready()
        channel = self.get_channel(ID_KENH_THONG_BAO)

        while not self.is_closed():
            self.phien_hien_tai += 1
            self.phien_dang_mo = True
            self.danh_sach_cuoc = []
            thoi_gian_con_lai = 60
            view = TaiXiuView(self)
            
            soi_cau_str = " ".join(self.lich_su_cau[-10:]) if self.lich_su_cau else "Chưa có dữ liệu"
            
            embed_cd = discord.Embed(title=f"🎲 TÀI XỈU PHIÊN #{self.phien_hien_tai}", color=0x3498db)
            embed_cd.add_field(name="📊 Cầu (10 phiên)", value=f"**{soi_cau_str}**", inline=False)
            embed_cd.add_field(name="⚡ Tỉ lệ hoàn trả", value="**x1.95**", inline=True)
            embed_cd.add_field(name="👤 Đã cược", value=f"**{len(self.danh_sach_cuoc)}**", inline=True)
            embed_cd.description = f"⏳ Còn lại: **{thoi_gian_con_lai} giây**"
            
            msg = await channel.send(embed=embed_cd, view=view)

            for _ in range(thoi_gian_con_lai // 10):
                await asyncio.sleep(10)
                thoi_gian_con_lai -= 10
                embed_cd.description = f"⏳ Còn lại: **{thoi_gian_con_lai} giây**"
                embed_cd.set_field_at(2, name="👤 Đã cược", value=f"**{len(self.danh_sach_cuoc)}**")
                try: await msg.edit(embed=embed_cd)
                except: pass

            await asyncio.sleep(thoi_gian_con_lai % 10)
            self.phien_dang_mo = False
            await msg.edit(content="🚫 **HẾT GIỜ ĐẶT CƯỢC!**", embed=None, view=None)

            dices = [random.randint(1, 6) for _ in range(3)]
            total = sum(dices)
            dice_emo = " ".join([f"[{d}]" for d in dices])
            ket_qua = "tai" if total >= 11 else "xiu"
            
            icon = "🔴" if ket_qua == "tai" else "⚪"
            self.lich_su_cau.append(icon)
            if len(self.lich_su_cau) > 10: self.lich_su_cau.pop(0)

            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()
            thanh_cong = []
            for cuoc in self.danh_sach_cuoc:
                if cuoc['lua_chon'] == ket_qua:
                    win_amount = int(cuoc['bet'] * 1.95)
                    cursor.execute("UPDATE users SET gem = gem + %s WHERE user_id = %s", (win_amount, cuoc['user_id']))
                    thanh_cong.append(f"<@{cuoc['user_id']}>")
            conn.commit(); conn.close()

            embed_res = discord.Embed(title=f"🎲 KẾT QUẢ PHIÊN #{self.phien_hien_tai}", color=0xffd700)
            embed_res.add_field(name="Xúc xắc", value=f"**{dice_emo} = {total}**", inline=False)
            embed_res.add_field(name="Kết quả", value=f"✨ **{ket_qua.upper()}** ✨", inline=True)
            if thanh_cong:
                embed_res.add_field(name="Người thắng", value=", ".join(thanh_cong[:15]), inline=False)
            await channel.send(embed=embed_res)
            await asyncio.sleep(5)

bot = MyBot()

def get_db(): return pymysql.connect(**DB_CONFIG)

def lay_acc_tu_kho(rank_type):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, account_info FROM account_stock WHERE rank_type=%s AND is_sold=0 LIMIT 1", (rank_type,))
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE account_stock SET is_sold=1 WHERE id=%s", (row['id'],))
                conn.commit(); return row['account_info']
            return None
    finally: conn.close()

# --- LỆNH NGƯỜI DÙNG ---

@bot.command(name="vi")
async def check_balance(ctx):
    user_id = str(ctx.author.id); conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT coin, gem, total_spent FROM users WHERE user_id=%s", (user_id,))
        user = cursor.fetchone()
    conn.close()
    if user: 
        await ctx.send(f"💳 {ctx.author.mention}: **{user['coin']:,}** Coin | 💎 **{user['gem']:,}** Đá.\n📊 Tổng chi tiêu: **{user['total_spent']:,}**")

@bot.command()
async def quay(ctx, loai: str):
    user_id = str(ctx.author.id); conn = get_db(); cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, coin, gem, total_spent) VALUES (%s, 0, 0, 0)", (user_id,))
        conn.commit(); user = {'coin': 0, 'gem': 0, 'total_spent': 0, 'last_free_spin': None}

    config = {"1": {"cost": 5000, "spins": 1}, "4": {"cost": 20000, "spins": 4}, "10": {"cost": 45000, "spins": 10}}
    if loai not in config: return await ctx.send("❌ Chọn: 1, 4, 10")
    
    cost = config[loai]["cost"]
    num_spins = config[loai]["spins"]
    is_free = (loai == "1" and str(user['last_free_spin']) != str(date.today()))
    if is_free: cost = 0
    if user['coin'] < cost: return await ctx.send("❌ Thiếu Coin!")

    new_total_spent = user['total_spent'] + cost
    final_res = []; gems_total = 0
    
    for _ in range(num_spins):
        r = random.random()
        
        # 1. 1% Trúng Nick lv40
        if r < 0.01: 
            acc = lay_acc_tu_kho("HIGH")
            if acc: 
                final_res.append("🌟 **Nick lv40**")
                await ctx.author.send(f"🌟 Thưởng Nick lv40: `{acc}`")
            else: 
                final_res.append("💎 +5 Đá (Kho hết hàng)"); gems_total += 5

        # 2. 5% Trúng Vật Phẩm (Flash, Civic, Koe, Balo, Vũ khí)
        elif r < 0.06: # (0.01 + 0.05)
            vp_list = ["Xe Flash ⚡", "Xe Civic 🚗", "Xe Koe 🏎️", "Balo 🎒", "Vũ khí VIP ⚔️"]
            vp_win = random.choice(vp_list)
            final_res.append(f"🎁 **{vp_win}**")
            await ctx.author.send(f"🎁 Chúc mừng! Bạn quay trúng vật phẩm: **{vp_win}** Tạo ticket để nhận thưởng")

        # 3. 3% Trúng Nick lv20 (Lấy từ r < 0.09 vì 0.06 + 0.03 = 0.09)
        elif r < 0.09:
            acc = lay_acc_tu_kho("LOW")
            if acc:
                final_res.append("📦 **Nick lv20**")
                await ctx.author.send(f"📦 Thưởng Nick lv20: `{acc}`")
            else: 
                final_res.append("💎 +2 Đá (Kho hết hàng)"); gems_total += 2

        # 4. Tỷ lệ trúng Đá Quý
        elif r < 0.50:
            g = random.randint(1, 3); gems_total += g; final_res.append(f"💎 +{g} Đá")
            
        # 5. Còn lại là trượt
        else: 
            final_res.append("🧧 Trượt")

    last_f = date.today() if is_free else user['last_free_spin']
    cursor.execute("UPDATE users SET coin = coin - %s, total_spent = %s, last_free_spin = %s, gem = gem + %s WHERE user_id = %s", 
                   (cost, new_total_spent, last_f, gems_total, user_id))
    conn.commit(); conn.close()
    
    emb = discord.Embed(title="🎡 KẾT QUẢ QUAY", color=0xffd700)
    emb.description = "\n".join([f"**Lượt {i+1}:** {res}" for i, res in enumerate(final_res)])
    await ctx.send(embed=emb)

# --- LỆNH ADMIN ---

@bot.command(name="addcoin")
@commands.has_any_role(1490238321312665600, 1490238659503325224)
async def add_coin(ctx, member: discord.Member, amount: int):
    user_id = str(member.id); conn = get_db(); cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id, coin) VALUES (%s, %s) ON DUPLICATE KEY UPDATE coin = coin + %s", (user_id, amount, amount))
    conn.commit(); conn.close(); await ctx.send(f"✅ Đã cộng {amount:,} Coin cho {member.mention}!")

@bot.command(name="adddaquy")
@commands.has_any_role(1490238321312665600, 1490238659503325224)
async def add_gem(ctx, member: discord.Member, amount: int):
    user_id = str(member.id); conn = get_db(); cursor = conn.cursor()
    cursor.execute("INSERT INTO users (user_id, gem) VALUES (%s, %s) ON DUPLICATE KEY UPDATE gem = gem + %s", (user_id, amount, amount))
    conn.commit(); conn.close(); await ctx.send(f"✅ Đã cộng {amount:,} Đá cho {member.mention}!")

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user} Online!')

bot.run(TOKEN)