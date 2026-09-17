import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import json
import os
import datetime
import asyncio
import random
import logging
import aiohttp
from database import *

# ===================== CONFIG =====================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN não definido.")

CONFIG_FILE = "/app/data/config.json"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Cores
PINK = 0xFFB6C1
CREAM = 0xFFF8DC
BROWN = 0xD2B48C
ROSE = 0xFF69B4
GREEN = 0x00FF00
RED = 0xFF0000
GOLD = 0xFFD700

# URLs
FOTO_PERFIL_URL = os.getenv("FOTO_PERFIL_URL", "https://cdn.discordapp.com/attachments/1530244163591733388/1530261464735158302/file_00000000f840820eb47ef8c8b417de1d.png?ex=6a64ee8c&is=6a639d0c&hm=d0a67e2ef95d93d3f3ed856d94933806fde1180d5063ef8ee40113b39d09a279&")
BANNER_PAINEL_URL = os.getenv("BANNER_PAINEL_URL", "https://cdn.discordapp.com/attachments/1530244163591733388/1530264443945095358/file_00000000b1a4820e8b6a6dbfcf67947d.png?ex=6a64f152&is=6a639fd2&hm=ac86542247d4c60b3b133a3af508a6ce455795ed7a6075056ff622df24875088&")
BANNER_TICKET_URL = os.getenv("BANNER_TICKET_URL", "https://cdn.discordapp.com/attachments/1530244163591733388/1530264209986687046/file_0000000073f4820ea170f186c8109b1f.png?ex=6a64f11a&is=6a639f9a&hm=90502790785b0e77c5b36cf5b70da0cc464130c91e811c4cfe29f95dfafafe64&")

# ===================== CONFIGURAÇÃO =====================
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    default = {
        "guild_id": None,
        "verified_role_id": None,
        "age_verification_enabled": False,
        "age_verified_role_id": None,
        "age_underage_role_id": None,
        "age_kick_underage": True,   # Se True, expulsa menores; se False, dá cargo de menor
        "age_verification_channel_id": None,
        "age_unverified_role_id": None,
        "age_native_verification_role_id": None,
        "age_panel_channel_id": None,
        "age_panel_message_id": None,
        "welcome_channel_id": None,
        "welcome_message": "Bem-vindo(a) ao cantinho da Nita! 🌸",
        "welcome_image_url": BANNER_PAINEL_URL,
        "admin_role_ids": [],
        "voice_channel_id": None,
        "voice_mute": True,
        "bot_status": "online",
        "painel_channel_id": None,
        "painel_message_id": None,
        "verification_channel_id": None,
        "ticket_category_doubt_id": None,
        "ticket_category_purchase_id": None,
        "ticket_logs_channel_id": None,
        "ticket_panel_channel_id": None,
        "ticket_panel_message_id": None,
        "ticket_support_role_ids": [],
        "feedback_channel_id": None,
        "suggestions_channel_id": None,
        "suggestions_panel_channel_id": None,
        "suggestions_panel_message_id": None,
        "verification_panel_channel_id": None,
        "verification_panel_message_id": None,
        "moderation_logs_channel_id": None,
        "reminders": []
    }
    save_config(default)
    return default

def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ===================== BOT =====================
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
config = load_config()

# ===================== UTILIDADES =====================
def get_guild():
    gid = config.get("guild_id")
    return bot.get_guild(gid) if gid else None

def get_voice_channel():
    guild = get_guild()
    if guild:
        cid = config.get("voice_channel_id")
        return guild.get_channel(cid) if cid else None
    return None

async def update_voice_name():
    guild = get_guild()
    if not guild:
        return
    channel = get_voice_channel()
    if not channel or not isinstance(channel, discord.VoiceChannel):
        return
    new_name = f"👥 {guild.member_count} membros"
    if channel.name != new_name:
        try:
            await channel.edit(name=new_name)
        except:
            pass

async def update_status():
    guild = get_guild()
    if guild:
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible
        }
        status = status_map.get(config.get("bot_status", "online"), discord.Status.online)
        await bot.change_presence(
            status=status,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"🌸 {guild.member_count} membros"
            )
        )

async def update_voice_mute():
    guild = get_guild()
    if not guild:
        return
    voice_client = guild.voice_client
    if not voice_client or not voice_client.is_connected():
        return
    mute = config.get("voice_mute", True)
    try:
        await guild.me.edit(mute=mute)
        logger.info(f"Bot {'mutado' if mute else 'desmutado'} na call.")
    except Exception as e:
        logger.error(f"Erro ao mutar/desmutar: {e}")

async def log_moderation_action(action, moderator, target, reason=None):
    log_moderation(action, moderator.id, target.id, reason or "Sem motivo")
    channel_id = config.get("moderation_logs_channel_id")
    if channel_id:
        channel = moderator.guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title=f"🛡️ Ação de Moderação",
                description=f"**Ação:** {action}\n**Moderador:** {moderator.mention}\n**Alvo:** {target.mention}\n**Motivo:** {reason or 'Não informado'}",
                color=RED if "ban" in action.lower() or "kick" in action.lower() else GOLD,
                timestamp=datetime.datetime.now()
            )
            embed.set_footer(text=f"ID do alvo: {target.id}")
            await channel.send(embed=embed)

async def log_age_verification(user, approved, age=None, birth_date=None, underage_role_given=False, error_msg=None):
    channel_id = config.get("moderation_logs_channel_id")
    if not channel_id:
        return
    channel = user.guild.get_channel(channel_id)
    if not channel:
        return
    embed = discord.Embed(
        title="🔞 Verificação de Idade",
        description=f"**Usuário:** {user.mention}\n**ID:** {user.id}\n**Resultado:** {'✅ Aprovado' if approved else '❌ Reprovado'}",
        color=GREEN if approved else RED,
        timestamp=datetime.datetime.now()
    )
    if birth_date:
        embed.add_field(name="Data informada", value=birth_date, inline=False)
    if age is not None:
        embed.add_field(name="Idade calculada", value=f"{age} anos", inline=False)
    if error_msg:
        embed.add_field(name="Erro", value=error_msg, inline=False)
    if not approved and underage_role_given:
        embed.add_field(name="Ação", value="Cargo de menor de idade atribuído (não expulso).", inline=False)
    elif not approved and not underage_role_given and not error_msg:
        embed.add_field(name="Ação", value="Usuário expulso por idade insuficiente.", inline=False)
    await channel.send(embed=embed)

def calcular_idade(data_nasc):
    try:
        nasc = datetime.datetime.strptime(data_nasc, "%d/%m/%Y")
        hoje = datetime.datetime.now()
        idade = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
        return idade
    except ValueError:
        return None

# ===================== EMBEDS =====================
def embed_painel():
    e = discord.Embed(
        title="🌸 Painel da Nita",
        description=(
            "**Bem-vinda(o) ao centro de configurações!**\n\n"
            "✅ **Verificação** – Captcha e +18\n"
            "💌 **Boas‑vindas** – mensagem, imagem e canal\n"
            "🔊 **Voz** – canal 24h, mute e status\n"
            "📌 **Painéis** – onde cada painel ficará fixo\n"
            "🎫 **Tickets** – categorias, suporte e painel\n"
            "⭐ **Avaliações** – feedback dos tickets\n"
            "💡 **Sugestões** – comunidade vota\n"
            "📅 **Eventos** – agendamento de mensagens\n"
            "⏰ **Lembretes** – agende datas e horas\n\n"
            "Selecione uma opção no menu abaixo. 💖"
        ),
        color=PINK
    )
    e.set_thumbnail(url=FOTO_PERFIL_URL)
    e.set_image(url=BANNER_PAINEL_URL)
    e.set_footer(text="🌸 Com amor, Nita", icon_url=FOTO_PERFIL_URL)
    return e

def embed_ticket_painel():
    e = discord.Embed(
        title="🎫 Central de Tickets",
        description=(
            "**Olá, seja bem-vindo(a)!** 🌸\n\n"
            "Aqui você pode abrir um ticket para receber atendimento personalizado.\n"
            "Clique no botão correspondente:\n\n"
            "❓ **Dúvidas** – perguntas gerais\n"
            "🛒 **Compras** – vendas ou compras\n\n"
            "Nossa equipe estará à disposição para te ajudar com carinho. 💖"
        ),
        color=PINK
    )
    e.set_thumbnail(url=FOTO_PERFIL_URL)
    e.set_image(url=BANNER_TICKET_URL)
    e.set_footer(text="🌸 Com amor, Nita", icon_url=FOTO_PERFIL_URL)
    return e

