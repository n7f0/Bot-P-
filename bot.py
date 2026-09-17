import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import json
import os
import datetime
import random
import logging
import aiohttp
from database import *

# ===================== TOKEN =====================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN não definido.")

CONFIG_FILE = "/app/data/config.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===================== CONFIG PADRÃO =====================
DEFAULT_CONFIG = {
    # 🎨 Identidade Visual (configurável pelo painel)
    "brand_name": "𝚙𝚡𝚔",
    "brand_emoji": "🖤",
    "brand_footer": "🖤 𝚙𝚡𝚔 • Sistema Oficial",
    "brand_color_primary": 0x8A2BE2,
    "brand_color_secondary": 0xB026FF,
    "brand_color_success": 0x00FF88,
    "brand_color_danger": 0xFF3366,
    "avatar_url": "",
    "_last_avatar_url": "",
    "banner_painel_url": "",
    "banner_ticket_url": "",
    "banner_welcome_url": "",

    # Servidor
    "guild_id": None,

    # Verificação Captcha
    "verified_role_id": None,
    "verification_channel_id": None,
    "verification_panel_channel_id": None,
    "verification_panel_message_id": None,

    # Verificação +18
    "age_verification_enabled": False,
    "age_verified_role_id": None,
    "age_underage_role_id": None,
    "age_unverified_role_id": None,
    "age_native_verification_role_id": None,
    "age_kick_underage": True,
    "age_verification_channel_id": None,
    "age_panel_channel_id": None,
    "age_panel_message_id": None,

    # Boas-vindas
    "welcome_channel_id": None,
    "welcome_message": "Bem-vindo(a) ao servidor!",
    "welcome_image_url": "",

    # Voz
    "voice_channel_id": None,
    "voice_mute": True,
    "bot_status": "online",

    # Admin
    "admin_role_ids": [],

    # Painel principal
    "painel_channel_id": None,
    "painel_message_id": None,

    # Tickets
    "ticket_category_doubt_id": None,
    "ticket_category_purchase_id": None,
    "ticket_logs_channel_id": None,
    "ticket_panel_channel_id": None,
    "ticket_panel_message_id": None,
    "ticket_support_role_ids": [],

    # Feedback / Sugestões
    "feedback_channel_id": None,
    "suggestions_channel_id": None,
    "suggestions_panel_channel_id": None,
    "suggestions_panel_message_id": None,

    # Moderação
    "moderation_logs_channel_id": None,

    # Lembretes
    "reminders": []
}

def load_config():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}
    # Merge com defaults (adiciona chaves novas)
    for k, v in DEFAULT_CONFIG.items():
        if k not in data:
            data[k] = v
    save_config(data)
    return data

def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

config = load_config()

# ===================== HELPERS DE IDENTIDADE =====================
def bname():  return config.get("brand_name") or "Bot"
def bemoji(): return config.get("brand_emoji") or "🖤"
def bfooter(): return config.get("brand_footer") or "Sistema Oficial"
def color_primary():   return config.get("brand_color_primary", 0x8A2BE2)
def color_secondary(): return config.get("brand_color_secondary", 0xB026FF)
def color_success():   return config.get("brand_color_success", 0x00FF88)
def color_danger():    return config.get("brand_color_danger", 0xFF3366)

def avatar_url():       return config.get("avatar_url") or None
def banner_painel():    return config.get("banner_painel_url") or None
def banner_ticket():    return config.get("banner_ticket_url") or None
def banner_welcome():   return config.get("welcome_image_url") or config.get("banner_welcome_url") or None

# ===================== BOT =====================
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===================== UTILITÁRIOS =====================
def get_guild():
    gid = config.get("guild_id")
    return bot.get_guild(gid) if gid else None

def get_voice_channel():
    guild = get_guild()
    if guild:
        cid = config.get("voice_channel_id")
        return guild.get_channel(cid) if cid else None
    return None

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
        except Exception:
            pass

async def update_status():
    guild = get_guild()
    if not guild:
        return
    status_map = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "invisible": discord.Status.invisible
    }
    status = status_map.get(config.get("bot_status", "online"), discord.Status.online)
    try:
        await bot.change_presence(
            status=status,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{bemoji()} {guild.member_count} membros em {bname()}"
            )
        )
    except Exception:
        pass

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
    except Exception as e:
        logger.error(f"Erro ao mutar/desmutar: {e}")

async def log_moderation_action(action, moderator, target, reason=None):
    try:
        log_moderation(action, moderator.id, target.id, reason or "Sem motivo")
    except Exception:
        pass
    channel_id = config.get("moderation_logs_channel_id")
    if channel_id:
        channel = moderator.guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title=f"🛡️ Ação de Moderação — {bname()}",
                description=f"**Ação:** {action}\n**Moderador:** {moderator.mention}\n**Alvo:** {target.mention}\n**Motivo:** {reason or 'Não informado'}",
                color=color_danger(),
                timestamp=datetime.datetime.now()
            )
            embed.set_footer(text=f"ID do alvo: {target.id} • {bname()}")
            try:
                await channel.send(embed=embed)
            except Exception:
                pass

async def log_age_verification(user, approved, age=None, birth_date=None, underage_role_given=False, error_msg=None):
    channel_id = config.get("moderation_logs_channel_id")
    if not channel_id:
        return
    channel = user.guild.get_channel(channel_id)
    if not channel:
        return
    embed = discord.Embed(
        title=f"🔞 Verificação de Idade — {bname()}",
        description=f"**Usuário:** {user.mention}\n**ID:** {user.id}\n**Resultado:** {'✅ Aprovado' if approved else '❌ Reprovado'}",
        color=color_success() if approved else color_danger(),
        timestamp=datetime.datetime.now()
    )
    if birth_date:
        embed.add_field(name="Data informada", value=birth_date, inline=False)
    if age is not None:
        embed.add_field(name="Idade calculada", value=f"{age} anos", inline=False)
    if error_msg:
        embed.add_field(name="Erro", value=error_msg, inline=False)
    if not approved and underage_role_given:
        embed.add_field(name="Ação", value="Cargo de menor atribuído (não expulso).", inline=False)
    elif not approved and not underage_role_given and not error_msg:
        embed.add_field(name="Ação", value="Usuário expulso por idade insuficiente.", inline=False)
    try:
        await channel.send(embed=embed)
    except Exception:
        pass

def calcular_idade(data_nasc):
    try:
        nasc = datetime.datetime.strptime(data_nasc, "%d/%m/%Y")
        hoje = datetime.datetime.now()
        return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
    except ValueError:
        return None

def role_select_options(include_none=True):
    opts = []
    if include_none:
        opts.append(discord.SelectOption(label="Nenhum", value="none"))
    guild = get_guild()
    if guild:
        for r in guild.roles:
            if r.name != "@everyone" and not r.managed:
                opts.append(discord.SelectOption(label=r.name[:100], value=str(r.id)))
    return opts[:25] or [discord.SelectOption(label="Nenhum cargo", value="none")]

def text_channel_options(placeholder="Escolha um canal"):
    guild = get_guild()
    opts = []
    if guild:
        for c in guild.text_channels:
            try:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}"[:100], value=str(c.id)))
            except Exception:
                continue
    return opts[:25] or [discord.SelectOption(label="Nenhum canal", value="none")]

# ===================== EMBEDS =====================
def embed_painel():
    e = discord.Embed(
        title=f"{bemoji()} Painel Administrativo — {bname()}",
        description=(
            f"**Bem-vindo(a) ao centro de configurações do servidor {bname()}!**\n\n"
            "🎨 **Identidade Visual** – nome, emoji, cores, avatar e banners\n"
            "✅ **Verificação Captcha** – cargo e canais\n"
            "🔞 **Verificação +18** – cargos, expulsão e painel\n"
            "💌 **Boas‑vindas** – mensagem, imagem e canal\n"
            "🔊 **Voz** – canal 24h, mute e status\n"
            "👑 **Cargos de Admin** – quem pode usar o painel\n"
            "📌 **Painel Fixo** – canal do painel principal\n"
            "🎫 **Tickets** – categorias, suporte e painel\n"
            "⭐ **Avaliações** – feedback dos tickets\n"
            "💡 **Sugestões** – comunidade vota\n"
            "📅 **Eventos** – agendamento de mensagens\n"
            "⏰ **Lembretes** – agende datas e horas\n\n"
            "Selecione uma opção no menu abaixo. 🖤💜"
        ),
        color=color_primary()
    )
    if avatar_url(): e.set_thumbnail(url=avatar_url())
    if banner_painel(): e.set_image(url=banner_painel())
    e.set_footer(text=bfooter(), icon_url=avatar_url() or None)
    return e

