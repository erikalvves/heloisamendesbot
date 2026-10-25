import os
import sys
import sqlite3
from datetime import datetime

# Garante que o terminal Windows suporte UTF-8 com emojis
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from create_pix import gerar_cobranca, PRODUTOS

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# === BANCO DE DADOS ===
def init_db():
    conn = sqlite3.connect("pedidos.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            paymentId TEXT PRIMARY KEY,
            usuario_id INTEGER,
            produto_id TEXT,
            valor_centavos INTEGER,
            status TEXT DEFAULT 'pendente',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pago_em TIMESTAMP,
            entregue_em TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def registrar_pedido(dados):
    conn = sqlite3.connect("pedidos.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO pedidos
        (paymentId, usuario_id, produto_id, valor_centavos, status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        dados["paymentId"],
        dados["usuario_id"],
        dados["produto_id"],
        dados["valor_centavos"],
        "pendente"
    ))
    conn.commit()
    conn.close()

init_db()

# === MENSAGEM INICIAL ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📸 Pack de Fotos — R$ 5,00", callback_data="confirmar:fotos")],
        [InlineKeyboardButton("🎬 Pack de Vídeos — R$ 12,00", callback_data="confirmar:videos")]
    ]
    await update.message.reply_text(
        "😈💋 Olá, safado… Veio me procurar, né? KKKK 🤭🔥\n\n"
        "Aqui você encontra meus packs +18 com as fotos e vídeos mais ousados… vem matar essa curiosidade 😏🍑🔞\n\n"
        "Escolha o produto que deseja:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === FLUXO COMPLETO COM PRÉVIA DE MÍDIA ===
async def processo_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    print(f"[CLIQUE] {query.data}")  # Debug — aparece no terminal

    # ==========================================
    # PASSO 1 — PRÉVIA PRIMEIRO
    # ==========================================
    if query.data.startswith("confirmar:"):
        _, produto_id = query.data.split(":")
        context.user_data["produto_escolhido"] = produto_id

        if produto_id == "fotos":
            # Apaga a mensagem com os botões
            await query.delete_message()

            try:
                with open("previa_fotos.jpg", "rb") as foto:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=foto,
                        caption=(
                            "📸 *Prévia — Pack de Fotos*\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            "✨ Mais de 50 fotos exclusivas\n"
                            "✨ As mais ousadas e sensuais 🔥\n"
                            "✨ Nada censurado 🔞\n"
                            "✨ Tudo enviado na hora!\n\n"
                            "💰 Valor: R$ 5,00"
                        ),
                        parse_mode="Markdown"
                    )
            except FileNotFoundError:
                print("[AVISO] previa_fotos.jpg nao encontrada. Enviando texto.")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        "📸 *Prévia — Pack de Fotos*\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "✨ Mais de 50 fotos exclusivas\n"
                        "✨ As mais ousadas e sensuais 🔥\n"
                        "✨ Nada censurado 🔞\n"
                        "✨ Tudo enviado na hora!\n\n"
                        "💰 Valor: R$ 5,00\n\n"
                        "⚠️ (Imagem de amostra em atualização)"
                    ),
                    parse_mode="Markdown"
                )

            # Botões aparecem DEPOIS da prévia
            keyboard = [
                [InlineKeyboardButton("✅ Sim, quero comprar!", callback_data="comprar:fotos")],
                [InlineKeyboardButton("❌ Só olhando por agora", callback_data="sair")]
            ]
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="O que achou? 😏👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        if produto_id == "videos":
            await query.delete_message()

            try:
                print("[DEBUG] Tentando enviar video...")
                with open("previa_videos.mp4", "rb") as video:
                    await context.bot.send_video(
                        chat_id=update.effective_chat.id,
                        video=video,
                        caption=(
                            "🎬 *Prévia — Pack de Vídeos*\n"
                            "━━━━━━━━━━━━━━━━━━━━━━\n"
                            "🔥 Vídeos longos e bem quentes\n"
                            "✨ Momentos mais íntimos e reais\n"
                            "✨ Tudo sem cortes 🔞\n"
                            "✨ Acesso imediato após pagamento\n\n"
                            "💰 Valor: R$ 12,00"
                        ),
                        parse_mode="Markdown"
                    )
                print("[DEBUG] Video enviado com sucesso!")
            except Exception as e:
                print(f"[ERRO] Falha ao enviar video: {e}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        "🎬 *Prévia — Pack de Vídeos*\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "🔥 Vídeos longos e bem quentes\n"
                        "✨ Momentos mais íntimos e reais\n"
                        "✨ Tudo sem cortes 🔞\n"
                        "✨ Acesso imediato após pagamento\n\n"
                        "💰 Valor: R$ 12,00\n\n"
                        "⚠️ Vídeo de amostra em breve… já garante o seu! 😈"
                    ),
                    parse_mode="Markdown"
                )

            keyboard = [
                [InlineKeyboardButton("✅ Sim, quero comprar!", callback_data="comprar:videos")],
                [InlineKeyboardButton("❌ Só olhando por agora", callback_data="sair")]
            ]
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="O que achou? 😈👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

    # ==========================================
    # PASSO 2 — GERA PAGAMENTO APÓS CONFIRMAR
    # ==========================================
    if query.data.startswith("comprar:"):
        _, produto_id = query.data.split(":")
        usuario = update.effective_user
        produto = PRODUTOS[produto_id]

        await query.edit_message_text(
            "Perfeito, escolha certa 😈🔥\nGerando seu PIX… aguarde um momento."
        )

        cobranca = gerar_cobranca(
            produto_id=produto_id,
            usuario_id=usuario.id,
            nome_usuario=usuario.full_name or "Cliente",
            email_usuario=f"usuario_{usuario.id}@exemplo.com"
        )

        if "erro" in cobranca:
            await query.edit_message_text(
                f"❌ Deu algum problema:\n{cobranca['erro']}\nTenta de novo mais tarde."
            )
            return

        registrar_pedido({
            "paymentId": cobranca["paymentId"],
            "usuario_id": usuario.id,
            "produto_id": produto_id,
            "valor_centavos": produto["valor_centavos"]
        })

        mensagem = (
            f"✅ *{produto['nome']}*\n"
            f"Valor: R$ {produto['valor_centavos']/100:.2f}\n\n"
            f"💳 Pague com esse código copia-e-cola:\n"
            f"`{cobranca['pix']['brCode']}`\n\n"
            f"📱 Pague pelo app do seu banco e o conteúdo chega aqui automaticamente!\n"
            f"⏳ Pode levar alguns minutos…"
        )

        await query.edit_message_text(mensagem, parse_mode="Markdown")

        qr_b64 = cobranca["pix"].get("qrCodeImage")
        if qr_b64:
            import base64
            from io import BytesIO
            imagem = BytesIO(base64.b64decode(qr_b64.replace("data:image/png;base64,", "")))
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=imagem,
                caption="📱 Ou escaneie pelo celular"
            )
        return

    # ==========================================
    # PASSO 3 — DESISTIU
    # ==========================================
    if query.data == "sair":
        await query.edit_message_text(
            "Tudo bem então 😘\nQuando tiver coragem de encarar, é só voltar… 🍑"
        )


if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(processo_compra, pattern=r"^(confirmar:|comprar:|sair)$"))
    
    print("✅ Bot rodando na nuvem! Aguardando mensagens...")
    application.run_polling(drop_pending_updates=True)
