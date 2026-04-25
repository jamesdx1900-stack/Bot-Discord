import discord
from discord.ext import commands, tasks
import pymysql
import random
import asyncio
import os
from datetime import date
from flask import Flask
from threading import Thread

# --- KHỞI TẠO WEB SERVER ĐỂ GIỮ BOT ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CẤU HÌNH ---
# Sử dụng os.environ để lấy Token từ mục "Secrets" trong Replit
TOKEN = os.environ.get('TOKEN') 

DB_CONFIG = {
    'host': 'YOUR_REMOTE_DB_HOST',  # THAY ĐỔI: Không dùng localhost
    'user': 'root',
    'password': 'your_password',
    'database': 'discord_bot',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}
ID_KENH_THONG_BAO = 1490233426211770509 

intents = discord.Intents.default()
intents.message_content = True

# --- PHẦN CLASS TAIXIUVIEW & MYBOT (Giữ nguyên logic của bạn) ---
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
        try:
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute("SELECT gem FROM users WHERE user_id=%s", (user_id,))
            user = cursor.fetchone()

            if not user or user['gem'] < amount:
                return await interaction.response.send_message("❌ Không đủ Đá Quý!", ephemeral=True)

            cursor.execute("UPDATE users SET gem = gem - %s WHERE user_id = %s", (amount, user_id))
            conn.commit()
            self.bot.danh_sach_cuoc.append({'user_id': user_id, 'lua_chon': choice, 'bet': amount})
            await interaction.response.send_message(f"✅ Đã đặt **{amount:,}** vào **{choice.upper()}**!", ephemeral=True)
        except Exception as e:
            print(f"Lỗi DB: {e}")
        finally:
            conn.close()

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
        if not channel: return

        while not self.is_closed():
            self.phien_hien_tai += 1
            self.phien_dang_mo = True
            self.danh_sach_cuoc = []
            thoi_gian_con_lai = 60
            view = TaiXiuView(self)
            
            soi_cau_str = " ".join(self.lich_su_cau[-10:]) if self.lich_su_cau else "Chưa có dữ liệu"
            
            embed_cd = discord.Embed(title=f"🎲 TÀI XỈU PHIÊN #{self.phien_hien_tai}", color=0x3498db)
            embed_cd.add_field(name="📊 Cầu (10 phiên)", value=f"**{soi_cau_str}**", inline=False)
            embed_cd.add_field(name="⚡ Tỉ lệ", value="**x1.95**", inline=True)
            embed_cd.add_field(name="👤 Đã cược", value=f"**0**", inline=True)
            embed_cd.description = f"⏳ Còn lại: **{thoi_gian_con_lai} giây**"
            
            msg = await channel.send(embed=embed_cd, view=view)

            for _ in range(6): # Cập nhật mỗi 10s
                await asyncio.sleep(10)
                thoi_gian_con_lai -= 10
                if thoi_gian_con_lai <= 0: break
                embed_cd.description = f"⏳ Còn lại: **{thoi_gian_con_lai} giây**"
                embed_cd.set_field_at(2, name="👤 Đã cược", value=f"**{len(self.danh_sach_cuoc)}**")
                try: await msg.edit(embed=embed_cd)
                except: pass

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
            await asyncio.sleep(10) # Nghỉ giữa các phiên

bot = MyBot()

# --- CÁC COMMAND KHÁC GIỮ NGUYÊN (Copy từ code cũ của bạn vào đây) ---
# ... (Phần quay, vi, addcoin, adddaquy) ...

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user} Online!')

# Chạy server giữ alive và bot
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
