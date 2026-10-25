import os
import requests
import json
import hmac
import hashlib
from dotenv import load_dotenv

load_dotenv()

PURINCASH_API_KEY = os.getenv("ps_live_0585c049183e39d4b4a5a25bed68e26d8422949ef0d27ae9fc5b6ea7f7cfead1")
PURINCASH_WEBHOOK_SECRET = os.getenv("f083f2aa6f38bb380894779fc1c3aaefab33d61705aa06d0")
PURINCASH_CALLBACK_URL = os.getenv("https://heloisamendesbot.onrender.com/webhook-purincash")

BASE_URL = "https://api.purincash.com/v1"

PRODUTOS = {
    "fotos": {
        "nome": "Pack de Fotos",
        "valor_centavos": 500,
        "entrega": "https://drive.google.com/drive/folders/1GPPoCyVd2k1XgEC_WWrzi43LciSlVtQF?usp=sharing"
    },
    "videos": {
        "nome": "Pack de Vídeos",
        "valor_centavos": 1200,
        "entrega": "https://drive.google.com/drive/folders/1M7UtYvfNt5Ue_m43RnLLyhCRNZ0txAwM?usp=sharing"
    }
}

def registrar_pedido(dados):
    import sqlite3
    conn = sqlite3.connect("pedidos.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            paymentId TEXT PRIMARY KEY,
            usuario_id INTEGER,
            produto_id TEXT,
            valor_centavos INTEGER,
            status TEXT DEFAULT 'pendente',
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        INSERT OR REPLACE INTO pedidos 
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

def gerar_cobranca(produto_id, usuario_id, nome_usuario, email_usuario):
    produto = PRODUTOS[produto_id]
    
    payload = {
        "amount": produto["valor_centavos"],
        "currency": "BRL",
        "description": f"{produto['nome']} — {nome_usuario}",
        "customer": {
            "name": nome_usuario,
            "email": email_usuario
        },
        "webhookUrl": PURINCASH_CALLBACK_URL,
        "metadata": {
            "usuario_id": usuario_id,
            "produto_id": produto_id
        }
    }
    
    headers = {
        "Authorization": f"Bearer {PURINCASH_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        resposta = requests.post(
            f"{BASE_URL}/charges",
            json=payload,
            headers=headers,
            timeout=15
        )
        resposta.raise_for_status()
        dados = resposta.json()
        
        return {
            "paymentId": dados["id"],
            "pix": {
                "brCode": dados["pix"]["qrcode"],
                "qrCodeImage": dados["pix"]["imageUrl"]
            }
        }
    except Exception as e:
        print(f"❌ Erro ao gerar cobrança: {e}")
        return {"erro": str(e)}