def embed_ticket_painel():
    e = discord.Embed(
        title=f"🎫 Central de Tickets — {bname()}",
        description=(
            f"**Olá, seja bem-vindo(a) ao {bname()}!** {bemoji()}\n\n"
            "Aqui você pode abrir um ticket para receber atendimento personalizado.\n"
            "Clique no botão correspondente:\n\n"
            "❓ **Dúvidas** – perguntas gerais\n"
            "🛒 **Compras** – vendas ou compras\n\n"
            f"Nossa equipe do {bname()} estará à disposição. 💜"
        ),
        color=color_primary()
    )
    if avatar_url(): e.set_thumbnail(url=avatar_url())
    if banner_ticket(): e.set_image(url=banner_ticket())
    e.set_footer(text=bfooter(), icon_url=avatar_url() or None)
    return e

def embed_sugestoes_painel():
    e = discord.Embed(
        title=f"💡 Painel de Sugestões — {bname()}",
        description=(
            f"**Queremos ouvir você!** {bemoji()}\n\n"
            "Clique no botão abaixo e compartilhe sua ideia.\n\n"
            "Todas as sugestões serão votadas pela comunidade. 💜"
        ),
        color=color_primary()
    )
    if avatar_url(): e.set_thumbnail(url=avatar_url())
    if banner_painel(): e.set_image(url=banner_painel())
    e.set_footer(text=bfooter(), icon_url=avatar_url() or None)
    return e

def embed_verificacao_painel():
    e = discord.Embed(
        title=f"✅ Verificação de Segurança — {bname()}",
        description=(
            f"**Proteja sua conta e ganhe acesso total ao {bname()}!** {bemoji()}\n\n"
            "Clique no botão **'🔐 Verificar Agora'** abaixo para iniciar sua verificação.\n"
            "Responda corretamente ao desafio matemático para ganhar o cargo de **Verificado**.\n\n"
            "**Como funciona:**\n"
            "• Clique em 'Verificar Agora'.\n"
            "• Um desafio aparecerá neste canal.\n"
            "• Clique em 'Verificar' e digite o resultado.\n"
            "• Se acertar, ganhará automaticamente o cargo.\n\n"
            "Caso já tenha o cargo, ignore esta mensagem.\n"
            "Qualquer dúvida, abra um ticket. 💜"
        ),
        color=color_secondary()
    )
    if avatar_url(): e.set_thumbnail(url=avatar_url())
    if banner_painel(): e.set_image(url=banner_painel())
    e.set_footer(text=bfooter(), icon_url=avatar_url() or None)
    return e

# ===================== VIEWS PRINCIPAIS =====================
class MainPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MainSelect())

class MainSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Identidade Visual", value="identity", emoji="🎨"),
            discord.SelectOption(label="Verificação Captcha", value="captcha", emoji="✅"),
            discord.SelectOption(label="Verificação +18", value="age18", emoji="🔞"),
            discord.SelectOption(label="Boas‑vindas", value="welcome", emoji="💌"),
            discord.SelectOption(label="Configurar Voz", value="voice_config", emoji="🔊"),
            discord.SelectOption(label="Cargos de Admin", value="admin", emoji="👑"),
            discord.SelectOption(label="Painel Fixo", value="painel", emoji="📌"),
            discord.SelectOption(label="Tickets", value="tickets", emoji="🎫"),
            discord.SelectOption(label="Avaliações (Feedback)", value="feedback", emoji="⭐"),
            discord.SelectOption(label="Sugestões", value="suggestions", emoji="💡"),
            discord.SelectOption(label="Eventos", value="events", emoji="📅"),
            discord.SelectOption(label="Lembretes", value="reminder", emoji="⏰"),
        ]
        super().__init__(placeholder=f"🖤 Configurações do {bname()}", options=options)

    async def callback(self, interaction: discord.Interaction):
        v = self.values[0]
        if v == "identity":
            await interaction.response.send_message("🎨 Configure a identidade visual:", view=IdentityConfigView(), ephemeral=True)
        elif v == "captcha":
            await interaction.response.send_message("Configure a verificação Captcha:", view=VerificationConfigView(), ephemeral=True)
        elif v == "age18":
            await interaction.response.send_message("Configure a verificação +18:", view=AgeVerificationConfigView(), ephemeral=True)
        elif v == "welcome":
            await interaction.response.send_message("Personalize as boas‑vindas:", view=WelcomeView(), ephemeral=True)
        elif v == "voice_config":
            await interaction.response.send_message("Configure as opções de voz:", view=VoiceConfigView(), ephemeral=True)
        elif v == "admin":
            await interaction.response.send_message("Selecione os cargos de administrador:", view=AdminRolesView(), ephemeral=True)
        elif v == "painel":
            await interaction.response.send_message("Escolha o canal para o painel principal:", view=PainelChannelView(), ephemeral=True)
        elif v == "tickets":
            await interaction.response.send_message("Configure o sistema de tickets:", view=TicketConfigView(), ephemeral=True)
        elif v == "feedback":
            await interaction.response.send_message("Configure o canal para avaliações:", view=FeedbackChannelView(), ephemeral=True)
        elif v == "suggestions":
            await interaction.response.send_message("Configure o painel de sugestões:", view=SuggestionsConfigView(), ephemeral=True)
        elif v == "events":
            await interaction.response.send_modal(EventModal())
        elif v == "reminder":
            await interaction.response.send_modal(ReminderModal())

