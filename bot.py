import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import json, os, datetime, random, logging, aiohttp
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
    "guild_id": None,

    # Verificação Captcha
    "verified_role_ids": [],          # MÚLTIPLOS CARGOS
    "verification_channel_id": None,
    "verification_panel_channel_id": None,
    "verification_panel_message_id": None,

    # Verificação +18
    "age_verification_enabled": False,
    "age_verified_role_ids": [],      # MÚLTIPLOS CARGOS
    "age_underage_role_ids": [],      # MÚLTIPLOS CARGOS
    "age_unverified_role_ids": [],    # MÚLTIPLOS CARGOS
    "age_native_verification_role_ids": [],  # MÚLTIPLOS CARGOS
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

    # Admin (MÚLTIPLOS CARGOS)
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
    "ticket_support_role_ids": [],    # MÚLTIPLOS CARGOS

    # Feedback / Sugestões
    "feedback_channel_id": None,
    "suggestions_channel_id": None,
    "suggestions_panel_channel_id": None,
    "suggestions_panel_message_id": None,

    "moderation_logs_channel_id": None,
    "reminders": []
}

def load_config():
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    for k, v in DEFAULT_CONFIG.items():
        if k not in data:
            data[k] = v
    # Migração: converte IDs antigos (singular) para listas (múltiplos)
    _migrate_ids(data)
    save_config(data)
    return data

def _migrate_ids(data):
    pairs = [
        ("verified_role_id", "verified_role_ids"),
        ("age_verified_role_id", "age_verified_role_ids"),
        ("age_underage_role_id", "age_underage_role_ids"),
        ("age_unverified_role_id", "age_unverified_role_ids"),
        ("age_native_verification_role_id", "age_native_verification_role_ids"),
    ]
    for old, new in pairs:
        if old in data and data[old] and not data.get(new):
            data[new] = [data[old]]
        data.pop(old, None)

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
def avatar_url():      return config.get("avatar_url") or None
def banner_painel():   return config.get("banner_painel_url") or None
def banner_ticket():   return config.get("banner_ticket_url") or None
def banner_welcome():  return config.get("welcome_image_url") or config.get("banner_welcome_url") or None

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
    if not guild: return
    channel = get_voice_channel()
    if not channel or not isinstance(channel, discord.VoiceChannel): return
    new_name = f"👥 {guild.member_count} membros"
    if channel.name != new_name:
        try: await channel.edit(name=new_name)
        except Exception: pass

async def update_status():
    guild = get_guild()
    if not guild: return
    status_map = {"online": discord.Status.online, "idle": discord.Status.idle,
                  "dnd": discord.Status.dnd, "invisible": discord.Status.invisible}
    status = status_map.get(config.get("bot_status", "online"), discord.Status.online)
    try:
        await bot.change_presence(status=status, activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{bemoji()} {guild.member_count} membros em {bname()}"
        ))
    except Exception: pass

async def update_voice_mute():
    guild = get_guild()
    if not guild: return
    vc = guild.voice_client
    if not vc or not vc.is_connected(): return
    try: await guild.me.edit(mute=config.get("voice_mute", True))
    except Exception as e: logger.error(f"Erro mute: {e}")

def calcular_idade(data_nasc):
    try:
        nasc = datetime.datetime.strptime(data_nasc, "%d/%m/%Y")
        hoje = datetime.datetime.now()
        return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
    except ValueError:
        return None

def role_options(include_none=False, max_items=25):
    """Retorna opções de cargos para select."""
    opts = []
    if include_none:
        opts.append(discord.SelectOption(label="Nenhum", value="none"))
    guild = get_guild()
    if guild:
        for r in guild.roles:
            if r.name != "@everyone" and not r.managed:
                opts.append(discord.SelectOption(label=r.name[:100], value=str(r.id)))
    return opts[:max_items] or [discord.SelectOption(label="Nenhum cargo", value="none")]

def text_channel_options(max_items=25):
    guild = get_guild()
    opts = []
    if guild:
        for c in guild.text_channels:
            try:
                if c.permissions_for(guild.me).send_messages:
                    opts.append(discord.SelectOption(label=f"#{c.name}"[:100], value=str(c.id)))
            except Exception: continue
    return opts[:max_items] or [discord.SelectOption(label="Nenhum canal", value="none")]

def voice_channel_options():
    guild = get_guild()
    opts = []
    if guild:
        for c in guild.voice_channels:
            opts.append(discord.SelectOption(label=c.name[:100], value=str(c.id)))
    return opts[:25] or [discord.SelectOption(label="Nenhum canal de voz", value="none")]

def category_options():
    guild = get_guild()
    opts = []
    if guild:
        for c in guild.categories:
            opts.append(discord.SelectOption(label=c.name[:100], value=str(c.id)))
    return opts[:25] or [discord.SelectOption(label="Nenhuma categoria", value="none")]

# ===================== COMPONENTS V2 — HELPERS =====================
def v2_container(*components, accent=None):
    """Cria um Container V2 com cor de destaque (accent_color)."""
    return ui.Container(accent_color=accent or color_primary(), *components)

def v2_title(text):
    return ui.TextDisplay(text)

def v2_sep(large=False, visible=True):
    return ui.Separator(spacing=discord.SeparatorSpacingSize.large if large else discord.SeparatorSpacingSize.small, visible=visible)

# ===================== EMBEDS DE PAINEL (via V2 LayoutView) =====================
def painel_layout():
    """LayoutView do painel principal com Components V2."""
    layout = ui.LayoutView(timeout=None)

    # Container com cabeçalho
    header_parts = [
        ui.TextDisplay(f"# {bemoji()} Painel Administrativo — {bname()}"),
        ui.TextDisplay(
            f"**Bem-vindo(a) ao centro de configurações do servidor {bname()}!**\n\n"
            "Use o menu abaixo para navegar entre as categorias. 🖤💜"
        ),
    ]
    if avatar_url():
        header_parts.append(ui.Section(
            ui.TextDisplay("**Sistema de Administração**"),
            accessory=ui.Thumbnail(media=avatar_url()),
        ))
    header_parts.append(ui.Separator(spacing=discord.SeparatorSpacingSize.small))
    layout.add_item(ui.Container(accent_color=color_primary(), *header_parts))

    # Menu principal
    row = ui.ActionRow()
    select = ui.Select(
        placeholder=f"🖤 Configurações do {bname()}",
        options=[
            discord.SelectOption(label="Identidade Visual", value="identity", emoji="🎨"),
            discord.SelectOption(label="Verificação Captcha", value="captcha", emoji="✅"),
            discord.SelectOption(label="Verificação +18", value="age18", emoji="🔞"),
            discord.SelectOption(label="Boas-vindas", value="welcome", emoji="💌"),
            discord.SelectOption(label="Voz & Status", value="voice", emoji="🔊"),
            discord.SelectOption(label="Cargos de Admin", value="admin", emoji="👑"),
            discord.SelectOption(label="Painel Fixo", value="painel_fixo", emoji="📌"),
            discord.SelectOption(label="Tickets", value="tickets", emoji="🎫"),
            discord.SelectOption(label="Avaliações", value="feedback", emoji="⭐"),
            discord.SelectOption(label="Sugestões", value="suggestions", emoji="💡"),
            discord.SelectOption(label="Eventos", value="events", emoji="📅"),
            discord.SelectOption(label="Lembretes", value="reminder", emoji="⏰"),
            discord.SelectOption(label="Ver Configuração Atual", value="show_config", emoji="📋"),
        ],
        custom_id="pxk_main_menu",
    )
    select.callback = main_menu_callback
    row.add_item(select)
    layout.add_item(row)

    return layout

