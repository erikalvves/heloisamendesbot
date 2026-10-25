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

# ================= PRODUTOS =================
PRODUTOS = {
    "fotos": {
        "valor_centavos": 500,
        "valor_exibicao": "5,00",
        "nome": "Pack de Fotos",
        "descricao": "Aqui estão as fotos mais ousadas...",
        "entrega": "COLE_SEU_LINK_AQUI_FOTOS"
    },
    "videos": {
        "valor_centavos": 1200,
        "valor_exibicao": "12,00",
        "nome": "Pack de Vídeos",
        "descricao": "Vídeos exclusivos esperando por você...",
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

# ================= CRIAR PAGAMENTO =================
def criar_pagamento_pix(usuario_id, produto_id):
    try:
        url = "https://api.purincash.com/v1/payment"
        valor = PRODUTOS[produto_id]["valor_centavos"] / 100

        headers = {
            "Authorization": f"Bearer {PURINCASH_API_KEY}",
            "Content-Type": "application/json"
        }

        if not PURINCASH_API_KEY:
            print("❌ PURINCASH_API_KEY não configurada!")
            return None

        dados = {
            "amount": valor,
            "currency": "BRL",
            "description": f"Compra {produto_id} — {usuario_id}",
            "webhook_url": PURINCASH_CALLBACK_URL,
            "external_id": str(usuario_id)
        }

        print(f"📤 Enviando: {dados}")
        resposta = requests.post(url, json=dados, headers=headers, timeout=30)
        print(f"📡 Status: {resposta.status_code}")
        
        if resposta.status_code != 200:
            print(f"📥 Erro: {resposta.text}")
            return None
            
        return resposta.json()

    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

# ================= MENSAGEM INICIAL =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "😈💋 Olá, safado… Veio me procurar, né? KKKK 🤭🔥\n"
        "Aqui você encontra meus packs +18 com as fotos e vídeos mais ousados… "
        "vem matar essa curiosidade 😏🍑🔞\n\n"
        "Escolha o produto que deseja:"
    )
    teclado = [
        [InlineKeyboardButton("📸 Pack de Fotos — R$ 5,00", callback_data="comprar_fotos")],
        [InlineKeyboardButton("🎬 Pack de Vídeos — R$ 12,00", callback_data="comprar_videos")]
    ]
    await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(teclado))

# ================= FLUXO DE COMPRA COM CONFIRMAÇÃO =================
async def processo_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)

    # 1️⃣ Usuário escolheu o produto → mostra prévia + confirmação
    if query.data.startswith("comprar_"):
        produto_id = query.data.replace("comprar_", "")
        prod = PRODUTOS[produto_id]
        
        texto = (
            f"📦 {prod['nome']}\n"
            f"💰 Valor: R$ {prod['valor_exibicao']}\n\n"
            f"{prod['descricao']}\n\n"
            "Confirma a compra?"
        )
        
        teclado = [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data=f"confirmar_{produto_id}"),
                InlineKeyboardButton("← Voltar", callback_data="inicio")
            ]
        ]
        
        await query.edit_message_text(
            texto,
            reply_markup=InlineKeyboardMarkup(teclado)
        )
        return

    # 2️⃣ Usuário confirmou → gera o PIX
    if query.data.startswith("confirmar_"):
        produto_id = query.data.replace("confirmar_", "")
        prod = PRODUTOS[produto_id]
        
        await query.edit_message_text(
            f"✅ {prod['nome']} confirmado!\n"
            f"Valor: R$ {prod['valor_exibicao']}\n\n"
            "Gerando seu código PIX..."
        )

        pix = criar_pagamento_pix(user_id, produto_id)

        if pix and "id" in pix and "qr_code" in pix:
            registrar_pedido(pix["id"], user_id, produto_id)
            await query.edit_message_text(
                f"✅ Pagamento gerado!\n\n"
                f"📦 {prod['nome']}\n"
                f"💰 Valor: R$ {prod['valor_exibicao']}\n\n"
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
                "Verifique as chaves da PurinCash e tente novamente."
            )
        return

    # 3️⃣ Voltar ao início
    if query.data == "inicio":
        await start(update, context)
        return

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