# ===================== IDENTIDADE VISUAL =====================
class IdentityConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @ui.button(label="Nome da Marca", style=discord.ButtonStyle.primary, row=0)
    async def set_brand_name(self, interaction, button):
        await interaction.response.send_modal(BrandNameModal())

    @ui.button(label="Emoji da Marca", style=discord.ButtonStyle.primary, row=0)
    async def set_brand_emoji(self, interaction, button):
        await interaction.response.send_modal(BrandEmojiModal())

    @ui.button(label="Rodapé Padrão", style=discord.ButtonStyle.primary, row=0)
    async def set_footer(self, interaction, button):
        await interaction.response.send_modal(BrandFooterModal())

    @ui.button(label="Cor Primária", style=discord.ButtonStyle.primary, row=1)
    async def set_color_primary(self, interaction, button):
        await interaction.response.send_modal(ColorModal("brand_color_primary", "Cor Primária"))

    @ui.button(label="Cor Secundária", style=discord.ButtonStyle.primary, row=1)
    async def set_color_secondary(self, interaction, button):
        await interaction.response.send_modal(ColorModal("brand_color_secondary", "Cor Secundária"))

    @ui.button(label="Cor Sucesso", style=discord.ButtonStyle.success, row=1)
    async def set_color_success(self, interaction, button):
        await interaction.response.send_modal(ColorModal("brand_color_success", "Cor de Sucesso"))

    @ui.button(label="Cor Perigo", style=discord.ButtonStyle.danger, row=1)
    async def set_color_danger(self, interaction, button):
        await interaction.response.send_modal(ColorModal("brand_color_danger", "Cor de Perigo"))

    @ui.button(label="Avatar do Bot (URL)", style=discord.ButtonStyle.primary, row=2)
    async def set_avatar(self, interaction, button):
        await interaction.response.send_modal(URLModal("avatar_url", "URL do Avatar"))

    @ui.button(label="Banner do Painel (URL)", style=discord.ButtonStyle.primary, row=2)
    async def set_banner_painel(self, interaction, button):
        await interaction.response.send_modal(URLModal("banner_painel_url", "URL do Banner do Painel"))

    @ui.button(label="Banner dos Tickets (URL)", style=discord.ButtonStyle.primary, row=3)
    async def set_banner_ticket(self, interaction, button):
        await interaction.response.send_modal(URLModal("banner_ticket_url", "URL do Banner de Tickets"))

    @ui.button(label="Banner de Boas-vindas (URL)", style=discord.ButtonStyle.primary, row=3)
    async def set_banner_welcome(self, interaction, button):
        await interaction.response.send_modal(URLModal("banner_welcome_url", "URL do Banner de Boas-vindas"))

    @ui.button(label="Aplicar Avatar Agora", style=discord.ButtonStyle.success, row=4)
    async def apply_avatar(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        ok = await apply_avatar_if_needed(force=True)
        if ok:
            await interaction.followup.send("✅ Avatar aplicado com sucesso!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Não foi possível aplicar o avatar. Verifique a URL.", ephemeral=True)

    @ui.button(label="Pré-visualizar Painel", style=discord.ButtonStyle.secondary, row=4)
    async def preview(self, interaction, button):
        await interaction.response.send_message(embed=embed_painel(), ephemeral=True)

class BrandNameModal(ui.Modal, title="✏️ Nome da Marca"):
    v = ui.TextInput(label="Nome da marca", required=True, max_length=50)
    async def on_submit(self, interaction):
        config["brand_name"] = self.v.value.strip()
        save_config(config)
        await update_status()
        await interaction.response.send_message(f"✅ Nome da marca definido para **{config['brand_name']}**", ephemeral=True)

class BrandEmojiModal(ui.Modal, title="✨ Emoji da Marca"):
    v = ui.TextInput(label="Emoji (1 ou mais)", required=True, max_length=10)
    async def on_submit(self, interaction):
        config["brand_emoji"] = self.v.value.strip()
        save_config(config)
        await update_status()
        await interaction.response.send_message(f"✅ Emoji definido para {config['brand_emoji']}", ephemeral=True)

class BrandFooterModal(ui.Modal, title="📝 Rodapé Padrão"):
    v = ui.TextInput(label="Texto do rodapé", required=True, max_length=120)
    async def on_submit(self, interaction):
        config["brand_footer"] = self.v.value.strip()
        save_config(config)
        await interaction.response.send_message(f"✅ Rodapé atualizado!", ephemeral=True)

class ColorModal(ui.Modal):
    def __init__(self, key, label):
        super().__init__(title=f"🎨 {label}")
        self.key = key
        self.v = ui.TextInput(label="HEX (sem #, ex: 8A2BE2)", required=True, min_length=6, max_length=7)
        self.add_item(self.v)
    async def on_submit(self, interaction):
        raw = self.v.value.strip().replace("#", "")
        try:
            val = int(raw, 16)
        except ValueError:
            await interaction.response.send_message("❌ HEX inválido. Ex: `8A2BE2`", ephemeral=True)
            return
        config[self.key] = val
        save_config(config)
        await interaction.response.send_message(f"✅ Cor salva: `#{raw.upper()}`", ephemeral=True)

class URLModal(ui.Modal):
    def __init__(self, key, label):
        super().__init__(title=f"🖼️ {label}")
        self.key = key
        self.v = ui.TextInput(label="URL da imagem (ou 'limpar')", required=True)
        self.add_item(self.v)
    async def on_submit(self, interaction):
        val = self.v.value.strip()
        if val.lower() in ("limpar", "clear", "none", "remover"):
            config[self.key] = ""
            save_config(config)
            await interaction.response.send_message("✅ URL removida.", ephemeral=True)
            return
        if not (val.startswith("http://") or val.startswith("https://")):
            await interaction.response.send_message("❌ URL inválida.", ephemeral=True)
            return
        config[self.key] = val
        save_config(config)
        await interaction.response.send_message("✅ URL salva!", ephemeral=True)

# ===================== VERIFICAÇÃO CAPTCHA =====================
class VerificationConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="Cargo de Verificação", style=discord.ButtonStyle.primary)
    async def set_role(self, interaction, button):
        await interaction.response.send_message("Escolha o cargo:", view=SimpleRoleSelectView("verified_role_id", "Cargo de Verificação"), ephemeral=True)

    @ui.button(label="Canal de Verificação", style=discord.ButtonStyle.primary)
    async def set_verification_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal dos desafios:", view=SimpleChannelSelectView("verification_channel_id", "Canal de Verificação"), ephemeral=True)

    @ui.button(label="Canal do Painel", style=discord.ButtonStyle.primary)
    async def set_panel_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal do painel:", view=SimpleChannelSelectView("verification_panel_channel_id", "Canal do Painel"), ephemeral=True)

# ===================== VERIFICAÇÃO +18 =====================
class AgeVerificationConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @ui.button(label="Ativar/Desativar", style=discord.ButtonStyle.primary, row=0)
    async def toggle_enabled(self, interaction, button):
        config["age_verification_enabled"] = not config.get("age_verification_enabled", False)
        save_config(config)
        await interaction.response.send_message(f"✅ Sistema +18 {'ativado' if config['age_verification_enabled'] else 'desativado'}.", ephemeral=True)

    @ui.button(label="Cargo +18", style=discord.ButtonStyle.primary, row=0)
    async def set_adult_role(self, interaction, button):
        await interaction.response.send_message("Cargo para MAIORES:", view=SimpleRoleSelectView("age_verified_role_id", "Cargo +18"), ephemeral=True)

    @ui.button(label="Cargo -18", style=discord.ButtonStyle.primary, row=0)
    async def set_underage_role(self, interaction, button):
        await interaction.response.send_message("Cargo para MENORES:", view=SimpleRoleSelectView("age_underage_role_id", "Cargo -18"), ephemeral=True)

    @ui.button(label="Cargo Não Verificado", style=discord.ButtonStyle.primary, row=1)
    async def set_unverified_role(self, interaction, button):
        await interaction.response.send_message("Cargo para usuários não verificados:", view=SimpleRoleSelectView("age_unverified_role_id", "Cargo Não Verificado"), ephemeral=True)

    @ui.button(label="Cargo Verificação Nativa", style=discord.ButtonStyle.primary, row=1)
    async def set_native_role(self, interaction, button):
        await interaction.response.send_message("Cargo concedido pelo Discord (verificação nativa):", view=SimpleRoleSelectView("age_native_verification_role_id", "Cargo Verificação Nativa"), ephemeral=True)

    @ui.button(label="Expulsar Menores", style=discord.ButtonStyle.danger, row=2)
    async def toggle_kick(self, interaction, button):
        config["age_kick_underage"] = not config.get("age_kick_underage", True)
        save_config(config)
        await interaction.response.send_message(f"✅ Expulsão de menores {'ativada' if config['age_kick_underage'] else 'desativada'}.", ephemeral=True)

    @ui.button(label="Canal de Verificação", style=discord.ButtonStyle.primary, row=2)
    async def set_channel(self, interaction, button):
        await interaction.response.send_message("Canal onde os usuários serão verificados:", view=SimpleChannelSelectView("age_verification_channel_id", "Canal de Verificação +18"), ephemeral=True)

    @ui.button(label="Canal do Painel de Idade", style=discord.ButtonStyle.primary, row=2)
    async def set_age_panel_channel(self, interaction, button):
        await interaction.response.send_message("Canal do painel de idade:", view=SimpleChannelSelectView("age_panel_channel_id", "Canal do Painel de Idade"), ephemeral=True)

# ===================== VIEWS REUTILIZÁVEIS =====================
class SimpleRoleSelectView(ui.View):
    def __init__(self, key, label):
        super().__init__(timeout=90)
        self.add_item(SimpleRoleSelect(key, label))

