import os
import json
import sqlite3
import time
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import hmac
import hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

load_dotenv()
app = Flask(__name__)

# ================= CONFIGURAÇÕES =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PURINCASH_API_KEY = os.getenv("PURINCASH_API_KEY")
PURINCASH_WEBHOOK_SECRET = os.getenv("PURINCASH_WEBHOOK_SECRET", "")
PURINCASH_CALLBACK_URL = os.getenv("PURINCASH_CALLBACK_URL")

# ================= PRODUTOS — EXATAMENTE COMO ERA =================
PRODUTOS = {
    "fotos": {
        "valor_centavos": 500,
        "entrega": "COLE_SEU_LINK_AQUI_FOTOS"
    },
    "videos": {
        "valor_centavos": 1200,
        "entrega": "COLE_SEU_LINK_AQUI_VIDEOS"
    }
}

# ================= BANCO DE DADOS =================
def init_db():
    conn = sqlite3.connect("pedidos.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS pedidos (
        payment_id TEXT PRIMARY KEY,
        usuario_id TEXT,
        produto_id TEXT,
        status TEXT DEFAULT 'pendente',
        criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

init_db()

def registrar_pedido(payment_id, usuario_id, produto_id):
    conn = sqlite3.connect("pedidos.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO pedidos VALUES (?, ?, ?, 'pendente', CURRENT_TIMESTAMP)",
              (payment_id, usuario_id, produto_id))
    conn.commit()
    conn.close()

def consultar_pedido(payment_id):
    conn = sqlite3.connect("pedidos.db")
    c = conn.cursor()
    c.execute("SELECT usuario_id, produto_id, status FROM pedidos WHERE payment_id = ?", (payment_id,))
    linha = c.fetchone()
    conn.close()
    if linha:
        return {"usuario_id": linha[0], "produto_id": linha[1], "status": linha[2]}
    return None

def entregar_produto(usuario_id, produto_id, payment_id, bot):
    produto = PRODUTOS[produto_id]
    conn = sqlite3.connect("pedidos.db")
    c = conn.cursor()
    c.execute("UPDATE pedidos SET status = 'entregue' WHERE payment_id = ?", (payment_id,))
    conn.commit()
    conn.close()
    try:
        import asyncio
        mensagem = (
            "🎉 *Pagamento confirmado!*\n\n"
            f"Aqui está o seu produto:\n\n"
            f"🔗 {produto['entrega']}\n\n"
            "Aproveita bem 😈💋🔥"
        )
        asyncio.run(bot.send_message(chat_id=usuario_id, text=mensagem, parse_mode="Markdown"))
        return True
    except Exception as e:
        print(f"Erro entrega: {e}")
        return False

# ================= ASSINATURA =================
def validar_assinatura(corpo_requisicao, assinatura_recebida):
    if not PURINCASH_WEBHOOK_SECRET:
        return True
    assinatura_esperada = hmac.new(
        key=PURINCASH_WEBHOOK_SECRET.encode("utf-8"),
        msg=corpo_requisicao,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(assinatura_esperada, assinatura_recebida)

# ================= FUNÇÃO CRIAR PIX =================
def criar_pagamento_pix(usuario_id, produto_id):
    try:
        url = "https://api.purincash.com/v1/payment"
        valor = PRODUTOS[produto_id]["valor_centavos"] / 100

        headers = {
            "Authorization": f"Bearer {PURINCASH_API_KEY}",
            "Content-Type": "application/json"
        }

        dados = {
            "amount": valor,
            "currency": "BRL",
            "description": f"Compra {produto_id} — {usuario_id}",
            "webhook_url": PURINCASH_CALLBACK_URL,
            "external_id": str(usuario_id)
        }

        resposta = requests.post(url, json=dados, headers=headers, timeout=30)
        print(f"📡 Status: {resposta.status_code}")
        if resposta.status_code != 200:
            print(f"📥 Erro: {resposta.text}")
        resposta.raise_for_status()
        return resposta.json()

    except Exception as e:
        print(f"❌ Erro ao criar PIX: {e}")
        return None

# ================= COMANDOS DO BOT =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "👋 Olá! Bem-vindo!\n\n"
        "Escolha o que deseja abaixo:"
    )
    teclado = [
        [InlineKeyboardButton("📸 Pack de Fotos — R$ 5,00", callback_data="comprar_fotos")],
        [InlineKeyboardButton("🎬 Pack de Vídeos — R$ 12,00", callback_data="comprar_videos")]
    ]
    await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(teclado))