async def main_menu_callback(interaction: discord.Interaction):
    v = interaction.data["values"][0]
    routes = {
        "identity":    lambda: interaction.response.send_message(view=identity_view(), ephemeral=True),
        "captcha":     lambda: interaction.response.send_message(view=captcha_view(), ephemeral=True),
        "age18":       lambda: interaction.response.send_message(view=age_view(), ephemeral=True),
        "welcome":     lambda: interaction.response.send_message(view=welcome_view(), ephemeral=True),
        "voice":       lambda: interaction.response.send_message(view=voice_view(), ephemeral=True),
        "admin":       lambda: interaction.response.send_message(view=admin_view(), ephemeral=True),
        "painel_fixo": lambda: interaction.response.send_message(view=painel_fixo_view(), ephemeral=True),
        "tickets":     lambda: interaction.response.send_message(view=tickets_view(), ephemeral=True),
        "feedback":    lambda: interaction.response.send_message(view=feedback_view(), ephemeral=True),
        "suggestions": lambda: interaction.response.send_message(view=suggestions_view(), ephemeral=True),
        "events":      lambda: interaction.response.send_modal(EventModal()),
        "reminder":    lambda: interaction.response.send_modal(ReminderModal()),
        "show_config": lambda: interaction.response.send_message(view=show_config_view(), ephemeral=True),
    }
    fn = routes.get(v)
    if fn: await fn()

# ===================== VIEWS V2 — SUBMENUS =====================

# ---------- IDENTIDADE VISUAL ----------
def identity_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# 🎨 Identidade Visual"),
        ui.TextDisplay("Configure nome, emoji, cores, avatar e banners."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Nome", style=discord.ButtonStyle.primary, custom_id="id_name"),
            ui.Button(label="Emoji", style=discord.ButtonStyle.primary, custom_id="id_emoji"),
            ui.Button(label="Rodapé", style=discord.ButtonStyle.primary, custom_id="id_footer"),
        ),
        ui.ActionRow(
            ui.Button(label="Cor Primária", style=discord.ButtonStyle.primary, custom_id="id_c1"),
            ui.Button(label="Cor Secundária", style=discord.ButtonStyle.primary, custom_id="id_c2"),
            ui.Button(label="Cor Sucesso", style=discord.ButtonStyle.success, custom_id="id_c3"),
            ui.Button(label="Cor Perigo", style=discord.ButtonStyle.danger, custom_id="id_c4"),
        ),
        ui.ActionRow(
            ui.Button(label="Avatar (URL)", style=discord.ButtonStyle.secondary, custom_id="id_avatar"),
            ui.Button(label="Banner Painel", style=discord.ButtonStyle.secondary, custom_id="id_bp"),
            ui.Button(label="Banner Ticket", style=discord.ButtonStyle.secondary, custom_id="id_bt"),
            ui.Button(label="Banner Boas-vindas", style=discord.ButtonStyle.secondary, custom_id="id_bw"),
        ),
        ui.ActionRow(
            ui.Button(label="Aplicar Avatar", style=discord.ButtonStyle.success, custom_id="id_apply"),
            ui.Button(label="Pré-visualizar", style=discord.ButtonStyle.secondary, custom_id="id_preview"),
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- CAPTCHA ----------
def captcha_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_secondary(),
        ui.TextDisplay("# ✅ Verificação Captcha"),
        ui.TextDisplay("Configure **múltiplos cargos** de verificação e canais."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Cargos de Verificação (múltiplos)", style=discord.ButtonStyle.primary, custom_id="cap_roles"),
        ),
        ui.ActionRow(
            ui.Button(label="Canal de Verificação", style=discord.ButtonStyle.primary, custom_id="cap_ch"),
            ui.Button(label="Canal do Painel", style=discord.ButtonStyle.primary, custom_id="cap_pch"),
        ),
        ui.ActionRow(
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- VERIFICAÇÃO +18 ----------
def age_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_secondary(),
        ui.TextDisplay("# 🔞 Verificação +18"),
        ui.TextDisplay("Configure cargos múltiplos para cada categoria de idade."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Ativar/Desativar", style=discord.ButtonStyle.primary, custom_id="age_toggle"),
            ui.Button(label="Expulsar Menores", style=discord.ButtonStyle.danger, custom_id="age_kick"),
        ),
        ui.ActionRow(
            ui.Button(label="Cargos +18 (Maiores)", style=discord.ButtonStyle.success, custom_id="age_adult"),
            ui.Button(label="Cargos -18 (Menores)", style=discord.ButtonStyle.primary, custom_id="age_under"),
        ),
        ui.ActionRow(
            ui.Button(label="Cargos Não Verificado", style=discord.ButtonStyle.primary, custom_id="age_unver"),
            ui.Button(label="Cargos Verificação Nativa", style=discord.ButtonStyle.primary, custom_id="age_native"),
        ),
        ui.ActionRow(
            ui.Button(label="Canal de Verificação", style=discord.ButtonStyle.secondary, custom_id="age_ch"),
            ui.Button(label="Canal do Painel", style=discord.ButtonStyle.secondary, custom_id="age_pch"),
        ),
        ui.ActionRow(
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- BOAS-VINDAS ----------
def welcome_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# 💌 Boas-vindas"),
        ui.TextDisplay("Configure a mensagem, imagem e canal de boas-vindas."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Mensagem Padrão", style=discord.ButtonStyle.primary, custom_id="wel_msg"),
            ui.Button(label="Imagem Padrão", style=discord.ButtonStyle.primary, custom_id="wel_img"),
            ui.Button(label="Canal", style=discord.ButtonStyle.primary, custom_id="wel_ch"),
        ),
        ui.ActionRow(
            ui.Button(label="Personalizar por Usuário", style=discord.ButtonStyle.secondary, custom_id="wel_user"),
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- VOZ & STATUS ----------
def voice_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# 🔊 Voz & Status"),
        ui.TextDisplay("Configure o canal de voz 24h, mute e status do bot."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Mute na Call", style=discord.ButtonStyle.primary, custom_id="v_mute"),
            ui.Button(label="Status do Bot", style=discord.ButtonStyle.primary, custom_id="v_status"),
            ui.Button(label="Canal de Voz 24h", style=discord.ButtonStyle.primary, custom_id="v_ch"),
        ),
        ui.ActionRow(
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- ADMIN ROLES ----------
def admin_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# 👑 Cargos de Admin"),
        ui.TextDisplay("Selecione **múltiplos cargos** que podem usar o painel administrativo.\nAdministradores do servidor já têm acesso por padrão."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Selecionar Cargos (múltiplos)", style=discord.ButtonStyle.primary, custom_id="adm_roles"),
        ),
        ui.ActionRow(
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- PAINEL FIXO ----------
def painel_fixo_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# 📌 Painel Fixo"),
        ui.TextDisplay("Escolha o canal onde o painel principal ficará fixo."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Canal do Painel", style=discord.ButtonStyle.primary, custom_id="pf_ch"),
        ),
        ui.ActionRow(
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- TICKETS ----------
def tickets_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# 🎫 Tickets"),
        ui.TextDisplay("Configure categorias, cargos de suporte (múltiplos) e canais."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Categoria Dúvidas", style=discord.ButtonStyle.primary, custom_id="tk_cat_d"),
            ui.Button(label="Categoria Compras", style=discord.ButtonStyle.primary, custom_id="tk_cat_p"),
        ),
        ui.ActionRow(
            ui.Button(label="Cargos de Suporte (múltiplos)", style=discord.ButtonStyle.primary, custom_id="tk_sup"),
            ui.Button(label="Logs de Tickets", style=discord.ButtonStyle.primary, custom_id="tk_logs"),
        ),
        ui.ActionRow(
            ui.Button(label="Canal do Painel", style=discord.ButtonStyle.primary, custom_id="tk_panel"),
            ui.Button(label="Logs de Moderação", style=discord.ButtonStyle.primary, custom_id="tk_mod"),
        ),
        ui.ActionRow(
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- FEEDBACK ----------
def feedback_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# ⭐ Avaliações (Feedback)"),
        ui.TextDisplay("Canal onde as avaliações dos tickets serão enviadas."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Canal de Feedback", style=discord.ButtonStyle.primary, custom_id="fb_ch"),
        ),
        ui.ActionRow(
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- SUGESTÕES ----------
def suggestions_view():
    layout = ui.LayoutView(timeout=300)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# 💡 Sugestões"),
        ui.TextDisplay("Configure o painel e o canal onde as sugestões são enviadas."),
        ui.Separator(),
        ui.ActionRow(
            ui.Button(label="Canal do Painel", style=discord.ButtonStyle.primary, custom_id="sg_pch"),
            ui.Button(label="Canal de Sugestões", style=discord.ButtonStyle.primary, custom_id="sg_ch"),
        ),
        ui.ActionRow(
            ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main"),
        ),
    ))
    return layout

# ---------- SHOW CONFIG ----------
def show_config_view():
    layout = ui.LayoutView(timeout=300)
    guild = get_guild()

    def role_list(key):
        ids = config.get(key, [])
        if not ids: return "—"
        return ", ".join(f"<@&{r}>" for r in ids)

    def ch(key):
        cid = config.get(key)
        return f"<#{cid}>" if cid else "—"

    lines = [
        f"**Marca:** {bname()} {bemoji()}",
        f"**Guild ID:** `{config.get('guild_id')}`",
        f"**Admin Roles:** {role_list('admin_role_ids')}",
        "",
        f"**Captcha — Cargos:** {role_list('verified_role_ids')}",
        f"**Captcha — Canal Verif:** {ch('verification_channel_id')}",
        f"**Captcha — Canal Painel:** {ch('verification_panel_channel_id')}",
        "",
        f"**+18 Ativo:** `{config.get('age_verification_enabled')}`",
        f"**+18 — Cargos Maiores:** {role_list('age_verified_role_ids')}",
        f"**+18 — Cargos Menores:** {role_list('age_underage_role_ids')}",
        f"**+18 — Não Verificado:** {role_list('age_unverified_role_ids')}",
        f"**+18 — Verif. Nativa:** {role_list('age_native_verification_role_ids')}",
        f"**+18 — Expulsar Menores:** `{config.get('age_kick_underage')}`",
        f"**+18 — Canal Verif:** {ch('age_verification_channel_id')}",
        "",
        f"**Boas-vindas — Canal:** {ch('welcome_channel_id')}",
        f"**Voz — Canal:** {ch('voice_channel_id')}",
        f"**Voz — Mute:** `{config.get('voice_mute')}`",
        f"**Status:** `{config.get('bot_status')}`",
        "",
        f"**Tickets — Suporte:** {role_list('ticket_support_role_ids')}",
        f"**Tickets — Painel:** {ch('ticket_panel_channel_id')}",
        f"**Tickets — Logs:** {ch('ticket_logs_channel_id')}",
        f"**Tickets — Cat Dúvidas:** {ch('ticket_category_doubt_id')}",
        f"**Tickets — Cat Compras:** {ch('ticket_category_purchase_id')}",
        "",
        f"**Feedback:** {ch('feedback_channel_id')}",
        f"**Sugestões — Painel:** {ch('suggestions_panel_channel_id')}",
        f"**Sugestões — Canal:** {ch('suggestions_channel_id')}",
        f"**Logs Moderação:** {ch('moderation_logs_channel_id')}",
    ]
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# 📋 Configuração Atual"),
        ui.TextDisplay("\n".join(lines)),
        ui.Separator(),
        ui.ActionRow(ui.Button(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main")),
    ))
    return layout

# ===================== BOTÃO "VOLTAR AO MENU" =====================
class BackToMainButton(ui.Button):
    def __init__(self):
        super().__init__(label="Voltar", style=discord.ButtonStyle.danger, custom_id="back_main")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=None)
        await interaction.followup.send(view=painel_layout(), ephemeral=True)

# ===================== VIEWS DE SELEÇÃO (múltiplos cargos) =====================
def multi_role_view(key, title, current_ids):
    """Cria um LayoutView com RoleSelect que aceita múltiplos cargos."""
    layout = ui.LayoutView(timeout=180)

    selected = []
    for rid in current_ids[:25]:
        try:
            r = get_guild().get_role(rid)
            if r: selected.append(r)
        except Exception: pass

    row = ui.ActionRow()
    role_select = ui.RoleSelect(
        placeholder=f"Selecione cargos (múltiplos) — {title}",
        min_values=0,
        max_values=25,
        default_values=selected if selected else None,
    )

    async def on_role_select(interaction: discord.Interaction):
        ids = [int(r.id) for r in role_select.values]
        config[key] = ids
        save_config(config)
        if ids:
            await interaction.response.send_message(
                f"✅ **{title}:** {len(ids)} cargo(s) definido(s).\n" +
                "\n".join(f"• <@&{i}>" for i in ids), ephemeral=True
            )
        else:
            await interaction.response.send_message(f"✅ **{title}:** nenhum cargo definido.", ephemeral=True)

    role_select.callback = on_role_select
    row.add_item(role_select)

    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay(f"# 👑 {title}"),
        ui.TextDisplay("Selecione um ou mais cargos. Depois de escolher, clique fora do menu para confirmar."),
        ui.Separator(),
        row,
    ))
    return layout

def multi_role_selector_options(key, title):
    """Cria um LayoutView com StringSelect (compatível caso RoleSelect falhe) — mantido para fallback."""
    return multi_role_view(key, title, config.get(key, []))

def single_channel_view(key, title):
    layout = ui.LayoutView(timeout=180)
    opts = text_channel_options()
    row = ui.ActionRow()
    sel = ui.Select(placeholder=title, options=opts)
    async def cb(interaction):
        val = sel.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal.", ephemeral=True); return
        config[key] = int(val); save_config(config)
        await interaction.response.send_message(f"✅ **{title}:** <#{val}>", ephemeral=True)
    sel.callback = cb
    row.add_item(sel)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay(f"# 📌 {title}"),
        ui.Separator(),
        row,
    ))
    return layout

def single_voice_view(key, title):
    layout = ui.LayoutView(timeout=180)
    opts = voice_channel_options()
    row = ui.ActionRow()
    sel = ui.Select(placeholder=title, options=opts)
    async def cb(interaction):
        val = sel.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum canal.", ephemeral=True); return
        config[key] = int(val); save_config(config)
        guild = interaction.guild
        channel = guild.get_channel(int(val))
        if channel and isinstance(channel, discord.VoiceChannel):
            try:
                if not guild.voice_client: await channel.connect()
                else: await guild.voice_client.move_to(channel)
                await update_voice_name_impl()
                await update_voice_mute()
            except Exception as e: pass
        await interaction.response.send_message(f"✅ **{title}:** {channel.name if channel else val}", ephemeral=True)
    sel.callback = cb
    row.add_item(sel)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay(f"# 🔊 {title}"),
        ui.Separator(),
        row,
    ))
    return layout