class SimpleRoleSelect(ui.Select):
    def __init__(self, key, label):
        self.key = key
        super().__init__(placeholder=label, options=role_select_options())

    async def callback(self, interaction):
        val = self.values[0]
        config[self.key] = None if val == "none" else int(val)
        save_config(config)
        if val == "none":
            await interaction.response.send_message("✅ Definido como **Nenhum**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"✅ Definido: <@&{val}>", ephemeral=True)

class SimpleChannelSelectView(ui.View):
    def __init__(self, key, label):
        super().__init__(timeout=90)
        self.add_item(SimpleChannelSelect(key, label))

class SimpleChannelSelect(ui.Select):
    def __init__(self, key, label):
        self.key = key
        super().__init__(placeholder=label, options=text_channel_options())

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config[self.key] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal definido: <#{val}>", ephemeral=True)

class MultiRoleSelectView(ui.View):
    def __init__(self, key, label):
        super().__init__(timeout=90)
        self.add_item(MultiRoleSelect(key, label))

class MultiRoleSelect(ui.Select):
    def __init__(self, key, label):
        self.key = key
        opts = role_select_options(include_none=False)
        if not opts:
            opts = [discord.SelectOption(label="Nenhum cargo disponível", value="none")]
        max_v = min(len(opts), 25)
        super().__init__(placeholder=label, options=opts[:25], min_values=0, max_values=max_v)

    async def callback(self, interaction):
        vals = [v for v in self.values if v != "none"]
        config[self.key] = [int(v) for v in vals]
        save_config(config)
        await interaction.response.send_message(f"✅ {len(vals)} cargos definidos.", ephemeral=True)

# ===================== VOZ =====================
class VoiceConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="Mute na Call", style=discord.ButtonStyle.primary)
    async def toggle_mute(self, interaction, button):
        config["voice_mute"] = not config.get("voice_mute", True)
        save_config(config)
        await update_voice_mute()
        await interaction.response.send_message(f"✅ Mute {'ativado' if config['voice_mute'] else 'desativado'}.", ephemeral=True)

    @ui.button(label="Status do Bot", style=discord.ButtonStyle.primary)
    async def set_status(self, interaction, button):
        await interaction.response.send_message("Escolha o status:", view=StatusSelectView(), ephemeral=True)

    @ui.button(label="Canal de Voz 24h", style=discord.ButtonStyle.primary)
    async def set_voice_channel(self, interaction, button):
        await interaction.response.send_message("Escolha o canal de voz:", view=VoiceChannelView(), ephemeral=True)

class StatusSelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(StatusSelect())

class StatusSelect(ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Online", value="online", emoji="🟢"),
            discord.SelectOption(label="Ausente", value="idle", emoji="🟡"),
            discord.SelectOption(label="Não perturbar", value="dnd", emoji="🔴"),
            discord.SelectOption(label="Invisível", value="invisible", emoji="⚫"),
        ]
        super().__init__(placeholder="Escolha o status", options=options)

    async def callback(self, interaction):
        config["bot_status"] = self.values[0]
        save_config(config)
        await update_status()
        await interaction.response.send_message(f"✅ Status alterado para **{self.values[0]}**", ephemeral=True)

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
                opts.append(discord.SelectOption(label=c.name[:100], value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum canal de voz", value="none")]
        super().__init__(placeholder="Escolha o canal de voz 24h", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["voice_channel_id"] = int(val)
        save_config(config)
        channel = interaction.guild.get_channel(int(val))
        if channel and isinstance(channel, discord.VoiceChannel):
            try:
                if not interaction.guild.voice_client:
                    await channel.connect()
                else:
                    await interaction.guild.voice_client.move_to(channel)
                await update_voice_name_impl()
                await update_voice_mute()
                await interaction.response.send_message(f"✅ Conectado ao {channel.name}", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)

# ===================== ADMIN ROLES =====================
class AdminRolesView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AdminRoleSelect())

class AdminRoleSelect(ui.Select):
    def __init__(self):
        opts = role_select_options(include_none=False)
        if not opts:
            opts = [discord.SelectOption(label="Nenhum cargo disponível", value="none")]
        super().__init__(placeholder="Selecione cargos de admin (múltiplos)", options=opts[:25],
                         min_values=0, max_values=min(len(opts), 25))

    async def callback(self, interaction):
        vals = [v for v in self.values if v != "none"]
        config["admin_role_ids"] = [int(v) for v in vals]
        save_config(config)
        await interaction.response.send_message(f"✅ {len(vals)} cargos definidos.", ephemeral=True)

# ===================== PAINEL FIXO =====================
class PainelChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(PainelChannelSelect())

class PainelChannelSelect(ui.Select):
    def __init__(self):
        super().__init__(placeholder="Canal do painel principal", options=text_channel_options())

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["painel_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal do painel: <#{val}>\nUse `/painelpxkadmin` para enviar/atualizar.", ephemeral=True)

# ===================== TICKETS (CONFIG) =====================
class TicketConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @ui.button(label="Categoria Dúvidas", style=discord.ButtonStyle.primary, row=0)
    async def cat_doubt(self, interaction, button):
        await interaction.response.send_message("Escolha a categoria:", view=TicketCategoryView("doubt"), ephemeral=True)

    @ui.button(label="Categoria Compras", style=discord.ButtonStyle.primary, row=0)
    async def cat_purchase(self, interaction, button):
        await interaction.response.send_message("Escolha a categoria:", view=TicketCategoryView("purchase"), ephemeral=True)

    @ui.button(label="Logs de Tickets", style=discord.ButtonStyle.primary, row=0)
    async def logs(self, interaction, button):
        await interaction.response.send_message("Canal de logs:", view=SimpleChannelSelectView("ticket_logs_channel_id", "Canal de Logs"), ephemeral=True)

    @ui.button(label="Canal do Painel", style=discord.ButtonStyle.primary, row=1)
    async def panel_channel(self, interaction, button):
        await interaction.response.send_message("Canal do painel de tickets:", view=SimpleChannelSelectView("ticket_panel_channel_id", "Canal do Painel"), ephemeral=True)

    @ui.button(label="Cargos de Suporte", style=discord.ButtonStyle.primary, row=1)
    async def support_roles(self, interaction, button):
        await interaction.response.send_message("Cargos de suporte:", view=MultiRoleSelectView("ticket_support_role_ids", "Cargos de Suporte"), ephemeral=True)

    @ui.button(label="Logs de Moderação", style=discord.ButtonStyle.primary, row=1)
    async def mod_logs(self, interaction, button):
        await interaction.response.send_message("Canal de logs de moderação:", view=SimpleChannelSelectView("moderation_logs_channel_id", "Logs de Moderação"), ephemeral=True)

class TicketCategoryView(ui.View):
    def __init__(self, tipo):
        super().__init__(timeout=60)
        self.add_item(TicketCategorySelect(tipo))

class TicketCategorySelect(ui.Select):
    def __init__(self, tipo):
        self.tipo = tipo
        guild = get_guild()
        opts = []
        if guild:
            for c in guild.categories:
                opts.append(discord.SelectOption(label=c.name[:100], value=str(c.id)))
        if not opts:
            opts = [discord.SelectOption(label="Nenhuma categoria", value="none")]
        super().__init__(placeholder="Escolha a categoria", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhuma categoria selecionada.", ephemeral=True)
            return
        if self.tipo == "doubt":
            config["ticket_category_doubt_id"] = int(val)
        else:
            config["ticket_category_purchase_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Categoria de {self.tipo} definida.", ephemeral=True)

# ===================== FEEDBACK =====================
class FeedbackChannelView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(FeedbackChannelSelect())

class FeedbackChannelSelect(ui.Select):
    def __init__(self):
        super().__init__(placeholder="Canal de feedback", options=text_channel_options())

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal selecionado.", ephemeral=True)
            return
        config["feedback_channel_id"] = int(val)
        save_config(config)
        await interaction.response.send_message(f"✅ Canal de feedback: <#{val}>", ephemeral=True)

# ===================== SUGESTÕES =====================
class SuggestionsConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="Canal do Painel", style=discord.ButtonStyle.primary)
    async def set_channel(self, interaction, button):
        await interaction.response.send_message("Canal do painel de sugestões:", view=SimpleChannelSelectView("suggestions_panel_channel_id", "Canal do Painel"), ephemeral=True)

    @ui.button(label="Canal de Sugestões", style=discord.ButtonStyle.primary)
    async def set_sug_channel(self, interaction, button):
        await interaction.response.send_message("Canal onde as sugestões são enviadas:", view=SimpleChannelSelectView("suggestions_channel_id", "Canal de Sugestões"), ephemeral=True)

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
            await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"💡 Nova Sugestão — {bname()}",
            description=self.sugestao.value,
            color=color_primary()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"ID: {interaction.user.id} • {bname()}")
        msg = await channel.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        await interaction.response.send_message("✅ Sugestão enviada! Obrigado.", ephemeral=True)

# ===================== BOAS-VINDAS =====================
class WelcomeView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @ui.button(label="Mensagem Padrão", style=discord.ButtonStyle.primary)
    async def edit_default_msg(self, interaction, button):
        await interaction.response.send_modal(WelcomeDefaultMessageModal())

    @ui.button(label="Imagem Padrão", style=discord.ButtonStyle.primary)
    async def edit_default_img(self, interaction, button):
        await interaction.response.send_modal(URLModal("welcome_image_url", "URL da Imagem"))

    @ui.button(label="Canal", style=discord.ButtonStyle.primary)
    async def choose_channel(self, interaction, button):
        await interaction.response.send_message("Canal de boas-vindas:", view=SimpleChannelSelectView("welcome_channel_id", "Canal de Boas-vindas"), ephemeral=True)

    @ui.button(label="Personalizar por Usuário", style=discord.ButtonStyle.primary)
    async def customize_user(self, interaction, button):
        await interaction.response.send_message("Selecione um usuário:", view=WelcomeUserSelectView(), ephemeral=True)

class WelcomeDefaultMessageModal(ui.Modal, title="Mensagem Padrão de Boas-vindas"):
    msg = ui.TextInput(label="Nova mensagem", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, interaction):
        config["welcome_message"] = self.msg.value
        save_config(config)
        await interaction.response.send_message("✅ Mensagem padrão atualizada!", ephemeral=True)

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
                    opts.append(discord.SelectOption(label=m.display_name[:100], value=str(m.id), description=f"@{m.name}"))
        if not opts:
            opts = [discord.SelectOption(label="Nenhum membro", value="none")]
        super().__init__(placeholder="Selecione um usuário", options=opts[:25])

    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum usuário selecionado.", ephemeral=True)
            return
        await interaction.response.send_modal(WelcomeUserMessageModal(int(val)))

class WelcomeUserMessageModal(ui.Modal, title="Mensagem Personalizada"):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.msg = ui.TextInput(label="Mensagem personalizada", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.msg)
        self.img = ui.TextInput(label="URL da imagem (opcional)", required=False)
        self.add_item(self.img)

    async def on_submit(self, interaction):
        image_url = self.img.value.strip() or None
        set_welcome_message(self.user_id, self.msg.value, image_url)
        user = interaction.guild.get_member(self.user_id)
        await interaction.response.send_message(f"✅ Personalizado para {user.mention if user else 'usuário'}!", ephemeral=True)

# ===================== TICKET (VIEW) =====================
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
        try:
            count = count_user_tickets_last_hours(interaction.user.id, hours=8)
        except Exception:
            count = 0
        if count >= 3:
            await interaction.response.send_message("❌ Limite de 3 tickets em 8h atingido.", ephemeral=True)
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
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
        }
        support_mentions = []
        for rid in config.get("ticket_support_role_ids", []):
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
                support_mentions.append(role.mention)

        nome_canal = f"ticket-{tipo}-{interaction.user.name[:20]}".lower().replace(" ", "-")
        try:
            channel = await guild.create_text_channel(
                name=nome_canal, category=category, overwrites=overwrites,
                reason=f"Ticket de {nome} aberto por {interaction.user}"
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao criar ticket: {e}", ephemeral=True)
            return

        try:
            add_open_ticket(interaction.user.id, channel.id)
        except Exception:
            pass

        embed = discord.Embed(
            title=f"{bemoji()} Ticket de {nome} — {bname()}",
            description=(
                f"**Olá {interaction.user.mention}!** Seja muito bem-vindo(a) ao nosso atendimento. 💜\n\n"
                "**📌 Como funciona:**\n"
                "• Descreva sua dúvida ou pedido abaixo.\n"
                "• Você pode enviar arquivos, imagens ou links.\n"
                "• Nossa equipe responderá assim que possível.\n\n"
                "Aguarde um momento, por favor. Estamos aqui para você! 🖤"
            ),
            color=color_primary()
        )
        if banner_ticket(): embed.set_image(url=banner_ticket())
        embed.set_footer(text=f"{bemoji()} Equipe {bname()}", icon_url=avatar_url() or None)
        await channel.send(embed=embed)

        if support_mentions:
            await channel.send(f"📢 **Suporte:** {', '.join(support_mentions)} – novo ticket de {nome} aberto por {interaction.user.mention}.")

        await channel.send("🔧 **Ações disponíveis:**", view=TicketActionsView(tipo, nome_canal, interaction.user.id))

        log_channel_id = config.get("ticket_logs_channel_id")
        if log_channel_id:
            log_ch = guild.get_channel(log_channel_id)
            if log_ch:
                log_embed = discord.Embed(
                    title=f"📩 Novo Ticket — {bname()}",
                    description=f"**Tipo:** {nome}\n**Usuário:** {interaction.user.mention}\n**Canal:** {channel.mention}",
                    color=color_primary(),
                    timestamp=datetime.datetime.now()
                )
                try:
                    await log_ch.send(embed=log_embed)
                except Exception:
                    pass

        resp = discord.Embed(
            title="✅ Ticket criado!",
            description=f"{bemoji()} Seu ticket de **{nome}** foi aberto em {channel.mention}.",
            color=color_success()
        )
        await interaction.response.send_message(embed=resp, ephemeral=True)

class TicketActionsView(ui.View):
    def __init__(self, ticket_type, ticket_name, user_id):
        super().__init__(timeout=None)
        self.ticket_type = ticket_type
        self.ticket_name = ticket_name
        self.user_id = user_id

    def is_staff(self, member):
        return any(role.id in config.get("ticket_support_role_ids", []) for role in member.roles)

    @ui.button(label="⭐ Avaliar", style=discord.ButtonStyle.primary, custom_id="rate_ticket")
    async def rate_ticket(self, interaction, button):
        if interaction.user.id != self.user_id and not self.is_staff(interaction.user):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        await interaction.response.send_modal(TicketRatingModal(self.ticket_name))

    @ui.button(label="🔒 Fechar", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction, button):
        if interaction.user.id != self.user_id and not self.is_staff(interaction.user):
            await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
            return
        confirm_view = ui.View()
        confirm_view.add_item(ConfirmCloseButton(self.ticket_type, self.ticket_name, self.user_id))
        await interaction.response.send_message("⚠️ Fechar este ticket? O canal será deletado.", view=confirm_view, ephemeral=True)

    @ui.button(label="👤 Adicionar", style=discord.ButtonStyle.primary, custom_id="add_member")
    async def add_member(self, interaction, button):
        if not self.is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)
            return
        guild = interaction.guild
        members = [m for m in guild.members if not m.bot][:25]
        if not members:
            await interaction.response.send_message("❌ Nenhum membro.", ephemeral=True)
            return
        opts = [discord.SelectOption(label=m.display_name[:100], value=str(m.id)) for m in members]
        select = MemberAddSelect()
        select.options = opts
        view = ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("Selecione o membro:", view=view, ephemeral=True)