async def processo_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)

    if query.data == "comprar_fotos":
        produto_id = "fotos"
        nome = "Pack de Fotos"
        valor = "5,00"
    elif query.data == "comprar_videos":
        produto_id = "videos"
        nome = "Pack de Vídeos"
        valor = "12,00"
    else:
        return

    await query.edit_message_text(
        f"✅ {nome} selecionado!\n"
        f"Valor: R$ {valor}\n\n"
        "Gerando seu código PIX..."
    )

    pix = criar_pagamento_pix(user_id, produto_id)

    if pix and "id" in pix and "qr_code" in pix:
        registrar_pedido(pix["id"], user_id, produto_id)
        await query.edit_message_text(
            f"✅ Pagamento gerado!\n\n"
            f"📦 {nome}\n"
            f"💰 Valor: R$ {valor}\n\n"
            "📱 Escaneie o QR Code ou copie o código abaixo:"
        )
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=f"`{pix['qr_code']}`",
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            "❌ Erro ao gerar pagamento.\n"
            "Tente novamente mais tarde."
        )

# ================= WEBHOOK =================
@app.route("/webhook-purincash", methods=["POST"])
def webhook():
    assinatura = request.headers.get("X-Webhook-Signature", "")
    corpo = request.get_data()

    if not validar_assinatura(corpo, assinatura):
        print("⚠️ Assinatura inválida")
        return jsonify({"erro": "assinatura inválida"}), 401

    dados = json.loads(corpo)
    tipo = dados.get("event")
    payment_id = dados.get("id")
    print(f"📥 Evento recebido: {tipo} — {payment_id}")

    if tipo not in ("charge.paid", "payment.paid"):
        return jsonify({"status": "ignorado"})

    pedido = consultar_pedido(payment_id)
    if not pedido:
        return jsonify({"erro": "pedido não encontrado"}), 404
    if pedido["status"] == "entregue":
        return jsonify({"status": "já entregue"})

    valor_pago = dados.get("amount", 0)
    valor_esperado = PRODUTOS[pedido["produto_id"]]["valor_centavos"]
    if valor_pago < valor_esperado:
        print(f"⚠️ Valor insuficiente: {valor_pago} < {valor_esperado}")
        return jsonify({"alerta": "valor insuficiente"}), 200

    entregar_produto(pedido["usuario_id"], pedido["produto_id"], payment_id, application.bot)
    return jsonify({"status": "sucesso"})

@app.route("/")
def home():
    return "✅ Webhook ativo e funcionando!"

# ================= INICIALIZAÇÃO =================
application = None

def main():
    global application

    for tentativa in range(5):
        try:
            print(f"🔄 Iniciando bot... ({tentativa+1}/5)")
            application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

            application.add_handler(CommandHandler("start", start))
            application.add_handler(CallbackQueryHandler(processo_compra))

            print("✅ Bot rodando! Aguardando mensagens...")

            application.run_polling(
                drop_pending_updates=True,
                close_loop=True,
                allowed_updates=["message", "callback_query"],
                bootstrap_retries=3
            )
            break

        except Exception as erro:
            print(f"⚠️ Erro: {erro}")
            time.sleep(5)

if __name__ == "__main__":
    from threading import Thread

    def rodar_flask():
        porta = int(os.getenv("PORT", 10000))
        app.run(host="0.0.0.0", port=porta)

    Thread(target=rodar_flask, daemon=True).start()
    main()