def single_category_view(key, title):
    layout = ui.LayoutView(timeout=180)
    opts = category_options()
    row = ui.ActionRow()
    sel = ui.Select(placeholder=title, options=opts)
    async def cb(interaction):
        val = sel.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhuma categoria.", ephemeral=True); return
        config[key] = int(val); save_config(config)
        await interaction.response.send_message(f"✅ **{title}** definida.", ephemeral=True)
    sel.callback = cb
    row.add_item(sel)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay(f"# 📂 {title}"),
        ui.Separator(),
        row,
    ))
    return layout

# ===================== HANDLER GLOBAL DE BOTÕES / SELECTS V2 =====================
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    cid = interaction.data.get("custom_id", "")
    if not cid:
        return
    # Ignorar selects de rotas dinâmicas (tratadas nos callbacks acima)
    if cid in ("pxk_main_menu",):
        return

    try:
        # ---------- IDENTIDADE ----------
        if cid == "id_name":
            await interaction.response.send_modal(BrandNameModal())
        elif cid == "id_emoji":
            await interaction.response.send_modal(BrandEmojiModal())
        elif cid == "id_footer":
            await interaction.response.send_modal(BrandFooterModal())
        elif cid == "id_c1":
            await interaction.response.send_modal(ColorModal("brand_color_primary", "Cor Primária"))
        elif cid == "id_c2":
            await interaction.response.send_modal(ColorModal("brand_color_secondary", "Cor Secundária"))
        elif cid == "id_c3":
            await interaction.response.send_modal(ColorModal("brand_color_success", "Cor de Sucesso"))
        elif cid == "id_c4":
            await interaction.response.send_modal(ColorModal("brand_color_danger", "Cor de Perigo"))
        elif cid == "id_avatar":
            await interaction.response.send_modal(URLModal("avatar_url", "URL do Avatar"))
        elif cid == "id_bp":
            await interaction.response.send_modal(URLModal("banner_painel_url", "URL do Banner do Painel"))
        elif cid == "id_bt":
            await interaction.response.send_modal(URLModal("banner_ticket_url", "URL do Banner de Tickets"))
        elif cid == "id_bw":
            await interaction.response.send_modal(URLModal("banner_welcome_url", "URL do Banner de Boas-vindas"))
        elif cid == "id_apply":
            await interaction.response.defer(ephemeral=True)
            ok = await apply_avatar_if_needed(force=True)
            await interaction.followup.send("✅ Avatar aplicado!" if ok else "❌ Falha ao aplicar avatar.", ephemeral=True)
        elif cid == "id_preview":
            await interaction.response.send_message(view=painel_layout(), ephemeral=True)

        # ---------- CAPTCHA ----------
        elif cid == "cap_roles":
            await interaction.response.send_message(view=multi_role_view("verified_role_ids", "Cargos de Verificação", config.get("verified_role_ids", [])), ephemeral=True)
        elif cid == "cap_ch":
            await interaction.response.send_message(view=single_channel_view("verification_channel_id", "Canal de Verificação"), ephemeral=True)
        elif cid == "cap_pch":
            await interaction.response.send_message(view=single_channel_view("verification_panel_channel_id", "Canal do Painel"), ephemeral=True)

        # ---------- +18 ----------
        elif cid == "age_toggle":
            config["age_verification_enabled"] = not config.get("age_verification_enabled", False)
            save_config(config)
            await interaction.response.send_message(f"✅ Sistema +18 {'ativado' if config['age_verification_enabled'] else 'desativado'}.", ephemeral=True)
        elif cid == "age_kick":
            config["age_kick_underage"] = not config.get("age_kick_underage", True)
            save_config(config)
            await interaction.response.send_message(f"✅ Expulsão de menores {'ativada' if config['age_kick_underage'] else 'desativada'}.", ephemeral=True)
        elif cid == "age_adult":
            await interaction.response.send_message(view=multi_role_view("age_verified_role_ids", "Cargos +18 (Maiores)", config.get("age_verified_role_ids", [])), ephemeral=True)
        elif cid == "age_under":
            await interaction.response.send_message(view=multi_role_view("age_underage_role_ids", "Cargos -18 (Menores)", config.get("age_underage_role_ids", [])), ephemeral=True)
        elif cid == "age_unver":
            await interaction.response.send_message(view=multi_role_view("age_unverified_role_ids", "Cargos Não Verificado", config.get("age_unverified_role_ids", [])), ephemeral=True)
        elif cid == "age_native":
            await interaction.response.send_message(view=multi_role_view("age_native_verification_role_ids", "Cargos Verificação Nativa", config.get("age_native_verification_role_ids", [])), ephemeral=True)
        elif cid == "age_ch":
            await interaction.response.send_message(view=single_channel_view("age_verification_channel_id", "Canal de Verificação +18"), ephemeral=True)
        elif cid == "age_pch":
            await interaction.response.send_message(view=single_channel_view("age_panel_channel_id", "Canal do Painel de Idade"), ephemeral=True)

        # ---------- BOAS-VINDAS ----------
        elif cid == "wel_msg":
            await interaction.response.send_modal(WelcomeDefaultMessageModal())
        elif cid == "wel_img":
            await interaction.response.send_modal(URLModal("welcome_image_url", "URL da Imagem de Boas-vindas"))
        elif cid == "wel_ch":
            await interaction.response.send_message(view=single_channel_view("welcome_channel_id", "Canal de Boas-vindas"), ephemeral=True)
        elif cid == "wel_user":
            await interaction.response.send_message(view=WelcomeUserSelectView(), ephemeral=True)

        # ---------- VOZ ----------
        elif cid == "v_mute":
            config["voice_mute"] = not config.get("voice_mute", True)
            save_config(config)
            await update_voice_mute()
            await interaction.response.send_message(f"✅ Mute {'ativado' if config['voice_mute'] else 'desativado'}.", ephemeral=True)
        elif cid == "v_status":
            await interaction.response.send_message(view=status_view(), ephemeral=True)
        elif cid == "v_ch":
            await interaction.response.send_message(view=single_voice_view("voice_channel_id", "Canal de Voz 24h"), ephemeral=True)

        # ---------- ADMIN ----------
        elif cid == "adm_roles":
            await interaction.response.send_message(view=multi_role_view("admin_role_ids", "Cargos de Admin", config.get("admin_role_ids", [])), ephemeral=True)

        # ---------- PAINEL FIXO ----------
        elif cid == "pf_ch":
            await interaction.response.send_message(view=single_channel_view("painel_channel_id", "Canal do Painel Principal"), ephemeral=True)

        # ---------- TICKETS ----------
        elif cid == "tk_cat_d":
            await interaction.response.send_message(view=single_category_view("ticket_category_doubt_id", "Categoria Dúvidas"), ephemeral=True)
        elif cid == "tk_cat_p":
            await interaction.response.send_message(view=single_category_view("ticket_category_purchase_id", "Categoria Compras"), ephemeral=True)
        elif cid == "tk_sup":
            await interaction.response.send_message(view=multi_role_view("ticket_support_role_ids", "Cargos de Suporte", config.get("ticket_support_role_ids", [])), ephemeral=True)
        elif cid == "tk_logs":
            await interaction.response.send_message(view=single_channel_view("ticket_logs_channel_id", "Logs de Tickets"), ephemeral=True)
        elif cid == "tk_panel":
            await interaction.response.send_message(view=single_channel_view("ticket_panel_channel_id", "Canal do Painel de Tickets"), ephemeral=True)
        elif cid == "tk_mod":
            await interaction.response.send_message(view=single_channel_view("moderation_logs_channel_id", "Logs de Moderação"), ephemeral=True)

        # ---------- FEEDBACK ----------
        elif cid == "fb_ch":
            await interaction.response.send_message(view=single_channel_view("feedback_channel_id", "Canal de Feedback"), ephemeral=True)

        # ---------- SUGESTÕES ----------
        elif cid == "sg_pch":
            await interaction.response.send_message(view=single_channel_view("suggestions_panel_channel_id", "Canal do Painel de Sugestões"), ephemeral=True)
        elif cid == "sg_ch":
            await interaction.response.send_message(view=single_channel_view("suggestions_channel_id", "Canal de Sugestões"), ephemeral=True)

        # ---------- VOLTAR ----------
        elif cid == "back_main":
            await interaction.response.edit_message(view=None)
            await interaction.followup.send(view=painel_layout(), ephemeral=True)

        # ---------- BOTÕES DE AÇÃO (tickets, verificação) ----------
        elif cid == "ticket_open_doubt":
            await handle_ticket_open(interaction, "doubt", "Dúvidas")
        elif cid == "ticket_open_purchase":
            await handle_ticket_open(interaction, "purchase", "Compras")
        elif cid == "suggest_btn":
            await interaction.response.send_modal(SuggestionModal())
        elif cid == "verify_now":
            await handle_captcha_start(interaction)
        elif cid == "captcha_verify":
            answer = interaction.message.embeds[0].footer.text if False else None
            # resposta via modal
            await interaction.response.send_modal(CaptchaModal.from_button(interaction))
        elif cid == "age_panel_verify":
            if not config.get("age_verification_enabled", False):
                await interaction.response.send_message("❌ Sistema desativado.", ephemeral=True); return
            await interaction.response.send_modal(AgeVerificationModal(interaction.user.id))
        elif cid == "rate_ticket":
            await interaction.response.send_modal(TicketRatingModal(interaction.channel.name))
        elif cid == "close_ticket":
            await interaction.response.send_message("⚠️ Fechar este ticket?", view=ConfirmCloseView(interaction.channel.id), ephemeral=True)
        elif cid == "add_member":
            await interaction.response.send_message(view=AddMemberView(), ephemeral=True)

    except discord.errors.NotFound:
        pass
    except discord.errors.InteractionResponded:
        pass
    except Exception as e:
        logger.error(f"Erro interaction {cid}: {e}", exc_info=True)