class MemberAddSelect(ui.Select):
    def __init__(self):
        super().__init__(placeholder="Escolha um membro", min_values=1, max_values=1)

    async def callback(self, interaction):
        member = interaction.guild.get_member(int(self.values[0]))
        if not member:
            await interaction.response.send_message("❌ Membro não encontrado.", ephemeral=True)
            return
        try:
            await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
            await interaction.response.send_message(f"✅ {member.mention} adicionado.", ephemeral=True)
            await interaction.channel.send(f"👤 {member.mention} foi adicionado por {interaction.user.mention}.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

class ConfirmCloseButton(ui.Button):
    def __init__(self, ticket_type, ticket_name, user_id):
        super().__init__(label="✅ Sim, fechar", style=discord.ButtonStyle.danger)
        self.ticket_type = ticket_type
        self.ticket_name = ticket_name
        self.user_id = user_id

    async def callback(self, interaction):
        channel = interaction.channel
        log_channel_id = config.get("ticket_logs_channel_id")
        if log_channel_id:
            log_ch = interaction.guild.get_channel(log_channel_id)
            if log_ch:
                try:
                    await log_ch.send(f"🔒 Ticket `{self.ticket_name}` fechado por {interaction.user.mention}.")
                except Exception:
                    pass
        try:
            remove_open_ticket(channel.id)
        except Exception:
            pass
        try:
            await channel.delete()
        except Exception as e:
            try:
                await interaction.response.send_message(f"❌ Erro ao deletar: {e}", ephemeral=True)
            except Exception:
                pass

class TicketRatingModal(ui.Modal, title="⭐ Avalie o Atendimento"):
    def __init__(self, ticket_name):
        super().__init__()
        self.ticket_name = ticket_name
        self.rating = ui.Select(
            placeholder="Escolha uma nota",
            options=[
                discord.SelectOption(label="1 - Péssimo", value="1", emoji="⭐"),
                discord.SelectOption(label="2 - Ruim", value="2", emoji="⭐"),
                discord.SelectOption(label="3 - Regular", value="3", emoji="⭐"),
                discord.SelectOption(label="4 - Bom", value="4", emoji="⭐"),
                discord.SelectOption(label="5 - Excelente", value="5", emoji="⭐"),
            ]
        )
        self.add_item(self.rating)
        self.comment = ui.TextInput(label="Comentário (opcional)", style=discord.TextStyle.paragraph, required=False)
        self.add_item(self.comment)

    async def on_submit(self, interaction):
        rating = int(self.rating.values[0])
        comment = self.comment.value or "Sem comentário"
        try:
            add_ticket_feedback(interaction.channel.id, interaction.user.id, rating, comment)
        except Exception:
            pass
        feedback_channel_id = config.get("feedback_channel_id")
        if feedback_channel_id:
            channel = interaction.guild.get_channel(feedback_channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"⭐ Nova Avaliação — {bname()}",
                    description=f"**Usuário:** {interaction.user.mention}\n**Ticket:** {self.ticket_name}\n**Nota:** {'⭐' * rating} ({rating}/5)\n**Comentário:** {comment}",
                    color=color_primary(),
                    timestamp=datetime.datetime.now()
                )
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass
        await interaction.response.send_message("✅ Obrigado pela avaliação!", ephemeral=True)

# ===================== VERIFICAÇÃO CAPTCHA =====================
class VerificationButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔐 Verificar Agora", style=discord.ButtonStyle.success, custom_id="verify_now")
    async def verify_now(self, interaction, button):
        guild = interaction.guild
        channel = interaction.channel
        member = interaction.user

        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        answer = num1 + num2

        embed = discord.Embed(
            title=f"🔐 Verificação para {member.display_name}",
            description=(
                f"Olá {member.mention}! Resolva a operação abaixo:\n\n"
                f"**{num1} + {num2} = ?**\n\n"
                "Clique no botão abaixo para responder."
            ),
            color=color_secondary()
        )
        view = CaptchaView(member, answer, guild.id, channel.id)
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Desafio enviado!", ephemeral=True)

class CaptchaView(ui.View):
    def __init__(self, member, answer, guild_id, channel_id):
        super().__init__(timeout=300)
        self.member = member
        self.answer = answer
        self.guild_id = guild_id
        self.channel_id = channel_id

    @ui.button(label="✅ Verificar", style=discord.ButtonStyle.success, custom_id="captcha_verify")
    async def verify(self, interaction, button):
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
        self.resposta = ui.TextInput(label="Resultado da operação:", required=True, placeholder="Ex: 8")
        self.add_item(self.resposta)

    async def on_submit(self, interaction):
        if self.resposta.value.strip() != str(self.answer):
            await interaction.response.send_message("❌ Resposta incorreta.", ephemeral=True)
            return

        guild = bot.get_guild(self.guild_id)
        if not guild:
            await interaction.response.send_message("❌ Servidor não encontrado.", ephemeral=True)
            return

        member = guild.get_member(self.user_id)
        role_id = config.get("verified_role_id")
        if role_id and member:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role)
                except Exception:
                    pass

        if config.get("age_verification_enabled", False):
            channel = guild.get_channel(self.channel_id)
            if channel and member:
                try:
                    await interaction.message.delete()
                except Exception:
                    pass
                await iniciar_verificacao_idade(member, channel)
                await interaction.response.send_message("✅ Captcha resolvido! Agora verifique sua idade.", ephemeral=True)
            else:
                await interaction.response.send_message("✅ Captcha resolvido!", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Verificação concluída! Você ganhou o cargo.", ephemeral=True)
            try:
                await interaction.message.delete()
            except Exception:
                pass

# ===================== VERIFICAÇÃO +18 =====================
class AgeVerificationPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔞 Verificar Idade", style=discord.ButtonStyle.danger, custom_id="age_panel_verify")
    async def age_panel_verify(self, interaction, button):
        if not config.get("age_verification_enabled", False):
            await interaction.response.send_message("❌ Sistema desativado.", ephemeral=True)
            return
        role_id = config.get("age_verified_role_id")
        if role_id:
            role = interaction.guild.get_role(role_id)
            if role and role in interaction.user.roles:
                await interaction.response.send_message("✅ Você já está verificado!", ephemeral=True)
                return
        await interaction.response.send_modal(AgeVerificationModal(interaction.user.id))

class AgeVerificationView(ui.View):
    def __init__(self, member):
        super().__init__(timeout=300)
        self.member = member

    @ui.button(label="🔞 Verificar Idade", style=discord.ButtonStyle.danger, custom_id="verify_age")
    async def verify_age(self, interaction, button):
        if interaction.user.id != self.member.id:
            await interaction.response.send_message("❌ Este botão não é para você.", ephemeral=True)
            return
        await interaction.response.send_modal(AgeVerificationModal(self.member.id))

class AgeVerificationModal(ui.Modal, title="🔞 Verificação de Idade"):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.nascimento = ui.TextInput(
            label="Data de nascimento",
            placeholder="DD/MM/AAAA",
            required=True, min_length=10, max_length=10
        )
        self.add_item(self.nascimento)

    async def on_submit(self, interaction):
        guild = interaction.guild
        member = guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)
            return

        idade = calcular_idade(self.nascimento.value)
        if idade is None:
            await interaction.response.send_message("❌ Data inválida. Use DD/MM/AAAA.", ephemeral=True)
            return

        adult_role_id = config.get("age_verified_role_id")
        underage_role_id = config.get("age_underage_role_id")
        unverified_role_id = config.get("age_unverified_role_id")
        kick_underage = config.get("age_kick_underage", True)

        if idade >= 18:
            if adult_role_id:
                r = guild.get_role(adult_role_id)
                if r:
                    try: await member.add_roles(r)
                    except Exception: pass
            for rid in (unverified_role_id, underage_role_id):
                if rid:
                    r = guild.get_role(rid)
                    if r and r in member.roles:
                        try: await member.remove_roles(r)
                        except Exception: pass

            await interaction.response.send_message("✅ **Verificação concluída!** Bem-vindo(a)! 🖤", ephemeral=True)

            welcome_channel_id = config.get("welcome_channel_id")
            if welcome_channel_id:
                channel = guild.get_channel(welcome_channel_id)
                if channel:
                    embed = discord.Embed(
                        title=f"{bemoji()} Bem-vindo(a) ao {bname()}, {member.mention}!",
                        description=config.get("welcome_message", "Bem-vindo(a)! 💜"),
                        color=color_primary()
                    )
                    img = banner_welcome()
                    if img: embed.set_image(url=img)
                    if avatar_url(): embed.set_thumbnail(url=avatar_url())
                    try: await channel.send(embed=embed)
                    except Exception: pass

            await log_age_verification(member, True, idade, self.nascimento.value)
        else:
            if kick_underage:
                try:
                    await guild.kick(member, reason=f"Menor de idade ({idade}) – verificação +18")
                    await interaction.response.send_message("❌ Você foi expulso por ter menos de 18 anos.", ephemeral=True)
                    await log_age_verification(member, False, idade, self.nascimento.value, underage_role_given=False)
                except discord.Forbidden:
                    error_msg = "Bot sem permissão para expulsar. Cargo de menor atribuído."
                    await interaction.response.send_message(
                        "⚠️ Não foi possível expulsar. Você recebeu o cargo restrito.", ephemeral=True
                    )
                    if underage_role_id:
                        r = guild.get_role(underage_role_id)
                        if r:
                            try: await member.add_roles(r)
                            except Exception: pass
                    if unverified_role_id:
                        r = guild.get_role(unverified_role_id)
                        if r and r in member.roles:
                            try: await member.remove_roles(r)
                            except Exception: pass
                    if adult_role_id:
                        r = guild.get_role(adult_role_id)
                        if r and r in member.roles:
                            try: await member.remove_roles(r)
                            except Exception: pass
                    await log_age_verification(member, False, idade, self.nascimento.value, underage_role_given=True, error_msg=error_msg)
            else:
                if underage_role_id:
                    r = guild.get_role(underage_role_id)
                    if r:
                        try: await member.add_roles(r)
                        except Exception: pass
                if unverified_role_id:
                    r = guild.get_role(unverified_role_id)
                    if r and r in member.roles:
                        try: await member.remove_roles(r)
                        except Exception: pass
                if adult_role_id:
                    r = guild.get_role(adult_role_id)
                    if r and r in member.roles:
                        try: await member.remove_roles(r)
                        except Exception: pass
                await interaction.response.send_message(
                    f"🔞 **Você é menor de idade ({idade} anos).** Cargo restrito aplicado.", ephemeral=True
                )
                await log_age_verification(member, False, idade, self.nascimento.value, underage_role_given=True)

