import os
import time
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
import requests
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# ================= CONFIGURAÇÕES =================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PURINCASH_API_KEY = os.getenv("PURINCASH_API_KEY")
PURINCASH_WEBHOOK_SECRET = os.getenv("PURINCASH_WEBHOOK_SECRET")
PURINCASH_CALLBACK_URL = os.getenv("PURINCASH_CALLBACK_URL")

# Inicializa Flask para webhook
app = Flask(__name__)

# ================= FUNÇÕES DO BOT =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    texto = (
        "👋 Olá! Bem-vindo!\n\n"
        "Escolha uma opção abaixo:"
    )
    
    teclado = [
        [InlineKeyboardButton("💳 Comprar", callback_data="comprar")],
        [InlineKeyboardButton("ℹ️ Sobre", callback_data="sobre")]
    ]
    
    await update.message.reply_text(
        texto,
        reply_markup=InlineKeyboardMarkup(teclado)
    )

async def processo_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa os cliques dos botões"""
    query = update.callback_query
    await query.answer()

    if query.data == "comprar":
        await query.edit_message_text(
            "💰 Você escolheu comprar!\n"
            "Gerando seu código PIX..."
        )
        
        # Chama a função de criar PIX
        pix = criar_pagamento_pix(update.effective_user.id)
        
        if pix and "qr_code" in pix:
            texto = (
                "✅ Pagamento gerado!\n\n"
                f"Valor: R$ {pix.get('valor', '0,00')}\n"
                f"ID: {pix.get('id', '---')}\n\n"
                "📱 Escaneie o QR Code ou copie o código abaixo:"
            )
            await query.edit_message_text(texto)
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=f"`{pix['qr_code']}`",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                "❌ Erro ao gerar pagamento. Tente novamente mais tarde."
            )

    elif query.data == "sobre":
        await query.edit_message_text(
            "ℹ️ Sobre o Bot\n\n"
            "Bot de pagamentos via PIX integrado com PurinCash.\n"
            "Pagamento confirmado automaticamente!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("← Voltar", callback_data="inicio")
            ]])
        )
    
    elif query.data == "inicio":
        await start(update, context)

def criar_pagamento_pix(user_id):
    """Cria o pagamento na PurinCash"""
    try:
        url = "https://api.purincash.com/v1/payment"
        
        headers = {
            "Authorization": f"Bearer {PURINCASH_API_KEY}",
            "Content-Type": "application/json"
        }
        
        dados = {
            "amount": 10.00,  # Valor do produto/serviço
            "currency": "BRL",
            "description": f"Compra - Usuário {user_id}",
            "webhook_url": PURINCASH_CALLBACK_URL,
            "external_id": str(user_id)
        }
        
        resposta = requests.post(url, json=dados, headers=headers, timeout=30)
        resposta.raise_for_status()
        return resposta.json()
        
    except Exception as e:
        print(f"Erro ao criar PIX: {e}")
        return None

# ================= WEBHOOK =================

@app.route("/webhook-purincash", methods=["POST"])
def webhook_purincash():
    """Recebe confirmação de pagamento da PurinCash"""
    try:
        assinatura = request.headers.get("X-Webhook-Signature", "")
        
        # Verifica se o segredo confere
        if assinatura != PURINCASH_WEBHOOK_SECRET:
            return jsonify({"status": "erro", "mensagem": "Assinatura inválida"}), 403
        
        dados = request.json
        status = dados.get("status")
        user_id = dados.get("external_id")
        
        if status == "paid" and user_id:
            # Envia mensagem de confirmação pro usuário
            mensagem = (
                "✅ PAGAMENTO CONFIRMADO!\n\n"
                "Obrigado pela compra! 🎉\n"
                "Aqui está o que você comprou..."
            )
            # Envia a mensagem via bot
            import asyncio
            from telegram.error import TelegramError
            
            async def enviar():
                try:
                    await application.bot.send_message(chat_id=user_id, text=mensagem)
                except TelegramError as e:
                    print(f"Não foi possível avisar o usuário {user_id}: {e}")
            
            asyncio.run(enviar())
        
        return jsonify({"status": "recebido"}), 200
        
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return jsonify({"erro": str(e)}), 500

# ================= INICIALIZAÇÃO =================

application = None

def main():
    global application
    
    max_tentativas = 5
    intervalo = 5  # segundos
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔄 Iniciando bot... (tentativa {tentativa+1}/{max_tentativas})")
            
            application = ApplicationBuilder().token(BOT_TOKEN).build()
            
            # Registra handlers
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CallbackQueryHandler(processo_compra))
            
            print("✅ Bot rodando! Aguardando mensagens...")
            
            # Inicia polling com proteção contra conflito
            application.run_polling(
                drop_pending_updates=True,
                close_loop=True,
                allowed_updates=["message", "callback_query"],
                bootstrap_retries=3
            )
            break  # Se chegou aqui, deu certo!
            
        except Exception as erro:
            print(f"⚠️ Erro: {erro}")
            if tentativa < max_tentativas - 1:
                print(f"⏳ Tentando novamente em {intervalo}s...")
                time.sleep(intervalo)
            else:
                print("❌ Falha após várias tentativas. Verifique o token!")

if __name__ == "__main__":
    # Inicia servidor Flask em paralelo (se necessário)
    from threading import Thread
    
    def rodar_flask():
        porta = int(os.getenv("PORT", 10000))
        app.run(host="0.0.0.0", port=porta)
    
    Thread(target=rodar_flask, daemon=True).start()
    
    main()