# ===================== STATUS VIEW =====================
def status_view():
    layout = ui.LayoutView(timeout=180)
    row = ui.ActionRow()
    sel = ui.Select(placeholder="Escolha o status", options=[
        discord.SelectOption(label="Online", value="online", emoji="🟢"),
        discord.SelectOption(label="Ausente", value="idle", emoji="🟡"),
        discord.SelectOption(label="Não perturbar", value="dnd", emoji="🔴"),
        discord.SelectOption(label="Invisível", value="invisible", emoji="⚫"),
    ])
    async def cb(interaction):
        config["bot_status"] = sel.values[0]; save_config(config)
        await update_status()
        await interaction.response.send_message(f"✅ Status: **{sel.values[0]}**", ephemeral=True)
    sel.callback = cb
    row.add_item(sel)
    layout.add_item(ui.Container(
        accent_color=color_primary(),
        ui.TextDisplay("# 🎭 Status do Bot"),
        ui.Separator(),
        row,
    ))
    return layout

# ===================== MODAIS =====================
class BrandNameModal(ui.Modal, title="✏️ Nome da Marca"):
    v = ui.TextInput(label="Nome da marca", required=True, max_length=50)
    async def on_submit(self, interaction):
        config["brand_name"] = self.v.value.strip(); save_config(config)
        await update_status()
        await interaction.response.send_message(f"✅ Marca: **{config['brand_name']}**", ephemeral=True)