async def iniciar_verificacao_idade(member, channel):
    verified_role_id = config.get("age_verified_role_id")
    if verified_role_id:
        role = member.guild.get_role(verified_role_id)
        if role and role in member.roles:
            return

    embed = discord.Embed(
        title=f"🔞 Verificação de Idade — {bname()}",
        description=(
            f"Olá {member.mention}! Para completar sua entrada, confirme que tem **18 anos ou mais**.\n"
            "Clique no botão abaixo e informe sua data de nascimento.\n\n"
            "**Atenção:** Usuários menores de 18 anos serão removidos automaticamente."
        ),
        color=color_secondary()
    )
    if banner_painel(): embed.set_image(url=banner_painel())
    embed.set_footer(text=bfooter(), icon_url=avatar_url() or None)
    try:
        await channel.send(embed=embed, view=AgeVerificationView(member))
    except Exception as e:
        logger.error(f"Erro ao iniciar verificação de idade: {e}")

# ===================== EVENTOS / LEMBRETES =====================
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
        except Exception:
            await interaction.response.send_message("❌ Formato inválido.", ephemeral=True)
            return
        if dt < datetime.datetime.now():
            await interaction.response.send_message("❌ Data no futuro.", ephemeral=True)
            return
        repeat = self.repetir.values[0] if self.repetir.values else "once"
        repeat_interval = None if repeat == "once" else int(repeat)
        add_scheduled_event(
            event_type="repeat" if repeat_interval else "once",
            channel_id=channel_id,
            message=self.mensagem.value,
            schedule_time=dt.isoformat(),
            repeat_interval=repeat_interval
        )
        await interaction.response.send_message(f"✅ Evento agendado para {dt.strftime('%d/%m/%Y %H:%M')}.", ephemeral=True)