def embed_sugestoes_painel():
    e = discord.Embed(
        title="💡 Painel de Sugestões",
        description=(
            "**Queremos ouvir você!** 🌸\n\n"
            "Clique no botão abaixo e compartilhe sua ideia.\n\n"
            "Todas as sugestões serão votadas pela comunidade. 💖"
        ),
        color=PINK
    )
    e.set_thumbnail(url=FOTO_PERFIL_URL)
    e.set_image(url=BANNER_PAINEL_URL)
    e.set_footer(text="🌸 Com amor, Nita", icon_url=FOTO_PERFIL_URL)
    return e

def embed_verificacao_painel():
    e = discord.Embed(
        title="✅ Verificação de Segurança",
        description=(
            "**Proteja sua conta e ganhe acesso total!** 🌸\n\n"
            "Clique no botão **'🔐 Verificar Agora'** abaixo para iniciar sua verificação.\n"
            "Responda corretamente ao desafio matemático para ganhar o cargo de **Verificado**.\n\n"
            "**Como funciona:**\n"
            "• Clique em 'Verificar Agora'.\n"
            "• Um desafio aparecerá neste canal.\n"
            "• Clique em 'Verificar' e digite o resultado.\n"
            "• Se acertar, ganhará automaticamente o cargo.\n\n"
            "Caso já tenha o cargo, ignore esta mensagem.\n"
            "Qualquer dúvida, abra um ticket. 💖"
        ),
        color=ROSE
    )
    e.set_thumbnail(url=FOTO_PERFIL_URL)
    e.set_image(url=BANNER_PAINEL_URL)
    e.set_footer(text="🌸 Com amor, Nita", icon_url=FOTO_PERFIL_URL)
    return e

# ===================== VIEWS =====================

# ---------- PAINEL PRINCIPAL ----------
class MainPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MainSelect())

class MainSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="✅ Verificação Captcha", value="captcha", emoji="✅"),
            discord.SelectOption(label="🔞 Verificação +18", value="age18", emoji="🔞"),
            discord.SelectOption(label="💌 Boas‑vindas", value="welcome", emoji="💌"),
            discord.SelectOption(label="🔊 Configurar Voz", value="voice_config", emoji="🔊"),
            discord.SelectOption(label="👑 Cargos de Admin", value="admin", emoji="👑"),
            discord.SelectOption(label="📌 Painel Fixo", value="painel", emoji="📌"),
            discord.SelectOption(label="🎫 Tickets", value="tickets", emoji="🎫"),
            discord.SelectOption(label="⭐ Avaliações (Feedback)", value="feedback", emoji="⭐"),
            discord.SelectOption(label="💡 Sugestões", value="suggestions", emoji="💡"),
            discord.SelectOption(label="📅 Eventos", value="events", emoji="📅"),
            discord.SelectOption(label="⏰ Lembretes", value="reminder", emoji="⏰"),
        ]
        super().__init__(placeholder="Escolha uma configuração", options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        if value == "captcha":
            await interaction.response.send_message("Configure a verificação Captcha:", view=VerificationConfigView(), ephemeral=True)
        elif value == "age18":
            await interaction.response.send_message("Configure o sistema de verificação +18:", view=AgeVerificationConfigView(), ephemeral=True)
        elif value == "welcome":
            await interaction.response.send_message("Personalize as boas‑vindas:", view=WelcomeView(), ephemeral=True)
        elif value == "voice_config":
            await interaction.response.send_message("Configure as opções de voz:", view=VoiceConfigView(), ephemeral=True)
        elif value == "admin":
            await interaction.response.send_message("Selecione os cargos de administrador:", view=AdminRolesView(), ephemeral=True)
        elif value == "painel":
            await interaction.response.send_message("Escolha o canal para o painel principal:", view=PainelChannelView(), ephemeral=True)
        elif value == "tickets":
            await interaction.response.send_message("Configure o sistema de tickets:", view=TicketConfigView(), ephemeral=True)
        elif value == "feedback":
            await interaction.response.send_message("Configure o canal para avaliações de tickets:", view=FeedbackChannelView(), ephemeral=True)
        elif value == "suggestions":
            await interaction.response.send_message("Configure o painel de sugestões:", view=SuggestionsConfigView(), ephemeral=True)
        elif value == "events":
            await interaction.response.send_modal(EventModal())
        elif value == "reminder":
            await interaction.response.send_modal(ReminderModal())

# ---------- CONFIGURAÇÃO +18 ----------
class AgeVerificationConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="🔞 Ativar/Desativar", style=discord.ButtonStyle.primary)
    async def toggle_enabled(self, interaction, button):
        current = config.get("age_verification_enabled", False)
        config["age_verification_enabled"] = not current
        save_config(config)
        await interaction.response.send_message(f"✅ Sistema +18 {'ativado' if config['age_verification_enabled'] else 'desativado'}.", ephemeral=True)

    @ui.button(label="👑 Cargo +18 (Maiores)", style=discord.ButtonStyle.primary)
    async def set_adult_role(self, interaction, button):
        await interaction.response.send_message("Escolha o cargo para usuários MAIORES de 18 anos:", view=AgeAdultRoleView(), ephemeral=True)

    @ui.button(label="🧒 Cargo -18 (Menores)", style=discord.ButtonStyle.primary)
    async def set_underage_role(self, interaction, button):
        await interaction.response.send_message("Escolha o cargo para usuários MENORES de 18 anos:", view=AgeUnderageRoleView(), ephemeral=True)

    @ui.button(label="🚫 Expulsar Menores", style=discord.ButtonStyle.danger)
    async def toggle_kick(self, interaction, button):
        current = config.get("age_kick_underage", True)
        config["age_kick_underage"] = not current
        save_config(config)
        await interaction.response.send_message(f"✅ Expulsão de menores {'ativada' if config['age_kick_underage'] else 'desativada'}.", ephemeral=True)

    @ui.button(label="📢 Canal de Verificação", style=discord.ButtonStyle.primary)
    async def set_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal onde os usuários serão verificados:", view=AgeVerificationChannelView(), ephemeral=True)

    @ui.button(label="🔄 Cargo Verificação Nativa", style=discord.ButtonStyle.primary)
    async def set_native_role(self, interaction, button):
        await interaction.response.send_message("Escolha o cargo que o Discord concede após verificação nativa:", view=AgeNativeVerificationRoleView(), ephemeral=True)

    @ui.button(label="📢 Canal do Painel de Idade", style=discord.ButtonStyle.primary)
    async def set_age_panel_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal onde o painel de verificação de idade será enviado:", view=AgePanelChannelView(), ephemeral=True)

class AgeAdultRoleView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AgeAdultRoleSelect())

class AgeAdultRoleSelect(ui.Select):
    def __init__(self):
        opts = [discord.SelectOption(label="Nenhum", value="none")]
        guild = get_guild()
        if guild:
            for r in guild.roles:
                if r.name != "@everyone":
                    opts.append(discord.SelectOption(label=r.name, value=str(r.id)))
        super().__init__(placeholder="Cargo para MAIORES de 18", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        config["age_verified_role_id"] = None if val == "none" else int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Cargo +18 definido: {val if val != 'none' else 'Nenhum'}", ephemeral=True)

class AgeUnderageRoleView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AgeUnderageRoleSelect())

class AgeUnderageRoleSelect(ui.Select):
    def __init__(self):
        opts = [discord.SelectOption(label="Nenhum", value="none")]
        guild = get_guild()
        if guild:
            for r in guild.roles:
                if r.name != "@everyone":
                    opts.append(discord.SelectOption(label=r.name, value=str(r.id)))
        super().__init__(placeholder="Cargo para MENORES de 18", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        config["age_underage_role_id"] = None if val == "none" else int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Cargo -18 definido: {val if val != 'none' else 'Nenhum'}", ephemeral=True)

class AgeVerificationChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AgeVerificationChannelSelect())

class AgeVerificationChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal de verificação", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["age_verification_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal de verificação definido: <#{val}>", ephemeral=True)

class AgeNativeVerificationRoleView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AgeNativeVerificationRoleSelect())

class AgeNativeVerificationRoleSelect(ui.Select):
    def __init__(self):
        opts = [discord.SelectOption(label="Nenhum", value="none")]
        guild = get_guild()
        if guild:
            for r in guild.roles:
                if r.name != "@everyone":
                    opts.append(discord.SelectOption(label=r.name, value=str(r.id)))
        super().__init__(placeholder="Cargo da verificação nativa", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        config["age_native_verification_role_id"] = None if val == "none" else int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Cargo de verificação nativa definido: {val if val != 'none' else 'Nenhum'}", ephemeral=True)

class AgePanelChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AgePanelChannelSelect())

class AgePanelChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal do painel de idade", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["age_panel_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal do painel de idade definido: <#{val}>", ephemeral=True)

# ---------- PAINEL DE VERIFICAÇÃO DE IDADE (VIEW COM BOTÃO) ----------
class AgeVerificationPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔞 Verificar Idade", style=discord.ButtonStyle.danger, custom_id="age_panel_verify")
    async def age_panel_verify(self, interaction: discord.Interaction, button: ui.Button):
        if not config.get("age_verification_enabled", False):
            await interaction.response.send_message("❌ O sistema de verificação de idade está desativado.", ephemeral=True)
            return
        role_id = config.get("age_verified_role_id")
        if role_id:
            role = interaction.guild.get_role(role_id)
            if role and role in interaction.user.roles:
                await interaction.response.send_message("✅ Você já está verificado!", ephemeral=True)
                return
        await interaction.response.send_modal(AgeVerificationModal(interaction.user.id))

# ---------- CONFIGURAÇÃO DE VOZ ----------
class VoiceConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="🔇 Mute na Call", style=discord.ButtonStyle.primary)
    async def toggle_mute(self, interaction, button):
        current = config.get("voice_mute", True)
        config["voice_mute"] = not current
        save_config(config)
        await update_voice_mute()
        await interaction.response.send_message(f"✅ Mute {'ativado' if config['voice_mute'] else 'desativado'}.", ephemeral=True)

    @ui.button(label="🎭 Status do Bot", style=discord.ButtonStyle.primary)
    async def set_status(self, interaction, button):
        await interaction.response.send_message("Escolha o status do bot:", view=StatusSelectView(), ephemeral=True)

class StatusSelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(StatusSelect())

class StatusSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🟢 Online", value="online", emoji="🟢"),
            discord.SelectOption(label="🟡 Ausente", value="idle", emoji="🟡"),
            discord.SelectOption(label="🔴 Não perturbar", value="dnd", emoji="🔴"),
            discord.SelectOption(label="⚫ Invisível", value="invisible", emoji="⚫"),
        ]
        super().__init__(placeholder="Escolha o status", options=options)

    async def callback(self, interaction):
        status = self.values[0]
        config["bot_status"] = status
        save_config(config)
        await update_status()
        await interaction.response.send_message(f"✅ Status alterado para **{status}**", ephemeral=True)

# ---------- CONFIGURAÇÃO CAPTCHA ----------
class VerificationConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="👑 Cargo de Verificação", style=discord.ButtonStyle.primary)
    async def set_role(self, interaction, button):
        await interaction.response.send_message("Escolha o cargo que será dado após a verificação:", view=CaptchaRoleView(), ephemeral=True)

    @ui.button(label="📢 Canal de Verificação (onde o captcha será enviado)", style=discord.ButtonStyle.primary)
    async def set_verification_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal onde os desafios de verificação serão enviados:", view=VerificationChannelView(), ephemeral=True)

    @ui.button(label="📢 Canal do Painel de Verificação", style=discord.ButtonStyle.primary)
    async def set_panel_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal onde o painel informativo de verificação será enviado:", view=VerificationPanelChannelView(), ephemeral=True)

class CaptchaRoleView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(CaptchaRoleSelect())

class CaptchaRoleSelect(ui.Select):
    def __init__(self):
        opts = [discord.SelectOption(label="Nenhum", value="none")]
        guild = get_guild()
        if guild:
            for r in guild.roles:
                if r.name != "@everyone":
                    opts.append(discord.SelectOption(label=r.name, value=str(r.id)))
        super().__init__(placeholder="Escolha o cargo de verificação", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        config["verified_role_id"] = None if val == "none" else int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Cargo de verificação definido: {val if val != 'none' else 'Nenhum'}", ephemeral=True)

class VerificationChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(VerificationChannelSelect())

class VerificationChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal de verificação", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["verification_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal de verificação definido: <#{val}>", ephemeral=True)

class VerificationPanelChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(VerificationPanelChannelSelect())

class VerificationPanelChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal do painel de verificação", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["verification_panel_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal do painel de verificação definido: <#{val}>", ephemeral=True)

# ---------- CONFIGURAÇÃO DE SUGESTÕES ----------
class SuggestionsConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="📢 Canal do Painel", style=discord.ButtonStyle.primary)
    async def set_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal para o painel de sugestões:", view=SuggestionsPanelChannelView(), ephemeral=True)

    @ui.button(label="📋 Canal de Sugestões", style=discord.ButtonStyle.primary)
    async def set_suggestions_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal onde as sugestões serão enviadas:", view=SuggestionsChannelView(), ephemeral=True)

class SuggestionsPanelChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(SuggestionsPanelChannelSelect())

class SuggestionsPanelChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal do painel de sugestões", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["suggestions_panel_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal do painel de sugestões definido: <#{val}>", ephemeral=True)

class SuggestionsChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(SuggestionsChannelSelect())

class SuggestionsChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal de sugestões", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["suggestions_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal de sugestões definido: <#{val}>", ephemeral=True)

# ---------- BOTÃO DE SUGESTÃO ----------
class SuggestionButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="💡 Enviar Sugestão", style=discord.ButtonStyle.primary, custom_id="suggest_btn")
    async def suggest(self, interaction, button):
        await interaction.response.send_modal(SuggestionModal())

class SuggestionModal(ui.Modal, title="💡 Enviar Sugestão"):
    sugestao = ui.TextInput(label="Sua sugestão", style=discord.TextStyle.paragraph, placeholder="Descreva sua ideia...", required=True)

    async def on_submit(self, interaction):
        channel_id = config.get("suggestions_channel_id")
        if not channel_id:
            await interaction.response.send_message("❌ Canal de sugestões não configurado.", ephemeral=True)
            return
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("❌ Canal de sugestões inválido.", ephemeral=True)
            return

        embed = discord.Embed(
            title="💡 Nova Sugestão",
            description=self.sugestao.value,
            color=PINK
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"ID: {interaction.user.id}")
        msg = await channel.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        await interaction.response.send_message("✅ Sugestão enviada! Obrigado pela contribuição.", ephemeral=True)

# ---------- CANAL DE AVALIAÇÕES ----------
class FeedbackChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(FeedbackChannelSelect())

class FeedbackChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal de feedback", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["feedback_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal de feedback definido: <#{val}>", ephemeral=True)

# ---------- CANAL DE LOGS DE MODERAÇÃO ----------
class ModerationLogsChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(ModerationLogsChannelSelect())

class ModerationLogsChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal de logs de moderação", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["moderation_logs_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal de logs de moderação definido: <#{val}>", ephemeral=True)

# ---------- CANAL DO PAINEL PRINCIPAL ----------
class PainelChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(PainelChannelSelect())

class PainelChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal disponível", value="none")]
        super().__init__(placeholder="Escolha o canal do painel principal", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        cid = int(val)
        config["painel_channel_id"] = cid
        save_config(config)
        channel = interaction.guild.get_channel(cid)
        if channel:
            msg = await channel.send(embed=embed_painel(), view=MainPanel())
            config["painel_message_id"] = msg.id
            save_config(config)
            await interaction.response.send_message(f"✅ Painel principal enviado em {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)

# ---------- CANAL DO PAINEL DE TICKETS ----------
class TicketPanelChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(TicketPanelChannelSelect())

class TicketPanelChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal do painel de tickets", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["ticket_panel_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal do painel de tickets definido: <#{val}>", ephemeral=True)

# ---------- BOAS‑VINDAS ----------
class WelcomeView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="✏️ Mensagem Padrão", style=discord.ButtonStyle.primary)
    async def edit_default_msg(self, interaction, button):
        await interaction.response.send_modal(WelcomeDefaultMessageModal())

    @ui.button(label="🖼️ Imagem Padrão", style=discord.ButtonStyle.primary)
    async def edit_default_img(self, interaction, button):
        await interaction.response.send_modal(WelcomeDefaultImageModal())

    @ui.button(label="📢 Canal", style=discord.ButtonStyle.primary)
    async def choose_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal de boas‑vindas:", view=WelcomeChannelView(), ephemeral=True)

    @ui.button(label="👤 Personalizar para usuário", style=discord.ButtonStyle.primary)
    async def customize_user(self, interaction, button):
        await interaction.response.send_message("Selecione um usuário para personalizar a mensagem de boas‑vindas:", view=WelcomeUserSelectView(), ephemeral=True)

class WelcomeDefaultMessageModal(ui.Modal, title="Mensagem Padrão de Boas‑vindas"):
    msg = ui.TextInput(label="Nova mensagem", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction):
        config["welcome_message"] = self.msg.value
        save_config(config)
        await interaction.response.send_message("✅ Mensagem padrão atualizada!", ephemeral=True)

class WelcomeDefaultImageModal(ui.Modal, title="Imagem Padrão"):
    url = ui.TextInput(label="URL da imagem", required=True)

    async def on_submit(self, interaction):
        config["welcome_image_url"] = self.url.value
        save_config(config)
        await interaction.response.send_message("✅ Imagem padrão atualizada!", ephemeral=True)

class WelcomeChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(WelcomeChannelSelect())

class WelcomeChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal disponível", value="none")]
        super().__init__(placeholder="Escolha o canal de boas‑vindas", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["welcome_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal de boas‑vindas definido: <#{val}>", ephemeral=True)

class WelcomeUserSelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(WelcomeUserSelect())

class WelcomeUserSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for m in guild.members:
                if not m.bot:
                    opts.append(discord.SelectOption(label=m.display_name, value=str(m.id), description=f"@{m.name}"))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum membro", value="none")]
        super().__init__(placeholder="Selecione um usuário", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum usuário selecionado.", ephemeral=True)
            return
        user_id = int(val)
        modal = WelcomeUserMessageModal(user_id)
        await interaction.response.send_modal(modal)

class WelcomeUserMessageModal(ui.Modal, title="Mensagem Personalizada"):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.msg = ui.TextInput(label="Mensagem personalizada", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.msg)
        self.img = ui.TextInput(label="URL da imagem (opcional)", required=False)
        self.add_item(self.img)

    async def on_submit(self, interaction):
        message = self.msg.value
        image_url = self.img.value or None
        set_welcome_message(self.user_id, message, image_url)
        user = interaction.guild.get_member(self.user_id)
        await interaction.response.send_message(f"✅ Mensagem personalizada definida para {user.mention if user else 'usuário'}!", ephemeral=True)

# ---------- CARGOS DE ADMIN ----------
class AdminRolesView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AdminRoleSelect())

class AdminRoleSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for r in guild.roles:
                if r.name != "@everyone":
                    opts.append(discord.SelectOption(label=r.name, value=str(r.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum cargo disponível", value="none")]
        super().__init__(placeholder="Selecione cargos (múltiplos)", options=opts[:25], min_values=0, max_values=len(opts))

    async def callback(self, interaction):
        vals = self.values
        if "none" in vals or not vals:
            config["admin_role_ids"] = []
        else:
            config["admin_role_ids"] = [int(v) for v in vals]
        save_config(config)
        await interaction.response.send_message(f"✅ {len(vals)} cargos definidos.", ephemeral=True)

# ---------- CANAL DE VOZ ----------
class VoiceChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(VoiceChannelSelect())

class VoiceChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.voice_channels:
                opts.append(discord.SelectOption(label=c.name, value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal de voz", value="none")]
        super().__init__(placeholder="Escolha o canal de voz 24h", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        cid = int(val)
        config["voice_channel_id"] = cid
        save_config(config)
        channel = interaction.guild.get_channel(cid)
        if channel and isinstance(channel, discord.VoiceChannel):
            try:
                if not interaction.guild.voice_client:
                    await channel.connect()
                else:
                    await interaction.guild.voice_client.move_to(channel)
                await update_voice_name()
                await update_voice_mute()
                await interaction.response.send_message(f"✅ Conectado ao {channel.name}", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)

# ---------- TICKETS (CONFIGURAÇÃO) ----------
class TicketConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="📂 Categoria Dúvidas", style=discord.ButtonStyle.primary)
    async def cat_doubt(self, interaction, button):
        await interaction.response.send_message("Escolha a categoria para Dúvidas:", view=TicketCategoryView("doubt"), ephemeral=True)

    @ui.button(label="🛒 Categoria Compras", style=discord.ButtonStyle.primary)
    async def cat_purchase(self, interaction, button):
        await interaction.response.send_message("Escolha a categoria para Compras:", view=TicketCategoryView("purchase"), ephemeral=True)

    @ui.button(label="📋 Logs", style=discord.ButtonStyle.primary)
    async def logs(self, interaction, button):
        await interaction.response.send_message("Escolha o canal de logs:", view=TicketLogsChannelView(), ephemeral=True)

    @ui.button(label="📢 Canal do Painel de Tickets", style=discord.ButtonStyle.primary)
    async def panel_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal do painel de tickets:", view=TicketPanelChannelView(), ephemeral=True)

    @ui.button(label="👥 Cargos de Suporte", style=discord.ButtonStyle.primary)
    async def support_roles(self, interaction, button):
        await interaction.response.send_message("Selecione os cargos de suporte:", view=TicketSupportRolesView(), ephemeral=True)

    @ui.button(label="📊 Logs de Moderação", style=discord.ButtonStyle.primary)
    async def mod_logs(self, interaction, button):
        await interaction.response.send_message("Escolha o canal para logs de moderação:", view=ModerationLogsChannelView(), ephemeral=True)

class TicketCategoryView(ui.View):
    def __init__(self, tipo):
        super().__init__(timeout=60)
        self.tipo = tipo
        self.add_item(TicketCategorySelect(tipo))

class TicketCategorySelect(ui.Select):
    def __init__(self, tipo):
        self.tipo = tipo
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.categories:
                opts.append(discord.SelectOption(label=c.name, value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhuma categoria", value="none")]
        super().__init__(placeholder="Escolha a categoria", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhuma categoria selecionada.", ephemeral=True)
            return
        cid = int(val)
        if self.tipo == "doubt":
            config["ticket_category_doubt_id"] = cid
        elif self.tipo == "purchase":
            config["ticket_category_purchase_id"] = cid
        save_config(config)
        await interaction.response.send_message(f"✅ Categoria de {self.tipo} definida.", ephemeral=True)

class TicketLogsChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(TicketLogsChannelSelect())

class TicketLogsChannelSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.text_channels:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal", value="none")]
        super().__init__(placeholder="Escolha o canal de logs", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["ticket_logs_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Logs definidos para <#{val}>", ephemeral=True)

class TicketSupportRolesView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(TicketSupportRolesSelect())

class TicketSupportRolesSelect(ui.Select):
    def __init__(self):
        guild = get_guild()
        opts = []
        if guild:
            for r in guild.roles:
                if r.name != "@everyone":
                    opts.append(discord.SelectOption(label=r.name, value=str(r.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum cargo disponível", value="none")]
        super().__init__(placeholder="Selecione cargos de suporte", options=opts[:25], min_values=0, max_values=len(opts))

    async def callback(self, interaction):
        vals = self.values
        if "none" in vals or not vals:
            config["ticket_support_role_ids"] = []
        else:
            config["ticket_support_role_ids"] = [int(v) for v in vals]
        save_config(config)
        await interaction.response.send_message(f"✅ {len(vals)} cargos definidos.", ephemeral=True)

# ---------- VIEW DO TICKET ----------
class TicketActionsView(ui.View):
    def __init__(self, ticket_type, ticket_name, user_id):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        self.ticket_name = ticket_name
        self.user_id = user_id

    @ui.button(label="⭐ Avaliar Ticket", style=discord.ButtonStyle.primary, custom_id="rate_ticket")
    async def rate_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id and not any(role.id in config.get("ticket_support_role_ids", []) for role in interaction.user.roles):
            await interaction.response.send_message("❌ Apenas o criador do ticket ou staff podem avaliar.", ephemeral=True)
            return
        await interaction.response.send_modal(TicketRatingModal(self.ticket_name))

    @ui.button(label="🔒 Fechar Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id and not any(role.id in config.get("ticket_support_role_ids", []) for role in interaction.user.roles):
            await interaction.response.send_message("❌ Você não tem permissão para fechar este ticket.", ephemeral=True)
            return
        confirm_view = ui.View()
        confirm_view.add_item(ConfirmCloseButton(self.ticket_type, self.ticket_name, self.user_id))
        await interaction.response.send_message(
            "⚠️ Tem certeza que deseja fechar este ticket? O canal será deletado.",
            view=confirm_view,
            ephemeral=True
        )

    @ui.button(label="👤 Adicionar Membro", style=discord.ButtonStyle.primary, custom_id="add_member")
    async def add_member(self, interaction: discord.Interaction, button: ui.Button):
        if not any(role.id in config.get("ticket_support_role_ids", []) for role in interaction.user.roles):
            await interaction.response.send_message("❌ Apenas staff pode adicionar membros.", ephemeral=True)
            return
        guild = interaction.guild
        if not guild:
            return
        members = [m for m in guild.members if not m.bot]
        if not members:
            await interaction.response.send_message("❌ Nenhum membro disponível.", ephemeral=True)
            return
        opts = []
        for m in members[:25]:
            opts.append(discord.SelectOption(label=m.display_name, value=str(m.id), description=f"@{m.name}"))
        select = MemberAddSelect(self.ticket_type, self.ticket_name)
        select.options = opts
        view = ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("Selecione o membro para adicionar ao ticket:", view=view, ephemeral=True)

class MemberAddSelect(ui.Select):
    def __init__(self, ticket_type, ticket_name):
        super().__init__(placeholder="Escolha um membro", min_values=1, max_values=1)
        self.ticket_type = ticket_type
        self.ticket_name = ticket_name

    async def callback(self, interaction: discord.Interaction):
        member_id = int(self.values[0])
        member = interaction.guild.get_member(member_id)
        if not member:
            await interaction.response.send_message("❌ Membro não encontrado.", ephemeral=True)
            return
        channel = interaction.channel
        try:
            await channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
            await interaction.response.send_message(f"✅ {member.mention} foi adicionado ao ticket.", ephemeral=True)
            await channel.send(f"👤 {member.mention} foi adicionado ao ticket por {interaction.user.mention}.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao adicionar: {e}", ephemeral=True)

class ConfirmCloseButton(ui.Button):
    def __init__(self, ticket_type, ticket_name, user_id):
        super().__init__(label="✅ Sim, fechar", style=discord.ButtonStyle.danger)
        self.ticket_type = ticket_type
        self.ticket_name = ticket_name
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.channel
        log_channel_id = config.get("ticket_logs_channel_id")
        if log_channel_id:
            log_ch = interaction.guild.get_channel(log_channel_id)
            if log_ch:
                await log_ch.send(f"🔒 Ticket `{self.ticket_name}` foi fechado por {interaction.user.mention}.")
        remove_open_ticket(channel.id)
        try:
            await channel.delete()
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao deletar: {e}", ephemeral=True)

class TicketRatingModal(ui.Modal, title="⭐ Avalie o Atendimento"):
    def __init__(self, ticket_name):
        super().__init__()
        self.ticket_name = ticket_name
        self.rating = ui.Select(
            placeholder="Escolha uma nota",
            options=[
                discord.SelectOption(label="⭐ 1 - Péssimo", value="1"),
                discord.SelectOption(label="⭐⭐ 2 - Ruim", value="2"),
                discord.SelectOption(label="⭐⭐⭐ 3 - Regular", value="3"),
                discord.SelectOption(label="⭐⭐⭐⭐ 4 - Bom", value="4"),
                discord.SelectOption(label="⭐⭐⭐⭐⭐ 5 - Excelente", value="5")
            ]
        )
        self.add_item(self.rating)
        self.comment = ui.TextInput(label="Comentário (opcional)", style=discord.TextStyle.paragraph, required=False)
        self.add_item(self.comment)

    async def on_submit(self, interaction):
        rating = int(self.rating.values[0])
        comment = self.comment.value or "Sem comentário"
        add_ticket_feedback(interaction.channel.id, interaction.user.id, rating, comment)
        feedback_channel_id = config.get("feedback_channel_id")
        if feedback_channel_id:
            channel = interaction.guild.get_channel(feedback_channel_id)
            if channel:
                embed = discord.Embed(
                    title="⭐ Nova Avaliação de Ticket",
                    description=f"**Usuário:** {interaction.user.mention}\n**Ticket:** {self.ticket_name}\n**Nota:** {'⭐' * rating} ({rating}/5)\n**Comentário:** {comment}",
                    color=GOLD,
                    timestamp=datetime.datetime.now()
                )
                await channel.send(embed=embed)
        await interaction.response.send_message("✅ Obrigado pela sua avaliação! Ela foi enviada para nossa equipe.", ephemeral=True)

# ---------- PAINEL DE TICKETS (ABERTURA) ----------
class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="❓ Dúvidas", style=discord.ButtonStyle.primary, custom_id="ticket_open_doubt")
    async def open_doubt(self, interaction, button):
        await self.create_ticket(interaction, "doubt", "Dúvidas")

    @ui.button(label="🛒 Compras", style=discord.ButtonStyle.success, custom_id="ticket_open_purchase")
    async def open_purchase(self, interaction, button):
        await self.create_ticket(interaction, "purchase", "Compras")

    async def create_ticket(self, interaction, tipo, nome):
        count = count_user_tickets_last_hours(interaction.user.id, hours=8)
        if count >= 3:
            await interaction.response.send_message("❌ Você já atingiu o limite de 3 tickets abertos nas últimas 8 horas. Aguarde um pouco.", ephemeral=True)
            return

        guild = interaction.guild
        cid = config.get(f"ticket_category_{tipo}_id")
        if not cid:
            await interaction.response.send_message(f"❌ Categoria para {nome} não configurada.", ephemeral=True)
            return
        category = guild.get_channel(cid)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ Categoria inválida.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        support_role_ids = config.get("ticket_support_role_ids", [])
        support_mentions = []
        for rid in support_role_ids:
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                support_mentions.append(role.mention)

        nome_canal = f"ticket-{tipo}-{interaction.user.name[:20]}"
        try:
            channel = await guild.create_text_channel(
                name=nome_canal,
                category=category,
                overwrites=overwrites,
                reason=f"Ticket de {nome} aberto por {interaction.user}"
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao criar ticket: {e}", ephemeral=True)
            return

        add_open_ticket(interaction.user.id, channel.id)

        embed = discord.Embed(
            title=f"🌸 Ticket de {nome}",
            description=(
                f"**Olá {interaction.user.mention}!** Seja muito bem-vindo(a) ao nosso atendimento personalizado. 💖\n\n"
                "Agradecemos por entrar em contato conosco. Nossa equipe está pronta para te ajudar com todo carinho.\n\n"
                "**📌 Como funciona:**\n"
                "• Descreva sua dúvida ou pedido detalhadamente abaixo.\n"
                "• Você pode enviar arquivos, imagens ou links para facilitar.\n"
                "• Nossa equipe de suporte responderá assim que possível.\n\n"
                "**💡 Dicas:**\n"
                "• Seja claro e objetivo para agilizar o atendimento.\n"
                "• Fique atento às notificações deste canal.\n\n"
                "Aguarde um momento, por favor. Estamos aqui para você! 🌸"
            ),
            color=PINK
        )
        embed.set_image(url=BANNER_TICKET_URL)
        embed.set_footer(text="🌸 Equipe Nita", icon_url=FOTO_PERFIL_URL)
        await channel.send(embed=embed)

        if support_mentions:
            await channel.send(f"📢 **Atenção equipe de suporte:** {', '.join(support_mentions)} – novo ticket de {nome} aberto por {interaction.user.mention}.")

        await channel.send("🔧 **Ações disponíveis:**", view=TicketActionsView(tipo, nome_canal, interaction.user.id))

        log_channel_id = config.get("ticket_logs_channel_id")
        if log_channel_id:
            log_ch = guild.get_channel(log_channel_id)
            if log_ch:
                log_embed = discord.Embed(
                    title="📩 Novo Ticket",
                    description=f"**Tipo:** {nome}\n**Usuário:** {interaction.user.mention}\n**Canal:** {channel.mention}",
                    color=CREAM,
                    timestamp=datetime.datetime.now()
                )
                await log_ch.send(embed=log_embed)

        embed_resp = discord.Embed(
            title="✅ Ticket criado com sucesso!",
            description=f"🌸 Seu ticket de **{nome}** foi aberto em {channel.mention}.\nAguarde o atendimento.",
            color=PINK
        )
        await interaction.response.send_message(embed=embed_resp, ephemeral=True)

# ---------- VERIFICAÇÃO +18 (BOTÃO E MODAL) ----------
class AgeVerificationView(ui.View):
    def __init__(self, member):
        super().__init__(timeout=300)
        self.member = member

    @ui.button(label="🔞 Verificar Idade", style=discord.ButtonStyle.danger, custom_id="verify_age")
    async def verify_age(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("❌ Este botão não é para você.", ephemeral=True)
            return
        await interaction.response.send_modal(AgeVerificationModal(self.member.id))

class AgeVerificationModal(ui.Modal, title="🔞 Verificação de Idade"):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.nascimento = ui.TextInput(
            label="Digite sua data de nascimento",
            placeholder="DD/MM/AAAA",
            required=True,
            min_length=10,
            max_length=10
        )
        self.add_item(self.nascimento)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)
            return

        idade = calcular_idade(self.nascimento.value)
        if idade is None:
            await interaction.response.send_message("❌ Data inválida. Use o formato DD/MM/AAAA.", ephemeral=True)
            return

        adult_role_id = config.get("age_verified_role_id")
        underage_role_id = config.get("age_underage_role_id")
        unverified_role_id = config.get("age_unverified_role_id")
        kick_underage = config.get("age_kick_underage", True)  # True = expulsar, False = dar cargo

        if idade >= 18:
            # MAIOR DE IDADE
            if adult_role_id:
                role = guild.get_role(adult_role_id)
                if role:
                    await member.add_roles(role)
            if unverified_role_id:
                role = guild.get_role(unverified_role_id)
                if role:
                    await member.remove_roles(role)
            if underage_role_id:
                role = guild.get_role(underage_role_id)
                if role:
                    await member.remove_roles(role)

            await interaction.response.send_message("✅ **Verificação concluída!** Você ganhou acesso ao servidor. 🌸", ephemeral=True)

            welcome_channel_id = config.get("welcome_channel_id")
            if welcome_channel_id:
                channel = guild.get_channel(welcome_channel_id)
                if channel:
                    embed = discord.Embed(
                        title=f"🌸 Bem-vindo(a) ao servidor, {member.mention}!",
                        description=config.get("welcome_message", "Bem-vindo(a)! 💖"),
                        color=PINK
                    )
                    img = config.get("welcome_image_url", BANNER_PAINEL_URL)
                    if img:
                        embed.set_image(url=img)
                    await channel.send(embed=embed)

            await log_age_verification(member, True, idade, self.nascimento.value)

        else:
            # MENOR DE IDADE
            if kick_underage:
                # Tenta expulsar
                try:
                    await guild.kick(member, reason=f"Idade insuficiente ({idade} anos) – verificação +18")
                    await interaction.response.send_message("❌ Você foi expulso por ter menos de 18 anos.", ephemeral=True)
                    await log_age_verification(member, False, idade, self.nascimento.value, underage_role_given=False)
                except discord.Forbidden:
                    # Se não tiver permissão, dá o cargo de menor
                    error_msg = "Bot sem permissão para expulsar. Atribuído cargo de menor."
                    await interaction.response.send_message(
                        f"⚠️ Não foi possível expulsar você devido a uma configuração do servidor. "
                        f"Você recebeu o cargo restrito. Um moderador será notificado.",
                        ephemeral=True
                    )
                    if underage_role_id:
                        role = guild.get_role(underage_role_id)
                        if role:
                            await member.add_roles(role)
                    if unverified_role_id:
                        role = guild.get_role(unverified_role_id)
                        if role:
                            await member.remove_roles(role)
                    if adult_role_id:
                        role = guild.get_role(adult_role_id)
                        if role:
                            await member.remove_roles(role)
                    await log_age_verification(member, False, idade, self.nascimento.value, underage_role_given=True, error_msg=error_msg)
            else:
                # Não expulsa, apenas dá o cargo de menor
                if underage_role_id:
                    role = guild.get_role(underage_role_id)
                    if role:
                        await member.add_roles(role)
                if unverified_role_id:
                    role = guild.get_role(unverified_role_id)
                    if role:
                        await member.remove_roles(role)
                if adult_role_id:
                    role = guild.get_role(adult_role_id)
                    if role:
                        await member.remove_roles(role)

                await interaction.response.send_message(
                    f"🔞 **Você é menor de idade ({idade} anos).** Você recebeu o cargo restrito. Algumas áreas do servidor podem estar bloqueadas.",
                    ephemeral=True
                )
                await log_age_verification(member, False, idade, self.nascimento.value, underage_role_given=True)

# ---------- CAPTCHA ----------
class CaptchaView(ui.View):
    def __init__(self, member, answer, guild_id, channel_id):
        super().__init__(timeout=300)
        self.member = member
        self.answer = answer
        self.guild_id = guild_id
        self.channel_id = channel_id

    @ui.button(label="✅ Verificar", style=discord.ButtonStyle.success, custom_id="captcha_verify")
    async def verify(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("❌ Este captcha não é para você.", ephemeral=True)
            return
        await interaction.response.send_modal(CaptchaModal(self.answer, self.guild_id, self.member.id, self.channel_id))

class CaptchaModal(ui.Modal, title="🔐 Verificação Captcha"):
    def __init__(self, answer, guild_id, user_id, channel_id):
        super().__init__()
        self.answer = answer
        self.guild_id = guild_id
        self.user_id = user_id
        self.channel_id = channel_id
        self.resposta = ui.TextInput(label="Digite o resultado da operação:", required=True, placeholder="Ex: 8")
        self.add_item(self.resposta)

    async def on_submit(self, interaction: discord.Interaction):
        if self.resposta.value.strip() == str(self.answer):
            guild = bot.get_guild(self.guild_id)
            if not guild:
                await interaction.response.send_message("❌ Servidor não encontrado.", ephemeral=True)
                return

            role_id = config.get("verified_role_id")
            if role_id:
                role = guild.get_role(role_id)
                if role:
                    member = guild.get_member(self.user_id)
                    if member:
                        await member.add_roles(role)

            if config.get("age_verification_enabled", False):
                channel = guild.get_channel(self.channel_id)
                if channel:
                    try:
                        await interaction.message.delete()
                    except:
                        pass
                    await iniciar_verificacao_idade(guild.get_member(self.user_id), channel)
                    await interaction.response.send_message("✅ Captcha resolvido! Agora verifique sua idade.", ephemeral=True)
                else:
                    await interaction.response.send_message("✅ Captcha resolvido! (não foi possível iniciar verificação de idade)", ephemeral=True)
            else:
                await interaction.response.send_message("✅ Verificação concluída! Você ganhou o cargo de verificado.", ephemeral=True)
                try:
                    await interaction.message.delete()
                except:
                    pass
        else:
            await interaction.response.send_message("❌ Resposta incorreta. Tente novamente.", ephemeral=True)

# ---------- INICIAR VERIFICAÇÃO DE IDADE ----------
async def iniciar_verificacao_idade(member: discord.Member, channel: discord.TextChannel):
    verified_role_id = config.get("age_verified_role_id")
    if verified_role_id:
        role = member.guild.get_role(verified_role_id)
        if role and role in member.roles:
            return

    embed = discord.Embed(
        title="🔞 Verificação de Idade Obrigatória",
        description=(
            f"Olá {member.mention}! Para completar sua entrada, você precisa confirmar que tem **18 anos ou mais**.\n"
            "Clique no botão abaixo e informe sua data de nascimento.\n\n"
            "**Atenção:**\n"
            "• Usuários com menos de 18 anos serão removidos automaticamente.\n"
            "• A informação é confidencial e usada apenas para esta verificação."
        ),
        color=ROSE
    )
    embed.set_image(url=BANNER_PAINEL_URL)
    embed.set_footer(text="🌸 Com amor, Nita", icon_url=FOTO_PERFIL_URL)
    await channel.send(embed=embed, view=AgeVerificationView(member))

# ---------- BOTÃO DE VERIFICAÇÃO (PAINEL) ----------
class VerificationButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔐 Verificar Agora", style=discord.ButtonStyle.success, custom_id="verify_now")
    async def verify_now(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        channel = interaction.channel
        member = interaction.user

        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        answer = num1 + num2

        embed = discord.Embed(
            title=f"🔐 Verificação para {member.display_name}",
            description=(
                f"Olá {member.mention}! Para confirmar que você não é um robô, resolva a seguinte operação:\n\n"
                f"**{num1} + {num2} = ?**\n\n"
                "Clique no botão abaixo para responder."
            ),
            color=ROSE
        )
        view = CaptchaView(member, answer, guild.id, channel.id)
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Desafio enviado! Resolva a operação acima.", ephemeral=True)

# ---------- EVENTOS ----------
class EventModal(ui.Modal, title="📅 Agendar Evento"):
    mensagem = ui.TextInput(label="Mensagem", style=discord.TextStyle.paragraph, required=True)
    canal_id = ui.TextInput(label="ID do Canal", required=True)
    data = ui.TextInput(label="Data (AAAA-MM-DD)", required=True)
    hora = ui.TextInput(label="Hora (HH:MM)", required=True)
    repetir = ui.Select(
        placeholder="Repetição",
        options=[
            discord.SelectOption(label="Uma vez", value="once"),
            discord.SelectOption(label="A cada hora", value="60"),
            discord.SelectOption(label="A cada 6 horas", value="360"),
            discord.SelectOption(label="A cada 12 horas", value="720"),
            discord.SelectOption(label="Diariamente", value="1440"),
        ]
    )

    async def on_submit(self, interaction):
        try:
            channel_id = int(self.canal_id.value)
            dt = datetime.datetime.strptime(f"{self.data.value} {self.hora.value}", "%Y-%m-%d %H:%M")
        except:
            await interaction.response.send_message("❌ Formato inválido. Verifique canal, data e hora.", ephemeral=True)
            return
        if dt < datetime.datetime.now():
            await interaction.response.send_message("❌ A data/hora deve ser no futuro.", ephemeral=True)
            return
        repeat = self.repetir.values[0]
        repeat_interval = None if repeat == "once" else int(repeat)
        add_scheduled_event(
            event_type="repeat" if repeat_interval else "once",
            channel_id=channel_id,
            message=self.mensagem.value,
            schedule_time=dt.isoformat(),
            repeat_interval=repeat_interval
        )
        await interaction.response.send_message(f"✅ Evento agendado para {dt.strftime('%d/%m/%Y %H:%M')} no canal <#{channel_id}>.", ephemeral=True)

# ---------- LEMBRETES ----------
class ReminderModal(ui.Modal, title="🌸 Lembrete"):
    msg = ui.TextInput(label="Mensagem", style=discord.TextStyle.paragraph, required=True)
    data = ui.TextInput(label="Data (AAAA-MM-DD)", required=True)
    hora = ui.TextInput(label="Hora (HH:MM)", required=True)

    async def on_submit(self, interaction):
        try:
            dt = datetime.datetime.strptime(f"{self.data.value} {self.hora.value}", "%Y-%m-%d %H:%M")
        except:
            await interaction.response.send_message("❌ Formato inválido.", ephemeral=True)
            return
        if dt < datetime.datetime.now():
            await interaction.response.send_message("❌ Data futura.", ephemeral=True)
            return
        config["reminders"].append({"user_id": interaction.user.id, "message": self.msg.value, "datetime_iso": dt.isoformat()})
        save_config(config)
        await interaction.response.send_message(f"✅ Lembrete para {dt.strftime('%d/%m/%Y %H:%M')}", ephemeral=True)

# ===================== COMANDOS =====================

@bot.tree.command(name="painel", description="🌸 Envia/atualiza o painel principal")
@app_commands.default_permissions(administrator=True)
async def cmd_painel(interaction):
    cid = config.get("painel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure o canal primeiro no menu '📌 Painel Fixo'.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cid)
    if not channel:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
        return

    msg_id = config.get("painel_message_id")
    if msg_id:
        try:
            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=embed_painel(), view=MainPanel())
            await interaction.response.send_message(f"✅ Painel principal atualizado em {channel.mention}", ephemeral=True)
            return
        except:
            pass

    msg = await channel.send(embed=embed_painel(), view=MainPanel())
    config["painel_message_id"] = msg.id
    save_config(config)
    await interaction.response.send_message(f"✅ Painel principal enviado em {channel.mention}", ephemeral=True)

@bot.tree.command(name="painelticket", description="🌸 Envia/atualiza o painel de tickets")
@app_commands.default_permissions(administrator=True)
async def cmd_painelticket(interaction):
    cid = config.get("ticket_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure o canal em 'Tickets > Canal do Painel de Tickets'.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cid)
    if not channel:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
        return

    await channel.send(embed=embed_ticket_painel(), view=TicketPanelView())
    await interaction.response.send_message(f"✅ Painel de tickets enviado em {channel.mention}", ephemeral=True)

@bot.tree.command(name="painelsugestoes", description="💡 Envia/atualiza o painel de sugestões")
@app_commands.default_permissions(administrator=True)
async def cmd_painelsugestoes(interaction):
    cid = config.get("suggestions_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure o canal em 'Sugestões > Canal do Painel'.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cid)
    if not channel:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
        return

    msg = await channel.send(embed=embed_sugestoes_painel(), view=SuggestionButton())
    config["suggestions_panel_message_id"] = msg.id
    save_config(config)
    await interaction.response.send_message(f"✅ Painel de sugestões enviado em {channel.mention}", ephemeral=True)

@bot.tree.command(name="painelverificacao", description="✅ Envia/atualiza o painel informativo com botão de verificação")
@app_commands.default_permissions(administrator=True)
async def cmd_painelverificacao(interaction):
    cid = config.get("verification_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure o canal em 'Verificação Captcha > Canal do Painel de Verificação'.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cid)
    if not channel:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
        return

    msg = await channel.send(embed=embed_verificacao_painel(), view=VerificationButton())
    config["verification_panel_message_id"] = msg.id
    save_config(config)
    await interaction.response.send_message(f"✅ Painel de verificação enviado em {channel.mention}", ephemeral=True)

@bot.tree.command(name="painelidade", description="🔞 Envia/atualiza o painel de verificação de idade")
@app_commands.default_permissions(administrator=True)
async def cmd_painelidade(interaction: discord.Interaction):
    cid = config.get("age_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure o canal em 'Verificação +18 > Canal do Painel de Idade'.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cid)
    if not channel:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔞 Verificação de Idade",
        description=(
            "**Este servidor é +18!** 🌸\n\n"
            "Para acessar todas as áreas, você precisa verificar sua idade.\n"
            "Clique no botão abaixo e informe sua data de nascimento.\n\n"
            "**Atenção:**\n"
            "• Usuários com menos de 18 anos receberão um cargo restrito (não serão expulsos).\n"
            "• A informação é confidencial e usada apenas para esta verificação.\n"
            "• Se você já tiver o cargo +18, ignore esta mensagem."
        ),
        color=ROSE
    )
    embed.set_thumbnail(url=FOTO_PERFIL_URL)
    embed.set_image(url=BANNER_PAINEL_URL)
    embed.set_footer(text="🌸 Com amor, Nita", icon_url=FOTO_PERFIL_URL)

    msg = await channel.send(embed=embed, view=AgeVerificationPanelView())
    config["age_panel_message_id"] = msg.id
    save_config(config)
    await interaction.response.send_message(f"✅ Painel de idade enviado em {channel.mention}", ephemeral=True)

@bot.tree.command(name="reverificar", description="🔄 Força um usuário a fazer a verificação +18 novamente")
@app_commands.default_permissions(administrator=True)
async def cmd_reverificar(interaction: discord.Interaction, membro: discord.Member):
    role_id = config.get("age_verified_role_id")
    if role_id:
        role = interaction.guild.get_role(role_id)
        if role and role in membro.roles:
            await membro.remove_roles(role)
    underage_role_id = config.get("age_underage_role_id")
    if underage_role_id:
        role = interaction.guild.get_role(underage_role_id)
        if role and role in membro.roles:
            await membro.remove_roles(role)
    unverified_role_id = config.get("age_unverified_role_id")
    if unverified_role_id:
        role = interaction.guild.get_role(unverified_role_id)
        if role:
            await membro.add_roles(role)
    verification_channel_id = config.get("age_verification_channel_id")
    if verification_channel_id:
        channel = interaction.guild.get_channel(verification_channel_id)
        if channel:
            try:
                await membro.move_to(channel)
            except:
                pass
    if verification_channel_id:
        channel = interaction.guild.get_channel(verification_channel_id)
        if channel:
            await iniciar_verificacao_idade(membro, channel)
    await interaction.response.send_message(f"✅ {membro.mention} foi colocado para verificação novamente.", ephemeral=True)

@bot.tree.command(name="mutar", description="🔇 Muta o bot na call atual")
async def cmd_mutar(interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Comando apenas no servidor.", ephemeral=True)
        return
    voice = guild.voice_client
    if not voice or not voice.is_connected():
        await interaction.response.send_message("❌ Bot não está em uma call.", ephemeral=True)
        return
    try:
        await guild.me.edit(mute=True)
        config["voice_mute"] = True
        save_config(config)
        await interaction.response.send_message("🔇 Bot mutado na call.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

@bot.tree.command(name="desmutar", description="🔊 Desmuta o bot na call atual")
async def cmd_desmutar(interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Comando apenas no servidor.", ephemeral=True)
        return
    voice = guild.voice_client
    if not voice or not voice.is_connected():
        await interaction.response.send_message("❌ Bot não está em uma call.", ephemeral=True)
        return
    try:
        await guild.me.edit(mute=False)
        config["voice_mute"] = False
        save_config(config)
        await interaction.response.send_message("🔊 Bot desmutado na call.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

@bot.tree.command(name="status", description="🎭 Altera o status do bot")
async def cmd_status(interaction, modo: str):
    modos_validos = ["online", "idle", "dnd", "invisible"]
    if modo.lower() not in modos_validos:
        await interaction.response.send_message(f"❌ Modo inválido. Use: {', '.join(modos_validos)}", ephemeral=True)
        return
    config["bot_status"] = modo.lower()
    save_config(config)
    await update_status()
    await interaction.response.send_message(f"✅ Status alterado para **{modo}**", ephemeral=True)

@bot.tree.command(name="lembrete", description="🌸 Agende um lembrete")
async def cmd_lembrete(interaction, mensagem: str, data: str, hora: str):
    try:
        dt = datetime.datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
    except:
        await interaction.response.send_message("❌ Formato inválido.", ephemeral=True)
        return
    if dt < datetime.datetime.now():
        await interaction.response.send_message("❌ Data futura.", ephemeral=True)
        return
    config["reminders"].append({"user_id": interaction.user.id, "message": mensagem, "datetime_iso": dt.isoformat()})
    save_config(config)
    await interaction.response.send_message(f"✅ Lembrete para {dt.strftime('%d/%m/%Y %H:%M')}", ephemeral=True)

# ===================== EVENTOS =====================

@bot.event
async def on_ready():
    logger.info(f"🌸 Bot conectado como {bot.user}")
    init_db()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FOTO_PERFIL_URL) as resp:
                if resp.status == 200:
                    avatar_data = await resp.read()
                    await bot.user.edit(avatar=avatar_data)
                    logger.info("✅ Avatar atualizado!")
    except Exception as e:
        logger.warning(f"⚠️ Não foi possível atualizar o avatar: {e}")

    try:
        await bot.tree.sync()
    except Exception as e:
        logger.error(f"Erro ao sincronizar comandos: {e}")
    if not config.get("guild_id") and bot.guilds:
        config["guild_id"] = bot.guilds[0].id
        save_config(config)

    guild = get_guild()
    if guild:
        me = guild.me
        if not me.guild_permissions.kick_members:
            logger.warning("⚠️ O bot NÃO tem permissão para expulsar membros! A verificação +18 atribuirá cargo de menor em vez de expulsar.")

    await bot_join_voice()
    await update_status()
    update_voice_name.start()
    check_reminders.start()
    check_events.start()
    update_status_task.start()

@bot.event
async def on_member_join(member):
    if member.bot:
        return

    guild = member.guild

    if config.get("age_verification_enabled", False):
        verified_role_id = config.get("age_verified_role_id")
        if verified_role_id:
            role = guild.get_role(verified_role_id)
            if role and role in member.roles:
                await update_voice_name()
                await update_status()
                return

        native_role_id = config.get("age_native_verification_role_id")
        if native_role_id:
            native_role = guild.get_role(native_role_id)
            if native_role and native_role in member.roles:
                if verified_role_id:
                    role = guild.get_role(verified_role_id)
                    if role:
                        await member.add_roles(role)
                        await log_age_verification(member, True, "Verificação nativa", "Discord")
                        welcome_channel_id = config.get("welcome_channel_id")
                        if welcome_channel_id:
                            channel = guild.get_channel(welcome_channel_id)
                            if channel:
                                embed = discord.Embed(
                                    title=f"🌸 Bem-vindo(a) ao servidor, {member.mention}!",
                                    description=config.get("welcome_message", "Bem-vindo(a)! 💖"),
                                    color=PINK
                                )
                                img = config.get("welcome_image_url", BANNER_PAINEL_URL)
                                if img:
                                    embed.set_image(url=img)
                                await channel.send(embed=embed)
                        await update_voice_name()
                        await update_status()
                        return

        unverified_role_id = config.get("age_unverified_role_id")
        if unverified_role_id:
            role = guild.get_role(unverified_role_id)
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass

        verification_channel_id = config.get("age_verification_channel_id")
        if verification_channel_id:
            channel = guild.get_channel(verification_channel_id)
            if channel:
                try:
                    await member.move_to(channel)
                except:
                    pass

                num1 = random.randint(1, 10)
                num2 = random.randint(1, 10)
                answer = num1 + num2
                embed = discord.Embed(
                    title=f"🔐 Verificação para {member.display_name}",
                    description=(
                        f"Olá {member.mention}! Para iniciar sua entrada, resolva a operação abaixo:\n\n"
                        f"**{num1} + {num2} = ?**\n\n"
                        "Após acertar, você será solicitado a verificar sua idade."
                    ),
                    color=ROSE
                )
                view = CaptchaView(member, answer, guild.id, channel.id)
                await channel.send(embed=embed, view=view)

    elif config.get("verification_channel_id"):
        cid_captcha = config.get("verification_channel_id")
        channel = guild.get_channel(cid_captcha)
        if channel:
            num1 = random.randint(1, 10)
            num2 = random.randint(1, 10)
            answer = num1 + num2
            embed = discord.Embed(
                title=f"🔐 Verificação para {member.display_name}",
                description=(
                    f"Olá {member.mention}! Resolva a operação abaixo para ganhar acesso.\n\n"
                    f"**{num1} + {num2} = ?**"
                ),
                color=ROSE
            )
            view = CaptchaView(member, answer, guild.id, channel.id)
            await channel.send(embed=embed, view=view)

    await update_voice_name()
    await update_status()

@bot.event
async def on_member_remove(member):
    await update_voice_name()
    await update_status()

@bot.event
async def on_guild_join(guild):
    config["guild_id"] = guild.id
    save_config(guild)
    me = guild.me
    if not me.guild_permissions.kick_members:
        logger.warning(f"⚠️ O bot NÃO tem permissão para expulsar membros no servidor {guild.name}! A verificação +18 atribuirá cargo de menor.")

# ===================== TASKS =====================

@tasks.loop(minutes=1)
async def update_voice_name():
    await update_voice_name_impl()

@tasks.loop(seconds=30)
async def check_reminders():
    now = datetime.datetime.now()
    reminders = config.get("reminders", [])
    to_remove = []
    for i, rem in enumerate(reminders):
        dt = datetime.datetime.fromisoformat(rem["datetime_iso"])
        if dt <= now:
            user = bot.get_user(rem["user_id"])
            if user:
                try:
                    await user.send(f"⏰ **Lembrete**: {rem['message']}")
                except:
                    pass
            to_remove.append(i)
    if to_remove:
        for i in reversed(to_remove):
            del reminders[i]
        save_config(config)

@tasks.loop(seconds=60)
async def check_events():
    now = datetime.datetime.now()
    events = get_active_events()
    for ev in events:
        dt = datetime.datetime.fromisoformat(ev["schedule_time"])
        if dt <= now:
            channel = bot.get_channel(ev["channel_id"])
            if channel:
                try:
                    await channel.send(ev["message"])
                except Exception as e:
                    logger.error(f"Erro ao enviar evento: {e}")
            if ev["event_type"] == "once":
                deactivate_event(ev["id"])
            else:
                interval = ev["repeat_interval"]
                next_time = dt + datetime.timedelta(minutes=interval)
                conn = get_db()
                c = conn.cursor()
                c.execute("UPDATE scheduled_events SET schedule_time = ? WHERE id = ?", (next_time.isoformat(), ev["id"]))
                conn.commit()
                conn.close()

@tasks.loop(minutes=5)
async def update_status_task():
    await update_status()

# ===================== FUNÇÕES AUX =====================

async def update_voice_name_impl():
    guild = get_guild()
    if not guild:
        return
    channel = get_voice_channel()
    if not channel or not isinstance(channel, discord.VoiceChannel):
        return
    new_name = f"👥 {guild.member_count} membros"
    if channel.name != new_name:
        try:
            await channel.edit(name=new_name)
        except:
            pass

async def bot_join_voice():
    guild = get_guild()
    if not guild:
        return
    cid = config.get("voice_channel_id")
    if not cid:
        return
    channel = guild.get_channel(cid)
    if not channel or not isinstance(channel, discord.VoiceChannel):
        return
    try:
        if not guild.voice_client:
            await channel.connect()
        else:
            await guild.voice_client.move_to(channel)
        await update_voice_name_impl()
        await update_voice_mute()
        await update_status()
    except Exception as e:
        logger.error(f"Erro ao conectar na voz: {e}")

# ===================== EXECUÇÃO =====================

if __name__ == "__main__":
    bot.run(TOKEN)