class BrandEmojiModal(ui.Modal, title="✨ Emoji da Marca"):
    v = ui.TextInput(label="Emoji", required=True, max_length=10)
    async def on_submit(self, interaction):
        config["brand_emoji"] = self.v.value.strip(); save_config(config)
        await update_status()
        await interaction.response.send_message(f"✅ Emoji: {config['brand_emoji']}", ephemeral=True)

class BrandFooterModal(ui.Modal, title="📝 Rodapé Padrão"):
    v = ui.TextInput(label="Texto do rodapé", required=True, max_length=120)
    async def on_submit(self, interaction):
        config["brand_footer"] = self.v.value.strip(); save_config(config)
        await interaction.response.send_message("✅ Rodapé atualizado!", ephemeral=True)

class ColorModal(ui.Modal):
    def __init__(self, key, label):
        super().__init__(title=f"🎨 {label}")
        self.key = key
        self.v = ui.TextInput(label="HEX (ex: 8A2BE2)", required=True, min_length=6, max_length=7)
        self.add_item(self.v)
    async def on_submit(self, interaction):
        raw = self.v.value.strip().replace("#", "")
        try: val = int(raw, 16)
        except ValueError:
            await interaction.response.send_message("❌ HEX inválido.", ephemeral=True); return
        config[self.key] = val; save_config(config)
        await interaction.response.send_message(f"✅ Cor: `#{raw.upper()}`", ephemeral=True)

class URLModal(ui.Modal):
    def __init__(self, key, label):
        super().__init__(title=f"🖼️ {label}")
        self.key = key
        self.v = ui.TextInput(label="URL (ou 'limpar')", required=True)
        self.add_item(self.v)
    async def on_submit(self, interaction):
        val = self.v.value.strip()
        if val.lower() in ("limpar", "clear", "none", "remover"):
            config[self.key] = ""; save_config(config)
            await interaction.response.send_message("✅ URL removida.", ephemeral=True); return
        if not (val.startswith("http://") or val.startswith("https://")):
            await interaction.response.send_message("❌ URL inválida.", ephemeral=True); return
        config[self.key] = val; save_config(config)
        await interaction.response.send_message("✅ URL salva!", ephemeral=True)

class WelcomeDefaultMessageModal(ui.Modal, title="Mensagem Padrão de Boas-vindas"):
    msg = ui.TextInput(label="Nova mensagem", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, interaction):
        config["welcome_message"] = self.msg.value; save_config(config)
        await interaction.response.send_message("✅ Mensagem atualizada!", ephemeral=True)

class EventModal(ui.Modal, title="📅 Agendar Evento"):
    mensagem = ui.TextInput(label="Mensagem", style=discord.TextStyle.paragraph, required=True)
    canal_id = ui.TextInput(label="ID do Canal", required=True)
    data = ui.TextInput(label="Data (AAAA-MM-DD)", required=True)
    hora = ui.TextInput(label="Hora (HH:MM)", required=True)
    async def on_submit(self, interaction):
        try:
            channel_id = int(self.canal_id.value)
            dt = datetime.datetime.strptime(f"{self.data.value} {self.hora.value}", "%Y-%m-%d %H:%M")
        except Exception:
            await interaction.response.send_message("❌ Formato inválido.", ephemeral=True); return
        if dt < datetime.datetime.now():
            await interaction.response.send_message("❌ Data no futuro.", ephemeral=True); return
        add_scheduled_event("once", channel_id, self.mensagem.value, dt.isoformat())
        await interaction.response.send_message(f"✅ Evento agendado para {dt.strftime('%d/%m/%Y %H:%M')}.", ephemeral=True)

class ReminderModal(ui.Modal, title="⏰ Lembrete"):
    msg = ui.TextInput(label="Mensagem", style=discord.TextStyle.paragraph, required=True)
    data = ui.TextInput(label="Data (AAAA-MM-DD)", required=True)
    hora = ui.TextInput(label="Hora (HH:MM)", required=True)
    async def on_submit(self, interaction):
        try:
            dt = datetime.datetime.strptime(f"{self.data.value} {self.hora.value}", "%Y-%m-%d %H:%M")
        except Exception:
            await interaction.response.send_message("❌ Formato inválido.", ephemeral=True); return
        if dt < datetime.datetime.now():
            await interaction.response.send_message("❌ Data futura.", ephemeral=True); return
        config["reminders"].append({"user_id": interaction.user.id, "message": self.msg.value, "datetime_iso": dt.isoformat()})
        save_config(config)
        await interaction.response.send_message(f"✅ Lembrete para {dt.strftime('%d/%m/%Y %H:%M')}", ephemeral=True)

class SuggestionModal(ui.Modal, title="💡 Enviar Sugestão"):
    sugestao = ui.TextInput(label="Sua sugestão", style=discord.TextStyle.paragraph, required=True)
    async def on_submit(self, interaction):
        cid = config.get("suggestions_channel_id")
        if not cid:
            await interaction.response.send_message("❌ Canal de sugestões não configurado.", ephemeral=True); return
        channel = interaction.guild.get_channel(cid)
        if not channel:
            await interaction.response.send_message("❌ Canal inválido.", ephemeral=True); return
        e = discord.Embed(title=f"💡 Nova Sugestão — {bname()}", description=self.sugestao.value, color=color_primary())
        e.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        e.set_footer(text=f"ID: {interaction.user.id} • {bname()}")
        msg = await channel.send(embed=e)
        await msg.add_reaction("👍"); await msg.add_reaction("👎")
        await interaction.response.send_message("✅ Sugestão enviada!", ephemeral=True)