class ReminderModal(ui.Modal, title="⏰ Lembrete"):
    msg = ui.TextInput(label="Mensagem", style=discord.TextStyle.paragraph, required=True)
    data = ui.TextInput(label="Data (AAAA-MM-DD)", required=True)
    hora = ui.TextInput(label="Hora (HH:MM)", required=True)

    async def on_submit(self, interaction):
        try:
            dt = datetime.datetime.strptime(f"{self.data.value} {self.hora.value}", "%Y-%m-%d %H:%M")
        except Exception:
            await interaction.response.send_message("❌ Formato inválido.", ephemeral=True)
            return
        if dt < datetime.datetime.now():
            await interaction.response.send_message("❌ Data futura.", ephemeral=True)
            return
        config["reminders"].append({"user_id": interaction.user.id, "message": self.msg.value, "datetime_iso": dt.isoformat()})
        save_config(config)
        await interaction.response.send_message(f"✅ Lembrete para {dt.strftime('%d/%m/%Y %H:%M')}", ephemeral=True)

# ===================== COMANDOS =====================

def is_admin(member):
    if member.guild_permissions.administrator:
        return True
    return any(r.id in config.get("admin_role_ids", []) for r in member.roles)

@bot.tree.command(name="painelpxkadmin", description="🖤 Painel administrativo do servidor 𝚙𝚡𝚔")
@app_commands.default_permissions(administrator=True)
async def cmd_painel_pxk_admin(interaction: discord.Interaction):
    cid = config.get("painel_channel_id")
    if cid:
        channel = interaction.guild.get_channel(cid)
        if channel:
            msg_id = config.get("painel_message_id")
            if msg_id:
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.edit(embed=embed_painel(), view=MainPanel())
                    await interaction.response.send_message(f"✅ Painel do **{bname()}** atualizado em {channel.mention}", ephemeral=True)
                    return
                except Exception:
                    pass

    msg = await interaction.channel.send(embed=embed_painel(), view=MainPanel())
    config["painel_channel_id"] = interaction.channel.id
    config["painel_message_id"] = msg.id
    save_config(config)
    await interaction.response.send_message(f"✅ Painel administrativo do **{bname()}** enviado!", ephemeral=True)