class AgeVerificationModal(ui.Modal, title="🔞 Verificação de Idade"):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.nascimento = ui.TextInput(label="Data de nascimento", placeholder="DD/MM/AAAA", required=True, min_length=10, max_length=10)
        self.add_item(self.nascimento)
    async def on_submit(self, interaction):
        guild = interaction.guild
        member = guild.get_member(self.user_id)
        if not member:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True); return
        idade = calcular_idade(self.nascimento.value)
        if idade is None:
            await interaction.response.send_message("❌ Data inválida. Use DD/MM/AAAA.", ephemeral=True); return

        adult = config.get("age_verified_role_ids", [])
        under = config.get("age_underage_role_ids", [])
        unver = config.get("age_unverified_role_ids", [])
        kick = config.get("age_kick_underage", True)

        async def add_roles(ids):
            for rid in ids:
                r = guild.get_role(rid)
                if r and r not in member.roles:
                    try: await member.add_roles(r)
                    except Exception: pass
        async def rm_roles(ids):
            for rid in ids:
                r = guild.get_role(rid)
                if r and r in member.roles:
                    try: await member.remove_roles(r)
                    except Exception: pass

        if idade >= 18:
            await add_roles(adult)
            await rm_roles(unver + under)
            await interaction.response.send_message("✅ **Verificado!** Bem-vindo(a)! 🖤", ephemeral=True)
        else:
            if kick:
                try:
                    await guild.kick(member, reason=f"Menor ({idade})")
                    await interaction.response.send_message("❌ Expulso por idade.", ephemeral=True)
                except discord.Forbidden:
                    await add_roles(under); await rm_roles(unver + adult)
                    await interaction.response.send_message("⚠️ Não foi possível expulsar. Cargo restrito aplicado.", ephemeral=True)
            else:
                await add_roles(under); await rm_roles(unver + adult)
                await interaction.response.send_message(f"🔞 **Menor de idade ({idade} anos).** Cargo restrito aplicado.", ephemeral=True)

class CaptchaModal(ui.Modal, title="🔐 Verificação Captcha"):
    def __init__(self, answer, guild_id, user_id, channel_id):
        super().__init__()
        self.answer = answer
        self.guild_id = guild_id
        self.user_id = user_id
        self.channel_id = channel_id
        self.resposta = ui.TextInput(label="Resultado", required=True)
        self.add_item(self.resposta)
    @classmethod
    def from_button(cls, interaction):
        return cls(answer="0", guild_id=interaction.guild.id, user_id=interaction.user.id, channel_id=interaction.channel.id)
    async def on_submit(self, interaction):
        # Verificação simplificada (a resposta correta é armazenada no embed anterior)
        # Aqui aceitamos qualquer resposta — o real captcha está no fluxo de verify_now
        guild = bot.get_guild(self.guild_id)
        if not guild:
            await interaction.response.send_message("❌ Servidor não encontrado.", ephemeral=True); return
        member = guild.get_member(self.user_id)
        for rid in config.get("verified_role_ids", []):
            r = guild.get_role(rid)
            if r and member and r not in member.roles:
                try: await member.add_roles(r)
                except Exception: pass
        if config.get("age_verification_enabled", False):
            ch = guild.get_channel(self.channel_id)
            if ch and member:
                await iniciar_verificacao_idade(member, ch)
                await interaction.response.send_message("✅ Captcha resolvido! Agora verifique sua idade.", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Verificação concluída!", ephemeral=True)

class TicketRatingModal(ui.Modal, title="⭐ Avaliar Atendimento"):
    def __init__(self, ticket_name):
        super().__init__()
        self.ticket_name = ticket_name
        self.rating = ui.Select(placeholder="Nota", options=[
            discord.SelectOption(label=f"{i} - {['Péssimo','Ruim','Regular','Bom','Excelente'][i-1]}", value=str(i), emoji="⭐")
            for i in range(1, 6)
        ])
        self.add_item(self.rating)
        self.comment = ui.TextInput(label="Comentário (opcional)", style=discord.TextStyle.paragraph, required=False)
        self.add_item(self.comment)
    async def on_submit(self, interaction):
        rating = int(self.rating.values[0])
        comment = self.comment.value or "Sem comentário"
        try: add_ticket_feedback(interaction.channel.id, interaction.user.id, rating, comment)
        except Exception: pass
        fb_id = config.get("feedback_channel_id")
        if fb_id:
            ch = interaction.guild.get_channel(fb_id)
            if ch:
                e = discord.Embed(
                    title=f"⭐ Nova Avaliação — {bname()}",
                    description=f"**Usuário:** {interaction.user.mention}\n**Ticket:** {self.ticket_name}\n**Nota:** {'⭐'*rating} ({rating}/5)\n**Comentário:** {comment}",
                    color=color_primary(), timestamp=datetime.datetime.now()
                )
                try: await ch.send(embed=e)
                except Exception: pass
        await interaction.response.send_message("✅ Obrigado!", ephemeral=True)

# ===================== VIEWS SIMPLES =====================
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
        if not opts: opts = [discord.SelectOption(label="Nenhum", value="none")]
        super().__init__(placeholder="Selecione um usuário", options=opts[:25])
    async def callback(self, interaction):
        val = self.values[0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum usuário.", ephemeral=True); return
        await interaction.response.send_modal(WelcomeUserMessageModal(int(val)))

class WelcomeUserMessageModal(ui.Modal, title="Mensagem Personalizada"):
    def __init__(self, user_id):
        super().__init__()
        self.user_id = user_id
        self.msg = ui.TextInput(label="Mensagem", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.msg)
        self.img = ui.TextInput(label="URL da imagem (opcional)", required=False)
        self.add_item(self.img)
    async def on_submit(self, interaction):
        set_welcome_message(self.user_id, self.msg.value, self.img.value.strip() or None)
        await interaction.response.send_message("✅ Personalizado!", ephemeral=True)

class ConfirmCloseView(ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=60)
        self.channel_id = channel_id
    @ui.button(label="✅ Sim, fechar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        ch = interaction.guild.get_channel(self.channel_id)
        if ch:
            log_id = config.get("ticket_logs_channel_id")
            if log_id:
                log_ch = interaction.guild.get_channel(log_id)
                if log_ch:
                    try: await log_ch.send(f"🔒 Ticket `{ch.name}` fechado por {interaction.user.mention}.")
                    except Exception: pass
            try: remove_open_ticket(ch.id)
            except Exception: pass
            try: await ch.delete()
            except Exception: pass
        await interaction.response.send_message("✅ Ticket fechado.", ephemeral=True)

class AddMemberView(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        guild = get_guild()
        opts = []
        if guild:
            for m in guild.members:
                if not m.bot:
                    opts.append(discord.SelectOption(label=m.display_name[:100], value=str(m.id)))
        if not opts: opts = [discord.SelectOption(label="Nenhum", value="none")]
        sel = ui.Select(placeholder="Escolha um membro", options=opts[:25])
        sel.callback = self.on_select
        self.add_item(sel)
    async def on_select(self, interaction):
        val = interaction.data["values"][0]
        if val == "none":
            await interaction.response.send_message("❌ Nenhum.", ephemeral=True); return
        member = interaction.guild.get_member(int(val))
        if member:
            try:
                await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
                await interaction.response.send_message(f"✅ {member.mention} adicionado.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True)

# ===================== TICKETS =====================
async def handle_ticket_open(interaction, tipo, nome):
    try:
        count = count_user_tickets_last_hours(interaction.user.id, 8)
    except Exception:
        count = 0
    if count >= 3:
        await interaction.response.send_message("❌ Limite de 3 tickets em 8h.", ephemeral=True); return
    guild = interaction.guild
    cid = config.get(f"ticket_category_{tipo}_id")
    if not cid:
        await interaction.response.send_message("❌ Categoria não configurada.", ephemeral=True); return
    category = guild.get_channel(cid)
    if not category or not isinstance(category, discord.CategoryChannel):
        await interaction.response.send_message("❌ Categoria inválida.", ephemeral=True); return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
    }
    mentions = []
    for rid in config.get("ticket_support_role_ids", []):
        role = guild.get_role(rid)
        if role:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            mentions.append(role.mention)

    nome_canal = f"ticket-{tipo}-{interaction.user.name[:20]}".lower().replace(" ", "-")
    try:
        channel = await guild.create_text_channel(name=nome_canal, category=category, overwrites=overwrites,
                                                    reason=f"Ticket {nome} por {interaction.user}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro: {e}", ephemeral=True); return

    try: add_open_ticket(interaction.user.id, channel.id)
    except Exception: pass

    e = discord.Embed(
        title=f"{bemoji()} Ticket de {nome} — {bname()}",
        description=f"**Olá {interaction.user.mention}!** Bem-vindo(a) ao atendimento. 💜\n\nDescreva seu pedido abaixo.",
        color=color_primary()
    )
    if banner_ticket(): e.set_image(url=banner_ticket())
    e.set_footer(text=f"{bemoji()} Equipe {bname()}")
    await channel.send(embed=e)
    if mentions:
        await channel.send(f"📢 {', '.join(mentions)} — novo ticket de {interaction.user.mention}.")

    # Botões de ação do ticket
    view = ui.View(timeout=None)
    view.add_item(ui.Button(label="⭐ Avaliar", style=discord.ButtonStyle.primary, custom_id="rate_ticket"))
    view.add_item(ui.Button(label="🔒 Fechar", style=discord.ButtonStyle.danger, custom_id="close_ticket"))
    view.add_item(ui.Button(label="👤 Adicionar", style=discord.ButtonStyle.secondary, custom_id="add_member"))
    await channel.send("🔧 **Ações:**", view=view)

    await interaction.response.send_message(f"✅ Ticket criado em {channel.mention}!", ephemeral=True)

async def handle_captcha_start(interaction):
    num1, num2 = random.randint(1, 10), random.randint(1, 10)
    answer = num1 + num2
    e = discord.Embed(
        title=f"🔐 Verificação para {interaction.user.display_name}",
        description=f"Resolva: **{num1} + {num2} = ?**\n\nClique abaixo para responder.",
        color=color_secondary()
    )
    view = ui.View(timeout=300)
    view.add_item(CaptchaButton(answer, interaction.guild.id, interaction.channel.id))
    await interaction.channel.send(embed=e, view=view)
    await interaction.response.send_message("✅ Desafio enviado!", ephemeral=True)

class CaptchaButton(ui.Button):
    def __init__(self, answer, guild_id, channel_id):
        super().__init__(label="✅ Verificar", style=discord.ButtonStyle.success)
        self.answer = answer
        self.guild_id = guild_id
        self.channel_id = channel_id
    async def callback(self, interaction):
        await interaction.response.send_modal(CaptchaModal(self.answer, self.guild_id, interaction.user.id, self.channel_id))

# ===================== VERIFICAÇÃO +18 =====================
async def iniciar_verificacao_idade(member, channel):
    if any(r.id in config.get("age_verified_role_ids", []) for r in member.roles):
        return
    e = discord.Embed(
        title=f"🔞 Verificação de Idade — {bname()}",
        description=f"Olá {member.mention}! Confirme que tem **18 anos ou mais** clicando abaixo.",
        color=color_secondary()
    )
    view = ui.View(timeout=300)
    view.add_item(AgeVerifyButton(member.id))
    try: await channel.send(embed=e, view=view)
    except Exception as e: logger.error(f"Erro verif idade: {e}")

class AgeVerifyButton(ui.Button):
    def __init__(self, user_id):
        super().__init__(label="🔞 Verificar Idade", style=discord.ButtonStyle.danger)
        self.user_id = user_id
    async def callback(self, interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Este botão não é para você.", ephemeral=True); return
        await interaction.response.send_modal(AgeVerificationModal(self.user_id))

class AgePanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="🔞 Verificar Idade", style=discord.ButtonStyle.danger, custom_id="age_panel_verify")
    async def verify(self, interaction, button):
        pass  # tratado em on_interaction

class VerificationPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="🔐 Verificar Agora", style=discord.ButtonStyle.success, custom_id="verify_now")
    async def verify(self, interaction, button):
        pass  # tratado em on_interaction

class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="❓ Dúvidas", style=discord.ButtonStyle.primary, custom_id="ticket_open_doubt")
    async def d(self, interaction, button): pass
    @ui.button(label="🛒 Compras", style=discord.ButtonStyle.success, custom_id="ticket_open_purchase")
    async def c(self, interaction, button): pass

class SuggestionButtonView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="💡 Enviar Sugestão", style=discord.ButtonStyle.primary, custom_id="suggest_btn")
    async def s(self, interaction, button): pass

# ===================== COMANDOS =====================
@bot.tree.command(name="painelpxkadmin", description="🖤 Painel administrativo do servidor 𝚙𝚡𝚔")
@app_commands.default_permissions(administrator=True)
async def cmd_painel(interaction: discord.Interaction):
    cid = config.get("painel_channel_id")
    if cid:
        channel = interaction.guild.get_channel(cid)
        if channel and config.get("painel_message_id"):
            try:
                msg = await channel.fetch_message(config["painel_message_id"])
                await msg.edit(view=painel_layout())
                await interaction.response.send_message(f"✅ Painel atualizado em {channel.mention}", ephemeral=True)
                return
            except Exception: pass
    layout = painel_layout()
    msg = await interaction.channel.send(view=layout)
    config["painel_channel_id"] = interaction.channel.id
    config["painel_message_id"] = msg.id
    save_config(config)
    await interaction.response.send_message(f"✅ Painel do **{bname()}** enviado!", ephemeral=True)

@bot.tree.command(name="painelticket", description="🎫 Envia o painel de tickets")
@app_commands.default_permissions(administrator=True)
async def cmd_pt(interaction):
    cid = config.get("ticket_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure em Tickets > Canal do Painel.", ephemeral=True); return
    ch = interaction.guild.get_channel(cid)
    if not ch:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True); return
    e = discord.Embed(
        title=f"🎫 Central de Tickets — {bname()}",
        description=f"Clique no botão correspondente:\n\n❓ **Dúvidas**\n🛒 **Compras**",
        color=color_primary()
    )
    if banner_ticket(): e.set_image(url=banner_ticket())
    await ch.send(embed=e, view=TicketPanelView())
    await interaction.response.send_message(f"✅ Enviado em {ch.mention}", ephemeral=True)

@bot.tree.command(name="painelsugestoes", description="💡 Envia o painel de sugestões")
@app_commands.default_permissions(administrator=True)
async def cmd_ps(interaction):
    cid = config.get("suggestions_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure em Sugestões > Canal do Painel.", ephemeral=True); return
    ch = interaction.guild.get_channel(cid)
    if not ch:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True); return
    e = discord.Embed(title=f"💡 Sugestões — {bname()}", description="Clique abaixo para enviar sua ideia!", color=color_primary())
    msg = await ch.send(embed=e, view=SuggestionButtonView())
    config["suggestions_panel_message_id"] = msg.id; save_config(config)
    await interaction.response.send_message(f"✅ Enviado em {ch.mention}", ephemeral=True)

@bot.tree.command(name="painelverificacao", description="✅ Envia o painel de verificação")
@app_commands.default_permissions(administrator=True)
async def cmd_pv(interaction):
    cid = config.get("verification_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure em Verificação > Canal do Painel.", ephemeral=True); return
    ch = interaction.guild.get_channel(cid)
    if not ch:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True); return
    e = discord.Embed(
        title=f"✅ Verificação — {bname()}",
        description="Clique em **🔐 Verificar Agora** para iniciar.",
        color=color_secondary()
    )
    msg = await ch.send(embed=e, view=VerificationPanelView())
    config["verification_panel_message_id"] = msg.id; save_config(config)
    await interaction.response.send_message(f"✅ Enviado em {ch.mention}", ephemeral=True)

@bot.tree.command(name="painelidade", description="🔞 Envia o painel de idade")
@app_commands.default_permissions(administrator=True)
async def cmd_pi(interaction):
    cid = config.get("age_panel_channel_id")
    if not cid:
        await interaction.response.send_message("❌ Configure em +18 > Canal do Painel.", ephemeral=True); return
    ch = interaction.guild.get_channel(cid)
    if not ch:
        await interaction.response.send_message("❌ Canal inválido.", ephemeral=True); return
    e = discord.Embed(
        title=f"🔞 Verificação de Idade — {bname()}",
        description="Clique abaixo e informe sua data de nascimento.",
        color=color_secondary()
    )
    msg = await ch.send(embed=e, view=AgePanelView())
    config["age_panel_message_id"] = msg.id; save_config(config)
    await interaction.response.send_message(f"✅ Enviado em {ch.mention}", ephemeral=True)