@bot.tree.command(name="painelticket", description="🎫 Envia o painel de tickets")
@app_commands.default_permissions(administrator=True)
async def cmd_painelticket(interaction):
    cid = config.get("ticket_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure o canal em `Tickets > Canal do Painel`.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cid)
    if not channel:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
        return
    await channel.send(embed=embed_ticket_painel(), view=TicketPanelView())
    await interaction.response.send_message(f"✅ Painel de tickets enviado em {channel.mention}", ephemeral=True)

@bot.tree.command(name="painelsugestoes", description="💡 Envia o painel de sugestões")
@app_commands.default_permissions(administrator=True)
async def cmd_painelsugestoes(interaction):
    cid = config.get("suggestions_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure o canal em `Sugestões > Canal do Painel`.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cid)
    if not channel:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
        return
    msg = await channel.send(embed=embed_sugestoes_painel(), view=SuggestionButton())
    config["suggestions_panel_message_id"] = msg.id
    save_config(config)
    await interaction.response.send_message(f"✅ Painel de sugestões enviado em {channel.mention}", ephemeral=True)

@bot.tree.command(name="painelverificacao", description="✅ Envia o painel de verificação")
@app_commands.default_permissions(administrator=True)
async def cmd_painelverificacao(interaction):
    cid = config.get("verification_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure o canal em `Verificação > Canal do Painel`.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cid)
    if not channel:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
        return
    msg = await channel.send(embed=embed_verificacao_painel(), view=VerificationButton())
    config["verification_panel_message_id"] = msg.id
    save_config(config)
    await interaction.response.send_message(f"✅ Painel de verificação enviado em {channel.mention}", ephemeral=True)

@bot.tree.command(name="painelidade", description="🔞 Envia o painel de verificação de idade")
@app_commands.default_permissions(administrator=True)
async def cmd_painelidade(interaction: discord.Interaction):
    cid = config.get("age_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure o canal em `Verificação +18 > Canal do Painel`.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(cid)
    if not channel:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True)
        return
    embed = discord.Embed(
        title=f"🔞 Verificação de Idade — {bname()}",
        description=(
            f"**Este servidor é +18!** {bemoji()}\n\n"
            "Para acessar todas as áreas, verifique sua idade.\n"
            "Clique no botão abaixo e informe sua data de nascimento.\n\n"
            "**Atenção:** Usuários menores de 18 anos receberão cargo restrito.\n"
            "A informação é confidencial e usada apenas para esta verificação."
        ),
        color=color_secondary()
    )
    if avatar_url(): embed.set_thumbnail(url=avatar_url())
    if banner_painel(): embed.set_image(url=banner_painel())
    embed.set_footer(text=bfooter(), icon_url=avatar_url() or None)
    msg = await channel.send(embed=embed, view=AgeVerificationPanelView())
    config["age_panel_message_id"] = msg.id
    save_config(config)
    await interaction.response.send_message(f"✅ Painel de idade enviado em {channel.mention}", ephemeral=True)

@bot.tree.command(name="reverificar", description="🔄 Força um usuário a reverificar a idade")
@app_commands.default_permissions(administrator=True)
async def cmd_reverificar(interaction: discord.Interaction, membro: discord.Member):
    for key in ("age_verified_role_id", "age_underage_role_id"):
        rid = config.get(key)
        if rid:
            r = interaction.guild.get_role(rid)
            if r and r in membro.roles:
                try: await membro.remove_roles(r)
                except Exception: pass
    unverified_role_id = config.get("age_unverified_role_id")
    if unverified_role_id:
        r = interaction.guild.get_role(unverified_role_id)
        if r:
            try: await membro.add_roles(r)
            except Exception: pass
    verification_channel_id = config.get("age_verification_channel_id")
    if verification_channel_id:
        channel = interaction.guild.get_channel(verification_channel_id)
        if channel:
            await iniciar_verificacao_idade(membro, channel)
    await interaction.response.send_message(f"✅ {membro.mention} foi colocado para reverificar.", ephemeral=True)

@bot.tree.command(name="mutar", description="🔇 Muta o bot na call")
async def cmd_mutar(interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Apenas no servidor.", ephemeral=True)
        return
    voice = guild.voice_client
    if not voice or not voice.is_connected():
        await interaction.response.send_message("❌ Bot não está em uma call.", ephemeral=True)
        return
    try:
        await guild.me.edit(mute=True)
        config["voice_mute"] = True
        save_config(config)
        await interaction.response.send_message("🔇 Mutado.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

@bot.tree.command(name="desmutar", description="🔊 Desmuta o bot na call")
async def cmd_desmutar(interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ Apenas no servidor.", ephemeral=True)
        return
    voice = guild.voice_client
    if not voice or not voice.is_connected():
        await interaction.response.send_message("❌ Bot não está em uma call.", ephemeral=True)
        return
    try:
        await guild.me.edit(mute=False)
        config["voice_mute"] = False
        save_config(config)
        await interaction.response.send_message("🔊 Desmutado.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

@bot.tree.command(name="status", description="🎭 Altera o status do bot")
async def cmd_status(interaction, modo: str):
    modos = ["online", "idle", "dnd", "invisible"]
    if modo.lower() not in modos:
        await interaction.response.send_message(f"❌ Use: {', '.join(modos)}", ephemeral=True)
        return
    config["bot_status"] = modo.lower()
    save_config(config)
    await update_status()
    await interaction.response.send_message(f"✅ Status: **{modo}**", ephemeral=True)

@bot.tree.command(name="lembrete", description="⏰ Agende um lembrete")
async def cmd_lembrete(interaction, mensagem: str, data: str, hora: str):
    try:
        dt = datetime.datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
    except Exception:
        await interaction.response.send_message("❌ Formato inválido.", ephemeral=True)
        return
    if dt < datetime.datetime.now():
        await interaction.response.send_message("❌ Data futura.", ephemeral=True)
        return
    config["reminders"].append({"user_id": interaction.user.id, "message": mensagem, "datetime_iso": dt.isoformat()})
    save_config(config)
    await interaction.response.send_message(f"✅ Lembrete para {dt.strftime('%d/%m/%Y %H:%M')}", ephemeral=True)

# ===================== TASKS =====================

@tasks.loop(minutes=1)
async def update_voice_name_task():
    await update_voice_name_impl()

@tasks.loop(seconds=30)
async def check_reminders():
    now = datetime.datetime.now()
    reminders = config.get("reminders", [])
    to_remove = []
    for i, rem in enumerate(reminders):
        try:
            dt = datetime.datetime.fromisoformat(rem["datetime_iso"])
        except Exception:
            to_remove.append(i)
            continue
        if dt <= now:
            user = bot.get_user(rem["user_id"])
            if user:
                try:
                    await user.send(f"⏰ **Lembrete {bname()}**: {rem['message']}")
                except Exception:
                    pass
            to_remove.append(i)
    if to_remove:
        for i in reversed(to_remove):
            del reminders[i]
        save_config(config)

@tasks.loop(seconds=60)
async def check_events():
    now = datetime.datetime.now()
    try:
        events = get_active_events()
    except Exception:
        return
    for ev in events:
        try:
            dt = datetime.datetime.fromisoformat(ev["schedule_time"])
        except Exception:
            continue
        if dt <= now:
            channel = bot.get_channel(ev["channel_id"])
            if channel:
                try:
                    await channel.send(ev["message"])
                except Exception as e:
                    logger.error(f"Erro ao enviar evento: {e}")
            if ev["event_type"] == "once":
                try: deactivate_event(ev["id"])
                except Exception: pass
            else:
                try:
                    interval = ev["repeat_interval"]
                    next_time = dt + datetime.timedelta(minutes=interval)
                    conn = get_db()
                    c = conn.cursor()
                    c.execute("UPDATE scheduled_events SET schedule_time = ? WHERE id = ?", (next_time.isoformat(), ev["id"]))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

@tasks.loop(minutes=5)
async def update_status_task():
    await update_status()

# ===================== AUXILIAR =====================
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
    except Exception as e:
        logger.error(f"Erro ao conectar na voz: {e}")

async def apply_avatar_if_needed(force=False):
    url = avatar_url()
    if not url:
        return False
    if not force and config.get("_last_avatar_url") == url:
        return True
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ Avatar não pôde ser baixado ({resp.status})")
                    return False
                data = await resp.read()
        await bot.user.edit(avatar=data)
        config["_last_avatar_url"] = url
        save_config(config)
        logger.info("✅ Avatar atualizado!")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Erro ao atualizar avatar: {e}")
        return False

# ===================== EVENTOS DO BOT =====================

@bot.event
async def on_ready():
    logger.info(f"{bemoji()} Bot {bname()} conectado como {bot.user}")
    try:
        init_db()
    except Exception as e:
        logger.error(f"Erro ao inicializar DB: {e}")

    if not config.get("guild_id") and bot.guilds:
        config["guild_id"] = bot.guilds[0].id
        save_config(config)

    # Detecta mudança de nome de guild automaticamente
    guild = get_guild()
    if guild and not config.get("brand_name_set"):
        pass  # deixa o usuário definir manualmente

    try:
        await bot.tree.sync()
        logger.info("✅ Comandos sincronizados")
    except Exception as e:
        logger.error(f"Erro ao sincronizar: {e}")

    await apply_avatar_if_needed()
    await bot_join_voice()
    await update_status()

    for task in (update_voice_name_task, check_reminders, check_events, update_status_task):
        if not task.is_running():
            task.start()

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
                await update_voice_name_impl()
                await update_status()
                return

        native_role_id = config.get("age_native_verification_role_id")
        if native_role_id:
            native_role = guild.get_role(native_role_id)
            if native_role and native_role in member.roles:
                if verified_role_id:
                    role = guild.get_role(verified_role_id)
                    if role:
                        try: await member.add_roles(role)
                        except Exception: pass
                        await log_age_verification(member, True, "Verificação nativa", "Discord")
                        welcome_channel_id = config.get("welcome_channel_id")
                        if welcome_channel_id:
                            channel = guild.get_channel(welcome_channel_id)
                            if channel:
                                embed = discord.Embed(
                                    title=f"{bemoji()} Bem-vindo(a) ao {bname()}, {member.mention}!",
                                    description=config.get("welcome_message", "Bem-vindo(a)! 💜"),
                                    color=color_primary()
                                )
                                img = banner_welcome()
                                if img: embed.set_image(url=img)
                                try: await channel.send(embed=embed)
                                except Exception: pass
                        await update_voice_name_impl()
                        await update_status()
                        return

        unverified_role_id = config.get("age_unverified_role_id")
        if unverified_role_id:
            role = guild.get_role(unverified_role_id)
            if role:
                try: await member.add_roles(role)
                except Exception: pass

        verification_channel_id = config.get("age_verification_channel_id")
        if verification_channel_id:
            channel = guild.get_channel(verification_channel_id)
            if channel:
                num1 = random.randint(1, 10)
                num2 = random.randint(1, 10)
                answer = num1 + num2
                embed = discord.Embed(
                    title=f"🔐 Verificação para {member.display_name}",
                    description=(
                        f"Olá {member.mention}! Para iniciar sua entrada no **{bname()}**, resolva:\n\n"
                        f"**{num1} + {num2} = ?**\n\n"
                        "Após acertar, você será solicitado a verificar sua idade."
                    ),
                    color=color_secondary()
                )
                view = CaptchaView(member, answer, guild.id, channel.id)
                try: await channel.send(embed=embed, view=view)
                except Exception: pass

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
                    f"Olá {member.mention}! Resolva a operação abaixo:\n\n"
                    f"**{num1} + {num2} = ?**"
                ),
                color=color_secondary()
            )
            view = CaptchaView(member, answer, guild.id, channel.id)
            try: await channel.send(embed=embed, view=view)
            except Exception: pass

    await update_voice_name_impl()
    await update_status()

@bot.event
async def on_member_remove(member):
    await update_voice_name_impl()
    await update_status()

@bot.event
async def on_guild_join(guild):
    config["guild_id"] = guild.id
    save_config(config)
    try:
        me = guild.me
        if not me.guild_permissions.kick_members:
            logger.warning(f"⚠️ Sem permissão de kick em {guild.name}.")
    except Exception:
        pass

# ===================== EXECUÇÃO =====================
if __name__ == "__main__":
    bot.run(TOKEN)