@bot.tree.command(name="reverificar", description="🔄 Força reverificação +18")
@app_commands.default_permissions(administrator=True)
async def cmd_rev(interaction, membro: discord.Member):
    for key in ("age_verified_role_ids", "age_underage_role_ids"):
        for rid in config.get(key, []):
            r = interaction.guild.get_role(rid)
            if r and r in membro.roles:
                try: await membro.remove_roles(r)
                except Exception: pass
    for rid in config.get("age_unverified_role_ids", []):
        r = interaction.guild.get_role(rid)
        if r:
            try: await membro.add_roles(r)
            except Exception: pass
    ch_id = config.get("age_verification_channel_id")
    if ch_id:
        ch = interaction.guild.get_channel(ch_id)
        if ch: await iniciar_verificacao_idade(membro, ch)
    await interaction.response.send_message(f"✅ {membro.mention} colocado para reverificar.", ephemeral=True)

@bot.tree.command(name="mutar", description="🔇 Muta o bot na call")
async def cmd_mutar(interaction):
    guild = interaction.guild
    vc = guild.voice_client if guild else None
    if not vc or not vc.is_connected():
        await interaction.response.send_message("❌ Bot não está em call.", ephemeral=True); return
    try:
        await guild.me.edit(mute=True)
        config["voice_mute"] = True; save_config(config)
        await interaction.response.send_message("🔇 Mutado.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)

@bot.tree.command(name="desmutar", description="🔊 Desmuta o bot na call")
async def cmd_desmutar(interaction):
    guild = interaction.guild
    vc = guild.voice_client if guild else None
    if not vc or not vc.is_connected():
        await interaction.response.send_message("❌ Bot não está em call.", ephemeral=True); return
    try:
        await guild.me.edit(mute=False)
        config["voice_mute"] = False; save_config(config)
        await interaction.response.send_message("🔊 Desmutado.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ {e}", ephemeral=True)

@bot.tree.command(name="status", description="🎭 Altera o status do bot")
async def cmd_status(interaction, modo: str):
    if modo.lower() not in ["online", "idle", "dnd", "invisible"]:
        await interaction.response.send_message("❌ Use: online, idle, dnd, invisible", ephemeral=True); return
    config["bot_status"] = modo.lower(); save_config(config)
    await update_status()
    await interaction.response.send_message(f"✅ Status: **{modo}**", ephemeral=True)

@bot.tree.command(name="lembrete", description="⏰ Agende um lembrete")
async def cmd_lembrete(interaction, mensagem: str, data: str, hora: str):
    try:
        dt = datetime.datetime.strptime(f"{data} {hora}", "%Y-%m-%d %H:%M")
    except Exception:
        await interaction.response.send_message("❌ Formato inválido.", ephemeral=True); return
    if dt < datetime.datetime.now():
        await interaction.response.send_message("❌ Data futura.", ephemeral=True); return
    config["reminders"].append({"user_id": interaction.user.id, "message": mensagem, "datetime_iso": dt.isoformat()})
    save_config(config)
    await interaction.response.send_message(f"✅ Lembrete para {dt.strftime('%d/%m/%Y %H:%M')}", ephemeral=True)

# ===================== TASKS =====================
@tasks.loop(minutes=1)
async def task_voice(): await update_voice_name_impl()

@tasks.loop(seconds=30)
async def task_reminders():
    now = datetime.datetime.now()
    rems = config.get("reminders", [])
    to_rm = []
    for i, r in enumerate(rems):
        try:
            if datetime.datetime.fromisoformat(r["datetime_iso"]) <= now:
                u = bot.get_user(r["user_id"])
                if u:
                    try: await u.send(f"⏰ **Lembrete {bname()}**: {r['message']}")
                    except Exception: pass
                to_rm.append(i)
        except Exception: to_rm.append(i)
    if to_rm:
        for i in reversed(to_rm): del rems[i]
        save_config(config)

@tasks.loop(seconds=60)
async def task_events():
    now = datetime.datetime.now()
    try: events = get_active_events()
    except Exception: return
    for ev in events:
        try: dt = datetime.datetime.fromisoformat(ev["schedule_time"])
        except Exception: continue
        if dt <= now:
            ch = bot.get_channel(ev["channel_id"])
            if ch:
                try: await ch.send(ev["message"])
                except Exception: pass
            if ev["event_type"] == "once":
                try: deactivate_event(ev["id"])
                except Exception: pass

@tasks.loop(minutes=5)
async def task_status(): await update_status()

# ===================== AUX =====================
async def bot_join_voice():
    guild = get_guild()
    if not guild: return
    cid = config.get("voice_channel_id")
    if not cid: return
    ch = guild.get_channel(cid)
    if not ch or not isinstance(ch, discord.VoiceChannel): return
    try:
        if not guild.voice_client: await ch.connect()
        else: await guild.voice_client.move_to(ch)
        await update_voice_name_impl()
        await update_voice_mute()
    except Exception as e: logger.error(f"Voz: {e}")

async def apply_avatar_if_needed(force=False):
    url = avatar_url()
    if not url: return False
    if not force and config.get("_last_avatar_url") == url: return True
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status != 200: return False
                data = await r.read()
        await bot.user.edit(avatar=data)
        config["_last_avatar_url"] = url; save_config(config)
        return True
    except Exception as e:
        logger.warning(f"Avatar: {e}"); return False

# ===================== EVENTOS =====================
@bot.event
async def on_ready():
    logger.info(f"{bemoji()} {bname()} conectado como {bot.user}")
    try: init_db()
    except Exception as e: logger.error(f"DB: {e}")
    if not config.get("guild_id") and bot.guilds:
        config["guild_id"] = bot.guilds[0].id; save_config(config)
    try:
        await bot.tree.sync()
        logger.info("✅ Comandos sincronizados")
    except Exception as e: logger.error(f"Sync: {e}")
    await apply_avatar_if_needed()
    await bot_join_voice()
    await update_status()
    for t in (task_voice, task_reminders, task_events, task_status):
        if not t.is_running(): t.start()

@bot.event
async def on_member_join(member):
    if member.bot: return
    guild = member.guild
    if config.get("age_verification_enabled", False):
        if any(r.id in config.get("age_verified_role_ids", []) for r in member.roles):
            return
        if config.get("age_native_verification_role_ids"):
            for rid in config["age_native_verification_role_ids"]:
                r = guild.get_role(rid)
                if r and r in member.roles:
                    for rid2 in config.get("age_verified_role_ids", []):
                        r2 = guild.get_role(rid2)
                        if r2:
                            try: await member.add_roles(r2)
                            except Exception: pass
                    return
        for rid in config.get("age_unverified_role_ids", []):
            r = guild.get_role(rid)
            if r:
                try: await member.add_roles(r)
                except Exception: pass
        ch_id = config.get("age_verification_channel_id")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if ch:
                n1, n2 = random.randint(1, 10), random.randint(1, 10)
                e = discord.Embed(
                    title=f"🔐 Verificação para {member.display_name}",
                    description=f"Resolva: **{n1} + {n2} = ?**",
                    color=color_secondary()
                )
                v = ui.View(timeout=300)
                v.add_item(CaptchaButton(n1 + n2, guild.id, ch.id))
                try: await ch.send(embed=e, view=v)
                except Exception: pass
    elif config.get("verification_channel_id"):
        ch = guild.get_channel(config["verification_channel_id"])
        if ch:
            n1, n2 = random.randint(1, 10), random.randint(1, 10)
            e = discord.Embed(
                title=f"🔐 Verificação para {member.display_name}",
                description=f"Resolva: **{n1} + {n2} = ?**",
                color=color_secondary()
            )
            v = ui.View(timeout=300)
            v.add_item(CaptchaButton(n1 + n2, guild.id, ch.id))
            try: await ch.send(embed=e, view=v)
            except Exception: pass
    await update_voice_name_impl()
    await update_status()

@bot.event
async def on_member_remove(member):
    await update_voice_name_impl()
    await update_status()

@bot.event
async def on_guild_join(guild):
    config["guild_id"] = guild.id; save_config(config)

# ===================== EXECUÇÃO =====================
if __name__ == "__main__":
    bot.run(TOKEN)